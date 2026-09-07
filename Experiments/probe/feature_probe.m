// feature_probe: ask CoreDeviceService to create a service socket for a feature and report the reply.
// usage: feature_probe <device-id> <coredevice-version e.g. 518.31> <feature> [feature...]
#import <Foundation/Foundation.h>
#include <xpc/xpc.h>
#include <uuid/uuid.h>
extern void _coredevice_xpc_add_bundle(NSBundle *bundle);
extern void _coredevice_xpc_init_services(void);
typedef void *xpc_remote_connection_t;
extern xpc_remote_connection_t xpc_remote_connection_create_with_connected_fd(int fd, dispatch_queue_t q, uint64_t flags, uint64_t mode);
extern void xpc_remote_connection_set_event_handler(xpc_remote_connection_t c, xpc_handler_t h);
extern void xpc_remote_connection_activate(xpc_remote_connection_t c);
extern xpc_object_t xpc_remote_connection_send_message_with_reply_sync(xpc_remote_connection_t c, xpc_object_t m);
extern void xpc_remote_connection_cancel(xpc_remote_connection_t c);
static xpc_object_t xpc_from_json(id obj) {
    if ([obj isKindOfClass:[NSDictionary class]]) { xpc_object_t d = xpc_dictionary_create_empty(); for (NSString *k in obj) { xpc_object_t v = xpc_from_json(obj[k]); xpc_dictionary_set_value(d, k.UTF8String, v); } return d; }
    if ([obj isKindOfClass:[NSArray class]]) { xpc_object_t a = xpc_array_create_empty(); for (id e in obj) xpc_array_append_value(a, xpc_from_json(e)); return a; }
    if ([obj isKindOfClass:[NSString class]]) { NSString *str = obj; if ([str hasPrefix:@"u64:"]) return xpc_uint64_create((uint64_t)[[str substringFromIndex:4] longLongValue]); if ([str hasPrefix:@"i64:"]) return xpc_int64_create([[str substringFromIndex:4] longLongValue]); if ([str hasPrefix:@"hex:"]) { NSMutableData *dd=[NSMutableData data]; NSString *h=[str substringFromIndex:4]; for (NSUInteger i=0;i+1<h.length;i+=2){unsigned v=0; [[NSScanner scannerWithString:[h substringWithRange:NSMakeRange(i,2)]] scanHexInt:&v]; uint8_t b=v; [dd appendBytes:&b length:1];} return xpc_data_create(dd.bytes, dd.length);} return xpc_string_create(str.UTF8String); }
    if ([obj isKindOfClass:[NSNumber class]]) { NSNumber *n = obj; if (strcmp(n.objCType, @encode(BOOL)) == 0 || strcmp(n.objCType, "c") == 0) return xpc_bool_create(n.boolValue); if (strchr("fd", n.objCType[0])) return xpc_double_create(n.doubleValue); return xpc_int64_create(n.longLongValue); }
    return xpc_null_create();
}

int main(int argc, const char *argv[]) {
    if (argc < 4) { fprintf(stderr, "usage: %s <device> <version> <feature>...\n", argv[0]); return 2; }
    const char *device = argv[1];
    const char *version_str = argv[2];
    unsigned long major = 0, minor = 0;
    sscanf(version_str, "%lu.%lu", &major, &minor);
    _coredevice_xpc_add_bundle([NSBundle bundleWithPath:@"/Library/Developer/PrivateFrameworks/CoreDevice.framework"]);
    _coredevice_xpc_init_services();
    dispatch_queue_t q = dispatch_queue_create("probe", DISPATCH_QUEUE_SERIAL);
    xpc_connection_t conn = xpc_connection_create("com.apple.CoreDevice.CoreDeviceService", q);
    xpc_connection_set_event_handler(conn, ^(xpc_object_t e) {
        char *d = xpc_copy_description(e); fprintf(stderr, "event: %s\n", d); free(d);
    });
    xpc_connection_resume(conn);
    for (int i = 3; i < argc; i++) {
        const char *feature = argv[i];
        uuid_t inv; uuid_generate(inv); char invs[37]; uuid_unparse_upper(inv, invs);
        xpc_object_t input = xpc_dictionary_create_empty();
        if (!getenv("PROBE_NO_FEATURE")) xpc_dictionary_set_string(input, "featureIdentifier", feature);
        xpc_object_t msg = xpc_dictionary_create_empty();
        const char *action = getenv("PROBE_ACTION") ? getenv("PROBE_ACTION") : "com.apple.coredevice.action.createservicesocket";
        xpc_dictionary_set_string(msg, "CoreDevice.actionIdentifier", action);
        xpc_dictionary_set_string(msg, "CoreDevice.deviceIdentifier", device);
        xpc_object_t version = xpc_dictionary_create_empty();
        xpc_object_t comps = xpc_array_create_empty();
        xpc_array_append_value(comps, xpc_uint64_create(major));
        xpc_array_append_value(comps, xpc_uint64_create(minor));
        xpc_dictionary_set_value(version, "components", comps);
        xpc_dictionary_set_int64(version, "originalComponentsCount", 2);
        xpc_dictionary_set_string(version, "stringValue", version_str);
        xpc_dictionary_set_value(msg, "CoreDevice.coreDeviceVersion", version);
        xpc_dictionary_set_int64(msg, "CoreDevice.CoreDeviceDDIProtocolVersion", 1);
        xpc_dictionary_set_string(msg, "CoreDevice.invocationIdentifier", invs);
        xpc_dictionary_set_value(msg, "CoreDevice.input", input);
        xpc_object_t reply = xpc_connection_send_message_with_reply_sync(conn, msg);
        xpc_object_t output = xpc_dictionary_get_dictionary(reply, "CoreDevice.output");
        if (output) {
            int fd = xpc_dictionary_dup_fd(output, "fileDescriptor");
            uint64_t flags = xpc_dictionary_get_uint64(output, "remoteXPCVersionFlags");
            char *od = xpc_copy_description(output);
            printf("%-64s OK fd=%d remoteXPCVersionFlags=0x%llx\n%s\n", feature, fd, flags, od); free(od);
            const char *js = getenv("PROBE_SEND_JSON");
            if (fd >= 0 && js) {
                dispatch_queue_t rq = dispatch_queue_create("probe-remote", DISPATCH_QUEUE_SERIAL);
                xpc_remote_connection_t rc = xpc_remote_connection_create_with_connected_fd(fd, rq, flags, 0);
                xpc_remote_connection_set_event_handler(rc, ^(xpc_object_t e) { char *ed = xpc_copy_description(e); fprintf(stderr, "remote event: %s\n", ed); free(ed); });
                xpc_remote_connection_activate(rc);
                NSError *err = nil; id obj = [NSJSONSerialization JSONObjectWithData:[NSData dataWithBytes:js length:strlen(js)] options:0 error:&err];
                if (!obj) { fprintf(stderr, "bad PROBE_SEND_JSON: %s\n", err.description.UTF8String); exit(2); }
                xpc_object_t msg = xpc_from_json(obj);
                char *md = xpc_copy_description(msg); printf(">>> send: %s\n", md); free(md);
                xpc_object_t rep = xpc_remote_connection_send_message_with_reply_sync(rc, msg);
                char *rd = rep ? xpc_copy_description(rep) : strdup("<null>"); printf("<<< reply: %s\n", rd); free(rd);
                usleep(300000);
                xpc_remote_connection_cancel(rc);
            } else if (fd >= 0) close(fd);
        } else {
            xpc_object_t err = xpc_dictionary_get_value(reply, "CoreDevice.error");
            if (err && xpc_get_type(err) == XPC_TYPE_DICTIONARY) {
                int64_t code = xpc_dictionary_get_int64(err, "code");
                const char *domain = xpc_dictionary_get_string(err, "domain");
                size_t len = 0; const void *bytes = xpc_dictionary_get_data(err, "userInfoWithNSSecureCoding", &len);
                NSString *info = @"";
                if (bytes && len) {
                    NSError *e = nil;
                    id obj = [NSKeyedUnarchiver unarchivedObjectOfClasses:[NSSet setWithObjects:[NSDictionary class],[NSString class],[NSNumber class],[NSArray class],[NSError class],[NSURL class],[NSDate class], nil] fromData:[NSData dataWithBytes:bytes length:len] error:&e];
                    info = obj ? [[[obj description] stringByReplacingOccurrencesOfString:@"\n" withString:@" "] stringByReplacingOccurrencesOfString:@"    " withString:@" "] : [e description];
                }
                printf("%-64s FAIL domain=%s code=%lld info=%s\n", feature, domain ? domain : "?", (long long)code, [info UTF8String]);
            } else {
                char *d = xpc_copy_description(reply);
                printf("%-64s FAIL raw=%s\n", feature, d); free(d);
            }
        }
    }
    return 0;
}
