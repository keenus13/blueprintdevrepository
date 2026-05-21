"""
load_env.py -- Forge Environment Loader
Part of: KD Empire / Forge AI Content System
Target: Jetson Orin Nano (~/kd_ai/)

Loads the .env file from ~/kd_ai/.env and sets environment variables.
Import this at the top of forge.py and forge_auto.py before anything else.

.env file format -- create this on the Jetson at ~/kd_ai/.env:
    ANTHROPIC_API_KEY=sk-ant-...
    FORGE_MODEL=claude-haiku-4-5-20251001

To create it on the Jetson:
    nano ~/kd_ai/.env
    (paste your key, save with Ctrl+X, Y, Enter)
"""

import os
from pathlib import Path


def load_env():
    """
    Load .env file from ~/kd_ai/.env into os.environ.
    Returns the ANTHROPIC_API_KEY value if found, None otherwise.
    """
    env_path = Path.home() / "kd_ai" / ".env"

    if not env_path.exists():
        print(f"[load_env] WARNING: No .env file found at {env_path}")
        print("[load_env] Create ~/kd_ai/.env with: ANTHROPIC_API_KEY=sk-ant-...")
        return None

    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()

            # Skip blank lines and comments
            if not line or line.startswith("#"):
                continue

            # Parse KEY=VALUE pairs
            if "=" not in line:
                continue

            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()

            # Strip surrounding quotes if present
            if (val.startswith('"') and val.endswith('"')) or \
               (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]

            os.environ[key] = val

    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if api_key:
        # Show last 4 chars only -- never log the full key
        print(f"[load_env] API key loaded (...{api_key[-4:]})")
    else:
        print("[load_env] WARNING: ANTHROPIC_API_KEY not found in .env file.")

    return api_key


if __name__ == "__main__":
    # Quick test -- run directly to verify your .env is loading
    key = load_env()
    if key:
        print("[load_env] Test PASSED -- environment loaded successfully.")
    else:
        print("[load_env] Test FAILED -- check ~/kd_ai/.env on the Jetson.")
