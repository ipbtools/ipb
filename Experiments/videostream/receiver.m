// Standalone media receiver — stage 1: transport + negotiation (fail-hard, unbuffered).
// Follows CoreDeviceMediaStreamSupport's own chain. All ObjC/C, no Swift shims.
#import <Foundation/Foundation.h>
#import <objc/runtime.h>
#include <xpc/xpc.h>
#include <uuid/uuid.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <net/if.h>
#include <string.h>
#include <dlfcn.h>
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
- (instancetype)initWithMode:(long)mode options:(NSDictionary*)o error:(NSError**)e;
- (BOOL)createOffer; - (NSData*)offer;
- (BOOL)setAnswer:(NSData*)a withError:(NSError**)e;
- (id)generateMediaStreamConfigurationWithError:(NSError**)e;
- (id)generateMediaStreamInitOptionsWithError:(NSError**)e;
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
    long mode=1;

    if(!dlopen("/Library/Developer/PrivateFrameworks/CoreDevice.framework/Versions/A/CoreDevice",RTLD_NOW)) DIE("CoreDevice dlopen: %s",dlerror());
    if(!dlopen("/System/Library/PrivateFrameworks/AVConference.framework/Versions/A/AVConference",RTLD_NOW)) DIE("AVConference dlopen: %s",dlerror());
    LOG("frameworks loaded");
    _coredevice_xpc_add_bundle([NSBundle bundleWithPath:@"/Library/Developer/PrivateFrameworks/CoreDevice.framework"]);
    _coredevice_xpc_init_services();
    LOG("coredevice services inited");

    Class N=objc_getClass("AVCMediaStreamNegotiator"); if(!N) DIE("no AVCMediaStreamNegotiator");
    NSError*e=nil; id neg=[[N alloc] initWithMode:mode options:@{} error:&e];
    if(!neg) DIE("negotiator init: %s",e.description.UTF8String);
    if(![neg createOffer]) DIE("createOffer failed");
    NSData*offer=[neg offer]; if(!offer.length) DIE("empty offer");
    LOG("offer: %lu bytes",(unsigned long)offer.length);

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
    xpc_dictionary_set_value(in,"options",xpc_dictionary_create_empty());
    xpc_object_t srep=xpc_remote_connection_send_message_with_reply_sync(rc,action_env("com.apple.coredevice.action.mediastreamstart",dev,in));
    if(!srep){ LOG("mediastreamstart: null reply"); return 2; }
    char*sd=xpc_copy_description(srep);
    LOG("start reply: %.700s",sd); free(sd);
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
    struct timeval tv={4,0}; setsockopt(rtp,SOL_SOCKET,SO_RCVTIMEO,&tv,sizeof tv);
    uint8_t pkt[2048]; struct sockaddr_in6 from; socklen_t fl=sizeof from;
    ssize_t n=recvfrom(rtp,pkt,sizeof pkt,0,(struct sockaddr*)&from,&fl);
    if(n>0){ char fb[64]; inet_ntop(AF_INET6,&from.sin6_addr,fb,sizeof fb);
        LOG("*** RTP RECEIVED: %zd bytes from [%s]:%u  hdr: %02x %02x %02x %02x",n,fb,ntohs(from.sin6_port),pkt[0],pkt[1],pkt[2],pkt[3]); }
    else LOG("no RTP within 4s (n=%zd errno=%s)",n,strerror(errno));

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
    LOG("stage1 done");
    return 0;
}
