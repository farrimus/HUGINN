# deal_store

## Overview
Persistent patron deal/contract storage for Structure AI. Stores address + structure_id pairs with message quotas and expiration timestamps. Files persisted as JSON in `data/deals/` directory. Supports creating deals, retrieving them, and consuming messages.

## When Should an Agent Use This Module?
- Issuing patron deals (message quota + expiration window)
- Checking pilot message allowance before responding
- Consuming (decrementing) messages when a patron uses a deal
- Revoking or extending expired deals

## Key API
| Symbol | Type | Purpose | Agent Instruction |
|--------|------|---------|------------------|
| `deal_store.issue(address, structure_id, payment_method, messages, duration_hours)` | method | Create or overwrite a patron deal | Use when pilot completes payment; returns DealRecord |
| `deal_store.get(address, structure_id)` | method | Fetch deal record | Use before responding to check if deal is valid (not expired, has messages) |
| `deal_store.consume_message(address, structure_id)` | method | Decrement messages_remaining and return validity | Call when patron sends a message; returns True if deal is still valid |
| `DealRecord` | dataclass | Deal metadata (address, structure_id, messages_remaining, expires_at, etc.) | Read-only access to deal state |

### DealRecord Fields
```python
@dataclass
class DealRecord:
    address: str                # Wallet address (lowercased)
    structure_id: str           # Structure assembly ID
    payment_method: str         # "item" | "sui" | "info"
    messages_remaining: int     # Quota counter (decremented by consume_message)
    expires_at: float           # Unix timestamp
    created_at: str             # ISO8601 timestamp
```

## Critical Gotchas & Pitfalls for Agents
• **Addresses are lowercased:** `issue()` and `consume_message()` convert address to lowercase. Always call `.lower()` on pilot addresses before storing/retrieving.
• **consume_message() returns False if invalid:** Use the return value to determine if the patron can send a message. Returns False if: deal missing, expired, or exhausted.
• **consume_message() modifies the file:** Calling `consume_message()` decrements `messages_remaining` on disk immediately. Expect the count to drop after each call.
• **Safe filenames:** Address and structure_id are sanitized to alphanumeric + underscore; non-safe chars are stripped.

## Architecture
```
Issue a deal:
  Input: address, structure_id, payment_method, messages, duration_hours
  ↓
  Create DealRecord with:
    - address (lowercased)
    - messages_remaining = messages
    - expires_at = now + duration_hours*3600
    - created_at = ISO8601 now
  ↓
  Write to data/deals/{safe_address}-{safe_structure_id}.json
  ↓
  Return DealRecord

Consume a message:
  Input: address, structure_id
  ↓
  Fetch DealRecord from disk
  ↓
  Check: expires_at > now? messages_remaining > 0?
  ↓
  If valid: decrement messages_remaining, write back to disk, return True
  If invalid: return False (don't modify file)
```

## Agent Guidance
**Primary Workflow**
1. Pilot pays for patron access: `deal = deal_store.issue(address.lower(), structure_id, "sui", messages=20, duration_hours=24)`
2. Send confirmation message to pilot with deal details
3. Before responding to pilot message: `valid = deal_store.consume_message(address.lower(), structure_id)`
4. If `valid` is True: respond to pilot (message already consumed from quota)
5. If `valid` is False: tell pilot deal expired or exhausted, offer renewal

**Example Check Flow**
```python
if deal_store.consume_message(pilot_address.lower(), structure_id):
    # Patron has valid deal with messages remaining; they may chat
    response = await structure_client.stream(...)
else:
    # No valid deal; reject or prompt for renewal
    return {"error": "Patron deal expired or exhausted"}
```

**Best Practices & Anti-Patterns**
- Always / Call `.lower()` on wallet addresses before storing/retrieving
- Always / Use `consume_message()` return value to guard responses — don't check separately
- Always / Log when issuing, revoking, or denying deals (audit trail)
- Always / Handle the case where `consume_message()` returns False gracefully
- Never / Assume a deal exists without checking `get() is not None`
- Never / Call `consume_message()` multiple times per message — the quota has already been decremented

**Cross-Module Dependencies**
- Depends on: `dataclasses`, `json` (stdlib)
- Used by: Structure AI chat routes, patron access control

## Progressive Disclosure
**Read this main file by default.**

**Load deeper files ONLY when:**
- You need payment flow: read `/docs/ref/structure-ai.md` section on patron mechanics
- You need to audit deals: check `data/deals/` directory for JSON files
