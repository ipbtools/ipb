// Standalone media receiver — stage 1: transport + negotiation (fail-hard, unbuffered).
// Follows CoreDeviceMediaStreamSupport's own chain. All ObjC/C, no Swift shims.
#import <Foundation/Foundation.h>
#import <objc/runtime.h>
#import <CoreMedia/CoreMedia.h>
#import <CoreVideo/CoreVideo.h>
#import <CoreImage/CoreImage.h>
#import <ImageIO/ImageIO.h>
#import <CoreGraphics/CoreGraphics.h>
#include <xpc/xpc.h>
#include <uuid/uuid.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <net/if.h>
#include <string.h>
#include <dlfcn.h>
@interface VCImageQueue : NSObject
- (BOOL)isLayerHostMode;
- (id)streamOutput;
- (void)setStreamOutput:(id)o;
- (long long)streamToken;
@end
@interface VCStreamOutput : NSObject
- (instancetype)initWithStreamToken:(long long)t clientProcessID:(int)pid delegate:(id)d delegateQueue:(dispatch_queue_t)q;
@end
@interface SinkTap : NSObject
@end

#define LOG(...) do{ fprintf(stderr, __VA_ARGS__); fprintf(stderr,"\n"); }while(0)
#define DIE(...) do{ LOG("FATAL: " __VA_ARGS__); return 2; }while(0)

extern void _coredevice_xpc_add_bundle(NSBundle*);
extern void _coredevice_xpc_init_services(void);
typedef void *xrc_t;
extern xrc_t xpc_remote_connection_create_with_connected_fd(int,dispatch_queue_t,uint64_t,uint64_t);
extern void xpc_remote_connection_set_event_handler(xrc_t,xpc_handler_t);
extern void xpc_remote_connection_activate(xrc_t);
extern xpc_object_t xpc_remote_connection_send_message_with_reply_sync(xrc_t,xpc_object_t);

@interface AVCMediaStreamNegotiator : NSObject
@end
@interface AVCMediaStreamNegotiator (X)
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
- (BOOL)start;
- (void)stop;
- (void)requestLastDecodedFrame;
- (BOOL)shouldRunInProcessWithOptions:(id)o;
@end

static int gFrames=0;
static void saveFrame(CVImageBufferRef px){
    if(!px||gFrames>=8) return;
    @autoreleasepool{
        CIImage *ci=[CIImage imageWithCVImageBuffer:px];
        CIContext *cc=[CIContext contextWithOptions:nil];
        CGImageRef img=[cc createCGImage:ci fromRect:ci.extent];
        if(img){
            NSString*path=[NSString stringWithFormat:@"/tmp/ipbframe%03d.png",gFrames];
            CGImageDestinationRef d=CGImageDestinationCreateWithURL((__bridge CFURLRef)[NSURL fileURLWithPath:path],(CFStringRef)@"public.png",1,NULL);
            if(d){CGImageDestinationAddImage(d,img,NULL);CGImageDestinationFinalize(d);CFRelease(d);
                  fprintf(stderr,"*** FRAME %d saved %s (%zux%zu)\n",gFrames,path.UTF8String,CGImageGetWidth(img),CGImageGetHeight(img));}
            CGImageRelease(img); gFrames++;
        }
    }
}
static IMP oShow,oDec;
static void nShow(id self,SEL c,id frame,CMTime t){
    if(oShow)((void(*)(id,SEL,id,CMTime))oShow)(self,c,frame,t);
    if(gFrames<8) fprintf(stderr,"HOOK showDecodedFrame: class=%s\n", frame?object_getClassName(frame):"nil");
    if(frame){ CFTypeID tid=CFGetTypeID((__bridge CFTypeRef)frame);
        if(tid==CVPixelBufferGetTypeID()) saveFrame((CVImageBufferRef)(__bridge void*)frame); }
}
static void nDec(id self,SEL c,id f,BOOL sh){ if(oDec)((void(*)(id,SEL,id,BOOL))oDec)(self,c,f,sh); static int n=0; if(n++<3) fprintf(stderr,"HOOK decodeFrame:showFrame:%d\n",sh); }
static IMP oOnVF,oSendLast,oSetVBD;
static void nOnVF(id self,SEL c,id f,double t,id a){ static int n=0; if(n++<3) fprintf(stderr,"HOOK onVideoFrame: class=%s t=%f\n", f?object_getClassName(f):"nil",t);
    if(f){CFTypeID x=CFGetTypeID((__bridge CFTypeRef)f); if(x==CVPixelBufferGetTypeID()) saveFrame((CVImageBufferRef)(__bridge void*)f);} 
    if(oOnVF)((void(*)(id,SEL,id,double,id))oOnVF)(self,c,f,t,a); }
static void nSendLast(id self,SEL c,id x){ fprintf(stderr,"HOOK sendLastRemoteVideoFrame: arg=%s\n", x?object_getClassName(x):"nil"); if(oSendLast)((void(*)(id,SEL,id))oSendLast)(self,c,x); }
static void hookOne(const char*cls,const char*sel,IMP n,IMP*o){ Class C=objc_getClass(cls); if(!C){fprintf(stderr,"no %s\n",cls);return;} Method m=class_getInstanceMethod(C,sel_registerName(sel)); if(!m){fprintf(stderr,"%s: no %s\n",cls,sel);return;} *o=method_getImplementation(m); method_setImplementation(m,n); fprintf(stderr,"hooked -[%s %s]\n",cls,sel); }
static IMP oSampBuf;
static void nSampBuf(id self,SEL c,CMSampleBufferRef sb){
    static int n=0;
    if(sb){ CVImageBufferRef px=CMSampleBufferGetImageBuffer(sb);
        if(n++<3) fprintf(stderr,"HOOK didReceiveSampleBuffer: sb=%p imageBuffer=%p\n",sb,px);
        if(px) saveFrame(px); }
    if(oSampBuf)((void(*)(id,SEL,CMSampleBufferRef))oSampBuf)(self,c,sb);
}
static id gIQ;
static IMP oIQinit,oIQslot,oIQlayer,oIQso,oIQvd,oIQfig,oIQstart,oIQdef;
static id nIQinit(id self,SEL c,unsigned fr,BOOL pr,id cfg){ id r=((id(*)(id,SEL,unsigned,BOOL,id))oIQinit)(self,c,fr,pr,cfg); gIQ=r; fprintf(stderr,"IQ init(rate=%u prot=%d) -> %p\n",fr,pr,(__bridge void*)r); return r; }
static void nIQslot(id self,SEL c){ fprintf(stderr,"IQ createSlotAndConnectCAQueue (layerHost=%d)\n",(int)[(VCImageQueue*)self isLayerHostMode]); if(oIQslot)((void(*)(id,SEL))oIQslot)(self,c); }
static void nIQlayer(id self,SEL c,CGRect r,id n){ fprintf(stderr,"IQ configureCALayerWithRect name=%s\n", n?[[n description] UTF8String]:"nil"); if(oIQlayer)((void(*)(id,SEL,CGRect,id))oIQlayer)(self,c,r,n); }
static void nIQso(id self,SEL c,id o){ fprintf(stderr,"IQ setStreamOutput: %s\n", o?object_getClassName(o):"nil"); if(oIQso)((void(*)(id,SEL,id))oIQso)(self,c,o); }
static void nIQvd(id self,SEL c,id o){ fprintf(stderr,"IQ setVideoDestination: %s\n", o?object_getClassName(o):"nil"); if(oIQvd)((void(*)(id,SEL,id))oIQvd)(self,c,o); }
static void nIQfig(id self,SEL c,id t,id d){ fprintf(stderr,"IQ setUpImageQueueForFigVideoTarget\n"); if(oIQfig)((void(*)(id,SEL,id,id))oIQfig)(self,c,t,d); }
static void nIQdef(id self,SEL c,id d){ fprintf(stderr,"IQ setupDefaultImageQueueForFigVideoTarget\n"); if(oIQdef)((void(*)(id,SEL,id))oIQdef)(self,c,d); }
static void nIQstart(id self,SEL c){
    VCImageQueue *iq=(VCImageQueue*)self;
    fprintf(stderr,"IQ start (layerHost=%d streamOutput=%s)\n",(int)[iq isLayerHostMode], [iq streamOutput]?object_getClassName([iq streamOutput]):"nil");
    if(getenv("SINK") && ![iq streamOutput]){
        Class SO=objc_getClass("VCStreamOutput");
        if(SO){ static SinkTap *sink; if(!sink) sink=[SinkTap new];
            id so=[[SO alloc] initWithStreamToken:[iq streamToken] clientProcessID:getpid() delegate:sink delegateQueue:dispatch_get_global_queue(0,0)];
            fprintf(stderr,"created VCStreamOutput=%s token=%lld\n", so?object_getClassName(so):"nil", [iq streamToken]);
            if(so){ [iq setStreamOutput:so]; fprintf(stderr,"installed streamOutput -> now %s\n", [iq streamOutput]?object_getClassName([iq streamOutput]):"nil"); } }
    }
    if(oIQstart)((void(*)(id,SEL))oIQstart)(self,c); }
static void hookRecv(void){
    hookOne("VCImageQueue","initWithFrameRate:imageQueueProtected:vcImageQueueConfig:",(IMP)nIQinit,&oIQinit);
    hookOne("VCImageQueue","createSlotAndConnectCAQueue",(IMP)nIQslot,&oIQslot);
    hookOne("VCImageQueue","configureCALayerWithRect:name:",(IMP)nIQlayer,&oIQlayer);
    hookOne("VCImageQueue","setStreamOutput:",(IMP)nIQso,&oIQso);
    hookOne("VCImageQueue","setVideoDestination:",(IMP)nIQvd,&oIQvd);
    hookOne("VCImageQueue","setUpImageQueueForFigVideoTargetWithTagCollection:withDataChannelConfig:",(IMP)nIQfig,&oIQfig);
    hookOne("VCImageQueue","setupDefaultImageQueueForFigVideoTargetWithDataChannelConfig:",(IMP)nIQdef,&oIQdef);
    hookOne("VCImageQueue","start",(IMP)nIQstart,&oIQstart);
    hookOne("VCStreamOutput","didReceiveSampleBuffer:",(IMP)nSampBuf,&oSampBuf);
    hookOne("VCVideoStream","onVideoFrame:frameTime:attribute:",(IMP)nOnVF,&oOnVF);
    hookOne("VCVideoStream","sendLastRemoteVideoFrame:",(IMP)nSendLast,&oSendLast);
    Class C=objc_getClass("VCVideoStreamReceiver");
    if(!C){ fprintf(stderr,"no VCVideoStreamReceiver\n"); return; }
    Method m=class_getInstanceMethod(C,sel_registerName("showDecodedFrame:atTime:"));
    if(m){ oShow=method_getImplementation(m); method_setImplementation(m,(IMP)nShow); fprintf(stderr,"hooked showDecodedFrame:atTime:\n"); }
    Method m2=class_getInstanceMethod(C,sel_registerName("decodeFrame:showFrame:"));
    if(m2){ oDec=method_getImplementation(m2); method_setImplementation(m2,(IMP)nDec); fprintf(stderr,"hooked decodeFrame:showFrame:\n"); }
}

@interface StreamTap : NSObject
@end
@implementation SinkTap
- (void)streamOutput:(id)o didReceiveSampleBuffer:(CMSampleBufferRef)sb {
    fprintf(stderr,"SINK streamOutput:didReceiveSampleBuffer: %p\n", sb);
}
- (BOOL)respondsToSelector:(SEL)sel { BOOL r=[super respondsToSelector:sel]; fprintf(stderr,"SINK probe %s -> %d\n",sel_getName(sel),r); return r; }
@end

@implementation StreamTap
- (void)stream:(id)s didStart:(BOOL)ok error:(NSError*)e {
    fprintf(stderr,"DELEGATE stream:didStart:%d error:%s\n", ok, e?e.description.UTF8String:"nil");
}
- (void)stream:(id)s didGetLastDecodedFrame:(id)f {
    fprintf(stderr,"*** DELEGATE didGetLastDecodedFrame: class=%s\n", f?object_getClassName(f):"nil");
    if(!f) return;
    CFTypeID t=CFGetTypeID((__bridge CFTypeRef)f);
    if(t==CVPixelBufferGetTypeID()){ saveFrame((CVImageBufferRef)(__bridge void*)f); return; }
    if(t==CMSampleBufferGetTypeID()){ CVImageBufferRef px=CMSampleBufferGetImageBuffer((CMSampleBufferRef)(__bridge void*)f); if(px) saveFrame(px); return; }
    if([f isKindOfClass:[NSData class]]){
        NSString*p=[NSString stringWithFormat:@"/tmp/ipbframe_raw%03d.bin",gFrames++];
        [(NSData*)f writeToFile:p atomically:YES];
        fprintf(stderr,"*** wrote raw frame %s (%lu bytes)\n",p.UTF8String,(unsigned long)[(NSData*)f length]); return; }
    fprintf(stderr,"    frame CFTypeID=%lu desc=%s\n",(unsigned long)t,[[(__bridge NSString*)CFCopyTypeIDDescription(t) description] UTF8String]);
}
- (void)vcMediaStreamDidStop:(id)s { fprintf(stderr,"DELEGATE vcMediaStreamDidStop\n"); }
// catch-all so we see any other delegate selector the stream sends
- (BOOL)respondsToSelector:(SEL)sel {
    BOOL r=[super respondsToSelector:sel];
    fprintf(stderr,"DELEGATE probe: %s -> %d\n", sel_getName(sel), r);
    return r;
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
int main(int argc,char**argv){
    setbuf(stdout,NULL); setbuf(stderr,NULL);
    if(argc<5){ LOG("usage: receiver <coredevice-uuid> <utun> <hostIP> <deviceIP>"); return 2; }
    const char*dev=argv[1]; const char*utun=argv[2]; const char*rxip=argv[3]; const char*txip=argv[4];
    long mode = getenv("MODE")? atol(getenv("MODE")) : 5;

    if(!dlopen("/Library/Developer/PrivateFrameworks/CoreDevice.framework/Versions/A/CoreDevice",RTLD_NOW)) DIE("CoreDevice dlopen: %s",dlerror());
    if(!dlopen("/System/Library/PrivateFrameworks/AVConference.framework/Versions/A/AVConference",RTLD_NOW)) DIE("AVConference dlopen: %s",dlerror());
    LOG("frameworks loaded");
    _coredevice_xpc_add_bundle([NSBundle bundleWithPath:@"/Library/Developer/PrivateFrameworks/CoreDevice.framework"]);
    _coredevice_xpc_init_services();
    LOG("coredevice services inited");

    Class N=objc_getClass("AVCMediaStreamNegotiator"); if(!N) DIE("no AVCMediaStreamNegotiator");
    NSError*e=nil;
    NSString*sessID=[[NSUUID UUID] UUIDString];
    const char*cn0 = getenv("CLIENTNAME") ?: "CoreDeviceScreenSharing";
    long tpt = getenv("TPT")? atol(getenv("TPT")) : 1;
    long ant = getenv("ANT")? atol(getenv("ANT")) : 1;
    NSMutableDictionary*negOpts=[NSMutableDictionary dictionary];
    if(getenv("NEG_TRANSPORT")){
      negOpts[@"AVCMediaStreamNegotiatorTransportProtocolType"]=@(getenv("TPT")?atol(getenv("TPT")):1);
      negOpts[@"AVCMediaStreamNegotiatorAccessNetworkType"]=@(getenv("ANT")?atol(getenv("ANT")):1);
    }
    LOG("negotiator options: %s", negOpts.description.UTF8String);
    id neg=[[N alloc] initWithMode:mode options:negOpts error:&e];
    if(!neg) DIE("negotiator init: %s",e.description.UTF8String);
    if(![neg createOffer]) DIE("createOffer failed");
    NSData*offer=[neg offer]; if(!offer.length) DIE("empty offer");
    LOG("offer: %lu bytes",(unsigned long)offer.length);
    Ivar sv=class_getInstanceVariable([neg class],"_dataSessionID"); NSString*callID = sv? object_getIvar(neg,sv):nil;
    if(!callID.length) DIE("no _dataSessionID");
    const char*clientName = getenv("CLIENTNAME") ?: "ipb";
    LOG("callID/sessionID = %s  clientName=%s", callID.UTF8String, clientName);

    // createservicesocket -> RemoteXPC to dtremotedisplayd
    dispatch_queue_t q=dispatch_queue_create("cds",0);
    xpc_connection_t c=xpc_connection_create("com.apple.CoreDevice.CoreDeviceService",q);
    xpc_connection_set_event_handler(c,^(xpc_object_t x){});
    xpc_connection_resume(c);
    xpc_object_t in0=xpc_dictionary_create_empty();
    xpc_dictionary_set_string(in0,"featureIdentifier","com.apple.coredevice.feature.startmediastream");
    xpc_object_t rep=xpc_connection_send_message_with_reply_sync(c,action_env("com.apple.coredevice.action.createservicesocket",dev,in0));
    xpc_object_t out=xpc_dictionary_get_dictionary(rep,"CoreDevice.output");
    if(!out){ char*d=xpc_copy_description(rep); LOG("createservicesocket no output: %.300s",d); return 2; }
    int sfd=xpc_dictionary_dup_fd(out,"fileDescriptor");
    uint64_t flags=xpc_dictionary_get_uint64(out,"remoteXPCVersionFlags");
    if(sfd<0) DIE("no service fd");
    xrc_t rc=xpc_remote_connection_create_with_connected_fd(sfd,dispatch_queue_create("rc",0),flags,0);
    xpc_remote_connection_set_event_handler(rc,^(xpc_object_t ev){ char*d=xpc_copy_description(ev); LOG("rc-event: %.160s",d); free(d); });
    xpc_remote_connection_activate(rc);
    LOG("service socket up (fd=%d flags=%llu)",sfd,flags);

    // our UDP receive socket on the host tunnel addr — FAIL HARD
    int rtp=socket(AF_INET6,SOCK_DGRAM,0); if(rtp<0) DIE("socket: %s",strerror(errno));
    int one=1; setsockopt(rtp,SOL_SOCKET,SO_REUSEADDR,&one,sizeof one); setsockopt(rtp,SOL_SOCKET,SO_REUSEPORT,&one,sizeof one);
    struct sockaddr_in6 la; memset(&la,0,sizeof la); la.sin6_len=sizeof la; la.sin6_family=AF_INET6;
    if(inet_pton(AF_INET6,rxip,&la.sin6_addr)!=1) DIE("bad host IP %s",rxip);
    la.sin6_scope_id=if_nametoindex(utun); if(!la.sin6_scope_id) DIE("no interface %s",utun);
    if(bind(rtp,(struct sockaddr*)&la,sizeof la)!=0) DIE("bind [%s%%%s]: %s",rxip,utun,strerror(errno));
    socklen_t sl=sizeof la; if(getsockname(rtp,(struct sockaddr*)&la,&sl)!=0) DIE("getsockname: %s",strerror(errno));
    uint16_t rxport=ntohs(la.sin6_port); if(!rxport) DIE("no bound port");
    LOG("RTP socket bound OK: [%s%%%s]:%u",rxip,utun,rxport);

    uint16_t txport=51000;
    xpc_object_t in=xpc_dictionary_create_empty();
    xpc_dictionary_set_string(in,"receiverIP",rxip); xpc_dictionary_set_uint64(in,"receiverPort",rxport);
    xpc_dictionary_set_string(in,"senderIP",txip); xpc_dictionary_set_uint64(in,"senderPort",txport);
    xpc_dictionary_set_uint64(in,"timeout",30);
    xpc_dictionary_set_string(in,"type","video"); xpc_dictionary_set_string(in,"direction","output");
    xpc_dictionary_set_data(in,"negotiatorOffer",offer.bytes,offer.length);
    xpc_dictionary_set_uint64(in,"clientSupportedFeatures",972);
    // MSS primary-screen receive path puts ONLY ClientSessionID, as CodableValue.uuid
    xpc_object_t opts=xpc_dictionary_create_empty();
    uuid_t sessUU; uuid_parse(sessID.UTF8String, sessUU);
    xpc_object_t cvUUID=xpc_dictionary_create_empty();
    xpc_dictionary_set_uuid(cvUUID,"uuid",sessUU);
    xpc_dictionary_set_value(opts,"avcMediaStreamOptionClientSessionID",cvUUID);
    if(getenv("WITH_TRANSPORT")){
      xpc_object_t t=xpc_dictionary_create_empty(); xpc_dictionary_set_int64(t,"int",getenv("TPT")?atol(getenv("TPT")):1);
      xpc_dictionary_set_value(opts,"AVCMediaStreamNegotiatorTransportProtocolType",t);
      xpc_object_t a=xpc_dictionary_create_empty(); xpc_dictionary_set_int64(a,"int",getenv("ANT")?atol(getenv("ANT")):1);
      xpc_dictionary_set_value(opts,"AVCMediaStreamNegotiatorAccessNetworkType",a);
    }
    LOG("options: ClientSessionID=.uuid(%s)%s", sessID.UTF8String, getenv("WITH_TRANSPORT")?" +transport ints":"");
    xpc_dictionary_set_value(in,"options",opts);
    xpc_object_t srep=xpc_remote_connection_send_message_with_reply_sync(rc,action_env("com.apple.coredevice.action.mediastreamstart",dev,in));
    if(!srep){ LOG("mediastreamstart: null reply"); return 2; }
    char*sd=xpc_copy_description(srep);
    LOG("start reply: %.3500s",sd); free(sd);
    xpc_object_t so=xpc_dictionary_get_dictionary(srep,"CoreDevice.output");
    { xpc_object_t err=xpc_dictionary_get_dictionary(srep,"CoreDevice.error");
      if(err){ int64_t code=xpc_dictionary_get_int64(err,"code"); const char*dom=xpc_dictionary_get_string(err,"domain");
        xpc_object_t ui=xpc_dictionary_get_dictionary(err,"userInfo");
        uint64_t det = ui? xpc_dictionary_get_uint64(ui,"NSErrorUserInfoDetailedError"):0;
        LOG("ERROR code=%lld domain=%s detailedError=%llu (0x%llx)",(long long)code,dom,det,det);
        size_t el=0; const void*ed=xpc_dictionary_get_data(err,"userInfoWithNSSecureCoding",&el);
        if(ed){ NSData*D=[NSData dataWithBytes:ed length:el]; NSError*ue=nil;
          id o=[NSKeyedUnarchiver unarchivedObjectOfClass:[NSDictionary class] fromData:D error:&ue];
          if(!o){ NSKeyedUnarchiver*u=[[NSKeyedUnarchiver alloc] initForReadingFromData:D error:nil]; u.requiresSecureCoding=NO; o=[u decodeObjectForKey:@"root"]; }
          LOG("userInfo unarchived: %s",[o description].UTF8String); } } }

    // transport check: does the device send RTP to us? (verification only; AVCVideoStream handoff is stage 2)
    if(getenv("STAGE2")) goto skip_probe;
    struct timeval tv={4,0}; setsockopt(rtp,SOL_SOCKET,SO_RCVTIMEO,&tv,sizeof tv);
    uint8_t pkt[2048]; struct sockaddr_in6 from; socklen_t fl=sizeof from;
    ssize_t n=recvfrom(rtp,pkt,sizeof pkt,0,(struct sockaddr*)&from,&fl);
    if(n>0){ char fb[64]; inet_ntop(AF_INET6,&from.sin6_addr,fb,sizeof fb);
        LOG("*** RTP RECEIVED: %zd bytes from [%s]:%u  hdr: %02x %02x %02x %02x",n,fb,ntohs(from.sin6_port),pkt[0],pkt[1],pkt[2],pkt[3]); }
    else LOG("no RTP within 4s (n=%zd errno=%s)",n,strerror(errno));

skip_probe:
    if(so){
        size_t alen=0; const void*ans=xpc_dictionary_get_data(so,"negotiatorAnswer",&alen);
        if(!ans) ans=xpc_dictionary_get_data(so,"answer",&alen);
        LOG("answer: %s (%zu bytes)",ans?"YES":"no",alen);
        if(ans){ NSError*ae=nil; BOOL ok=[neg setAnswer:[NSData dataWithBytes:ans length:alen] withError:&ae];
            LOG("setAnswer=%d err=%s",ok,ae?ae.description.UTF8String:"nil");
            id cfg=[neg generateMediaStreamConfigurationWithError:&ae];
            LOG("config=%p err=%s",cfg,ae?[ae.description substringToIndex:MIN(140UL,ae.description.length)].UTF8String:"nil");
            id opt=[neg generateMediaStreamInitOptionsWithError:&ae];
            LOG("initOptions=%p err=%s",opt,ae?[ae.description substringToIndex:MIN(140UL,ae.description.length)].UTF8String:"nil");
        }
    }
    // ---- stage 2: hand our socket to AVCVideoStream for in-process decode ----
    if(so && getenv("STAGE2")){
        // learn the device's RTP source via MSG_PEEK (do not consume), then connect() the socket
        struct timeval ptv={6,0}; setsockopt(rtp,SOL_SOCKET,SO_RCVTIMEO,&ptv,sizeof ptv);
        uint8_t pk[4]; struct sockaddr_in6 peer; socklen_t pl=sizeof peer;
        ssize_t pn=recvfrom(rtp,pk,sizeof pk,MSG_PEEK,(struct sockaddr*)&peer,&pl);
        if(pn<=0){ LOG("stage2: no RTP to peek (n=%zd %s) - cannot connect socket",pn,strerror(errno)); }
        else{
            char pb[64]; inet_ntop(AF_INET6,&peer.sin6_addr,pb,sizeof pb);
            LOG("stage2: peer RTP [%s]:%u (peeked %zd bytes, hdr %02x %02x)",pb,ntohs(peer.sin6_port),pn,pk[0],pk[1]);
            if(connect(rtp,(struct sockaddr*)&peer,sizeof peer)!=0) LOG("stage2: connect failed: %s",strerror(errno));
            else LOG("stage2: socket connected to peer");
        }
        struct timeval z={0,0}; setsockopt(rtp,SOL_SOCKET,SO_RCVTIMEO,&z,sizeof z);

        NSError*ae2=nil;
        id cfg2=[neg generateMediaStreamConfigurationWithError:&ae2];
        id opt2=[neg generateMediaStreamInitOptionsWithError:&ae2];
        LOG("stage2: cfg=%s opt=%s", cfg2?object_getClassName(cfg2):"nil", opt2?object_getClassName(opt2):"nil");
        if(cfg2){
            unsigned nm=0; Method*ms=class_copyMethodList([cfg2 class],&nm);
            NSMutableArray*sels=[NSMutableArray array];
            for(unsigned i=0;i<nm;i++){const char*sn=sel_getName(method_getName(ms[i]));
                if(!strchr(sn,':')) [sels addObject:[NSString stringWithUTF8String:sn]];}
            free(ms);
            for(NSString*sn in sels){
                const char*c=sn.UTF8String;
                if(strcasestr(c,"port")||strcasestr(c,"ip")||strcasestr(c,"addr")||strcasestr(c,"remote")||strcasestr(c,"local")||strcasestr(c,"ssrc")||strcasestr(c,"payload")||strcasestr(c,"socket")||strcasestr(c,"connection")){
                    @try{ id v=[cfg2 valueForKey:sn]; LOG("  cfg.%s = %s", c, [[v description] UTF8String]); }@catch(id e){}
                }
            }
        }
        if(cfg2){
            for(NSString*k in @[@"remoteAddress",@"localAddress"]){
                @try{ id a=[cfg2 valueForKey:k];
                    LOG("== %s: %s", k.UTF8String, [[a description] UTF8String]);
                    unsigned an=0; Method*am=class_copyMethodList([a class],&an);
                    for(unsigned i=0;i<an;i++){const char*sn=sel_getName(method_getName(am[i]));
                        if(!strchr(sn,':')&&(strcasestr(sn,"port")||strcasestr(sn,"addr")||strcasestr(sn,"string")||strcasestr(sn,"ip")||strcasestr(sn,"family"))){
                            @try{ id v=[a valueForKey:[NSString stringWithUTF8String:sn]]; LOG("   %s.%s = %s", k.UTF8String, sn, [[v description] UTF8String]); }@catch(id e){} } }
                    free(am);
                }@catch(id e){}
            }
            @try{ LOG("cfg FULL: %s", [[cfg2 description] UTF8String]); }@catch(id e){}
        }
        if(opt2 && [opt2 isKindOfClass:[NSDictionary class]]) LOG("initOptions keys: %s", [[(NSDictionary*)opt2 allKeys] description].UTF8String);
        NSMutableDictionary*o2=[NSMutableDictionary dictionary];
        if([opt2 isKindOfClass:[NSDictionary class]]) [o2 addEntriesFromDictionary:opt2];
        o2[@"avcMediaStreamOptionRunInProcess"]=@(getenv("OOP")?NO:YES);
        o2[@"avcMediaStreamOptionClientName"]=@"CoreDeviceScreenSharing";
        o2[@"avcMediaStreamOptionClientSessionID"]=[[NSUUID alloc] initWithUUIDString:sessID];
        xpc_object_t socks=xpc_dictionary_create_empty();
        xpc_dictionary_set_fd(socks,"avcKeySharedSocket",rtp);
        hookRecv();
        Class VS=objc_getClass("AVCVideoStream");
        if(!VS){ LOG("no AVCVideoStream class"); return 3; }
        NSError*se=nil;
        AVCVideoStream *vs=[[VS alloc] initWithNetworkSockets:(id)socks options:o2 error:&se];
        LOG("AVCVideoStream init -> %s err=%s", vs?"OK":"nil", se?se.description.UTF8String:"nil");
        if(vs){
            LOG("shouldRunInProcess=%d", [vs shouldRunInProcessWithOptions:o2]);
            StreamTap*tap=[StreamTap new];
            [vs setDelegate:tap];
            NSError*ce=nil; BOOL okc=[vs configure:cfg2 error:&ce];
            LOG("configure -> %d err=%s", okc, ce?ce.description.UTF8String:"nil");
            [(AVCVideoStream*)vs start];
            LOG("start called");
            [[NSNotificationCenter defaultCenter] addObserverForName:nil object:nil queue:nil usingBlock:^(NSNotification*n){
                const char*nn=n.name.UTF8String;
                if(nn && (strcasestr(nn,"vcMediaStream")||strcasestr(nn,"Frame")||strcasestr(nn,"avc")))
                    fprintf(stderr,"NOTE %s userInfo=%s\n", nn, n.userInfo?[[n.userInfo allKeys] description].UTF8String:"nil");
            }];
            for(int i=0;i<24;i++){ [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.5]];
                if(i%6==5){ [vs requestLastDecodedFrame]; fprintf(stderr,"pulled requestLastDecodedFrame\n"); } }
            [vs stop];
            LOG("stage2 stopped");
        }
    }
    LOG("stage1 done");
    return 0;
}
