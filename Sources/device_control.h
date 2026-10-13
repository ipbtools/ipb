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

enum { IPBDevicePayloadLimit=2*1024*1024 };
// One runner on the serial device-control queue (or before the window opens).
// Metadata and clipboard share cancellation/deadlines. Payloads never enter argv/logs.
static NSData *ipbDeviceCommand(NSString *device, NSArray<NSString *> *arguments,
                              NSData *input, BOOL jsonOutput, NSString **failure) {
    if(input.length>IPBDevicePayloadLimit){ *failure=@"clipboard text exceeds 2 MiB"; return nil; }
    NSTask *task=[NSTask new];
    NSString *path=NSProcessInfo.processInfo.environment[@"IPB_DEVICECTL_PATH"] ?:
        @"/Library/Developer/PrivateFrameworks/CoreDevice.framework/Resources/bin/devicectl";
    NSMutableArray *args=[arguments mutableCopy];
    if ([path isEqualToString:@"xcrun devicectl"]) { path=@"/usr/bin/xcrun"; [args insertObject:@"devicectl" atIndex:0]; }
    [args addObjectsFromArray:@[@"--device",device,@"--timeout",@"5",@"--quiet"]];
    if(jsonOutput) [args addObjectsFromArray:@[@"--json-output",@"-"]];
    task.executableURL=[NSURL fileURLWithPath:path]; task.arguments=args;
    NSPipe *pipe=[NSPipe pipe]; task.standardOutput=pipe;
    task.standardError=NSFileHandle.fileHandleWithStandardError;
    NSPipe *inPipe=input?[NSPipe pipe]:nil;
    task.standardInput=inPipe ?: [NSFileHandle fileHandleWithNullDevice];
    NSError *error=nil;
    @synchronized(ipbControlLock()) {
        if(ipbControlStopped){ *failure=@"device control stopped"; return nil; }
        if (![task launchAndReturnError:&error]) { *failure=error.localizedDescription; return nil; }
        ipbActiveControlTask=task;
    }
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW,6*NSEC_PER_SEC),dispatch_get_global_queue(QOS_CLASS_UTILITY,0),^{
        @synchronized(ipbControlLock()) { if(ipbActiveControlTask==task && task.running) kill(task.processIdentifier,SIGKILL); }
    });
    dispatch_group_t writes=dispatch_group_create();
    __block BOOL writeFailed=NO;
    if(inPipe) dispatch_group_async(writes,dispatch_get_global_queue(QOS_CLASS_UTILITY,0),^{
        @try { [inPipe.fileHandleForWriting writeData:input]; }
        @catch(NSException *exception) { writeFailed=YES; }
        @finally { [inPipe.fileHandleForWriting closeFile]; }
    });
    NSMutableData *data=[NSMutableData data]; BOOL oversized=NO;
    for(;;){
        NSData *chunk=[pipe.fileHandleForReading readDataOfLength:65536];
        if(!chunk.length) break;
        if(data.length+chunk.length>IPBDevicePayloadLimit){ oversized=YES; kill(task.processIdentifier,SIGKILL); break; }
        [data appendData:chunk];
    }
    [pipe.fileHandleForReading closeFile];
    [task waitUntilExit];
    BOOL writerTimedOut=dispatch_group_wait(writes,dispatch_time(DISPATCH_TIME_NOW,NSEC_PER_SEC))!=0;
    @synchronized(ipbControlLock()) { if(ipbActiveControlTask==task) ipbActiveControlTask=nil; }
    if(task.terminationStatus || oversized || writerTimedOut || writeFailed){
        *failure=[NSString stringWithFormat:@"devicectl %@ failed (exit %d)%@",arguments,task.terminationStatus,
            oversized?@": output exceeds 2 MiB":writerTimedOut || writeFailed?@": stdin transfer failed":@""];
        return nil;
    }
    return data;
}

static NSDictionary *ipbDeviceControl(NSString *device, NSArray<NSString *> *arguments, NSString **failure) {
    NSData *data=ipbDeviceCommand(device,arguments,nil,YES,failure);
    if(!data) return nil;
    NSError *error=nil;
    NSDictionary *json=[NSJSONSerialization JSONObjectWithData:data options:0 error:&error];
    if(![json isKindOfClass:NSDictionary.class]) json=nil;
    NSDictionary *info=[json[@"info"] isKindOfClass:NSDictionary.class]?json[@"info"]:nil;
    if (![json isKindOfClass:NSDictionary.class] || json[@"error"] ||
        ![info[@"outcome"] isEqual:@"success"]) {
        *failure=[NSString stringWithFormat:@"devicectl %@ failed: %@",arguments,
                  json[@"error"] ?: error.localizedDescription ?: @"missing successful result"];
        return nil;
    }
    return [json[@"result"] isKindOfClass:NSDictionary.class] ? json[@"result"] : @{};
}
#endif
