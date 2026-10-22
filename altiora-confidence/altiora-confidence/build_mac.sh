#!/bin/bash
# Altiora Confidence - build the macOS app (.dmg). Run on a Mac:  bash build_mac.sh
# Internet is needed during the build only. Takes 5-10 minutes.
#
# Optional (Apple Developer account, $99/year) - sign + notarise so the app opens without warnings:
#   export MAC_SIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)"
#   export APPLE_ID="you@example.com" APPLE_TEAM_ID="TEAMID" APPLE_APP_PASSWORD="xxxx-xxxx-xxxx-xxxx"
set -uo pipefail
cd "$(dirname "$0")"
APP="Altiora Confidence"
VERSION="1.0"
ARCH="$(uname -m)"; [ "$ARCH" = "arm64" ] && LABEL="apple-silicon" || LABEL="intel"
mkdir -p build output
LOG="$PWD/build/build-mac.log"; : > "$LOG"

step() { echo "  $1"; }
fail() {
  echo; echo "  [X] $1"; echo "  ---- last lines of build/build-mac.log ----"
  tail -25 "$LOG"; echo "  -------------------------------------------"; exit 1
}

echo
echo "  ====================================================="
echo "    $APP  -  build macOS ($LABEL)"
echo "  ====================================================="
echo

# 1. A Python the AI libraries support (3.10 - 3.14)
CHECK='import sys; sys.exit(0 if (3,10)<=sys.version_info[:2]<=(3,14) else 1)'
PY=""
for c in python3.13 python3.12 python3.11 python3.14 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "$CHECK" 2>/dev/null; then PY="$c"; break; fi
done
[ -z "$PY" ] && fail "No compatible Python found. Install Python 3.13 from https://www.python.org/downloads/ and run again."
step "[1/5] Preparing the environment ($($PY --version 2>&1))..."
if [ -x .build-venv-mac/bin/python ] && ! .build-venv-mac/bin/python -c "$CHECK" 2>/dev/null; then rm -rf .build-venv-mac; fi
[ -x .build-venv-mac/bin/python ] || "$PY" -m venv .build-venv-mac >>"$LOG" 2>&1 || fail "Could not create the Python environment."
VPY="$PWD/.build-venv-mac/bin/python"
"$VPY" -m pip install --upgrade pip >>"$LOG" 2>&1
"$VPY" -m pip install --prefer-binary --only-binary=spacy,thinc,blis,numpy,cymem,preshed,murmurhash,srsly,pymupdf \
  -r requirements.txt >>"$LOG" 2>&1 || fail "Installing the libraries failed."

# 2. AI model + OCR languages
step "[2/5] Downloading the AI model and OCR languages..."
"$VPY" packaging/prepare_resources.py >>"$LOG" 2>&1 || fail "Downloading the resources failed."

# 3. Build the .app
step "[3/5] Building the app (a few minutes)..."
rm -rf "dist/$APP" "dist/$APP.app"
"$VPY" -m PyInstaller --noconfirm --clean --distpath dist --workpath build/work \
  packaging/altiora_confidence.spec >>"$LOG" 2>&1 || fail "Building the app failed."
[ -d "dist/$APP.app" ] || fail "dist/$APP.app was not created."

# 4. Self-test of the finished app
step "[4/5] Automatic check..."
rm -rf build/selftest
"dist/$APP.app/Contents/MacOS/$APP" --selftest "$PWD/exemple_contrat.pdf" "$PWD/build/selftest" >>"$LOG" 2>&1
if ! grep -q "RESULT=OK" build/selftest/selftest.txt 2>/dev/null; then
  cat build/selftest/selftest.txt 2>/dev/null; fail "The automatic check failed."
fi
echo "        OK: AI model loaded, scan reading available, test document anonymised."

# Optional: real signature + Apple notarisation
if [ -n "${MAC_SIGN_IDENTITY:-}" ]; then
  step "      Signing with: $MAC_SIGN_IDENTITY"
  codesign --force --deep --timestamp --options runtime --entitlements packaging/entitlements.plist \
    -s "$MAC_SIGN_IDENTITY" "dist/$APP.app" >>"$LOG" 2>&1 || fail "Signing failed."
fi

# 5. Disk image
step "[5/5] Creating the .dmg..."
DMG="output/Altiora_Confidence_${VERSION}_mac_${LABEL}.dmg"
STAGE="build/dmg"; rm -rf "$STAGE"; mkdir -p "$STAGE"
cp -R "dist/$APP.app" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
rm -f "$DMG"
hdiutil create -volname "$APP" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >>"$LOG" 2>&1 || fail "Creating the .dmg failed."

if [ -n "${MAC_SIGN_IDENTITY:-}" ] && [ -n "${APPLE_ID:-}" ]; then
  step "      Sending to Apple for notarisation (a few minutes)..."
  codesign --timestamp -s "$MAC_SIGN_IDENTITY" "$DMG" >>"$LOG" 2>&1
  xcrun notarytool submit "$DMG" --apple-id "$APPLE_ID" --team-id "$APPLE_TEAM_ID" \
    --password "$APPLE_APP_PASSWORD" --wait >>"$LOG" 2>&1 || fail "Notarisation failed."
  xcrun stapler staple "$DMG" >>"$LOG" 2>&1
fi

echo
echo "  ====================================================="
echo "    Done!  $DMG"
echo "  ====================================================="
echo
[ -z "${CI:-}" ] && open output
exit 0
