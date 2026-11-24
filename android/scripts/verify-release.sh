#!/usr/bin/env bash
# Checks a release APK before it is published (android/README.md, Releases): signed (v2 or
# later), RollCall's app ID, and the version and version code the tag asks for. Prints the
# signing certificate's SHA-256, which every release must share.
#
#   verify-release.sh <apk> <version, e.g. 1.2.3 or 1.2.3-rc.1> [expected certificate SHA-256]
set -euo pipefail

apk=$1
version=$2
expected_cert=${3:-}

tools=$(ls -d "${ANDROID_HOME:?set ANDROID_HOME}"/build-tools/* | sort -V | tail -n 1)
aapt2=$tools/aapt2
apksigner=$tools/apksigner
# On Windows (Git Bash) the tools are aapt2.exe and apksigner.bat.
[[ -e $apksigner ]] || apksigner=$tools/apksigner.bat
# major.minor.patch, each 0-999 with no leading zero and not all 0, then optionally -rc.N with
# N from 1 and no leading zero (docs/releasing.md, Versioning). A release candidate
# (1.2.3-rc.1) shares its final release's version code (ADR-0024).
part='(0|[1-9][0-9]{0,2})'
code=0
if [[ $version =~ ^$part\.$part\.$part(-rc\.[1-9][0-9]*)?$ ]]; then
  code=$((BASH_REMATCH[1] * 1000000 + BASH_REMATCH[2] * 1000 + BASH_REMATCH[3]))
fi
if ((code == 0)); then
  echo "the version must look like 1.2.3 or 1.2.3-rc.1 (each part 0-999 with no leading zero, not all 0; N from 1 with no leading zero), got: $version" >&2
  exit 1
fi

# Only the first line, read without closing the pipe early (head would, and pipefail would
# then fail on aapt2's SIGPIPE).
badging=$("$aapt2" dump badging "$apk" | sed -n 1p)
want="package: name='io.github.sirmeili.rollcall' versionCode='$code' versionName='$version'"
if [[ $badging != "$want"* ]]; then
  echo "unexpected package line: $badging" >&2
  echo "expected it to start with: $want" >&2
  exit 1
fi

signing=$("$apksigner" verify --verbose --print-certs "$apk" 2>&1 | tr -d '\r')
grep -q "Verified using v2 scheme (APK Signature Scheme v2): true" <<<"$signing" || {
  echo "not signed with APK Signature Scheme v2" >&2
  exit 1
}
# The signer's label differs between apksigner versions ("Signer #1", "Signer (minSdkVersion=…)").
cert=$(grep -m 1 -ioE 'certificate SHA-256 digest: [0-9a-f]{64}' <<<"$signing" | grep -oiE '[0-9a-f]{64}$' || true)
if [[ -z $cert ]]; then
  echo "no signing certificate found in apksigner's output (build-tools ${tools##*/}); its lines:" >&2
  sed -E 's/[0-9a-fA-F]{16,}/<hex>/g' <<<"$signing" >&2
  exit 1
fi
cert=${cert,,}
if [[ -n $expected_cert && $cert != "${expected_cert,,}" ]]; then
  echo "signed with an unexpected certificate: $cert" >&2
  exit 1
fi
echo "ok: io.github.sirmeili.rollcall $version ($code), certificate SHA-256 $cert"
