#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

REPO="jfsunday/epp"
BUILD_LINUX=false
BUILD_WINDOWS=false

# Parse flags
while [[ $# -gt 0 ]]; do
    case "$1" in
        -l) BUILD_LINUX=true; shift ;;
        -w) BUILD_WINDOWS=true; shift ;;
        *) shift ;;
    esac
done

# No flags = build both
if ! $BUILD_LINUX && ! $BUILD_WINDOWS; then
    BUILD_LINUX=true
    BUILD_WINDOWS=true
fi

echo "=== E++ Build ==="
echo ""

# Push & trigger Windows build
if $BUILD_WINDOWS; then
    echo "[..] Pushing latest changes to GitHub..."
    git push origin main 2>/dev/null || true
    echo "[..] Triggering Windows build on GitHub..."
    gh workflow run release.yml --repo "$REPO"
    echo "[ok] Windows build triggered"
    echo ""
fi

# Build Linux locally
if $BUILD_LINUX; then
    echo "[..] Building Linux binary locally..."
    if [ -f .venv/bin/activate ]; then
        source .venv/bin/activate
    fi
    python3 build.py
    echo ""
fi

# Wait for Windows build
if $BUILD_WINDOWS; then
    echo "[..] Waiting for Windows build to finish..."
    sleep 5

    RUN_ID=""
    for i in {1..10}; do
        RUN_ID=$(gh run list --repo "$REPO" --workflow release.yml --limit 1 --json databaseId,status --jq '.[0].databaseId' 2>/dev/null)
        if [ -n "$RUN_ID" ]; then break; fi
        sleep 2
    done

    if [ -z "$RUN_ID" ]; then
        echo "[!!] Could not find Windows build run"
        exit 1
    fi

    echo "[..] Watching run $RUN_ID..."
    gh run watch "$RUN_ID" --repo "$REPO" --exit-status 2>&1 || {
        echo "[!!] Windows build failed! Check: gh run view $RUN_ID --repo $REPO --log"
        exit 1
    }

    echo "[..] Downloading epp.exe..."
    mkdir -p dist
    gh run download "$RUN_ID" --repo "$REPO" --name epp-windows --dir dist/windows
    mv dist/windows/epp.exe dist/epp.exe
    rm -rf dist/windows
fi

echo ""
echo "=================================================="
if $BUILD_LINUX; then echo "  Linux:   dist/epp"; fi
if $BUILD_WINDOWS; then echo "  Windows: dist/epp.exe"; fi
echo "=================================================="
echo ""
echo "  Usage:"
echo "    ./build.sh        # both"
echo "    ./build.sh -l     # Linux only"
echo "    ./build.sh -w     # Windows only"
echo "=================================================="
