// Send an arbitrary CoreDeviceService action with an arbitrary input dictionary, and print the
// reply. Schema discovery tool: the service decodes CoreDevice.input as a Swift Codable and names
// the key it wanted ("Expected to find key reason."), so the schema can be walked out one key at a
// time. Used to work out TunnelAssertionRequest for TODO(tunnel-keepalive).
//
//   cd_action <device-uuid> <action-identifier> [key=value | key:i=123 | key:b=1 | key:d={...}]...
//
// build: clang -fobjc-arc -o build/cd_action Experiments/tools/cd_action.m \
//           -F/Library/Developer/PrivateFrameworks -framework Foundation -framework CoreDevice \
//           -Xlinker -undefined -Xlinker dynamic_lookup
#import <Foundation/Foundation.h>
#include <xpc/xpc.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <uuid/uuid.h>
#include <dispatch/dispatch.h>

// CoreDeviceService refuses a connection from a process that has not registered the bundle first;
// without this the reply is "Connection invalid". Same two calls Sources/action_sender.m makes.
extern void _coredevice_xpc_add_bundle(NSBundle *bundle);
extern void _coredevice_xpc_init_services(void);

int main(int argc, const char *argv[]) {
    if (argc < 3) {
        fprintf(stderr, "usage: %s <device-uuid> <action> [key=value | key:i=int | key:b=bool]...\n", argv[0]);
        return 2;
    }
    const char *device = argv[1], *action = argv[2];

    NSBundle *bundle = [NSBundle bundleWithPath:@"/Library/Developer/PrivateFrameworks/CoreDevice.framework"];
    if (!bundle) { fprintf(stderr, "no CoreDevice bundle\n"); return 2; }
    _coredevice_xpc_add_bundle(bundle);
    _coredevice_xpc_init_services();

    xpc_object_t input = xpc_dictionary_create_empty();
    for (int i = 3; i < argc; i++) {
        char *entry = strdup(argv[i]);
        char *eq = strchr(entry, '=');
        if (!eq) { fprintf(stderr, "bad pair: %s\n", entry); free(entry); return 2; }
        *eq = 0;
        const char *value = eq + 1;
        char *colon = strchr(entry, ':');
        char type = (colon && colon[1]) ? colon[1] : 's';
        if (colon) *colon = 0;

        // "parent.child" writes into a nested dictionary, created on first use.
        xpc_object_t target = input;
        char *dot = strchr(entry, '.');
        const char *leaf = entry;
        if (dot) {
            *dot = 0; leaf = dot + 1;
            xpc_object_t parent = xpc_dictionary_get_dictionary(input, entry);
            if (!parent) { parent = xpc_dictionary_create_empty();
                           xpc_dictionary_set_value(input, entry, parent); }
            target = parent;
        }

        if (type == 'i') xpc_dictionary_set_int64(target, leaf, strtoll(value, NULL, 0));
        else if (type == 'b') xpc_dictionary_set_bool(target, leaf, atoi(value) != 0);
        else if (type == 'e') xpc_dictionary_set_value(target, leaf, xpc_dictionary_create_empty());
        else if (type == 'o') {   // array of one dictionary: "field=value"
            xpc_object_t arr = xpc_array_create_empty();
            xpc_object_t obj = xpc_dictionary_create_empty();
            char *copy = strdup(value), *sep = strchr(copy, '=');
            if (sep) { *sep = 0; xpc_dictionary_set_string(obj, copy, sep + 1); }
            free(copy);
            xpc_array_append_value(arr, obj);
            xpc_dictionary_set_value(target, leaf, arr);
        }
        else if (type == 'a') {   // comma-separated array of strings
            xpc_object_t arr = xpc_array_create_empty();
            char *copy = strdup(value), *tok = strtok(copy, ",");
            while (tok) { xpc_array_append_value(arr, xpc_string_create(tok)); tok = strtok(NULL, ","); }
            free(copy);
            xpc_dictionary_set_value(target, leaf, arr);
        }
        else xpc_dictionary_set_string(target, leaf, value);
        free(entry);
    }

    dispatch_queue_t queue = dispatch_queue_create("cd-action", DISPATCH_QUEUE_SERIAL);
    xpc_connection_t conn = xpc_connection_create("com.apple.CoreDevice.CoreDeviceService", queue);
    xpc_connection_set_event_handler(conn, ^(xpc_object_t e) { (void)e; });
    xpc_connection_resume(conn);

    uuid_t invocation; uuid_generate(invocation);
    char invocation_string[37]; uuid_unparse_upper(invocation, invocation_string);

    xpc_object_t msg = xpc_dictionary_create_empty();
    xpc_dictionary_set_string(msg, "CoreDevice.actionIdentifier", action);
    xpc_dictionary_set_string(msg, "CoreDevice.deviceIdentifier", device);
    xpc_object_t version = xpc_dictionary_create_empty();
    xpc_object_t components = xpc_array_create_empty();
    xpc_array_append_value(components, xpc_uint64_create(636));
    xpc_array_append_value(components, xpc_uint64_create(3));
    xpc_dictionary_set_value(version, "components", components);
    xpc_dictionary_set_int64(version, "originalComponentsCount", 2);
    xpc_dictionary_set_string(version, "stringValue", "636.3");
    xpc_dictionary_set_value(msg, "CoreDevice.coreDeviceVersion", version);
    xpc_dictionary_set_int64(msg, "CoreDevice.CoreDeviceDDIProtocolVersion", 1);
    xpc_dictionary_set_string(msg, "CoreDevice.invocationIdentifier", invocation_string);
    xpc_dictionary_set_value(msg, "CoreDevice.input", input);

    xpc_object_t reply = xpc_connection_send_message_with_reply_sync(conn, msg);
    char *d = xpc_copy_description(reply);
    printf("reply: %s\n", d ? d : "<null>");
    free(d);

    // Hold the connection open if asked, so an acquired assertion stays held.
    const char *hold = getenv("CD_ACTION_HOLD_S");
    if (hold) { fprintf(stderr, "holding connection for %s s\n", hold); sleep((unsigned)atoi(hold)); }
    return 0;
}
