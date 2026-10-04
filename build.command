#!/bin/zsh
set -eu
cd "${0:A:h}"
APP="${PWD}/SilenceTrim.app"
CACHE="$(mktemp -d "${TMPDIR:-/tmp}/silencetrim-build.XXXXXX")"
trap 'rm -rf "$CACHE"' EXIT
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
swiftc -O -target "$(uname -m)-apple-macos13.0" -module-cache-path "$CACHE" source/TrimEngine.swift source/main.swift -o "$APP/Contents/MacOS/SilenceTrim" -framework Cocoa
cp source/Info.plist "$APP/Contents/Info.plist"
cp source/AppIcon.icns "$APP/Contents/Resources/AppIcon.icns"
codesign --force --sign - "$APP"
echo "Đã build: $APP"
