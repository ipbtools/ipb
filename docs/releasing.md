# Release process

## Current channels

PR CI is implemented in [.github/workflows/ci.yml](../.github/workflows/ci.yml).
It runs on pull requests to main, pushes to main and manual dispatch. Native build and
host tests use GitHub's ARM64 `xcode-27` runner with Xcode 27.0 selected explicitly.
Native build, host/package checks and actual precompiled Homebrew install/test passed:
[run 38244949806](https://github.com/ipbtools/ipb/actions/runs/38244949806), macOS 27.0.1 /
Xcode 27.0 / CoreDevice 651.19. The first verified archive from run38242939599 starts on Mac-M2 macOS 27.2 / CoreDevice
642.15. These are host/package results, not physical device acceptance.

No stable version tag or stable GitHub Release has been published. The disposable branch test below has been published as a prerelease. VERSION remains `0.2.0`; Homebrew HEAD
still builds `main` from source. CI artifacts are development packages, not releases.

## PR test packages

The job checks the OS, architecture, selected Xcode and required Apple frameworks, builds
all native targets, then runs `make check-host`. This includes existing AX, CLI/update,
smoke-assertion, bounded-sender, display, device-control, input-report and mirror-keyboard
fixtures. These tests use host mocks; no physical device or real clipboard is accessed.

`scripts/package_test_build.py` stages the existing `make install` layout and adds the MIT
license, build metadata and trial instructions. Only ipb-owned files are included. The
package records the actual checkout commit (a PR merge commit on pull_request), PR head,
OS/Xcode/CoreDevice versions and file hashes (`schemaVersion: 1`; OS fields are structured). Install-time signing finishes before hashing.
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
The first cloud build and downloaded package passed host verification. Follow-up automation
prepares Draft Releases and a Homebrew stable formula while preserving the acceptance
checklist below. The source formula remains HEAD-only until a verified published release
provides a generated stable formula. CI also installs the real archive through that formula
on its disposable VM, verifies the installed product hashes and runs `brew test`.
This uses a precompiled archive formula, not Homebrew's bottle format.

Sources: [runner software](https://github.com/actions/runner-images/blob/main/images/macos/xcode-27-arm64-Readme.md),
[artifact permissions and tar archives](https://github.com/actions/upload-artifact#permission-loss).

## Disposable branch Release test

Actual end-to-end test passes in [run38274014354](https://github.com/ipbtools/ipb/actions/runs/38274014354)
at source commit e30cf71. The [published test Release](https://github.com/ipbtools/ipb/releases/tag/release-test-v0.2.0-20261012155616)
contains five uploaded assets and remains deletable (`immutable=false`). The job creates the
draft and uploads with its actual Actions GITHUB_TOKEN, publishes the prerelease, downloads
its public archive/sidecar and passes Homebrew install/test plus installed-file hashes.
An independent local download also matches every payload hash. No stable publication or
physical device acceptance is implied.

The user explicitly authorizes a branch-built release test that can be deleted afterwards.
Push a tag named `release-test-vX.Y.Z-YYYYMMDDHHMMSS` at the selected branch commit, with
X.Y.Z matching VERSION and the timestamp in UTC. The same release workflow builds/tests
and uploads real GitHub Release assets using its own GITHUB_TOKEN. This lane records
`kind: branch-release-test`, creates a draft, attaches its assets, then publishes only that
release as a prerelease with `latest=false`. It downloads the public archive/sidecar, checks
SHA256 and runs an actual precompiled Homebrew installation from the public release URL.

This test lane does not merge main, alter VERSION, change the stable tap or certify the
physical device gate. Formal `vX.Y.Z` tags still require main ancestry and stay draft-only.
The stable tap validator rejects the test tag and prerelease. To clean up after testing,
delete the test Release first and then its tag (for example `gh release delete <test-tag>
--cleanup-tag --yes`). Keep the test URL, source commit and verified scope in the local
handoff and condensed verification record.

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

## Prepare and publish the reviewed version

1. Merge the reviewed source change, verify the resulting main commit and matching VERSION,
   then push an existing tag `vX.Y.Z`. The tag-push workflow, or a manual **Draft release
   candidate** run for that tag, requires the commit to be an ancestor of main and VERSION
   to match. It never creates a tag from an arbitrary branch.
2. The job repeats native build/host checks, generates `ipb-X.Y.Z-macos27-arm64.tar.gz`, its
   SHA256, BUILD_INFO.json and the pinned `ipb.rb` stable formula, and exercises the binary
   formula with Homebrew on the CI VM. It creates/updates only a **Draft Release** using
   this repository's GITHUB_TOKEN. A published release is never overwritten.
3. Complete the supported physical-device gate against the actual candidate package,
   inspect downloaded-copy behavior, and review the draft notes/requirements. Publish
   manually only after these results are satisfactory. A green candidate job alone is
   not approval to publish. No Developer ID credential or Apple component is bundled.
4. In [ipbtools/homebrew-ipb](https://github.com/ipbtools/homebrew-ipb/pull/1), dispatch **Prepare stable Homebrew formula** with the published tag.
   That tap-owned workflow checks the public release/assets and Homebrew installation,
   then pushes a candidate branch and supplies a compare link. Create/review/merge the
   formula PR from that link. The tap's default token cannot create PRs under its current
   repository policy; this flow does not change that policy or require a cross-repo PAT.
5. Install the stable formula from the merged tap and verify it on the supported host/device.
   Stable installs use `brew upgrade` through `ipb update`; existing HEAD installs retain
   their HEAD reinstall behavior and the development channel still follows main.

No tag, draft or published release is created by adding these workflows to the PR. They
become available after review/merge; no stable tap target changes until the separate formula
PR is merged. Native host/package, download quarantine and physical-device checks retain
their distinct scopes.

Sources: [GitHub release management](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository),
[Homebrew precompiled bottles](https://docs.brew.sh/Bottles),
[workflow triggers](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).
