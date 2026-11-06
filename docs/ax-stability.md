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

## Expanded physical App matrix (2026-11-06)

Purpose: determine whether omitting2025 improves real accepted-snapshot success,
not merely query duration. This is a follow-up validation of the58e5c32 baseline;
production code, timeouts, graph budgets and action guards stay fixed.

Device: explicit12mini CoreDevice UUID1D533177-5153-5A0C-9102-8D0A8ADDAEFB,
iPhone13,1/iOS27.0/24A437, wired and unlocked, macOS27.2/26B123,
Xcode27.2/27B52. The user confirmed this allocation. Initial screen is Home.
13Pro belongs to the live PocketAgent latency comparison; other devices/sims are excluded.

Predeclared broad phase:18 inventory-selected apps, each in its observed landing state:
Settings, Calculator, Safari, AppStore, Files, Calendar, Clock, Notes, Reminders,
Maps, Weather, Books, Shortcuts, Music, Stocks, Translate, Bitwarden and PocketAgent.
These cover system lists/grids, WebKit, dynamic/canvas views, forms and third-party
login/SwiftUI surfaces. App names alone do not prove framework internals; record actual
onboarding/permission/empty/content state from captures. A launch/setup refusal is a
matrix cell result, not silently substituted by another App or counted as a native nil.

Three arms use real isolated CLI installs: main8c227a1 full (before),58e5c32 full
(compatibility control),58e5c32 explicit core (opt-in after). Each App/state gets6
attempts per arm, ordered by the six permutations of these arms (18 total), with a
fixed3s inter-attempt gap and fresh one-shot USB/DTX connection. Rotate the first
permutation by App ordinal; record ordinal, previous arm and actual process-exit gap.
Confirm PID via fresh process inventory before each attempt. Use screenshots, lock
state and centre hit-PID checks before/after each cell, plus non-AX lock state between
permutation blocks. A failed state check or changed PID marks all attempts since the
last good foreground check state-invalid, retained separately without replacement or
inclusion in within-state success denominators. Stop on lock. Spacing is not a
native-drain guarantee; report carryover strata and first-after-setup separately. Do not retry failed measurements.
Store stdout/stderr, exit/status, wall time and query/snapshot timing outside Git.

Accepted success requires rc0 plus a validated complete schema2 tree, matching device
and explicit PID, correct profile metadata and closed connection/tunnel. Count native
nil, type2 semantic timeout, other semantic/global timeout, graph/archive budget,
identity/selection/transport and cleanup failures separately. Report per-App/state
numerators/denominators and latency; success-only timing never hides failed attempts.
No aggregate across heterogeneous Apps is a universal reliability estimate.

Then add observed reachable search/keyboard, secondary-page, Web-content and overlay
states using reversible navigation without sending messages or editing user content.
A natural failure in any arm symmetrically selects a cell for separate confirmation;
selection-phase observations are never pooled into its rates. After the interim data,
Opus recommended an explicit sampling revision: uniform fast background refusal gets
three same-PID state re-entries with foreground positive controls, rather than
redundant30/arm. Valid foreground failures or arm/re-entry discordance retain30/arm.
The observed foreground search timeout selected five re-entries of6/arm (30/arm),
with rotated first arms. If a state cannot be recreated, report that explicitly.
Read-only old/new locate samples use actual unique observed selectors on representative
states. Whole-tree3002 comparison requires a separately labelled read-only physical
experiment; product input is not a read-only snapshot command and is not auto-replayed.

Opus reviews the matrix before the broad run and the actual findings afterward. Reuse
the current tested install; no new product test infrastructure or device app is added.
Use the existing compact_observe validator uniformly for all successful observations.
Old full versus new full is a compatibility/noise control, old full versus opt-in core
is a requested-attribute tradeoff, and only old/new locate is the same-default-path
before/after comparison. Report graph-count/path drift on adjacent successful samples.
Activate with devicectl process launch --activate without --terminate-existing.
Record shared-host load; the13Pro task can affect host timing even on a different phone.
Scripts and detailed personal AX/screenshot evidence stay outside Git; this plan and
verification.md retain only condensed, verified findings and artefact references.

## Physical findings and remaining coverage

The user requested another expansion after the completed23-candidate run. A fresh
12mini all-App inventory still contains76 entries; the default developer-only list
contains four and is not the all-App inventory. The next12 candidates are Tips,
Compass, Podcasts, TV, Games, Preview, Freeform, Watch, Fitness, Voice Memos, Health
and iTunes Store. They add landing-page coverage without replacing any prior refusal.
Use the same6/arm controls, guards and failure denominators; do not start recording,
playback, purchases, authentication or answer new privacy choices. This follow-up
remains pinned to the before/after manifests above and excludes13Pro. Results pending.

The permission blocker is resolved. The user authorized Allow, but the guarded action
found no visible alert and sent nothing; a screenshot then confirmed the card had
already disappeared. This does not prove that this task changed the OS permission.
LocalDevVPN's dashboard is now measured separately from the permission overlay.

Old/new default locate comparisons on Settings, Calculator, Safari tab overview,
Maps and PocketAgent diagnostics, plus the permission card, each pass6/6 per arm.
Query medians fall from221–1033ms to111–166ms on the five App states. The explicit
core deep comparisons likewise show lower cost; default full remains the compatibility
control. These successful samples do not establish improved natural-failure success.
Only locate has a physical before/after comparison here; wait, press and end-to-end
input share the request change but were not compared, and no product `ui input` was sent.

A reproducible nil path now exists independently of the permission card: activate
Settings, activate Calculator, then query the still-running Settings PID explicitly.
Three same-PID re-entries produce0/18 accepted reads in each arm, all fast native
nil. Old-full/new-core foreground controls before and after every entry pass with the
same Settings PID. Core does not recover this background refusal; the Apple internal
cause and relationship to the simulator's roughly3s nil remain unproven.
Only one target/occluder pair was tested. This path requires an explicit PID; it is a
deterministic refusal in this observed state, not a foreground reliability rate.

The read-only focused-search3002 workload initially gives old-full5/6 (one first-arm
type2 timeout), new-full6/6 and core6/6. Five same-PID re-entries of visually empty
search are30/30 in every arm, all279 records, with the real responder resolver passing
30/30 per arm. Snapshot medians are2244/2247/508ms (old/full/core). Thus the isolated
initial timeout is not attributable to a code version: new-full sends the same request.
Setup uses guarded press and can warm the app; there are only five first-after-setup
reads, so a cold-first timeout rate is not excluded. No success-rate difference is
established. Native value is the fixed `Search` placeholder (length6), not an empty
string; screenshots show no query. No product input or clipboard call is represented
by this experiment. Placeholder and resolver passes are not end-to-end input evidence.
One own local HID query `a` was cleared; its
accidentally retained setup cohort is labelled separately and excluded from confirmation.

The loaded public Swift Concurrency page exposes64 native Safari records with an
AXRemoteElement, not the article's complete Web content. Implicit selection hits the
WebContent PID but the snapshot root identifies Safari. This is one actual after-core
`ui --deep --native-profile core --json` call without `--pid`, rejected by the root
guard; old/full implicit selection was not measured. Explicit Safari PID/chrome-point
sampling preserves the strict guard. Settings Apps (129 records) is a completed cell;
General (102) is discovery only;300–512 coverage is still missing.

All23 predeclared candidates were attempted: nine have measured App states (six of
the original18, three of the additional five). Third-party coverage is PocketAgent
diagnostics, LocalDevVPN dashboard and Stash3.6 What's New, not their entire flows.
Thirteen Apps fail activation with CoreDevice10004 and zero AX attempts; the cause
is unknown. Eleven failures precede the first permission-card capture, while Contacts/Photos fail
after it disappeared. Bitwarden remains auth-gated; no authentication is bypassed.
The device is restored to Home with screenshot/hit-PID evidence. The supported
HID/media gate is separate;300–512 and full Web content remain unverified.

Raw plans, isolated before/after installs and private AX/screenshot data stay outside
Git at `/Users/borealin/Documents/Codex/2026-11-06/ipb-ax-app-matrix/` (directory0700).
See verification.md for completed cells, separate denominators and dated evidence.
