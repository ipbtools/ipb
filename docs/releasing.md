# Release process

## Current channels

PR CI is implemented in [.github/workflows/ci.yml](../.github/workflows/ci.yml).
It runs on pull requests to main, pushes to main and manual dispatch. Native build and
host tests use GitHub's ARM64 `xcode-27` runner with Xcode 27.0 selected explicitly.
The first cloud build and final downloaded artifact are pending validation.

No tag or GitHub Release has been published. VERSION remains `0.2.0`; Homebrew HEAD
still builds `main` from source. CI artifacts are development packages, not releases.

## PR test packages

The job checks the OS, architecture, selected Xcode and required Apple frameworks, builds
all native targets, then runs `make check-host`. This includes existing AX, CLI/update,
smoke-assertion, bounded-sender, display, device-control, input-report and mirror-keyboard
fixtures. These tests use host mocks; no physical device or real clipboard is accessed.

`scripts/package_test_build.py` stages the existing `make install` layout and adds the MIT
license, build metadata and trial instructions. Only ipb-owned files are included. The
package records the actual checkout commit (a PR merge commit on pull_request), PR head,
OS/Xcode/CoreDevice versions and file hashes. Install-time signing finishes before hashing.
CI checks ARM64 slices, signatures, the exact file list, extraction and host startup of
all three helpers. It then uploads the tarball, SHA256, BUILD_INFO.json and TEST_PACKAGE.md
as an Actions artifact retained for 14 days.

Download from a successful run's **Artifacts** section. Unzip the artifact, verify and
extract the tarball, then run the extracted CLI by its full path:

```sh
shasum -a 256 -c *.sha256
tar -xzf ipb-*-macos27-arm64.tar.gz
./ipb-<version>-ci.<commit>-macos27-arm64/bin/ipb version
./ipb-<version>-ci.<commit>-macos27-arm64/bin/ipb help
```

Keep bin/libexec/share together. The optional AX Python dependencies remain a separate
host setup. Existing Apple runtime components are still required; no Apple framework or
DDI is redistributed. Signatures are ad-hoc, not Developer ID/notarized. Downloaded-copy
quarantine and physical HID/media/AX behavior need separate supported-host verification.
Fetch another CI artifact to update a trial copy; `ipb update` does not upgrade these copies.

A green PR job does not close the full supported physical-device gate or publish a release.
Release/Homebrew automation follows only after the cloud build and downloaded package have
been verified; stable publication still follows the acceptance checklist below.

Sources: [runner software](https://github.com/actions/runner-images/blob/main/images/macos/xcode-27-arm64-Readme.md),
[artifact permissions and tar archives](https://github.com/actions/upload-artifact#permission-loss).

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

PR automation now provides the native ARM64 build and test artifact described above.
The workflow has contents-read permission, no publishing credentials, pinned official actions,
a 20-minute job timeout and cancellation of superseded PR runs. It does not merge, tag, write
a Release or update the tap. Once the first build/package validation passes, add the tag/manual
release and bottle flows without presenting host CI as physical-device acceptance.

See [workflow triggers](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).
