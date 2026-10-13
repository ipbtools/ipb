#ifndef IPB_DISPLAY_GEOMETRY_H
#define IPB_DISPLAY_GEOMETRY_H
#import <Foundation/Foundation.h>
#import <CoreGraphics/CoreGraphics.h>
#include <math.h>

// Unit coordinates have a top-left origin. q counts visual left quarter-turns.
// Device Hub capture: pointer is in presentation space, digitizer in native
// space; q=1 maps pointer (x,y) back to native (1-y,x).
static inline CGPoint ipbRotateUnit(CGPoint p, int q) {
    switch (q & 3) {
        case 1: return CGPointMake(p.y,1-p.x);
        case 2: return CGPointMake(1-p.x,1-p.y);
        case 3: return CGPointMake(1-p.y,p.x);
        default: return p;
    }
}
static inline int ipbDeviceQuarter(NSString *name) {
    NSArray *names=@[@"portrait",@"landscapeLeft",@"portraitUpsideDown",@"landscapeRight"];
    NSUInteger q=[names indexOfObject:name ?: @""];
    return q==NSNotFound ? -1 : (int)q;
}
static inline int ipbDisplayQuarter(NSString *name) {
    NSArray *names=@[@"rot0",@"rot90",@"rot180",@"rot270"];
    NSUInteger q=[names indexOfObject:name ?: @""];
    return q==NSNotFound ? -1 : (int)q;
}
typedef struct {
    CGSize nativeSize;
    double pointScale;
    uint64_t displayID;
    int deviceQuarter, contentQuarter;
} IPBDisplayInfo;

static inline BOOL ipbParseDisplayInfo(NSDictionary *result, IPBDisplayInfo *out) {
    if (![result isKindOfClass:NSDictionary.class]) return NO;
    NSArray *displays=result[@"displays"];
    NSDictionary *orientation=result[@"orientation"], *primary=nil;
    if (![displays isKindOfClass:NSArray.class] || ![orientation isKindOfClass:NSDictionary.class]) return NO;
    for (id d in displays) {
        if (![d isKindOfClass:NSDictionary.class] || ![d[@"primary"] isKindOfClass:NSNumber.class] || ![d[@"primary"] boolValue]) continue;
        if (primary) return NO; // ambiguous selection must not silently choose the first
        primary=d;
    }
    NSArray *size=primary[@"nativeSize"];
    if (![size isKindOfClass:NSArray.class] || size.count!=2 ||
        ![size[0] isKindOfClass:NSNumber.class] || ![size[1] isKindOfClass:NSNumber.class] ||
        ![primary[@"pointScale"] isKindOfClass:NSNumber.class] || ![primary[@"displayId"] isKindOfClass:NSNumber.class]) return NO;
    IPBDisplayInfo value={.nativeSize=CGSizeMake([size[0] doubleValue],[size[1] doubleValue]),
        .pointScale=[primary[@"pointScale"] doubleValue], .displayID=[primary[@"displayId"] unsignedLongLongValue]};
    value.deviceQuarter=ipbDeviceQuarter(orientation[@"currentDeviceOrientation"]);
    if (value.deviceQuarter<0) value.deviceQuarter=ipbDeviceQuarter(orientation[@"currentDeviceNonFlatOrientation"]);
    value.contentQuarter=ipbDisplayQuarter(primary[@"currentOrientation"]);
    // The verified iPhone primary display has rot0 native axes. Do not invent a
    // correction for a different native coordinate system without a capture.
    if (ipbDisplayQuarter(primary[@"nativeOrientation"])!=0 || value.deviceQuarter<0 || value.contentQuarter<0 ||
        !isfinite(value.nativeSize.width) || !isfinite(value.nativeSize.height) ||
        value.nativeSize.width<=0 || value.nativeSize.height<=0 ||
        floor(value.nativeSize.width)!=value.nativeSize.width || floor(value.nativeSize.height)!=value.nativeSize.height ||
        !isfinite(value.pointScale) || value.pointScale<=0 || !value.displayID) return NO;
    *out=value; return YES;
}
#endif
