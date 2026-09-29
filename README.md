# Flutter Termux

Run the Flutter SDK on [Termux](https://termux.dev) (Android / Bionic ARM64).

This project cross-compiles the upstream Flutter SDK into a `.deb` package that
installs into a Termux `$PREFIX` and enables `flutter run`,
`flutter build apk`, and `flutter build linux` on-device.

## Version

| Component | Version |
|-----------|---------|
| Flutter   | main channel |
| Dart      | 3.14.0-271.0.dev |
| Architecture | aarch64 (ARM64) only |
| Package   | `flutter_0~main.20260926.8db5526-1_aarch64.deb` |

Release assets include:
- `flutter_<tag>-<pkg_rel>_aarch64.deb`
- `flutter_<tag>-<pkg_rel>_aarch64.deb.sha256`
- `flutter_<tag>-<pkg_rel>_aarch64.deb.size.txt`
- `inventory.txt`, `build_metadata.json`, `build_evidence.json`

Download (after the first main build publishes):

```bash
RELEASE_TAG=main
DEB="flutter_0~main.20260926.8db5526-1_aarch64.deb"
BASE_URL="https://github.com/GeneralKaos666/prerelease-flutter-for-termux/releases/download/${RELEASE_TAG}/"

curl -fSL -o "$DEB" "${BASE_URL}${DEB}"
curl -fSL -o "${DEB}.sha256" "${BASE_URL}${DEB}.sha256"
sha256sum -c "${DEB}.sha256"
```

No hosted main-channel release exists yet. Build the deb yourself
(see [Build guide](docs/guides/BUILD_GUIDE.md)) and `adb push` it until
the first main build publishes. Installers fail closed on
`EXPECTED_SHA256` until the hash refreshes.

## Install

Requirements:

- An AArch64 device running Termux. You need ARM64 hardware.
- Run `pkg up` first, and install `x11-repo`:

```bash
pkg update && pkg upgrade
pkg install x11-repo
```

### One-command install

```bash
curl -sL https://raw.githubusercontent.com/GeneralKaos666/prerelease-flutter-for-termux/main/install_flutter_complete.sh \
  -o install_flutter_complete.sh
bash install_flutter_complete.sh
```

You get the release package plus the on-device Android SDK/toolchain
(see [Install guide](docs/guides/INSTALL_GUIDE.md)).

### Manual install

```bash
RELEASE_TAG=main
DEB="flutter_0~main.20260926.8db5526-1_aarch64.deb"
BASE_URL="https://github.com/GeneralKaos666/prerelease-flutter-for-termux/releases/download/${RELEASE_TAG}/"

curl -fSL -o "$DEB" "${BASE_URL}${DEB}"
curl -fSL -o "${DEB}.sha256" "${BASE_URL}${DEB}.sha256"
curl -fSL -o "${DEB}.size.txt" "${BASE_URL}${DEB}.size.txt"

# verify integrity
sha256sum -c "${DEB}.sha256"
test "$(cat "${DEB}.size.txt")" = "$(stat -c '%s' "$DEB")"

apt install "./${DEB}"
bash $PREFIX/share/flutter/post_install.sh
```

You find `flutter` under `$PREFIX/opt/flutter`. Verify with:

```bash
flutter doctor -v
```

### Uninstall

```bash
apt remove flutter
```

## Build an Android APK

Create your first project and build a debug APK:

```bash
flutter create my_app
cd my_app
flutter devices        # connect a device or emulator via adb
flutter build apk --debug --no-tree-shake-icons
```

### Per-project configuration

Run this script once per project:

```bash
bash $PREFIX/share/flutter/flutter_project_config.sh
```

or do it by hand:

`android/gradle.properties`:

```properties
android.aapt2FromMavenOverride=/data/data/com.termux/files/usr/bin/aapt2
```

`android/app/build.gradle.kts`:

```kotlin
android {
    compileSdk = 36
    targetSdk = 36
    defaultConfig {
        ndk {
            abiFilters += listOf("arm64-v8a")
        }
    }
}
```

> You use compileSdk 36 because Termux ships aapt2 16.0.0.4, which loads the
> android-35/36 `android.jar`. `post_install.sh` pins `compileSdk = 36` /
> `targetSdk = 36` through `flutter_project_config.sh` and falls back
> 36 → 35 → 34 when your installed aapt2 cannot load the newest platform.
> You build the engine against Android API 26 with weak imports, so compileSdk
> shapes APK packaging tools, nothing else.
> See [AAPT2 analysis](docs/guides/AAPT2_RELEASE_BUILD_BUG_ANALYSIS.md).

## Hot reload

Run on a connected device:

```bash
flutter devices
flutter run -d <device_id>
```

<p align="center">
  <img src="assets/demo_hot_reload.jpg" alt="Hot reload" width="60%"/>
</p>

## Linux desktop (Termux:X11)

Use [Termux:X11](https://github.com/termux/termux-x11/releases) to preview the
app:

```bash
export DISPLAY=:0
termux-x11 :0 >/dev/null 2>&1 &
flutter run -d linux
```

## Web server

```bash
flutter run -d web-server --web-port 8080
```

Then open `http://localhost:8080` in your browser.

## Build the package from source

You run the full pipeline on a Linux x86-64 host (WSL2 or self-hosted runner)
with NDK r29, `dpkg`, and `ar`:

```bash
python3 -m pip install -r requirements.txt
export ANDROID_NDK=/opt/android-ndk-r29

python3 build.py clone
python3 build.py sync
python3 build.py sysroot --arch=arm64
python3 build.py configure --arch=arm64 --mode=release
python3 build.py build --arch=arm64 --mode=release
python3 build.py debuild --arch=arm64
```

Plan 2-4 hours for a full run on 24 threads. The `.gclient` `custom_hooks`
apply patches during `sync`, so you skip `patch_*` (running one right after `sync` fails with "already
exists"). See [Build guide](docs/guides/BUILD_GUIDE.md) for details and
troubleshooting.

## CI/CD

The daily gated `Build` workflow (`build.yml`) builds and publishes prereleases
on `ubuntu-latest`. It runs when something changes and derives the deb name at
build time. You trigger it by manual dispatch too. A self-hosted
evidence-tracked fallback (`build-deb.yml`) plus an ADB device smoke gate
(`device-smoke.yml`) cover manual runs.
See [CI/CD and device lab](docs/CI_CD.md).

## Documentation

- [Install guide](docs/guides/INSTALL_GUIDE.md): on-device setup, prerequisites, troubleshooting.
- [Build guide](docs/guides/BUILD_GUIDE.md): end-to-end source build and packaging.
- [Upgrade guide](docs/guides/UPGRADE_GUIDE.md): moving to a new Flutter release.
- [Build process](docs/guides/BUILD_PROCESS.md): historical build notes.
- [Changelog](docs/releases/CHANGELOG.md): version history and notable fixes.
- [Release notes](docs/releases/RELEASE_NOTES.md): GitHub release body.

## Acknowledgements

You build on earlier work:

- [mumumusuc/Flutter-Termux](https://github.com/mumumusuc/Flutter-Termux):
  the original Termux port. You get the `is_termux` GN toolchain, Bionic linker
  handling, and the engine/Dart/Skia patch approach through `gclient`
  hooks.
- Sergey Yamshchikov, Not Sarv, Susan Dahal, and Ron Sloan contributed code
  and docs.
- You depend on upstream [Flutter](https://github.com/flutter/flutter), Dart,
  Skia, and Termux to build and run.
- You track Flutter `main` here as `prerelease-flutter-for-termux`, continuing
  the `GeneralKaos666/flutter-for-termux` line.

## Limitations

- ARM64 only: `arm` and `x64` gen_snapshot builds fail (32-bit BoringSSL shift
  overflow / sysroot mismatch), so you get the `aarch64` package.
- The bundle ships `release` mode. Rebuild with `--mode=debug|profile` for
  debug/profile.