"""
src/datahub_types.py

GameType catalog — Datahub World API integration.

Provides DatahubTypeCatalog, responsible for pre-warming and querying
game type metadata (names, descriptions, categories, icons) from the
EVE Frontier Datahub API.

Consumed by SuiAdapter (which inherits it) and indirectly by ai_tools.py
via EntityResolver.
"""

import logging
from typing import Optional

import httpx

log = logging.getLogger(__name__)


class DatahubTypeCatalog:
    """
    Manages the permanent game type cache, populated by prewarm_types() at startup.

    Provides: type lookup, category/name indexing, knowledge block generation.
    Does NOT interact with the Sui blockchain — that lives in SuiAdapter.
    """

    def __init__(self, datahub_host: str) -> None:
        self.datahub_host   = datahub_host
        self._http          = httpx.AsyncClient(timeout=10.0)
        # Permanent type cache: type_id_str -> dict
        self._types: dict[str, dict] = {}
        # Name index: lowercase_name -> list of type_id_str (built after prewarm)
        self._name_index: dict[str, list[str]] = {}
        # Category index: categoryName -> list of type_id_str (built after prewarm)
        self._category_index: dict[str, list[str]] = {}

    async def close(self) -> None:
        await self._http.aclose()

    # -----------------------------------------------------------------------
    # Internal HTTP helper
    # -----------------------------------------------------------------------

    async def _datahub_get(self, path: str) -> Optional[dict]:
        """GET from Datahub World API. Returns parsed JSON or None on error."""
        url = f"https://{self.datahub_host}{path}"
        try:
            resp = await self._http.get(url, timeout=8.0)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            log.warning("datahub_types: request failed %s: %s", path, e)
            return None

    # -----------------------------------------------------------------------
    # Pre-warm GameType cache
    # -----------------------------------------------------------------------

    async def prewarm_types(self) -> None:
        """Fetch all game types from Datahub at startup. Populates permanent type cache."""
        log.info("datahub_types: pre-warming type cache (host=%s)…", self.datahub_host)
        offset = 0
        limit  = 500
        total  = 0
        while True:
            data = await self._datahub_get(f"/v2/types?limit={limit}&offset={offset}")
            if not data:
                break
            items = (
                data if isinstance(data, list)
                else data.get("data") or data.get("items") or data.get("types") or []
            )
            if not items:
                break
            for item in items:
                type_id = str(item.get("id", ""))
                if type_id:
                    self._types[type_id] = item
            total += len(items)
            if len(items) < limit:
                break
            offset += limit
        log.info("datahub_types: type cache pre-warmed (%d types)", total)
        self._build_name_index()
        self._build_category_index()
        try:
            self.write_knowledge_file()
        except Exception as e:
            log.warning("datahub_types: knowledge file write failed: %s", e)

    def _build_name_index(self) -> None:
        """Build lowercase name → [type_id] reverse index from _types cache."""
        index: dict[str, list[str]] = {}
        for type_id, record in self._types.items():
            name = record.get("name", "")
            if not name:
                continue
            key = name.lower()
            index.setdefault(key, []).append(type_id)
        self._name_index = index
        log.info("datahub_types: name index built (%d entries)", len(index))

    def _build_category_index(self) -> None:
        """Build categoryName → [type_id] index from _types cache."""
        index: dict[str, list[str]] = {}
        for type_id, record in self._types.items():
            cat = record.get("categoryName") or "Unknown"
            index.setdefault(cat, []).append(type_id)
        self._category_index = index
        log.info("datahub_types: category index built (%d categories)", len(index))

    def get_all_categories(self) -> dict[str, int]:
        """Return all known categoryNames and the count of types in each."""
        return {cat: len(ids) for cat, ids in self._category_index.items()}

    def get_types_for_category(self, category: str, max_results: int = 50) -> list[dict]:
        """Return up to max_results full type records for a given categoryName."""
        type_ids = self._category_index.get(category, [])[:max_results]
        return [
            self._types[tid]
            for tid in type_ids
            if tid in self._types
        ]

    def get_type_description(self, type_id) -> Optional[str]:
        """Return the description string for a type_id from the cache, or None."""
        record = self._types.get(str(type_id))
        if not record:
            return None
        return record.get("description") or None

    def get_knowledge_block(self, categories: list[str], max_chars: int = 1200) -> str:
        """
        Return a compact 'Name: description.' text block for the given categories.

        Used to auto-inject type knowledge into companion context so HUGINN knows
        what items, ships, and materials are without tool calls.
        """
        lines = []
        for cat in categories:
            type_ids = self._category_index.get(cat, [])
            cat_lines = []
            for tid in type_ids:
                rec = self._types.get(tid, {})
                name = rec.get("name", "")
                desc = (rec.get("description") or "").strip()
                if desc and "." in desc:
                    desc = desc.split(".")[0] + "."
                elif desc and len(desc) > 80:
                    desc = desc[:80] + "…"
                if name:
                    cat_lines.append(f"  {name}: {desc}" if desc else f"  {name}")
            if cat_lines:
                lines.append(f"[{cat}]")
                lines.extend(cat_lines)
        block = "\n".join(lines)
        return block[:max_chars]

    def write_knowledge_file(self, path: str = None) -> None:
        """
        Write all cached types grouped by category to a JSON file.
        Called once after prewarm as a persistent reference.
        """
        import json
        import os
        tenant = getattr(self, "tenant", "unknown")
        if path is None:
            path = f"data/type_knowledge_{tenant}.json"
        catalog: dict[str, list[dict]] = {}
        for cat, type_ids in self._category_index.items():
            catalog[cat] = [
                {
                    "id":          tid,
                    "name":        self._types[tid].get("name", ""),
                    "description": self._types[tid].get("description", ""),
                    "groupName":   self._types[tid].get("groupName", ""),
                }
                for tid in type_ids if tid in self._types
            ]
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(catalog, f, indent=2)
        log.info(
            "datahub_types: type knowledge written to %s (%d categories)",
            path, len(catalog),
        )

    # -----------------------------------------------------------------------
    # GameType lookup
    # -----------------------------------------------------------------------

    async def get_type(self, type_id) -> Optional[dict]:
        """Fetch a game type by ID (str or int). Returns Datahub /v2/types/{id} dict."""
        key = str(type_id)
        cached = self._types.get(key)
        if cached is not None:
            return cached
        data = await self._datahub_get(f"/v2/types/{key}")
        if data:
            self._types[key] = data
        return data

    def search_types_by_name(self, query: str, max_results: int = 5) -> list[dict]:
        """
        Search game types by name. Returns up to max_results full Datahub records.

        Matches in priority order: exact → prefix → substring (all case-insensitive).
        Each result includes: type_id, name, description, groupName, categoryName,
        mass, volume, iconUrl.
        """
        q = query.lower().strip()
        if not q:
            return []

        exact:    list[str] = []
        prefix:   list[str] = []
        contains: list[str] = []

        for name_lower, type_ids in self._name_index.items():
            if name_lower == q:
                exact.extend(type_ids)
            elif name_lower.startswith(q):
                prefix.extend(type_ids)
            elif q in name_lower:
                contains.extend(type_ids)

        ordered = (exact + prefix + contains)[:max_results]
        results = []
        for type_id in ordered:
            record = self._types.get(type_id)
            if record:
                results.append({
                    "type_id":      type_id,
                    "name":         record.get("name", ""),
                    "description":  record.get("description", ""),
                    "groupName":    record.get("groupName", ""),
                    "categoryName": record.get("categoryName", ""),
                    "mass":         record.get("mass"),
                    "volume":       record.get("volume"),
                    "iconUrl":      record.get("iconUrl", ""),
                })
        return results
