#import <Foundation/Foundation.h>
#include <assert.h>
#include <dispatch/dispatch.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#import "../Sources/device_control.h"

static int failures;

static void check(BOOL condition, const char *message) {
    if (!condition) {
        fprintf(stderr, "FAIL: %s\n", message);
        failures++;
    }
}

static double monotonic_seconds(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;
}

static NSString *make_fixture(NSString *directory, NSString *marker) {
    NSString *path = [directory stringByAppendingPathComponent:@"fake-devicectl.sh"];
    NSString *script = [NSString stringWithFormat:
        @"#!/bin/sh\n"
         "mode=\"$2\"\n"
         "case \"$mode\" in\n"
         "success) printf '%%s\\n' '{\"info\":{\"outcome\":\"success\"},\"result\":{\"ok\":true}}' ;;\n"
         "error-json) printf '%%s\\n' '{\"info\":{\"outcome\":\"failure\"},\"error\":\"fixture error\"}' ;;\n"
         "non-dict) printf '%%s\\n' '[]' ;;\n"
         "info-array) printf '%%s\\n' '{\"info\":[]}' ;;\n"
         "nonzero) printf '%%s\\n' '{\"info\":{\"outcome\":\"success\"}}'; exit 7 ;;\n"
         "timeout) exec /bin/sleep 10 ;;\n"
         "stop) printf '%%s\\n' x >> '%@'; exec /bin/sleep 10 ;;\n"
         "*) printf '%%s\\n' '{\"info\":{\"outcome\":\"success\"},\"result\":{}}' ;;\n"
         "esac\n", marker];
    check([script writeToFile:path atomically:YES encoding:NSUTF8StringEncoding error:nil], "write fake devicectl");
    NSDictionary *attributes = @{ NSFilePosixPermissions: @0755 };
    check([[NSFileManager defaultManager] setAttributes:attributes ofItemAtPath:path error:nil], "chmod fake devicectl");
    return path;
}

static NSDictionary *run_fixture(NSString *mode, NSString **failure) {
    return ipbDeviceControl(@"fixture-device", @[@"fixture", mode], failure);
}

static NSDictionary *run_fixture_catching(NSString *mode, NSString **failure, BOOL *threw) {
    *threw = NO;
    @try {
        return run_fixture(mode, failure);
    } @catch (NSException *exception) {
        *threw = YES;
        *failure = [NSString stringWithFormat:@"uncaught %@: %@", exception.name, exception.reason];
        return nil;
    }
}

int main(void) { @autoreleasepool {
    NSString *directory = [NSTemporaryDirectory() stringByAppendingPathComponent:
        [NSString stringWithFormat:@"ipb-device-control-%d", getpid()]];
    [[NSFileManager defaultManager] createDirectoryAtPath:directory
                               withIntermediateDirectories:YES attributes:nil error:nil];
    NSString *marker = [directory stringByAppendingPathComponent:@"started"];
    NSString *fixture = make_fixture(directory, marker);
    setenv("IPB_DEVICECTL_PATH", fixture.fileSystemRepresentation, 1);

    NSString *failure = nil;
    NSDictionary *result = run_fixture(@"success", &failure);
    check([result isKindOfClass:NSDictionary.class] && [result[@"ok"] boolValue], "success JSON result");
    check(failure == nil, "success has no failure");

    failure = nil;
    check(run_fixture(@"error-json", &failure) == nil && failure.length > 0, "error JSON fails");
    failure = nil;
    check(run_fixture(@"non-dict", &failure) == nil && failure.length > 0, "non-dictionary JSON fails without crashing");
    failure = nil;
    BOOL infoThrew = NO;
    check(run_fixture_catching(@"info-array", &failure, &infoThrew) == nil && failure.length > 0 && !infoThrew,
          "non-dictionary info fails without crashing");
    failure = nil;
    check(run_fixture(@"nonzero", &failure) == nil && failure.length > 0, "non-zero process exit fails");

    failure = nil;
    double started = monotonic_seconds();
    check(run_fixture(@"timeout", &failure) == nil && failure.length > 0, "Apple/host timeout fails");
    double elapsed = monotonic_seconds() - started;
    check(elapsed >= 5.0 && elapsed < 8.5, "host deadline kills the 10-second fixture near 6 seconds");

    dispatch_semaphore_t completed = dispatch_semaphore_create(0);
    __block NSString *stopFailure = nil;
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_UTILITY, 0), ^{
        (void)run_fixture(@"stop", &stopFailure);
        dispatch_semaphore_signal(completed);
    });
    BOOL startedFixture = NO;
    for (int i = 0; i < 200; i++) {
        if ([[NSFileManager defaultManager] fileExistsAtPath:marker]) { startedFixture = YES; break; }
        usleep(10000);
    }
    check(startedFixture, "stop fixture started");
    ipbStopDeviceControl();
    check(dispatch_semaphore_wait(completed, dispatch_time(DISPATCH_TIME_NOW, 2 * NSEC_PER_SEC)) == 0,
          "stop cancels active task");
    check(stopFailure.length > 0, "cancelled task reports failure");
    unsigned long long markerSize = [[[NSFileManager defaultManager] attributesOfItemAtPath:marker error:nil][NSFileSize] unsignedLongLongValue];
    NSString *secondFailure = nil;
    check(run_fixture(@"success", &secondFailure) == nil && [secondFailure containsString:@"stopped"],
          "stop prevents a new task from launching");
    unsigned long long markerSizeAfter = [[[NSFileManager defaultManager] attributesOfItemAtPath:marker error:nil][NSFileSize] unsignedLongLongValue];
    check(markerSize == markerSizeAfter, "stopped state launches no replacement task");

    [[NSFileManager defaultManager] removeItemAtPath:directory error:nil];
    unsetenv("IPB_DEVICECTL_PATH");
    if (failures == 0) puts("device control contracts passed (host; no device command)");
    return failures ? 1 : 0;
} }
