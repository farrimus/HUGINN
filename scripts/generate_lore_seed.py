#!/usr/bin/env python3
"""
Generate data/lore_seed.json from data/type_knowledge_stillness.json.

For entries with a game_id: looks up description by ID.
For entries without a game_id (or with empty description): tries name search.
Entries with no usable description get a TODO: placeholder.

Run from project root:
    python scripts/generate_lore_seed.py

After filling all TODO: entries, run:
    python scripts/import_lore.py
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.parent
DATA = ROOT / "data"

# ---------------------------------------------------------------------------
# Load type knowledge
# ---------------------------------------------------------------------------

with open(DATA / "type_knowledge_stillness.json") as f:
    _raw = json.load(f)

# Build flat lookup dicts from the category-grouped structure.
# type_knowledge_stillness.json format: {categoryName: [{id, name, description, groupName}]}

id_map: dict[str, dict] = {}    # str(type_id) -> entry
name_map: dict[str, dict] = {}  # lowercase name -> entry (first match wins)

for category_name, entries in _raw.items():
    for entry in entries:
        entry_with_cat = {**entry, "categoryName": category_name}
        type_id = str(entry.get("id", ""))
        if type_id:
            id_map[type_id] = entry_with_cat
        name = (entry.get("name") or "").lower().strip()
        if name and name not in name_map:
            name_map[name] = entry_with_cat


def _lookup(game_id, search_name: str = None) -> str:
    """
    Return the best available description string for an entry, or empty string.
    Resolution order:
      1. game_id -> id_map (exact)
      2. search_name (or title) -> name_map (exact match)
      3. search_name -> name_map (prefix/substring match)
    """
    # Try by ID first
    if game_id is not None:
        record = id_map.get(str(game_id))
        if record:
            desc = (record.get("description") or "").strip()
            if desc:
                return desc

    # Try exact name match
    if search_name:
        q = search_name.lower().strip()
        record = name_map.get(q)
        if record:
            desc = (record.get("description") or "").strip()
            if desc:
                return desc
        # Try prefix/substring match
        for name_lower, record in name_map.items():
            if name_lower.startswith(q) or q in name_lower:
                desc = (record.get("description") or "").strip()
                if desc:
                    return desc

    return ""


# ---------------------------------------------------------------------------
# Lore entry spec
# Each entry: id, category, title, game_id (or None), tags, aliases,
#             and optionally search_name (overrides title for name lookup).
# ---------------------------------------------------------------------------

SPEC: list[dict] = [
    # --- Setting (5) ---
    dict(id="setting_the_frontier",     category="setting",  title="The Frontier",              game_id=None, tags="frontier,space,universe,new eden,colonization", aliases="the frontier,frontier space"),
    dict(id="setting_the_collapse",     category="setting",  title="The Collapse",              game_id=None, tags="collapse,history,catastrophe,origin,lore", aliases="the collapse,collapse event"),
    dict(id="setting_rogue_drones",     category="setting",  title="Rogue Drones (Setting)",    game_id=None, tags="rogue drones,drones,hostile,setting,lore", aliases="rogue drone lore,drone history"),
    dict(id="setting_riders",           category="setting",  title="The Riders",                game_id=None, tags="riders,entity,unknown,mysterious,ancient", aliases="the riders,ancient riders"),
    dict(id="setting_digital_physics",  category="setting",  title="Digital Physics & Energy",  game_id=None, tags="digital physics,energy,physics,heat,temperature,universe", aliases="digital physics,energy physics"),

    # --- Factions (4) ---
    dict(id="faction_tribes",               category="faction", title="Tribes",               game_id=None, tags="tribe,player,organization,corp,social", aliases="tribe,tribes"),
    dict(id="faction_syndicates",           category="faction", title="Syndicates",           game_id=None, tags="syndicate,player,organization,corp,social", aliases="syndicate,syndicates"),
    dict(id="faction_exclave_ventures",     category="faction", title="Exclave Ventures",     game_id=None, tags="exclave ventures,npc,orphan geist,faction", aliases="exclave,exclave ventures"),
    dict(id="faction_ophidia_operations",   category="faction", title="Ophidia Operations",   game_id=None, tags="ophidia,npc,askur,ophidian,faction", aliases="ophidia,ophidia operations"),

    # --- Game Pillars (5) ---
    dict(id="pillar_realism",               category="pillar", title="Realism",               game_id=None, tags="realism,design,pillar,philosophy", aliases="realism pillar"),
    dict(id="pillar_cruel_survival",        category="pillar", title="Cruel Survival",        game_id=None, tags="cruel survival,survival,pvp,death,risk", aliases="cruel survival"),
    dict(id="pillar_broken_world",          category="pillar", title="Broken World",          game_id=None, tags="broken world,collapse,environment,lore", aliases="broken world"),
    dict(id="pillar_forever_game",          category="pillar", title="Forever Game",          game_id=None, tags="forever game,persistent,long term,economy", aliases="forever game"),
    dict(id="pillar_co_created_universe",   category="pillar", title="Co-Created Universe",   game_id=None, tags="co-created,player driven,sandbox,economy", aliases="co-created universe,player created"),

    # --- Ships (14) ---
    dict(id="ship_wend",    category="ship", title="Wend",   game_id=87698, tags="shuttle,wend,basic,starter,travel", aliases="wend shuttle"),
    dict(id="ship_recurve", category="ship", title="Recurve",game_id=87846, tags="corvette,recurve,combat,short-range", aliases="recurve corvette"),
    dict(id="ship_reflex",  category="ship", title="Reflex", game_id=87847, tags="corvette,reflex,long-range,fuel-efficient,jump", aliases="reflex corvette"),
    dict(id="ship_reiver",  category="ship", title="Reiver", game_id=87848, tags="corvette,reiver,combat,agile", aliases="reiver corvette"),
    dict(id="ship_stride",  category="ship", title="Stride", game_id=91106, tags="corvette,stride,jump,long-range,explorer", aliases="stride corvette"),
    dict(id="ship_carom",   category="ship", title="Carom",  game_id=91107, tags="corvette,carom,jump,ultra-range", aliases="carom corvette"),
    dict(id="ship_usv",     category="ship", title="USV",    game_id=81609, tags="frigate,usv,combat,medium", aliases="usv frigate"),
    dict(id="ship_mcf",     category="ship", title="MCF",    game_id=81904, tags="frigate,mcf,combat", aliases="mcf frigate"),
    dict(id="ship_haf",     category="ship", title="HAF",    game_id=82424, tags="frigate,haf,combat,heavy assault", aliases="haf frigate,heavy assault frigate"),
    dict(id="ship_lai",     category="ship", title="LAI",    game_id=82425, tags="frigate,lai,long-range,jump", aliases="lai frigate"),
    dict(id="ship_lorha",   category="ship", title="LORHA",  game_id=82426, tags="frigate,lorha,long-range,hauler", aliases="lorha frigate"),
    dict(id="ship_tades",   category="ship", title="TADES",  game_id=81808, tags="destroyer,tades,combat", aliases="tades destroyer"),
    dict(id="ship_maul",    category="ship", title="MAUL",   game_id=82430, tags="cruiser,maul,heavy,combat", aliases="maul cruiser"),
    dict(id="ship_chumaq",  category="ship", title="Chumaq", game_id=81611, tags="battlecruiser,chumaq,capital,combat,heavy", aliases="chumaq battlecruiser"),

    # --- Fuel (7) ---
    dict(id="fuel_d1",       category="fuel", title="D1 Fuel",       game_id=88335, tags="fuel,d1,corvette,basic fuel,jump", aliases="d1,d1 fuel,tier 1 fuel"),
    dict(id="fuel_d2",       category="fuel", title="D2 Fuel",       game_id=88319, tags="fuel,d2,frigate,jump fuel", aliases="d2,d2 fuel,tier 2 fuel"),
    dict(id="fuel_sof40",    category="fuel", title="SOF-40 Fuel",   game_id=84868, tags="fuel,sof,sof-40,structure fuel,deployable", aliases="sof40,sof-40,small outpost fuel 40"),
    dict(id="fuel_sof80",    category="fuel", title="SOF-80 Fuel",   game_id=78515, tags="fuel,sof,sof-80,structure fuel", aliases="sof80,sof-80"),
    dict(id="fuel_eu40",     category="fuel", title="EU-40 Fuel",    game_id=78516, tags="fuel,eu,eu-40,energy unit,structure", aliases="eu40,eu-40"),
    dict(id="fuel_eu90",     category="fuel", title="EU-90 Fuel",    game_id=78437, tags="fuel,eu,eu-90,energy unit,structure", aliases="eu90,eu-90"),
    dict(id="fuel_unstable", category="fuel", title="Unstable Fuel", game_id=77818, tags="fuel,unstable,salvage,hazard", aliases="unstable fuel,degraded fuel"),

    # --- Structures (17) ---
    dict(id="structure_ssu",          category="structure", title="Smart Storage Unit",  game_id=None,  search_name="Smart Storage Unit", tags="ssu,storage,smart storage unit,core,base", aliases="ssu,smart storage,storage unit"),
    dict(id="structure_smartgate",    category="structure", title="SmartGate",           game_id=88086, tags="smartgate,gate,travel,jump gate,connection", aliases="smart gate,smartgate,mini gate,small gate"),
    dict(id="structure_smart_turret", category="structure", title="Smart Turret",        game_id=84556, tags="turret,defense,smart turret,weapon", aliases="smart turret,turret,defense structure"),
    dict(id="structure_network_node", category="structure", title="Network Node",        game_id=88092, tags="network node,network,base,core,anchor", aliases="network node,node"),
    dict(id="structure_refuge",       category="structure", title="Refuge",              game_id=87160, tags="refuge,fitting,rest,repair,service", aliases="refuge,safe house"),
    dict(id="structure_nursery",      category="structure", title="Nursery",             game_id=91978, tags="nursery,clone,industry,spawn", aliases="nursery,clone nursery"),
    dict(id="structure_nest",         category="structure", title="Nest",                game_id=91871, tags="nest,hangar,ship storage,parking", aliases="nest,ship hangar"),
    dict(id="structure_printer",      category="structure", title="Printer",             game_id=87119, tags="printer,manufacturing,build,fabrication", aliases="printer,3d printer,fabricator"),
    dict(id="structure_refinery",     category="structure", title="Refinery",            game_id=88063, tags="refinery,processing,ore,materials,industry", aliases="refinery"),
    dict(id="structure_berth",        category="structure", title="Berth",               game_id=88069, tags="berth,industry,production", aliases="berth"),
    dict(id="structure_assembler",    category="structure", title="Assembler",           game_id=88068, tags="assembler,manufacturing,assembly,industry", aliases="assembler"),
    dict(id="structure_relay",        category="structure", title="Relay",               game_id=90184, tags="relay,industry,network,signal", aliases="relay"),
    dict(id="structure_field_cairn",  category="structure", title="Field Cairn",         game_id=93141, tags="field cairn,cairn,deployable,temporary,field", aliases="field cairn,cairn"),
    dict(id="structure_seer",         category="structure", title="SEER",                game_id=89775, tags="seer,misc,deployable,sensor", aliases="seer"),
    dict(id="structure_harbinger",    category="structure", title="HARBINGER",           game_id=89777, tags="harbinger,misc,deployable", aliases="harbinger"),
    dict(id="structure_rainmaker",    category="structure", title="RAINMAKER",           game_id=89779, tags="rainmaker,misc,deployable", aliases="rainmaker"),
    dict(id="structure_monolith",     category="structure", title="Monolith",            game_id=88098, tags="monolith,misc,deployable,rare", aliases="monolith"),

    # --- NPCs (11) ---
    # game_ids 92096-92503 are not in static data — all will get TODO placeholders
    dict(id="npc_rogue_drones",    category="npc", title="Rogue Drones (faction)", game_id=None,  tags="rogue drone,drone,hostile,npc,faction", aliases="rogue drones,drones"),
    dict(id="npc_caird",           category="npc", title="Caird",                  game_id=92096, tags="caird,rogue drone,npc,hostile", aliases="caird drone"),
    dict(id="npc_luthier",         category="npc", title="Luthier",                game_id=92097, tags="luthier,rogue drone,npc,hostile", aliases="luthier drone"),
    dict(id="npc_ostler",          category="npc", title="Ostler",                 game_id=92098, tags="ostler,rogue drone,npc,hostile", aliases="ostler drone"),
    dict(id="npc_wright",          category="npc", title="Wright",                 game_id=92099, tags="wright,rogue drone,npc,hostile", aliases="wright drone"),
    dict(id="npc_shambler",        category="npc", title="Shambler",               game_id=92100, tags="shambler,rogue drone,npc,hostile", aliases="shambler drone"),
    dict(id="npc_dowser",          category="npc", title="Dowser",                 game_id=92101, tags="dowser,rogue drone,npc,hostile", aliases="dowser drone"),
    dict(id="npc_scrivener",       category="npc", title="Scrivener",              game_id=92102, tags="scrivener,rogue drone,npc,hostile", aliases="scrivener drone"),
    dict(id="npc_grave_variants",  category="npc", title="Grave Variants",         game_id=92271, tags="grave,elite,rogue drone,npc,elite tier", aliases="grave drone,elite drone"),
    dict(id="npc_watcher",         category="npc", title="Watcher",                game_id=92503, tags="watcher,npc,observer,hostile", aliases="watcher"),
    dict(id="npc_riders",          category="npc", title="The Riders",             game_id=None,  tags="riders,entity,mysterious,ancient,npc", aliases="the riders,riders"),

    # --- Ores (11) --- no individual game_ids; search_name targets the family name in static data
    dict(id="ore_crude_matter",     category="ore", title="Crude Matter",      game_id=None, search_name="Crude Matter",          tags="crude matter,rift,rare,valuable,ore", aliases="crude matter,rift ore"),
    dict(id="ore_char",             category="ore", title="Char belt ores",    game_id=None, search_name="Feldspar Crystals",     tags="char,feldspar,belt ore,common", aliases="char ore,feldspar crystals"),
    dict(id="ore_slag",             category="ore", title="Slag belt ores",    game_id=None, search_name="Platinum-Palladium",   tags="slag,platinum,palladium,belt ore", aliases="slag ore,platinum-palladium matrix"),
    dict(id="ore_ingot",            category="ore", title="Ingot belt ores",   game_id=None, search_name="Iridosmine",            tags="ingot,iridosmine,belt ore", aliases="ingot ore,iridosmine nodules"),
    dict(id="ore_comet",            category="ore", title="Comet belt ores",   game_id=None, search_name="Hydrated Sulfide",      tags="comet,hydrated sulfide,belt ore", aliases="comet ore,hydrated sulfide matrix"),
    dict(id="ore_dewdrop",          category="ore", title="Dewdrop belt ores", game_id=None, search_name="Methane Ice",           tags="dewdrop,methane ice,belt ore,ice", aliases="dewdrop ore,methane ice shards"),
    dict(id="ore_ember",            category="ore", title="Ember belt ores",   game_id=None, search_name="Primitive Kerogen",     tags="ember,kerogen,belt ore", aliases="ember ore,primitive kerogen matrix"),
    dict(id="ore_glint",            category="ore", title="Glint belt ores",   game_id=None, search_name="Aromatic Carbon",       tags="glint,aromatic carbon,belt ore", aliases="glint ore,aromatic carbon veins"),
    dict(id="ore_soot",             category="ore", title="Soot belt ores",    game_id=None, search_name="Tholin",                tags="soot,tholin,belt ore", aliases="soot ore,tholin nodules"),
    dict(id="ore_hermetite",        category="ore", title="Hermetite",         game_id=None, search_name="Hermetite",             tags="hermetite,fluid,crystallizing,stale,sediment,ore", aliases="hermetite ore"),
    dict(id="ore_deep_core_carbon", category="ore", title="Deep-Core Carbon",  game_id=78429, tags="deep core carbon,rare ore,deep,mining", aliases="deep core carbon,deep-core carbon"),

    # --- Rogue Drone Materials (5) --- all have empty descriptions in static data
    dict(id="material_gravionite",     category="material", title="Gravionite",      game_id=83891, tags="gravionite,rogue drone,material,rare", aliases="gravionite"),
    dict(id="material_luminalis",      category="material", title="Luminalis",       game_id=83892, tags="luminalis,rogue drone,material,rare", aliases="luminalis"),
    dict(id="material_eclipsite",      category="material", title="Eclipsite",       game_id=83893, tags="eclipsite,rogue drone,material,rare", aliases="eclipsite"),
    dict(id="material_radiantium",     category="material", title="Radiantium",      game_id=83894, tags="radiantium,rogue drone,material,rare", aliases="radiantium"),
    dict(id="material_catalytic_dust", category="material", title="Catalytic Dust",  game_id=83899, tags="catalytic dust,rogue drone,material,crafting", aliases="catalytic dust"),

    # --- Key Materials (7) ---
    dict(id="material_feral_echo",  category="material", title="Feral Echo",    game_id=88564, tags="feral echo,material,key material,rare,crafting", aliases="feral echo"),
    dict(id="material_still_knot",  category="material", title="Still Knot",    game_id=88565, tags="still knot,material,key material,rare,crafting", aliases="still knot"),
    dict(id="material_echo_chamber",category="material", title="Echo Chamber",  game_id=88780, tags="echo chamber,material,crafting", aliases="echo chamber"),
    dict(id="material_sophrogon",   category="material", title="Sophrogon",     game_id=77728, tags="sophrogon,material,crafting", aliases="sophrogon"),
    dict(id="material_palladium",   category="material", title="Palladium",     game_id=99001, tags="palladium,material,metal,crafting", aliases="palladium"),
    dict(id="material_salt",        category="material", title="Salt",          game_id=83839, tags="salt,material,eve,currency,crafting", aliases="salt,$eve,eve token"),
    dict(id="material_feral_data",  category="material", title="Feral Data",   game_id=72244, tags="feral data,data,rogue drone,analysis,material", aliases="feral data"),

    # --- Key Items (8) ---
    dict(id="item_ophidian_sensor_cloak",  category="item", title="Ophidian Sensor Cloak",      game_id=73192, tags="ophidian sensor cloak,cloak,stealth,ophidia,item", aliases="ophidian cloak,sensor cloak"),
    dict(id="item_askur_access_code",      category="item", title="Askur Access Code Cypher",   game_id=73210, tags="askur,access code,cypher,ophidia,item,key", aliases="askur access code,askur cypher"),
    dict(id="item_fossilized_exotronics",  category="item", title="Fossilized Exotronics",      game_id=83818, tags="fossilized exotronics,exotronics,rare,crafting,item", aliases="fossilized exotronics,exotronics"),
    dict(id="item_network_pollinator",     category="item", title="Network Pollinator",         game_id=83982, tags="network pollinator,pollinator,network,item", aliases="network pollinator"),
    dict(id="item_void_residue",           category="item", title="Void Residue",               game_id=91206, tags="void residue,residue,rare,item", aliases="void residue"),
    dict(id="item_calamitous_marrow",      category="item", title="Calamitous Marrow",          game_id=91937, tags="calamitous marrow,marrow,rare,item", aliases="calamitous marrow"),
    dict(id="item_mummified_clone",        category="item", title="Mummified Clone",            game_id=88765, tags="mummified clone,clone,rare,item", aliases="mummified clone"),
    dict(id="item_reaping_shell",          category="item", title="Reaping Shell",              game_id=91749, tags="reaping shell,shell,combat,item", aliases="reaping shell"),

    # --- Mechanics (6) ---
    dict(id="mechanic_energy_heat",     category="mechanic", title="Energy & Heat System",   game_id=None, tags="energy,heat,temperature,specific heat,adaptive level,heat ejectors,jump", aliases="heat system,energy system,temperature"),
    dict(id="mechanic_jump_drive",      category="mechanic", title="Jump Drive",             game_id=None, tags="jump drive,jump,fuel,range,light years,travel", aliases="jump drive,jump range"),
    dict(id="mechanic_warp",            category="mechanic", title="Intra-System Warp",      game_id=None, tags="warp,intra-system,warp accelerator,travel,fast travel", aliases="warp,intra system warp,warp accelerator"),
    dict(id="mechanic_networks",        category="mechanic", title="Network Topology",       game_id=None, tags="network,topology,network node,relay,connected assemblies,structures", aliases="network topology,network,connected structures"),
    dict(id="mechanic_clones",          category="mechanic", title="Shell / Clone System",   game_id=None, tags="clone,shell,nursery,nest,clone death,respawn,pod", aliases="clone system,shell system,clone death"),
    dict(id="mechanic_access_control",  category="mechanic", title="SSU Access Control",     game_id=None, tags="access control,tier,owner,tribe,vetted,none,access registry,ssu", aliases="access control,tier system,access tiers"),
]

# ---------------------------------------------------------------------------
# Resolve content for each entry
# ---------------------------------------------------------------------------

from datetime import datetime, timezone
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

output: list[dict] = []
auto_filled: list[str] = []
needs_manual: list[str] = []

for spec in SPEC:
    game_id    = spec.get("game_id")
    search_name = spec.get("search_name") or spec["title"]
    content    = _lookup(game_id, search_name)

    if content:
        auto_filled.append(spec["id"])
    else:
        content = f"TODO: {spec['category']} / {spec['title']}"
        needs_manual.append(spec["id"])

    output.append({
        "id":         spec["id"],
        "category":   spec["category"],
        "title":      spec["title"],
        "game_id":    game_id,
        "content":    content,
        "tags":       spec.get("tags", ""),
        "aliases":    spec.get("aliases", ""),
    })

# ---------------------------------------------------------------------------
# Write output
# ---------------------------------------------------------------------------

out_path = DATA / "lore_seed.json"
with open(out_path, "w") as f:
    json.dump(output, f, indent=2)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

print(f"Written: {out_path}")
print(f"Total entries : {len(output)}")
print(f"Auto-filled   : {len(auto_filled)}")
print(f"Needs content : {len(needs_manual)}")

if needs_manual:
    print("\nEntries needing manual content:")
    for entry_id in needs_manual:
        spec = next(s for s in SPEC if s["id"] == entry_id)
        print(f"  {entry_id:<40}  [{spec['category']}] {spec['title']}")

print("\nFill all TODO: entries in data/lore_seed.json, then run:")
print("  python scripts/import_lore.py")
