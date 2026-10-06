#!/bin/zsh
set -eu
cd "${0:A:h}"
APP="${PWD}/SilenceTrim.app"
CACHE="$(mktemp -d "${TMPDIR:-/tmp}/silencetrim-build.XXXXXX")"
trap 'rm -rf "$CACHE"' EXIT
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
ARCH_LIST="${BUILD_ARCHS:-$(uname -m)}"
typeset -a BINARIES
for ARCH in ${=ARCH_LIST}; do
    case "$ARCH" in arm64|x86_64) ;; *) echo "Unsupported architecture: $ARCH" >&2; exit 1 ;; esac
    BINARY="$CACHE/SilenceTrim-$ARCH"
    swiftc -O -target "$ARCH-apple-macos13.0" -module-cache-path "$CACHE/modules" source/TrimEngine.swift source/main.swift -o "$BINARY" -framework Cocoa
    BINARIES+=("$BINARY")
done
lipo -create "${BINARIES[@]}" -output "$APP/Contents/MacOS/SilenceTrim"
cp source/Info.plist "$APP/Contents/Info.plist"
cp source/AppIcon.icns "$APP/Contents/Resources/AppIcon.icns"
codesign --force --sign - "$APP"
echo "Đã build: $APP"
