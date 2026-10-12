# Interactive mirror

See [installation channels](../README.md#installation-channels) for the source branch that
contains these keyboard/clipboard additions.

## Start and controls

One window displays the device screen and accepts mouse control, without DeviceHub, injection
into any Apple process, or any special entitlement.

```sh
bin/ipb mirror [--seconds S] [--csv PATH]
bin/ipb mirror --help
```

Click, hold and drag directly on the screen. Wheel/trackpad events use the captured
scroll path (`0x501`, iOS 27 only), but physical delta/acceleration/momentum parity remains
unverified; some unsupported event phases are explicitly refused. Mouse drag-scroll is
verified. The shortcuts match DeviceHub:

| Shortcut | Action |
| --- | --- |
| ⇧⌘H | Home |
| ⌃⇧⌘H | App Switcher |
| ⌘L | Lock, or wake a dark screen — the same side-button press |
| ⌘K / `123` button | Show or hide the numeric keypad |
| ⌘A / ⌘C / ⌘X / ⌘V | Select all / copy to Mac / cut to Mac / paste Mac text |
| ⌃Space | Next Mac input method (also available in Edit) |
| ⌘W / ⌘Q | Close the mirror / quit |
| ⌘↑ / ⌘↓ | Volume up / down |
| ⇧⌘S | Save the latest decoded frame as a PNG in `~/Pictures` |
| ⌘← / ⌘→ | Rotate device left / right, then update the preview and input mapping |
| ⌘0 | Zoom to fit |
| ⌘1 | Actual size (falls back to fit if it exceeds the available screen) |

## Keyboard, input methods and text clipboard

The `123` button in the window title bar opens digits **0–9**, **Backspace** and **Return**
for focused numeric input. This can help with hidden streamed keypads if iOS accepts keyboard
input on that page. It sends keyboard keys; its buttons do not
represent reconstructed iPhone touch positions. While open, Mac number keys, Backspace and
Return are forwarded too. Close it with `123`, `⌘K`, or its close button. Keyboard usages are
omitted from event CSV and diagnostics. Password-sheet and lockscreen acceptance still require
device validation; a visible panel does not prove iOS will accept its keyboard events.

Click the phone view to focus the window, then type normally. Letters, numbers, punctuation,
navigation/function keys and modifier combinations use the discovered keyboard HID service.
Key down/up preserve the full held-key set; ordinary key repeat is forwarded. Existing mirror
shortcuts above remain local/reserved and do not repeat. Focus loss and close release held keys.
Physical key input follows the iPhone's keyboard layout/input method.

Choose an enabled Mac input method in **Edit → Input Method**, or use **Control-Space** / Edit →
Next Input Method. System-wide shortcuts can be intercepted by macOS; the menu remains available.
Mac input methods keep composition/candidates on the Mac and send committed text by UTF-8
clipboard paste. The composing text appears at the bottom of the mirror. Emoji and other Unicode
commits use the same path. This does not provide a local copy of the phone's editable document
for reconversion or replacement of previously committed ranges.

The Edit menu also exposes text Cut, Copy, Paste and Select All. Copy/Cut wait for a changed
iPhone clipboard before retrieving text; if nothing is selected, the mirror stays open. A newer
Mac clipboard is preserved. Paste replaces the iPhone text clipboard. Transfers are ordered with
keyboard input, capped at 2 MiB of UTF-8, and never retried after a submitted chord. Images/rich
text and continuous clipboard synchronization are not implemented. iOS may ask the focused app
to allow paste from `dtpasteboardd`; handle that prompt normally. Sender success does not prove
the app inserted text. Secure-field/lockscreen acceptance remains unverified.

## Session, display and geometry

**Requires a GUI login session**, just like `ipb stream`: in-process decoding needs
`CVDisplayLink`. It works with SIP enabled and needs no entitlement; plain ssh is unsupported.

While a mirror session runs, `ipb` holds a resident `devicectl notification observe`
subscription to keep the CoreDevice tunnel lease alive. HID traffic alone does not renew the
lease. This proxy keepalive is the accepted workaround; see `docs/verification.md`.

A static display can stop publishing frames and resume when the screen changes. After the first
valid frame, silence alone does not close the mirror or stream. Explicit stream/connection errors
still fail; collection and shutdown remain bounded. A silent transport failure without an error
callback cannot currently be distinguished from an idle display until new content arrives.

The default run lasts 300 seconds; `--seconds` accepts values greater than 0 and at most 3600.
The existing 8192-input-event cap also ends the run. Statistics retain their existing fields and
go to **stderr**. No CSV is produced by default; `--csv PATH` writes the event header and rows to
that file (overwriting it; its parent directory must exist). CSV open/write failures exit 8.
`IPB_MIRROR_HELPER` overrides the helper; otherwise `libexec/ipb-mirror` is preferred over
`build/ipb-mirror`. The source is `Sources/mirror.m`. The helper's existing `--service-id ID`
option is also passed through for a known touchscreen ID; descriptor discovery remains the default.

The mirror reads the live primary display before opening and refreshes it on a serial background
queue once per second, with at most one query in flight. Each query has a 5-second Apple timeout
and a 6-second host bound; close cancels the active child. Query/geometry errors fail the session
explicitly. Metadata changes drain old input before changing the crop or transform. External
orientation changes can take a refresh interval to appear; there is no atomic frame/metadata epoch
in this version. Device direction controls the preview; touch coordinates map back to native axes,
while pointer coordinates stay in preview space. Saved PNGs retain the cropped native orientation.

Decoded frames carry encoder padding for 16-pixel alignment (on the iPhone 13 Pro, 1184×2576
against a 1170×2532 screen). The mirror crops it rather than compensating for it, so the window's
aspect ratio matches the phone's and a click lands where it is drawn. Live primary `nativeSize`
is preferred, followed by the existing model table, Xcode lookup and content detector; see the 2026-09-09 record in
[verification.md](verification.md).

## Limits and exit codes

Not implemented: Siri (⇧⌥⌘H), screen recording (⇧⌘R), Action Button, and Camera Control. A Device Hub Siri invocation has now been captured (code `0xcf`, states 0/1), but produced no visible
Siri UI on the tested phone; its full typed page encoding and functional behavior still need validation.
The other hardware buttons lack usage-code evidence; recording lacks capture/recording behavior evidence. The local 13 Pro also lacks Action Button and Camera Control hardware.

Exit codes: 0 success, **1 input/connection failure**, 2 usage/local setup, 3 service socket or
descriptor discovery failure, 4 tunnel/interface/bind failure, 5 negotiation failure,
6 media/decoder/display failure, 7 no initial media frame within 12 seconds, **8 local I/O failure**
(including CSV output, descriptor capture, or screenshot shutdown drain), 9 setup/run/shutdown
watchdog or input-drain timeout, 130 SIGINT, 143 SIGTERM. Unlike `stream`, mirror has input
failure code 1 and no `--count` contract. Sent input is never automatically replayed.

Supported `service-id` roles:

```sh
bin/ipb service-id touchscreen
bin/ipb service-id gesture
bin/ipb service-id keyboard
bin/ipb service-id buttons
bin/ipb service-id avp
```
