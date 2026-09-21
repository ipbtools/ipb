# operator — synthetic input for driving Device Hub's own window

`click.m` posts real `CGEvent` mouse events at screen coordinates, so an agent
can operate Apple's Device Hub the way a person does. It exists because
capturing Device Hub's own traffic requires somebody clicking inside its
mirrored screen, and the previous capture harness was built around a human
pressing ENTER.

```sh
clang -fobjc-arc -framework ApplicationServices -framework CoreGraphics \
      -framework Foundation -o click click.m

IPB_CLICK_EXPECT="Device Hub" ./click move <x> <y>
IPB_CLICK_EXPECT="Device Hub" ./click tap  <x> <y>
IPB_CLICK_EXPECT="Device Hub" ./click hold <x> <y> <seconds>
```

`hold` exists because System Events' `click at` cannot express a press-and-hold,
which is the only way to reach the home-screen "Remove App" menu — the route to
a reproducible system alert.

## The guard, and why it is not optional

**The Accessibility API tells you where a window logically sits. It is not
evidence that anything is drawn there.**

On 2026-09-21 `System Events` reported Device Hub's window at `(530,121)
1100×800`, consistently, before and after a menu click. Every coordinate derived
from that frame looked correct. What was actually rendered at those screen
coordinates was a full-screen remote-desktop client on the active Space, with
Device Hub sitting on a different Space. A click computed from AX geometry would
have gone into the remote machine — not a voided trial, but real input into an
unrelated session.

So with `IPB_CLICK_EXPECT` set, `click` asks `CGWindowListCopyWindowInfo` for the
on-screen list in **front-to-back order** — the one thing AX cannot report — finds
the frontmost `layer == 0` window containing the target point, and refuses to
emit a single event unless its owner matches. It exits 4 and names what it found
instead.

Two things this caught immediately:

- The window owner is **`Device Hub`**, with a space — not the process name
  `DeviceHub`. Any naive comparison silently mismatches forever.
- It refuses while occluded, which is how the Space problem was proven rather
  than guessed.

`click` also refuses a coordinate that is not on any active display, for the same
reason: an off-screen click is a silent no-op that scores as a performed action.

## Testing this tool

**Use `move`, never `tap`.** A `tap` used to test the guard once ran against a
stale binary after a failed compile and posted a real click into whatever was
in front. `move` exercises the identical guard path and posts no button event.
