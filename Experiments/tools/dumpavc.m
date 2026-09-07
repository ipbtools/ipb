#import <Foundation/Foundation.h>
#import <objc/runtime.h>
#include <dlfcn.h>
static void dumpClass(const char *name) {
    Class c = objc_getClass(name);
    if (!c) { printf("== %s: ABSENT\n", name); return; }
    printf("== %s (super %s)\n", name, class_getName(class_getSuperclass(c)));
    unsigned n = 0; Method *ms = class_copyMethodList(c, &n);
    NSMutableArray *names = [NSMutableArray array];
    for (unsigned i = 0; i < n; i++) [names addObject:[NSString stringWithFormat:@"-%s", sel_getName(method_getName(ms[i]))]];
    free(ms);
    Method *cms = class_copyMethodList(object_getClass(c), &n);
    for (unsigned i = 0; i < n; i++) [names addObject:[NSString stringWithFormat:@"+%s", sel_getName(method_getName(cms[i]))]];
    free(cms);
    for (NSString *s in [names sortedArrayUsingSelector:@selector(compare:)]) printf("  %s\n", s.UTF8String);
    unsigned pn = 0; objc_property_t *ps = class_copyPropertyList(c, &pn);
    for (unsigned i = 0; i < pn; i++) printf("  @property %s (%s)\n", property_getName(ps[i]), property_getAttributes(ps[i]));
    free(ps);
}
static void dumpProtocol(const char *name) {
    Protocol *p = objc_getProtocol(name);
    if (!p) { printf("== @protocol %s: ABSENT\n", name); return; }
    printf("== @protocol %s\n", name);
    for (int req = 1; req >= 0; req--) for (int inst = 1; inst >= 0; inst--) {
        unsigned n = 0; struct objc_method_description *d = protocol_copyMethodDescriptionList(p, req, inst, &n);
        for (unsigned i = 0; i < n; i++) printf("  %s%s %s\n", inst ? "-" : "+", req ? "" : " (optional)", sel_getName(d[i].name));
        free(d);
    }
}
int main(int argc, char **argv) {
    void *h = dlopen("/System/Library/PrivateFrameworks/AVConference.framework/AVConference", RTLD_NOW);
    if (!h) { printf("dlopen failed: %s\n", dlerror()); return 1; }
    for (int i = 1; i < argc; i++) { if (argv[i][0] == '@') dumpProtocol(argv[i] + 1); else dumpClass(argv[i]); }
    return 0;
}
