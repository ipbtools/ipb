#import <Foundation/Foundation.h>
#include <dlfcn.h>
#import <objc/runtime.h>
@interface AVCMediaStreamNegotiator : NSObject
- (instancetype)initWithMode:(long)mode error:(NSError**)e;
- (instancetype)initWithMode:(long)mode options:(NSDictionary*)o error:(NSError**)e;
- (BOOL)createOffer;
- (NSData*)offer;
@end
int main(void) {
    void *h = dlopen("/System/Library/PrivateFrameworks/AVConference.framework/AVConference", RTLD_NOW);
    if (!h) { printf("dlopen: %s\n", dlerror()); return 1; }
    Class N = objc_getClass("AVCMediaStreamNegotiator");
    printf("negotiator class = %p\n", N);
    for (long mode = 0; mode <= 4; mode++) {
        NSError *e = nil;
        id neg = [[N alloc] initWithMode:mode error:&e];
        printf("mode %ld -> neg=%p err=%s\n", mode, neg, e ? e.description.UTF8String : "nil");
        if (neg) {
            NSError *e2 = nil;
            id neg2 = [[N alloc] initWithMode:mode options:@{} error:&e2];
            printf("   with options{} -> %p err=%s\n", neg2, e2 ? [e2.description substringToIndex:MIN(120,e2.description.length)].UTF8String : "nil");
            BOOL ok = [neg createOffer];
            NSData *off = [neg offer];
            printf("   createOffer=%d offer=%lu bytes\n", ok, (unsigned long)off.length);
            if (off.length) printf("   offer head: %s\n", [[off subdataWithRange:NSMakeRange(0, MIN(48,off.length))] description].UTF8String);
        }
    }
    return 0;
}
