# Flutter main for Termux ARM64

**Flutter main / Dart 3.14.0-271.0.dev for Android-bionic ARM64 hosts.**

This package brings the Termux Flutter SDK to Flutter main. You get post-v3.44.2 installer hardening, dynamic JAVA_HOME auto-detection, PREFIX quoting hardened for `set -euo pipefail`, and refreshed Termux toolchain sysroot packages.

## Package

| Item | Value |
|------|-------|
| Package | `flutter_3.47.6~0.0.pre+main.20260926.8db5526-1_aarch64.deb` |
| Size | `TBD (refresh on first main build)` |
| SHA256 | `TBD (refresh on first main build)` |
| Flutter | main |
| Flutter Tools Dart | 3.14.0-271.0.dev |
| Dart VM | post-install `dartvm` resolves to Dart 3.14.0-271.0.dev (`android_arm64`) |
| Target host | Termux / Android bionic / ARM64 |

## Install

```bash
pkg update -y
pkg install -y x11-repo wget openjdk-21 7zip
# NOTE (tracking-main): no hosted main-channel release exists yet. Build the
# deb yourself (see BUILD_GUIDE.md) and adb push it instead of wget.
wget https://github.com/GeneralKaos666/prerelease-flutter-for-termux/releases/download/main/flutter_3.47.6~0.0.pre+main.20260926.8db5526-1_aarch64.deb
dpkg -i flutter_3.47.6~0.0.pre+main.20260926.8db5526-1_aarch64.deb
apt --fix-broken install -y
bash $PREFIX/share/flutter/post_install.sh
source $PREFIX/etc/profile.d/flutter.sh
flutter doctor -v
```

## Verified

Device smoke on Samsung SM-X716B / Android 16 / ARM64 Termux:

| Command | Result |
|---------|--------|
| `flutter --version` | ✅ Flutter main (framework `8db5526`, `2026-09-26`) |
| `dart --version` | ✅ Dart 3.14.0-271.0.dev on `android_arm64` |
| `dartvm --version` | ✅ Dart 3.14.0-271.0.dev on `linux_arm64` |
| `flutter doctor -v` | ✅ completes; unknown channel / no connected device are expected warnings |
| `flutter create --platforms=android,linux` | ✅ |
| `flutter build apk --release --target-platform android-arm64 --no-tree-shake-icons` | ✅ ARM64 APK produced |
| `flutter build linux --release` | ✅ ARM64 Linux bundle produced |
| deb artifact validator | ✅ `dart`, `dartvm`, `dartaotruntime` executable |

## Highlights

### Flutter main update

- Track Flutter main with updated package metadata, NDK configurations, and patches (Dart 3.14.0-271.0.dev, framework `8db5526` dated `2026-09-26`).
- Keep the Flutter CLI on Termux JIT Dart and preserve engine VM tools for snapshots.

### Installer & Environment Hardening

- Guard `$PREFIX` paths against whitespace and `set -u` unbound variable errors.
- Discover `JAVA_HOME` across Termux OpenJDK installations at runtime.
- Resolve dependencies at install time, including OpenJDK 21 and 7zip.

### Post-install Dart VM detection fix

- Fixed the `post_install.sh` system Dart VM replacement logic to inspect the target path (`/data/data/com.termux/files/usr/bin/dart`) instead of `command -v`, stopping path shadowing.

### Technical Details

- Build output directories: `linux_debug_arm64/`, `linux_release_arm64/`, `linux_profile_arm64/`, `android_release_arm64/`, `android_profile_arm64/`
- Deb package size is TBD until the first main build publishes.

## Required per-project Android settings

To build APKs on Termux, configure these project properties:

```properties
# android/gradle.properties
android.aapt2FromMavenOverride=/data/data/com.termux/files/usr/bin/aapt2
android.enableResourceOptimizations=false
```

```kotlin
// android/app/build.gradle.kts
android {
    compileSdk = 36
    defaultConfig {
        targetSdk = 36
        ndk { abiFilters += listOf("arm64-v8a") }
    }
    buildTypes {
        release {
            isMinifyEnabled = false
            isShrinkResources = false
        }
    }
}
```

Build with:

```bash
flutter build apk --release --target-platform android-arm64 --no-tree-shake-icons
```

## Known limitations

- Android APK targets are ARM64-only (`android-arm64` / `arm64-v8a`).
- `flutter run` for Android requires ADB pairing/connection from inside Termux.
- You can ignore Flutter doctor warnings about unknown channel/source in this repackaged SDK.
- You point `android.aapt2FromMavenOverride` at Termux aapt2 (16.0.0.4); you default projects to `compileSdk`/`targetSdk` 36, with a fail-closed fallback to 35/34 when aapt2 cannot load the newest platform.

## Previous releases

### v3.41.5 (2026-04-13)

- Upgraded the Flutter SDK to 3.41.5 (Dart 3.11.3).
- Added `flutter build linux` support.
- Fixed post-install sed delimiter and flutter_tools snapshot invalidation.

### v3.35.0 (2026-01-07)

- First public release.
- Added APK build and hot reload support for ARM64 Termux.
