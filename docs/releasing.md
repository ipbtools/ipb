# Release process

## Current channels

The formal [v0.2.0 release](https://github.com/ipbtools/ipb/releases/tag/v0.2.0) is published
as a standard release (not draft or prerelease) and marked latest. Its tagged source commit is
`ac19b3fd4144b1b270ea1526af2cbbfcce884bfb`; main CI
passed in [run 38338717398](https://github.com/ipbtools/ipb/actions/runs/38338717398), and the
formal native build/package workflow passed in [run 38338803091](https://github.com/ipbtools/ipb/actions/runs/38338803091)
on macOS 27.0.1 / Xcode 27.0 / CoreDevice 651.19. Native host/package checks and a real
Homebrew install with installed-file hashes passed. An independent download matched its
checksum and all 14 packaged payload hashes.

The tap's stable-formula workflow passed in [run 38339077000](https://github.com/ipbtools/homebrew-ipb/actions/runs/38339077000):
it checked the public release metadata, tag/main ancestry and payload hashes, then installed
and tested the formula with Homebrew. The generated formula is byte-identical to the formula
asset in the release. [Tap PR #2](https://github.com/ipbtools/homebrew-ipb/pull/2) merged at
`c55740c31f74e35614216226879f5b58099046ee`; its CI passed in [run 38339257052](https://github.com/ipbtools/homebrew-ipb/actions/runs/38339257052).
The maintained source formula remains the
`--HEAD` template; the stable fields are generated from the verified release asset.

The prior disposable test prerelease `release-test-v0.2.0-20261012155616` and its tag were
removed after the formal release was verified. That lane's passing run remains historical
process evidence below; its deleted release URL is intentionally not linked.

For this `v0.2.0` simple validation release, the maintainer authorized publication after host,
package and Homebrew verification without a new physical-device run. The supported macOS 27 +
Xcode 27 + iOS 27+ physical gate remains open, and this release does not claim full device
acceptance. This is a current-release exception; the general future release gate below is
unchanged.

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
checklist below. The maintained source formula is the HEAD template; the tap installs the generated stable
formula from a verified published release. CI also installs the real archive through that formula
on its disposable VM, verifies the installed product hashes and runs `brew test`.
This uses a precompiled archive formula, not Homebrew's bottle format.

Sources: [runner software](https://github.com/actions/runner-images/blob/main/images/macos/xcode-27-arm64-Readme.md),
[artifact permissions and tar archives](https://github.com/actions/upload-artifact#permission-loss).

## Disposable branch Release test (historical)

The branch-test workflow passed in [run 38274014354](https://github.com/ipbtools/ipb/actions/runs/38274014354)
at source commit `e30cf71`, including draft creation, asset upload, public download/checksum,
and precompiled Homebrew install/test. Its disposable prerelease `release-test-v0.2.0-20261012155616`
and tag were removed after the formal `v0.2.0` release was verified. The historical run does
not represent stable publication or physical-device acceptance.

For an authorized disposable branch Release test, use the separate test lane:
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

The full supported physical matrix remains open. The explicit v0.2.0 publication decision
is recorded above; standard Release status does not certify physical acceptance.

## Prepare and publish the reviewed version

1. Merge the reviewed source change, verify the resulting main commit and matching VERSION,
   then push an existing tag `vX.Y.Z`. The tag-push workflow, or a manual **Release candidate and branch test** run for that tag, requires the commit to be an ancestor of main and VERSION
   to match. It never creates a tag from an arbitrary branch.
2. The job repeats native build/host checks, generates `ipb-X.Y.Z-macos27-arm64.tar.gz`, its
   SHA256, BUILD_INFO.json and the pinned `ipb.rb` stable formula, and exercises the binary
   formula with Homebrew on the CI VM. It creates/updates only a **Draft Release** using
   this repository's GITHUB_TOKEN. A published release is never overwritten.
3. For future releases, complete the supported physical-device gate against the actual
   candidate package, inspect downloaded-copy behavior, and review the draft notes and
   requirements. Publish only after these results are satisfactory. The v0.2.0 maintainer
   exception is recorded under Current channels. A green candidate job alone is not
   approval to publish. No Developer ID credential or Apple component is bundled.
4. In [ipbtools/homebrew-ipb](https://github.com/ipbtools/homebrew-ipb), dispatch **Prepare stable Homebrew formula** with the published tag.
   That tap-owned workflow checks the public release/assets and Homebrew installation,
   then pushes a candidate branch and supplies a compare link. Create/review/merge the
   formula PR from that link. The tap's default token cannot create PRs under its current
   repository policy; this flow does not change that policy or require a cross-repo PAT.
5. Install the stable formula from the merged tap and verify it on the supported host/device.
   Stable installs use `brew upgrade` through `ipb update`; existing HEAD installs retain
   their HEAD reinstall behavior and the development channel still follows main.

The release and tap workflows are now available on their merged default branches. The
formal release, Homebrew package checks and physical-device acceptance retain distinct scopes.

Sources: [GitHub release management](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository),
[Homebrew precompiled bottles](https://docs.brew.sh/Bottles),
[workflow triggers](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).
