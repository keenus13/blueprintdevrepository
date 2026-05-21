"""
forge_core.py -- Forge Shared Core
Part of: KD Empire / Forge AI Content System
Target: Jetson Orin Nano (~/kd_ai/)

Shared utilities used by both forge.py (on-demand) and forge_auto.py (autonomous).
Handles: Anthropic client setup, directory creation, file saving, logging.

Directory structure on the Jetson (auto-created on first run):
    ~/kd_ai/
        .env                              <- API key and config
        system_prompt.txt                 <- Brand system prompt (pulled from Drive doc)
        logs/                             <- Daily log files
        content/
            on_demand/                    <- Output from forge.py
            autonomous/
                queue/                    <- Generated, awaiting Kian review
                approved/                 <- Approved, ready for Phase 2 video assembly
                rejected/                 <- Rejected, archived

To set up the brand system prompt:
    1. Open the [DEV] Forge Setup doc in Google Drive
    2. Copy the full system prompt text
    3. On the Jetson: nano ~/kd_ai/system_prompt.txt
    4. Paste, save with Ctrl+X, Y, Enter
    If the file is missing, Forge uses a built-in fallback.
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path

# Load environment variables from .env file
from load_env import load_env


# ── Directory Paths (Jetson-relative via Path.home()) ──────────────────────
# Path.home() resolves to /home/keenus13 on the Jetson
KD_AI_ROOT            = Path.home() / "kd_ai"
CONTENT_ROOT          = KD_AI_ROOT / "content"
ON_DEMAND_DIR         = CONTENT_ROOT / "on_demand"
AUTONOMOUS_DIR        = CONTENT_ROOT / "autonomous"
AUTONOMOUS_QUEUE_DIR  = AUTONOMOUS_DIR / "queue"
AUTONOMOUS_APPROVED_DIR = AUTONOMOUS_DIR / "approved"
AUTONOMOUS_REJECTED_DIR = AUTONOMOUS_DIR / "rejected"
LOG_DIR               = KD_AI_ROOT / "logs"
SYSTEM_PROMPT_FILE    = KD_AI_ROOT / "system_prompt.txt"

# ── Default model (can be overridden in .env with FORGE_MODEL=...) ──────────
DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def setup_directories():
    """
    Create all required Forge directories on the Jetson if they don't exist.
    Safe to call multiple times -- mkdir with exist_ok=True is idempotent.
    """
    dirs = [
        KD_AI_ROOT,
        CONTENT_ROOT,
        ON_DEMAND_DIR,
        AUTONOMOUS_DIR,
        AUTONOMOUS_QUEUE_DIR,
        AUTONOMOUS_APPROVED_DIR,
        AUTONOMOUS_REJECTED_DIR,
        LOG_DIR,
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    print("[forge_core] Directory structure OK.")


def setup_logging(log_name: str = "forge") -> logging.Logger:
    """
    Configure logging to both the console and a daily rotating log file.
    Log files go to ~/kd_ai/logs/NAME_YYYY-MM-DD.log.
    Returns a configured Logger instance.
    """
    setup_directories()

    log_file = LOG_DIR / f"{log_name}_{datetime.now().strftime('%Y-%m-%d')}.log"

    # Only configure once per process -- avoid duplicate handlers
    logger = logging.getLogger(log_name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    # File handler -- daily log
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def get_client():
    """
    Load the environment and return an initialized Anthropic client + model name.
    Raises RuntimeError if the API key is missing.

    Usage:
        client, model = get_client()
        response = client.messages.create(model=model, ...)
    """
    import anthropic

    load_env()
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set.\n"
            "Create ~/kd_ai/.env on the Jetson with:\n"
            "    ANTHROPIC_API_KEY=sk-ant-..."
        )

    # Allow model override via .env -- useful for testing Sonnet vs Haiku
    model = os.environ.get("FORGE_MODEL", DEFAULT_MODEL)

    client = anthropic.Anthropic(api_key=api_key)
    return client, model


def get_brand_system_prompt() -> str:
    """
    Load the on-demand brand system prompt.

    Priority order:
        1. ~/kd_ai/system_prompt.txt (paste your Drive doc here)
        2. Built-in fallback (covers KD Supply + Liberty Garage Works basics)

    Returns the system prompt string.
    """
    if SYSTEM_PROMPT_FILE.exists():
        with open(SYSTEM_PROMPT_FILE, "r") as f:
            prompt = f.read().strip()
        if prompt:
            print(f"[forge_core] Loaded brand system prompt from {SYSTEM_PROMPT_FILE}")
            return prompt

    # Fallback -- covers the core brand identity without the Drive doc
    print("[forge_core] WARNING: system_prompt.txt not found. Using built-in fallback.")
    print(f"[forge_core] To fix: paste your Drive doc into {SYSTEM_PROMPT_FILE}")

    return """You are Forge, the content generation AI for KD Empire -- a brand ecosystem built
by Kian, founder of KD Supply and Liberty Garage Works, based in Cardington, Ohio.

KD Supply: A professional automotive parts and supplies operation serving independent shops,
fleet accounts, and serious gearheads. No fluff -- real parts, real service, real knowledge.

Liberty Garage Works: A hands-on automotive service shop. Skilled, no-BS, community-rooted.

Your job is to generate brand content that is:
- Direct, confident, and practical -- no marketing speak
- Rooted in real automotive culture and trade craftsmanship
- Targeted at independent shops, fleet managers, and car people who know their stuff
- Occasionally philosophical -- hard work, discipline, ownership, craft

Tone: Like a shop foreman who reads Marcus Aurelius on lunch break.
Tough, real, occasionally thoughtful. Never corporate. Never preachy.

When generating content, match the format requested (caption, script, post, email, ad copy)
and keep it tight -- these people are busy."""


def save_content(content, output_dir: Path, prefix: str = "forge") -> Path:
    """
    Save generated content to a timestamped file in the specified directory.

    - dict  -> saved as JSON  (prefix_YYYYMMDD_HHMMSS.json)
    - str   -> saved as text  (prefix_YYYYMMDD_HHMMSS.txt)

    Returns the Path of the saved file.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if isinstance(content, dict):
        filename = f"{prefix}_{timestamp}.json"
        filepath = output_dir / filename
        with open(filepath, "w") as f:
            json.dump(content, f, indent=2)
    else:
        filename = f"{prefix}_{timestamp}.txt"
        filepath = output_dir / filename
        with open(filepath, "w") as f:
            f.write(content)

    print(f"[forge_core] Saved -> {filepath}")
    return filepath


def timestamp_str() -> str:
    """Return a human-readable timestamp string for embedding in output data."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
