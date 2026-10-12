# Release process

## Current channels

As checked on 2026-10-12, neither `ipbtools/ipb` nor `ipbtools/homebrew-ipb` has a
GitHub Actions workflow, tag or GitHub Release. The source VERSION is `0.2.0`;
Homebrew offers HEAD from `main`. The alignment PR is a development change, not a release.
This document defines a manual checklist; no publishing workflow is implemented here.

## Before a release

1. Review the exact candidate commit and its dependencies. Preserve the recorded Apple
   framework/DDI/iOS seed and each feature's known limits.
2. Build and install with macOS 27 + Xcode 27 and a physical iOS 27+ device. Run the full
   `scripts/smoke_matrix.sh` gate, including appropriate interactive steps and `SMOKE_AX=1`
   for a version shipping UI reads. Inspect screenshots and actual state changes.
3. Record host/device/build, confirmed issues and the verification boundary in
   [verification.md](verification.md). Keep success-only raw evidence and artifact hashes
   outside Git. AX-only or supplementary macOS26 results do not close the release gate.
4. Update VERSION, user guides and release notes for the reviewed version. Record an exact
   candidate SHA; complete review before selecting the commit to tag.

The alignment branch's full supported matrix is still open. A Draft PR can be reviewed
while that remains open; a release must not be described as validated until it passes.

## Publish the reviewed version

1. Merge the reviewed change, verify the resulting main commit, and tag that exact commit
   with the matching `v<version>`. Do not infer release readiness from VERSION alone.
2. Prepare GitHub release notes naming scope, requirements, validated seed and unresolved
   limits. Start as a draft; publish only after the checklist is complete.
3. Source archives are sufficient for the current source-build distribution. If binaries
   are added later, validate their install layout, checksums, runtime dependencies and
   support scope before advertising them. Do not bundle Apple components.
4. Keep the published tag and notes tied to the tested source. Homebrew installation is a
   separate validation step, not proof that the GitHub release is usable on a device.

See [GitHub release management](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository).

## Homebrew and future automation

The coordinated repositories are `ipbtools/ipb` and `ipbtools/homebrew-ipb`. After tagging
and validating a source release, add a stable formula source pinned to that tag and its
archive SHA256, synchronize the intended formula into the tap, then install/test that
version on the supported host/device. Retain HEAD separately for main development.
Neither formula nor tap is switched to a stable release by this PR.

Recommended first automation is a PR workflow for syntax, archive/CLI host contracts and
report-size checks. A native build job needs a confirmed macOS27/Xcode27 environment.
Physical HID/media/UI validation remains explicit device evidence; a green host job must
not represent the full device gate. Add tag/manual release automation only after these
roles and the actual runner environment are established. Do not assume an existing
self-hosted runner, signing identity or release secret.

See [workflow triggers](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).
