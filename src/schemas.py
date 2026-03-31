"""
Pydantic request/response schemas for all FastAPI endpoints.

Extracted from main.py to follow best practices and improve code organization.
"""

from pydantic import BaseModel, ConfigDict, field_validator, Field
from typing import Optional, List


# ── SHIP AI ───────────────────────────────────────────────────────────────────

class ShipProfileRequest(BaseModel):
    hull_mass:      Optional[float] = None
    current_mass:   Optional[float] = None
    specific_heat:  Optional[float] = None
    adaptive_level: Optional[int]   = None
    fuel_type:      Optional[str]   = None
    fuel_quantity:  Optional[float] = None
    external_temp:  Optional[float] = None
    ship_type:      Optional[str]   = None
    extra_cargo_kg: Optional[float] = None


class RouteRequest(BaseModel):
    origin:         Optional[str]   = None
    destination:    str
    # Optional per-request ship overrides (hypothetical mode)
    hull_mass:      Optional[float] = None
    current_mass:   Optional[float] = None
    specific_heat:  Optional[float] = None
    adaptive_level: Optional[int]   = None
    fuel_type:      Optional[str]   = None
    fuel_quantity:  Optional[float] = None
    cargo_fuel:     int             = 0     # extra fuel in cargo hold (adds mass + budget)
    external_temp:  Optional[float] = None
    extra_cargo_kg: Optional[float] = None    # if provided, replaces base profile value
    gate_only:      bool            = False   # force gate-only BFS
    cost_mode:      str             = "jumps"  # "jumps" or "fuel"


class RouteActivateRequest(BaseModel):
    variant: str  # "primary" or "alternative"


class LogEvent(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str


class ChatRequest(BaseModel):
    message: str
    history: list = []
    disabled_tools: List[str] = []


# ── SEARCH & DISCOVERY ────────────────────────────────────────────────────────

class RadiusSearchRequest(BaseModel):
    center_system: str
    radius_ly: float = Field(gt=0, description="Radius in light-years, must be > 0")
    filters: List[str] = Field(default=["planets"], description="Filter types to apply")
    killmail_hours: int = Field(default=24, ge=1, description="Hours to search for killmails, must be >= 1")
    top_n: int = Field(default=10, gt=0, description="Number of results to return, must be > 0")
    skip_heat_traps: bool = False

    @field_validator('filters')
    @classmethod
    def validate_filters(cls, v: List[str]) -> List[str]:
        valid_types = {"planets", "killmails", "heat", "structures"}
        invalid = set(v) - valid_types
        if invalid:
            raise ValueError(f"Invalid filter types: {invalid}. Valid types are: {valid_types}")
        return v


class RecordStructureRequest(BaseModel):
    assembly_id: str = Field(min_length=1, description="Structure ID, cannot be empty")
    system_name: str = Field(min_length=1, description="System name, cannot be empty")
    reported_by: str = Field(min_length=1, description="Reporter name, cannot be empty")
    tribe: Optional[str] = None


class DiscoveryLog(BaseModel):
    timestamp: str
    success: bool
    assembly_id: Optional[str] = None
    error: Optional[str] = None
    logs: list = []


class DerivationRequest(BaseModel):
    """Request to look up StorageUnit address via Sui RPC query"""
    item_id: str  # Game item_id (from URL params, NOT blockchain item_id)
    tenant: str  # Tenant name


# ── STRUCTURE AUTH ────────────────────────────────────────────────────────────

class ChallengeRequest(BaseModel):
    assembly_id: str


class VerifyRequest(BaseModel):
    address: str
    signature: str
    nonce: str
    assembly_id: str
    tier_registry_object_id: Optional[str] = None  # required on first owner auth

    @field_validator('address')
    @classmethod
    def validate_address(cls, v: str) -> str:
        if not v or not v.startswith('0x') or len(v) != 66:
            raise ValueError('address must be 0x followed by 64 hexadecimal characters')
        try:
            int(v[2:], 16)
        except ValueError:
            raise ValueError('address contains non-hexadecimal characters')
        return v.lower()


class DealOfferRequest(BaseModel):
    assembly_id: str
    address: str


class DealClaimRequest(BaseModel):
    nonce: str
    address: str
    assembly_id: str
    signature: str
    payment_method: str          # "item" | "sui" | "info"
    proof: dict = {}             # payment_method-specific evidence

    @field_validator('address')
    @classmethod
    def validate_address(cls, v: str) -> str:
        if not v or not v.startswith('0x') or len(v) != 66:
            raise ValueError('address must be 0x followed by 64 hexadecimal characters')
        try:
            int(v[2:], 16)
        except ValueError:
            raise ValueError('address contains non-hexadecimal characters')
        return v.lower()


# ── STRUCTURE MANAGEMENT ──────────────────────────────────────────────────────

class StructureProfileUpdate(BaseModel):
    structure_name: Optional[str] = None
    structure_type: Optional[str] = None
    system_name:    Optional[str] = None
    fuel_pct:       Optional[float] = None
    shield_pct:     Optional[float] = None
    services_online: Optional[int] = None
    services_total:  Optional[int] = None
    docked_count:   Optional[int] = None


class LocationManualRequest(BaseModel):
    system_name: str


class LocationRevealRequest(BaseModel):
    jwt_token: str


class StructureChatRequest(BaseModel):
    message: str
    history: list = []
    assembly_id: str


class StructureDebugChatRequest(BaseModel):
    assembly_id: str
    message: str
    history: list = []
