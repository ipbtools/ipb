#import "../Sources/display_geometry.h"
#include <assert.h>

static void equal(CGPoint a, CGPoint b) {
    assert(fabs(a.x-b.x)<0.00004 && fabs(a.y-b.y)<0.00004);
}
int main(void) { @autoreleasepool {
    // Measured Device Hub pointer -> digitizer pairs, including quantization.
    equal(ipbRotateUnit(CGPointMake(.84929,.74358),-1),CGPointMake(.25643,.84929));
    equal(ipbRotateUnit(CGPointMake(.72270,.14868),-2),CGPointMake(.27729,.85132));
    // Landscape-right Calculator bottom-edge capture: presentation bottom
    // center starts at native (1,.5005), then moves left to (.6108,.5005).
    equal(ipbRotateUnit(CGPointMake(.4995,1),-3),CGPointMake(1,.5005));
    // Corners, center and an asymmetric point must survive a full round trip.
    CGPoint points[]={{0,0},{1,0},{0,1},{1,1},{.5,.5},{.23,.71}};
    for(int q=0;q<4;q++) for(unsigned i=0;i<sizeof(points)/sizeof(points[0]);i++)
        equal(ipbRotateUnit(ipbRotateUnit(points[i],q),-q),points[i]);
    NSDictionary *lcd=@{@"primary":@YES,@"displayId":@1,@"nativeSize":@[@1170,@2532],
        @"pointScale":@3,@"nativeOrientation":@"rot0",@"currentOrientation":@"rot90"};
    NSDictionary *wireless=@{@"primary":@NO,@"displayId":@2,@"nativeSize":@[@1184,@2576]};
    NSMutableDictionary *result=[@{@"displays":@[wireless,lcd],@"orientation":@{
        @"currentDeviceOrientation":@"landscapeRight",@"currentDeviceNonFlatOrientation":@"landscapeRight"}} mutableCopy];
    IPBDisplayInfo info;
    assert(ipbParseDisplayInfo(result,&info));
    assert(info.displayID==1 && info.nativeSize.width==1170 && info.pointScale==3);
    assert(info.deviceQuarter==3 && info.contentQuarter==1);
    // In a landscape app, the content's logical bottom is the native right edge.
    CGPoint native=ipbRotateUnit(CGPointMake(.5,.99),-info.deviceQuarter);
    equal(ipbRotateUnit(native,-info.contentQuarter),CGPointMake(.5,.99));
    result[@"orientation"]=@{@"currentDeviceOrientation":@"faceUp",@"currentDeviceNonFlatOrientation":@"landscapeLeft"};
    assert(ipbParseDisplayInfo(result,&info) && info.deviceQuarter==1);
    result[@"displays"]=@[wireless]; assert(!ipbParseDisplayInfo(result,&info));
    result[@"displays"]=@[lcd,lcd]; assert(!ipbParseDisplayInfo(result,&info));
    NSMutableDictionary *invalid=[lcd mutableCopy]; invalid[@"nativeSize"]=@[@0,@2532];
    result[@"displays"]=@[invalid]; assert(!ipbParseDisplayInfo(result,&info));
    invalid[@"nativeSize"]=@[@1170,@2532]; invalid[@"nativeOrientation"]=@"unknown";
    assert(!ipbParseDisplayInfo(result,&info));
    assert(!ipbParseDisplayInfo(@{},&info));
    puts("display geometry contracts passed (host; does not replace device tests)");
} }
