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
extern void _coredevice_xpc_add_bundle(NSBundle *bundle);
extern void _coredevice_xpc_init_services(void);
typedef void *xrc_t;
extern xrc_t xpc_remote_connection_create_with_connected_fd(int fd, dispatch_queue_t q, uint64_t flags, uint64_t mode);
extern void xpc_remote_connection_set_event_handler(xrc_t c, xpc_handler_t h);
extern void xpc_remote_connection_activate(xrc_t c);
extern xpc_object_t xpc_remote_connection_send_message_with_reply_sync(xrc_t c, xpc_object_t m);

@interface AVCMediaStreamNegotiator : NSObject
- (instancetype)initWithMode:(long)mode options:(NSDictionary*)o error:(NSError**)e;
- (BOOL)createOffer; - (NSData*)offer;
- (BOOL)setAnswer:(NSData*)a withError:(NSError**)e;
- (id)generateMediaStreamConfigurationWithError:(NSError**)e;
@end

static xpc_object_t action_env(const char *action, const char *dev, xpc_object_t input) {
    uuid_t u; uuid_generate(u); char us[37]; uuid_unparse_upper(u, us);
    xpc_object_t m = xpc_dictionary_create_empty();
    xpc_dictionary_set_string(m, "CoreDevice.actionIdentifier", action);
    xpc_dictionary_set_string(m, "CoreDevice.deviceIdentifier", dev);
    xpc_dictionary_set_string(m, "CoreDevice.invocationIdentifier", us);
    xpc_object_t ver = xpc_dictionary_create_empty(); xpc_object_t comps = xpc_array_create_empty();
    xpc_array_append_value(comps, xpc_uint64_create(642)); xpc_array_append_value(comps, xpc_uint64_create(15));
    xpc_dictionary_set_value(ver, "components", comps); xpc_dictionary_set_int64(ver, "originalComponentsCount", 2);
    xpc_dictionary_set_string(ver, "stringValue", "642.15");
    xpc_dictionary_set_value(m, "CoreDevice.coreDeviceVersion", ver);
    xpc_dictionary_set_int64(m, "CoreDevice.CoreDeviceDDIProtocolVersion", 1);
    xpc_dictionary_set_value(m, "CoreDevice.input", input);
    return m;
}
int main(int argc, char **argv) {
    const char *dev = argv[1];
    long mode = argc > 2 ? atol(argv[2]) : 1;
    const char *rxip = argc > 3 ? argv[3] : "fdZZ:ZZZZ:ZZZZ::2";
    const char *txip = argc > 4 ? argv[4] : "fdZZ:ZZZZ:ZZZZ::1";
    dlopen("/System/Library/PrivateFrameworks/AVConference.framework/AVConference", RTLD_NOW);
    _coredevice_xpc_add_bundle([NSBundle bundleWithPath:@"/Library/Developer/PrivateFrameworks/CoreDevice.framework"]);
    _coredevice_xpc_init_services();
    Class N = objc_getClass("AVCMediaStreamNegotiator");
    NSError *e = nil;
    id neg = [[N alloc] initWithMode:mode options:@{} error:&e];
    if (!neg) { printf("negotiator init failed: %s\n", e.description.UTF8String); return 1; }
    if (![neg createOffer]) { printf("createOffer failed\n"); return 1; }
    NSData *offer = [neg offer];
    printf("offer: %lu bytes\n", (unsigned long)offer.length);

    // open the display service socket
    dispatch_queue_t q = dispatch_queue_create("probe", 0);
    xpc_connection_t c = xpc_connection_create("com.apple.CoreDevice.CoreDeviceService", q);
    xpc_connection_set_event_handler(c, ^(xpc_object_t x){});
    xpc_connection_resume(c);
    xpc_object_t input0 = xpc_dictionary_create_empty();
    xpc_dictionary_set_string(input0, "featureIdentifier", "com.apple.coredevice.feature.startmediastream");
    xpc_object_t req = action_env("com.apple.coredevice.action.createservicesocket", dev, input0);
    xpc_object_t rep = xpc_connection_send_message_with_reply_sync(c, req);
    xpc_object_t out = xpc_dictionary_get_dictionary(rep, "CoreDevice.output");
    if (!out) { char*d=xpc_copy_description(rep); printf("no socket: %s\n", d); return 1; }
    int fd = xpc_dictionary_dup_fd(out, "fileDescriptor");
    uint64_t flags = xpc_dictionary_get_uint64(out, "remoteXPCVersionFlags");
    xrc_t rc = xpc_remote_connection_create_with_connected_fd(fd, dispatch_queue_create("rc",0), flags, 0);
    xpc_remote_connection_set_event_handler(rc, ^(xpc_object_t ev){ char*d=xpc_copy_description(ev); fprintf(stderr,"event: %.200s\n", d); free(d); });
    xpc_remote_connection_activate(rc);

    // build start input
    xpc_object_t in = xpc_dictionary_create_empty();
    // bind a real UDP receiver on the host tunnel address
    int rtp = socket(AF_INET6, SOCK_DGRAM, 0);
    struct sockaddr_in6 la; memset(&la,0,sizeof la); la.sin6_len=sizeof la; la.sin6_family=AF_INET6; la.sin6_port=0;
    inet_pton(AF_INET6, rxip, &la.sin6_addr);
    unsigned scope = if_nametoindex(getenv("HDB_UTUN") ?: "utun9"); la.sin6_scope_id = scope;
    int br = bind(rtp, (struct sockaddr*)&la, sizeof la);
    socklen_t sl = sizeof la; getsockname(rtp, (struct sockaddr*)&la, &sl);
    uint16_t rxport = ntohs(la.sin6_port);
    printf("host RTP socket bound rc=%d on [%s%%%u]:%u\n", br, rxip, scope, rxport);
    uint16_t txport = argc>5 ? atoi(argv[5]) : 51000;
    xpc_dictionary_set_string(in, "receiverIP", rxip);
    xpc_dictionary_set_uint64(in, "receiverPort", rxport);
    xpc_dictionary_set_string(in, "senderIP", txip);
    xpc_dictionary_set_uint64(in, "senderPort", txport);
    xpc_dictionary_set_uint64(in, "timeout", 30);
    xpc_dictionary_set_string(in, "type", "video");
    xpc_dictionary_set_string(in, "direction", "output");
    xpc_dictionary_set_data(in, "negotiatorOffer", offer.bytes, offer.length);
    xpc_dictionary_set_uint64(in, "clientSupportedFeatures", 972);
    xpc_dictionary_set_value(in, "options", xpc_dictionary_create_empty());
    xpc_object_t sreq = action_env("com.apple.coredevice.action.mediastreamstart", dev, in);
    xpc_object_t srep = xpc_remote_connection_send_message_with_reply_sync(rc, sreq);
    char *sd = srep ? xpc_copy_description(srep) : strdup("<null>");
    // trim
    NSString *s = [NSString stringWithUTF8String:sd]; free(sd);
    s = [[s componentsSeparatedByCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]] componentsJoinedByString:@" "];
    printf("start reply: %.900s\n", s.UTF8String);
    // poll for inbound RTP for 3s
    struct timeval tv={3,0}; setsockopt(rtp,SOL_SOCKET,SO_RCVTIMEO,&tv,sizeof tv);
    uint8_t pkt[2048]; struct sockaddr_in6 from; socklen_t fl=sizeof from;
    ssize_t n = recvfrom(rtp, pkt, sizeof pkt, 0, (struct sockaddr*)&from, &fl);
    if (n>0){ char fb[64]; inet_ntop(AF_INET6,&from.sin6_addr,fb,sizeof fb); printf("RTP packet: %zd bytes from [%s]:%u  first: %02x %02x %02x %02x\n", n, fb, ntohs(from.sin6_port), pkt[0],pkt[1],pkt[2],pkt[3]); }
    else printf("no RTP packet within 3s (n=%zd)\n", n);
    xpc_object_t so = xpc_dictionary_get_dictionary(srep, "CoreDevice.output");
    if (so) {
        size_t alen = 0; const void *ans = xpc_dictionary_get_data(so, "negotiatorAnswer", &alen);
        if (!ans) ans = xpc_dictionary_get_data(so, "answer", &alen);
        printf("answer present: %s (%zu bytes)\n", ans ? "YES" : "no", alen);
        if (ans) {
            NSError *ae = nil; BOOL ok = [neg setAnswer:[NSData dataWithBytes:ans length:alen] withError:&ae];
            printf("setAnswer=%d err=%s\n", ok, ae?ae.description.UTF8String:"nil");
            id cfg = [neg generateMediaStreamConfigurationWithError:&ae];
            printf("config=%p err=%s\n", cfg, ae?[ae.description substringToIndex:MIN(140,ae.description.length)].UTF8String:"nil");
            if (cfg) { printf("config: %.600s\n", [[cfg performSelector:@selector(dictionary)] description].UTF8String); }
        }
    }
    return 0;
}
