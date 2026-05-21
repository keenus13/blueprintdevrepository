"""
forge_auto.py -- Autonomous Philosophical Content Generator
Part of: KD Empire / Forge AI Content System
Target: Jetson Orin Nano (~/kd_ai/)

Generates daily philosophical short-form video scripts for TikTok / YouTube Shorts.
No brand affiliation -- standalone philosophical content channel.
Designed to run unattended via cron.

Editorial Guardrails:
    GREEN  -- Philosophy, discipline, classical virtue, stoicism, history, craft,
              self-mastery, resilience, legacy, time, hard work
    YELLOW -- Modernity critique (handle carefully), non-denominational religion,
              wealth/poverty philosophy (avoid preachiness)
    RED    -- Partisan politics, current events, conspiracy theories,
              named political figures, named religious groups (divisive framing),
              named demographic targets. NEVER generated.

Usage:
    python forge_auto.py                         # Generate 1 script (normal cron use)
    python forge_auto.py --count 3               # Generate a batch of 3 scripts
    python forge_auto.py --topic "amor fati"     # Force a specific topic
    python forge_auto.py --list-topics           # Show full topic pool and exit

Cron setup on Jetson (8am daily):
    Run: crontab -e
    Add: 0 8 * * * cd ~/kd_ai && python forge_auto.py >> ~/kd_ai/logs/cron.log 2>&1

Output: ~/kd_ai/content/autonomous/queue/forge_auto_YYYYMMDD_HHMMSS.json
Each file contains: title, hook, body, close, full_script, imagery_notes,
                    tts_notes, runtime_estimate, topic_tags, guardrail_category,
                    and generation metadata.
"""

import sys
import json
import random
import argparse
from pathlib import Path

# Make sure forge_core and load_env are importable from any directory
sys.path.insert(0, str(Path(__file__).parent))

from forge_core import (
    setup_logging,
    setup_directories,
    get_client,
    save_content,
    AUTONOMOUS_QUEUE_DIR,
    timestamp_str,
)


# ── System Prompt ────────────────────────────────────────────────────────────
# This is baked in -- no external file needed for autonomous mode.
AUTONOMOUS_SYSTEM_PROMPT = """You are a philosophical content writer specializing in short-form video scripts
for TikTok and YouTube Shorts. Your content channel explores ancient wisdom, stoic philosophy,
classical virtue, and timeless ideas about human nature.

No political agenda. No brand affiliation. No culture war framing.
You draw from Stoics (Marcus Aurelius, Epictetus, Seneca, Zeno), Greek philosophers
(Socrates, Plato, Aristotle, Heraclitus), Roman historians, and classical thought generally.

Voice: Calm, direct, slightly austere. Like a teacher who has read everything and speaks plainly.
Never preachy. Never lecturing. More like someone sharing something they have been sitting with.

Script structure:
- HOOK: One arresting opening line or question. No "hey guys." No intro. In medias res.
- BODY: One clear idea, briefly explored. One concrete historical reference or example.
- CLOSE: A single memorable line. Leave them thinking, not sold to.

Target runtime: 30-60 seconds when read aloud (roughly 80-150 spoken words for the full script).

Output format -- respond with ONLY a valid JSON object, no other text, no markdown:
{
  "title": "Short punchy title, under 60 characters",
  "hook": "Opening line only -- the single sentence that opens the video",
  "body": "Middle section, 2-4 sentences",
  "close": "Final line only",
  "full_script": "Complete script formatted for TTS -- hook through close, paragraph breaks OK",
  "imagery_notes": "2-3 specific visual suggestions for the editor (B-roll ideas, text overlay style, visual tone)",
  "tts_notes": "Brief pacing or emphasis notes for the TTS voice (e.g. 'slow and deliberate', 'pause after hook')",
  "runtime_estimate": "Estimated spoken runtime (e.g. '40 seconds')",
  "topic_tags": ["tag1", "tag2", "tag3"],
  "guardrail_category": "GREEN or YELLOW"
}

Stay within GREEN unless a topic genuinely requires YELLOW nuance.
NEVER generate RED content: no partisan politics, no current events, no conspiracy,
no named political figures, no religious groups in a divisive context."""


# ── Topic Pool ───────────────────────────────────────────────────────────────

# GREEN zone -- safe to generate any day, no risk, core content
GREEN_TOPICS = [
    "the Stoic view on complaining",
    "what Marcus Aurelius wrote about waking up to do work",
    "why Seneca thought most people waste their lives",
    "amor fati -- the Stoic practice of loving your fate",
    "Epictetus the slave philosopher and what he understood about freedom",
    "memento mori -- why ancient people kept reminders of death on their desks",
    "why the Stoics practiced voluntary discomfort",
    "what Aristotle meant by eudaimonia and why it is not happiness",
    "arete -- the ancient concept of excellence as a daily practice",
    "why the Stoics believed anger was always a choice",
    "the Stoic view on reputation versus character",
    "why Socrates said the unexamined life is not worth living",
    "the ancient craft ethic -- what it means to do work well",
    "what the Stoics wrote about grief and loss",
    "Roman dignitas and how it differs from modern status",
    "why Seneca wrote that we suffer more in imagination than reality",
    "the Stoic practice of negative visualization",
    "what Heraclitus meant by the river you cannot step in twice",
    "the philosophy of time -- why most people live in the past or the future",
    "the ancient view on discipline as a form of freedom",
    "what Zeno of Citium built after losing everything in a shipwreck",
    "the Stoic view on other people's opinions",
    "the obstacle is the way -- Marcus Aurelius on adversity",
    "the philosophy of the craftsman -- mastery as a form of meaning",
    "what the Stoics wrote about how to face death",
    "kairos versus chronos -- right time versus clock time",
    "the Stoic concept of the reserved action -- planning without attachment",
    "what Plato's allegory of the cave says about perception and reality",
    "the Stoic view on wealth -- having it versus being ruled by it",
    "why the Stoics kept journals and what they wrote in them",
    "the philosophy of legacy -- what you leave without your name on it",
    "what Cato said about idleness",
    "the Stoic technique of the view from above",
    "Epictetus on the dichotomy of control -- what is yours and what is not",
    "what Marcus Aurelius said about how quickly all things are forgotten",
    "the Stoic practice of premortem -- imagining failure before it happens",
    "why ancient philosophers thought solitude was essential",
    "the concept of the inner citadel -- where no one can follow you",
    "what Seneca said about the value of a single well-spent day",
    "the ancient practice of philosophical mentorship",
    "why Aristotle thought habit was the architect of character",
    "the Stoic view on luck -- preparation meeting indifference to outcome",
    "what Marcus Aurelius wrote the night before a military campaign",
    "the philosophy of enough -- the ancient case against endless wanting",
    "why Epictetus said freedom begins when you stop worrying about things outside your control",
    "the Stoic view on criticism from lesser men",
    "what Seneca meant by 'retreat into yourself as much as you can'",
    "why the Stoics thought philosophy was a practice, not a belief system",
    "the ancient understanding of resilience -- bending without breaking",
    "Marcus Aurelius on the brevity of fame",
]

# YELLOW zone -- handle with nuance, deploy sparingly
YELLOW_TOPICS = [
    "the philosophy of what modern life has traded away for comfort",
    "why ancient thinkers were deeply suspicious of the crowd",
    "the ancient tension between tradition and progress",
    "the philosophical case for silence in a world that rewards noise",
    "what ancient philosophy says about attention in an age of distraction",
    "the Stoic view on wealth inequality -- not political, philosophical",
]

# Combined pool for random selection
TOPIC_POOL = GREEN_TOPICS + YELLOW_TOPICS


def pick_topic(force_topic: str = None) -> tuple:
    """
    Select a topic for this generation run.
    Returns a (topic_string, guardrail_category) tuple.

    Without a forced topic, runs ~85% GREEN / ~15% YELLOW by default.
    With a forced topic, classifies it automatically.
    """
    if force_topic:
        # Classify by checking if it matches a known YELLOW topic
        category = "YELLOW" if force_topic in YELLOW_TOPICS else "GREEN"
        return force_topic, category

    # Weighted random draw
    if random.random() < 0.85 or not YELLOW_TOPICS:
        return random.choice(GREEN_TOPICS), "GREEN"
    else:
        return random.choice(YELLOW_TOPICS), "YELLOW"


def generate_script(topic: str, guardrail_hint: str = "GREEN") -> dict:
    """
    Call the Anthropic API and generate a philosophical video script.

    Args:
        topic:          The philosophical topic to write about
        guardrail_hint: "GREEN" or "YELLOW" -- passed as context to the model

    Returns:
        A dict with the script fields and generation metadata.
        If the model returns malformed JSON, wraps raw text as fallback.
    """
    logger = setup_logging("forge_auto")
    setup_directories()

    client, model = get_client()

    user_prompt = (
        f"Generate a philosophical short-form video script on this topic:\n"
        f"Topic: {topic}\n"
        f"Guardrail target: {guardrail_hint}\n\n"
        f"Output ONLY valid JSON -- no explanation, no markdown, just the JSON object."
    )

    logger.info(f"Topic: {topic} | Guardrail: {guardrail_hint} | Model: {model}")

    # ── API call ──────────────────────────────────────────────────────────────
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=AUTONOMOUS_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": user_prompt}
        ]
    )

    raw_text = response.content[0].text.strip()

    # ── Parse JSON response ───────────────────────────────────────────────────
    try:
        script_data = json.loads(raw_text)
        parse_ok = True
    except json.JSONDecodeError as e:
        # Model occasionally wraps JSON in markdown code fences -- try stripping them
        logger.warning(f"Initial JSON parse failed: {e} -- attempting cleanup")
        cleaned = raw_text
        if cleaned.startswith("```"):
            # Strip ```json ... ``` wrapper if present
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else cleaned
        try:
            script_data = json.loads(cleaned)
            parse_ok = True
            logger.info("JSON parsed successfully after cleanup.")
        except json.JSONDecodeError:
            logger.warning("JSON parse failed after cleanup. Storing raw text as fallback.")
            script_data = {
                "title": f"Script -- {topic[:50]}",
                "full_script": raw_text,
                "guardrail_category": guardrail_hint,
                "_parse_error": "Model returned non-JSON -- stored raw output",
            }
            parse_ok = False

    # ── Attach generation metadata ────────────────────────────────────────────
    script_data["_meta"] = {
        "generated_at":    timestamp_str(),
        "mode":            "autonomous",
        "topic_requested": topic,
        "guardrail_hint":  guardrail_hint,
        "model":           model,
        "json_parse_ok":   parse_ok,
        "tokens_used": {
            "input":  response.usage.input_tokens,
            "output": response.usage.output_tokens,
        },
        "status": "queued",   # For future queue-processing scripts
    }

    title = script_data.get("title", "(untitled)")
    logger.info(
        f"Script generated: '{title}' | "
        f"{response.usage.output_tokens} out tokens | "
        f"JSON parse: {'OK' if parse_ok else 'FALLBACK'}"
    )

    return script_data


def run_generation(count: int = 1, force_topic: str = None) -> list:
    """
    Full generation cycle: pick topic(s), generate script(s), save to queue.

    Args:
        count:       Number of scripts to generate
        force_topic: If set, every script in this batch uses this topic

    Returns:
        List of Path objects for the saved files.
    """
    setup_directories()
    saved_files = []

    print(f"\n[ Forge Auto -- Autonomous Generation | {timestamp_str()} ]")
    print(f"Generating {count} script(s)...\n")

    for i in range(count):
        if count > 1:
            print(f"--- Script {i + 1} of {count} ---")

        topic, guardrail = pick_topic(force_topic)
        print(f"Topic:     {topic}")
        print(f"Guardrail: {guardrail}")

        script = generate_script(topic, guardrail)

        # Print a quick preview to console
        title = script.get("title", "(untitled)")
        hook = script.get("hook", "")
        print(f"Title:     {title}")
        if hook:
            print(f"Hook:      {hook[:100]}")

        # Save to queue
        saved_path = save_content(script, AUTONOMOUS_QUEUE_DIR, prefix="forge_auto")
        saved_files.append(saved_path)

        if count > 1 and i < count - 1:
            print()  # Spacing between scripts in batch mode

    print(f"\n[Forge Auto] Complete. {len(saved_files)} script(s) saved to queue.")
    return saved_files


def list_topics():
    """Print the full topic pool to the console."""
    print(f"\n[ Forge Auto -- Topic Pool ({len(TOPIC_POOL)} total) ]\n")
    print("GREEN zone topics (core content, always safe):")
    for i, t in enumerate(GREEN_TOPICS, 1):
        print(f"  {i:2}. {t}")
    print(f"\nYELLOW zone topics (handle with nuance, ~15% frequency):")
    for i, t in enumerate(YELLOW_TOPICS, 1):
        print(f"  {i:2}. {t}")
    print(
        f"\nTotal: {len(TOPIC_POOL)} topics | "
        f"{len(GREEN_TOPICS)} GREEN / {len(YELLOW_TOPICS)} YELLOW"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Forge Auto -- Autonomous Philosophical Content Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python forge_auto.py                       # Daily cron run, 1 script\n"
            "  python forge_auto.py --count 5             # Queue batch of 5\n"
            "  python forge_auto.py --topic 'amor fati'   # Force a specific topic\n"
            "  python forge_auto.py --list-topics         # Show topic pool\n\n"
            "Cron setup on Jetson (8am daily):\n"
            "  0 8 * * * cd ~/kd_ai && python forge_auto.py >> ~/kd_ai/logs/cron.log 2>&1"
        )
    )
    parser.add_argument(
        "--count", "-n",
        type=int,
        default=1,
        help="Number of scripts to generate in this run (default: 1)"
    )
    parser.add_argument(
        "--topic", "-t",
        default=None,
        help="Force a specific topic instead of random selection"
    )
    parser.add_argument(
        "--list-topics",
        action="store_true",
        help="Print all available topics and exit"
    )

    args = parser.parse_args()

    if args.list_topics:
        list_topics()
        sys.exit(0)

    run_generation(count=args.count, force_topic=args.topic)


if __name__ == "__main__":
    main()
