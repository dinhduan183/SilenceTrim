#!/bin/zsh
set -eu
cd "${0:A:h}/.."
TEST_CACHE="$(mktemp -d "${TMPDIR:-/tmp}/silencetrim-tests.XXXXXX")"
trap 'rm -rf "$TEST_CACHE"' EXIT
swiftc -module-cache-path "$TEST_CACHE/cache" source/ReleaseUpdates.swift source/TrimEngine.swift tests/main.swift -o "$TEST_CACHE/path-tests"
"$TEST_CACHE/path-tests" "$PWD/SilenceTrim.app/Contents/MacOS/SilenceTrim"
