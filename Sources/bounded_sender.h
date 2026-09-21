#ifndef IPB_BOUNDED_SENDER_H
#define IPB_BOUNDED_SENDER_H

#include <dispatch/dispatch.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdint.h>
#include <time.h>

// A sender owns one uncancellable synchronous call at a time.  The owner is
// retained after the caller's deadline until the real call returns, so a
// timed-out call cannot race the next call on the same RemoteXPC connection.
enum { IPB_BOUNDED_TIMEOUT = -62, IPB_BOUNDED_CLOSED = -63 };

typedef struct {
    pthread_mutex_t lock;
    pthread_cond_t idle;
    bool inFlight;
    bool closing;
    dispatch_group_t active;
} ipb_bounded_sender;

static inline uint64_t ipb_bounded_now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}

static inline dispatch_time_t ipb_bounded_dispatch_deadline(uint64_t deadline) {
    uint64_t now = ipb_bounded_now_ns();
    if (deadline <= now) return DISPATCH_TIME_NOW;
    uint64_t remaining = deadline - now;
    return dispatch_time(DISPATCH_TIME_NOW,
                         remaining > INT64_MAX ? INT64_MAX : (int64_t)remaining);
}

static inline struct timespec ipb_bounded_cond_remaining(uint64_t deadline) {
    struct timespec ts;
    uint64_t now = ipb_bounded_now_ns();
    uint64_t add = deadline > now ? deadline - now : 0;
    ts.tv_sec = (time_t)(add / 1000000000ull);
    ts.tv_nsec = (long)(add % 1000000000ull);
    return ts;
}

static inline void ipb_bounded_sender_init(ipb_bounded_sender *sender) {
    pthread_mutex_init(&sender->lock, NULL);
    pthread_cond_init(&sender->idle, NULL);
    sender->inFlight = false;
    sender->closing = false;
    sender->active = dispatch_group_create();
}

// Returns true only when no call remains in flight at the deadline.  Once
// closing is set, admission cannot race this wait or start another call.
static inline bool ipb_bounded_sender_close(ipb_bounded_sender *sender,
                                            uint64_t deadline) {
    pthread_mutex_lock(&sender->lock);
    sender->closing = true;
    pthread_cond_broadcast(&sender->idle);
    pthread_mutex_unlock(&sender->lock);
    bool drained = dispatch_group_wait(sender->active,
                                       ipb_bounded_dispatch_deadline(deadline)) == 0;
    pthread_mutex_lock(&sender->lock);
    bool idle = !sender->inFlight;
    pthread_mutex_unlock(&sender->lock);
    return drained && idle;
}

// `started` distinguishes a deadline spent waiting for ownership from a
// deadline that abandoned a call already inside Apple's synchronous sender.
static inline int ipb_bounded_call(ipb_bounded_sender *sender,
                                   uint64_t deadline,
                                   int (^call)(void),
                                   bool *started) {
    if (started) *started = false;
    pthread_mutex_lock(&sender->lock);
    while (sender->inFlight && !sender->closing && ipb_bounded_now_ns() < deadline) {
        struct timespec remaining = ipb_bounded_cond_remaining(deadline);
        int waitResult = pthread_cond_timedwait_relative_np(&sender->idle, &sender->lock, &remaining);
        if (waitResult != 0) break;
    }
    if (sender->closing) {
        pthread_mutex_unlock(&sender->lock);
        return IPB_BOUNDED_CLOSED;
    }
    if (sender->inFlight || ipb_bounded_now_ns() >= deadline) {
        pthread_mutex_unlock(&sender->lock);
        return IPB_BOUNDED_TIMEOUT;
    }
    sender->inFlight = true;
    dispatch_group_enter(sender->active);
    if (started) *started = true;
    pthread_mutex_unlock(&sender->lock);

    __block int result = 0;
    dispatch_semaphore_t done = dispatch_semaphore_create(0);
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{
        result = call();
        pthread_mutex_lock(&sender->lock);
        sender->inFlight = false;
        pthread_cond_broadcast(&sender->idle);
        pthread_mutex_unlock(&sender->lock);
        dispatch_group_leave(sender->active);
        dispatch_semaphore_signal(done);
    });
    if (dispatch_semaphore_wait(done, ipb_bounded_dispatch_deadline(deadline))) {
        // `result` belongs to the worker from this point onward.  The owner
        // remains in sender->active until that worker really returns.
        return IPB_BOUNDED_TIMEOUT;
    }
    return result;
}

#endif
