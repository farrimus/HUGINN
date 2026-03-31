"""Load prompt templates from prompts/ directory."""
import os

_PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")


def load_prompt(name: str) -> str:
    """Read and return the contents of prompts/{name}.md."""
    path = os.path.join(_PROMPTS_DIR, f"{name}.md")
    with open(path, encoding="utf-8") as f:
        return f.read()
