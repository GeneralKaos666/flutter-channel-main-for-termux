# Termux Flutter main Installation Guide

This guide covers `flutter_3.49.0~0.2.pre+main.20261001.3a1c990-1_aarch64.deb` on ARM64 Termux:

- `flutter doctor -v`
- `flutter create`
- `flutter build apk --release`
- `flutter build linux --release`
- `flutter run` + hot reload (requires an ADB device connection)

## Verified Versions

| Item | Value |
|------|-------|
| Flutter | main (framework `8db5526`, `2026-09-26 15:45:14 -0700`) |
| Flutter Tools Dart | 3.14.0-271.0.dev |
| Dart VM (`dartvm`) | post-install `dartvm` resolves to Dart 3.14.0-271.0.dev (`android_arm64`) |

| Test device | Samsung SM-X716B / Android 16 / ARM64 (reference smoke device) |
| deb size | TBD (refresh on first main build) |
| SHA256 | `TBD (refresh on first main build)` |

## System Requirements

| Item | Requirement |
|------|-------------|
| Android | Android 11 (API 30) or higher |
| CPU | ARM64 / aarch64 |
| Termux | Use the F-Droid build or official GitHub release build |
| Storage | At least 5GB; use 8GB+ for a full Android SDK/NDK + Gradle cache |
| Java | `openjdk-21` |

## Method 1: One-Command Install (Recommended)

```bash
curl -sL https://raw.githubusercontent.com/GeneralKaos666/prerelease-flutter-for-termux/main/install_flutter_complete.sh -o ~/install.sh
bash ~/install.sh
```

You install Flutter, the Android SDK/NDK, the required Termux packages, and run post-install with this script. The first run downloads a large amount of data. Keep the screen on and the network stable.

## Method 2: Manual deb Install

```bash
pkg update -y
pkg install -y x11-repo git wget curl unzip openjdk-21 aapt2 android-tools cmake ninja clang

cd ~
# NOTE (tracking-main): no hosted main-channel release exists yet. Build the
# deb yourself (see BUILD_GUIDE.md) and adb push it, e.g.:
# adb push flutter_3.49.0~0.2.pre+main.20261001.3a1c990-1_aarch64.deb /data/local/tmp/
wget https://github.com/GeneralKaos666/prerelease-flutter-for-termux/releases/download/v3.49.0-0.2.pre.20261001.3a1c990/flutter_3.49.0~0.2.pre+main.20261001.3a1c990-1_aarch64.deb
sha256sum flutter_3.49.0~0.2.pre+main.20261001.3a1c990-1_aarch64.deb
# No published hash to confirm against yet; the installer fails closed until
# EXPECTED_SHA256 is refreshed after the first main build.

dpkg -i flutter_3.49.0~0.2.pre+main.20261001.3a1c990-1_aarch64.deb
apt --fix-broken install -y

# Required: dpkg only installs files; this step patches the Termux runtime.
bash $PREFIX/share/flutter/post_install.sh

source $PREFIX/etc/profile.d/flutter.sh
flutter doctor -v
```

You can ignore these warnings in `flutter doctor`:

- unknown channel / unknown upstream source: the Flutter SDK in the deb is not an official git remote checkout.
- no connected device: you connected no ADB device in Termux yet. You can still run `flutter build apk`.

## What post_install.sh Does

| Category | Details |
|----------|---------|
| Dart | Runs the Flutter CLI with Termux JIT Dart, keeping the engine `dartvm` / `dartaotruntime` for snapshots |
| Flutter Tools | Patches the Android/Termux host lookup and clears stale `flutter_tools` snapshots/cache |
| Gradle plugin | ARM64-only ABI; adds the `PLATFORM_ABI_LIST` that Flutter 3.44 needs |
| Android SDK | Installs/patches API 34/36, cmdline-tools, build-tools, licenses |
| NDK | Creates clang wrappers, patches the CMake host tag, replaces objcopy/strip |
| Linux desktop | Enables `flutter build linux` to run on the Termux host |

If you still see old Gradle or Kotlin errors after upgrading, re-run:

```bash
bash $PREFIX/share/flutter/post_install.sh
rm -rf ~/.gradle/caches ~/.gradle/daemon
```

## Verify the Installation

```bash
flutter --version
dart --version
dartvm --version
flutter doctor -v
```

Expected highlights:

- `flutter --version` shows Flutter main.
- `dart --version` shows `android_arm64` (Termux JIT Dart).
- `dartvm --version` shows `linux_arm64` (engine VM).

## Create an Android APK Project (Mode A: Local Build)

Create the project and fix the shebang:

```bash
flutter create myapp
cd myapp
sed -i '1s|#!/usr/bin/env bash|#!/data/data/com.termux/files/usr/bin/bash|' android/gradlew
```

1. Set the project Gradle properties (in `android/gradle.properties`):

```properties
android.aapt2FromMavenOverride=/data/data/com.termux/files/usr/bin/aapt2
android.enableResourceOptimizations=false
shrink=false
org.gradle.jvmargs=-Xmx2048m -XX:MaxMetaspaceSize=512m -Dfile.encoding=UTF-8
```

2. Edit `android/app/build.gradle.kts` (set the SDK and disable minification/shrinking):

```kotlin
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

3. Build (JIT Dart cannot run the icon tree shaker, so bypass it):

```bash
flutter build apk --release --target-platform android-arm64 --no-tree-shake-icons
```

Artifacts:

```text
build/app/outputs/flutter-apk/app-release.apk
```

## Create a Linux Desktop Project

```bash
flutter create mylinux --platforms=linux
cd mylinux
sed -i '1i set(CMAKE_SYSTEM_NAME Linux)' linux/CMakeLists.txt
flutter build linux --release
```

Artifacts:

```text
build/linux/arm64/release/bundle/
```

## flutter run / Hot Reload

`flutter run` needs ADB inside Termux to see the Android device. For the same tablet/phone, use Android "wireless debugging":

```bash
pkg install android-tools
adb pair 127.0.0.1:<pair_port>
adb connect 127.0.0.1:<connect_port>
flutter devices
flutter run -d <device_id>
```

If `flutter doctor` shows no connected device, connect ADB. The SDK works.

## Common Problems

### `PLATFORM_ABI_LIST` unresolved

The post-install Flutter Gradle plugin template or the Gradle cache is stale. After updating to the main deb, run:

```bash
bash $PREFIX/share/flutter/post_install.sh
./android/gradlew --stop || true
rm -rf ~/.gradle/caches .gradle android/.gradle build android/app/build
flutter build apk --release --target-platform android-arm64 --no-tree-shake-icons
```

### AAPT2 / compileSdk Errors

Use API 36 and point to the Termux ARM64 aapt2 (post-install falls back to 35/34 if aapt2 cannot load android-36):

```properties
android.aapt2FromMavenOverride=/data/data/com.termux/files/usr/bin/aapt2
```

```kotlin
compileSdk = 36
defaultConfig { targetSdk = 36 }
```

### NDK or CMake Cannot Find the Compiler

Gradle may have downloaded a new NDK or build-tools. Re-run post-install:

```bash
bash $PREFIX/share/flutter/post_install.sh
```

### Out of Storage Space

```bash
rm -rf ~/.gradle/caches ~/.gradle/wrapper ~/.pub-cache/hosted
pkg clean
```

### Need an arm / x64 APK

This project provides only the ARM64 Android target, so use:

```bash
flutter build apk --release --target-platform android-arm64
```