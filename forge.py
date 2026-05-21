"""
forge.py -- On-Demand Brand Content Generator
Part of: KD Empire / Forge AI Content System
Target: Jetson Orin Nano (~/kd_ai/)

Generates brand content for KD Supply and Liberty Garage Works on request.
Uses the system prompt from ~/kd_ai/system_prompt.txt (paste from Drive doc).

Usage:
    python forge.py                                          # Interactive mode
    python forge.py "Write a caption for our brake pad drop"
    python forge.py -t script "Product launch for truck night"
    python forge.py -t email "Follow up to a new fleet account"
    python forge.py -t ad "Oil filter promo, 3-pack deal"

Content types (-t flag):
    caption   Social media caption with hashtags (default)
    script    Short-form video script, 30-90 seconds
    email     Customer or B2B email with subject line
    post      Long-form social or blog post
    ad        Short punchy ad copy, under 50 words

Output saved to: ~/kd_ai/content/on_demand/
"""

import sys
import argparse
from pathlib import Path

# Make sure forge_core and load_env are importable when running from any directory
sys.path.insert(0, str(Path(__file__).parent))

from forge_core import (
    setup_logging,
    setup_directories,
    get_client,
    get_brand_system_prompt,
    save_content,
    ON_DEMAND_DIR,
    timestamp_str,
)


# ── Content Type Definitions ────────────────────────────────────────────────
# Each entry has a label and an instruction appended to the user's brief.
CONTENT_TYPES = {
    "caption": {
        "label": "Social Media Caption",
        "instruction": (
            "Write a social media caption. Open with a strong hook (under 150 characters). "
            "Follow with 1-2 supporting lines. End with 3-5 relevant hashtags. "
            "No corporate fluff. No emoji overload."
        ),
    },
    "script": {
        "label": "Short Video Script",
        "instruction": (
            "Write a short-form video script that reads in 30-90 seconds. "
            "Format with these labeled sections:\n"
            "[HOOK] - First line only. Arresting, immediate.\n"
            "[BODY] - 2-4 sentences of substance.\n"
            "[CLOSE] - One punchy final line or CTA.\n"
            "Add brief visual cue notes in (parentheses) where useful. "
            "Write it conversational -- no teleprompter stiffness."
        ),
    },
    "email": {
        "label": "Email",
        "instruction": (
            "Write a professional, direct email. No filler. "
            "Format:\n"
            "Subject: [subject line]\n\n"
            "[body -- get to the point in the first sentence]\n\n"
            "[close with a clear next step or ask]"
        ),
    },
    "post": {
        "label": "Long-Form Post",
        "instruction": (
            "Write a long-form social or blog post. "
            "Open with a strong line that makes people stop scrolling. "
            "Give real value or a real story in the body. "
            "Use paragraph breaks -- not a wall of text. "
            "Close with a clear point or call to action."
        ),
    },
    "ad": {
        "label": "Ad Copy",
        "instruction": (
            "Write short ad copy. Under 50 words total. "
            "Structure: punchy hook, one clear benefit, strong CTA. "
            "No hype words. No exclamation marks unless they earn it."
        ),
    },
}


def build_user_prompt(brief: str, content_type: str) -> str:
    """
    Combine the user's brief with the content type instruction.
    This is what gets sent to the model as the user message.
    """
    type_info = CONTENT_TYPES.get(content_type, CONTENT_TYPES["caption"])
    return f"{type_info['instruction']}\n\nBrief: {brief}"


def generate_content(brief: str, content_type: str = "caption") -> dict:
    """
    Call the Anthropic API and generate brand content.

    Args:
        brief:        The content brief from the user
        content_type: One of the keys in CONTENT_TYPES

    Returns:
        A dict containing the generated output and metadata.
        This dict is what gets saved to disk as JSON.
    """
    logger = setup_logging("forge_ondemand")
    setup_directories()

    client, model = get_client()
    system_prompt = get_brand_system_prompt()
    user_prompt = build_user_prompt(brief, content_type)

    type_label = CONTENT_TYPES.get(content_type, {}).get("label", content_type)
    logger.info(f"Generating: {type_label} | Model: {model}")
    logger.info(f"Brief: {brief}")

    # ── API call ────────────────────────────────────────────────────────────
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_prompt}
        ]
    )

    generated_text = response.content[0].text

    # ── Build the output package ────────────────────────────────────────────
    result = {
        "generated_at":     timestamp_str(),
        "mode":             "on_demand",
        "content_type":     content_type,
        "content_type_label": type_label,
        "brief":            brief,
        "model":            model,
        "output":           generated_text,
        "tokens_used": {
            "input":  response.usage.input_tokens,
            "output": response.usage.output_tokens,
        },
    }

    logger.info(
        f"Done. {response.usage.output_tokens} output tokens | "
        f"{response.usage.input_tokens} input tokens"
    )
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Forge -- On-Demand Brand Content Generator for KD Empire",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python forge.py 'New brake pad drop, 3 SKUs in stock'\n"
            "  python forge.py -t script 'KD Supply truck night promo'\n"
            "  python forge.py -t email 'Welcome a new fleet account'\n"
            "  python forge.py -t ad 'Oil filter 3-pack, bulk pricing'"
        )
    )
    parser.add_argument(
        "brief",
        nargs="?",
        help="Content brief or topic. Omit to enter interactively."
    )
    parser.add_argument(
        "--type", "-t",
        default="caption",
        choices=list(CONTENT_TYPES.keys()),
        metavar="TYPE",
        help=(
            "Content type: caption (default), script, email, post, ad. "
            "Example: -t script"
        )
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Print output only -- do not save to file"
    )

    args = parser.parse_args()

    # ── Get brief -- interactive if not passed as argument ──────────────────
    if args.brief:
        brief = args.brief.strip()
    else:
        print("\n[ Forge -- On-Demand Content Generator ]")
        print("Content types: " + ", ".join(CONTENT_TYPES.keys()))
        brief = input("\nBrief (what do you need content for?):\n> ").strip()
        if not brief:
            print("[Forge] No brief provided. Exiting.")
            sys.exit(1)

    # ── Generate ─────────────────────────────────────────────────────────────
    type_label = CONTENT_TYPES.get(args.type, {}).get("label", args.type)
    print(f"\n[Forge] Generating {type_label}...")

    result = generate_content(brief, args.type)

    # ── Print output ─────────────────────────────────────────────────────────
    print("\n" + "=" * 62)
    print(f"  {result['content_type_label'].upper()}")
    print("=" * 62)
    print(result["output"])
    print("=" * 62)
    print(
        f"Tokens: {result['tokens_used']['input']} in / "
        f"{result['tokens_used']['output']} out"
    )

    # ── Save to disk ─────────────────────────────────────────────────────────
    if not args.no_save:
        saved_path = save_content(result, ON_DEMAND_DIR, prefix="forge_ondemand")
        print(f"Saved to: {saved_path}")


if __name__ == "__main__":
    main()
