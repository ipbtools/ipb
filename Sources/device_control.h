#ifndef IPB_DEVICE_CONTROL_H
#define IPB_DEVICE_CONTROL_H
#import <Foundation/Foundation.h>
#include <signal.h>

static NSTask *ipbActiveControlTask;
static BOOL ipbControlStopped;
static NSObject *ipbControlLock(void) {
    static NSObject *lock; static dispatch_once_t once;
    dispatch_once(&once,^{ lock=[NSObject new]; }); return lock;
}
static void ipbStopDeviceControl(void) {
    @synchronized(ipbControlLock()) {
        ipbControlStopped=YES;
        if(ipbActiveControlTask.running) kill(ipbActiveControlTask.processIdentifier,SIGKILL);
    }
}

// Called only on the serial device-control queue (or before the window opens).
// The Apple command deadline is backed by a host kill deadline; no orphaned or
// overlapping metadata query is allowed. stderr retains Apple's exact errors.
static NSDictionary *ipbDeviceControl(NSString *device, NSArray<NSString *> *arguments, NSString **failure) {
    NSTask *task=[NSTask new];
    NSString *path=NSProcessInfo.processInfo.environment[@"IPB_DEVICECTL_PATH"] ?:
        @"/Library/Developer/PrivateFrameworks/CoreDevice.framework/Resources/bin/devicectl";
    NSMutableArray *args=[arguments mutableCopy];
    if ([path isEqualToString:@"xcrun devicectl"]) { path=@"/usr/bin/xcrun"; [args insertObject:@"devicectl" atIndex:0]; }
    [args addObjectsFromArray:@[@"--device",device,@"--timeout",@"5",@"--json-output",@"-",@"--quiet"]];
    task.executableURL=[NSURL fileURLWithPath:path]; task.arguments=args;
    NSPipe *pipe=[NSPipe pipe]; task.standardOutput=pipe;
    task.standardError=NSFileHandle.fileHandleWithStandardError;
    NSError *error=nil;
    @synchronized(ipbControlLock()) {
        if(ipbControlStopped){ *failure=@"device control stopped"; return nil; }
        if (![task launchAndReturnError:&error]) { *failure=error.localizedDescription; return nil; }
        ipbActiveControlTask=task;
    }
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW,6*NSEC_PER_SEC),dispatch_get_global_queue(QOS_CLASS_UTILITY,0),^{
        @synchronized(ipbControlLock()) { if(ipbActiveControlTask==task && task.running) kill(task.processIdentifier,SIGKILL); }
    });
    NSData *data=[pipe.fileHandleForReading readDataToEndOfFile];
    [task waitUntilExit];
    @synchronized(ipbControlLock()) { if(ipbActiveControlTask==task) ipbActiveControlTask=nil; }
    NSDictionary *json=[NSJSONSerialization JSONObjectWithData:data options:0 error:&error];
    if(![json isKindOfClass:NSDictionary.class]) json=nil;
    NSDictionary *info=[json[@"info"] isKindOfClass:NSDictionary.class]?json[@"info"]:nil;
    if (task.terminationStatus || ![json isKindOfClass:NSDictionary.class] || json[@"error"] ||
        ![info[@"outcome"] isEqual:@"success"]) {
        *failure=[NSString stringWithFormat:@"devicectl %@ failed (exit %d): %@",arguments,task.terminationStatus,
                  json[@"error"] ?: error.localizedDescription ?: @"missing successful result"];
        return nil;
    }
    return [json[@"result"] isKindOfClass:NSDictionary.class] ? json[@"result"] : @{};
}
#endif
