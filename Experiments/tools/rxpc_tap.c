// DYLD_INSERT_LIBRARIES interposer: log every RemoteXPC message the helper sends/receives.
#include <xpc/xpc.h>
#include <stdio.h>
#include <stdlib.h>
#include <dispatch/dispatch.h>
typedef void *xpc_remote_connection_t;
extern void xpc_remote_connection_send_message(xpc_remote_connection_t c, xpc_object_t m);
extern void xpc_remote_connection_send_message_with_reply(xpc_remote_connection_t c, xpc_object_t m, dispatch_queue_t q, xpc_handler_t h);
extern xpc_object_t xpc_remote_connection_send_message_with_reply_sync(xpc_remote_connection_t c, xpc_object_t m);
extern void xpc_remote_connection_set_event_handler(xpc_remote_connection_t c, xpc_handler_t h);
static void logmsg(const char *tag, xpc_object_t m) {
    char *d = xpc_copy_description(m);
    fprintf(stderr, "\n>>> %s\n%s\n", tag, d ? d : "<null>"); free(d);
}
static void my_send(xpc_remote_connection_t c, xpc_object_t m) { logmsg("SEND", m); xpc_remote_connection_send_message(c, m); }
static void my_send_reply(xpc_remote_connection_t c, xpc_object_t m, dispatch_queue_t q, xpc_handler_t h) {
    logmsg("SEND_WITH_REPLY", m);
    xpc_handler_t wrapped = ^(xpc_object_t r) { logmsg("REPLY", r); h(r); };
    xpc_remote_connection_send_message_with_reply(c, m, q, wrapped);
}
static xpc_object_t my_send_sync(xpc_remote_connection_t c, xpc_object_t m) {
    logmsg("SEND_SYNC", m);
    xpc_object_t r = xpc_remote_connection_send_message_with_reply_sync(c, m);
    logmsg("SYNC_REPLY", r); return r;
}
static void my_set_handler(xpc_remote_connection_t c, xpc_handler_t h) {
    xpc_handler_t wrapped = ^(xpc_object_t e) { logmsg("EVENT", e); h(e); };
    xpc_remote_connection_set_event_handler(c, wrapped);
}
__attribute__((used)) static struct { const void *n, *o; } interposers[] __attribute__((section("__DATA,__interpose"))) = {
    { (const void *)my_send, (const void *)xpc_remote_connection_send_message },
    { (const void *)my_send_reply, (const void *)xpc_remote_connection_send_message_with_reply },
    { (const void *)my_send_sync, (const void *)xpc_remote_connection_send_message_with_reply_sync },
    { (const void *)my_set_handler, (const void *)xpc_remote_connection_set_event_handler },
};
