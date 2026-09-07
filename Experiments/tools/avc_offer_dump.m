#import <Foundation/Foundation.h>
#import <objc/runtime.h>
#include <dlfcn.h>
@interface AVCMediaStreamNegotiator : NSObject
- (instancetype)initWithMode:(long)mode options:(NSDictionary*)o error:(NSError**)e;
- (instancetype)initWithMode:(long)mode error:(NSError**)e;
- (BOOL)createOffer; - (NSData*)offer;
- (id)generateMediaStreamConfigurationWithError:(NSError**)e;
- (id)generateMediaStreamInitOptionsWithError:(NSError**)e;
@end
static void pp(id o, int ind) {
    NSString *pad = [@"" stringByPaddingToLength:ind*2 withString:@" " startingAtIndex:0];
    if ([o isKindOfClass:[NSDictionary class]]) {
        for (id k in [[o allKeys] sortedArrayUsingSelector:@selector(description)]) {
            id v = o[k];
            if ([v isKindOfClass:[NSDictionary class]] || [v isKindOfClass:[NSArray class]]) { printf("%s%s:\n", pad.UTF8String, [k description].UTF8String); pp(v, ind+1); }
            else if ([v isKindOfClass:[NSData class]]) printf("%s%s: <%lu bytes>\n", pad.UTF8String, [k description].UTF8String, (unsigned long)[v length]);
            else printf("%s%s: %s\n", pad.UTF8String, [k description].UTF8String, [[v description] substringToIndex:MIN(80,[[v description] length])].UTF8String);
        }
    } else if ([o isKindOfClass:[NSArray class]]) { int i=0; for (id v in o) { printf("%s[%d]:\n", pad.UTF8String, i++); pp(v, ind+1);} }
    else printf("%s%s\n", pad.UTF8String, [[o description] substringToIndex:MIN(120,[[o description] length])].UTF8String);
}
int main(int argc, char**argv) {
    dlopen("/System/Library/PrivateFrameworks/AVConference.framework/AVConference", RTLD_NOW);
    long mode = argc>1?atol(argv[1]):1;
    Class N = objc_getClass("AVCMediaStreamNegotiator");
    NSError *e=nil; id neg=[[N alloc] initWithMode:mode options:@{} error:&e];
    if(!neg){printf("init fail %s\n",e.description.UTF8String);return 1;}
    id initOpts = [neg generateMediaStreamInitOptionsWithError:&e];
    printf("== initOptions err=%s\n", e?e.description.UTF8String:"nil"); if(initOpts) pp(initOpts,1);
    [neg createOffer]; NSData *off=[neg offer];
    id plist=[NSPropertyListSerialization propertyListWithData:off options:0 format:NULL error:&e];
    printf("== offer (mode %ld, %lu bytes) err=%s\n", mode, (unsigned long)off.length, e?e.description.UTF8String:"nil");
    if(plist) pp(plist,1);
    return 0;
}
