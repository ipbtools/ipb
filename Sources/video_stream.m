// ipb-video: pull live screen frames from a physical iPhone with no DeviceHub and no injection.
//
// Pipeline (all reverse-engineered; see docs/video-stream.md and docs/verification.md 2026-09-08):
//   raw RemoteXPC createservicesocket -> dtremotedisplayd
//   AVCMediaStreamNegotiator mode 5 (CoreDeviceScreenSharing) -> createOffer
//   our own AF_INET6 UDP socket bound on the host tunnel address
//   mediastreamstart { options: { avcMediaStreamOptionClientSessionID: .uuid } }
//   setAnswer -> generateMediaStreamConfiguration -> generateMediaStreamInitOptions
//   MSG_PEEK the first RTP datagram, connect() the socket to the device's RTP source
//   xpc_dictionary_set_fd(socks,"avcKeySharedSocket",fd) -> AVCVideoStream initWithNetworkSockets:options:
//   -[AVCVideoStream requestLastDecodedFrame] -> delegate stream:didGetLastDecodedFrame: -> baseline JPEG NSData
//
// Decode runs out-of-process in the system daemon avconferenced, which gates the client on the
// entitlement com.apple.videoconference.allow-conferencing (see docs; distribution caveat).
//
// Exit codes: 0 ok; 2 usage/setup; 3 socket/service refused; 4 tunnel down; 5 negotiation rejected;
//             6 stream did not start; 7 no frames within the watchdog window.

#import <Foundation/Foundation.h>
#import <CoreMedia/CoreMedia.h>
#import <CoreVideo/CoreVideo.h>
#import <objc/runtime.h>
#import <CoreImage/CoreImage.h>
#import <ImageIO/ImageIO.h>
#import <CoreServices/CoreServices.h>
#include <xpc/xpc.h>
#include <uuid/uuid.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <net/if.h>
#include <string.h>
#include <errno.h>
#include <dlfcn.h>

#define LOGE(...) do{ fprintf(stderr, "ipb-video: " __VA_ARGS__); fprintf(stderr,"\n"); }while(0)
#define DIE(code, ...) do{ LOGE(__VA_ARGS__); return (code); }while(0)

extern void _coredevice_xpc_add_bundle(NSBundle*);
extern void _coredevice_xpc_init_services(void);
typedef void *xrc_t;
extern xrc_t xpc_remote_connection_create_with_connected_fd(int,dispatch_queue_t,uint64_t,uint64_t);
extern void xpc_remote_connection_set_event_handler(xrc_t,xpc_handler_t);
extern void xpc_remote_connection_activate(xrc_t);
extern xpc_object_t xpc_remote_connection_send_message_with_reply_sync(xrc_t,xpc_object_t);

@interface AVCMediaStreamNegotiator : NSObject
- (instancetype)initWithMode:(long)mode options:(NSDictionary*)o error:(NSError**)e;
- (BOOL)createOffer; - (NSData*)offer;
- (BOOL)setAnswer:(NSData*)a withError:(NSError**)e;
- (id)generateMediaStreamConfigurationWithError:(NSError**)e;
- (id)generateMediaStreamInitOptionsWithError:(NSError**)e;
@end
@interface AVCVideoStream : NSObject
- (instancetype)initWithNetworkSockets:(id)socks options:(id)opts error:(NSError**)e;
- (BOOL)configure:(id)cfg error:(NSError**)e;
- (void)setDelegate:(id)d;
- (void)start;
- (void)stop;
- (void)requestLastDecodedFrame;
@end
@interface VCImageQueue : NSObject
- (long long)streamToken;
- (id)streamOutput;
- (void)setStreamOutput:(id)o;
@end
@interface VCStreamOutput : NSObject
- (instancetype)initWithStreamToken:(long long)t clientProcessID:(int)pid delegate:(id)d delegateQueue:(dispatch_queue_t)q;
@end

// ---- frame sink ----
static NSString *gOutDir;          // write frame%06d.jpg here, or nil
static int gMaxFrames = 0;         // stop after N distinct frames (0 = until timeout)
static double gMinInterval = 0;    // seconds between saved frames (fps limiter)
static BOOL gStdout = NO;          // stream frames to stdout as [4-byte BE length][jpeg]...
static int gSaved = 0, gPulls = 0;
static unsigned long gPrevHash = 0;
static double gLastSaveT = 0, gDeadlineExtend = 0;
static AVCVideoStream *gStream = nil;
static double gStopAt = 0;
static BOOL gDaemon = NO;   // --daemon: decode in avconferenced (needs entitlement); default is in-process

static double nowSec(void){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC,&ts); return ts.tv_sec+ts.tv_nsec/1e9; }
static unsigned long fnv(const void*d,size_t n){ const unsigned char*p=d; unsigned long h=1469598103934665603UL; for(size_t i=0;i<n;i+=1024){h^=p[i];h*=1099511628211UL;} return h; }

static CIContext *gCI = nil;
static void emitJPEG(NSData *jpeg);   // fwd

// Encode a decoded CVPixelBuffer to baseline JPEG and emit it.
static void emitPixelBuffer(CVImageBufferRef px){
    if(!px) return;
    @autoreleasepool{
        if(!gCI) gCI=[CIContext contextWithOptions:nil];
        CIImage *ci=[CIImage imageWithCVImageBuffer:px];
        CGColorSpaceRef cs=CGColorSpaceCreateDeviceRGB();
        NSData *jpeg=[gCI JPEGRepresentationOfImage:ci colorSpace:cs options:@{}];
        CGColorSpaceRelease(cs);
        if(jpeg.length) emitJPEG(jpeg);
    }
}

// In-process sink: VCImageQueue forwards every decoded frame to our VCStreamOutput delegate.
static id gImageQueue = nil;   // captured live VCImageQueue
@interface InProcSink : NSObject @end
@implementation InProcSink
- (void)didReceiveSampleBuffer:(CMSampleBufferRef)sb { if(sb) emitPixelBuffer(CMSampleBufferGetImageBuffer(sb)); }
- (void)streamOutput:(id)o didReceiveSampleBuffer:(CMSampleBufferRef)sb { [self didReceiveSampleBuffer:sb]; }
@end
static IMP gOrigIQStart;
static void swz_iq_start(id self, SEL _cmd){
    gImageQueue = self;
    if(![(VCImageQueue*)self streamOutput]){
        Class SO=objc_getClass("VCStreamOutput");
        if(SO){ static InProcSink *sink; if(!sink) sink=[InProcSink new];
            id so=[[SO alloc] initWithStreamToken:[(VCImageQueue*)self streamToken] clientProcessID:getpid()
                                          delegate:sink delegateQueue:dispatch_get_global_queue(0,0)];
            if(so) [(VCImageQueue*)self setStreamOutput:so]; }
    }
    ((void(*)(id,SEL))gOrigIQStart)(self,_cmd);
}
static void installInProcessSink(void){
    Class C=objc_getClass("VCImageQueue"); if(!C){ LOGE("no VCImageQueue class"); return; }
    Method m=class_getInstanceMethod(C,sel_registerName("start"));
    if(m){ gOrigIQStart=method_getImplementation(m); method_setImplementation(m,(IMP)swz_iq_start); }
}

// Emit one JPEG frame (dedup by content, honour --fps / --count / output sink). Thread-safe enough
// for a single delivery queue; both the in-process sink and the daemon pull funnel through here.
static void emitJPEG(NSData *jpeg){
    if(!jpeg.length) return;
    unsigned long h=fnv(jpeg.bytes,jpeg.length);
    double t=nowSec();
    if(h==gPrevHash) return;                                   // identical frame; skip
    if(gMinInterval>0 && (t-gLastSaveT)<gMinInterval) return;  // fps cap
    gPrevHash=h; gLastSaveT=t;
    if(gStdout){ uint32_t n=htonl((uint32_t)jpeg.length); fwrite(&n,4,1,stdout); fwrite(jpeg.bytes,1,jpeg.length,stdout); fflush(stdout); }
    if(gOutDir){ NSString*p=[gOutDir stringByAppendingPathComponent:[NSString stringWithFormat:@"frame%06d.jpg",gSaved]]; [jpeg writeToFile:p atomically:NO]; }
    gSaved++; gDeadlineExtend=t;
    if(gMaxFrames>0 && gSaved>=gMaxFrames){ if(gStream) [gStream stop]; gStopAt=t; }
}

@interface FrameSink : NSObject @end
@implementation FrameSink
- (void)stream:(id)s didStart:(BOOL)ok error:(NSError*)e {
    if(!ok) LOGE("stream did not start: %s", e?e.description.UTF8String:"(nil)");
}
- (void)stream:(id)s didGetLastDecodedFrame:(id)f {
    gPulls++;
    if([f isKindOfClass:[NSData class]]) emitJPEG((NSData*)f);
    if(gStream && (gStopAt==0)) [gStream requestLastDecodedFrame];   // pipeline next pull
}
- (void)streamDidStop:(id)s {}
- (void)vcMediaStreamDidStop:(id)s {}
- (void)streamDidServerDie:(id)s { LOGE("media server (avconferenced) closed the stream"); }
@end

static xpc_object_t action_env(const char*action,const char*dev,xpc_object_t input){
    uuid_t u; uuid_generate(u); char us[37]; uuid_unparse_upper(u,us);
    xpc_object_t m=xpc_dictionary_create_empty();
    xpc_dictionary_set_string(m,"CoreDevice.actionIdentifier",action);
    xpc_dictionary_set_string(m,"CoreDevice.deviceIdentifier",dev);
    xpc_dictionary_set_string(m,"CoreDevice.invocationIdentifier",us);
    xpc_object_t ver=xpc_dictionary_create_empty(); xpc_object_t comps=xpc_array_create_empty();
    xpc_array_append_value(comps,xpc_uint64_create(642)); xpc_array_append_value(comps,xpc_uint64_create(15));
    xpc_dictionary_set_value(ver,"components",comps); xpc_dictionary_set_int64(ver,"originalComponentsCount",2);
    xpc_dictionary_set_string(ver,"stringValue","642.15");
    xpc_dictionary_set_value(m,"CoreDevice.coreDeviceVersion",ver);
    xpc_dictionary_set_int64(m,"CoreDevice.CoreDeviceDDIProtocolVersion",1);
    xpc_dictionary_set_value(m,"CoreDevice.input",input);
    return m;
}

static void usage(void){
    fprintf(stderr,
      "usage: ipb-video <coredevice-uuid> <utun> <hostIP> <deviceIP> [options]\n"
      "  --dir DIR       write frames as DIR/frame%%06d.jpg\n"
      "  --stdout        stream frames to stdout: repeated [uint32 BE length][jpeg bytes]\n"
      "  --count N       stop after N distinct frames (default: run until --seconds)\n"
      "  --fps F         cap saved frames to at most F per second\n"
      "  --seconds S     run for S seconds (default 10; ignored once --count is met)\n"
      "  --daemon        decode in avconferenced instead of in-process (needs entitlement)\n");
}

int main(int argc,char**argv){
    setbuf(stderr,NULL);
    if(argc<5){ usage(); return 2; }
    const char*dev=argv[1]; const char*utun=argv[2]; const char*rxip=argv[3]; const char*txip=argv[4];
    double runSeconds = 10.0;
    for(int i=5;i<argc;i++){
        if(!strcmp(argv[i],"--dir") && i+1<argc) gOutDir=[NSString stringWithUTF8String:argv[++i]];
        else if(!strcmp(argv[i],"--stdout")) gStdout=YES;
        else if(!strcmp(argv[i],"--count") && i+1<argc) gMaxFrames=atoi(argv[++i]);
        else if(!strcmp(argv[i],"--fps") && i+1<argc){ double f=atof(argv[++i]); if(f>0) gMinInterval=1.0/f; }
        else if(!strcmp(argv[i],"--seconds") && i+1<argc) runSeconds=atof(argv[++i]);
        else if(!strcmp(argv[i],"--daemon")) gDaemon=YES;
        else { usage(); return 2; }
    }
    if(!gOutDir && !gStdout){ LOGE("nothing to do: pass --dir or --stdout"); return 2; }
    if(gOutDir) [[NSFileManager defaultManager] createDirectoryAtPath:gOutDir withIntermediateDirectories:YES attributes:nil error:nil];

    if(!dlopen("/Library/Developer/PrivateFrameworks/CoreDevice.framework/Versions/A/CoreDevice",RTLD_NOW)) DIE(2,"CoreDevice dlopen: %s",dlerror());
    if(!dlopen("/System/Library/PrivateFrameworks/AVConference.framework/Versions/A/AVConference",RTLD_NOW)) DIE(2,"AVConference dlopen: %s",dlerror());
    _coredevice_xpc_add_bundle([NSBundle bundleWithPath:@"/Library/Developer/PrivateFrameworks/CoreDevice.framework"]);
    _coredevice_xpc_init_services();

    NSString *sessID = [[NSUUID UUID] UUIDString];
    Class N = objc_getClass("AVCMediaStreamNegotiator"); if(!N) DIE(2,"no AVCMediaStreamNegotiator");
    NSError *e=nil;
    id neg=[[N alloc] initWithMode:5 options:@{} error:&e];   // 5 = CoreDeviceScreenSharing
    if(!neg) DIE(2,"negotiator init: %s",e.description.UTF8String);
    if(![neg createOffer]) DIE(2,"createOffer failed");
    NSData *offer=[neg offer]; if(!offer.length) DIE(2,"empty offer");

    dispatch_queue_t q=dispatch_queue_create("ipb.video.cds",0);
    xpc_connection_t c=xpc_connection_create("com.apple.CoreDevice.CoreDeviceService",q);
    xpc_connection_set_event_handler(c,^(xpc_object_t x){});
    xpc_connection_resume(c);
    xpc_object_t in0=xpc_dictionary_create_empty();
    xpc_dictionary_set_string(in0,"featureIdentifier","com.apple.coredevice.feature.startmediastream");
    xpc_object_t rep=xpc_connection_send_message_with_reply_sync(c,action_env("com.apple.coredevice.action.createservicesocket",dev,in0));
    xpc_object_t out=xpc_dictionary_get_dictionary(rep,"CoreDevice.output");
    if(!out) DIE(3,"createservicesocket: no output (device/service unavailable)");
    int sfd=xpc_dictionary_dup_fd(out,"fileDescriptor");
    uint64_t flags=xpc_dictionary_get_uint64(out,"remoteXPCVersionFlags");
    if(sfd<0) DIE(3,"no service fd");
    xrc_t rc=xpc_remote_connection_create_with_connected_fd(sfd,dispatch_queue_create("ipb.video.rc",0),flags,0);
    xpc_remote_connection_set_event_handler(rc,^(xpc_object_t ev){});
    xpc_remote_connection_activate(rc);

    int rtp=socket(AF_INET6,SOCK_DGRAM,0); if(rtp<0) DIE(3,"socket: %s",strerror(errno));
    int one=1; setsockopt(rtp,SOL_SOCKET,SO_REUSEADDR,&one,sizeof one); setsockopt(rtp,SOL_SOCKET,SO_REUSEPORT,&one,sizeof one);
    struct sockaddr_in6 la; memset(&la,0,sizeof la); la.sin6_len=sizeof la; la.sin6_family=AF_INET6;
    if(inet_pton(AF_INET6,rxip,&la.sin6_addr)!=1) DIE(2,"bad host IP %s",rxip);
    la.sin6_scope_id=if_nametoindex(utun); if(!la.sin6_scope_id) DIE(4,"no tunnel interface %s (is the device connected?)",utun);
    if(bind(rtp,(struct sockaddr*)&la,sizeof la)!=0) DIE(4,"bind [%s%%%s]: %s",rxip,utun,strerror(errno));
    socklen_t sl=sizeof la; if(getsockname(rtp,(struct sockaddr*)&la,&sl)!=0) DIE(3,"getsockname: %s",strerror(errno));
    uint16_t rxport=ntohs(la.sin6_port); if(!rxport) DIE(3,"no bound port");

    xpc_object_t in=xpc_dictionary_create_empty();
    xpc_dictionary_set_string(in,"receiverIP",rxip); xpc_dictionary_set_uint64(in,"receiverPort",rxport);
    xpc_dictionary_set_string(in,"senderIP",txip); xpc_dictionary_set_uint64(in,"senderPort",51000);
    xpc_dictionary_set_uint64(in,"timeout",30);
    xpc_dictionary_set_string(in,"type","video"); xpc_dictionary_set_string(in,"direction","output");
    xpc_dictionary_set_data(in,"negotiatorOffer",offer.bytes,offer.length);
    xpc_dictionary_set_uint64(in,"clientSupportedFeatures",972);
    xpc_object_t opts=xpc_dictionary_create_empty();
    uuid_t sessUU; uuid_parse(sessID.UTF8String, sessUU);
    xpc_object_t cvUUID=xpc_dictionary_create_empty(); xpc_dictionary_set_uuid(cvUUID,"uuid",sessUU);
    xpc_dictionary_set_value(opts,"avcMediaStreamOptionClientSessionID",cvUUID);
    xpc_dictionary_set_value(in,"options",opts);

    xpc_object_t srep=xpc_remote_connection_send_message_with_reply_sync(rc,action_env("com.apple.coredevice.action.mediastreamstart",dev,in));
    if(!srep) DIE(5,"mediastreamstart: null reply");
    xpc_object_t serr=xpc_dictionary_get_dictionary(srep,"CoreDevice.error");
    if(serr){ int64_t code=xpc_dictionary_get_int64(serr,"code"); const char*dom=xpc_dictionary_get_string(serr,"domain");
              DIE(5,"device rejected mediastreamstart: %s %lld",dom?dom:"?",(long long)code); }
    xpc_object_t so=xpc_dictionary_get_dictionary(srep,"CoreDevice.output");
    if(!so) DIE(5,"mediastreamstart: no output");
    size_t alen=0; const void*ans=xpc_dictionary_get_data(so,"negotiatorAnswer",&alen);
    if(!ans) ans=xpc_dictionary_get_data(so,"answer",&alen);
    if(!ans) DIE(5,"no negotiator answer from device");
    NSError *ae=nil;
    if(![neg setAnswer:[NSData dataWithBytes:ans length:alen] withError:&ae]) DIE(5,"setAnswer: %s",ae?ae.description.UTF8String:"?");
    id cfg=[neg generateMediaStreamConfigurationWithError:&ae]; if(!cfg) DIE(5,"generateConfiguration: %s",ae?ae.description.UTF8String:"?");
    id initOpts=[neg generateMediaStreamInitOptionsWithError:&ae]; if(!initOpts) DIE(5,"generateInitOptions: %s",ae?ae.description.UTF8String:"?");

    // learn the device's RTP source (MSG_PEEK, do not consume) and connect the socket to it
    struct timeval ptv={8,0}; setsockopt(rtp,SOL_SOCKET,SO_RCVTIMEO,&ptv,sizeof ptv);
    uint8_t pk[4]; struct sockaddr_in6 peer; socklen_t pl=sizeof peer;
    ssize_t pn=recvfrom(rtp,pk,sizeof pk,MSG_PEEK,(struct sockaddr*)&peer,&pl);
    if(pn<=0) DIE(6,"no RTP from device within 8s (peek: %s)",strerror(errno));
    if(connect(rtp,(struct sockaddr*)&peer,sizeof peer)!=0) DIE(6,"connect to RTP peer: %s",strerror(errno));

    NSMutableDictionary *o2=[NSMutableDictionary dictionary];
    if([initOpts isKindOfClass:[NSDictionary class]]) [o2 addEntriesFromDictionary:initOpts];
    o2[@"avcMediaStreamOptionRunInProcess"]=@(gDaemon ? NO : YES);   // default: decode in-process (no entitlement)
    o2[@"avcMediaStreamOptionClientName"]=@"CoreDeviceScreenSharing";
    o2[@"avcMediaStreamOptionClientSessionID"]=[[NSUUID alloc] initWithUUIDString:sessID];

    xpc_object_t socks=xpc_dictionary_create_empty();
    xpc_dictionary_set_fd(socks,"avcKeySharedSocket",rtp);
    if(!gDaemon) installInProcessSink();  // in-process capture (needs a GUI display session)
    Class VS=objc_getClass("AVCVideoStream"); if(!VS) DIE(6,"no AVCVideoStream class");
    NSError *se=nil;
    AVCVideoStream *vs=[[VS alloc] initWithNetworkSockets:(id)socks options:o2 error:&se];
    if(!vs) DIE(6,"AVCVideoStream init: %s",se?se.description.UTF8String:"?");
    FrameSink *sink=[FrameSink new];
    [vs setDelegate:sink];
    NSError *ce=nil; if(![vs configure:cfg error:&ce]) DIE(6,"configure: %s",ce?ce.description.UTF8String:"?");
    [vs start];
    gStream=vs;

    // warm up, then collect frames; in-process frames arrive by push, daemon frames by pull.
    double t0=nowSec(); gLastSaveT=t0; gDeadlineExtend=t0;
    for(int w=0; w<50; w++) [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.05]];  // ~2.5s
    if(gDaemon) [vs requestLastDecodedFrame];
    double start=nowSec();
    while(1){
        [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.05]];
        double t=nowSec();
        if(gStopAt) break;
        if(gMaxFrames==0 && (t-start) >= runSeconds) break;
        if(gDaemon && gStream && (t-gDeadlineExtend) > 2.0){ gDeadlineExtend=t; [vs requestLastDecodedFrame]; }  // daemon: re-arm on stall
        if((t-gDeadlineExtend) > 12.0) break;  // hard stall guard (no frames at all)
    }
    [vs stop];
    LOGE("saved %d distinct frame(s) from %d pull(s)", gSaved, gPulls);
    return gSaved>0 ? 0 : 7;
}
