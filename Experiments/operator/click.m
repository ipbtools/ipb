// click — precise synthetic mouse for driving Device Hub's mirror window.
//
//   click move  <x> <y>              move only, no button
//   click tap   <x> <y>              down+up at the current spot (moves first)
//   click hold  <x> <y> <seconds>    press, hold, release -- a long press
//
// System Events' `click at` cannot express a press-and-hold, and system python
// has no Quartz binding on this host, so the operator needs a real CGEvent tool
// to reach anything behind a long press (e.g. the home-screen "Remove App"
// menu, which is the route to a reproducible system alert).
//
// Every step prints what it did with a timestamp, so the operator's log and the
// tracer's JSONL can be joined afterwards without a handshake.
#import <ApplicationServices/ApplicationServices.h>
#import <Foundation/Foundation.h>

static void post(CGEventType t, CGPoint p, CGMouseButton b) {
    CGEventRef e = CGEventCreateMouseEvent(NULL, t, p, b);
    if (!e) return;
    CGEventPost(kCGHIDEventTap, e);
    CFRelease(e);
}

static double now(void) { return [[NSDate date] timeIntervalSince1970]; }

// Refuse to click unless the intended app both owns the frontmost window and
// actually has a window covering the target point.
//
// This guard exists because of a near miss: Device Hub's window was on another
// Space while a full-screen remote-desktop client occupied the active one. The
// Accessibility API still reported Device Hub's window frame perfectly happily,
// so coordinates derived from it looked correct -- but a real click at those
// screen coordinates would have landed in the remote session instead of the
// phone. AX position is where a window logically sits; it is not evidence that
// anything is drawn there.
//
// CGWindowListCopyWindowInfo reports the on-screen window list in front-to-back
// order, which is the thing AX cannot tell us. Set IPB_CLICK_EXPECT to the
// owner name that must be in front at the click point.
static bool frontmostAtPointIs(CGPoint p, NSString *owner, NSString **sawOut) {
    CFArrayRef list = CGWindowListCopyWindowInfo(
        kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements,
        kCGNullWindowID);
    if (!list) return false;
    bool ok = false;
    for (NSDictionary *w in (__bridge NSArray *)list) {
        NSNumber *layer = w[(id)kCGWindowLayer];
        if (layer.intValue != 0) continue;          // skip menu bar, dock, overlays
        CGRect r = CGRectZero;
        CGRectMakeWithDictionaryRepresentation(
            (__bridge CFDictionaryRef)w[(id)kCGWindowBounds], &r);
        if (!CGRectContainsPoint(r, p)) continue;
        NSString *name = w[(id)kCGWindowOwnerName] ?: @"?";
        if (sawOut) *sawOut = name;                 // first (frontmost) hit wins
        ok = [name isEqualToString:owner];
        break;
    }
    CFRelease(list);
    return ok;
}

int main(int argc, const char **argv) { @autoreleasepool {
    if (argc < 4) {
        fprintf(stderr, "usage: click move|tap|hold <x> <y> [seconds]\n");
        return 2;
    }
    const char *verb = argv[1];
    CGPoint p = CGPointMake(atof(argv[2]), atof(argv[3]));

    // A click that lands outside every display is a silent no-op, which would be
    // scored as a performed action. Refuse it instead.
    CGDirectDisplayID ids[8]; uint32_t n = 0;
    CGGetActiveDisplayList(8, ids, &n);
    bool inside = false;
    for (uint32_t i = 0; i < n; i++) {
        CGRect r = CGDisplayBounds(ids[i]);
        if (CGRectContainsPoint(r, p)) { inside = true; break; }
    }
    if (!inside) {
        fprintf(stderr, "click: (%.1f, %.1f) is not on any active display\n", p.x, p.y);
        return 3;
    }

    NSString *expect = [[NSProcessInfo processInfo] environment][@"IPB_CLICK_EXPECT"];
    if (expect.length) {
        NSString *saw = nil;
        if (!frontmostAtPointIs(p, expect, &saw)) {
            fprintf(stderr, "click: refusing -- (%.1f, %.1f) is covered by %s, not %s\n",
                    p.x, p.y, saw ? saw.UTF8String : "(nothing)", expect.UTF8String);
            return 4;
        }
    }

    post(kCGEventMouseMoved, p, kCGMouseButtonLeft);
    if (strcmp(verb, "move") == 0) {
        printf("{\"ts\":%.6f,\"action\":\"move\",\"x\":%.1f,\"y\":%.1f}\n", now(), p.x, p.y);
        return 0;
    }
    double hold = (strcmp(verb, "hold") == 0) ? (argc > 4 ? atof(argv[4]) : 1.0) : 0.0;
    if (strcmp(verb, "tap") != 0 && strcmp(verb, "hold") != 0) {
        fprintf(stderr, "click: unknown verb %s\n", verb);
        return 2;
    }
    usleep(120000);   // let the move settle before the button goes down
    double t0 = now();
    post(kCGEventLeftMouseDown, p, kCGMouseButtonLeft);
    if (hold > 0) usleep((useconds_t)(hold * 1e6));
    post(kCGEventLeftMouseUp, p, kCGMouseButtonLeft);
    printf("{\"ts\":%.6f,\"action\":\"%s\",\"x\":%.1f,\"y\":%.1f,\"hold\":%.2f}\n",
           t0, verb, p.x, p.y, hold);
    return 0;
} }
