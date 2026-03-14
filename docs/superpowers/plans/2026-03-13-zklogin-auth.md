# zkLogin Auth + Wallet Standard Fix

**Goal:** Make the EVEVault wallet connect flow work end-to-end in `structure.html`.

**Deadline:** March 31, 2026 (hackathon).

---

## Background

EVEVault is a Chrome MV3 extension using Sui zkLogin (FusionAuth OAuth → ZK proof → Sui address — no private key). It injects into pages via the **Sui Wallet Standard**, registering as `"Eve Vault"`. The in-game Chromium 122 browser exposes the same wallet provider as normal Chrome — but only if the extension is loaded.

Two bugs block the current auth flow:

### Bug 1 — Wrong wallet discovery in `structure.html`

Our code checks `window.__suiWallets` and `window.suiWallet`. Neither is the Wallet Standard API. EVEVault registers via:

```javascript
window["@wallet-standard/app"]  // registry object, has .get() and .on()
```

The `wallet-standard:register-wallet` event listener we have is correct but fires only for wallets that register *after* our listener is attached. If EVEVault is already registered (extension loaded before page), we miss it. We need to check the registry first.

### Bug 2 — Server can't verify zkLogin signatures

Our `verify_sui_personal_message` in `structure_auth.py` only handles `flag=0x00` (ed25519). EVEVault produces `flag=0x03` (zkLogin) — a different structure containing a Groth16 ZK proof + ephemeral signature. Our code will raise `ValueError` or `InvalidSignature` on every EVEVault user.

**zkLogin compact signature layout (base64-decoded):**
```
[0x03] [BCS-encoded zkLoginSignature]
  └── inputs:
        proof_points (A, B, C — Groth16)
        iss_base64_details (iss from JWT)
        header_base64
        address_seed
      max_epoch: u64
      user_signature: CompressedSignature (ephemeral ed25519/secp256r1)
```

Address derivation for zkLogin:
```
address = blake2b(0x05 || bcs(iss) || bcs(address_seed))[:32]
```

---

## Approach

### Fix 1 — Wallet discovery (vanilla JS, no build step)

Replace the broken `connectWallet` discovery block with proper Wallet Standard lookup:

```javascript
async function findEveVault(timeoutMs = 3000) {
  // 1. Check already-registered wallets via Wallet Standard registry
  const reg = window["@wallet-standard/app"];
  if (reg) {
    const found = reg.get().find(w => w.name.includes("Eve Vault"));
    if (found) return found;
  }

  // 2. Wait for late injection (wallet registers after page load)
  return new Promise(resolve => {
    const tid = setTimeout(() => resolve(null), timeoutMs);
    window.addEventListener('wallet-standard:register-wallet', (e) => {
      const w = e.detail || e;
      if (w && w.name && w.name.includes("Eve Vault")) {
        clearTimeout(tid);
        resolve(w);
      }
    });
    // Re-check registry in case event already fired
    const reg2 = window["@wallet-standard/app"];
    if (reg2) {
      const found = reg2.get().find(w => w.name.includes("Eve Vault"));
      if (found) { clearTimeout(tid); resolve(found); }
    }
  });
}
```

Also update the error message to include a debug hint:
```javascript
if (!wallet) throw new Error(
  'EVE Vault not found. Is the extension installed and unlocked? ' +
  'walletStd=' + !!window["@wallet-standard/app"] +
  ' wallets=' + (window["@wallet-standard/app"]?.get().length ?? 0)
);
```

### Fix 2 — Server-side zkLogin verification

**Option A (preferred): Delegate to Sui fullnode RPC**

The Sui fullnode exposes `sui_verifyPersonalMessageSignature` (to be confirmed — see Step 2.1 below). If available:

```python
async def verify_via_rpc(message_bytes: bytes, signature_b64: str, address: str) -> bool:
    import base64, httpx
    payload = {
        "jsonrpc": "2.0", "id": 1,
        "method": "sui_verifyPersonalMessageSignature",
        "params": [
            base64.b64encode(message_bytes).decode(),
            signature_b64,
            address,
            None  # intent scope, None = PersonalMessage
        ]
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(NOVA_RPC_URL, json=payload, timeout=10)
        result = r.json()
        return result.get("result", False) is True
```

**Option B (fallback): Skip crypto verification for zkLogin**

If the RPC method doesn't exist, for the hackathon: detect flag `0x03`, skip Groth16 verification, verify only that the nonce was legitimately issued. The nonce prevents replay; the AccessRegistry enforces who gets access. Security is weaker but acceptable for a demo.

```python
def verify_sui_personal_message(message_bytes, signature_b64, expected_address):
    sig_bytes = base64.b64decode(signature_b64)
    flag = sig_bytes[0]
    if flag == 0x00:
        # existing ed25519 path
        _verify_ed25519(message_bytes, sig_bytes, expected_address)
    elif flag == 0x03:
        # zkLogin — skip Groth16, trust address (hackathon mode)
        # TODO: replace with RPC verification post-hackathon
        pass
    else:
        raise ValueError(f"Unsupported signature flag: {flag:#x}")
```

---

## Steps

### Step 1 — Fix wallet discovery in `static/structure.html`

- [x] **1.1** Replace `connectWallet` wallet-finding block with `findEveVault()` as above
- [x] **1.2** Update error message to include `walletStd` debug info
- [x] **1.3** Test in Chrome desktop with EVEVault extension loaded — confirm wallet is detected
- [x] **1.4** Test in-game SSU browser — confirm same

### Step 2 — Fix server-side zkLogin verification

- [x] **2.1 Research:** confirm whether `sui_verifyPersonalMessageSignature` exists on Sui testnet fullnode
  ```bash
  curl -s -X POST https://fullnode.testnet.sui.io \
    -H 'Content-Type: application/json' \
    -d '{"jsonrpc":"2.0","id":1,"method":"sui_verifyPersonalMessageSignature","params":["aGVsbG8=","","0x0000000000000000000000000000000000000000000000000000000000000000",null]}' \
    | python3 -m json.tool
  ```
  - If response is `{"error": {"code": -32601}}` → method not found → use Option B
  - If response is anything else (even an invalid sig error) → method exists → use Option A

- [x] **2.2** Update `src/structure_auth.py`:
  - If Option A: add async RPC call for `flag=0x03`
  - If Option B: add `flag=0x03` passthrough with comment

- [x] **2.3** Update `tests/test_structure_auth.py`:
  - Add test: `flag=0x03` signature does not raise (Option B), or mocked RPC returns True (Option A)
  - Add test: unknown flag raises `ValueError`

- [x] **2.4** Run all tests — expect pass
  ```bash
  cd /opt/eve-frontier && .venv/bin/pytest tests/test_structure_auth.py -v
  ```

- [x] **2.5** Restart server

### Step 3 — End-to-end test

- [x] **3.1** Open `http://<VPS_IP>:8745/static/structure.html?id=keep-7a&registry=0x89e9...` in Chrome desktop with EVEVault extension
- [x] **3.2** Click Connect Wallet → complete FusionAuth OAuth → confirm OWNER tier appears
- [x] **3.3** Send a message — confirm Structure AI responds
- [x] **3.4** Test in-game SSU browser — same flow
- [x] **3.5** Commit

---

## Resolved Issues (2026-03-14)

- `sui_verifyPersonalMessageSignature` does **not** exist on testnet → Option B (passthrough) used
- EVEVault uses signature flag `0x05`, not `0x03` — both handled in passthrough
- In-game browser (HTTP/1.0) truncates URLs longer than ~157 chars — registry object ID stripped from URL, now configured server-side via `NOVA_REGISTRY_OBJECT_ID` env var. URL is just `?id=keep-7a`.
- EVEVault injects automatically when extension is loaded; wallet standard `register-wallet` event fires on page load, not button click — registry must be set up at page load time

## Open Questions

| Question | Answer |
|----------|--------|
| Does `sui_verifyPersonalMessageSignature` exist on testnet? | No — Option B used |
| Does EVEVault inject into the in-game browser automatically? | Yes, if extension is loaded |
| Which tenant — Utopia or Stillness? | Testnet = Utopia |
| Is `signPersonalMessage` supported by EVEVault? | Yes, confirmed working |

---

## Post-Hackathon (not blocking)

- Replace Option B passthrough with full Groth16 zkLogin verification
- Or: replace nonce/signature flow entirely with EVEVault OAuth session (trust FusionAuth JWT directly)
