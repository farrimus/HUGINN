"""
EVE Frontier game data types — Pydantic models.

Three sources:
  World API  — REST responses from world-api-{tenant}.*.evefrontier.com
  Blockchain — On-chain Move struct data via Sui GraphQL / JSON-RPC
  Derived    — Computed/transformed by our backend from the above

Field names follow the API JSON keys where possible.
Use model.model_dump(by_alias=True) when serialising back to World API format.
"""

from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Shared config: accept both camelCase API keys and snake_case Python names
# ---------------------------------------------------------------------------

_API = ConfigDict(populate_by_name=True)


# ===========================================================================
# WORLD API — Primitives
# ===========================================================================

class Location3D(BaseModel):
    """Galactic coordinate (large integers, metre-scale)."""
    model_config = _API
    x: int
    y: int
    z: int


# ===========================================================================
# WORLD API — Solar Systems
# ===========================================================================

class SolarSystem(BaseModel):
    """Lightweight solar system (list endpoints, gate link destinations)."""
    model_config = _API
    id: int
    name: str
    constellation_id: int = Field(alias="constellationId")
    region_id: int = Field(alias="regionId")
    location: Location3D


class GateLink(BaseModel):
    """A gate connection from a solar system to a destination system."""
    model_config = _API
    id: int
    name: str
    location: Location3D
    destination: SolarSystem


class DetailedSolarSystem(SolarSystem):
    """Full solar system with gate link list."""
    gate_links: list[GateLink] = Field(default_factory=list, alias="gateLinks")


# ===========================================================================
# WORLD API — Game Types (item/structure type catalogue)
# ===========================================================================

class GameType(BaseModel):
    """
    Item/structure type from /v2/types.

    type_id values for known assembly types:
      77917 = Heavy Storage (SSU)
      ... (catalogue has 392+ types total)
    """
    model_config = _API
    id: int
    name: str
    description: str
    mass: Optional[float] = None
    radius: Optional[float] = None
    volume: Optional[float] = None
    portion_size: Optional[int] = Field(default=None, alias="portionSize")
    group_name: Optional[str] = Field(default=None, alias="groupName")
    group_id: Optional[int] = Field(default=None, alias="groupId")
    category_name: Optional[str] = Field(default=None, alias="categoryName")
    category_id: Optional[int] = Field(default=None, alias="categoryId")
    icon_url: Optional[str] = Field(default=None, alias="iconUrl")
    attributes: dict = Field(default_factory=dict)


# ===========================================================================
# WORLD API — Ships
# ===========================================================================

class ShipSlots(BaseModel):
    model_config = _API
    high: int
    medium: int
    low: int


class ShipHealth(BaseModel):
    model_config = _API
    shield: float
    armor: float
    structure: float


class ShipHeat(BaseModel):
    model_config = _API
    heat_capacity: float = Field(alias="heatCapacity")
    conductance: float


class ShipPhysics(BaseModel):
    model_config = _API
    mass: float
    maximum_velocity: float = Field(alias="maximumVelocity")
    inertia_modifier: float = Field(alias="inertiaModifier")
    heat: ShipHeat


class DamageLayer(BaseModel):
    """Damage resistance values for one layer (shield, armor, structure)."""
    model_config = _API
    em_damage: float = Field(alias="emDamage")
    thermal_damage: float = Field(alias="thermalDamage")
    kinetic_damage: float = Field(alias="kineticDamage")
    explosive_damage: float = Field(alias="explosiveDamage")


class ShipResistances(BaseModel):
    model_config = _API
    shield: DamageLayer
    armor: DamageLayer
    structure: DamageLayer


class ShipCapacitor(BaseModel):
    model_config = _API
    capacity: float
    recharge_rate: float = Field(alias="rechargeRate")


class Ship(BaseModel):
    """Full ship type from /v2/ships/{id}."""
    model_config = _API
    id: int
    name: str
    class_id: int = Field(alias="classId")
    class_name: str = Field(alias="className")
    description: str
    slots: ShipSlots
    health: ShipHealth
    physics: ShipPhysics
    damage_resistances: ShipResistances = Field(alias="damageResistances")
    fuel_capacity: float = Field(alias="fuelCapacity")
    cpu_output: float = Field(alias="cpuOutput")
    powergrid_output: float = Field(alias="powergridOutput")
    capacitor: ShipCapacitor


# ===========================================================================
# WORLD API — Jumps (character location history)
# ===========================================================================

class ShipRef(BaseModel):
    """Ship instance reference inside a Jump."""
    model_config = _API
    instance_id: int = Field(alias="instanceId")
    type_id: int = Field(alias="typeId")


class Jump(BaseModel):
    """
    Gate jump record from /v2/characters/me/jumps.

    The latest jump's `destination` is the player's current location.
    Requires BearerAuth (player JWT).
    """
    model_config = _API
    id: int          # UNIX millisecond timestamp
    time: str        # ISO-8601 string
    origin: SolarSystem
    destination: SolarSystem
    ship: ShipRef


# ===========================================================================
# WORLD API — Tribes & Constellations
# ===========================================================================

class Tribe(BaseModel):
    """Player or NPC corporation from /v2/tribes."""
    model_config = _API
    id: int
    name: str
    name_short: str = Field(alias="nameShort")
    description: str
    tax_rate: float = Field(alias="taxRate")
    tribe_url: str = Field(alias="tribeUrl")


class Constellation(BaseModel):
    """Constellation from /v2/constellations/{id}."""
    model_config = _API
    id: int
    name: str
    region_id: int = Field(alias="regionId")
    location: Location3D
    solar_systems: list[SolarSystem] = Field(default_factory=list, alias="solarSystems")


# ===========================================================================
# BLOCKCHAIN — Move struct types (via Sui GraphQL JSON)
# ===========================================================================

class TenantItemId(BaseModel):
    """
    Deterministic game-derived key for any on-chain object.
    Appears as `key` on assemblies, characters, etc.
    """
    item_id: str
    tenant: str   # e.g. "utopia", "stillness"


class AssemblyStatusVariant(BaseModel):
    """Status enum value — `@variant` is the discriminator string."""
    model_config = ConfigDict(populate_by_name=True)
    variant: str = Field(alias="@variant")  # "ONLINE" | "OFFLINE"


class AssemblyStatusData(BaseModel):
    """Status wrapper object on a structure/assembly."""
    assembly_id: Optional[str] = None
    item_id: Optional[str] = None
    type_id: Optional[str] = None
    status: AssemblyStatusVariant


class AssemblyMetadata(BaseModel):
    """Metadata attached to assemblies and characters."""
    assembly_id: str
    name: str
    description: str
    url: str


class AssemblyLocation(BaseModel):
    """On-chain location record (hashed — not a raw coordinate)."""
    location_hash: str
    structure_id: str


class AssemblyFuel(BaseModel):
    """
    Fuel data for Network Nodes.
    All numeric values are u64 serialised as strings on-chain.
    """
    max_capacity: str
    burn_rate_in_ms: str
    type_id: str
    unit_volume: str
    quantity: str
    is_burning: bool
    previous_cycle_elapsed_time: str
    burn_start_time: str
    last_updated: str


class AssemblyEnergySource(BaseModel):
    """Energy source data for Network Nodes (all u64 as strings)."""
    max_energy_production: str
    current_energy_production: str
    total_reserved_energy: str


class Assembly(BaseModel):
    """
    On-chain smart assembly object (StorageUnit, Gate, Turret, NetworkNode).

    Retrieved via Sui GraphQL `getAssemblyWithOwner()` or `getObjectWithJson()`.
    Fields vary by assembly type — optional fields are type-specific.

    Known type_id ranges (u64):
      Gate         — check category_name == "Gate" in World API /v2/types
      StorageUnit  — group_name == "Storage"
      Turret       — (TBD, check /v2/types)
      NetworkNode  — (TBD, check /v2/types)
    """
    id: str                                       # Sui object ID (0x...)
    type_id: str                                  # u64 game type, serialised as string
    extension: Optional[Any] = None
    key: Optional[TenantItemId] = None
    inventory_keys: Optional[list[str]] = None
    linked_gate_id: Optional[str] = None          # SmartGate only
    energy_source_id: Optional[str] = None        # NetworkNode only
    location: Optional[AssemblyLocation] = None
    metadata: Optional[AssemblyMetadata] = None
    owner_cap_id: Optional[str] = None
    status: Optional[AssemblyStatusData] = None
    fuel: Optional[AssemblyFuel] = None           # NetworkNode only
    energy_source: Optional[AssemblyEnergySource] = None  # NetworkNode only
    connected_assembly_ids: Optional[list[str]] = None    # NetworkNode only


class Character(BaseModel):
    """
    Raw on-chain Character object (Move struct).

    The character holds OwnerCaps for all assemblies the player owns.
    Retrieved via getWalletCharacters() or getCharacterAndOwnedObjects().
    """
    id: str                    # Sui object ID (0x...)
    key: TenantItemId
    tribe_id: int
    character_address: str     # Sui wallet address (0x...)
    metadata: AssemblyMetadata
    owner_cap_id: str


class CharacterInfo(BaseModel):
    """
    Processed/transformed character — human-friendly, post-transform.

    Source: dapp-kit transformToCharacter() or our own derivation.
    """
    id: str             # Sui object ID
    address: str        # wallet address
    name: str
    tribe_id: int
    character_id: int   # game integer ID (from TenantItemId.item_id)


class OwnerCap(BaseModel):
    """
    OwnerCap on-chain object — authorises control of one assembly.

    The OwnerCap is held by the Character object (not the wallet directly).
    `authorized_object_id` == the Assembly's Sui object ID.
    """
    id: str
    authorized_object_id: str
