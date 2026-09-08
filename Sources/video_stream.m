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
//             6 stream did not start/server died; 7 no frames within the watchdog window;
//             8 output failed/incomplete (including undrained consumer or unmet count);
//             9 process watchdog expired (setup, framework call, or shutdown stalled).

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
#include <pthread.h>
#include <signal.h>
#include <math.h>
#include <unistd.h>

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
static double gLastSaveT = 0;       // writer-owned
static double gLastOutputT = 0, gLastRequestT = 0; // protected by gFrameLock
static AVCVideoStream *gStream = nil;
static pthread_mutex_t gFrameLock = PTHREAD_MUTEX_INITIALIZER;
static dispatch_queue_t gDelegateQueue, gWriterQueue;
static dispatch_group_t gWriterGroup;
static CMSampleBufferRef gLatest = NULL; // one owned CF reference, protected by gFrameLock
static NSData *gLatestJPEG;             // daemon's alternative pending frame (ARC-owned)
static CMTime gNewestPTS;               // protected by gFrameLock
static BOOL gBusy = NO, gStopping = NO;
static unsigned long gBackpressureDrops = 0;
static unsigned long gInvalidPTS = 0, gNonIncreasingPTS = 0;
static int gFailure = 0;               // protected by gFrameLock
static int gReportedSaved = 0;          // locked snapshot; gSaved belongs to the writer

// Caller holds gFrameLock. Never call AVConference or wait for the writer under this lock.
static void stopFramesLocked(void){
    gStopping=YES;
    if(gLatest){ CFRelease(gLatest); gLatest=NULL; }
    gLatestJPEG=nil;
}
static BOOL gDaemon = NO;   // --daemon: decode in avconferenced (needs entitlement); default is in-process

static double nowSec(void){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC,&ts); return ts.tv_sec+ts.tv_nsec/1e9; }
static unsigned long fnv(const void*d,size_t n){ const unsigned char*p=d; unsigned long h=1469598103934665603UL; for(size_t i=0;i<n;i+=1024){h^=p[i];h*=1099511628211UL;} return h; }

static CIContext *gCI = nil;
static void emitJPEG(NSData *jpeg);   // fwd

// Encode a decoded CVPixelBuffer to baseline JPEG and emit it.
static void emitPixelBuffer(CVImageBufferRef px){
    if(!px) return;
    @autoreleasepool{
        CIImage *ci=[CIImage imageWithCVImageBuffer:px];
        CGColorSpaceRef cs=CGColorSpaceCreateDeviceRGB();
        NSData *jpeg=[gCI JPEGRepresentationOfImage:ci colorSpace:cs options:@{}];
        CGColorSpaceRelease(cs);
        if(jpeg.length) emitJPEG(jpeg);
    }
}

// Exactly one worker drains the latest slot. Taking a frame and clearing busy on an
// empty slot use the same lock as submission, so a submit cannot lose its wakeup.
static void wakeWriterLocked(void){
    if(gBusy || gStopping) return;
    gBusy=YES;
    dispatch_group_async(gWriterGroup,gWriterQueue,^{
        for(;;){
            @autoreleasepool{
                pthread_mutex_lock(&gFrameLock);
                CMSampleBufferRef sb=gLatest;
                NSData *jpeg=gLatestJPEG;
                gLatest=NULL; gLatestJPEG=nil;
                if(!sb && !jpeg){
                    gBusy=NO;
                    pthread_mutex_unlock(&gFrameLock);
                    return;
                }
                pthread_mutex_unlock(&gFrameLock);
                // Apply the fps cap before the expensive pixel-buffer JPEG encoding.
                if(gMinInterval<=0 || nowSec()-gLastSaveT>=gMinInterval){
                    if(sb) emitPixelBuffer(CMSampleBufferGetImageBuffer(sb));
                    else emitJPEG(jpeg);
                }
                if(sb) CFRelease(sb); // ownership transferred out of the pending slot
                if(gDaemon) dispatch_async(dispatch_get_main_queue(),^{
                    pthread_mutex_lock(&gFrameLock);
                    BOOL active=!gStopping;
                    if(active) gLastRequestT=nowSec();
                    pthread_mutex_unlock(&gFrameLock);
                    if(active) [gStream requestLastDecodedFrame];
                });
            }
        }
    });
}

// In-process sink: VCImageQueue forwards every decoded frame to our VCStreamOutput delegate.
static id gImageQueue = nil;   // captured live VCImageQueue
@interface InProcSink : NSObject @end
@implementation InProcSink
- (void)didReceiveSampleBuffer:(CMSampleBufferRef)sb {
    if(!sb) return;
    CMTime pts=CMSampleBufferGetPresentationTimeStamp(sb);
    pthread_mutex_lock(&gFrameLock);
    // Reject invalid/late timestamps before they can replace a newer pending frame.
    if(gStopping){
        // Shutdown callbacks do not count as timestamp drops.
    }else if(!CMTIME_IS_NUMERIC(pts)){
        gInvalidPTS++;
    }else if(CMTIME_IS_NUMERIC(gNewestPTS) && CMTimeCompare(pts,gNewestPTS)<=0){
        gNonIncreasingPTS++;
    }else{
        gNewestPTS=pts;
        CFRetain(sb);
        if(gLatest){ CFRelease(gLatest); gBackpressureDrops++; }
        gLatest=sb;
        wakeWriterLocked();
    }
    pthread_mutex_unlock(&gFrameLock);
}
- (void)streamOutput:(id)o didReceiveSampleBuffer:(CMSampleBufferRef)sb { [self didReceiveSampleBuffer:sb]; }
@end
static IMP gOrigIQStart;
static void swz_iq_start(id self, SEL _cmd){
    gImageQueue = self;
    if(![(VCImageQueue*)self streamOutput]){
        Class SO=objc_getClass("VCStreamOutput");
        if(SO){ static InProcSink *sink; if(!sink) sink=[InProcSink new];
            id so=[[SO alloc] initWithStreamToken:[(VCImageQueue*)self streamToken] clientProcessID:getpid()
                                          delegate:sink delegateQueue:gDelegateQueue];
            if(so) [(VCImageQueue*)self setStreamOutput:so]; }
    }
    ((void(*)(id,SEL))gOrigIQStart)(self,_cmd);
}
static void installInProcessSink(void){
    Class C=objc_getClass("VCImageQueue"); if(!C){ LOGE("no VCImageQueue class"); return; }
    Method m=class_getInstanceMethod(C,sel_registerName("start"));
    if(m){ gOrigIQStart=method_getImplementation(m); method_setImplementation(m,(IMP)swz_iq_start); }
}

// Only the writer calls this function, for both in-process and daemon frames.
static void emitJPEG(NSData *jpeg){
    if(!jpeg.length) return;
    unsigned long h=fnv(jpeg.bytes,jpeg.length);
    double t=nowSec();
    if(h==gPrevHash) return;                                   // identical frame; skip
    BOOL ok=YES;
    if(gStdout){
        uint32_t n=htonl((uint32_t)jpeg.length);
        ok=jpeg.length<=UINT32_MAX && fwrite(&n,1,4,stdout)==4 &&
           fwrite(jpeg.bytes,1,jpeg.length,stdout)==jpeg.length && fflush(stdout)==0;
        if(!ok) LOGE("stdout write/flush failed: %s",strerror(errno));
    }
    if(ok && gOutDir){
        NSString*p=[gOutDir stringByAppendingPathComponent:[NSString stringWithFormat:@"frame%06d.jpg",gSaved]];
        NSError *error=nil;
        ok=[jpeg writeToFile:p options:0 error:&error];
        if(!ok) LOGE("write %s failed: %s",p.UTF8String,error.description.UTF8String);
    }
    if(!ok){
        pthread_mutex_lock(&gFrameLock);
        gFailure=8;
        stopFramesLocked();
        pthread_mutex_unlock(&gFrameLock);
        return;
    }
    gPrevHash=h; gLastSaveT=t;
    gSaved++;
    pthread_mutex_lock(&gFrameLock);
    gReportedSaved=gSaved; gLastOutputT=nowSec(); // only completed output renews the stall guard
    if(gMaxFrames>0 && gSaved>=gMaxFrames) stopFramesLocked();
    pthread_mutex_unlock(&gFrameLock);
}

@interface FrameSink : NSObject @end
@implementation FrameSink
- (void)stream:(id)s didStart:(BOOL)ok error:(NSError*)e {
    if(!ok){
        pthread_mutex_lock(&gFrameLock);
        if(!gFailure) gFailure=6;
        stopFramesLocked();
        pthread_mutex_unlock(&gFrameLock);
        LOGE("stream did not start: %s", e?e.description.UTF8String:"(nil)");
    }
}
- (void)stream:(id)s didGetLastDecodedFrame:(id)f {
    pthread_mutex_lock(&gFrameLock);
    if(!gStopping){
        gPulls++;
        if([f isKindOfClass:[NSData class]]){
            if(gLatestJPEG) gBackpressureDrops++;
            gLatestJPEG=(NSData*)f;
            wakeWriterLocked();
        }
    }
    pthread_mutex_unlock(&gFrameLock);
}
- (void)streamDidStop:(id)s {}
- (void)vcMediaStreamDidStop:(id)s {}
- (void)streamDidServerDie:(id)s {
    pthread_mutex_lock(&gFrameLock);
    BOOL active=!gStopping;
    if(active){ if(!gFailure) gFailure=6; stopFramesLocked(); }
    pthread_mutex_unlock(&gFrameLock);
    if(active) LOGE("media server (avconferenced) closed the stream");
}
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
      "  --seconds S     maximum collection time, including --count (default 10)\n"
      "  --daemon        decode in avconferenced instead of in-process (needs entitlement)\n");
}

// Serialize stage changes with expiry, so an old timer event cannot use a new stage label.
static void armWatchdog(dispatch_source_t timer, dispatch_queue_t queue, double seconds,
                        const char *message, size_t length){
    dispatch_sync(queue,^{
        dispatch_source_set_event_handler(timer,^{
            write(STDERR_FILENO,message,length);
            _Exit(9);
        });
        dispatch_source_set_timer(timer,dispatch_time(DISPATCH_TIME_NOW,(int64_t)(seconds*NSEC_PER_SEC)),DISPATCH_TIME_FOREVER,0);
    });
}

int main(int argc,char**argv){
    setbuf(stderr,NULL);
    signal(SIGPIPE,SIG_IGN); // report broken stdout as output failure (8)
    // Independent of the main run loop and writer: also bounds synchronous private API calls.
    // Keep the watchdog armed from initialization through start/warmup/first pull.
    // The existing 45s engineering budget covers negotiation (request timeout=30s),
    // RTP wait (8s), warmup (50 * 0.05s ~= 2.5s), leaving nominally 4.5s for setup,
    // start, first pull and scheduling. No cold-start measurements establish its adequacy.
    const double setupBudget=45;
    const double writerGrace=5;   // existing bounded-output acceptance contract
    const double stopGrace=5;     // shutdown policy allowance, not a measured private-API limit
    const double watchdogMargin=5; // scheduling/transition policy; not backed by cold-start measurements
    static const char setupTimeout[]="ipb-video: watchdog timeout: setup/start/warmup\n";
    static const char collectionTimeout[]="ipb-video: watchdog timeout: collection\n";
    static const char shutdownTimeout[]="ipb-video: watchdog timeout: shutdown/writer-drain/stop\n";
    dispatch_queue_t watchdogQueue=dispatch_queue_create("ipb.video.watchdog",DISPATCH_QUEUE_SERIAL);
    dispatch_source_t watchdog=dispatch_source_create(DISPATCH_SOURCE_TYPE_TIMER,0,0,watchdogQueue);
    armWatchdog(watchdog,watchdogQueue,setupBudget,setupTimeout,sizeof setupTimeout-1);
    dispatch_resume(watchdog);
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
    if(!isfinite(runSeconds) || runSeconds<=0 || runSeconds>(double)INT64_MAX/NSEC_PER_SEC-60 || gMaxFrames<0)
        DIE(2,"--seconds must be finite and positive; --count must be nonnegative");
    if(gOutDir){
        NSError *error=nil;
        if(![[NSFileManager defaultManager] createDirectoryAtPath:gOutDir withIntermediateDirectories:YES attributes:nil error:&error])
            DIE(8,"create output directory: %s",error.description.UTF8String);
    }

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
    gCI=[CIContext contextWithOptions:nil]; // eager, single-threaded, before any stream callback
    gDelegateQueue=dispatch_queue_create("ipb.video.delegate",DISPATCH_QUEUE_SERIAL);
    gWriterQueue=dispatch_queue_create("ipb.video.writer",DISPATCH_QUEUE_SERIAL);
    gWriterGroup=dispatch_group_create();
    gNewestPTS=kCMTimeInvalid;
    dispatch_sync(gWriterQueue,^{ gLastSaveT=nowSec(); });
    gLastOutputT=gLastRequestT=nowSec();
    if(!gDaemon) installInProcessSink();  // in-process capture (needs a GUI display session)
    Class VS=objc_getClass("AVCVideoStream"); if(!VS) DIE(6,"no AVCVideoStream class");
    NSError *se=nil;
    AVCVideoStream *vs=[[VS alloc] initWithNetworkSockets:(id)socks options:o2 error:&se];
    if(!vs) DIE(6,"AVCVideoStream init: %s",se?se.description.UTF8String:"?");
    FrameSink *sink=[FrameSink new];
    [vs setDelegate:sink];
    NSError *ce=nil; if(![vs configure:cfg error:&ce]) DIE(6,"configure: %s",ce?ce.description.UTF8String:"?");
    gStream=vs;
    [vs start];

    // warm up, then collect frames; in-process frames arrive by push, daemon frames by pull.
    for(int w=0; w<50; w++) [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.05]];  // ~2.5s
    pthread_mutex_lock(&gFrameLock);
    BOOL active=!gStopping;
    if(gDaemon && active) gLastRequestT=nowSec();
    pthread_mutex_unlock(&gFrameLock);
    if(gDaemon && active) [vs requestLastDecodedFrame];
    // Reset the already-armed timer: requested collection time + 5s scheduling headroom.
    // Shutdown receives a separate full budget when collection ends.
    armWatchdog(watchdog,watchdogQueue,runSeconds+watchdogMargin,
                collectionTimeout,sizeof collectionTimeout-1);
    double start=nowSec();
    while(1){
        [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.05]];
        double t=nowSec();
        pthread_mutex_lock(&gFrameLock);
        BOOL stopped=gStopping;
        double lastSave=gLastOutputT;
        BOOL rearm=gDaemon && !stopped && !gBusy && (t-gLastRequestT)>2.0;
        if(rearm) gLastRequestT=t;
        pthread_mutex_unlock(&gFrameLock);
        if(stopped) break;
        if((t-start) >= runSeconds) break;
        if(rearm) [vs requestLastDecodedFrame];  // daemon: re-arm on stall
        if((t-lastSave) > 12.0) break;  // hard stall guard (no frames at all)
    }
    // Fresh complete shutdown budget, independent of time left in collection:
    // existing 5s writer grace + 5s framework stop policy + 5s scheduling headroom.
    armWatchdog(watchdog,watchdogQueue,writerGrace+stopGrace+watchdogMargin,
                shutdownTimeout,sizeof shutdownTimeout-1);
    pthread_mutex_lock(&gFrameLock);
    stopFramesLocked(); // reject callbacks and release pending before stopping AVConference
    pthread_mutex_unlock(&gFrameLock);
    // A consumer that never reads stdout must not make shutdown wait forever.
    long writerBlocked=dispatch_group_wait(gWriterGroup,dispatch_time(DISPATCH_TIME_NOW,(int64_t)(writerGrace*NSEC_PER_SEC)));
    if(writerBlocked)
        LOGE("writer still blocked after 5s shutdown grace period");
    pthread_mutex_lock(&gFrameLock);
    int saved=gReportedSaved, pulls=gPulls;
    int failure=gFailure;
    unsigned long dropped=gBackpressureDrops;
    unsigned long invalidPTS=gInvalidPTS, nonIncreasingPTS=gNonIncreasingPTS;
    pthread_mutex_unlock(&gFrameLock);
    LOGE("saved %d distinct frame(s) from %d pull(s); dropped %lu frame(s) due to backpressure; invalidPTS %lu; nonIncreasingPTS %lu", saved, pulls, dropped, invalidPTS, nonIncreasingPTS);
    // exit() would flush stdout and could wait on the blocked writer's stdio lock.
    if(writerBlocked || failure==8) _Exit(8);
    // Preserve the private API's main-thread call site. The watchdog queue never waits
    // for the main thread or writer; the full shutdown deadline remains armed during stop.
    [vs stop];
    if(failure) _Exit(failure);
    if(!saved) _Exit(7);
    if(gMaxFrames>0 && saved<gMaxFrames) _Exit(8);
    _Exit(0); // all output was flushed by the writer; do not wait for framework teardown
}
