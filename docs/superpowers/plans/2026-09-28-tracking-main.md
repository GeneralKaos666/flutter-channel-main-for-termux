# Tracking-main Branch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a long-lived `tracking-main` branch that builds the Termux Flutter `.deb` from Flutter `main` instead of stable.

**Architecture:** Keep `main` on stable (`build.toml tag='3.47.5'`). On the new branch, point the Flutter checkout at `main`, teach the version/drift contracts to accept a non-semver channel, gate stable-only automation off the branch, and rebase the three Termux patches.

**Tech Stack:** Python (Fire CLI `build.py`), `build.toml`, `.gclient` custom_hooks, `scripts/ci/check_version_drift.py`, `scripts/ci/check_repo.py`, GitHub Actions (`autorelease.yml`, `validate.yml`, `build.yml`, `build-deb.yml`), `test_build.py`.

**Spec:** This conversation: "branch this repo and have the branch use flutter master instead of stable" as a long-lived publishable branch (not a throwaway local `--tag=main` override).

## Global Constraints

- `python -m py_compile build.py package.py sysroot.py utils.py scripts/ci/check_repo.py scripts/ci/check_version_drift.py scripts/ci/verify_release_asset.py scripts/ci/generate_versions.py` must pass.
- `pytest test_build.py` must pass (no `tests/` dir; `pytest.ini` names the file).
- `bash -n scripts/install/post_install.sh scripts/test/gh_e2e_test.sh scripts/device/termux_smoke.sh` must pass.
- `python scripts/ci/generate_versions.py --check`, `python scripts/ci/check_version_drift.py`, `python scripts/ci/check_repo.py`, `git diff --check` must pass on the branch.
- New docs live under `docs/`; root markdown allowlist is enforced by `check_repo.py`.
- Every `.sh` keeps `#!` + LF-only endings; never commit `scratch/`, `*.bak`, `*.receipt.json`, test caches.
- `patches/dart.new.patch` stays a symlink to `patches/dart.patch` — edit `dart.patch` only.
- `build()` ninja target list is contract (`flutter`, `flutter/build/archives:artifacts`, `:dart_sdk_archive`, `:flutter_patched_sdk`, `flutter/shell/platform/linux:flutter_gtk`, `flutter/tools/font_subset`) — asserted by `test_build.py`.
- `package.yaml` resource keys and `safe_eval()` expression constraints stay intact.
- Only ARM64 is supported for the packaged build.

## Review Focus

- `main` moves daily: a green patch rebase today can be red tomorrow; the plan must leave a repeatable rebase loop, not a one-shot fix.
- `utils.flutter_tag()` (`git describe --tag`) on a `main` checkout returns the nearest stable tag, so clone-skip logic can delete/re-clone unexpectedly.
- `main` debs must never publish over a stable release tag/asset name (`flutter_3.47.5-1_aarch64.deb` pattern).
- `autorelease.yml` (stable bump bot) must never push stable versions onto `tracking-main` or vice versa.
- `post_install.sh` / installer `FLUTTER_VERSION` / `CANONICAL_*` markers drift silently if the branch pins placeholder versions.

---

### Task 1: Branch + main-pointed build config

**Files:**
- Modify: `build.toml`
- Modify: `build.py:124-147` (`clone()` skip/branch logic)
- Modify: `utils.py:35-42` (`flutter_tag()` branch handling)
- Test: `test_build.py`

**Interfaces:**
- Consumes: current `build.toml [flutter] tag='3.47.5'` (`build.toml:2`), `Build.clone(url, tag, out, force)`, `utils.flutter_tag(root)`.
- Produces: `tracking-main` branch where `Build(tag='main').clone()` checks out Flutter `main` without misfiring the stable-tag skip; `Build.output('arm64')` yields a main-distinct deb name.

- [ ] **Step 1: Create the branch from current main**

Run: `git checkout -b tracking-main`
Expected: `git branch --show-current` prints `tracking-main`.

- [ ] **Step 2: Write a failing check for main clone-skip behavior**

Run: `python3 -c "import utils; print(utils.flutter_tag('./flutter'))"` on a main checkout (or a fixture mocking `git describe` returning a stable tag while `git rev-parse --abbrev-ref HEAD` is `main`)
Expected: demonstrates `flutter_tag()` returns a stable tag (e.g. `3.47.5`) instead of `main`, so `Build.clone()` would wrongly report "flutter exists, skip."

- [ ] **Step 3: Implement minimal `build.toml` + skip-logic changes on `tracking-main`**

In `build.toml` set `[flutter] tag = 'main'` and set `dart_version`, `framework_revision`, `framework_commit_date`, `devtools_version` to the real values from the fresh main checkout (dart `tools/VERSION`, framework `git rev-parse HEAD` + commit date, DevTools pubspec at the DEPS-pinned rev); keep `[package] pkg_rel = '1'` so `Build.output('arm64')` is `flutter_main-1_aarch64.deb` — already distinct from stable assets via the tag, no suffix scheme needed.
In `build.py:124-147` and `utils.py:35-42`, handle non-semver `tag`: when `self.tag == 'main'` (or `tag` is not `\d+\.\d+\.\d+`), resolve the checkout identity via branch/commit (`git rev-parse --abbrev-ref HEAD` / `git rev-parse HEAD`) instead of `git describe --tag --abbrev=0` for the skip decision.

- [ ] **Step 4: Run contract tests**

Run: `python -m py_compile build.py utils.py && pytest test_build.py -v`
Expected: PASS. If `test_output_uses_package_version_suffix` or manifest tests assume semver, update the assertions to derive from `build.toml` (same pattern the file already uses) rather than hardcoding a version literal.

- [ ] **Step 5: Commit**

```bash
git add build.toml build.py utils.py test_build.py
git commit -m "feat(main): track Flutter main on tracking-main branch"
```

---

### Task 2: Teach version-drift + repo contracts about the main channel

**Files:**
- Modify: `scripts/ci/check_version_drift.py`
- Modify: `scripts/ci/check_repo.py`
- Test: `test_build.py` (unchanged unless drift helpers need unit coverage)

**Interfaces:**
- Consumes: Task 1 `build.toml tag='main'`; drift regexes `SEMVER_PATTERN`, `DEB_NAME_PATTERN` (`check_version_drift.py:43-44`).
- Produces: `check_version_drift.py` + `check_repo.py` pass on `tracking-main` while still failing closed on `main` for real drift.

- [ ] **Step 1: Reproduce the failure**

Run: `python scripts/ci/check_version_drift.py; python scripts/ci/check_repo.py`
Expected: FAIL (semver/deb-name/installer-marker mismatches against `main`).

- [ ] **Step 2: Implement channel-aware checks**

Extend the deb-name handling in `check_version_drift.py` for the `main` channel: `DEB_NAME_PATTERN` accepts `flutter_main(-suffix)?_aarch64.deb`, and the AGENTS.md / guide deb checks compare such names against `asset_name`. Add `export `-prefix support to the `replace_line_value` / `replace_line_int_value` autofix helpers (needed for `versions_common.sh`). Keep every stable-branch check byte-identical; no `check_repo.py` change needed (`check_installer_contract` already resolves through `{tag}`). Gate strictly on the `main` channel values, no generic "any string passes" fallback.

- [ ] **Step 3: Sync branch files to the new expected values**

Run: `python scripts/ci/check_version_drift.py --fix`
Expected: rewrites `AGENTS.md`, guides, `post_install.sh` markers, installer defaults to `main` values; review with `git diff --stat` and keep only intended version-string hunks.

- [ ] **Step 4: Verify**

Run: `python scripts/ci/check_version_drift.py && python scripts/ci/check_repo.py && git diff --check`
Expected: all PASS, no whitespace errors.

- [ ] **Step 5: Commit**

```bash
git add scripts/ci/check_version_drift.py scripts/ci/check_repo.py AGENTS.md docs/ README.md install_flutter_complete.sh scripts/
git commit -m "fix(main): accept main channel in version contracts"
```

---

### Task 3: Gate CI so stable automation and main builds cannot collide

**Files:**
- Modify: `.github/workflows/autorelease.yml`
- Modify: `.github/workflows/validate.yml`
- Modify: `.github/workflows/build.yml`
- Modify: `.github/workflows/build-deb.yml` (only if it lacks the same guards)

**Interfaces:**
- Consumes: Task 1 branch name `tracking-main`; stable-only assumptions (`autorelease.yml:24-40` stable-tag detection + push to `main`; `validate.yml:77-84` `--branch "$TAG"` shallow clone; `build.yml:10-13` `workflow_run` on `main` + release publish).
- Produces: `autorelease.yml` never touches `tracking-main`; `validate.yml` clones `main` and checks the rebased engine patch; `build.yml`/`build-deb.yml` can run manually on the branch without overwriting a stable release.

- [ ] **Step 1: Implement `autorelease.yml` branch guard**

Add a job-level guard so the nightly stable bump only runs on `main` (e.g. `if: github.ref == 'refs/heads/main'` on the release job) and confirm the push step still targets `HEAD:main`, never the current branch.

- [ ] **Step 2: Confirm `validate.yml` main clone path (no change expected)**

When `build.toml tag == 'main'`, the existing `git clone --depth=1 --branch "$TAG"` already clones the `main` branch (branch-named tag), then `git apply ../patches/engine.patch` as today. Verify only; change only if the clone fails.

- [ ] **Step 3: Implement `build.yml` / `build-deb.yml` publish guard**

Scope `workflow_run` auto-build to `branches: [main]` (already true in `build.yml:10-13`; verify `build-deb.yml` matches), keep `workflow_dispatch` available for `tracking-main`, and ensure the release step never publishes the main deb over a stable tag (guard to `refs/heads/main`) — never `overwrite_files` onto a stable tag with a colliding asset name.

- [ ] **Step 4: Verify**

Run: `python -c "import yaml; [yaml.safe_load(open(f'./.github/workflows/{w}')) for w in ['autorelease.yml','validate.yml','build.yml','build-deb.yml']]" && python -m py_compile scripts/ci/check_repo.py && python scripts/ci/check_repo.py`
Expected: YAML parses, repo contract (which asserts workflow layout) passes.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/
git commit -m "ci(main): isolate stable automation from tracking-main"
```

---

### Task 4: Verify Termux patches against main and pin versions

**Files:**
- Modify: `patches/engine.patch`
- Modify: `patches/dart.patch` (keep `patches/dart.new.patch` as symlink)
- Modify: `patches/skia.patch`
- Modify: `.gclient` only if hook paths changed upstream
- Modify: `build.toml` (final `dart_version` / `framework_revision` / `framework_commit_date` / `devtools_version` from the successful sync)

**Interfaces:**
- Consumes: Tasks 1–3 (main checkout, tolerant contracts, gated CI); `.gclient:27-43` hook patch application during `gclient sync -DR`.
- Produces: `python3 build.py sync` succeeds on `tracking-main` with all three patches applied; `build.toml` version fields match the synced tree.

- [ ] **Step 1: Attempt sync and capture rejections**

Run: `python3 build.py clone --force && python3 build.py sync`
Expected: initially FAIL with `git apply` rejections or fuzz warnings — save the full log; each rejected hunk is the work list.

- [ ] **Step 2: Rebase each patch hunk-by-hunk**

For `engine`, `dart` (`engine/src/flutter/third_party/dart`), `skia` (`engine/src/flutter/third_party/skia`): apply with `git apply --reject`, port the Termux intent (GN `is_termux=true` toolchain, `-llog -lm`, `fl_view_accessible.cc` ATK guard, `BUILD.gn` `invoker.libs`, Dart `sh` path + `DART_HOST_OS_ANDROID`/`__TERMUX__` shims, skia include fixes) onto the new upstream context, regenerate with `git diff` from the correct repo root, and re-verify `test_build.py` patch-contract assertions still describe the new hunks (update assertions deliberately if the intended hunk moved).

- [ ] **Step 3: Prove clean sync from scratch**

Run: `rm -rf flutter && python3 build.py clone && python3 build.py sync`
Expected: PASS with `patch engine`, `patch dart`, `patch skia` hooks reporting success and no `.rej` files under `flutter/`.

- [ ] **Step 4: Pin versions to the rebased tree and run the lightweight suite**

Read `flutter/bin/internal/engine.version`, framework `git rev-parse HEAD` + commit date, `dart --version` / devtools version from the synced tree into `build.toml`; then run `python -m py_compile build.py package.py sysroot.py utils.py scripts/ci/check_repo.py scripts/ci/check_version_drift.py scripts/ci/verify_release_asset.py scripts/ci/generate_versions.py && pytest test_build.py && bash -n scripts/install/post_install.sh scripts/test/gh_e2e_test.sh scripts/device/termux_smoke.sh && python scripts/ci/generate_versions.py --check && python scripts/ci/check_version_drift.py && python scripts/ci/check_repo.py && git diff --check`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add patches/ .gclient build.toml test_build.py
git commit -m "fix(main): rebase Termux patches onto Flutter main"
```

---

### Task 5: Document the branch and push

**Files:**
- Modify: `docs/guides/BUILD_GUIDE.md` (or `docs/README.md` index target — follow `check_repo.py` link checks)
- Test: full lightweight verification (AGENTS.md list)

**Interfaces:**
- Consumes: Tasks 1–4 (working main branch).
- Produces: a maintainer can discover, update, and rebuild `tracking-main` without reading this plan; branch pushed.

- [ ] **Step 1: Document branch policy**

Add a short section: branch name `tracking-main`, `build.toml tag='main'` + `pkg_rel` convention, how to refresh (`clone --force` → verify patches → pin versions → run Task 4 Step 4 suite), that `autorelease.yml` is stable-only, that main debs use main-distinct names and never publish, and the expected `python3 build.py` full-pipeline invocation (`sysroot` → `configure --arch=arm64 --mode=release` → `build` → `debuild`).

- [ ] **Step 2: Run the full pre-push verification**

Run: `python -m py_compile build.py package.py sysroot.py utils.py scripts/ci/check_repo.py scripts/ci/check_version_drift.py scripts/ci/verify_release_asset.py scripts/ci/generate_versions.py && pytest test_build.py && bash -n scripts/install/post_install.sh scripts/test/gh_e2e_test.sh scripts/device/termux_smoke.sh && python scripts/ci/generate_versions.py --check && python scripts/ci/check_version_drift.py && python scripts/ci/check_repo.py && git diff --check`
Expected: all PASS.

- [ ] **Step 3: Keep the branch local (no push for now)**

Run: `git branch --show-current && git status --short --branch && git log --oneline -5`
Expected: on `tracking-main`, working tree clean, push deferred — do NOT `git push` until explicitly asked.

- [ ] **Step 4: Commit docs (stay local)**

```bash
git add docs/
git commit -m "docs(main): document tracking-main branch policy"
```
Do NOT push — branch stays local until explicitly requested.
