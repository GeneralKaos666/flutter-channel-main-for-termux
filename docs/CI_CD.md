# CI/CD and Device Lab

This repository uses GitHub Actions for both lightweight validation and the full Flutter Engine build:

1. **GitHub-hosted workflows** for fast, free, public-repository validation **and** the full `.deb` build on `ubuntu-latest`.
2. **Self-hosted workflows** as fallbacks for the expensive build and for Android tablet smoke tests.

Keep pull requests cheap and safe, and keep release builds reproducible.

## GitHub Actions cost and limits

This is a public open-source repository, so standard GitHub-hosted runner
minutes are free for the lightweight `CI`/`Release check` workflows **and** the
full `Build` workflow. The self-hosted build/device fallbacks also do not
consume GitHub-hosted runner minutes.

Limits still apply:

- GitHub still enforces workflow, queue, API, concurrency, cache, and artifact
  limits. For example, GitHub-hosted jobs have a 6-hour execution limit, and
  self-hosted jobs have a 5-day execution limit.
- The full `Build` workflow is a multi-hour, tens-of-GB job; on the 4-vCPU / 14
  GB standard runner it can approach or exceed the 6-hour cap. If it times
  out, switch `runs-on` to a larger (paid) runner, or use the self-hosted
  `Build deb (self-hosted)` fallback.
- Keep artifacts and caches small and short-lived. Put large `.deb`
  release payloads in GitHub Releases.
- Your WSL/Windows machine, disk space, tablet availability, and network
  limit self-hosted runner capacity.

References:

- [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [GitHub Actions limits](https://docs.github.com/en/actions/reference/limits)

## Workflow map

| Workflow | File | Runner | Trigger | Purpose |
|----------|------|--------|---------|---------|
| CI | `.github/workflows/ci.yml` | `ubuntu-latest` | PR, push to `main`, manual | Python/shell/PowerShell syntax, package/docs/workflow sanity, whitespace checks |
| Build | `.github/workflows/build.yml` | `ubuntu-latest` | push of fresh pins (event-driven, gated) + scheduled daily fallback + `workflow_dispatch` | Full `build.py` pipeline on GitHub-hosted runner, `.deb` packaging, stable release publish |
| Build deb (self-hosted) | `.github/workflows/build-deb.yml` | self-hosted Linux/WSL | manual | Full `build.py` pipeline, `.deb` packaging, optional release publishing (fallback) |
| Device smoke | `.github/workflows/device-smoke.yml` | self-hosted Windows + ADB tablet | manual | Install deb in Termux, run `post_install.sh`, `flutter doctor`, create/build APK/Linux smoke |
| Release check | `.github/workflows/release-check.yml` | `ubuntu-latest` | release publish/edit, manual | Verify release asset name, size, and SHA256 digest |

You build with the modernized `build.yml` GitHub-hosted path: it replaced the legacy `newkdev/setup-depot-tools@v1.0.1` dependency (unmaintained) with an inline `depot_tools` clone, and reads NDK detection from GitHub-hosted runner env (`ANDROID_NDK` / `ANDROID_NDK_LATEST_HOME` / `ANDROID_NDK_HOME`), which the ubuntu images do set. **Build (GitHub-hosted)** is the primary build path, and Build deb (self-hosted) remains as a fallback.

## Why the split exists

You run the full build on standard GitHub-hosted runners (free for public repositories). This build differs from a normal CI job:

- `gclient sync` downloads tens of GB.
- Flutter Engine builds can take hours (multi-hour on the 4-vCPU runner).
- The build needs an Android NDK (hosted images include one; the env vars
  `ANDROID_NDK` / `ANDROID_NDK_LATEST_HOME` / `ANDROID_NDK_HOME` point at it).
  You record `build.toml [ndk] version` (r29) in packaging metadata; self-hosted
  installs pin it at `/opt/android-ndk-r29`.
- You need an attached Android/Termux tablet for real release confidence.

Therefore:

- **PR CI must stay lightweight** and never touch self-hosted device hardware.
- **The full build is the `ubuntu-latest` `Build` workflow**, push-triggered
  on fresh pins (gated, builds only if anything new) plus daily scheduled
  fallback plus manual dispatch.
- **Device smoke is a manual self-hosted gate** run by a maintainer.

## PR / push CI

`ci.yml` runs on every PR and push to `main`:

```text
python -m py_compile build.py package.py sysroot.py utils.py scripts/ci/check_repo.py scripts/ci/check_version_drift.py scripts/ci/verify_release_asset.py scripts/ci/generate_versions.py
bash -n install_flutter_complete.sh scripts/install/*.sh scripts/test/gh_e2e_test.sh scripts/device/termux_smoke.sh
PowerShell parser check for scripts/device/run_termux_smoke.ps1
python scripts/ci/generate_versions.py --check
python scripts/ci/check_repo.py
python scripts/ci/check_version_drift.py
git diff --check
```

You validate repo-specific contracts with `check_repo.py`, including:

- workflow YAML parses
- self-hosted workflows are not triggered by `pull_request`
- `package.yaml` still packages `dart`, `dartvm`, `dartaotruntime`, and `post_install`
- `post_install.sh` still contains the Flutter 3.44 `PLATFORM_ABI_LIST` and Android-host patches
- installer defaults remain on Flutter main and NDK r29 for Termux installs
- release/download docs do not regress to stale 3.41.5 commands

## Full deb build

Primary workflow: **Build** (`.github/workflows/build.yml`).

Runs on `ubuntu-latest` via `workflow_run` right after the daily refresh
(11:00 UTC, event-driven, gated: the
cheap `gate` job skips the multi-hour build when pins are stale or the deb
for the current pins is already released), on push of hand-edited build
inputs, on a daily schedule fallback
(`0 12 * * *` UTC) and on manual dispatch
(`workflow_dispatch`), reusing the NDK that ships on GitHub-hosted runners.
You derive the deb name at build time from the `build.toml` pins at tip, so
it matches the Flutter version you build. It:

1. Installs host deps and bootstraps `depot_tools` (inline clone).
2. Detects the NDK from the runner env (`ANDROID_NDK` → `ANDROID_NDK_LATEST_HOME` → `ANDROID_NDK_HOME`).
3. Runs the documented pipeline. The `.gclient` `custom_hooks` apply patches
   during `sync`, so skip any explicit `patch_*` step:

   ```bash
   python3 build.py clone
   python3 build.py sync
   python3 build.py sysroot --arch=arm64
   python3 build.py configure --arch=arm64 --mode=release
   python3 build.py build    --arch=arm64 --mode=release
   python3 build.py debuild  --arch=arm64
   ```

   Use the `patch_*` helpers only to re-apply / rebase a patch
   to a fresh checkout; running them right after `sync` fails with "already
   exists".
4. Publishes a GitHub Release tagged with the Flutter version containing
   `**/*.deb`.

If the hosted runner hits its 6-hour cap (or you want build metadata), fall
back to **Build deb (self-hosted)** (`.github/workflows/build-deb.yml`):

- Runs on `${{ inputs.runner_labels_json }}` (default `["self-hosted","linux"]`).
- Requires `/opt/android-ndk-r29` (or `ANDROID_NDK`/`NDK_PATH` env) and a Linux/WSL runner with 100GB+ disk.
- Uploads the deb plus `sha256`/`size.txt`, `build_metadata.json`, `build_evidence.json`, and `inventory.txt` as a workflow artifact for `device-smoke.yml`.

If `gclient` is missing, you bootstrap `depot_tools` in that self-hosted workflow,
then run the same patched pipeline (see above) before uploading:

- `flutter_3.47.6~0.0.pre+main.20260926.8db5526-1_aarch64.deb`
- `flutter_3.47.6~0.0.pre+main.20260926.8db5526-1_aarch64.deb.sha256`
- `flutter_3.47.6~0.0.pre+main.20260926.8db5526-1_aarch64.deb.size.txt`

## Release policy

Merging to `main` leaves publishing to the refresh-triggered `Build` run. The `Build`
run (daily 11:00 UTC refresh via `workflow_run`, plus 12:00 UTC fallback) builds only when the pins
equal upstream HEAD and the deb for those pins is not yet released, then
publishes the resulting `.deb` as a stable release under a versioned tag
(`v<upstream>.<YYYYMMDD>.<shorthash>`, e.g. `v3.49.0-0.1.pre.20260929.fab9915`) while the deb
itself keeps the full dpkg version (`3.49.0~0.1.pre+main.20260929.fab9915-1`).
You can also dispatch `Build` through `workflow_dispatch`. Any push-race or
patch conflict fails closed: resolve the conflict and get a green build before
any pin push, build, or new tag.

### Keep-stable per-deb policy (2026-09-29 decision)

Each main `.deb` ships under its own date+hash-suffixed tag (`$RELEASE_TAG`,
`v<upstream>.<YYYYMMDD>.<shorthash>`), never a bare semver, so a main tag can
never collide with a stable release tag and main debs never reuse a stable
tag or asset name. The tag shape is proven by
`test_build.py::test_main_release_tag_never_collides_with_stable`. Because
every refresh renames both tag and asset, stable `Latest` moves with each
per-deb publish by design; that is expected, not a regression. Asset
immutability is guarded twice: the `release_guard` job sets
`should_publish=false` when the deb already exists on `$RELEASE_TAG`, and the
publish step uses `overwrite_files: false`, so reruns leave existing assets in
place.

The release flow:

1. Merge only after PR CI passes.
2. **Build**: use the refresh-triggered gated run when anything is new (daily
   fallback covers misses), or dispatch
   it through `workflow_dispatch` on the chosen commit/tag.
3. Run device smoke against the produced or published `.deb`.
4. Let **Release check** verify the release asset metadata after publish/edit.

If you need a dry build (no auto publish) or richer build metadata, use the
self-hosted **Build deb (self-hosted)** workflow instead.

## Device smoke

Manual workflow: **Device smoke (self-hosted)**

No hosted main-channel release exists yet. After the first main build
publishes, test that release asset with the default input:

```text
deb_url: https://github.com/GeneralKaos666/prerelease-flutter-for-termux/releases/download/main/flutter_3.47.6~0.0.pre+main.20260926.8db5526-1_aarch64.deb
expected_sha256: TBD (refresh after the first main build; installers fail closed until then)
```

Required self-hosted environment:

- Windows runner with ADB installed
- Android tablet connected and authorized for USB debugging
- Termux installed and launchable as `com.termux`
- Tablet awake/unlocked before the run; secure lock screens block ADB text injection into Termux
- Free enough tablet storage for the deb, Android SDK/NDK, Gradle caches, APK, and Linux build

Keep the tablet awake with the PowerShell driver:

```powershell
adb shell svc power stayon true
adb shell input keyevent 224
adb shell wm dismiss-keyguard
```

You then push the deb and `scripts/device/termux_smoke.sh`, launch Termux, inject:

```text
sh /sdcard/Download/termux_ci_smoke.sh
```

and poll `/sdcard/Download/termux_ci_smoke.txt` until `DONE` or timeout.

Required success markers:

```text
INSTALL_STATUS=0
POST_INSTALL_STATUS=0
FLUTTER_VERSION_STATUS=0
DART_VERSION_STATUS=0
DARTVM_VERSION_STATUS=0
DOCTOR_STATUS=0
CREATE_STATUS=0
BUILD_APK_STATUS=0
APK_MANIFEST_STATUS=0
APK_RESOURCES_STATUS=0
APK_COPY_STATUS=0
BUILD_LINUX_STATUS=0
DONE
```

Turn `svc power stayon` back off before the workflow exits.

## Release check

You verify release metadata from GitHub with `release-check.yml`:

- expected tag exists
- expected asset exists
- asset size is plausible
- asset digest matches the expected SHA256 when GitHub exposes the digest

You can run this workflow on GitHub-hosted runners: it only reads public release metadata.

## Security model

- Fork PRs only get `ci.yml` on GitHub-hosted runners; `Build` runs on
  push of fresh pins plus its daily fallback schedule plus
  `workflow_dispatch` (never on PRs); `Release check`
  runs on release publish/edit plus manual dispatch.
- Self-hosted `Build deb (self-hosted)`/`Device smoke` workflows are
  `workflow_dispatch` only.
- A maintainer triggers device smoke by hand; untrusted PR code stays out unless you dispatch it.
- Release publishing requires `contents: write`: the GitHub-hosted `Build`
  workflow publishes on gated push + schedule + manual dispatch, behind a
  release-asset immutability guard (`should_publish` is false when the deb
  exists on the tag, so reruns leave the asset in place) and a `gate`
  job (with stale pins or already-released debs it skips the build; you push
  a new tag only after you resolve conflicts and the build succeeds).

## Branch Protection and Repository Governance

Find the governance rules for the `main` branch in `.github/rulesets/main_protection_ruleset.json`:

- **Pull Request Requirements**: Request PR review and resolve threads before you merge.
- **Status Checks**: You need green `ci.yml` (Python/Shell/Actionlint sanity, contract validation, version drift checks) before you merge.
- **History & Integrity**: You keep linear git history; the ruleset blocks force pushes (`non_fast_forward`) and branch deletion.
- **Repository Hygiene**: You keep scratch artifacts, test caches, backups, and stage receipts out of git tracking through automated pre-merge checks.

## Local equivalents

Fast local checks:

```bash
python -m py_compile build.py package.py sysroot.py utils.py scripts/ci/check_repo.py scripts/ci/check_version_drift.py scripts/ci/verify_release_asset.py scripts/ci/generate_versions.py
bash -n install_flutter_complete.sh scripts/install/*.sh scripts/test/gh_e2e_test.sh scripts/device/termux_smoke.sh
python scripts/ci/generate_versions.py --check
python scripts/ci/check_repo.py
python scripts/ci/check_version_drift.py
git diff --check
```

Manual Termux release E2E test inside Termux:

```bash
bash scripts/test/gh_e2e_test.sh
```

Manual Windows-to-tablet smoke:

```powershell
scripts/device/run_termux_smoke.ps1 `
  -AdbPath "C:\Users\aa223\AppData\Local\Android\Sdk\platform-tools\adb.exe" `
  -DebUrl "https://github.com/GeneralKaos666/prerelease-flutter-for-termux/releases/download/main/flutter_3.47.6~0.0.pre+main.20260926.8db5526-1_aarch64.deb"
```
