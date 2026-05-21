"""
forge_auto.py -- Autonomous Philosophical Content Generator
Part of: KD Empire / Forge AI Content System
Target: Jetson Orin Nano (~/kd_ai/)

Generates daily philosophical short-form video content packages for TikTok / YouTube Shorts.
No brand affiliation -- standalone philosophical channel, separate identity from all KD brands.
Monetization: TikTok Creator Fund + YouTube Shorts ad revenue (passive income).

Format reference: LearnFromChristOfficial aesthetic lane.
-- Slow, weighted TTS narration (wise narrator cadence)
-- Classical/timeless imagery (Renaissance paintings, marble statues, storms, fire, ruins)
-- Bold caption overlays synced phrase-by-phrase with voiceover
-- 3-second hook rule -- earn attention immediately
-- Hook -> one developed idea -> resolution (thought to sit with)
-- No CTAs in autonomous content

Target runtime: 60-120 seconds (160-300 spoken words at wise narrator pace)
Monetization threshold: 60+ seconds qualifies for TikTok Creator Fund + YouTube Shorts revenue

Editorial Guardrails:
    GREEN  -- Go freely. Stoicism, existentialism, Eastern philosophy, discipline,
              self-mastery, suffering as teacher, classical masculine virtue (courage,
              duty, sacrifice, builder ethos), critique of modernity (philosophical),
              mortality, legacy, time as currency, beauty and the sublime, great
              builders and thinkers in history, universal spiritual themes, gender
              (classical virtue framing), aesthetics, ancient wisdom traditions

    YELLOW -- Approach with care but not off-limits. "Why modern X is weak" without
              naming enemies. Religious themes -- universal language over specific
              tradition. Gender commentary -- classical virtue OK, modern dating
              discourse use carefully. Identity -- classical framing only.

    TRUE RED -- Never. These risk platform bans and demonetization:
              Conspiracy theories and disinfo, health/medical claims,
              direct attacks on specific named living individuals,
              calls to action against any group.

Phase 1 (current): Text content packages only. Output to queue for Kian review.
Phase 2 (future): Full local pipeline -- Piper TTS + ffmpeg + auto YouTube upload.

Queue workflow:
    Generated -> ~/kd_ai/content/autonomous/queue/     (awaiting review)
    Approved  -> ~/kd_ai/content/autonomous/approved/  (ready for production)
    Rejected  -> ~/kd_ai/content/autonomous/rejected/  (archived, not used)

Usage:
    python3 forge_auto.py                          # Generate 1 script (normal cron run)
    python3 forge_auto.py --count 3                # Generate a batch of 3
    python3 forge_auto.py --topic "memento mori"  # Force a specific topic
    python3 forge_auto.py --list-topics            # Show topic pool and exit

Cron setup on Jetson (8am daily):
    0 8 * * * cd ~/kd_ai && python3 forge_auto.py >> ~/kd_ai/logs/cron.log 2>&1

Output: ~/kd_ai/content/autonomous/queue/forge_auto_YYYYMMDD_HHMMSS.json
"""

import sys
import json
import random
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from forge_core import (
    setup_logging,
    setup_directories,
    get_client,
    save_content,
    AUTONOMOUS_QUEUE_DIR,
    timestamp_str,
)


# ── System Prompt ─────────────────────────────────────────────────────────────
AUTONOMOUS_SYSTEM_PROMPT = """You are a philosophical content writer producing short-form video scripts for a
standalone philosophical channel on TikTok and YouTube Shorts. This channel has zero
brand affiliation. It exists purely to deliver timeless wisdom to people running on
a higher frequency -- viewers seeking meaning, discipline, and perspective rather
than entertainment.

FORMAT MODEL: The aesthetic of LearnFromChristOfficial -- not the religious specificity,
the FORMAT. Slow, weighted TTS narration with a wise narrator cadence. Classical imagery.
Bold caption overlays synced phrase by phrase. Arresting and contemplative.

STRUCTURE (non-negotiable):
- HOOK: Earns attention in 3 seconds flat. One striking statement or question.
  No warmup. No greeting. Start in the middle of the thought.
- BODY: Develops exactly ONE idea. Historical reference or concrete example required.
  No tangents. No lists. One thread, pulled tight.
- CLOSE: A single line the viewer will sit with after the video ends.
  Not a summary. Not a CTA. A thought that lands and stays.

VOICE: Calm. Authoritative. Slightly austere. Like someone who has read everything
and sees no need to impress you. Never preachy. Never urgent. The opposite of hype.

TARGET RUNTIME: 60-120 seconds when read aloud at a slow, deliberate pace.
That means 160-300 spoken words for the full script. Hit this range.

CONTENT THAT WORKS IN THIS LANE:
Stoicism, existentialism, Eastern philosophy, Jungian ideas, discipline and self-mastery,
suffering as teacher and forge, classical masculine virtue (courage, duty, sacrifice,
builder ethos), critique of modernity through a philosophical lens, mortality and memento mori,
legacy and what outlasts a life, time as the ultimate currency, beauty and the sublime,
great builders and thinkers in history, universal spiritual and metaphysical themes,
the nature of strength and weakness, the examined life, what civilization was built on.

WHAT TO NEVER GENERATE:
Conspiracy theories, health or medical claims, direct attacks on named living individuals,
calls to action against any group. These risk platform bans. Everything else is territory
worth exploring with intelligence and care.

OUTPUT FORMAT -- respond with ONLY a valid JSON object, no other text, no markdown fences:
{
  "title_options": {
    "tiktok": "Hook-driven TikTok title -- punchy, scroll-stopping, under 60 chars",
    "youtube": "SEO-friendly YouTube Shorts title -- searchable, under 70 chars",
    "short": "3-5 word short title for file naming"
  },
  "three_second_hook": "The very first sentence only -- must stop a scrolling thumb cold",
  "hook": "Full opening section -- 1-2 sentences, sets the philosophical tension",
  "body": "Middle section -- develops one idea, 5-8 sentences, includes a historical reference",
  "close": "Final line only -- the thought that lingers after the video ends",
  "full_script": "Complete narration from first word to last, formatted for TTS reading. Paragraph breaks between hook, body, and close. 160-300 words.",
  "word_count": 185,
  "caption_breakdown": [
    "Short phrase 1 for caption overlay",
    "Short phrase 2 for caption overlay",
    "Each entry is one caption beat -- 4 to 8 words max",
    "Cover the entire script from hook to close"
  ],
  "imagery_prompts": [
    "Specific visual search term for opening shot -- e.g. marble Roman bust dramatic studio lighting black background",
    "Specific visual for body section -- e.g. ancient ruins golden hour atmospheric fog",
    "Specific visual for close -- e.g. single candle flame dark background slow motion"
  ],
  "hashtags": {
    "tiktok": "#stoicism #philosophy #wisdom #discipline #mindset #ancientwisdom #selfmastery",
    "youtube": "#stoicism #philosophy #shorts #wisdom #ancientphilosophy"
  },
  "tts_notes": "Specific pacing and emphasis notes for the TTS voice -- where to pause, what to stress, overall cadence instruction",
  "runtime_estimate": "75 seconds",
  "guardrail_category": "GREEN or YELLOW",
  "topic_tags": ["tag1", "tag2", "tag3"]
}"""


# ── Topic Pool ────────────────────────────────────────────────────────────────

GREEN_TOPICS = [
    # Stoic canon
    "the Stoic view on complaining",
    "what Marcus Aurelius wrote about waking up to do hard work",
    "why Seneca thought most people waste their entire lives",
    "amor fati -- the Stoic practice of loving your fate completely",
    "Epictetus the slave philosopher and what he understood about freedom",
    "memento mori -- why ancient people kept reminders of death on their desks",
    "why the Stoics practiced voluntary discomfort and deprivation",
    "the Stoic view on reputation versus actual character",
    "why Seneca wrote that we suffer more in imagination than in reality",
    "the Stoic practice of negative visualization -- imagining everything lost",
    "the Stoic technique of the view from above",
    "Epictetus on the dichotomy of control -- what is yours and what never was",
    "the concept of the inner citadel -- where no external force can follow",
    "what Marcus Aurelius wrote the night before a military campaign",
    "why Marcus Aurelius said obstacles are not in the way -- they are the way",
    "what the Stoics wrote about how to face death without flinching",
    "why the Stoics kept journals and what they actually wrote in them",
    "Marcus Aurelius on how quickly everything is forgotten by history",
    "the Stoic practice of premortem -- imagining your failure in advance",
    "the Stoic view on criticism from men of lesser quality",
    "what Seneca meant by retreating into yourself as much as possible",
    "why the Stoics thought philosophy was a daily practice, not a belief",
    "the Stoic reserved action -- planning without attachment to outcome",

    # Classical and masculine virtue
    "arete -- the ancient Greek concept of excellence as a daily practice",
    "what Aristotle meant by eudaimonia and why it has nothing to do with happiness",
    "Roman dignitas -- what it actually meant and why we lost it",
    "the ancient craft ethic -- what it means to do work with full commitment",
    "the philosophy of the craftsman -- mastery as the original form of meaning",
    "why Aristotle thought habit was the true architect of character",
    "what Cato the Elder said about idleness and soft men",
    "the classical view on courage as the foundation of all other virtues",
    "what ancient Romans meant by duty -- and why it has no modern equivalent",
    "the builder ethos -- why great civilizations were built by men who made things",
    "the ancient concept of honor and why modern men traded it for comfort",

    # Mortality and legacy
    "the philosophy of legacy -- what you leave without your name attached",
    "what it means to live as though today could be your last -- without the cliche",
    "why ancient philosophers thought about death every single morning",
    "the Stoic view on grief and loss -- feeling it without being destroyed by it",
    "kairos versus chronos -- the right moment versus the endless clock",
    "why Seneca said the value of a single well-spent day cannot be measured",
    "what Marcus Aurelius said about the brevity of fame and the silence after",
    "the ancient understanding of time as the only currency that cannot be earned back",

    # Philosophy and wisdom traditions
    "why Socrates said the unexamined life is not worth living -- and meant it",
    "what Plato's allegory of the cave says about the reality most people accept",
    "what Heraclitus meant by the river you cannot step into twice",
    "the philosophy of enough -- the ancient case against wanting without end",
    "why ancient philosophers were deeply suspicious of the mob and the crowd",
    "the ancient practice of philosophical mentorship and why it disappeared",
    "why Zeno of Citium built something extraordinary from total shipwreck",
    "what Epictetus, born in chains, understood about the free man",
    "the Stoic view on wealth -- having it versus being owned by it",

    # Self-mastery and discipline
    "why discipline is not restriction -- it is the only real form of freedom",
    "the ancient view on suffering as the forge that creates the capable man",
    "why the Stoics thought anger was always a choice, never an inevitability",
    "the philosophy of voluntary hardship -- why easy lives produce weak men",
    "what it means to want what you already have -- and why it is the hardest thing",
    "the ancient understanding of resilience -- bending completely without breaking",
    "why ancient thinkers believed solitude was not optional for a serious man",

    # Modernity critique and classical contrast
    "why the ancient world revered the builder and the modern world reveres the commentator",
    "what classical masculine virtue actually demanded -- and what it produced",
    "the philosophical case for silence in a world that rewards noise above all",
    "what ancient philosophy says about distraction as a form of slow death",
    "why the Stoics believed the examined life required removing the unnecessary",
    "the ancient concept of the worthy opponent -- why you need resistance to grow",
    "beauty and the sublime -- why ancient thinkers thought ugliness was a cultural symptom",

    # Eastern philosophy crossover
    "what the Stoics and the Taoists agreed on about the nature of resistance",
    "the Buddhist concept of impermanence and what the Stoics independently discovered",
    "wu wei -- the ancient Chinese principle of effortless action and why it is not laziness",
    "what Lao Tzu and Marcus Aurelius would have agreed on about power",
    "the Zen concept of beginner's mind and why mastery requires returning to it",
]

YELLOW_TOPICS = [
    "why the modern man was never taught what strength actually requires",
    "what the ancient world understood about masculine initiation that we no longer practice",
    "the philosophical case for why comfort is the enemy the Stoics warned about",
    "what happens to a civilization when it forgets what it was built on",
    "the ancient view on why weakness in leadership destroys more than open war",
    "universal spiritual themes -- what every wisdom tradition agrees on about suffering",
    "the philosophy of redemption -- ancient frameworks without modern sentimentality",
    "why every great spiritual tradition placed suffering at the center of real growth",
    "what classical philosophy says about the man who has never been tested",
    "the ancient case for why trials are not obstacles to a good life -- they are the path",
]

TOPIC_POOL = GREEN_TOPICS + YELLOW_TOPICS


def pick_topic(force_topic: str = None) -> tuple:
    """
    Select a topic for this generation run.
    Returns (topic_string, guardrail_category).
    Weighted draw: ~85% GREEN, ~15% YELLOW.
    """
    if force_topic:
        category = "YELLOW" if force_topic in YELLOW_TOPICS else "GREEN"
        return force_topic, category

    if random.random() < 0.85 or not YELLOW_TOPICS:
        return random.choice(GREEN_TOPICS), "GREEN"
    else:
        return random.choice(YELLOW_TOPICS), "YELLOW"


def generate_script(topic: str, guardrail_hint: str = "GREEN") -> dict:
    """
    Call the Anthropic API and generate a full philosophical content package.

    Returns a dict containing:
    - title_options (TikTok / YouTube / short)
    - three_second_hook, hook, body, close, full_script
    - word_count, runtime_estimate
    - caption_breakdown (phrase-by-phrase list for overlay sync)
    - imagery_prompts (specific, searchable visual references)
    - hashtags (TikTok and YouTube sets)
    - tts_notes, topic_tags, guardrail_category
    - _meta (generation metadata, status, phase)
    """
    logger = setup_logging("forge_auto")
    setup_directories()

    client, model = get_client()

    user_prompt = (
        f"Generate a complete philosophical short-form video content package.\n"
        f"Topic: {topic}\n"
        f"Guardrail category: {guardrail_hint}\n"
        f"Target runtime: 60-120 seconds (160-300 spoken words, slow wise narrator pace)\n\n"
        f"Output ONLY valid JSON -- no explanation, no markdown code fences, just the object."
    )

    logger.info(f"Topic: {topic} | Guardrail: {guardrail_hint} | Model: {model}")

    # ── API call ──────────────────────────────────────────────────────────────
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=AUTONOMOUS_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": user_prompt}
        ]
    )

    raw_text = response.content[0].text.strip()

    # ── Parse JSON -- with markdown fence cleanup fallback ────────────────────
    try:
        script_data = json.loads(raw_text)
        parse_ok = True
    except json.JSONDecodeError as e:
        logger.warning(f"Initial JSON parse failed: {e} -- attempting cleanup")
        cleaned = raw_text
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            start = 1 if lines[0].startswith("```") else 0
            end = -1 if lines[-1].strip() == "```" else len(lines)
            cleaned = "\n".join(lines[start:end])
        try:
            script_data = json.loads(cleaned)
            parse_ok = True
            logger.info("JSON parsed successfully after cleanup.")
        except json.JSONDecodeError:
            logger.warning("JSON parse failed after cleanup. Storing raw output as fallback.")
            script_data = {
                "title_options": {"short": topic[:50]},
                "full_script": raw_text,
                "guardrail_category": guardrail_hint,
                "_parse_error": "Model returned non-JSON -- stored raw output",
            }
            parse_ok = False

    # ── Attach generation metadata ─────────────────────────────────────────────
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
        "status": "queued",   # queued -> approved or rejected (moved manually by Kian)
        "phase":  "1",        # Phase 1 = text package only. Phase 2 = full video assembly.
    }

    title = (
        script_data.get("title_options", {}).get("short")
        or script_data.get("title_options", {}).get("tiktok")
        or "(untitled)"
    )
    runtime = script_data.get("runtime_estimate", "?")
    words = script_data.get("word_count", "?")

    logger.info(
        f"Package: '{title}' | ~{runtime} | {words} words | "
        f"{response.usage.output_tokens} tokens | JSON: {'OK' if parse_ok else 'FALLBACK'}"
    )

    return script_data


def run_generation(count: int = 1, force_topic: str = None) -> list:
    """
    Full generation cycle: pick topic(s), generate package(s), save to queue.
    Returns list of saved file Paths.
    """
    setup_directories()
    saved_files = []

    print(f"\n[ Forge Auto | {timestamp_str()} ]")
    print(f"Generating {count} content package(s)...\n")

    for i in range(count):
        if count > 1:
            print(f"--- Package {i + 1} of {count} ---")

        topic, guardrail = pick_topic(force_topic)
        print(f"Topic:     {topic}")
        print(f"Guardrail: {guardrail}")

        package = generate_script(topic, guardrail)

        title = (
            package.get("title_options", {}).get("tiktok")
            or package.get("title_options", {}).get("short")
            or "(untitled)"
        )
        hook = package.get("three_second_hook") or package.get("hook", "")
        runtime = package.get("runtime_estimate", "?")
        words = package.get("word_count", "?")

        print(f"Title:     {title}")
        if hook:
            print(f"Hook:      {hook[:100]}")
        print(f"Runtime:   ~{runtime} | Words: {words}")

        saved_path = save_content(package, AUTONOMOUS_QUEUE_DIR, prefix="forge_auto")
        saved_files.append(saved_path)

        if count > 1 and i < count - 1:
            print()

    print(f"\n[Forge Auto] Done. {len(saved_files)} package(s) in queue.")
    print(f"Review:  ~/kd_ai/content/autonomous/queue/")
    print(f"Approve: mv <file> ~/kd_ai/content/autonomous/approved/")
    return saved_files


def list_topics():
    """Print the full topic pool to the console."""
    print(f"\n[ Forge Auto -- Topic Pool ({len(TOPIC_POOL)} total) ]\n")
    print(f"GREEN zone ({len(GREEN_TOPICS)} topics):")
    for i, t in enumerate(GREEN_TOPICS, 1):
        print(f"  {i:2}. {t}")
    print(f"\nYELLOW zone ({len(YELLOW_TOPICS)} topics):")
    for i, t in enumerate(YELLOW_TOPICS, 1):
        print(f"  {i:2}. {t}")


def main():
    parser = argparse.ArgumentParser(
        description="Forge Auto -- Autonomous Philosophical Content Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 forge_auto.py                        # Daily cron run\n"
            "  python3 forge_auto.py --count 5              # Batch of 5\n"
            "  python3 forge_auto.py --topic 'amor fati'    # Force topic\n"
            "  python3 forge_auto.py --list-topics          # Show topic pool\n\n"
            "Cron (8am daily):\n"
            "  0 8 * * * cd ~/kd_ai && python3 forge_auto.py >> ~/kd_ai/logs/cron.log 2>&1"
        )
    )
    parser.add_argument("--count", "-n", type=int, default=1,
                        help="Number of packages to generate (default: 1)")
    parser.add_argument("--topic", "-t", default=None,
                        help="Force a specific topic instead of random selection")
    parser.add_argument("--list-topics", action="store_true",
                        help="Print all available topics and exit")

    args = parser.parse_args()

    if args.list_topics:
        list_topics()
        sys.exit(0)

    run_generation(count=args.count, force_topic=args.topic)


if __name__ == "__main__":
    main()
