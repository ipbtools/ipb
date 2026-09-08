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

#define LOGE(...) do{ fprintf(stderr, "ipb-mirror-probe: " __VA_ARGS__); fprintf(stderr,"\n"); }while(0)
#define DIE(code, ...) do{ fail((code), [NSString stringWithFormat:@"" __VA_ARGS__]); return (code); }while(0)

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


#include <stdatomic.h>
#include <fcntl.h>
#include <poll.h>
// Evidence: docs/video-stream.md and docs/verification.md (2026-09-08), and
// Sources/video_stream.m: mode-5 negotiation and VCImageQueue installation copied below.
// HID oracle: Sources/action_sender.m send_coredevice_pointer_report / main;
// docs/protocol.md "Pointer" records Xcode 27 beta 2 symbol evidence and probes.
// No new private ABI. Relative pointer deltas do NOT prove absolute screen placement.
extern int uhid_make_pointer_hid_report(int64_t,int64_t,uint32_t,double,double,uint32_t,void*);
extern int coredevice_send_universalhid_hid_report(xrc_t,const void*,uint64_t);
extern int coredevice_send_universalhid_barrier(xrc_t);
extern void xpc_remote_connection_cancel(xrc_t);

enum { Capacity=8192, PendingLimit=64 };
typedef enum { Down, Move, Up } Kind;
typedef enum { Pending, Running, Sent, Rejected, Overload, BuildFailed, SendFailed, BarrierFailed, Interrupted } Result;
typedef struct { uint64_t seq, generation, gesture; Kind kind; double x,y,submit; } Event;
typedef struct { Event event; unsigned depth; Result result; int reportCode,barrierCode;
                 double received,reportReturn,barrierReturn; } Record;
static pthread_mutex_t gLock=PTHREAD_MUTEX_INITIALIZER;
// The existing Swift report builder retains reports; the same run cap also bounds
// that oracle allocation without modifying released glue.
static Record gRecords[Capacity]; // bounded ring; CLI caps total so no submission is overwritten
static unsigned gPending[PendingLimit],gHead,gCount,gMaxDepth,gSubmitted;
static BOOL gWorker,gStopping,gCollect;
static _Atomic uint64_t gGeneration=1;
static _Atomic int gFailure=0;
static _Atomic bool gFinished=false;
static NSString *gReason;
static uint64_t gFrames,gDrops,gMediaErrors,gIntervals;
static double gFrameIntervals[Capacity],gLastFrame;
static CMTime gNewestPTS;
static AVCVideoStream *gStream;
static dispatch_queue_t gDelegateQueue,gInputQueue;
static dispatch_group_t gInputGroup;
static xrc_t gInput; // only input queue reads/writes this connection and gesture state
static int gInputFD=-1;
static BOOL gInputLive;
static double nowSec(void){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC,&ts); return ts.tv_sec+ts.tv_nsec/1e9; }
static void fail(int code,NSString *reason){
    pthread_mutex_lock(&gLock);
    if(!atomic_load(&gFailure)){ gReason=reason; atomic_store(&gFailure,code); }
    pthread_mutex_unlock(&gLock);
}
static void inputError(NSString *reason){
    // Invalidate before taking the metrics lock, including while a sender is blocked.
    atomic_fetch_add(&gGeneration,1);
    fail(1,[reason stringByAppendingString:@"; gesture abandoned; device release is NOT guaranteed after disconnect/failure"]);
}
static void mediaError(NSString *reason){
    pthread_mutex_lock(&gLock); BOOL active=!gStopping; if(active) gMediaErrors++; pthread_mutex_unlock(&gLock);
    if(active) fail(6,reason);
}
static int compareDouble(const void*a,const void*b){ double x=*(const double*)a,y=*(const double*)b; return (x>y)-(x<y); }
static void percentiles(NSMutableString *s,const char *label,double *v,unsigned n){
    if(!n){ [s appendFormat:@"%s p50=NA p95=NA p99=NA n=0\n",label]; return; }
    qsort(v,n,sizeof *v,compareDouble);
    [s appendFormat:@"%s p50=%.3f p95=%.3f p99=%.3f n=%u (ms)\n",label,
        v[(unsigned)ceil(n*.50)-1]*1000,v[(unsigned)ceil(n*.95)-1]*1000,v[(unsigned)ceil(n*.99)-1]*1000,n];
}
// One top-level finalizer for normal completion, setup failures, signals and watchdog.
// Never calls private APIs or waits for the input queue. No lock is held across a sender.
static void finish(int code,NSString *reason) __attribute__((noreturn));
static void finish(int code,NSString *reason){
    // A losing finalizer must not return from main and preempt the winner's output.
    if(atomic_exchange(&gFinished,true)) pthread_exit(NULL);
    static Record records[Capacity]; static double intervals[Capacity];
    pthread_mutex_lock(&gLock);
    gStopping=YES; gCollect=NO; atomic_fetch_add(&gGeneration,1);
    unsigned n=gSubmitted; memcpy(records,gRecords,sizeof records);
    uint64_t frames=gFrames,drops=gDrops,errors=gMediaErrors,intervalCount=gIntervals;
    memcpy(intervals,gFrameIntervals,sizeof intervals);
    unsigned maxDepth=gMaxDepth;
    if(atomic_load(&gFailure)){ code=atomic_load(&gFailure); reason=gReason; }
    pthread_mutex_unlock(&gLock);
    NSMutableString *s=[NSMutableString stringWithFormat:@"ipb-mirror-probe: exit=%d reason=%@\n",code,reason];
    static double values[4][Capacity]; unsigned counts[4]={0};
    unsigned executed=0,rejected=0,overload=0,inflight=0;
    const char *kinds[]={"DOWN","MOVE","UP"};
    const char *results[]={"pending","running","sent","rejected","overload","build_failed","send_failed","barrier_failed","interrupted"};
    for(unsigned i=0;i<n;i++){
        Record *r=&records[i];
        if(r->result==Pending){ r->result=Rejected; }
        if(r->reportReturn) executed++;
        else if(r->result==Running) inflight++;
        else rejected++;
        if(r->result==Overload) overload++;
        if(r->received) values[0][counts[0]++]=r->received-r->event.submit;
        if(r->reportReturn){ values[1][counts[1]++]=r->reportReturn-r->received; values[2][counts[2]++]=r->reportReturn-r->event.submit; }
        if(r->barrierReturn) values[3][counts[3]++]=r->barrierReturn-r->reportReturn;
    }
    percentiles(s,"input queue+entry",values[0],counts[0]);
    percentiles(s,"input exec",values[1],counts[1]);
    percentiles(s,"input host total",values[2],counts[2]);
    percentiles(s,"gesture tail",values[3],counts[3]);
    [s appendFormat:@"submitted=%u executed=%u rejected=%u overload=%u in_flight=%u max_queue_depth=%u\n",n,executed,rejected,overload,inflight,maxDepth];
    unsigned intervalN=(unsigned)MIN(intervalCount,Capacity);
    qsort(intervals,intervalN,sizeof *intervals,compareDouble);
    [s appendFormat:@"media frames=%llu interval_p50=%@ interval_p95=%@ drops=%llu errors=%llu interval_n=%u interval_total=%llu (ms; last <=8192)\n",
        (unsigned long long)frames,
        intervalN?[NSString stringWithFormat:@"%.3f",intervals[(unsigned)ceil(intervalN*.50)-1]*1000]:@"NA",
        intervalN?[NSString stringWithFormat:@"%.3f",intervals[(unsigned)ceil(intervalN*.95)-1]*1000]:@"NA",
        (unsigned long long)drops,(unsigned long long)errors,intervalN,(unsigned long long)intervalCount];
    [s appendString:@"drops=local invalid/non-increasing PTS only; transport/decoder losses unknown. Times=CLOCK_MONOTONIC seconds; blank=not reached.\nseq,type,generation,gesture,result,queue_depth,t_submit,t_received,t_report_return,t_barrier_return,report_code,barrier_code\n"];
    for(unsigned i=0;i<n;i++){
        Record r=records[i];
        [s appendFormat:@"%llu,%s,%llu,%llu,%s,%u,%.9f,%@,%@,%@,%d,%d\n",(unsigned long long)r.event.seq,kinds[r.event.kind],(unsigned long long)r.event.generation,(unsigned long long)r.event.gesture,results[r.result],r.depth,r.event.submit,
            r.received?[NSString stringWithFormat:@"%.9f",r.received]:@"",
            r.reportReturn?[NSString stringWithFormat:@"%.9f",r.reportReturn]:@"",
            r.barrierReturn?[NSString stringWithFormat:@"%.9f",r.barrierReturn]:@"",r.reportCode,r.barrierCode];
    }
    // Bound output too: a pipe whose reader stopped must not defeat the watchdog.
    NSData *data=[s dataUsingEncoding:NSUTF8StringEncoding];
    int flags=fcntl(STDOUT_FILENO,F_GETFL); fcntl(STDOUT_FILENO,F_SETFL,flags|O_NONBLOCK);
    size_t offset=0; double deadline=nowSec()+3;
    while(offset<data.length && nowSec()<deadline){
        ssize_t wrote=write(STDOUT_FILENO,(const char*)data.bytes+offset,data.length-offset);
        if(wrote>0) offset+=(size_t)wrote;
        else if(errno==EAGAIN || errno==EINTR){ struct pollfd p={STDOUT_FILENO,POLLOUT,0}; poll(&p,1,50); }
        else break;
    }
    if(offset<data.length) code=8;
    _Exit(code);
}

@interface InProcSink : NSObject @end
@implementation InProcSink
- (void)didReceiveSampleBuffer:(CMSampleBufferRef)sb {
    if(!sb) return;
    double t=nowSec(); CMTime pts=CMSampleBufferGetPresentationTimeStamp(sb);
    pthread_mutex_lock(&gLock);
    if(gCollect && !gStopping){
        if(!CMTIME_IS_NUMERIC(pts) || (CMTIME_IS_NUMERIC(gNewestPTS) && CMTimeCompare(pts,gNewestPTS)<=0)) gDrops++;
        else {
            gNewestPTS=pts; gFrames++;
            if(gLastFrame) gFrameIntervals[gIntervals++%Capacity]=t-gLastFrame;
            gLastFrame=t;
        }
    }
    pthread_mutex_unlock(&gLock);
}
- (void)streamOutput:(id)o didReceiveSampleBuffer:(CMSampleBufferRef)sb { [self didReceiveSampleBuffer:sb]; }
@end
static id gImageQueue = nil;
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


@interface FrameSink : NSObject @end
@implementation FrameSink
- (void)stream:(id)s didStart:(BOOL)ok error:(NSError*)e { if(!ok) mediaError([NSString stringWithFormat:@"stream did not start: %@",e]); }
- (void)streamDidStop:(id)s { mediaError(@"unexpected stream stop"); }
- (void)vcMediaStreamDidStop:(id)s { mediaError(@"unexpected media stream stop"); }
- (void)streamDidServerDie:(id)s { mediaError(@"media server died"); }
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


static int openInput(const char *dev){ // called only on gInputQueue
    dispatch_queue_t queue=dispatch_queue_create("ipb.mirror.hid.service",DISPATCH_QUEUE_SERIAL);
    xpc_connection_t conn=xpc_connection_create("com.apple.CoreDevice.CoreDeviceService",queue);
    xpc_connection_set_event_handler(conn,^(xpc_object_t event){});
    xpc_connection_resume(conn);
    xpc_object_t input=xpc_dictionary_create_empty();
    xpc_dictionary_set_string(input,"featureIdentifier","com.apple.coredevice.feature.remote.universalhidservice");
    xpc_object_t reply=xpc_connection_send_message_with_reply_sync(conn,action_env("com.apple.coredevice.action.createservicesocket",dev,input));
    xpc_object_t output=reply && xpc_get_type(reply)==XPC_TYPE_DICTIONARY ? xpc_dictionary_get_dictionary(reply,"CoreDevice.output") : NULL;
    if(!output){
        xpc_object_t error=reply && xpc_get_type(reply)==XPC_TYPE_DICTIONARY ? xpc_dictionary_get_dictionary(reply,"CoreDevice.error") : NULL;
        int64_t code=error?xpc_dictionary_get_int64(error,"code"):0;
        const char *domain=error?xpc_dictionary_get_string(error,"domain"):NULL;
        char *description=reply?xpc_copy_description(reply):NULL;
        int result=domain && !strcmp(domain,"com.apple.dt.CoreDeviceError") && code==4000?4:3;
        fail(result,[NSString stringWithFormat:@"UHID service socket refused: %s",description?description:"null reply"]);
        free(description); xpc_connection_cancel(conn); return result;
    }
    gInputFD=xpc_dictionary_dup_fd(output,"fileDescriptor");
    uint64_t flags=xpc_dictionary_get_uint64(output,"remoteXPCVersionFlags");
    xpc_connection_cancel(conn);
    if(gInputFD<0) DIE(3,"UHID service reply has no fd");
    // Separate error callback queue: a synchronous Swift sender must not delay invalidation.
    gInput=xpc_remote_connection_create_with_connected_fd(gInputFD,dispatch_queue_create("ipb.mirror.hid.events",DISPATCH_QUEUE_SERIAL),flags,0);
    if(!gInput) DIE(1,"UHID RemoteXPC create failed");
    pthread_mutex_lock(&gLock); gInputLive=YES; pthread_mutex_unlock(&gLock);
    xpc_remote_connection_set_event_handler(gInput,^(xpc_object_t event){
        if(event && xpc_get_type(event)==XPC_TYPE_ERROR){
            pthread_mutex_lock(&gLock); BOOL active=gInputLive && !gStopping; pthread_mutex_unlock(&gLock);
            if(active){
                const char *desc=xpc_dictionary_get_string(event,XPC_ERROR_KEY_DESCRIPTION);
                inputError([NSString stringWithFormat:@"UHID RemoteXPC error: %s",desc?desc:"unknown"]);
            }
        }
    });
    xpc_remote_connection_activate(gInput);
    return 0;
}

// Only this worker owns state, active gesture and prior relative-pointer position.
// One drain block, not one dispatch block per event. Queue capacity excludes the
// one executing event. No coalescing, replay, sleep, or per-event output.
static void drainInput(void){
    static enum { Idle, Pressed, Ending } state=Idle;
    static uint64_t activeGesture,activeGeneration;
    static double previousX,previousY;
    for(;;){ @autoreleasepool {
        pthread_mutex_lock(&gLock);
        if(!gCount){ gWorker=NO; pthread_mutex_unlock(&gLock); return; }
        unsigned index=gPending[gHead]; gHead=(gHead+1)%PendingLimit; gCount--;
        Record r=gRecords[index];
        r.received=nowSec(); r.result=Running; gRecords[index]=r;
        pthread_mutex_unlock(&gLock);
        const Event event=r.event; // immutable main-thread-produced value
        uint64_t generation=atomic_load(&gGeneration);
        if(activeGeneration!=generation){ state=Idle; activeGesture=0; }
        if(event.generation!=generation || atomic_load(&gFailure)) r.result=Rejected;
        else if((event.kind==Down && state!=Idle) ||
                (event.kind!=Down && (state!=Pressed || activeGesture!=event.gesture))) {
            r.result=Rejected; inputError(@"invalid input state transition");
        }else{
            if(event.kind==Down){
                state=Pressed; activeGesture=event.gesture; activeGeneration=event.generation;
                previousX=event.x; previousY=event.y;
            }else if(event.kind==Up) state=Ending;
            // Experimental mapping, NOT an absolute-coordinate protocol claim:
            // model path x=.35..65,y=.5; 1000 relative units per model unit.
            // Pointer is relative (docs/protocol.md Pointer); DOWN/UP use zero delta.
            // Quantize cumulative positions so low-amplitude MOVE rounding does not drift.
            int64_t dx=event.kind==Move?llround(event.x*1000)-llround(previousX*1000):0;
            int64_t dy=event.kind==Move?llround(event.y*1000)-llround(previousY*1000):0;
            uint64_t words[2]={0,0};
            int count=uhid_make_pointer_hid_report(dx,dy,event.kind==Up?0:1,0,0,0,words);
            if(count!=sizeof words){ r.result=BuildFailed; r.reportCode=count; inputError(@"pointer report construction failed"); }
            else if(event.generation!=atomic_load(&gGeneration)) r.result=Rejected;
            else {
                r.reportCode=coredevice_send_universalhid_hid_report(gInput,words,0x501);
                r.reportReturn=nowSec(); r.result=r.reportCode?SendFailed:Sent;
                // Publish the third point before a possibly stalled barrier.
                pthread_mutex_lock(&gLock); gRecords[index]=r; pthread_mutex_unlock(&gLock);
                if(r.reportCode) inputError(@"UHID report sender failed (see report_code)");
                else if(event.generation!=atomic_load(&gGeneration)) r.result=Interrupted;
                else if(event.kind==Up){
                    r.barrierCode=coredevice_send_universalhid_barrier(gInput);
                    r.barrierReturn=nowSec();
                    if(r.barrierCode){ r.result=BarrierFailed; inputError(@"UHID barrier failed (see barrier_code)"); }
                    else if(event.generation!=atomic_load(&gGeneration)) r.result=Interrupted;
                    state=Idle; activeGesture=0;
                }
            }
            previousX=event.x; previousY=event.y;
        }
        if(event.generation!=atomic_load(&gGeneration)){ state=Idle; activeGesture=0; }
        pthread_mutex_lock(&gLock); gRecords[index]=r; pthread_mutex_unlock(&gLock);
    }}
}
static void submit(Kind kind,uint64_t gesture,uint64_t generation,double x,double y){
    NSCAssert([NSThread isMainThread],@"producer must run on main thread");
    const Event event={gSubmitted+1,generation,gesture,kind,x,y,nowSec()};
    BOOL overloaded=NO;
    pthread_mutex_lock(&gLock);
    unsigned index=gSubmitted++%Capacity;
    Record r={.event=event,.depth=gCount,.result=Pending};
    if(gStopping || generation!=atomic_load(&gGeneration) || atomic_load(&gFailure)) r.result=Rejected;
    else if(gCount==PendingLimit){ r.result=Overload; overloaded=YES; }
    else {
        gPending[(gHead+gCount)%PendingLimit]=index; gCount++;
        if(gCount>gMaxDepth) gMaxDepth=gCount;
        if(!gWorker){ gWorker=YES; dispatch_group_async(gInputGroup,gInputQueue,^{ drainInput(); }); }
    }
    gRecords[index]=r;
    pthread_mutex_unlock(&gLock);
    // Losing DOWN/UP/MOVE invalidates the entire gesture, never sends a partial replay.
    if(overloaded) inputError(@"pending input queue overloaded");
}
static void pumpUntil(double deadline){
    while(nowSec()<deadline && !atomic_load(&gFailure))
        [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:MIN(.005,MAX(0,deadline-nowSec()))]];
}
static void armWatchdog(dispatch_source_t timer,double seconds){
    dispatch_source_set_timer(timer,dispatch_time(DISPATCH_TIME_NOW,(int64_t)(seconds*NSEC_PER_SEC)),DISPATCH_TIME_FOREVER,0);
}
static void usage(void){
    fprintf(stderr,"usage: ipb-mirror-probe <coredevice-uuid> <utun> <hostIP> <deviceIP> [--drag-seconds S] [--hz N] [--gestures G] [--no-input]\n"
        "defaults: 3 seconds, 60 Hz, 3 gestures; 0.5s between gestures. <=8192 total events, <=3600s collection.\n"
        "Requires GUI display session; input service 0x501 requires iOS 27. Model path is normalized; pointer deltas do not establish absolute screen position.\n");
}
static int runProbe(int argc,char **argv,dispatch_source_t watchdog){
    if(argc<5){ usage(); DIE(2,"missing arguments"); }
    const char *dev=argv[1],*utun=argv[2],*rxip=argv[3],*txip=argv[4];
    double dragSeconds=3,hz=60,gesturesValue=3; BOOL noInput=NO;
    for(int i=5;i<argc;i++){
        if(!strcmp(argv[i],"--no-input")){ noInput=YES; continue; }
        double *target=NULL;
        if(!strcmp(argv[i],"--drag-seconds")) target=&dragSeconds;
        else if(!strcmp(argv[i],"--hz")) target=&hz;
        else if(!strcmp(argv[i],"--gestures")) target=&gesturesValue;
        if(!target || i+1==argc){ usage(); DIE(2,"unknown/incomplete option"); }
        char *end=NULL; errno=0; *target=strtod(argv[++i],&end);
        if(errno || end==argv[i] || *end || !isfinite(*target) || *target<=0) DIE(2,"options must be finite positive numbers");
    }
    double stepsValue=round(dragSeconds*hz);
    if(!isfinite(stepsValue) || stepsValue<1 || fabs(stepsValue-dragSeconds*hz)>1e-6 ||
       gesturesValue!=floor(gesturesValue) || (stepsValue+2)*gesturesValue>Capacity ||
       dragSeconds*gesturesValue+.5*(gesturesValue-1)>3600)
        DIE(2,"S*Hz must be integral; G integral; total events <=8192; duration <=3600s");
    uuid_t deviceUUID; if(uuid_parse(dev,deviceUUID)) DIE(2,"invalid CoreDevice UUID");
    unsigned moves=(unsigned)stepsValue,gestures=(unsigned)gesturesValue;
    double runSeconds=dragSeconds*gestures+.5*(gestures-1);
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
    xpc_object_t out=rep && xpc_get_type(rep)==XPC_TYPE_DICTIONARY ? xpc_dictionary_get_dictionary(rep,"CoreDevice.output") : NULL;
    if(!out) DIE(3,"createservicesocket: no output (device/service unavailable)");
    int sfd=xpc_dictionary_dup_fd(out,"fileDescriptor");
    uint64_t flags=xpc_dictionary_get_uint64(out,"remoteXPCVersionFlags");
    if(sfd<0) DIE(3,"no service fd");
    xrc_t rc=xpc_remote_connection_create_with_connected_fd(sfd,dispatch_queue_create("ipb.video.rc",0),flags,0);
    if(!rc) DIE(3,"media RemoteXPC create failed");
    xpc_remote_connection_set_event_handler(rc,^(xpc_object_t ev){
        if(ev && xpc_get_type(ev)==XPC_TYPE_ERROR){
            const char *desc=xpc_dictionary_get_string(ev,XPC_ERROR_KEY_DESCRIPTION);
            mediaError([NSString stringWithFormat:@"media RemoteXPC: %s",desc?desc:"unknown"]);
        }
    });
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
    if(!srep || xpc_get_type(srep)!=XPC_TYPE_DICTIONARY) DIE(5,"mediastreamstart: null/error reply");
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
    o2[@"avcMediaStreamOptionRunInProcess"]=@(YES);   // default: decode in-process (no entitlement)
    o2[@"avcMediaStreamOptionClientName"]=@"CoreDeviceScreenSharing";
    o2[@"avcMediaStreamOptionClientSessionID"]=[[NSUUID alloc] initWithUUIDString:sessID];

    xpc_object_t socks=xpc_dictionary_create_empty();
    xpc_dictionary_set_fd(socks,"avcKeySharedSocket",rtp);
    gDelegateQueue=dispatch_queue_create("ipb.mirror.media.delegate",DISPATCH_QUEUE_SERIAL);
    gNewestPTS=kCMTimeInvalid;
    installInProcessSink(); // original VCImageQueue/VCStreamOutput path, GUI session required
    Class VS=objc_getClass("AVCVideoStream"); if(!VS) DIE(6,"no AVCVideoStream class");
    NSError *se=nil;
    AVCVideoStream *vs=[[VS alloc] initWithNetworkSockets:(id)socks options:o2 error:&se];
    if(!vs) DIE(6,"AVCVideoStream init: %s",se?se.description.UTF8String:"?");
    FrameSink *sink=[FrameSink new];
    [vs setDelegate:sink];
    NSError *ce=nil; if(![vs configure:cfg error:&ce]) DIE(6,"configure: %s",ce?ce.description.UTF8String:"?");
    gStream=vs;
    [vs start];

    pumpUntil(nowSec()+2.5); // same warmup budget, no input until media has started
    if(atomic_load(&gFailure)) return atomic_load(&gFailure);
    gInputQueue=dispatch_queue_create("ipb.mirror.input",DISPATCH_QUEUE_SERIAL);
    gInputGroup=dispatch_group_create();
    if(!noInput){
        dispatch_group_async(gInputGroup,gInputQueue,^{ openInput(dev); });
        while(dispatch_group_wait(gInputGroup,DISPATCH_TIME_NOW)!=0 && !atomic_load(&gFailure)) pumpUntil(nowSec()+.005);
        if(atomic_load(&gFailure)) return atomic_load(&gFailure);
    }
    // Start a fresh, equally defined collection window in input and baseline modes.
    pthread_mutex_lock(&gLock); gCollect=YES; pthread_mutex_unlock(&gLock);
    armWatchdog(watchdog,runSeconds+10); // bounds collection and input drain
    double start=nowSec();
    if(noInput) pumpUntil(start+runSeconds);
    else for(unsigned gesture=1;gesture<=gestures && !atomic_load(&gFailure);gesture++){
        double begin=start+(gesture-1)*(dragSeconds+.5);
        pumpUntil(begin);
        uint64_t generation=atomic_load(&gGeneration);
        submit(Down,gesture,generation,.35,.5);
        for(unsigned step=1;step<=moves && !atomic_load(&gFailure);step++){
            pumpUntil(begin+step/hz);
            if(atomic_load(&gFailure)) break;
            submit(Move,gesture,generation,.35+.30*step/moves,.5);
        }
        // Even after failure, preserve the submitted UP outcome; old generation is rejected.
        submit(Up,gesture,generation,.65,.5);
    }
    // Freeze media at the nominal end, before input drain; baseline and load use same window.
    pthread_mutex_lock(&gLock); gCollect=NO; pthread_mutex_unlock(&gLock);
    double drainDeadline=nowSec()+5;
    while(dispatch_group_wait(gInputGroup,DISPATCH_TIME_NOW)!=0 && nowSec()<drainDeadline)
        [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:.005]];
    if(dispatch_group_wait(gInputGroup,DISPATCH_TIME_NOW)) fail(9,@"input drain exceeded 5s; device release is not guaranteed");
    pthread_mutex_lock(&gLock); uint64_t frames=gFrames; pthread_mutex_unlock(&gLock);
    if(!frames) fail(7,@"no valid media frames during collection");
    // Keep watchdog armed across main-thread private stop and input cancellation.
    armWatchdog(watchdog,10);
    pthread_mutex_lock(&gLock); gStopping=YES; pthread_mutex_unlock(&gLock);
    [vs stop];
    if(!noInput && !dispatch_group_wait(gInputGroup,DISPATCH_TIME_NOW)){
        dispatch_group_async(gInputGroup,gInputQueue,^{
            pthread_mutex_lock(&gLock); gInputLive=NO; pthread_mutex_unlock(&gLock);
            if(gInput) xpc_remote_connection_cancel(gInput);
            if(gInputFD>=0) close(gInputFD);
        });
        if(dispatch_group_wait(gInputGroup,dispatch_time(DISPATCH_TIME_NOW,5*NSEC_PER_SEC))) fail(9,@"UHID shutdown exceeded 5s");
    }
    xpc_remote_connection_cancel(rc); close(sfd); close(rtp); xpc_connection_cancel(c);
    return atomic_load(&gFailure);
}
int main(int argc,char **argv){ @autoreleasepool {
    signal(SIGPIPE,SIG_IGN);
    dispatch_queue_t watchdogQueue=dispatch_queue_create("ipb.mirror.watchdog",DISPATCH_QUEUE_SERIAL);
    dispatch_source_t watchdog=dispatch_source_create(DISPATCH_SOURCE_TYPE_TIMER,0,0,watchdogQueue);
    dispatch_source_set_event_handler(watchdog,^{ finish(9,@"watchdog expired during setup/collection/shutdown; device release is not guaranteed"); });
    armWatchdog(watchdog,45); dispatch_resume(watchdog);
    signal(SIGINT,SIG_IGN); signal(SIGTERM,SIG_IGN);
    dispatch_source_t interrupt=dispatch_source_create(DISPATCH_SOURCE_TYPE_SIGNAL,SIGINT,0,watchdogQueue);
    dispatch_source_t terminate=dispatch_source_create(DISPATCH_SOURCE_TYPE_SIGNAL,SIGTERM,0,watchdogQueue);
    dispatch_source_set_event_handler(interrupt,^{ finish(130,@"SIGINT; device release is not guaranteed"); });
    dispatch_source_set_event_handler(terminate,^{ finish(143,@"SIGTERM; device release is not guaranteed"); });
    dispatch_resume(interrupt); dispatch_resume(terminate);
    @try {
        int result=runProbe(argc,argv,watchdog);
        finish(result,result?@"probe failed":@"complete (host sender return is not device acknowledgement)");
    } @catch(NSException *exception) {
        finish(2,[NSString stringWithFormat:@"exception: %@",exception]);
    }
    return 9;
}}
