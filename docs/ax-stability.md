# AX snapshot workload and explicit core observations

Branch: `codex/ax-stability`. Base: main `8c227a1` (v0.6.0).
The separate Duo branch was rebased onto that main; this PR contains AX work only.

## Problem and evidence

Safari simulator application snapshots can spend several seconds computing native
visibility2025 across visible/hidden windows. An external client receives error0/nil
around3s while native computation can finish later. Removing2025 produced the same
664 ordered path records/identities and other fields in0.326s in one captured state.
That graph exceeds the product's512-record limit, so this is workload evidence,
not an already demonstrated product failure-to-success case. See verification.md's
November5/6 records. Exact intermediate deadline ownership remains unknown.

Locate/wait/press/input request2025 without consuming it. Their existing target
identity, value, live state/frame and exact-hit guards must remain unchanged.
Default deep dumps, scroll and alert operations consume native visibility and keep
their current requests. Root-only3002 is rejected as a shortcut: retained samples
have truncated children and lack responder traits/value.

## Design

- Derive one core attribute list from the existing full list by excluding2025.
  Use it for locate/wait/press and for input with whole-tree3002 added. Keep the
  structural validation, action guards, timeouts, graph budgets and no-replay
  behavior unchanged. Project only requested native attributes in the parser.
- Add opt-in `ui --deep --native-profile core`; `full` remains the default and
  preserves its current output. Profile selection is valid only for deep dumps.
  Core keeps complete structure/geometry/text, omits native node.visible, and adds
  `nativeAttributeProfile:"core"`, `nativeVisibility:"not-requested"`. Extra server
  visibility is not published as requested core state. Later full-state values
  remain separately attributed under supplementalAX.
- MCP observe accepts optional `nativeProfile` with the same full/core values.
  Its adapter validates and propagates core provenance; incomplete/contradictory
  metadata or request/result profile mismatch fails before a successful observe
  can clear isolation. Existing callers keep the full profile. There is no fallback.
- This provides a cheaper explicit observation path; it does not claim to cure all
  legacy full-profile nils, oversized graphs or identity changes after scroll.

## Implementation and delivery baseline

Source baseline58e5c32 is the first complete implementation offered for acceptance;
it stays fixed across follow-up validation. Stage1 cadcefa and stage2 are accepted
by actual Opus5.5 source reviews, including the final delivery boundary review.
[PR15](https://github.com/ipbtools/ipb/pull/15) contains the implementation. Native
host, isolated package and CI/Homebrew gates pass; see verification.md for exact
revisions and artifacts. These are not supported physical HID/media acceptance.

The initial implementation used only a task-owned simulator. The user subsequently
requested a broader physical App matrix and explicitly selected12mini. That authorizes
foreground App/page setup and AX sampling on that device.13Pro belongs to the active
PocketAgent latency comparison; other devices/simulators remain excluded. No production
code, timeout, graph budget or action guard is changed for the matrix.

## Physical matrix method and scope

The before arm is main8c227a1 full; compatibility control is58e5c32 full;
the opt-in arm is58e5c32 core. The same native install and pinned Python dependencies
are used. Hashes, argv, raw receipts and private screenshots stay outside Git at
`/Users/borealin/Documents/Codex/2026-11-06/ipb-ax-app-matrix/` (0700).
Only the allocated wired12mini is operated: CoreDevice UUID
1D533177-5153-5A0C-9102-8D0A8ADDAEFB, iPhone13,1/iOS27.0/24A437,
macOS27.2/26B123, Xcode27.2/27B52, CoreDevice651.32. The concurrently allocated
13Pro is excluded. Production/tests/build source remains58e5c32.

Each App/state receives6 attempts per arm, interleaved by all six arm permutations,
with rotated first arm, fresh process inventory per attempt and fixed3s gap. Record
actual gap, previous arm and shared-host load. Pre/post screenshot, unlocked state
and stable foreground hit-PID checks bracket each cohort; between-block checks prove
unlocked state only. A visible App-main check point can replace a blank/helper centre;
queries still use the explicit main PID and unchanged root identity guard. Foreground
stability between boundary checks is inferred. No automatic action/measurement replay.
State-invalid attempts are retained separately without replacement.

Success requires rc0 plus the existing compact_observe validation of the complete
schema2 tree, device/PID/profile provenance and closed connection/tunnel. Separate
nil, semantic timeout, graph/archive limit, identity, transport and cleanup failures.
Only default locate is a same-default-path before/after experiment; explicit core
omits native visibility. Report per-state denominators, latency and count/path drift.
There is no pooled reliability rate across Apps/states or independent-trial claim.
Spacing and a new process do not prove native work has drained.

A valid target-App natural failure symmetrically selects separate30/arm confirmation,
keeping discovery separate. Opus approved two bounded revisions: uniform fast
background refusal uses three same-PID re-entries with foreground controls; the
separate PDUI diagnostic stops at6/arm because returned core trees hit the unchanged
node/depth guard. Its full timeouts are not structural findings, and that system row
is outside target-App coverage and supports no reliability estimate. Target-App
confirmation policy otherwise remains unchanged.

## Current physical findings

The first23 candidates yielded nine actual target Apps: Settings, Calculator, Safari,
App Store, Maps, PocketAgent diagnostics, LocalDevVPN dashboard, Phone and Stash
What's New. Thirteen other Apps had CoreDevice10004 before AX; Bitwarden was
FaceID/auth-gated. Those failures are retained, with no retrospective cause assigned.

The user requested12 more inventory-selected candidates: Tips, Compass, Podcasts,
TV/Videos, Games, Preview, Freeform, Watch, Fitness, Voice Memos, Health and iTunes
Store. First-use/system-helper gates are distinct from target-App measurements.
The user separately authorized this round's data-use Accept & Continue, wireless-data
WLAN & Cellular, and location Allow While Using App. Record exact one-shot receipts;
other TCC, login, purchases and profile submission remain excluded. Optional iCloud
Not Now and onboarding dismissal defer setup; they do not establish permission state.
An observed10004 now stops for fresh foreground/component/screenshot classification
before another App is launched. Setup changes never count as a code-version recovery.

Eleven additional Apps complete198 deep reads,6/6 per arm in every state, bringing
the measured total to20 Apps across35 candidates. Exact results are maintained in
the latest dated verification record. Empty/onboarding/authentication landing states count only for
that observed state, not the App's full business workflow. Preview's embedded helper
is not main-PID graph coverage. Health stops at the personal-profile form without
entering/submitting values. Notification choices are not sent. Voice Memos' old
location card disappears before the newly authorized choice could be sent; no OS
permission change is inferred. Compass' actual matching location card is explicitly
accepted once, followed by its separately authorized network card. No recording, playback, pairing, purchase or login is performed.

The default locate comparison on the original five App states passes6/6 old/new;
query medians fall from221–1033ms to111–166ms (about1.7–6.6x). A separate permission
card is also6/6 each. The additional Freeform locator, preselected uniquely from
its old-full snapshots, passes6/6 per default arm: query median1493→174ms; CLI
wall median2.583→1.201s and max12.674→2.388s; the residual wall cost is
unattributed and there is no tail guarantee. Explicit core deep snapshot medians are
lower in all11 new states; this is not a uniform wall-time or maximum-latency result.
Compass core wall median0.883s exceeds old full0.810s, and its snapshot maximum
exceeds both full arms. Default full remains the compatibility control. These successes do not demonstrate improved natural-failure success.

Settings→Calculator→read the still-running Settings explicit PID reproduces fast
nil0/18 per arm across three re-entries; same-PID foreground controls recover.
Core does not fix this background refusal. Only one App pair was tested; Apple
internal cause and its relationship to simulator roughly3s nil remain unknown.

The read-only focused-search3002 discovery has one first-arm old-full type2 timeout
(5/6 versus6/6 new-full/core). Five same-PID re-entries then pass30/30 in every arm,
with279 records and passing responder resolver. Medians are2244/2247/508ms.
The field is visually empty but native value is the fixed Search placeholder, length6.
Guarded setup may warm the path; five first-after-setup reads are not a cold-start
rate. This is not end-to-end input evidence. An earlier query-a exploration remains
separately excluded; the task's HID query was cleared without clipboard/business text.

Loaded Safari exposes64 native framework records including AXRemoteElement, not the
complete article body. One after-core implicit-selection call hits WebContent but
root identifies Safari and is correctly rejected; old/full implicit selection is
unmeasured. Explicit main PID/chrome-point reads preserve that guard. iTunes'
144–146 record/path changes are disclosed as dynamic graph drift, not deduplicated.
Largest accepted state remains279;300–512, complete Web content, other devices,
cold-first reliability and the full supported HID/media matrix remain unverified.
Phone's first core read takes2.020s versus0.194s median: no uniform tail guarantee.

The separate PDUIApp diagnostic is0/6 per arm: both full profiles type2 attribute52
time out; core reaches the unchanged node/depth guard with no partial tree emitted.
The exact size/bound is unknown (request maxDepth48, local depth32/512 records).
Do not infer that a full tree would exceed the same bound or that2025 alone causes
its timeout. Error-path cleanup is not reported by those receipts. This is neither
target-App success nor a success-rate improvement.

Actual Opus reviews cover the implementation, matrix method and bounded interpretation;
source/host/package CI, physical AX evidence and the full supported HID/media gate
remain separate proof layers. No merge or release is part of this follow-up.

## Follow-up: background Settings nil (2026-11-06)

The user explicitly requested a real acquisition-failure investigation/fix, starting
from the stable Settings→Calculator→explicit Settings PID reproduction. Current head
is28582fc; the first complete source baseline58e5c32 stays fixed. Only12mini is
operated; the13Pro thread is freshly confirmed active on its own device.

Fresh passive wire capture confirms type1 still returns the same application root
identity, while background type2/attribute52 replies in6–7ms with error0 and actual
keyed-archive resultData UID0. Full/core both fail. Ordinary type5 returns error17
and only a few synthetic/basic fields; no valid ordinary graph is recovered. A single
DTX session spanning foreground129-node snapshot→Calculator→background type5/type2
→Settings again gives the same failures and then129 nodes. A new root on that same
connection also fails in the background. clientType0/2 research controls agree.
These exclude a host decoder/selection explanation and connection retention as the
recovery, without proving the Apple process-suspension predicate was true.

Matching-product24A437 APT maps underlying signed status-25215 to error17. AXRuntime
returns that status when the required AX server port is unavailable; a suspended-PID
gate and normal lookup failure can both produce no port. The requesting-client override
and allows-suspended-server byte are separate in the inspected code. No supported
remote setter or successful original-position background-read path is established.

Next decision is user-owned: whether an explicit activation recovery may bring the
target App to the foreground. Existing ui stays read-only, and activation must not be
reported as background-read success. The proposed separate activate command must
preserve the existing process; launch currently terminates it. No new production
change is made pending this behavior choice and Opus's evidence discussion.

Detailed raw archives, probes and sanitized findings remain outside Git under
`/Users/borealin/Documents/Codex/2026-11-06/ipb-ax-background-nil/` (0700).
