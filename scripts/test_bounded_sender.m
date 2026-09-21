#include <dispatch/dispatch.h>
#include <errno.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdatomic.h>
#include <unistd.h>
#include "../Sources/bounded_sender.h"

typedef struct {
    ipb_bounded_sender *sender;
    uint64_t deadline;
    int result;
    bool started;
    int (^call)(void);
    dispatch_semaphore_t returned;
} invocation;

static void check(bool condition, const char *message) {
    if (!condition) { fprintf(stderr, "FAIL: %s\n", message); exit(1); }
}

static bool wait_for(dispatch_semaphore_t semaphore, double seconds) {
    return dispatch_semaphore_wait(semaphore,
        dispatch_time(DISPATCH_TIME_NOW, (int64_t)(seconds * NSEC_PER_SEC))) == 0;
}

static void *invoke(void *opaque) {
    invocation *in = opaque;
    in->result = ipb_bounded_call(in->sender, in->deadline, in->call, &in->started);
    if (in->returned) dispatch_semaphore_signal(in->returned);
    return NULL;
}

typedef struct {
    dispatch_semaphore_t entered;
    dispatch_semaphore_t release;
    _Atomic int calls;
    _Atomic int active;
    _Atomic int maxActive;
} fault;

static int blocking_call(fault *f) {
    int active = atomic_fetch_add(&f->active, 1) + 1;
    atomic_fetch_add(&f->calls, 1);
    int old = atomic_load(&f->maxActive);
    while (active > old && !atomic_compare_exchange_weak(&f->maxActive, &old, active)) {}
    dispatch_semaphore_signal(f->entered);
    dispatch_semaphore_wait(f->release, DISPATCH_TIME_FOREVER);
    atomic_fetch_sub(&f->active, 1);
    return 17;
}

int main(void) {
    ipb_bounded_sender sender;
    ipb_bounded_sender_init(&sender);
    fault f = {
        .entered = dispatch_semaphore_create(0),
        .release = dispatch_semaphore_create(0),
    };
    __block fault *fp = &f;
    dispatch_semaphore_t firstReturned = dispatch_semaphore_create(0);
    invocation first = {
        .sender = &sender,
        .deadline = ipb_bounded_now_ns() + 100ull * NSEC_PER_MSEC,
        .call = ^{ return blocking_call(fp); },
        .returned = firstReturned,
    };
    pthread_t firstThread;
    check(pthread_create(&firstThread, NULL, invoke, &first) == 0, "create first invocation");
    check(wait_for(f.entered, 1.0), "first call entered");
    check(wait_for(firstReturned, 1.0), "first caller reached its deadline");

    bool secondStarted = false;
    int second = ipb_bounded_call(&sender,
        ipb_bounded_now_ns() + 100ull * NSEC_PER_MSEC,
        ^{ atomic_fetch_add(&fp->calls, 1); return 23; }, &secondStarted);
    check(second == IPB_BOUNDED_TIMEOUT, "second call is bounded while owner is active");
    check(!secondStarted, "second call was not admitted");
    check(atomic_load(&f.calls) == 1, "second call was not invoked");
    check(atomic_load(&f.maxActive) == 1, "at most one call was active");

    dispatch_semaphore_signal(f.release);
    check(pthread_join(firstThread, NULL) == 0, "join first invocation");
    check(first.result == IPB_BOUNDED_TIMEOUT, "first caller times out while owner continues");

    bool recoveredStarted = false;
    int recovered = ipb_bounded_call(&sender,
        ipb_bounded_now_ns() + NSEC_PER_SEC,
        ^{ atomic_fetch_add(&fp->calls, 1); return 19; }, &recoveredStarted);
    check(recovered == 19 && recoveredStarted, "sender recovers after owner returns");
    check(atomic_load(&f.maxActive) == 1, "recovery did not overlap the old owner");

    int propagated = ipb_bounded_call(&sender,
        ipb_bounded_now_ns() + NSEC_PER_SEC,
        ^{ return -7; }, NULL);
    check(propagated == -7, "sender failure propagates without retry");
    check(atomic_load(&f.calls) == 2, "no replay occurred");

    ipb_bounded_sender occupied;
    ipb_bounded_sender_init(&occupied);
    fault f2 = {
        .entered = dispatch_semaphore_create(0),
        .release = dispatch_semaphore_create(0),
    };
    __block fault *fp2 = &f2;
    invocation held = {
        .sender = &occupied,
        .deadline = ipb_bounded_now_ns() + 3ull * NSEC_PER_SEC,
        .call = ^{ return blocking_call(fp2); },
    };
    pthread_t heldThread;
    check(pthread_create(&heldThread, NULL, invoke, &held) == 0, "create occupied invocation");
    check(wait_for(f2.entered, 1.0), "occupied call entered");
    bool drained = ipb_bounded_sender_close(&occupied,
        ipb_bounded_now_ns() + 100ull * NSEC_PER_MSEC);
    check(!drained, "close reports an active owner at its deadline");
    bool rejectedStarted = false;
    int rejected = ipb_bounded_call(&occupied,
        ipb_bounded_now_ns() + NSEC_PER_SEC,
        ^{ return 31; }, &rejectedStarted);
    check(rejected == IPB_BOUNDED_CLOSED && !rejectedStarted,
          "closing rejects admission without invoking the call");
    dispatch_semaphore_signal(f2.release);
    check(pthread_join(heldThread, NULL) == 0, "join occupied invocation");
    check(held.result == 17, "active owner completes after bounded close");
    check(ipb_bounded_sender_close(&occupied,
        ipb_bounded_now_ns() + NSEC_PER_SEC), "closed sender becomes idle");
    check(atomic_load(&f2.calls) == 1, "close path did not replay the owner");

    puts("bounded sender test passed");
    return 0;
}
