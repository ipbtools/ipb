#import <Foundation/Foundation.h>
#import <xpc/xpc.h>
#include <uuid/uuid.h>
#include <execinfo.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

typedef struct OS_xpc_remote_connection *xpc_remote_connection_t;
static bool g_quiet = false;
static bool g_sync_remote = false;

static void crash_handler(int signo) {
    void *frames[64];
    int count = backtrace(frames, 64);
    fprintf(stderr, "caught signal %d\n", signo);
    backtrace_symbols_fd(frames, count, STDERR_FILENO);
    _exit(128 + signo);
}

extern void _coredevice_xpc_add_bundle(NSBundle *bundle);
extern void _coredevice_xpc_init_services(void);
extern xpc_remote_connection_t xpc_remote_connection_create_with_connected_fd(int fd, dispatch_queue_t target_queue, uint64_t version_flags, uint64_t connection_mode);
extern void xpc_remote_connection_set_event_handler(xpc_remote_connection_t connection, xpc_handler_t handler);
extern void xpc_remote_connection_activate(xpc_remote_connection_t connection);
extern void xpc_remote_connection_cancel(xpc_remote_connection_t connection);
extern void xpc_remote_connection_send_message(xpc_remote_connection_t connection, xpc_object_t message);
extern void xpc_remote_connection_send_message_with_reply(xpc_remote_connection_t connection, xpc_object_t message, dispatch_queue_t reply_queue, xpc_handler_t handler);
extern xpc_object_t xpc_remote_connection_send_message_with_reply_sync(xpc_remote_connection_t connection, xpc_object_t message);
extern int mercury_send_xpc_message(xpc_remote_connection_t connection, xpc_object_t message) __attribute__((weak_import));
extern int mercury_send_xpc_message_sync(xpc_remote_connection_t connection, xpc_object_t message) __attribute__((weak_import));
extern int mercury_send_uhid_request_value(xpc_remote_connection_t connection, const uint8_t *bytes, int length, uint64_t service_id) __attribute__((weak_import));
extern int coredevice_send_universalhid_hid_report(xpc_remote_connection_t connection, const void *report_words, uint64_t service_id) __attribute__((weak_import));
extern int coredevice_reset_universalhid_gesture(xpc_remote_connection_t connection, uint64_t service_id) __attribute__((weak_import));
extern int coredevice_send_universalhid_barrier(xpc_remote_connection_t connection) __attribute__((weak_import));
extern int coredevice_send_hid_button_custom(xpc_remote_connection_t connection, uint64_t usage_page, uint64_t usage_code, uint8_t state) __attribute__((weak_import));
extern int coredevice_send_hid_button_barrier(xpc_remote_connection_t connection) __attribute__((weak_import));
extern int coredevice_send_hid_digitizer_cgpoint(xpc_remote_connection_t connection, double point_one_x, double point_one_y, double point_two_x, double point_two_y, uint64_t point_two_optional_tag, uint64_t event_type, uint64_t edge, uint64_t target_low, uint64_t target_high) __attribute__((weak_import));
extern int coredevice_print_connected_services(xpc_remote_connection_t connection) __attribute__((weak_import));
extern int coredevice_print_connected_descriptors_async_raw(xpc_remote_connection_t connection) __attribute__((weak_import));
extern int coredevice_print_hid_service_ids(void) __attribute__((weak_import));
extern int uhid_make_digitizer_report(double x, double y, int touching, int in_range, uint8_t *output, int output_capacity) __attribute__((weak_import));
extern int uhid_make_digitizer_hid_report(double x, double y, int touching, int in_range, void *output) __attribute__((weak_import));
extern int uhid_make_digitizer_swipe_hid_report(double x, double y, int touching, int in_range, int swipe_pending, int swipe_locked, int swipe_up, void *output) __attribute__((weak_import));
extern int uhid_make_navigation_swipe_hid_report(uint32_t phase, uint32_t swipe_mask, uint32_t gesture_motion, uint32_t flavor, double progress, double x, double y, void *output) __attribute__((weak_import));
extern int uhid_make_dock_swipe_hid_report(uint32_t phase, uint32_t swipe_mask, uint32_t gesture_motion, uint32_t flavor, double progress, double x, double y, void *output) __attribute__((weak_import));
extern int uhid_make_keyboard_hid_report(uint32_t usage, int pressed, void *output) __attribute__((weak_import));

static void print_xpc(const char *label, xpc_object_t object) {
    if (g_quiet) {
        return;
    }
    if (!object) {
        printf("%s: <null>\n", label);
        return;
    }
    char *desc = xpc_copy_description(object);
    printf("%s: %s\n", label, desc ? desc : "<no description>");
    free(desc);
}

static void set_uuid_string(xpc_object_t dict, const char *key, const char *uuid_string) {
    uuid_t uuid;
    if (uuid_parse(uuid_string, uuid) != 0) {
        fprintf(stderr, "Invalid UUID for %s: %s\n", key, uuid_string);
        exit(2);
    }
    xpc_dictionary_set_uuid(dict, key, uuid);
}

static void add_coredevice_registration(void) {
    NSBundle *coreDeviceBundle = [NSBundle bundleWithPath:@"/Library/Developer/PrivateFrameworks/CoreDevice.framework"];
    if (!coreDeviceBundle) {
        fprintf(stderr, "Unable to create CoreDevice bundle object\n");
        exit(2);
    }
    _coredevice_xpc_add_bundle(coreDeviceBundle);
    _coredevice_xpc_init_services();
}

static xpc_object_t point2(double x, double y) {
    xpc_object_t point = xpc_dictionary_create_empty();
    xpc_dictionary_set_double(point, "x", x);
    xpc_dictionary_set_double(point, "y", y);
    return point;
}

static xpc_object_t point3(double x, double y, double z) {
    xpc_object_t point = point2(x, y);
    xpc_dictionary_set_double(point, "z", z);
    return point;
}

static xpc_object_t hid_event(const char *feature, const char *message_type, xpc_object_t payload, bool barrier) {
    xpc_object_t event = xpc_dictionary_create_empty();
    xpc_dictionary_set_string(event, "featureIdentifier", feature);
    xpc_dictionary_set_string(event, "messageType", message_type);
    xpc_dictionary_set_bool(event, "isBarrier", barrier);
    if (payload) {
        xpc_dictionary_set_value(event, "payload", payload);
    }
    return event;
}

static xpc_object_t mercury_wrapper(const char *mangled_type_name, xpc_object_t value) {
    xpc_object_t wrapper = xpc_dictionary_create_empty();
    xpc_dictionary_set_string(wrapper, "mangledTypeName", mangled_type_name);
    if (value) {
        xpc_dictionary_set_value(wrapper, "value", value);
    }
    return wrapper;
}

static xpc_object_t uhid_request_connected_services(void) {
    xpc_object_t request = xpc_dictionary_create_empty();
    xpc_object_t payload = xpc_dictionary_create_empty();
    xpc_dictionary_set_value(request, "connectedServices", payload);
    xpc_release(payload);

    xpc_object_t wrapper = mercury_wrapper("$s19CoreDeviceUtilities29DDIUniversalHIDServicePayloadO7RequestO", request);
    xpc_release(request);
    return wrapper;
}

static xpc_object_t uhid_request_connected_services_flat(void) {
    xpc_object_t request = xpc_dictionary_create_empty();
    xpc_dictionary_set_bool(request, "connectedServices", true);

    xpc_object_t wrapper = mercury_wrapper("$s19CoreDeviceUtilities29DDIUniversalHIDServicePayloadO7RequestO", request);
    xpc_release(request);
    return wrapper;
}

static xpc_object_t hid_service_id(uint64_t service_id) {
    xpc_object_t dict = xpc_dictionary_create_empty();
    xpc_dictionary_set_uint64(dict, "id", service_id);
    return dict;
}

static xpc_object_t hid_usage_pair(uint64_t page, uint64_t code) {
    xpc_object_t dict = xpc_dictionary_create_empty();
    xpc_dictionary_set_uint64(dict, "page", page);
    xpc_dictionary_set_uint64(dict, "code", code);
    return dict;
}

static xpc_object_t uhid_touchscreen_descriptor(uint64_t service_id, bool wrap_storage) {
    xpc_object_t fields = xpc_dictionary_create_empty();
    xpc_object_t sid = hid_service_id(service_id);
    xpc_object_t usages = xpc_array_create_empty();
    xpc_object_t touchscreen = hid_usage_pair(0x0d, 0x04);

    xpc_array_append_value(usages, touchscreen);
    xpc_dictionary_set_value(fields, "serviceID", sid);
    xpc_dictionary_set_int64(fields, "vendorID", 0x05ac);
    xpc_dictionary_set_int64(fields, "productID", 1);
    xpc_dictionary_set_string(fields, "product", "Codex Touchscreen");
    xpc_dictionary_set_value(fields, "usages", usages);
    xpc_dictionary_set_bool(fields, "authenticatedDevice", true);
    xpc_dictionary_set_bool(fields, "builtIn", true);
    xpc_dictionary_set_string(fields, "displayIdentifier", "1");

    xpc_release(touchscreen);
    xpc_release(usages);
    xpc_release(sid);

    if (!wrap_storage) {
        return fields;
    }

    xpc_object_t descriptor = xpc_dictionary_create_empty();
    xpc_dictionary_set_value(descriptor, "storage", fields);
    xpc_release(fields);
    return descriptor;
}

static xpc_object_t uhid_request_create_touchscreen(uint64_t service_id, bool positional, bool wrap_storage) {
    xpc_object_t request = xpc_dictionary_create_empty();
    xpc_object_t descriptor = uhid_touchscreen_descriptor(service_id, wrap_storage);
    if (positional) {
        xpc_object_t payload = xpc_dictionary_create_empty();
        xpc_dictionary_set_value(payload, "_0", descriptor);
        xpc_dictionary_set_value(request, "createService", payload);
        xpc_release(payload);
    } else {
        xpc_dictionary_set_value(request, "createService", descriptor);
    }
    xpc_release(descriptor);

    xpc_object_t wrapper = mercury_wrapper("$s19CoreDeviceUtilities29DDIUniversalHIDServicePayloadO7RequestO", request);
    xpc_release(request);
    return wrapper;
}

static xpc_object_t uhid_request_reset_gesture(uint64_t service_id) {
    xpc_object_t request = xpc_dictionary_create_empty();
    xpc_object_t payload = xpc_dictionary_create_empty();
    xpc_object_t sid = hid_service_id(service_id);
    xpc_dictionary_set_value(payload, "serviceID", sid);
    xpc_dictionary_set_value(request, "resetGestureState", payload);
    xpc_release(sid);
    xpc_release(payload);

    xpc_object_t wrapper = mercury_wrapper("$s19CoreDeviceUtilities29DDIUniversalHIDServicePayloadO7RequestO", request);
    xpc_release(request);
    return wrapper;
}

static xpc_object_t uhid_request_send_report(const void *bytes, size_t length, uint64_t service_id) {
    xpc_object_t request = xpc_dictionary_create_empty();
    xpc_object_t payload = xpc_dictionary_create_empty();
    xpc_object_t sid = hid_service_id(service_id);
    xpc_dictionary_set_data(payload, "report", bytes, length);
    xpc_dictionary_set_value(payload, "serviceID", sid);
    xpc_dictionary_set_value(request, "send", payload);
    xpc_release(sid);
    xpc_release(payload);

    xpc_object_t wrapper = mercury_wrapper("$s19CoreDeviceUtilities29DDIUniversalHIDServicePayloadO7RequestO", request);
    xpc_release(request);
    return wrapper;
}

static xpc_object_t uhid_request_send_report_positional(const void *bytes, size_t length, uint64_t service_id) {
    xpc_object_t request = xpc_dictionary_create_empty();
    xpc_object_t payload = xpc_dictionary_create_empty();
    xpc_object_t sid = hid_service_id(service_id);
    xpc_dictionary_set_data(payload, "_0", bytes, length);
    xpc_dictionary_set_value(payload, "_1", sid);
    xpc_dictionary_set_value(request, "send", payload);
    xpc_release(sid);
    xpc_release(payload);

    xpc_object_t wrapper = mercury_wrapper("$s19CoreDeviceUtilities29DDIUniversalHIDServicePayloadO7RequestO", request);
    xpc_release(request);
    return wrapper;
}

static xpc_object_t uhid_request_digitizer_report(double x, double y, bool touching, bool in_range, uint64_t service_id) {
    if (!uhid_make_digitizer_report) {
        fprintf(stderr, "UniversalHID report generator is not linked\n");
        exit(2);
    }
    uint8_t bytes[128];
    int count = uhid_make_digitizer_report(x, y, touching ? 1 : 0, in_range ? 1 : 0, bytes, (int)sizeof(bytes));
    if (count <= 0 || count > (int)sizeof(bytes)) {
        fprintf(stderr, "Unable to build UniversalHID digitizer report, result=%d\n", count);
        exit(2);
    }
    return uhid_request_send_report(bytes, (size_t)count, service_id);
}

static xpc_object_t uhid_request_digitizer_report_positional(double x, double y, bool touching, bool in_range, uint64_t service_id) {
    if (!uhid_make_digitizer_report) {
        fprintf(stderr, "UniversalHID report generator is not linked\n");
        exit(2);
    }
    uint8_t bytes[128];
    int count = uhid_make_digitizer_report(x, y, touching ? 1 : 0, in_range ? 1 : 0, bytes, (int)sizeof(bytes));
    if (count <= 0 || count > (int)sizeof(bytes)) {
        fprintf(stderr, "Unable to build UniversalHID digitizer report, result=%d\n", count);
        exit(2);
    }
    return uhid_request_send_report_positional(bytes, (size_t)count, service_id);
}

static xpc_object_t digitizer_payload(double x, double y, uint64_t event_type) {
    xpc_object_t payload = xpc_dictionary_create_empty();
    xpc_object_t p1 = point2(x, y);
    xpc_dictionary_set_value(payload, "pointOne", p1);
    xpc_dictionary_set_uint64(payload, "eventType", event_type);
    xpc_dictionary_set_uint64(payload, "edge", 0);
    xpc_dictionary_set_uint64(payload, "target", 0);
    xpc_release(p1);
    return payload;
}

static xpc_object_t button_payload(uint64_t usage_page, uint64_t usage_code, uint64_t state) {
    xpc_object_t payload = xpc_dictionary_create_empty();
    xpc_dictionary_set_uint64(payload, "usagePage", usage_page);
    xpc_dictionary_set_uint64(payload, "usageCode", usage_code);
    xpc_dictionary_set_uint64(payload, "state", state);
    return payload;
}

static xpc_object_t scroll_payload(double x, double y, double z, uint64_t phase, uint64_t momentum, uint64_t target) {
    xpc_object_t payload = xpc_dictionary_create_empty();
    xpc_object_t p = point3(x, y, z);
    xpc_dictionary_set_value(payload, "point", p);
    xpc_dictionary_set_uint64(payload, "phase", phase);
    xpc_dictionary_set_uint64(payload, "momentum", momentum);
    xpc_dictionary_set_uint64(payload, "target", target);
    xpc_release(p);
    return payload;
}

static xpc_object_t make_remote_message(const char *feature, int argc, const char *argv[]) {
    const char *kind = argc > 5 ? argv[5] : "probe";
    if (strcmp(kind, "mw_digitizer") == 0) {
        double x = argc > 6 ? strtod(argv[6], NULL) : 200.0;
        double y = argc > 7 ? strtod(argv[7], NULL) : 400.0;
        uint64_t event_type = argc > 8 ? strtoull(argv[8], NULL, 0) : 0;
        xpc_object_t payload = digitizer_payload(x, y, event_type);
        xpc_object_t wrapper = mercury_wrapper("$s19CoreDeviceUtilities20IndigoDigitizerEventV", payload);
        xpc_release(payload);
        return wrapper;
    }
    if (strcmp(kind, "mw_hidxpc_digitizer") == 0) {
        double x = argc > 6 ? strtod(argv[6], NULL) : 200.0;
        double y = argc > 7 ? strtod(argv[7], NULL) : 400.0;
        uint64_t event_type = argc > 8 ? strtoull(argv[8], NULL, 0) : 0;
        xpc_object_t payload = digitizer_payload(x, y, event_type);
        xpc_object_t event = hid_event(feature, "IndigoDigitizerEvent", payload, false);
        xpc_release(payload);
        xpc_object_t wrapper = mercury_wrapper("$s19CoreDeviceUtilities18HIDXPCServiceEventO", event);
        xpc_release(event);
        return wrapper;
    }
    if (strcmp(kind, "uhid_connected") == 0) {
        return uhid_request_connected_services();
    }
    if (strcmp(kind, "uhid_connected_flat") == 0) {
        return uhid_request_connected_services_flat();
    }
    if (strcmp(kind, "uhid_create_flat") == 0) {
        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 0xff0001;
        return uhid_request_create_touchscreen(service_id, false, false);
    }
    if (strcmp(kind, "uhid_create_pos") == 0) {
        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 0xff0001;
        return uhid_request_create_touchscreen(service_id, true, false);
    }
    if (strcmp(kind, "uhid_create_storage") == 0) {
        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 0xff0001;
        return uhid_request_create_touchscreen(service_id, false, true);
    }
    if (strcmp(kind, "uhid_create_pos_storage") == 0) {
        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 0xff0001;
        return uhid_request_create_touchscreen(service_id, true, true);
    }
    if (strcmp(kind, "uhid_reset") == 0) {
        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 0;
        return uhid_request_reset_gesture(service_id);
    }
    if (strcmp(kind, "uhid_report") == 0) {
        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 1;
        double x = argc > 7 ? strtod(argv[7], NULL) : 0.5;
        double y = argc > 8 ? strtod(argv[8], NULL) : 0.5;
        bool touching = argc > 9 ? strtol(argv[9], NULL, 0) != 0 : true;
        bool in_range = argc > 10 ? strtol(argv[10], NULL, 0) != 0 : touching;
        return uhid_request_digitizer_report(x, y, touching, in_range, service_id);
    }
    if (strcmp(kind, "uhid_report_pos") == 0) {
        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 1;
        double x = argc > 7 ? strtod(argv[7], NULL) : 0.5;
        double y = argc > 8 ? strtod(argv[8], NULL) : 0.5;
        bool touching = argc > 9 ? strtol(argv[9], NULL, 0) != 0 : true;
        bool in_range = argc > 10 ? strtol(argv[10], NULL, 0) != 0 : touching;
        return uhid_request_digitizer_report_positional(x, y, touching, in_range, service_id);
    }
    if (strcmp(kind, "digitizer") == 0) {
        double x = argc > 6 ? strtod(argv[6], NULL) : 200.0;
        double y = argc > 7 ? strtod(argv[7], NULL) : 400.0;
        uint64_t event_type = argc > 8 ? strtoull(argv[8], NULL, 0) : 0;
        xpc_object_t payload = digitizer_payload(x, y, event_type);
        xpc_object_t event = hid_event(feature, "IndigoDigitizerEvent", payload, false);
        xpc_release(payload);
        return event;
    }
    if (strcmp(kind, "button") == 0) {
        uint64_t usage_page = argc > 6 ? strtoull(argv[6], NULL, 0) : 0;
        uint64_t usage_code = argc > 7 ? strtoull(argv[7], NULL, 0) : 0;
        uint64_t state = argc > 8 ? strtoull(argv[8], NULL, 0) : 0;
        xpc_object_t payload = button_payload(usage_page, usage_code, state);
        xpc_object_t event = hid_event(feature, "IndigoButtonEvent", payload, false);
        xpc_release(payload);
        return event;
    }
    if (strcmp(kind, "scroll") == 0) {
        double x = argc > 6 ? strtod(argv[6], NULL) : 0.0;
        double y = argc > 7 ? strtod(argv[7], NULL) : -200.0;
        double z = argc > 8 ? strtod(argv[8], NULL) : 0.0;
        uint64_t phase = argc > 9 ? strtoull(argv[9], NULL, 0) : 2;
        uint64_t momentum = argc > 10 ? strtoull(argv[10], NULL, 0) : 0;
        uint64_t target = argc > 11 ? strtoull(argv[11], NULL, 0) : 0;
        xpc_object_t payload = scroll_payload(x, y, z, phase, momentum, target);
        xpc_object_t event = hid_event(feature, "IndigoScrollEvent", payload, false);
        xpc_release(payload);
        return event;
    }
    if (strcmp(kind, "barrier") == 0) {
        const char *message_type = argc > 6 ? argv[6] : "";
        return hid_event(feature, message_type, NULL, true);
    }

    xpc_object_t remote_msg = xpc_dictionary_create_empty();
    xpc_dictionary_set_string(remote_msg, "probe", kind);
    return remote_msg;
}

static void send_remote_message(xpc_remote_connection_t remote, xpc_object_t message, useconds_t delay_after) {
    print_xpc("remote request", message);
    if (getenv("HIDCTL_MERCURY_SYNC") && mercury_send_xpc_message_sync) {
        int result = mercury_send_xpc_message_sync(remote, message);
        if (!g_quiet) {
            printf("mercury sync result=%d\n", result);
        }
        if (delay_after) {
            usleep(delay_after);
        }
        return;
    }
    if (getenv("HIDCTL_MERCURY") && mercury_send_xpc_message) {
        int result = mercury_send_xpc_message(remote, message);
        if (!g_quiet) {
            printf("mercury send result=%d\n", result);
        }
        if (delay_after) {
            usleep(delay_after);
        }
        return;
    }
    if (g_sync_remote) {
        dispatch_semaphore_t sema = dispatch_semaphore_create(0);
        __block xpc_object_t block_reply = NULL;
        dispatch_queue_t reply_queue = dispatch_queue_create("action-sender-remote-reply", DISPATCH_QUEUE_SERIAL);
        xpc_remote_connection_send_message_with_reply(remote, message, reply_queue, ^(xpc_object_t reply) {
            if (reply) {
                block_reply = xpc_retain(reply);
            }
            dispatch_semaphore_signal(sema);
        });
        long waited = dispatch_semaphore_wait(sema, dispatch_time(DISPATCH_TIME_NOW, 3LL * NSEC_PER_SEC));
        if (waited == 0) {
            print_xpc("remote reply", block_reply);
            if (block_reply) xpc_release(block_reply);
        } else {
            printf("remote reply: <timeout>\n");
        }
        dispatch_release(reply_queue);
        dispatch_release(sema);
    } else {
        xpc_remote_connection_send_message(remote, message);
    }
    if (delay_after) {
        usleep(delay_after);
    }
}

static void send_hid_barrier(xpc_remote_connection_t remote, const char *feature, const char *message_type, useconds_t delay_after);

static void send_tap(xpc_remote_connection_t remote, const char *feature, double x, double y) {
    xpc_object_t down_payload = digitizer_payload(x, y, 0);
    xpc_object_t down = hid_event(feature, "IndigoDigitizerEvent", down_payload, false);
    xpc_release(down_payload);
    send_remote_message(remote, down, 80000);
    xpc_release(down);

    xpc_object_t up_payload = digitizer_payload(x, y, 2);
    xpc_object_t up = hid_event(feature, "IndigoDigitizerEvent", up_payload, false);
    xpc_release(up_payload);
    send_remote_message(remote, up, 300000);
    xpc_release(up);
    send_hid_barrier(remote, feature, "IndigoDigitizerEvent", 100000);
}

static void send_digitizer_event(xpc_remote_connection_t remote, const char *feature, double x, double y, uint64_t event_type, useconds_t delay_after) {
    xpc_object_t payload = digitizer_payload(x, y, event_type);
    xpc_object_t event = hid_event(feature, "IndigoDigitizerEvent", payload, false);
    xpc_release(payload);
    send_remote_message(remote, event, delay_after);
    xpc_release(event);
}

static void send_hid_barrier(xpc_remote_connection_t remote, const char *feature, const char *message_type, useconds_t delay_after) {
    xpc_object_t barrier = hid_event(feature, message_type, NULL, true);
    send_remote_message(remote, barrier, delay_after);
    xpc_release(barrier);
}

static void send_long_press(xpc_remote_connection_t remote, const char *feature, double x, double y, useconds_t duration) {
    send_digitizer_event(remote, feature, x, y, 0, duration);
    send_digitizer_event(remote, feature, x, y, 2, 300000);
    send_hid_barrier(remote, feature, "IndigoDigitizerEvent", 100000);
}

static void send_swipe(xpc_remote_connection_t remote, const char *feature, double x1, double y1, double x2, double y2, useconds_t duration, useconds_t hold_after_move) {
    const int steps = 10;
    useconds_t step_delay = duration / steps;
    send_digitizer_event(remote, feature, x1, y1, 0, step_delay);
    for (int i = 1; i <= steps; i++) {
        double t = (double)i / (double)steps;
        double x = x1 + (x2 - x1) * t;
        double y = y1 + (y2 - y1) * t;
        send_digitizer_event(remote, feature, x, y, 1, i == steps ? hold_after_move : step_delay);
    }
    send_digitizer_event(remote, feature, x2, y2, 2, 300000);
    send_hid_barrier(remote, feature, "IndigoDigitizerEvent", 100000);
}

static xpc_object_t mercury_digitizer_message(double x, double y, uint64_t event_type) {
    xpc_object_t payload = digitizer_payload(x, y, event_type);
    xpc_object_t wrapper = mercury_wrapper("$s19CoreDeviceUtilities20IndigoDigitizerEventV", payload);
    xpc_release(payload);
    return wrapper;
}

static void send_mercury_tap(xpc_remote_connection_t remote, double x, double y) {
    xpc_object_t down = mercury_digitizer_message(x, y, 0);
    send_remote_message(remote, down, 80000);
    xpc_release(down);

    xpc_object_t up = mercury_digitizer_message(x, y, 2);
    send_remote_message(remote, up, 300000);
    xpc_release(up);
}

static void send_uhid_report(xpc_remote_connection_t remote, uint64_t service_id, double x, double y, bool touching, bool in_range, useconds_t delay_after) {
    xpc_object_t report = uhid_request_digitizer_report(x, y, touching, in_range, service_id);
    send_remote_message(remote, report, delay_after);
    xpc_release(report);
}

static void send_uhid_report_positional(xpc_remote_connection_t remote, uint64_t service_id, double x, double y, bool touching, bool in_range, useconds_t delay_after) {
    xpc_object_t report = uhid_request_digitizer_report_positional(x, y, touching, in_range, service_id);
    send_remote_message(remote, report, delay_after);
    xpc_release(report);
}

static void send_uhid_report_typed(xpc_remote_connection_t remote, uint64_t service_id, double x, double y, bool touching, bool in_range, useconds_t delay_after) {
    if (!uhid_make_digitizer_report || !mercury_send_uhid_request_value) {
        fprintf(stderr, "Typed UniversalHID sender is not linked\n");
        exit(2);
    }
    uint8_t bytes[128];
    int count = uhid_make_digitizer_report(x, y, touching ? 1 : 0, in_range ? 1 : 0, bytes, (int)sizeof(bytes));
    if (count <= 0 || count > (int)sizeof(bytes)) {
        fprintf(stderr, "Unable to build UniversalHID digitizer report, result=%d\n", count);
        exit(2);
    }
    int result = mercury_send_uhid_request_value(remote, bytes, count, service_id);
    if (!g_quiet) {
        printf("mercury typed result=%d\n", result);
    }
    if (delay_after) {
        usleep(delay_after);
    }
}

static void send_coredevice_hid_report(xpc_remote_connection_t remote, uint64_t service_id, double x, double y, bool touching, bool in_range, useconds_t delay_after) {
    if (!uhid_make_digitizer_hid_report || !coredevice_send_universalhid_hid_report) {
        fprintf(stderr, "CoreDevice UniversalHID sender is not linked\n");
        exit(2);
    }
    uint64_t report_words[2] = {0, 0};
    int count = uhid_make_digitizer_hid_report(x, y, touching ? 1 : 0, in_range ? 1 : 0, report_words);
    if (count != (int)sizeof(report_words)) {
        fprintf(stderr, "Unable to build UniversalHID HIDReport, result=%d\n", count);
        exit(2);
    }
    int result = coredevice_send_universalhid_hid_report(remote, report_words, service_id);
    if (!g_quiet) {
        printf("coredevice hid result=%d\n", result);
    }
    if (delay_after) {
        usleep(delay_after);
    }
}

static void send_coredevice_hid_swipe_report(xpc_remote_connection_t remote, uint64_t service_id, double x, double y, bool touching, bool in_range, bool swipe_pending, bool swipe_locked, bool swipe_up, useconds_t delay_after) {
    if (!uhid_make_digitizer_swipe_hid_report || !coredevice_send_universalhid_hid_report) {
        fprintf(stderr, "CoreDevice UniversalHID swipe contact sender is not linked\n");
        exit(2);
    }
    uint64_t report_words[2] = {0, 0};
    int count = uhid_make_digitizer_swipe_hid_report(
        x,
        y,
        touching ? 1 : 0,
        in_range ? 1 : 0,
        swipe_pending ? 1 : 0,
        swipe_locked ? 1 : 0,
        swipe_up ? 1 : 0,
        report_words
    );
    if (count != (int)sizeof(report_words)) {
        fprintf(stderr, "Unable to build UniversalHID digitizer swipe HIDReport, result=%d\n", count);
        exit(2);
    }
    int result = coredevice_send_universalhid_hid_report(remote, report_words, service_id);
    if (!g_quiet) {
        printf("coredevice hid swipe-contact result=%d x=%g y=%g touch=%d range=%d pending=%d locked=%d up=%d\n",
               result, x, y, touching, in_range, swipe_pending, swipe_locked, swipe_up);
    }
    if (delay_after) {
        usleep(delay_after);
    }
}

static void send_coredevice_hid_barrier(xpc_remote_connection_t remote, useconds_t delay_after);

static void send_coredevice_keyboard_report(xpc_remote_connection_t remote, uint64_t service_id, uint32_t usage, bool pressed, useconds_t delay_after) {
    if (!uhid_make_keyboard_hid_report || !coredevice_send_universalhid_hid_report) {
        fprintf(stderr, "CoreDevice keyboard sender is not linked\n");
        exit(2);
    }
    uint64_t report_words[2] = {0, 0};
    int count = uhid_make_keyboard_hid_report(usage, pressed ? 1 : 0, report_words);
    if (count != (int)sizeof(report_words)) {
        fprintf(stderr, "Unable to build UniversalHID keyboard HIDReport, result=%d usage=0x%x\n", count, usage);
        exit(2);
    }
    int result = coredevice_send_universalhid_hid_report(remote, report_words, service_id);
    if (!g_quiet) {
        printf("coredevice keyboard result=%d service=0x%llx usage=0x%x pressed=%d\n",
               result,
               (unsigned long long)service_id,
               usage,
               pressed);
    }
    if (delay_after) {
        usleep(delay_after);
    }
}

static void send_coredevice_keyboard_key(xpc_remote_connection_t remote, uint64_t service_id, uint32_t usage, useconds_t hold) {
    send_coredevice_keyboard_report(remote, service_id, usage, true, hold);
    send_coredevice_keyboard_report(remote, service_id, usage, false, 120000);
    send_coredevice_hid_barrier(remote, 100000);
}

static void send_coredevice_hid_reset_gesture(xpc_remote_connection_t remote, uint64_t service_id, useconds_t delay_after) {
    if (!coredevice_reset_universalhid_gesture) {
        fprintf(stderr, "CoreDevice UniversalHID reset sender is not linked\n");
        exit(2);
    }
    int result = coredevice_reset_universalhid_gesture(remote, service_id);
    if (!g_quiet) {
        printf("coredevice hid reset result=%d service=0x%llx\n", result, (unsigned long long)service_id);
    }
    if (delay_after) {
        usleep(delay_after);
    }
}

static void send_coredevice_navigation_swipe_report(xpc_remote_connection_t remote, uint64_t service_id, uint32_t phase, uint32_t swipe_mask, uint32_t gesture_motion, uint32_t flavor, double progress, double x, double y, useconds_t delay_after) {
    if (!uhid_make_navigation_swipe_hid_report || !coredevice_send_universalhid_hid_report) {
        fprintf(stderr, "CoreDevice navigation swipe sender is not linked\n");
        exit(2);
    }
    uint64_t report_words[2] = {0, 0};
    int count = uhid_make_navigation_swipe_hid_report(phase, swipe_mask, gesture_motion, flavor, progress, x, y, report_words);
    if (count != (int)sizeof(report_words)) {
        fprintf(stderr, "Unable to build UniversalHID navigation swipe HIDReport, result=%d\n", count);
        exit(2);
    }
    int result = coredevice_send_universalhid_hid_report(remote, report_words, service_id);
    if (!g_quiet) {
        printf("coredevice nav result=%d phase=0x%x mask=0x%x motion=0x%x flavor=0x%x progress=%g x=%g y=%g\n",
               result, phase, swipe_mask, gesture_motion, flavor, progress, x, y);
    }
    if (delay_after) {
        usleep(delay_after);
    }
}

static void send_coredevice_dock_swipe_report(xpc_remote_connection_t remote, uint64_t service_id, uint32_t phase, uint32_t swipe_mask, uint32_t gesture_motion, uint32_t flavor, double progress, double x, double y, useconds_t delay_after) {
    if (!uhid_make_dock_swipe_hid_report || !coredevice_send_universalhid_hid_report) {
        fprintf(stderr, "CoreDevice dock swipe sender is not linked\n");
        exit(2);
    }
    uint64_t report_words[2] = {0, 0};
    int count = uhid_make_dock_swipe_hid_report(phase, swipe_mask, gesture_motion, flavor, progress, x, y, report_words);
    if (count != (int)sizeof(report_words)) {
        fprintf(stderr, "Unable to build UniversalHID dock swipe HIDReport, result=%d\n", count);
        exit(2);
    }
    int result = coredevice_send_universalhid_hid_report(remote, report_words, service_id);
    if (!g_quiet) {
        printf("coredevice dock result=%d phase=0x%x mask=0x%x motion=0x%x flavor=0x%x progress=%g x=%g y=%g\n",
               result, phase, swipe_mask, gesture_motion, flavor, progress, x, y);
    }
    if (delay_after) {
        usleep(delay_after);
    }
}

static void send_coredevice_navigation_recents(xpc_remote_connection_t remote, uint64_t service_id, uint32_t swipe_mask, uint32_t flavor) {
    const uint32_t began = 0x01;
    const uint32_t changed = 0x02;
    const uint32_t ended = 0x04;
    const uint32_t from_bottom_edge = 0x0d;
    send_coredevice_navigation_swipe_report(remote, service_id, began, swipe_mask, from_bottom_edge, flavor, 0.0, 0.5, 0.99, 120000);
    send_coredevice_navigation_swipe_report(remote, service_id, changed, swipe_mask, from_bottom_edge, flavor, 0.35, 0.5, 0.82, 220000);
    send_coredevice_navigation_swipe_report(remote, service_id, changed, swipe_mask, from_bottom_edge, flavor, 0.62, 0.5, 0.72, 650000);
    send_coredevice_navigation_swipe_report(remote, service_id, ended, swipe_mask, from_bottom_edge, flavor, 1.0, 0.5, 0.72, 250000);
    send_coredevice_hid_barrier(remote, 100000);
}

static void send_coredevice_dock_recents(xpc_remote_connection_t remote, uint64_t service_id, uint32_t swipe_mask, uint32_t flavor) {
    const uint32_t began = 0x01;
    const uint32_t changed = 0x02;
    const uint32_t ended = 0x04;
    const uint32_t from_bottom_edge = 0x0d;
    send_coredevice_dock_swipe_report(remote, service_id, began, swipe_mask, from_bottom_edge, flavor, 0.0, 0.5, 0.99, 120000);
    send_coredevice_dock_swipe_report(remote, service_id, changed, swipe_mask, from_bottom_edge, flavor, 0.30, 0.5, 0.88, 180000);
    send_coredevice_dock_swipe_report(remote, service_id, changed, swipe_mask, from_bottom_edge, flavor, 0.60, 0.5, 0.74, 650000);
    send_coredevice_dock_swipe_report(remote, service_id, ended, swipe_mask, from_bottom_edge, flavor, 1.0, 0.5, 0.74, 250000);
    send_coredevice_hid_barrier(remote, 100000);
}

static void send_coredevice_hid_tap(xpc_remote_connection_t remote, uint64_t service_id, double x, double y) {
    send_coredevice_hid_report(remote, service_id, x, y, true, true, 80000);
    send_coredevice_hid_report(remote, service_id, x, y, false, false, 250000);
    if (coredevice_send_universalhid_barrier) {
        int result = coredevice_send_universalhid_barrier(remote);
        if (!g_quiet) {
            printf("coredevice hid barrier result=%d\n", result);
        }
        usleep(100000);
    }
}

static void send_coredevice_hid_barrier(xpc_remote_connection_t remote, useconds_t delay_after) {
    if (coredevice_send_universalhid_barrier) {
        int result = coredevice_send_universalhid_barrier(remote);
        if (!g_quiet) {
            printf("coredevice hid barrier result=%d\n", result);
        }
    }
    if (delay_after) {
        usleep(delay_after);
    }
}

static void send_coredevice_button_event(xpc_remote_connection_t remote, uint64_t usage_page, uint64_t usage_code, uint8_t state, useconds_t delay_after) {
    if (!coredevice_send_hid_button_custom) {
        fprintf(stderr, "CoreDevice HIDButton sender is not linked\n");
        exit(2);
    }
    int result = coredevice_send_hid_button_custom(remote, usage_page, usage_code, state);
    if (!g_quiet) {
        printf("coredevice button result=%d page=0x%llx code=0x%llx state=%u\n",
               result,
               (unsigned long long)usage_page,
               (unsigned long long)usage_code,
               state);
    }
    if (delay_after) {
        usleep(delay_after);
    }
}

static void send_coredevice_button_barrier(xpc_remote_connection_t remote, useconds_t delay_after) {
    if (coredevice_send_hid_button_barrier) {
        int result = coredevice_send_hid_button_barrier(remote);
        if (!g_quiet) {
            printf("coredevice button barrier result=%d\n", result);
        }
    }
    if (delay_after) {
        usleep(delay_after);
    }
}

static void send_coredevice_button_click(xpc_remote_connection_t remote, uint64_t usage_page, uint64_t usage_code, useconds_t hold) {
    send_coredevice_button_event(remote, usage_page, usage_code, 0, hold);
    send_coredevice_button_event(remote, usage_page, usage_code, 1, 120000);
    send_coredevice_button_barrier(remote, 100000);
}

static void send_coredevice_button_double_click(xpc_remote_connection_t remote, uint64_t usage_page, uint64_t usage_code) {
    send_coredevice_button_click(remote, usage_page, usage_code, 70000);
    usleep(80000);
    send_coredevice_button_click(remote, usage_page, usage_code, 70000);
}

static void send_coredevice_digitizer_cgpoint(xpc_remote_connection_t remote, double x1, double y1, double x2, double y2, uint64_t point_two_optional_tag, uint64_t event_type, uint64_t edge, uint64_t target_low, uint64_t target_high, useconds_t delay_after) {
    if (!coredevice_send_hid_digitizer_cgpoint) {
        fprintf(stderr, "CoreDevice HIDDigitizer sender is not linked\n");
        exit(2);
    }
    int result = coredevice_send_hid_digitizer_cgpoint(remote, x1, y1, x2, y2, point_two_optional_tag, event_type, edge, target_low, target_high);
    if (!g_quiet) {
        printf("coredevice digitizer result=%d p1=(%g,%g) p2=(%g,%g) p2tag=%llu event=0x%llx edge=0x%llx target=(0x%llx,0x%llx)\n",
               result,
               x1,
               y1,
               x2,
               y2,
               (unsigned long long)point_two_optional_tag,
               (unsigned long long)event_type,
               (unsigned long long)edge,
               (unsigned long long)target_low,
               (unsigned long long)target_high);
    }
    if (delay_after) {
        usleep(delay_after);
    }
}

static void send_coredevice_digitizer_tap(xpc_remote_connection_t remote, double x, double y, uint64_t target_low, uint64_t target_high) {
    const uint64_t optional_none = 1;
    const uint64_t event_start = 0;
    const uint64_t event_end = 2;
    const uint64_t edge_none = 0;
    send_coredevice_digitizer_cgpoint(remote, x, y, 0, 0, optional_none, event_start, edge_none, target_low, target_high, 90000);
    send_coredevice_digitizer_cgpoint(remote, x, y, 0, 0, optional_none, event_end, edge_none, target_low, target_high, 250000);
}

static void send_coredevice_digitizer_long_press(xpc_remote_connection_t remote, double x, double y, uint64_t target_low, uint64_t target_high, useconds_t duration) {
    const uint64_t optional_none = 1;
    const uint64_t event_start = 0;
    const uint64_t event_position = 1;
    const uint64_t event_end = 2;
    const uint64_t edge_none = 0;
    const useconds_t pulse_delay = 80000;
    int pulses = (int)(duration / pulse_delay);
    if (pulses < 1) {
        pulses = 1;
    }
    send_coredevice_digitizer_cgpoint(remote, x, y, 0, 0, optional_none, event_start, edge_none, target_low, target_high, pulse_delay);
    for (int i = 0; i < pulses; i++) {
        send_coredevice_digitizer_cgpoint(remote, x, y, 0, 0, optional_none, event_position, edge_none, target_low, target_high, pulse_delay);
    }
    send_coredevice_digitizer_cgpoint(remote, x, y, 0, 0, optional_none, event_end, edge_none, target_low, target_high, 350000);
}

static void send_coredevice_digitizer_swipe(xpc_remote_connection_t remote, double x1, double y1, double x2, double y2, uint64_t edge, uint64_t target_low, uint64_t target_high, useconds_t duration, useconds_t hold_after_move) {
    const uint64_t optional_none = 1;
    const uint64_t event_start = 0;
    const uint64_t event_position = 1;
    const uint64_t event_end = 2;
    const int steps = 12;
    useconds_t step_delay = duration / steps;
    send_coredevice_digitizer_cgpoint(remote, x1, y1, 0, 0, optional_none, event_start, edge, target_low, target_high, step_delay);
    for (int i = 1; i <= steps; i++) {
        double t = (double)i / (double)steps;
        double x = x1 + (x2 - x1) * t;
        double y = y1 + (y2 - y1) * t;
        send_coredevice_digitizer_cgpoint(remote, x, y, 0, 0, optional_none, event_position, edge, target_low, target_high, i == steps ? hold_after_move : step_delay);
    }
    send_coredevice_digitizer_cgpoint(remote, x2, y2, 0, 0, optional_none, event_end, edge, target_low, target_high, 250000);
}

static void send_coredevice_hid_long_press(xpc_remote_connection_t remote, uint64_t service_id, double x, double y, useconds_t duration) {
    send_coredevice_hid_report(remote, service_id, x, y, true, true, duration);
    send_coredevice_hid_report(remote, service_id, x, y, false, false, 250000);
    send_coredevice_hid_barrier(remote, 100000);
}

static void send_coredevice_hid_swipe(xpc_remote_connection_t remote, uint64_t service_id, double x1, double y1, double x2, double y2, useconds_t duration, useconds_t hold_after_move) {
    const int steps = 12;
    useconds_t step_delay = duration / steps;
    send_coredevice_hid_report(remote, service_id, x1, y1, true, true, step_delay);
    for (int i = 1; i <= steps; i++) {
        double t = (double)i / (double)steps;
        double x = x1 + (x2 - x1) * t;
        double y = y1 + (y2 - y1) * t;
        send_coredevice_hid_report(remote, service_id, x, y, true, true, i == steps ? hold_after_move : step_delay);
    }
    send_coredevice_hid_report(remote, service_id, x2, y2, false, false, 250000);
    send_coredevice_hid_barrier(remote, 100000);
}

static void send_coredevice_hid_edge_swipe_up(xpc_remote_connection_t remote, uint64_t service_id, double x1, double y1, double x2, double y2, useconds_t duration, useconds_t hold_after_move) {
    const int steps = 12;
    useconds_t step_delay = duration / steps;
    send_coredevice_hid_swipe_report(remote, service_id, x1, y1, true, true, true, false, true, step_delay);
    for (int i = 1; i <= steps; i++) {
        double t = (double)i / (double)steps;
        double x = x1 + (x2 - x1) * t;
        double y = y1 + (y2 - y1) * t;
        send_coredevice_hid_swipe_report(remote, service_id, x, y, true, true, false, true, true, i == steps ? hold_after_move : step_delay);
    }
    send_coredevice_hid_swipe_report(remote, service_id, x2, y2, false, false, false, false, false, 250000);
    send_coredevice_hid_barrier(remote, 100000);
}

static void send_uhid_tap(xpc_remote_connection_t remote, uint64_t service_id, double x, double y) {
    send_uhid_report(remote, service_id, x, y, true, true, 80000);
    send_uhid_report(remote, service_id, x, y, false, false, 250000);
}

static void send_uhid_tap_positional(xpc_remote_connection_t remote, uint64_t service_id, double x, double y) {
    send_uhid_report_positional(remote, service_id, x, y, true, true, 80000);
    send_uhid_report_positional(remote, service_id, x, y, false, false, 250000);
}

static void send_uhid_tap_typed(xpc_remote_connection_t remote, uint64_t service_id, double x, double y) {
    send_uhid_report_typed(remote, service_id, x, y, true, true, 80000);
    send_uhid_report_typed(remote, service_id, x, y, false, false, 250000);
}

static void send_uhid_create_touchscreen(xpc_remote_connection_t remote, uint64_t service_id, bool positional, bool wrap_storage) {
    xpc_object_t create = uhid_request_create_touchscreen(service_id, positional, wrap_storage);
    send_remote_message(remote, create, 300000);
    xpc_release(create);
}

static void send_uhid_create_tap(xpc_remote_connection_t remote, uint64_t service_id, double x, double y, bool positional, bool wrap_storage) {
    send_uhid_create_touchscreen(remote, service_id, positional, wrap_storage);
    send_uhid_tap_positional(remote, service_id, x, y);
}

int main(int argc, const char *argv[]) {
    setbuf(stdout, NULL);
    if (!getenv("HIDCTL_NO_CRASH_HANDLER")) {
        signal(SIGSEGV, crash_handler);
        signal(SIGBUS, crash_handler);
        signal(SIGILL, crash_handler);
    }
    setbuf(stderr, NULL);
    g_quiet = getenv("HIDCTL_QUIET") != NULL;
    g_sync_remote = getenv("HIDCTL_SYNC") != NULL;
    const char *device = argc > 1 ? argv[1] : "<device-uuid>";
    const char *action = argc > 2 ? argv[2] : "com.apple.coredevice.action.createservicesocket";
    const char *feature = argc > 3 ? argv[3] : "com.apple.coredevice.feature.remote.universalhidservice";
    uint64_t connection_mode = argc > 4 ? strtoull(argv[4], NULL, 0) : 0;

    @autoreleasepool {
        add_coredevice_registration();

        const char *early_kind = argc > 5 ? argv[5] : NULL;
        if (early_kind && strcmp(early_kind, "cd_hid_service_ids") == 0) {
            if (!coredevice_print_hid_service_ids) {
                fprintf(stderr, "HID service ID printer is not linked\n");
                exit(2);
            }
            return coredevice_print_hid_service_ids();
        }

        dispatch_queue_t queue = dispatch_queue_create("action-sender", DISPATCH_QUEUE_SERIAL);
        xpc_connection_t conn = xpc_connection_create("com.apple.CoreDevice.CoreDeviceService", queue);
        xpc_connection_set_event_handler(conn, ^(xpc_object_t event) {
            print_xpc("event", event);
        });
        xpc_connection_resume(conn);

        uuid_t invocation;
        uuid_generate(invocation);
        char invocation_string[37];
        uuid_unparse_upper(invocation, invocation_string);

        xpc_object_t input = xpc_dictionary_create_empty();
        if (feature && feature[0]) {
            xpc_dictionary_set_string(input, "featureIdentifier", feature);
        }
        const char *service_name = getenv("HIDCTL_CREATE_SERVICE_NAME");
        if (service_name && service_name[0]) {
            xpc_dictionary_set_string(input, "serviceName", service_name);
        }

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

        print_xpc("request", msg);
        xpc_object_t reply = xpc_connection_send_message_with_reply_sync(conn, msg);
        print_xpc("reply", reply);

        xpc_object_t output = reply ? xpc_dictionary_get_dictionary(reply, "CoreDevice.output") : NULL;
        if (output) {
            int service_fd = xpc_dictionary_dup_fd(output, "fileDescriptor");
            uint64_t version_flags = xpc_dictionary_get_uint64(output, "remoteXPCVersionFlags");
            if (!g_quiet) {
                printf("service_fd=%d remoteXPCVersionFlags=%llu\n", service_fd, version_flags);
            }

            if (service_fd >= 0) {
                dispatch_queue_t remote_queue = dispatch_queue_create("action-sender-remote", DISPATCH_QUEUE_SERIAL);
                xpc_remote_connection_t remote = xpc_remote_connection_create_with_connected_fd(service_fd, remote_queue, version_flags, connection_mode);
                if (!g_quiet) {
                    printf("remote=%p\n", remote);
                }
                if (remote) {
                    xpc_remote_connection_set_event_handler(remote, ^(xpc_object_t event) {
                        print_xpc("remote event", event);
                    });
                    xpc_remote_connection_activate(remote);

                    const char *kind = argc > 5 ? argv[5] : "probe";
                    if (strcmp(kind, "tap") == 0) {
                        double x = argc > 6 ? strtod(argv[6], NULL) : 200.0;
                        double y = argc > 7 ? strtod(argv[7], NULL) : 400.0;
                        send_tap(remote, feature, x, y);
                    } else if (strcmp(kind, "uhid_tap") == 0) {
                        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 1;
                        double x = argc > 7 ? strtod(argv[7], NULL) : 0.5;
                        double y = argc > 8 ? strtod(argv[8], NULL) : 0.5;
                        send_uhid_tap(remote, service_id, x, y);
                    } else if (strcmp(kind, "uhid_tap_pos") == 0) {
                        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 1;
                        double x = argc > 7 ? strtod(argv[7], NULL) : 0.5;
                        double y = argc > 8 ? strtod(argv[8], NULL) : 0.5;
                        send_uhid_tap_positional(remote, service_id, x, y);
                    } else if (strcmp(kind, "uhid_tap_typed") == 0) {
                        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 0x101;
                        double x = argc > 7 ? strtod(argv[7], NULL) : 0.5;
                        double y = argc > 8 ? strtod(argv[8], NULL) : 0.5;
                        send_uhid_tap_typed(remote, service_id, x, y);
                    } else if (strcmp(kind, "uhid_report_typed") == 0) {
                        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 0x101;
                        double x = argc > 7 ? strtod(argv[7], NULL) : 0.5;
                        double y = argc > 8 ? strtod(argv[8], NULL) : 0.5;
                        bool touching = argc > 9 ? strtol(argv[9], NULL, 0) != 0 : true;
                        bool in_range = argc > 10 ? strtol(argv[10], NULL, 0) != 0 : touching;
                        send_uhid_report_typed(remote, service_id, x, y, touching, in_range, 250000);
                    } else if (strcmp(kind, "cd_button") == 0) {
                        uint64_t usage_page = argc > 6 ? strtoull(argv[6], NULL, 0) : 0x0c;
                        uint64_t usage_code = argc > 7 ? strtoull(argv[7], NULL, 0) : 0x40;
                        uint8_t state = argc > 8 ? (uint8_t)strtoul(argv[8], NULL, 0) : 0;
                        send_coredevice_button_event(remote, usage_page, usage_code, state, 250000);
                    } else if (strcmp(kind, "cd_button_click") == 0) {
                        uint64_t usage_page = argc > 6 ? strtoull(argv[6], NULL, 0) : 0x0c;
                        uint64_t usage_code = argc > 7 ? strtoull(argv[7], NULL, 0) : 0x40;
                        useconds_t hold = argc > 8 ? (useconds_t)(strtod(argv[8], NULL) * 1000000.0) : 80000;
                        send_coredevice_button_click(remote, usage_page, usage_code, hold);
                    } else if (strcmp(kind, "cd_home_button") == 0) {
                        send_coredevice_button_click(remote, 0x0c, 0x40, 80000);
                    } else if (strcmp(kind, "cd_lock_button") == 0) {
                        send_coredevice_button_click(remote, 0x0c, 0x30, 80000);
                    } else if (strcmp(kind, "cd_siri_button") == 0) {
                        send_coredevice_button_click(remote, 0x0c, 0xcf, 850000);
                    } else if (strcmp(kind, "cd_recents_button") == 0) {
                        send_coredevice_button_click(remote, 0xff01, 0x100, 80000);
                    } else if (strcmp(kind, "cd_home_double_button") == 0) {
                        send_coredevice_button_double_click(remote, 0x0c, 0x40);
                    } else if (strcmp(kind, "cd_connected_services") == 0) {
                        if (!coredevice_print_connected_services) {
                            fprintf(stderr, "Connected-services printer is not linked\n");
                            exit(2);
                        }
                        int result = coredevice_print_connected_services(remote);
                        if (!g_quiet) {
                            printf("connected services result=%d\n", result);
                        }
                    } else if (strcmp(kind, "cd_connected_descriptors_async_raw") == 0) {
                        if (!coredevice_print_connected_descriptors_async_raw) {
                            fprintf(stderr, "Connected-descriptors async raw printer is not linked\n");
                            exit(2);
                        }
                        int result = coredevice_print_connected_descriptors_async_raw(remote);
                        if (!g_quiet) {
                            printf("connected descriptors async raw result=%d\n", result);
                        }
                    } else if (strcmp(kind, "cd_reset_gesture") == 0) {
                        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 0x101;
                        send_coredevice_hid_reset_gesture(remote, service_id, 250000);
                    } else if (strcmp(kind, "cd_key_report") == 0) {
                        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 0x200;
                        uint32_t usage = argc > 7 ? (uint32_t)strtoul(argv[7], NULL, 0) : 0;
                        bool pressed = argc > 8 ? strtol(argv[8], NULL, 0) != 0 : false;
                        send_coredevice_keyboard_report(remote, service_id, usage, pressed, 250000);
                    } else if (strcmp(kind, "cd_key") == 0) {
                        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 0x200;
                        uint32_t usage = argc > 7 ? (uint32_t)strtoul(argv[7], NULL, 0) : 0x29;
                        useconds_t hold = argc > 8 ? (useconds_t)(strtod(argv[8], NULL) * 1000000.0) : 80000;
                        send_coredevice_keyboard_key(remote, service_id, usage, hold);
                    } else if (strcmp(kind, "cd_digitizer_ext") == 0) {
                        double x1 = argc > 6 ? strtod(argv[6], NULL) : 0.5;
                        double y1 = argc > 7 ? strtod(argv[7], NULL) : 0.5;
                        double x2 = argc > 8 ? strtod(argv[8], NULL) : 0.0;
                        double y2 = argc > 9 ? strtod(argv[9], NULL) : 0.0;
                        uint64_t point_two_optional_tag = argc > 10 ? strtoull(argv[10], NULL, 0) : 1;
                        uint64_t event_type = argc > 11 ? strtoull(argv[11], NULL, 0) : 0;
                        uint64_t edge = argc > 12 ? strtoull(argv[12], NULL, 0) : 0;
                        uint64_t target_low = argc > 13 ? strtoull(argv[13], NULL, 0) : 0;
                        uint64_t target_high = argc > 14 ? strtoull(argv[14], NULL, 0) : 0;
                        send_coredevice_digitizer_cgpoint(remote, x1, y1, x2, y2, point_two_optional_tag, event_type, edge, target_low, target_high, 250000);
                    } else if (strcmp(kind, "cd_digitizer_tap") == 0) {
                        double x = argc > 6 ? strtod(argv[6], NULL) : 0.5;
                        double y = argc > 7 ? strtod(argv[7], NULL) : 0.5;
                        uint64_t target_low = argc > 8 ? strtoull(argv[8], NULL, 0) : 0;
                        uint64_t target_high = argc > 9 ? strtoull(argv[9], NULL, 0) : 0;
                        send_coredevice_digitizer_tap(remote, x, y, target_low, target_high);
                    } else if (strcmp(kind, "cd_digitizer_long") == 0) {
                        double x = argc > 6 ? strtod(argv[6], NULL) : 0.5;
                        double y = argc > 7 ? strtod(argv[7], NULL) : 0.5;
                        uint64_t target_low = argc > 8 ? strtoull(argv[8], NULL, 0) : 0;
                        uint64_t target_high = argc > 9 ? strtoull(argv[9], NULL, 0) : 0;
                        useconds_t duration = argc > 10 ? (useconds_t)(strtod(argv[10], NULL) * 1000000.0) : 900000;
                        send_coredevice_digitizer_long_press(remote, x, y, target_low, target_high, duration);
                    } else if (strcmp(kind, "cd_digitizer_swipe") == 0) {
                        double x1 = argc > 6 ? strtod(argv[6], NULL) : 0.5;
                        double y1 = argc > 7 ? strtod(argv[7], NULL) : 0.8;
                        double x2 = argc > 8 ? strtod(argv[8], NULL) : 0.5;
                        double y2 = argc > 9 ? strtod(argv[9], NULL) : 0.3;
                        uint64_t edge = argc > 10 ? strtoull(argv[10], NULL, 0) : 0;
                        uint64_t target_low = argc > 11 ? strtoull(argv[11], NULL, 0) : 0;
                        uint64_t target_high = argc > 12 ? strtoull(argv[12], NULL, 0) : 0;
                        useconds_t duration = argc > 13 ? (useconds_t)(strtod(argv[13], NULL) * 1000000.0) : 300000;
                        useconds_t hold = argc > 14 ? (useconds_t)(strtod(argv[14], NULL) * 1000000.0) : 0;
                        send_coredevice_digitizer_swipe(remote, x1, y1, x2, y2, edge, target_low, target_high, duration, hold);
                    } else if (strcmp(kind, "cd_nav_report") == 0) {
                        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 0x101;
                        uint32_t phase = argc > 7 ? (uint32_t)strtoul(argv[7], NULL, 0) : 0x01;
                        uint32_t swipe_mask = argc > 8 ? (uint32_t)strtoul(argv[8], NULL, 0) : 0x01;
                        uint32_t gesture_motion = argc > 9 ? (uint32_t)strtoul(argv[9], NULL, 0) : 0x0d;
                        uint32_t flavor = argc > 10 ? (uint32_t)strtoul(argv[10], NULL, 0) : 0x05;
                        double progress = argc > 11 ? strtod(argv[11], NULL) : 0.0;
                        double x = argc > 12 ? strtod(argv[12], NULL) : 0.5;
                        double y = argc > 13 ? strtod(argv[13], NULL) : 0.99;
                        send_coredevice_navigation_swipe_report(remote, service_id, phase, swipe_mask, gesture_motion, flavor, progress, x, y, 250000);
                    } else if (strcmp(kind, "cd_recents_nav") == 0) {
                        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 0x101;
                        uint32_t swipe_mask = argc > 7 ? (uint32_t)strtoul(argv[7], NULL, 0) : 0x01;
                        uint32_t flavor = argc > 8 ? (uint32_t)strtoul(argv[8], NULL, 0) : 0x05;
                        send_coredevice_navigation_recents(remote, service_id, swipe_mask, flavor);
                    } else if (strcmp(kind, "cd_dock_report") == 0) {
                        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 0x101;
                        uint32_t phase = argc > 7 ? (uint32_t)strtoul(argv[7], NULL, 0) : 0x01;
                        uint32_t swipe_mask = argc > 8 ? (uint32_t)strtoul(argv[8], NULL, 0) : 0x01;
                        uint32_t gesture_motion = argc > 9 ? (uint32_t)strtoul(argv[9], NULL, 0) : 0x0d;
                        uint32_t flavor = argc > 10 ? (uint32_t)strtoul(argv[10], NULL, 0) : 0x03;
                        double progress = argc > 11 ? strtod(argv[11], NULL) : 0.0;
                        double x = argc > 12 ? strtod(argv[12], NULL) : 0.5;
                        double y = argc > 13 ? strtod(argv[13], NULL) : 0.99;
                        send_coredevice_dock_swipe_report(remote, service_id, phase, swipe_mask, gesture_motion, flavor, progress, x, y, 250000);
                    } else if (strcmp(kind, "cd_recents_dock") == 0) {
                        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 0x101;
                        uint32_t swipe_mask = argc > 7 ? (uint32_t)strtoul(argv[7], NULL, 0) : 0x01;
                        uint32_t flavor = argc > 8 ? (uint32_t)strtoul(argv[8], NULL, 0) : 0x03;
                        send_coredevice_dock_recents(remote, service_id, swipe_mask, flavor);
                    } else if (strcmp(kind, "cd_uhid_report") == 0) {
                        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 0x101;
                        double x = argc > 7 ? strtod(argv[7], NULL) : 0.5;
                        double y = argc > 8 ? strtod(argv[8], NULL) : 0.5;
                        bool touching = argc > 9 ? strtol(argv[9], NULL, 0) != 0 : true;
                        bool in_range = argc > 10 ? strtol(argv[10], NULL, 0) != 0 : touching;
                        send_coredevice_hid_report(remote, service_id, x, y, touching, in_range, 250000);
                    } else if (strcmp(kind, "cd_uhid_swipe_report") == 0) {
                        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 0x101;
                        double x = argc > 7 ? strtod(argv[7], NULL) : 0.5;
                        double y = argc > 8 ? strtod(argv[8], NULL) : 0.5;
                        bool touching = argc > 9 ? strtol(argv[9], NULL, 0) != 0 : true;
                        bool in_range = argc > 10 ? strtol(argv[10], NULL, 0) != 0 : touching;
                        bool pending = argc > 11 ? strtol(argv[11], NULL, 0) != 0 : false;
                        bool locked = argc > 12 ? strtol(argv[12], NULL, 0) != 0 : false;
                        bool up = argc > 13 ? strtol(argv[13], NULL, 0) != 0 : false;
                        send_coredevice_hid_swipe_report(remote, service_id, x, y, touching, in_range, pending, locked, up, 250000);
                    } else if (strcmp(kind, "cd_uhid_tap") == 0) {
                        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 0x101;
                        double x = argc > 7 ? strtod(argv[7], NULL) : 0.5;
                        double y = argc > 8 ? strtod(argv[8], NULL) : 0.5;
                        send_coredevice_hid_tap(remote, service_id, x, y);
                    } else if (strcmp(kind, "cd_uhid_long") == 0) {
                        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 0x101;
                        double x = argc > 7 ? strtod(argv[7], NULL) : 0.5;
                        double y = argc > 8 ? strtod(argv[8], NULL) : 0.5;
                        useconds_t duration = argc > 9 ? (useconds_t)(strtod(argv[9], NULL) * 1000000.0) : 800000;
                        send_coredevice_hid_long_press(remote, service_id, x, y, duration);
                    } else if (strcmp(kind, "cd_uhid_swipe") == 0) {
                        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 0x101;
                        double x1 = argc > 7 ? strtod(argv[7], NULL) : 0.5;
                        double y1 = argc > 8 ? strtod(argv[8], NULL) : 0.8;
                        double x2 = argc > 9 ? strtod(argv[9], NULL) : 0.5;
                        double y2 = argc > 10 ? strtod(argv[10], NULL) : 0.3;
                        useconds_t duration = argc > 11 ? (useconds_t)(strtod(argv[11], NULL) * 1000000.0) : 300000;
                        useconds_t hold = argc > 12 ? (useconds_t)(strtod(argv[12], NULL) * 1000000.0) : 0;
                        send_coredevice_hid_swipe(remote, service_id, x1, y1, x2, y2, duration, hold);
                    } else if (strcmp(kind, "cd_uhid_scroll") == 0) {
                        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 0x101;
                        double x = argc > 7 ? strtod(argv[7], NULL) : 0.5;
                        double y = argc > 8 ? strtod(argv[8], NULL) : 0.75;
                        double dx = argc > 9 ? strtod(argv[9], NULL) : 0.0;
                        double dy = argc > 10 ? strtod(argv[10], NULL) : -0.35;
                        useconds_t duration = argc > 11 ? (useconds_t)(strtod(argv[11], NULL) * 1000000.0) : 350000;
                        send_coredevice_hid_swipe(remote, service_id, x, y, x + dx, y + dy, duration, 0);
                    } else if (strcmp(kind, "cd_home") == 0) {
                        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 0x101;
                        send_coredevice_hid_swipe(remote, service_id, 0.5, 0.985, 0.5, 0.55, 280000, 0);
                    } else if (strcmp(kind, "cd_recents") == 0) {
                        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 0x101;
                        send_coredevice_hid_swipe(remote, service_id, 0.5, 0.985, 0.5, 0.55, 360000, 800000);
                    } else if (strcmp(kind, "cd_recents_edge") == 0) {
                        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 0x101;
                        send_coredevice_hid_edge_swipe_up(remote, service_id, 0.5, 0.995, 0.5, 0.55, 420000, 850000);
                    } else if (strcmp(kind, "uhid_create_flat_tap") == 0) {
                        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 0xff0001;
                        double x = argc > 7 ? strtod(argv[7], NULL) : 0.5;
                        double y = argc > 8 ? strtod(argv[8], NULL) : 0.5;
                        send_uhid_create_tap(remote, service_id, x, y, false, false);
                    } else if (strcmp(kind, "uhid_create_pos_tap") == 0) {
                        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 0xff0001;
                        double x = argc > 7 ? strtod(argv[7], NULL) : 0.5;
                        double y = argc > 8 ? strtod(argv[8], NULL) : 0.5;
                        send_uhid_create_tap(remote, service_id, x, y, true, false);
                    } else if (strcmp(kind, "uhid_create_storage_tap") == 0) {
                        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 0xff0001;
                        double x = argc > 7 ? strtod(argv[7], NULL) : 0.5;
                        double y = argc > 8 ? strtod(argv[8], NULL) : 0.5;
                        send_uhid_create_tap(remote, service_id, x, y, false, true);
                    } else if (strcmp(kind, "uhid_create_pos_storage_tap") == 0) {
                        uint64_t service_id = argc > 6 ? strtoull(argv[6], NULL, 0) : 0xff0001;
                        double x = argc > 7 ? strtod(argv[7], NULL) : 0.5;
                        double y = argc > 8 ? strtod(argv[8], NULL) : 0.5;
                        send_uhid_create_tap(remote, service_id, x, y, true, true);
                    } else if (strcmp(kind, "mw_tap") == 0) {
                        double x = argc > 6 ? strtod(argv[6], NULL) : 200.0;
                        double y = argc > 7 ? strtod(argv[7], NULL) : 400.0;
                        send_mercury_tap(remote, x, y);
                    } else if (strcmp(kind, "long") == 0) {
                        double x = argc > 6 ? strtod(argv[6], NULL) : 200.0;
                        double y = argc > 7 ? strtod(argv[7], NULL) : 400.0;
                        useconds_t duration = argc > 8 ? (useconds_t)(strtod(argv[8], NULL) * 1000000.0) : 800000;
                        send_long_press(remote, feature, x, y, duration);
                    } else if (strcmp(kind, "swipe") == 0) {
                        double x1 = argc > 6 ? strtod(argv[6], NULL) : 200.0;
                        double y1 = argc > 7 ? strtod(argv[7], NULL) : 700.0;
                        double x2 = argc > 8 ? strtod(argv[8], NULL) : 200.0;
                        double y2 = argc > 9 ? strtod(argv[9], NULL) : 300.0;
                        useconds_t duration = argc > 10 ? (useconds_t)(strtod(argv[10], NULL) * 1000000.0) : 300000;
                        useconds_t hold = argc > 11 ? (useconds_t)(strtod(argv[11], NULL) * 1000000.0) : 0;
                        send_swipe(remote, feature, x1, y1, x2, y2, duration, hold);
                    } else if (strcmp(kind, "home") == 0) {
                        send_swipe(remote, feature, 195.0, 830.0, 195.0, 520.0, 250000, 0);
                    } else if (strcmp(kind, "recents") == 0) {
                        send_swipe(remote, feature, 195.0, 830.0, 195.0, 540.0, 300000, 700000);
                    } else {
                        xpc_object_t remote_msg = make_remote_message(feature, argc, argv);
                        if (argc > 5) {
                            send_remote_message(remote, remote_msg, 500000);
                        } else {
                            alarm(3);
                            xpc_object_t remote_reply = xpc_remote_connection_send_message_with_reply_sync(remote, remote_msg);
                            alarm(0);
                            print_xpc("remote reply", remote_reply);
                            if (remote_reply) xpc_release(remote_reply);
                        }
                        xpc_release(remote_msg);
                    }
                    const char *wait_ms = getenv("HIDCTL_WAIT_MS");
                    if (wait_ms) {
                        usleep((useconds_t)(strtoull(wait_ms, NULL, 0) * 1000));
                    }
                    xpc_remote_connection_cancel(remote);
                }
                close(service_fd);
            }
        }

        if (reply) xpc_release(reply);
        xpc_release(msg);
        xpc_release(input);
        xpc_release(components);
        xpc_release(version);
        xpc_connection_cancel(conn);
    }
    return 0;
}
