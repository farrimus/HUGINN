"""Load structure configurations from JSON files.

Directory: data/structures/{structure_id}.json
One file per structure; filename must match id field.
"""

import json
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

REQUIRED_FIELDS = [
    "id",
    "system_name",
    "owner_address",
    "tier_registry_object_id",
    "ssu_object_id"
]


def validate_structure(struct: dict) -> None:
    """Validate a structure config dict.

    Checks required fields; adds sensible defaults for optional fields.
    Modifies struct in-place.

    Args:
        struct: Structure dict to validate

    Raises:
        ValueError if required fields missing or invalid
    """
    # Check required fields
    missing = [f for f in REQUIRED_FIELDS if f not in struct]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")

    # Apply defaults for optional fields
    if "services" not in struct:
        struct["services"] = []
    if "polling_enabled" not in struct:
        struct["polling_enabled"] = True


def load_structures_from_directory(directory: str) -> list[dict]:
    """Load all structure configs from data/structures/*.json.

    Each file must:
    - Be named {id}.json
    - Contain JSON with matching "id" field
    - Have all required fields (see REQUIRED_FIELDS)

    Returns:
        List of structure dicts, sorted by ID

    Raises:
        FileNotFoundError if directory doesn't exist
        ValueError if any JSON is malformed or invalid
    """
    struct_dir = Path(directory)

    # Create directory if it doesn't exist (first-time setup)
    if not struct_dir.exists():
        struct_dir.mkdir(parents=True, exist_ok=True)
        return []

    structures = []

    # Load all .json files from directory, sorted by filename
    for json_file in sorted(struct_dir.glob("*.json")):
        # Skip template files
        if json_file.name == "TEMPLATE.json":
            continue

        try:
            with open(json_file) as f:
                struct = json.load(f)

            # Validate required fields
            validate_structure(struct)

            # Check filename matches ID
            expected_filename = f"{struct['id']}.json"
            if json_file.name != expected_filename:
                raise ValueError(
                    f"Filename {json_file.name} doesn't match ID '{struct['id']}' "
                    f"(expected {expected_filename})"
                )

            structures.append(struct)
            log.debug(f"Loaded structure: {struct['id']}")

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {json_file.name}: {e}")
        except Exception as e:
            raise ValueError(f"Error loading {json_file.name}: {e}")

    return structures


def get_structure_by_id(structures: list[dict], structure_id: str) -> Optional[dict]:
    """Find a structure by ID.

    Args:
        structures: List of structure dicts
        structure_id: ID to search for

    Returns:
        Structure dict or None if not found
    """
    for struct in structures:
        if struct["id"] == structure_id:
            return struct
    return None
