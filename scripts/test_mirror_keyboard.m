// Exercise the real mirror FIFO/continuations with mock HID and a host-only command fixture.
// No NSApplication window, device socket or system clipboard is opened.
#define main ipb_mirror_unused_main
#define uhid_make_keyboard_state_hid_report fixture_keyboard_build
#define coredevice_send_universalhid_hid_report fixture_keyboard_send
#define coredevice_send_universalhid_barrier fixture_keyboard_barrier
#include "../Sources/mirror.m"
#undef main
#include <assert.h>
#include <sys/stat.h>

static IPBKeyboardState built[128],sent[128];
static unsigned builtCount,sentCount;
static NSString *fixturePayloadPath;
static NSString *fixtureCountPath;
static BOOL copyBeforeChord;
@interface FixturePasteboard : NSObject
@property(nonatomic) NSInteger changeCount;
@property(nonatomic,strong) NSString *text;
+ (id)board;
- (NSString*)stringForType:(id)type;
- (NSInteger)clearContents;
- (BOOL)setString:(NSString*)value forType:(id)type;
@end
static FixturePasteboard *fixtureBoard;
@implementation FixturePasteboard
+ (id)board { return fixtureBoard; }
- (NSString*)stringForType:(id)type { return self.text; }
- (NSInteger)clearContents { self.text=nil; return ++self.changeCount; }
- (BOOL)setString:(NSString*)value forType:(id)type { self.text=value; return YES; }
@end
int fixture_keyboard_build(const uint32_t *usages,int32_t count,void *output){
    assert(builtCount<128); IPBKeyboardState held={0};
    for(int32_t i=0;i<count;i++) ipbKeyboardSet(&held,usages[i],true);
    built[builtCount]=held;
    uint64_t *words=output; words[0]=builtCount++; words[1]=0; return 16;
}
int fixture_keyboard_send(xrc_t remote,const void *output,uint64_t service){
    const uint64_t *words=output; assert(sentCount<128);
    sent[sentCount++]=built[words[0]];
    if(sentCount==1) copyBeforeChord=[[NSData dataWithContentsOfFile:fixturePayloadPath]
        isEqualToData:[@"fixture-中文🙂" dataUsingEncoding:NSUTF8StringEncoding]];
    if(ipbKeyboardHas(sent[sentCount-1],227) && ipbKeyboardHas(sent[sentCount-1],6)){
        assert([@"copied-中文🙂" writeToFile:fixturePayloadPath atomically:YES encoding:NSUTF8StringEncoding error:nil]);
        assert([@"2" writeToFile:fixtureCountPath atomically:YES encoding:NSUTF8StringEncoding error:nil]);
    }
    return 0;
}
int fixture_keyboard_barrier(xrc_t remote){ return 0; }
static void waitInput(void){
    double deadline=nowSec()+3;
    while(dispatch_group_wait(gInputGroup,DISPATCH_TIME_NOW) && nowSec()<deadline)
        [[NSRunLoop mainRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:.005]];
    assert(!dispatch_group_wait(gInputGroup,DISPATCH_TIME_NOW));
}
int main(void){ @autoreleasepool {
    signal(SIGPIPE,SIG_IGN);
    NSString *directory=[NSTemporaryDirectory() stringByAppendingPathComponent:NSUUID.UUID.UUIDString];
    assert([[NSFileManager defaultManager] createDirectoryAtPath:directory withIntermediateDirectories:YES attributes:nil error:nil]);
    fixturePayloadPath=[directory stringByAppendingPathComponent:@"payload"];
    fixtureCountPath=[directory stringByAppendingPathComponent:@"count"];
    assert([@"1" writeToFile:fixtureCountPath atomically:YES encoding:NSUTF8StringEncoding error:nil]);
    NSString *command=[directory stringByAppendingPathComponent:@"devicectl"];
    NSString *script=[NSString stringWithFormat:@"#!/bin/sh\ncase \"$3\" in\n"
        "copy) exec /bin/cat > '%@' ;;\n"
        "paste) exec /bin/cat '%@' ;;\n"
        "info) count=$(/bin/cat '%@'); printf '{\"info\":{\"outcome\":\"success\"},\"result\":{\"changeCount\":%%s}}' \"$count\" ;;\n"
        "esac\n",fixturePayloadPath,fixturePayloadPath,fixtureCountPath];
    assert([script writeToFile:command atomically:YES encoding:NSUTF8StringEncoding error:nil]);
    assert(!chmod(command.fileSystemRepresentation,0700));
    setenv("IPB_DEVICECTL_PATH",command.fileSystemRepresentation,1);
    gDeviceIdentifier=@"fixture"; gKeyboardServiceID=0x200; gReady=YES;
    gInputQueue=dispatch_queue_create("fixture.input",DISPATCH_QUEUE_SERIAL);
    gDeviceQueue=dispatch_queue_create("fixture.control",DISPATCH_QUEUE_SERIAL);
    gInputGroup=dispatch_group_create(); gDeviceGroup=dispatch_group_create();
    ipb_bounded_sender_init(&gInputSender);
    NSData *text=[@"fixture-中文🙂" dataUsingEncoding:NSUTF8StringEncoding];
    gTextPayloads[0]=text; gTextPayloadBytes=text.length;
    submitEvent((Event){.kind=PasteText,.generation=1,.keyboardEpoch=1,.submit=nowSec()},Pending);
    IPBKeyboardState b={0}; ipbKeyboardSet(&b,5,true);
    submitEvent((Event){.kind=KeyboardState,.generation=1,.keyboardEpoch=1,.keyboardState=b,.submit=nowSec()},Pending);
    waitInput();
    assert(copyBeforeChord && sentCount==5);
    assert(ipbKeyboardHas(sent[0],227) && !ipbKeyboardHas(sent[0],25));
    assert(ipbKeyboardHas(sent[1],227) && ipbKeyboardHas(sent[1],25));
    assert(!ipbKeyboardHas(sent[2],227) && ipbKeyboardHas(sent[2],25));
    assert(ipbKeyboardEmpty(sent[3]) && ipbKeyboardHas(sent[4],5));
    assert(!gTextPayloadBytes && !gTextPayloads[0]);
    // Repeat releases/represses only B while preserving Shift, then key-up keeps Shift.
    ipbKeyboardSet(&b,225,true);
    submitEvent((Event){.kind=KeyboardState,.generation=1,.keyboardEpoch=1,.keyboardState=b,.keyboardUsage=5,.submit=nowSec()},Pending);
    ipbKeyboardSet(&b,5,false);
    submitEvent((Event){.kind=KeyboardState,.generation=1,.keyboardEpoch=1,.keyboardState=b,.submit=nowSec()},Pending);
    waitInput();
    assert(ipbKeyboardHas(sent[5],225) && !ipbKeyboardHas(sent[5],5));
    assert(ipbKeyboardHas(sent[6],225) && ipbKeyboardHas(sent[6],5));
    assert(ipbKeyboardHas(sent[7],225) && !ipbKeyboardHas(sent[7],5));
    // A stale queued down cannot revive keys; focus loss still admits an empty release.
    atomic_store(&gKeyboardEpoch,2); gKeyboardTouched=YES; gKeyboardHeld=b;
    submitEvent((Event){.kind=KeyboardState,.generation=1,.keyboardEpoch=1,.keyboardState=b,.submit=nowSec()},Pending);
    releaseKeyboard(YES); waitInput();
    assert(ipbKeyboardEmpty(sent[8]) && ipbKeyboardEmpty(sent[9]));
    assert(!atomic_load(&gFailure) && ipbKeyboardEmpty(gKeyboardHeld));
    // Substitute only this test process's pasteboard getter. The user's clipboard is untouched.
    fixtureBoard=[FixturePasteboard new]; fixtureBoard.text=@"old"; fixtureBoard.changeCount=1;
    Method getter=class_getClassMethod(NSPasteboard.class,@selector(generalPasteboard));
    IMP original=method_getImplementation(getter);
    method_setImplementation(getter,method_getImplementation(class_getClassMethod(FixturePasteboard.class,@selector(board))));
    unsigned start=sentCount;
    submitEvent((Event){.kind=CopyText,.generation=1,.keyboardEpoch=3,.hostClipboardCount=1,.submit=nowSec()},Pending);
    submitEvent((Event){.kind=PasteText,.generation=1,.keyboardEpoch=3,.pasteFromHost=YES,.submit=nowSec()},Pending);
    waitInput();
    assert(!atomic_load(&gFailure) && sentCount==start+8);
    assert([fixtureBoard.text isEqualToString:@"copied-中文🙂"]);
    assert([[NSString stringWithContentsOfFile:fixturePayloadPath encoding:NSUTF8StringEncoding error:nil]
        isEqualToString:@"copied-中文🙂"]); // following Paste did not capture old Mac clipboard
    assert(!gTextPayloadBytes);
    method_setImplementation(getter,original);
    assert(ipb_bounded_sender_close(&gInputSender,ipb_bounded_now_ns()+NSEC_PER_SEC));
    [[NSFileManager defaultManager] removeItemAtPath:directory error:nil];
    puts("mirror keyboard FIFO passed (paste ordering, chord, repeat, held modifiers, stale release, Copy→Paste; mocks)");
    return 0;
} }
