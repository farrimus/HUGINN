"""Load prompt templates from prompts/ directory."""
import os

_PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")


def load_prompt(name: str) -> str:
    """Read and return the contents of prompts/{name}.md."""
    path = os.path.join(_PROMPTS_DIR, f"{name}.md")
    with open(path, encoding="utf-8") as f:
        return f.read()


def load_tool_prompts() -> dict:
    """
    Load prompts/tools.yaml into {tool_name: {field: value}}.
    Returns empty dict on missing file so callers fall back to hardcoded descriptions.
    """
    import yaml
    path = os.path.join(_PROMPTS_DIR, "tools.yaml")
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data or {}
    except FileNotFoundError:
        return {}
