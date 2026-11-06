// Read-only simulator guest probe. ABI/source evidence: docs/duo-ddi-exploration.md.
// This executable is never installed on a physical phone or shipped by make install.
#import <Foundation/Foundation.h>
#import <UIKit/UIKit.h>
#import <objc/message.h>
#include <dlfcn.h>
#include <math.h>
#include <signal.h>
#include <unistd.h>

static SEL method(id object, const char *name) {
    SEL result = sel_registerName(name);
    if (!object || ![object respondsToSelector:result])
        @throw [NSException exceptionWithName:@"Unavailable" reason:@(name) userInfo:nil];
    return result;
}
static id get(id object, const char *name) {
    return ((id (*)(id, SEL))objc_msgSend)(object, method(object, name));
}
static id get1(id object, const char *name, id argument) {
    return ((id (*)(id, SEL, id))objc_msgSend)(object, method(object, name), argument);
}
static void invoke(id object, const char *name) {
    ((void (*)(id, SEL))objc_msgSend)(object, method(object, name));
}
static void invoke1(id object, const char *name, id argument) {
    ((void (*)(id, SEL, id))objc_msgSend)(object, method(object, name), argument);
}
static NSNumber *integer(id object, const char *name) {
    return @(((NSInteger (*)(id, SEL))objc_msgSend)(object, method(object, name)));
}
static NSNumber *boolean(id object, const char *name) {
    return @(((BOOL (*)(id, SEL))objc_msgSend)(object, method(object, name)));
}
static id nullable(id object) { return object ?: NSNull.null; }
static NSDictionary *rect(id object, const char *name) {
    CGRect value = ((CGRect (*)(id, SEL))objc_msgSend)(object, method(object, name));
    if (!isfinite(value.origin.x) || !isfinite(value.origin.y) ||
        !isfinite(value.size.width) || !isfinite(value.size.height))
        @throw [NSException exceptionWithName:@"InvalidFrame" reason:@(name) userInfo:nil];
    return @{@"x": @(value.origin.x), @"y": @(value.origin.y),
             @"width": @(value.size.width), @"height": @(value.size.height)};
}
static NSDictionary *identity(id object) {
    return @{@"uniqueIdentifier": nullable(get(object, "uniqueIdentifier")),
             @"displayID": @(((uint32_t (*)(id, SEL))objc_msgSend)(object, method(object, "displayID"))),
             @"connectionSeed": @(((uint32_t (*)(id, SEL))objc_msgSend)(object, method(object, "connectionSeed"))),
             @"typeRaw": integer(object, "type"), @"isExternal": boolean(object, "isExternal"),
             @"isMainDisplay": boolean(object, "isMainDisplay"),
             @"isUIKitMainLike": boolean(object, "isUIKitMainLike")};
}
static NSDictionary *configuration(id object) {
    return @{@"uniqueIdentifier": nullable(get(object, "uniqueIdentifier")),
             @"name": nullable(get(object, "name")), @"bounds": rect(object, "bounds"),
             @"pointScale": @(((double (*)(id, SEL))objc_msgSend)(object, method(object, "pointScale"))),
             @"identity": identity(get(object, "identity"))};
}
static id layout(id object) {
    if (!object) return NSNull.null;
    if (![object isKindOfClass:NSClassFromString(@"FBSDisplayLayout")])
        @throw [NSException exceptionWithName:@"UnexpectedLayoutClass"
                                      reason:NSStringFromClass([object class]) userInfo:nil];
    NSMutableArray *elements = [NSMutableArray array];
    for (id element in get(object, "elements")) {
        [elements addObject:@{@"identifier": nullable(get(element, "identifier")),
            @"bundleIdentifier": nullable(get(element, "bundleIdentifier")),
            @"frame": rect(element, "frame"), @"referenceFrame": rect(element, "referenceFrame"),
            @"hasKeyboardFocus": boolean(element, "hasKeyboardFocus"),
            @"isUIApplicationElement": boolean(element, "isUIApplicationElement"),
            @"fillsDisplayBounds": boolean(element, "fillsDisplayBounds"),
            @"levelRaw": integer(element, "level")}];
    }
    // Opaque identifiers and these raw rectangles are not a scene registry or a transform.
    return @{@"sourceSpace": @"fbs-layout-raw", @"elements": elements,
             @"bounds": rect(object, "bounds"), @"referenceBounds": rect(object, "referenceBounds"),
             @"interfaceOrientationRaw": integer(object, "interfaceOrientation"),
             @"displayConfiguration": configuration(get(object, "displayConfiguration"))};
}
static void expired(int number) { (void)number; _exit(5); }
int main(void) {
    signal(SIGALRM, expired);
    alarm(8);
    @autoreleasepool {
        @try {
            if (!dlopen("/System/Library/PrivateFrameworks/FrontBoardServices.framework/FrontBoardServices",
                        RTLD_NOW | RTLD_GLOBAL)) return 6;
            id displays = [[NSClassFromString(@"FBSDisplayMonitor") alloc] init];
            id config = get(NSClassFromString(@"FBSDisplayLayoutMonitorConfiguration"),
                            "configurationForDefaultMainDisplayMonitor");
            invoke1(config, "setTransitionHandler:", ^(id monitor, id value, id context) {
                (void)monitor; (void)value; (void)context;
            });
            id monitor = get1(NSClassFromString(@"FBSDisplayLayoutMonitor"), "monitorWithConfiguration:", config);
            [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:2]];
            NSMutableArray *inventory = [NSMutableArray array];
            for (id item in get(displays, "connectedIdentities"))
                [inventory addObject:@{@"identity": identity(item),
                    @"configuration": configuration(get1(displays, "configurationForIdentity:", item))}];
            id result = @{@"backend": @"simulator-guest-frontboard", @"atomic": @NO,
                @"displays": inventory,
                @"defaultMainLayout": layout(get(monitor, "currentLayout"))};
            invoke(monitor, "invalidate");
            invoke(displays, "invalidate");
            NSError *error = nil;
            NSData *data = [NSJSONSerialization dataWithJSONObject:result
                options:NSJSONWritingSortedKeys error:&error];
            if (!data) { fprintf(stderr, "%s\n", error.description.UTF8String); return 6; }
            fwrite(data.bytes, 1, data.length, stdout); puts("");
            return 0;
        } @catch (NSException *error) {
            fprintf(stderr, "%s: %s\n", error.name.UTF8String, error.reason.UTF8String);
            return 6;
        }
    }
}
