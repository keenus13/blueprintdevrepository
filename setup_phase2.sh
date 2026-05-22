#!/bin/bash
# setup_phase2.sh -- Phase 2 Dependency Installer
# Run this ONCE on the Jetson to install everything forge_produce.py needs.
# Usage: bash ~/kd_ai/setup_phase2.sh
#
# Installs:
#   - ffmpeg (video assembly)
#   - EB Garamond font (caption typography)
#   - Piper TTS binary (local voiceover, aarch64)
#   - en_GB-alan-medium voice model (~63MB)
#
# Creates:
#   - ~/kd_ai/piper/          (Piper binary location)
#   - ~/kd_ai/assets/voices/  (voice model location)
#   - ~/kd_ai/assets/backgrounds/ (add your .mp4 loops here)

set -e  # Exit on any error

KD_AI="$HOME/kd_ai"
PIPER_DIR="$KD_AI/piper"
VOICES_DIR="$KD_AI/assets/voices"
BACKGROUNDS_DIR="$KD_AI/assets/backgrounds"

echo ""
echo "======================================================"
echo "  Forge Phase 2 Setup -- Iron Logos Production Stack"
echo "======================================================"
echo ""

# ── Step 1: System packages ─────────────────────────────────────────────────
echo "[1/4] Installing ffmpeg and EB Garamond font..."
sudo apt-get update -qq
sudo apt-get install -y ffmpeg fonts-ebgaramond wget
echo "      ffmpeg: OK"
echo "      EB Garamond font: OK"

# ── Step 2: Create directories ───────────────────────────────────────────────
echo ""
echo "[2/4] Creating asset directories..."
mkdir -p "$PIPER_DIR"
mkdir -p "$VOICES_DIR"
mkdir -p "$BACKGROUNDS_DIR"
echo "      Directories: OK"

# ── Step 3: Download Piper TTS binary (aarch64) ──────────────────────────────
echo ""
echo "[3/4] Downloading Piper TTS binary for aarch64..."
PIPER_VERSION="2023.11.14-2"
PIPER_URL="https://github.com/rhasspy/piper/releases/download/${PIPER_VERSION}/piper_linux_aarch64.tar.gz"
PIPER_ARCHIVE="/tmp/piper_aarch64.tar.gz"

wget -q --show-progress -O "$PIPER_ARCHIVE" "$PIPER_URL"
tar -xzf "$PIPER_ARCHIVE" -C "$PIPER_DIR" --strip-components=1
rm "$PIPER_ARCHIVE"
chmod +x "$PIPER_DIR/piper"

# Verify
if "$PIPER_DIR/piper" --help > /dev/null 2>&1; then
    echo "      Piper binary: OK ($PIPER_DIR/piper)"
else
    echo "      ERROR: Piper binary failed to run. Check the download."
    exit 1
fi

# ── Step 4: Download voice model (en_GB-alan-medium) ─────────────────────────
echo ""
echo "[4/4] Downloading en_GB-alan-medium voice model (~63MB)..."
VOICE_BASE="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/alan/medium"

wget -q --show-progress \
    -O "$VOICES_DIR/en_GB-alan-medium.onnx" \
    "$VOICE_BASE/en_GB-alan-medium.onnx"

wget -q --show-progress \
    -O "$VOICES_DIR/en_GB-alan-medium.onnx.json" \
    "$VOICE_BASE/en_GB-alan-medium.onnx.json"

echo "      Voice model: OK"

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "======================================================"
echo "  Phase 2 setup complete."
echo "======================================================"
echo ""
echo "Piper binary:  $PIPER_DIR/piper"
echo "Voice model:   $VOICES_DIR/en_GB-alan-medium.onnx"
echo "Backgrounds:   $BACKGROUNDS_DIR"
echo ""
echo "NEXT: Add background video loops to $BACKGROUNDS_DIR"
echo "      Download .mp4 files from Pexels (see FORGE_DAILY_WORKFLOW.md)"
echo "      Search terms: 'marble texture dark', 'ancient ruins atmospheric',"
echo "      'fire close up slow motion', 'storm dark sky dramatic'"
echo ""
echo "Then run: python3 ~/kd_ai/forge_produce.py --file <approved_package.json>"
echo ""
