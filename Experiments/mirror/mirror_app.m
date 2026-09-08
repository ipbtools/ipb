#import <Foundation/Foundation.h>
#import <CoreMedia/CoreMedia.h>
#import <CoreVideo/CoreVideo.h>
#import <CoreImage/CoreImage.h>
#import <objc/runtime.h>
#import <AppKit/AppKit.h>
#import <AVFoundation/AVFoundation.h>
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

#define LOGE(...) do{ fprintf(stderr, "ipb-mirror: " __VA_ARGS__); fprintf(stderr,"\n"); }while(0)
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
// HID evidence: docs/protocol.md Wire Format and Sources/action_sender.m:625,
// using the existing Xcode 27 oracle glue unchanged.
extern int uhid_make_digitizer_hid_report(double,double,int,int,void*);
extern int coredevice_print_connected_descriptors_async_raw(xrc_t);
extern int coredevice_send_universalhid_hid_report(xrc_t,const void*,uint64_t);
extern int coredevice_send_universalhid_barrier(xrc_t);
extern void xpc_remote_connection_cancel(xrc_t);
extern int coredevice_send_hid_button_custom(xrc_t,uint64_t,uint64_t,uint8_t);
extern int coredevice_send_hid_button_barrier(xrc_t);
extern int coredevice_send_hid_digitizer_cgpoint(xrc_t,double,double,double,double,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t);

enum { Capacity=8192, PendingLimit=64 };
typedef enum { Down, Move, Up, KeyHome, KeyRecents, KeyVolumeUp, KeyVolumeDown } Kind;
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
static CMSampleBufferRef gLatest;
static CVPixelBufferRef gScreenshotFrame; // latest accepted frame, independent of display consumption
static _Atomic bool gScreenshotBusy=false;
static BOOL gLocalShortcutPending; // at most one local action awaiting the input barrier
static dispatch_group_t gScreenshotGroup;
static uint64_t gDisplayDrops,gDisplayed,gBlackBars;
static BOOL gReady,gClosing,gMousePressed;
static uint64_t gServiceID,gGesture,gMouseGeneration;
static double gMouseX,gMouseY;
static CGSize gVideoSize;
static AVSampleBufferDisplayLayer *gDisplay;
static NSWindow *gWindow;
static int gOutputFD=-1;
static dispatch_source_t gWatchdog;
static _Atomic bool gWatchdogExpired=false;
static xrc_t gMediaRemote;
static xpc_connection_t gMediaService;
static int gMediaFD=-1,gRTP=-1;
static void requestClose(NSString *reason);
static void presentLatest(void);
static AVCVideoStream *gStream;
static dispatch_queue_t gDelegateQueue,gInputQueue;
static dispatch_group_t gInputGroup;
static xrc_t gInput; // only input queue reads/writes this connection and gesture state
static int gInputFD=-1;
static xrc_t gButton,gDigitizer;
static int gButtonFD=-1,gDigitizerFD=-1;
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
    unsigned n=MIN(gSubmitted,Capacity); memcpy(records,gRecords,sizeof records);
    uint64_t frames=gFrames,drops=gDrops,errors=gMediaErrors,intervalCount=gIntervals;
    memcpy(intervals,gFrameIntervals,sizeof intervals);
    unsigned maxDepth=gMaxDepth;
    if(atomic_load(&gFailure)){ code=atomic_load(&gFailure); reason=gReason; }
    else if(gReason) reason=gReason;
    uint64_t displayDrops=gDisplayDrops,displayed=gDisplayed,blackBars=gBlackBars;
    pthread_mutex_unlock(&gLock);
    NSMutableString *s=[NSMutableString stringWithFormat:@"ipb-mirror: exit=%d reason=%@\n",code,reason];
    [s appendFormat:@"enqueued=%llu display_backpressure_drops=%llu black_bar_rejections=%llu\n",
        (unsigned long long)displayed,(unsigned long long)displayDrops,(unsigned long long)blackBars];
    static double values[4][Capacity]; unsigned counts[4]={0};
    unsigned executed=0,rejected=0,overload=0,inflight=0;
    const char *kinds[]={"DOWN","MOVE","UP","KEY_HOME","KEY_RECENTS","KEY_VOLUME_UP","KEY_VOLUME_DOWN"};
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
    [s appendString:@"KEY_* report_return=first send return; barrier_return=button barrier or RECENTS end return (digitizer has no barrier in the existing oracle).\n"];
    [s appendString:@"drops=local invalid/non-increasing PTS only; transport/decoder losses unknown. Times=CLOCK_MONOTONIC seconds; blank=not reached.\nseq,type,generation,gesture,result,queue_depth,x,y,t_submit,t_received,t_report_return,t_barrier_return,report_code,barrier_code\n"];
    for(unsigned i=0;i<n;i++){
        Record r=records[i];
        [s appendFormat:@"%llu,%s,%llu,%llu,%s,%u,%.5f,%.5f,%.9f,%@,%@,%@,%d,%d\n",(unsigned long long)r.event.seq,kinds[r.event.kind],(unsigned long long)r.event.generation,(unsigned long long)r.event.gesture,results[r.result],r.depth,r.event.x,r.event.y,r.event.submit,
            r.received?[NSString stringWithFormat:@"%.9f",r.received]:@"",
            r.reportReturn?[NSString stringWithFormat:@"%.9f",r.reportReturn]:@"",
            r.barrierReturn?[NSString stringWithFormat:@"%.9f",r.barrierReturn]:@"",r.reportCode,r.barrierCode];
    }
    // Bound output too: a pipe whose reader stopped must not defeat the watchdog.
    NSData *data=[s dataUsingEncoding:NSUTF8StringEncoding];
    int flags=fcntl(gOutputFD,F_GETFL); fcntl(gOutputFD,F_SETFL,flags|O_NONBLOCK);
    size_t offset=0; double deadline=nowSec()+3;
    while(offset<data.length && nowSec()<deadline){
        ssize_t wrote=write(gOutputFD,(const char*)data.bytes+offset,data.length-offset);
        if(wrote>0) offset+=(size_t)wrote;
        else if(errno==EAGAIN || errno==EINTR){ struct pollfd p={gOutputFD,POLLOUT,0}; poll(&p,1,50); }
        else break;
    }
    if(offset<data.length) code=8;
    _Exit(code);
}

@interface InProcSink : NSObject @end
@implementation InProcSink
- (void)didReceiveSampleBuffer:(CMSampleBufferRef)sb {
    if(!sb) return;
    double t=nowSec(); CMTime pts=CMSampleBufferGetOutputPresentationTimeStamp(sb);
    pthread_mutex_lock(&gLock);
    if(gCollect && !gStopping){
        if(!CMTIME_IS_NUMERIC(pts) || !CMSampleBufferGetImageBuffer(sb) ||
           (CMTIME_IS_NUMERIC(gNewestPTS) && CMTimeCompare(pts,gNewestPTS)<=0)) gDrops++;
        else {
            gNewestPTS=pts; gFrames++;
            if(gLastFrame) gFrameIntervals[gIntervals++%Capacity]=t-gLastFrame;
            gLastFrame=t;
            if(gLatest){ CFRelease(gLatest); gDisplayDrops++; }
            gLatest=(CMSampleBufferRef)CFRetain(sb);
            if(gScreenshotFrame) CVPixelBufferRelease(gScreenshotFrame);
            gScreenshotFrame=CVPixelBufferRetain(CMSampleBufferGetImageBuffer(sb));
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
    Class C=objc_getClass("VCImageQueue"); if(!C){ fail(6,@"no VCImageQueue class"); return; }
    Method m=class_getInstanceMethod(C,sel_registerName("start"));
    if(m){ gOrigIQStart=method_getImplementation(m); method_setImplementation(m,(IMP)swz_iq_start); }
    else fail(6,@"no VCImageQueue start method");
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


static int openInput(const char *dev,const char *feature,xrc_t *remote,int *fd){ // called only on gInputQueue
    dispatch_queue_t queue=dispatch_queue_create("ipb.mirror.hid.service",DISPATCH_QUEUE_SERIAL);
    xpc_connection_t conn=xpc_connection_create("com.apple.CoreDevice.CoreDeviceService",queue);
    xpc_connection_set_event_handler(conn,^(xpc_object_t event){});
    xpc_connection_resume(conn);
    xpc_object_t input=xpc_dictionary_create_empty();
    xpc_dictionary_set_string(input,"featureIdentifier",feature);
    xpc_object_t reply=xpc_connection_send_message_with_reply_sync(conn,action_env("com.apple.coredevice.action.createservicesocket",dev,input));
    xpc_object_t output=reply && xpc_get_type(reply)==XPC_TYPE_DICTIONARY ? xpc_dictionary_get_dictionary(reply,"CoreDevice.output") : NULL;
    if(!output){
        xpc_object_t error=reply && xpc_get_type(reply)==XPC_TYPE_DICTIONARY ? xpc_dictionary_get_dictionary(reply,"CoreDevice.error") : NULL;
        int64_t code=error?xpc_dictionary_get_int64(error,"code"):0;
        const char *domain=error?xpc_dictionary_get_string(error,"domain"):NULL;
        char *description=reply?xpc_copy_description(reply):NULL;
        int result=domain && !strcmp(domain,"com.apple.dt.CoreDeviceError") && code==4000?4:3;
        fail(result,[NSString stringWithFormat:@"%s service socket refused: %s",feature,description?description:"null reply"]);
        free(description); xpc_connection_cancel(conn); return result;
    }
    *fd=xpc_dictionary_dup_fd(output,"fileDescriptor");
    uint64_t flags=xpc_dictionary_get_uint64(output,"remoteXPCVersionFlags");
    xpc_connection_cancel(conn);
    if(*fd<0) DIE(3,"%s service reply has no fd",feature);
    // Separate error callback queue: a synchronous Swift sender must not delay invalidation.
    *remote=xpc_remote_connection_create_with_connected_fd(*fd,dispatch_queue_create("ipb.mirror.hid.events",DISPATCH_QUEUE_SERIAL),flags,0);
    if(!*remote) DIE(1,"%s RemoteXPC create failed",feature);
    pthread_mutex_lock(&gLock); gInputLive=YES; pthread_mutex_unlock(&gLock);
    xpc_remote_connection_set_event_handler(*remote,^(xpc_object_t event){
        if(event && xpc_get_type(event)==XPC_TYPE_ERROR){
            pthread_mutex_lock(&gLock); BOOL active=gInputLive && !gStopping; pthread_mutex_unlock(&gLock);
            if(active){
                const char *desc=xpc_dictionary_get_string(event,XPC_ERROR_KEY_DESCRIPTION);
                inputError([NSString stringWithFormat:@"%s RemoteXPC error: %s",feature,desc?desc:"unknown"]);
            }
        }
    });
    xpc_remote_connection_activate(*remote);
    return 0;
}

// A key owns the drain until its final continuation. Exactly one delayed block
// exists at a time; gWorker stays YES, and the group includes the entire sequence.
// Sources/action_sender.m button_click and digitizer_swipe + bin/ipb recents are
// the timing/argument oracle. No guessed digitizer barrier is sent.
static void drainInput(void);
static void keyStep(unsigned index,unsigned step){
    pthread_mutex_lock(&gLock); Record r=gRecords[index]; pthread_mutex_unlock(&gLock);
    BOOL recents=r.event.kind==KeyRecents,done=NO;
    double delay=0;
    if(r.event.generation!=atomic_load(&gGeneration)){
        r.result=Interrupted; done=YES;
    }else{
        int code;
        if(recents){
            unsigned position=MIN(step,12u);
            code=coredevice_send_hid_digitizer_cgpoint(gDigitizer,.5,.995+(.74-.995)*position/12.0,
                                                      0,0,1,step==0?0:step==13?2:1,3,0,0);
            done=step==13;
            delay=step==12?1.05:.03;
        }else{
            // Home: docs/protocol.md. Volume: M3 brief, 2026-09-08 13 Pro:
            // E9 showed a HUD; EA is the paired usage, rc=0 only (HUD unconfirmed).
            uint64_t usage=r.event.kind==KeyHome?0x40:r.event.kind==KeyVolumeUp?0xE9:0xEA;
            code=step==2?coredevice_send_hid_button_barrier(gButton):
                coredevice_send_hid_button_custom(gButton,0x0c,usage,(uint8_t)step);
            done=step==2; delay=step==0?.08:.12;
        }
        double returned=nowSec();
        if(step==0){ r.reportCode=code; r.reportReturn=returned; }
        if(done){ r.barrierCode=code; r.barrierReturn=returned; }
        if(code){
            if(!done) r.reportCode=code;
            r.result=done?BarrierFailed:SendFailed; done=YES;
            inputError(@"shortcut sender failed (see CSV codes)");
        }else if(r.event.generation!=atomic_load(&gGeneration)){
            r.result=Interrupted; done=YES;
        }else if(done) r.result=Sent;
    }
    pthread_mutex_lock(&gLock); gRecords[index]=r; pthread_mutex_unlock(&gLock);
    if(done){
        // Preserve the oracle's post-END settling interval before the next input.
        double settle=recents && r.result==Sent?.25:0;
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW,(int64_t)(settle*NSEC_PER_SEC)),gInputQueue,^{
            drainInput(); dispatch_group_leave(gInputGroup);
        });
    }else dispatch_after(dispatch_time(DISPATCH_TIME_NOW,(int64_t)(delay*NSEC_PER_SEC)),gInputQueue,^{ keyStep(index,step+1); });
}

// Only this worker owns the HID state and active gesture.
// One drain block, not one dispatch block per event. Queue capacity excludes the
// one executing event. No coalescing, replay, sleep, or per-event output.
static void drainInput(void){
    static enum { Idle, Pressed, Ending } state=Idle;
    static uint64_t activeGesture,activeGeneration;
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
        if(event.generation!=generation || (atomic_load(&gFailure) && event.kind!=Up)) r.result=Rejected;
        else if(event.kind>=KeyHome){
            if(state!=Idle){ r.result=Rejected; inputError(@"shortcut reached active touch; release required"); }
            else { dispatch_group_enter(gInputGroup); keyStep(index,0); return; }
        }
        else if((event.kind==Down && state!=Idle) ||
                (event.kind!=Down && (state!=Pressed || activeGesture!=event.gesture))) {
            r.result=Rejected; inputError(@"invalid input state transition");
        }else{
            if(event.kind==Down){
                state=Pressed; activeGesture=event.gesture; activeGeneration=event.generation;
            }else if(event.kind==Up) state=Ending;
            uint64_t words[2]={0,0};
            int count=uhid_make_digitizer_hid_report(event.x,event.y,event.kind!=Up,event.kind!=Up,words);
            if(count!=sizeof words){ r.result=BuildFailed; r.reportCode=count; inputError(@"digitizer report construction failed"); }
            else if(event.generation!=atomic_load(&gGeneration)) r.result=Rejected;
            else {
                r.reportCode=coredevice_send_universalhid_hid_report(gInput,words,gServiceID);
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
        }
        if(event.generation!=atomic_load(&gGeneration)){ state=Idle; activeGesture=0; }
        pthread_mutex_lock(&gLock); gRecords[index]=r; pthread_mutex_unlock(&gLock);
    }}
}
static void submit(Kind kind,uint64_t gesture,uint64_t generation,double x,double y,double submitted){
    NSCAssert([NSThread isMainThread],@"producer must run on main thread");
    // Existing oracle retains each report. End this prototype run before the ring
    // wraps, reserving its final slot for the release (same bounded policy as M1).
    if(gSubmitted>=Capacity) return;
    const Event event={gSubmitted+1,generation,gesture,kind,x,y,submitted};
    BOOL overloaded=NO;
    pthread_mutex_lock(&gLock);
    unsigned index=gSubmitted++%Capacity;
    Record r={.event=event,.depth=gCount,.result=Pending};
    if(gStopping || generation!=atomic_load(&gGeneration) || (atomic_load(&gFailure) && kind!=Up)) r.result=Rejected;
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
    if(atomic_load(&gWatchdogExpired) && seconds>5) return;
    dispatch_source_set_timer(timer,dispatch_time(DISPATCH_TIME_NOW,(int64_t)(seconds*NSEC_PER_SEC)),DISPATCH_TIME_FOREVER,0);
}
// Discovery reuses the existing printer oracle and bin/ipb's touchscreen match.
// Redirect only during startup, before AppKit input; finalizer uses a separate fd.
static void discoverService(void){
    FILE *capture=tmpfile();
    if(!capture){ fail(8,@"descriptor capture tmpfile failed"); return; }
    fflush(stdout);
    if(dup2(fileno(capture),STDOUT_FILENO)<0){ fclose(capture); fail(8,@"descriptor capture redirect failed"); return; }
    int result=coredevice_print_connected_descriptors_async_raw(gInput);
    fflush(stdout);
    int restored=dup2(gOutputFD,STDOUT_FILENO);
    long length=ftell(capture);
    if(result || restored<0 || length<0 || length>1024*1024){
        fclose(capture); fail(3,@"touchscreen descriptor discovery failed or output exceeded 1MiB"); return;
    }
    rewind(capture);
    char *line=NULL; size_t capacity=0;
    while(getline(&line,&capacity,capture)>0){
        if(strncmp(line,"connectedDescriptor[",20) || !strstr(line,"string:\"CoreDevice touchscreen(")) continue;
        char *id=strstr(line,"serviceID:");
        if(id){ char *end=NULL; errno=0; uint64_t value=strtoull(id+10,&end,0);
            if(!errno && end!=id+10 && (*end==' ' || *end=='\n') && value){ gServiceID=value; break; }
        }
    }
    free(line); fclose(capture);
    if(!gServiceID) fail(3,@"no touchscreen descriptor; use --service-id only with a known touchscreen ID");
}

static void releaseMouse(double submitted){
    if(!gMousePressed) return;
    gMousePressed=NO;
    submit(Up,gGesture,gMouseGeneration,gMouseX,gMouseY,submitted);
}
static void requestClose(NSString *reason){
    if(gClosing) return;
    releaseMouse(nowSec());
    gReady=NO; gClosing=YES;
    // First failure keeps its precise reason; successful close records its event.
    pthread_mutex_lock(&gLock);
    if(!gReason) gReason=reason;
    pthread_mutex_unlock(&gLock);
    armWatchdog(gWatchdog,10);
}

// Before the first frame use a screen-fitting placeholder; afterwards lock to
// presentation dimensions. Reapply on format/screen changes, never per frame.
static void fitWindow(CGSize ratio,BOOL lockAspect){
    NSScreen *screen=gWindow.screen ?: NSScreen.mainScreen;
    if(!screen) return;
    NSRect visible=screen.visibleFrame;
    NSSize available=[gWindow contentRectForFrameRect:visible].size;
    double height=MIN(gWindow.contentView.bounds.size.height,available.height);
    height=MIN(height,available.width*ratio.height/ratio.width);
    if(height<=0) return;
    NSSize content=NSMakeSize(height*ratio.width/ratio.height,height);
    if(lockAspect) gWindow.contentAspectRatio=ratio;
    [gWindow setContentSize:content];
    NSRect frame=gWindow.frame;
    frame.origin.x=MAX(NSMinX(visible),MIN(frame.origin.x,NSMaxX(visible)-frame.size.width));
    frame.origin.y=MAX(NSMinY(visible),MIN(frame.origin.y,NSMaxY(visible)-frame.size.height));
    [gWindow setFrame:frame display:YES];
    [gWindow.contentView setNeedsLayout:YES];
    [gWindow.contentView layoutSubtreeIfNeeded];
}

// Local shortcuts retain the existing aspect-ratio policy; only the requested size changes.
static void resizeMirror(BOOL actualSize){
    if(gVideoSize.width<=0 || gVideoSize.height<=0){ LOGE("resize: no video frame yet"); return; }
    NSScreen *screen=gWindow.screen ?: NSScreen.mainScreen;
    if(!screen) return;
    NSRect visible=screen.visibleFrame;
    NSSize available=[gWindow contentRectForFrameRect:visible].size;
    double scale=MIN(available.width/gVideoSize.width,available.height/gVideoSize.height);
    if(scale<=0) return;
    if(actualSize){
        double oneToOne=1.0/gWindow.backingScaleFactor;
        if(oneToOne<=scale) scale=oneToOne;
        else LOGE("Actual Size exceeds the visible screen; using Zoom to Fit.");
    }
    [gWindow setContentSize:NSMakeSize(gVideoSize.width*scale,gVideoSize.height*scale)];
    fitWindow(gVideoSize,YES);
}

static void saveScreenshot(void){
    if(atomic_exchange(&gScreenshotBusy,true)){ LOGE("screenshot: save already in progress; ignored"); return; }
    pthread_mutex_lock(&gLock);
    CVPixelBufferRef frame=gScreenshotFrame?CVPixelBufferRetain(gScreenshotFrame):NULL;
    pthread_mutex_unlock(&gLock);
    if(!frame){ atomic_store(&gScreenshotBusy,false); LOGE("screenshot: no video frame yet"); return; }
    if(!gScreenshotGroup) gScreenshotGroup=dispatch_group_create();
    dispatch_group_async(gScreenshotGroup,dispatch_get_global_queue(QOS_CLASS_UTILITY,0),^{ @autoreleasepool {
        @try {
            CIImage *image=[CIImage imageWithCVPixelBuffer:frame];
            CIContext *context=[CIContext contextWithOptions:nil];
            CGImageRef rendered=[context createCGImage:image fromRect:image.extent];
            NSBitmapImageRep *bitmap=rendered?[[NSBitmapImageRep alloc] initWithCGImage:rendered]:nil;
            if(rendered) CGImageRelease(rendered);
            NSData *png=[bitmap representationUsingType:NSBitmapImageFileTypePNG properties:@{}];
            NSString *name=[NSString stringWithFormat:@"ipb-mirror-%@.png",NSUUID.UUID.UUIDString];
            NSURL *directory=[[NSFileManager defaultManager] URLsForDirectory:NSPicturesDirectory inDomains:NSUserDomainMask].firstObject;
            NSError *error=nil;
            NSURL *destination=[directory URLByAppendingPathComponent:name];
            if(!png || !destination) LOGE("screenshot: PNG encoding or Pictures directory lookup failed");
            else if(![[NSFileManager defaultManager] createDirectoryAtURL:directory withIntermediateDirectories:YES attributes:nil error:&error] ||
                    ![png writeToURL:destination options:NSDataWritingAtomic error:&error])
                LOGE("screenshot: save failed: %s",error.description.UTF8String);
            else LOGE("screenshot saved: %s",destination.path.UTF8String);
        } @catch(NSException *exception){ LOGE("screenshot failed: %s",exception.description.UTF8String); }
        @finally { CVPixelBufferRelease(frame); atomic_store(&gScreenshotBusy,false); }
    }});
}

@interface MirrorView : NSView @end
@implementation MirrorView
- (BOOL)isFlipped { return YES; }
- (BOOL)acceptsFirstResponder { return YES; }
- (void)layout {
    [super layout];
    [CATransaction begin]; [CATransaction setDisableActions:YES];
    gDisplay.frame=self.bounds;
    gDisplay.contentsScale=self.window.backingScaleFactor;
    [CATransaction commit];
}
- (void)viewDidChangeBackingProperties { [super viewDidChangeBackingProperties]; [self setNeedsLayout:YES]; }
- (BOOL)mapEvent:(NSEvent*)event x:(double*)x y:(double*)y {
    if(gVideoSize.width<=0 || gVideoSize.height<=0) return NO;
    // Stay in the view's own (flipped, points) space. Backing conversion is NOT
    // used on purpose: -convertPointToBacking:/-convertRectToBacking: map into the
    // unflipped backing store, which negates y on a flipped view (measured: view
    // y=20 near the top became backing y=-40 against a bounds origin of -1688,
    // normalising to 0.976 instead of 0.024). The scale cancels in the ratio
    // anyway, so working in points is both correct and Retina-independent.
    NSRect bounds=self.bounds;
    NSPoint point=[self convertPoint:event.locationInWindow fromView:nil];
    NSRect content=AVMakeRectWithAspectRatioInsideRect(gVideoSize,bounds);
    if(content.size.width<=0 || content.size.height<=0 || !NSPointInRect(point,content)){
        pthread_mutex_lock(&gLock); gBlackBars++; pthread_mutex_unlock(&gLock); return NO;
    }
    *x=(point.x-content.origin.x)/content.size.width;
    *y=(point.y-content.origin.y)/content.size.height; // flipped view: top-left is (0,0)
    return YES;
}
- (BOOL)performKeyEquivalent:(NSEvent*)event {
    NSEventModifierFlags flags=event.modifierFlags &
        (NSEventModifierFlagCommand|NSEventModifierFlagShift|NSEventModifierFlagControl|NSEventModifierFlagOption);
    NSString *key=event.charactersIgnoringModifiers.lowercaseString;
    NSEventModifierFlags command=NSEventModifierFlagCommand,shiftCommand=command|NSEventModifierFlagShift;
    Kind kind=KeyHome;
    enum { DeviceKey, Screenshot, ZoomToFit, ActualSize } action=DeviceKey;
    // Device Hub bindings captured in the M4 brief (Xcode 27 beta 6).
    if(flags==shiftCommand && [key isEqualToString:@"h"]) kind=KeyHome;
    else if(flags==(shiftCommand|NSEventModifierFlagControl) && [key isEqualToString:@"h"]) kind=KeyRecents;
    else if(flags==command && key.length==1 && [key characterAtIndex:0]==NSUpArrowFunctionKey) kind=KeyVolumeUp;
    else if(flags==command && key.length==1 && [key characterAtIndex:0]==NSDownArrowFunctionKey) kind=KeyVolumeDown;
    else if(flags==shiftCommand && [key isEqualToString:@"s"]) action=Screenshot;
    else if(flags==command && [key isEqualToString:@"0"]) action=ZoomToFit;
    else if(flags==command && [key isEqualToString:@"1"]) action=ActualSize;
    else return [super performKeyEquivalent:event];
    double t=nowSec();
    if(event.isARepeat || !gReady || gClosing || atomic_load(&gFailure)) return YES;
    if(gSubmitted>=Capacity-2){ requestClose(@"event capacity reached"); return YES; }
    // Main producer clears pressed immediately: subsequent drag/up cannot revive
    // the old gesture. FIFO worker completes this UP + barrier before the key.
    releaseMouse(t);
    if(action==DeviceKey) submit(kind,0,atomic_load(&gGeneration),0,0,t);
    else if(!gLocalShortcutPending){
        gLocalShortcutPending=YES;
        uint64_t generation=atomic_load(&gGeneration);
        // The group includes the drain and all key continuations, hence the UP
        // barrier completes before any local action. One notification at most.
        dispatch_group_notify(gInputGroup,dispatch_get_main_queue(),^{
            gLocalShortcutPending=NO;
            if(!gReady || gClosing || atomic_load(&gFailure) || generation!=atomic_load(&gGeneration)) return;
            if(action==Screenshot) saveScreenshot();
            else resizeMirror(action==ActualSize);
        });
    }
    return YES;
}
- (void)mouseDown:(NSEvent*)event {
    double t=nowSec(),x,y; // real AppKit arrival, before conversion/submission
    if(!gReady || gClosing || gMousePressed || atomic_load(&gFailure)) return;
    if(gSubmitted>=Capacity-2){ requestClose(@"event capacity reached"); return; }
    if(![self mapEvent:event x:&x y:&y]) return;
    gMousePressed=YES; gGesture++; gMouseGeneration=atomic_load(&gGeneration);
    gMouseX=x; gMouseY=y; submit(Down,gGesture,gMouseGeneration,x,y,t);
}
- (void)mouseDragged:(NSEvent*)event {
    double t=nowSec(),x,y;
    if(!gMousePressed || !gReady || gClosing) return;
    if(gSubmitted>=Capacity-1){ requestClose(@"event capacity reached"); return; }
    if(![self mapEvent:event x:&x y:&y]) return;
    gMouseX=x; gMouseY=y; submit(Move,gGesture,gMouseGeneration,x,y,t);
}
- (void)mouseUp:(NSEvent*)event {
    double t=nowSec(),x,y;
    if(!gMousePressed) return;
    if([self mapEvent:event x:&x y:&y]){ gMouseX=x; gMouseY=y; }
    // An outside UP is rejected as a position, then ends at the last valid point.
    releaseMouse(t);
}
@end
@interface MirrorDelegate : NSObject <NSWindowDelegate,NSApplicationDelegate> @end
@implementation MirrorDelegate
- (BOOL)windowShouldClose:(NSWindow*)window { requestClose(@"window closed"); return NO; }
- (void)windowDidChangeScreen:(NSNotification*)n {
    if(gVideoSize.width>0 && gVideoSize.height>0) fitWindow(gVideoSize,YES);
}
- (void)windowDidResignKey:(NSNotification*)n { releaseMouse(nowSec()); }
- (void)applicationDidResignActive:(NSNotification*)n { releaseMouse(nowSec()); }
- (NSApplicationTerminateReply)applicationShouldTerminate:(NSApplication*)app {
    requestClose(@"application quit"); return NSTerminateCancel;
}
@end
static void createWindow(void){
    static MirrorDelegate *delegate; delegate=[MirrorDelegate new];
    NSApp.delegate=delegate;
    gWindow=[[NSWindow alloc] initWithContentRect:NSMakeRect(0,0,420,840)
        styleMask:NSWindowStyleMaskTitled|NSWindowStyleMaskClosable|NSWindowStyleMaskResizable|NSWindowStyleMaskMiniaturizable
        backing:NSBackingStoreBuffered defer:NO];
    gWindow.releasedWhenClosed=NO; gWindow.delegate=delegate;
    gWindow.title=@"ipb mirror";
    MirrorView *view=[[MirrorView alloc] initWithFrame:NSMakeRect(0,0,420,840)];
    view.wantsLayer=YES; view.layer.backgroundColor=NSColor.blackColor.CGColor;
    gDisplay=[AVSampleBufferDisplayLayer layer];
    gDisplay.videoGravity=AVLayerVideoGravityResizeAspect;
    [view.layer addSublayer:gDisplay]; gWindow.contentView=view;
    [view setNeedsLayout:YES]; [gWindow center]; fitWindow(CGSizeMake(420,840),NO); [gWindow makeKeyAndOrderFront:nil];
    [gWindow makeFirstResponder:view]; [NSApp activateIgnoringOtherApps:YES];
}
static void presentLatest(void){
    // A main-run-loop timer (also in event-tracking mode) consumes one latest slot.
    // The sink never queues main-thread blocks, even while AppKit is busy resizing.
    if(gDisplay.status==AVQueuedSampleBufferRenderingStatusFailed){
        fail(6,[NSString stringWithFormat:@"display layer failed: %@",gDisplay.error]); return;
    }
    if(!gDisplay.readyForMoreMediaData) return;
    pthread_mutex_lock(&gLock); CMSampleBufferRef sb=gLatest; gLatest=NULL; pthread_mutex_unlock(&gLock);
    if(!sb) return;
    CMSampleBufferRef copy=NULL;
    // Make an independent sample container around the retained decoded image.
    // CMSampleBuffer.h documents CreateCopy as shallow; constructing a new image
    // sample gives us private sample-attachment dictionaries even if the source
    // already has presentation keys. Pixel storage itself is never modified.
    CMSampleTimingInfo timing;
    OSStatus status=CMSampleBufferGetSampleTimingInfo(sb,0,&timing);
    if(!status) status=CMSampleBufferCreateReadyWithImageBuffer(kCFAllocatorDefault,
        CMSampleBufferGetImageBuffer(sb),CMSampleBufferGetFormatDescription(sb),&timing,&copy);
    if(!status){
        CMPropagateAttachments(sb,copy);
        CMSampleBufferSetOutputPresentationTimeStamp(copy,CMSampleBufferGetOutputPresentationTimeStamp(sb));
        CFArrayRef source=CMSampleBufferGetSampleAttachmentsArray(sb,false);
        CFArrayRef target=CMSampleBufferGetSampleAttachmentsArray(copy,true);
        if(source && target && CFArrayGetCount(source) && CFArrayGetCount(target)){
            NSDictionary *values=(__bridge NSDictionary*)CFArrayGetValueAtIndex(source,0);
            CFMutableDictionaryRef dest=(CFMutableDictionaryRef)CFArrayGetValueAtIndex(target,0);
            for(id key in values) CFDictionarySetValue(dest,(__bridge const void*)key,(__bridge const void*)values[key]);
        }
    }
    CFRelease(sb);
    if(status || !copy){ fail(6,[NSString stringWithFormat:@"sample copy failed: %d",(int)status]); return; }
    CMVideoFormatDescriptionRef format=CMSampleBufferGetFormatDescription(copy);
    CGSize size=CMVideoFormatDescriptionGetPresentationDimensions(format,YES,YES);
    if(size.width<=0 || size.height<=0){ CFRelease(copy); fail(6,@"invalid video dimensions"); return; }
    if(!CGSizeEqualToSize(gVideoSize,size)){
        gVideoSize=size;
        fitWindow(size,YES);
    }
    // M3 brief runtime evidence (13 Pro): presentation/raw=1184x2576,
    // physical screen=1170x2532, no clean aperture. Encoder alignment padding
    // implies ~1.2% horizontal / ~1.7% vertical coordinate bias. Its side is
    // unknown, so do not invent an offset/crop compensation.
    { static BOOL logged; if(!logged){ logged=YES;
        CMVideoDimensions raw=CMVideoFormatDescriptionGetDimensions(format);
        fprintf(stderr,"ipb-mirror: video presentation=%.0fx%.0f raw=%dx%d\n",
                size.width,size.height,raw.width,raw.height); } }
    // Only our new sample container's dictionaries are changed (never Apple's sb).
    CFArrayRef attachments=CMSampleBufferGetSampleAttachmentsArray(copy,true);
    for(CFIndex i=0;attachments && i<CFArrayGetCount(attachments);i++){
        CFMutableDictionaryRef d=(CFMutableDictionaryRef)CFArrayGetValueAtIndex(attachments,i);
        CFDictionarySetValue(d,kCMSampleAttachmentKey_DisplayImmediately,kCFBooleanTrue);
    }
    [gDisplay enqueueSampleBuffer:copy]; CFRelease(copy);
    pthread_mutex_lock(&gLock); gDisplayed++; pthread_mutex_unlock(&gLock);
}

static void usage(void){
    fprintf(stderr,"usage: ipb-mirror <coredevice-uuid> <utun> <hostIP> <deviceIP> [--service-id ID] [--seconds S]\n"
        "Defaults: touchscreen descriptor discovery, 300 seconds; maximum 3600 seconds / 8192 input events. CSV on stdout.\n");
}
static int runMirror(int argc,char **argv,dispatch_source_t watchdog){
    if(argc<5){ usage(); DIE(2,"missing arguments"); }
    const char *dev=argv[1],*utun=argv[2],*rxip=argv[3],*txip=argv[4];
    double runSeconds=300;
    for(int i=5;i<argc;i++){
        if(i+1==argc){ usage(); DIE(2,"incomplete option"); }
        const char *option=argv[i],*value=argv[++i]; char *end=NULL; errno=0;
        if(!strcmp(option,"--service-id")){
            gServiceID=strtoull(value,&end,0);
            if(errno || end==value || *end || !gServiceID || value[0]=='-') DIE(2,"invalid service id");
        }else if(!strcmp(option,"--seconds")){
            runSeconds=strtod(value,&end);
            if(errno || end==value || *end || !isfinite(runSeconds) || runSeconds<=0 || runSeconds>3600) DIE(2,"seconds must be >0 and <=3600");
        }else { usage(); DIE(2,"unknown option"); }
    }
    uuid_t deviceUUID; if(uuid_parse(dev,deviceUUID)) DIE(2,"invalid CoreDevice UUID");
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
    gMediaService=c; gMediaRemote=rc; gMediaFD=sfd;
    if(!rc) DIE(3,"media RemoteXPC create failed");
    xpc_remote_connection_set_event_handler(rc,^(xpc_object_t ev){
        if(ev && xpc_get_type(ev)==XPC_TYPE_ERROR){
            const char *desc=xpc_dictionary_get_string(ev,XPC_ERROR_KEY_DESCRIPTION);
            mediaError([NSString stringWithFormat:@"media RemoteXPC: %s",desc?desc:"unknown"]);
        }
    });
    xpc_remote_connection_activate(rc);

    int rtp=socket(AF_INET6,SOCK_DGRAM,0); gRTP=rtp; if(rtp<0) DIE(3,"socket: %s",strerror(errno));
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

    gInputQueue=dispatch_queue_create("ipb.mirror.input",DISPATCH_QUEUE_SERIAL);
    gInputGroup=dispatch_group_create();
    dispatch_group_async(gInputGroup,gInputQueue,^{
        if(openInput(dev,"com.apple.coredevice.feature.remote.universalhidservice",&gInput,&gInputFD)) return;
        if(!gServiceID) discoverService();
        if(atomic_load(&gFailure)) return;
        if(openInput(dev,"com.apple.coredevice.feature.remote.hid.button",&gButton,&gButtonFD)) return;
        if(atomic_load(&gFailure)) return;
        openInput(dev,"com.apple.coredevice.feature.remote.hid.digitizer",&gDigitizer,&gDigitizerFD);
    });
    double inputDeadline=nowSec()+15;
    while(dispatch_group_wait(gInputGroup,DISPATCH_TIME_NOW)!=0 && !atomic_load(&gFailure) && nowSec()<inputDeadline)
        pumpUntil(nowSec()+.005);
    if(dispatch_group_wait(gInputGroup,DISPATCH_TIME_NOW)) fail(9,@"input setup/discovery exceeded 15s");
    if(atomic_load(&gFailure)) return atomic_load(&gFailure);
    pthread_mutex_lock(&gLock); gCollect=YES; gLastFrame=nowSec(); pthread_mutex_unlock(&gLock);
    createWindow(); gReady=YES;
    // M4 brief: AX menu capture, Device Hub in Xcode 27 beta 6, iPhone 13 Pro.
    // hardwareGestureControls.actionButton / .sideButton use ConditionalKeyboardShortcut;
    // neither menu item appears with the 13 Pro. Revisit on corresponding hardware.
    LOGE("Shortcuts: ⇧⌘H=Home, ⌃⇧⌘H=App Switcher, ⌘↑=Volume+, ⌘↓=Volume−, ⇧⌘S=Screenshot, ⌘0=Zoom to Fit, ⌘1=Actual Size (key repeat ignored).");
    LOGE("Lock (⌘L) / Siri (⇧⌥⌘H): not implemented; usage-code evidence missing. Recording (⇧⌘R): not implemented; capture/recording behavior evidence missing. Action Button / Camera Control: usage-code evidence and corresponding local hardware missing.");
    armWatchdog(watchdog,runSeconds+10);
    double deadline=nowSec()+runSeconds;
    NSTimer *timer=[NSTimer timerWithTimeInterval:1.0/120 repeats:YES block:^(NSTimer *t){
        @try {
            if(atomic_load(&gFailure)) requestClose(@"connection/stream failure");
            if(nowSec()>=deadline) requestClose(@"run duration reached");
            if(gSubmitted>=Capacity-1) requestClose(@"8192-event oracle allocation limit reached");
            pthread_mutex_lock(&gLock); double last=gLastFrame; pthread_mutex_unlock(&gLock);
            if(nowSec()-last>12){ fail(7,@"no media frames for 12s"); requestClose(@"media stall"); }
            if(!gClosing) presentLatest();
            if(gClosing){
                [NSApp stop:nil];
                [NSApp postEvent:[NSEvent otherEventWithType:NSEventTypeApplicationDefined
                    location:NSZeroPoint modifierFlags:0 timestamp:0 windowNumber:0
                    context:nil subtype:0 data1:0 data2:0] atStart:YES];
            }
        } @catch(NSException *e){ fail(2,[NSString stringWithFormat:@"GUI exception: %@",e]); requestClose(@"GUI exception"); [NSApp stop:nil]; }
    }];
    [[NSRunLoop mainRunLoop] addTimer:timer forMode:NSRunLoopCommonModes];
    [NSApp run];
    [timer invalidate];
    requestClose(@"application stopped");
    return atomic_load(&gFailure);
}

static void shutdownMirror(void){
    // UP is already on the ordered input chain. Keep every private call bounded
    // by the independent shutdown watchdog, including stop/cancel.
    armWatchdog(gWatchdog,10);
    if(gInputGroup && dispatch_group_wait(gInputGroup,dispatch_time(DISPATCH_TIME_NOW,5*NSEC_PER_SEC)))
        fail(9,@"input drain exceeded 5s; device release is NOT guaranteed");
    pthread_mutex_lock(&gLock);
    gStopping=YES; gCollect=NO;
    if(gLatest){ CFRelease(gLatest); gLatest=NULL; }
    if(gScreenshotFrame){ CVPixelBufferRelease(gScreenshotFrame); gScreenshotFrame=NULL; }
    pthread_mutex_unlock(&gLock);
    if(gScreenshotGroup && dispatch_group_wait(gScreenshotGroup,dispatch_time(DISPATCH_TIME_NOW,5*NSEC_PER_SEC)))
        fail(8,@"screenshot save exceeded 5s during shutdown");
    [gStream stop];
    [gDisplay flushAndRemoveImage];
    if(gInputGroup && !dispatch_group_wait(gInputGroup,DISPATCH_TIME_NOW)){
        dispatch_group_async(gInputGroup,gInputQueue,^{
            pthread_mutex_lock(&gLock); gInputLive=NO; pthread_mutex_unlock(&gLock);
            if(gButton) xpc_remote_connection_cancel(gButton);
            if(gDigitizer) xpc_remote_connection_cancel(gDigitizer);
            if(gButtonFD>=0){ close(gButtonFD); gButtonFD=-1; }
            if(gDigitizerFD>=0){ close(gDigitizerFD); gDigitizerFD=-1; }
            if(gInput) xpc_remote_connection_cancel(gInput);
            if(gInputFD>=0){ close(gInputFD); gInputFD=-1; }
        });
        if(dispatch_group_wait(gInputGroup,dispatch_time(DISPATCH_TIME_NOW,2*NSEC_PER_SEC))) fail(9,@"input cancellation exceeded 2s");
    }
    if(gMediaRemote) xpc_remote_connection_cancel(gMediaRemote);
    if(gMediaService) xpc_connection_cancel(gMediaService);
    if(gMediaFD>=0) close(gMediaFD);
    if(gRTP>=0) close(gRTP);
}

int main(int argc,char **argv){ @autoreleasepool {
    gOutputFD=dup(STDOUT_FILENO);
    if(gOutputFD<0) return 8;
    signal(SIGPIPE,SIG_IGN);
    setenv("HIDCTL_QUIET","1",1); // existing glue: no per-event logging
    [NSApplication sharedApplication];
    [NSApp setActivationPolicy:NSApplicationActivationPolicyRegular];
    dispatch_queue_t watchdogQueue=dispatch_queue_create("ipb.mirror.watchdog",DISPATCH_QUEUE_SERIAL);
    dispatch_source_t watchdog=dispatch_source_create(DISPATCH_SOURCE_TYPE_TIMER,0,0,watchdogQueue);
    dispatch_source_set_event_handler(watchdog,^{
        if(atomic_exchange(&gWatchdogExpired,true))
            finish(9,@"watchdog shutdown grace expired; device release is NOT guaranteed");
        fail(9,@"watchdog expired during setup/collection/shutdown; device release is NOT guaranteed");
        armWatchdog(watchdog,5);
        dispatch_async(dispatch_get_main_queue(),^{ requestClose(@"watchdog expired"); });
    });
    gWatchdog=watchdog;
    armWatchdog(watchdog,45); dispatch_resume(watchdog);
    signal(SIGINT,SIG_IGN); signal(SIGTERM,SIG_IGN);
    dispatch_source_t interrupt=dispatch_source_create(DISPATCH_SOURCE_TYPE_SIGNAL,SIGINT,0,watchdogQueue);
    dispatch_source_t terminate=dispatch_source_create(DISPATCH_SOURCE_TYPE_SIGNAL,SIGTERM,0,watchdogQueue);
    dispatch_source_set_event_handler(interrupt,^{ fail(130,@"SIGINT"); dispatch_async(dispatch_get_main_queue(),^{ requestClose(@"SIGINT"); }); });
    dispatch_source_set_event_handler(terminate,^{ fail(143,@"SIGTERM"); dispatch_async(dispatch_get_main_queue(),^{ requestClose(@"SIGTERM"); }); });
    dispatch_resume(interrupt); dispatch_resume(terminate);
    @try {
        int result=runMirror(argc,argv,watchdog);
        requestClose(@"shutdown");
        shutdownMirror();
        finish(result,result?@"mirror failed":@"complete (host sender return is not device acknowledgement)");
    } @catch(NSException *exception) {
        fail(2,[NSString stringWithFormat:@"exception: %@",exception]);
        requestClose(@"exception"); shutdownMirror(); finish(2,@"exception");
    }
    return 9;
}}
