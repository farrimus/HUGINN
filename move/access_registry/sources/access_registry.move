/// AccessRegistry — per-structure access control for EVE Frontier Structure AI
/// Deployed on Nova (builder sandbox chain).
/// Owner manages tribe (corp members) and vetted (approved outsiders) address lists.
///
/// Note: The spec describes structure_id as u64 (on-chain game ID). We use String
/// (human-readable key matching the server profile, e.g. "keep-7a") because the
/// server identifies structures by the URL ?id= param, not a numeric chain ID.
/// If the game's numeric structure ID is needed later, add a separate field.
module access_registry::registry {
    use sui::object::{Self, UID};
    use sui::tx_context::{Self, TxContext};
    use sui::transfer;
    use std::vector;
    use std::string::{Self, String};

    /// One shared object per structure. Created by the structure owner.
    public struct AccessRegistry has key {
        id: UID,
        /// Game structure identifier (e.g., "keep-7a") — matches server profile key
        structure_id: String,
        /// Owner's Sui wallet address
        owner: address,
        /// Tribe/corp members — full chat access
        tribe: vector<address>,
        /// Vetted outsiders — limited chat access
        vetted: vector<address>,
    }

    // ── Errors ──────────────────────────────────────────────────────────────
    const E_NOT_OWNER: u64 = 1;
    const E_ALREADY_IN_LIST: u64 = 2;
    const E_NOT_IN_LIST: u64 = 3;

    // ── Owner functions ──────────────────────────────────────────────────────

    /// Create a new AccessRegistry for a structure. Shared immediately.
    public entry fun create(structure_id: vector<u8>, ctx: &mut TxContext) {
        let registry = AccessRegistry {
            id: object::new(ctx),
            structure_id: string::utf8(structure_id),
            owner: tx_context::sender(ctx),
            tribe: vector::empty(),
            vetted: vector::empty(),
        };
        transfer::share_object(registry);
    }

    public entry fun add_tribe(registry: &mut AccessRegistry, addr: address, ctx: &TxContext) {
        assert!(registry.owner == tx_context::sender(ctx), E_NOT_OWNER);
        assert!(!vector::contains(&registry.tribe, &addr), E_ALREADY_IN_LIST);
        vector::push_back(&mut registry.tribe, addr);
    }

    public entry fun remove_tribe(registry: &mut AccessRegistry, addr: address, ctx: &TxContext) {
        assert!(registry.owner == tx_context::sender(ctx), E_NOT_OWNER);
        let (exists, idx) = vector::index_of(&registry.tribe, &addr);
        assert!(exists, E_NOT_IN_LIST);
        vector::remove(&mut registry.tribe, idx);
    }

    public entry fun add_vetted(registry: &mut AccessRegistry, addr: address, ctx: &TxContext) {
        assert!(registry.owner == tx_context::sender(ctx), E_NOT_OWNER);
        assert!(!vector::contains(&registry.vetted, &addr), E_ALREADY_IN_LIST);
        vector::push_back(&mut registry.vetted, addr);
    }

    public entry fun remove_vetted(registry: &mut AccessRegistry, addr: address, ctx: &TxContext) {
        assert!(registry.owner == tx_context::sender(ctx), E_NOT_OWNER);
        let (exists, idx) = vector::index_of(&registry.vetted, &addr);
        assert!(exists, E_NOT_IN_LIST);
        vector::remove(&mut registry.vetted, idx);
    }

    /// Transfer ownership to a new address
    public entry fun transfer_ownership(registry: &mut AccessRegistry, new_owner: address, ctx: &TxContext) {
        assert!(registry.owner == tx_context::sender(ctx), E_NOT_OWNER);
        registry.owner = new_owner;
    }

    // ── Read accessors (public, no auth required) ────────────────────────────

    public fun owner(registry: &AccessRegistry): address { registry.owner }
    public fun tribe(registry: &AccessRegistry): &vector<address> { &registry.tribe }
    public fun vetted(registry: &AccessRegistry): &vector<address> { &registry.vetted }
    public fun structure_id(registry: &AccessRegistry): &String { &registry.structure_id }

    public fun is_tribe(registry: &AccessRegistry, addr: address): bool {
        vector::contains(&registry.tribe, &addr)
    }

    public fun is_vetted(registry: &AccessRegistry, addr: address): bool {
        vector::contains(&registry.vetted, &addr)
    }
}
