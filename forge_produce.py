"""
forge_produce.py -- Phase 2 Video Production Pipeline
Part of: KD Empire / Iron Logos / Forge AI Content System
Target: Jetson Orin Nano (~/kd_ai/)

Reads an approved content package (JSON) and produces a fully assembled,
upload-ready vertical video (.mp4) for TikTok and YouTube Shorts.

Pipeline:
    approved JSON
        -> Piper TTS (local, British voice) -> .wav narration
        -> Caption timing (estimated from word count, text from package)
        -> Background video loop (random from ~/kd_ai/assets/backgrounds/)
        -> ffmpeg assembles: background + audio + captions + branding
        -> 1080x1920 .mp4 -> ~/kd_ai/content/autonomous/produced/

CAPTION NOTE: Captions are sourced directly from the caption_breakdown field
in the JSON package -- the text Claude already wrote. No AI transcription or
speech recognition is involved. Text is sanitized before rendering to prevent
ffmpeg artifacts (apostrophes, special chars, non-ASCII stripped).

Dependencies (installed by setup_phase2.sh):
    - ffmpeg (apt)
    - EB Garamond font (apt: fonts-ebgaramond)
    - Piper TTS binary at ~/kd_ai/piper/piper
    - Voice model at ~/kd_ai/assets/voices/en_GB-alan-medium.onnx

Background videos:
    Place .mp4 files in ~/kd_ai/assets/backgrounds/
    Recommended: marble, ruins, fire, storm, stone from Pexels (free)
    Fallback: dark gradient generated automatically if folder is empty

Usage:
    python3 forge_produce.py --file approved/forge_auto_20260521_024939.json
    python3 forge_produce.py --all      # produce all unproduced approved packages
"""

import sys
import os
import json
import re
import random
import shutil
import subprocess
import tempfile
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from forge_core import (
    setup_logging,
    setup_directories,
    KD_AI_ROOT,
    AUTONOMOUS_APPROVED_DIR,
    AUTONOMOUS_PRODUCED_DIR,
    VOICES_DIR,
    BACKGROUNDS_DIR,
    timestamp_str,
)


# ── Asset Paths ────────────────────────────────────────────────────────────────
PIPER_BINARY  = KD_AI_ROOT / "piper" / "piper"
VOICE_MODEL   = VOICES_DIR / "en_GB-alan-medium.onnx"
VOICE_CONFIG  = VOICES_DIR / "en_GB-alan-medium.onnx.json"

# ── Video Spec (1080x1920 vertical = TikTok / YouTube Shorts) ─────────────────
VIDEO_WIDTH   = 1080
VIDEO_HEIGHT  = 1920
VIDEO_FPS     = 30

# TTS pacing: slow narrator cadence for Iron Logos
# Used to estimate caption timing when total audio duration is known
NARRATOR_WPM  = 120  # words per minute at wise narrator pace


# ── Caption Utilities ──────────────────────────────────────────────────────────

def sanitize_for_ass(text: str) -> str:
    """
    Clean a caption string for safe rendering in ASS subtitle format.
    Strips characters that cause ffmpeg rendering artifacts.

    What this removes:
        - Non-ASCII characters (accents, unicode symbols)
        - ASS override tag delimiters { } (would break styling)
        - Backslashes (ASS escape character)
        - Leading/trailing whitespace

    What this keeps:
        - All standard English punctuation
        - Apostrophes, commas, periods, hyphens, colons
    """
    # Strip to ASCII only -- safest for ffmpeg libass renderer
    text = text.encode("ascii", errors="ignore").decode("ascii")
    # Remove ASS override tag delimiters
    text = text.replace("{", "").replace("}", "")
    # Remove backslashes (ASS escape character)
    text = text.replace("\\", "")
    return text.strip()


def count_words(text: str) -> int:
    return len(text.split())


def format_ass_time(seconds: float) -> str:
    """Format seconds as ASS timestamp: H:MM:SS.cc"""
    seconds = max(0.0, seconds)
    h  = int(seconds // 3600)
    m  = int((seconds % 3600) // 60)
    s  = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def build_ass_subtitles(caption_breakdown: list, total_duration: float) -> str:
    """
    Build an ASS subtitle file from the caption_breakdown list.

    Timing is estimated proportionally by word count:
        time_for_caption = (words_in_caption / total_words) * total_duration

    Minimum 1.5 seconds per caption to ensure readability.

    Iron Logos style:
        - Bold EB Garamond, 76pt, white, centered bottom-third
        - Semi-transparent dark background box for readability
        - IRON LOGOS branding in small aged-gold serif, bottom-right, full duration

    Returns the complete ASS file content as a string.
    """
    # Sanitize all captions first
    captions = [sanitize_for_ass(c) for c in caption_breakdown if c.strip()]

    if not captions:
        captions = [""]

    # Calculate proportional timing
    word_counts  = [max(count_words(c), 1) for c in captions]
    total_words  = sum(word_counts)
    events       = []
    current_time = 0.0

    for caption, words in zip(captions, word_counts):
        duration = max((words / total_words) * total_duration, 1.5)
        # Don't overshoot
        if current_time + duration > total_duration + 0.1:
            duration = total_duration - current_time
        if duration < 0.1:
            break

        start = format_ass_time(current_time)
        end   = format_ass_time(current_time + duration)
        events.append(f"Dialogue: 0,{start},{end},Caption,,0,0,0,,{caption}")
        current_time += duration

    # Channel branding: full video duration, bottom-right corner
    branding_end = format_ass_time(total_duration)
    events.append(
        f"Dialogue: 0,0:00:00.00,{branding_end},Branding,,0,0,0,,IRON LOGOS"
    )

    # ASS color format: &HAABBGGRR (alpha, blue, green, red -- reversed)
    # White text:              &H00FFFFFF
    # Aged gold (Iron Logos):  #A0793D -> R=A0, G=79, B=3D -> &H003D79A0
    # Semi-transparent black:  &H90000000 (56% alpha black box)
    # Fully transparent:       &H00000000

    ass = f"""[Script Info]
Title: Iron Logos
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: {VIDEO_WIDTH}
PlayResY: {VIDEO_HEIGHT}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,EB Garamond,76,&H00FFFFFF,&H000000FF,&H00000000,&H90000000,-1,0,0,0,100,100,2,0,3,0,0,2,80,80,220,1
Style: Branding,EB Garamond,36,&H803D79A0,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,3,30,30,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "\n".join(events)

    return ass


# ── TTS ────────────────────────────────────────────────────────────────────────

def generate_tts(script_text: str, output_wav: Path, logger) -> bool:
    """
    Generate a .wav narration file using the local Piper TTS binary.
    No API calls -- runs fully on the Jetson.

    Uses a temp file for the script text to avoid shell escaping issues
    with quotes, apostrophes, and other special characters in the script.

    Returns True on success, False on failure.
    """
    piper_cmd = str(PIPER_BINARY) if PIPER_BINARY.exists() else "piper"

    # Write script to temp file -- avoids shell quoting entirely
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(script_text)
        tmp_path = tmp.name

    try:
        cmd = [
            piper_cmd,
            "--model",       str(VOICE_MODEL),
            "--output_file", str(output_wav),
        ]
        with open(tmp_path, "r", encoding="utf-8") as stdin_f:
            result = subprocess.run(
                cmd,
                stdin=stdin_f,
                capture_output=True,
                text=True,
                timeout=180,
            )
        if result.returncode != 0:
            logger.error(f"Piper TTS failed (exit {result.returncode}):\n{result.stderr}")
            return False
        if not output_wav.exists():
            logger.error("Piper ran but no .wav file was created.")
            return False
        size_kb = output_wav.stat().st_size // 1024
        logger.info(f"TTS complete: {output_wav.name} ({size_kb}KB)")
        return True
    finally:
        os.unlink(tmp_path)


def get_audio_duration(wav_path: Path) -> float:
    """
    Get the duration of a .wav file in seconds using ffprobe.
    Falls back to wave module if ffprobe fails.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams", str(wav_path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)
        return float(data["streams"][0]["duration"])
    except Exception:
        # Fallback: use wave module
        import wave as wave_mod
        with wave_mod.open(str(wav_path), "rb") as wf:
            frames = wf.getnframes()
            rate   = wf.getframerate()
            return frames / float(rate)


# ── Background ─────────────────────────────────────────────────────────────────

def select_background(logger) -> Path:
    """
    Pick a random .mp4 background loop from ~/kd_ai/assets/backgrounds/.
    If the folder is empty, generates a dark gradient as fallback.
    The fallback is a near-black static color -- minimal, on-brand for Iron Logos.
    Returns path to the background to use (real or fallback).
    """
    if BACKGROUNDS_DIR.exists():
        loops = (
            list(BACKGROUNDS_DIR.glob("*.mp4")) +
            list(BACKGROUNDS_DIR.glob("*.mov"))
        )
        if loops:
            chosen = random.choice(loops)
            logger.info(f"Background: {chosen.name}")
            return chosen

    # No video loops found -- generate dark gradient fallback
    logger.info(
        "No background loops in assets/backgrounds/. Using dark gradient fallback. "
        "Add .mp4 files there for visual variety."
    )
    fallback = Path(tempfile.mktemp(suffix="_bg.mp4"))
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=#0d0d0d:size={VIDEO_WIDTH}x{VIDEO_HEIGHT}:rate={VIDEO_FPS}",
        "-t", "120",           # 2 min -- long enough for any video
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        str(fallback),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to generate fallback background:\n{result.stderr}")
    return fallback


# ── Assembly ───────────────────────────────────────────────────────────────────

def assemble_video(
    audio_path:     Path,
    background_path: Path,
    ass_content:    str,
    output_path:    Path,
    logger,
) -> bool:
    """
    Assemble the final .mp4 using ffmpeg.

    Process:
        1. Loop background video to match audio length
        2. Scale/crop background to 1080x1920 (vertical, TikTok/Shorts)
        3. Burn ASS captions + IRON LOGOS branding directly into video
        4. Mix in TTS audio track
        5. Output H.264/AAC .mp4 optimized for upload

    Returns True on success.
    """
    # Write ASS to a temp file with a clean path (no spaces or special chars)
    ass_tmp = Path(tempfile.mktemp(suffix=".ass"))
    ass_tmp.write_text(ass_content, encoding="utf-8")

    try:
        # ffmpeg filter chain:
        #   scale+crop: fill vertical frame from any aspect ratio input
        #   fps: normalize frame rate
        #   subtitles: burn ASS captions and branding
        filter_chain = (
            f"[0:v]"
            f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
            f"fps={VIDEO_FPS},"
            f"subtitles={ass_tmp}[v]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1",           # loop background indefinitely
            "-i", str(background_path),      # input 0: background
            "-i", str(audio_path),           # input 1: TTS audio
            "-filter_complex", filter_chain,
            "-map", "[v]",                   # use filtered video
            "-map", "1:a",                   # use TTS audio
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",                    # quality -- 18=best, 28=smallest
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",                     # end when audio ends
            "-movflags", "+faststart",       # web-optimized (moov atom at front)
            str(output_path),
        ]

        logger.info("Running ffmpeg assembly...")
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600
        )

        if result.returncode != 0:
            # Log last 3000 chars of stderr (ffmpeg is verbose)
            logger.error(f"ffmpeg failed:\n{result.stderr[-3000:]}")
            return False

        size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"Assembly complete: {output_path.name} ({size_mb:.1f}MB)")
        return True

    finally:
        if ass_tmp.exists():
            ass_tmp.unlink()


# ── Main Production Function ───────────────────────────────────────────────────

def produce_package(package_path: Path, logger) -> Path | None:
    """
    Run the full production pipeline for one approved content package.

    Steps:
        1. Load and validate the JSON package
        2. Generate TTS narration with Piper
        3. Get audio duration, build ASS caption file
        4. Select background video (or generate fallback)
        5. Assemble video with ffmpeg
        6. Update package metadata with produced status + output path

    Returns the Path to the finished .mp4, or None on failure.
    """
    logger.info(f"{'='*50}")
    logger.info(f"Producing: {package_path.name}")

    # ── Load package ───────────────────────────────────────────────────────────
    with open(package_path, encoding="utf-8") as f:
        package = json.load(f)

    script   = package.get("full_script", "").strip()
    captions = package.get("caption_breakdown", [])
    titles   = package.get("title_options", {})
    short    = titles.get("short", "iron_logos_video")

    if not script:
        logger.error("Package has no full_script field. Cannot produce. Skipping.")
        return None

    # Use script sentences as caption fallback if breakdown is missing
    if not captions:
        logger.warning("No caption_breakdown found. Splitting script by sentence.")
        captions = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script) if s.strip()]

    # ── Build output path ──────────────────────────────────────────────────────
    AUTONOMOUS_PRODUCED_DIR.mkdir(parents=True, exist_ok=True)
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = re.sub(r"[^a-z0-9]+", "_", short.lower()).strip("_")[:40]
    output_mp4 = AUTONOMOUS_PRODUCED_DIR / f"ironlogos_{safe_title}_{timestamp}.mp4"

    # ── Use temp directory for intermediate files ──────────────────────────────
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp        = Path(tmpdir)
        audio_path = tmp / "narration.wav"

        # Step 1: Generate TTS
        logger.info("Step 1/4: TTS narration...")
        if not generate_tts(script, audio_path, logger):
            return None

        # Step 2: Get duration + build captions
        logger.info("Step 2/4: Caption timing...")
        duration = get_audio_duration(audio_path)
        logger.info(f"Audio: {duration:.1f}s")
        ass_content = build_ass_subtitles(captions, duration)

        # Step 3: Background
        logger.info("Step 3/4: Selecting background...")
        bg_source = select_background(logger)
        is_fallback = not (
            BACKGROUNDS_DIR.exists() and
            (list(BACKGROUNDS_DIR.glob("*.mp4")) or list(BACKGROUNDS_DIR.glob("*.mov")))
        )

        # Step 4: Assemble
        logger.info("Step 4/4: Assembling video...")
        success = assemble_video(audio_path, bg_source, ass_content, output_mp4, logger)

        # Clean up fallback background temp file if generated
        if is_fallback and bg_source.exists():
            try:
                bg_source.unlink()
            except Exception:
                pass

        if not success:
            return None

    # ── Update package metadata ────────────────────────────────────────────────
    package.setdefault("_meta", {})
    package["_meta"]["status"]         = "produced"
    package["_meta"]["produced_at"]    = timestamp_str()
    package["_meta"]["produced_video"] = str(output_mp4)
    with open(package_path, "w", encoding="utf-8") as f:
        json.dump(package, f, indent=2)

    size_mb = output_mp4.stat().st_size / (1024 * 1024)
    logger.info(f"COMPLETE: {output_mp4.name} ({size_mb:.1f}MB)")
    logger.info(f"{'='*50}")
    return output_mp4


# ── Dependency Check ───────────────────────────────────────────────────────────

def check_dependencies() -> bool:
    """Verify all Phase 2 dependencies are installed before running."""
    ok = True

    piper_ok = PIPER_BINARY.exists() or shutil.which("piper") is not None
    if not piper_ok:
        print(f"[forge_produce] MISSING: Piper binary not found at {PIPER_BINARY}")
        ok = False

    if not VOICE_MODEL.exists():
        print(f"[forge_produce] MISSING: Voice model not found at {VOICE_MODEL}")
        ok = False

    if shutil.which("ffmpeg") is None:
        print("[forge_produce] MISSING: ffmpeg not installed")
        ok = False

    if not ok:
        print("")
        print("Run the setup script to install everything:")
        print("    bash ~/kd_ai/setup_phase2.sh")

    return ok


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Forge Produce -- Phase 2 Video Production Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 forge_produce.py --file forge_auto_20260521_024939.json\n"
            "  python3 forge_produce.py --all\n\n"
            "Output: ~/kd_ai/content/autonomous/produced/ironlogos_*.mp4\n"
            "Transfer: scp keenus13@192.168.4.155:~/kd_ai/content/autonomous/produced/*.mp4 ."
        ),
    )
    parser.add_argument(
        "--file", "-f",
        type=str, default=None,
        help="Path to a specific approved JSON package to produce",
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Produce all unproduced packages in the approved folder",
    )

    args = parser.parse_args()
    logger = setup_logging("forge_produce")
    setup_directories()

    if not check_dependencies():
        sys.exit(1)

    if args.file:
        # Allow filename only (no path) -- look in approved dir
        path = Path(args.file)
        if not path.exists():
            path = AUTONOMOUS_APPROVED_DIR / args.file
        if not path.exists():
            print(f"[forge_produce] File not found: {args.file}")
            sys.exit(1)

        result = produce_package(path, logger)
        if result:
            print(f"\n[forge_produce] Video ready: {result}")
            print(f"Transfer to Windows:")
            print(f"  scp keenus13@192.168.4.155:{result} C:\\Users\\james\\Desktop\\")
        else:
            print("\n[forge_produce] Production failed. Check logs.")
            sys.exit(1)

    elif args.all:
        packages = sorted(AUTONOMOUS_APPROVED_DIR.glob("*.json"))
        if not packages:
            print("[forge_produce] No approved packages found.")
            return

        produced = 0
        failed   = 0
        for pkg in packages:
            try:
                data   = json.loads(pkg.read_text(encoding="utf-8"))
                status = data.get("_meta", {}).get("status", "")
                if status == "produced":
                    print(f"[forge_produce] Already produced: {pkg.name} -- skipping")
                    continue
            except Exception:
                pass

            result = produce_package(pkg, logger)
            if result:
                produced += 1
            else:
                failed += 1

        print(f"\n[forge_produce] Done. {produced} produced, {failed} failed.")
        if produced:
            print(f"Videos in: ~/kd_ai/content/autonomous/produced/")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
