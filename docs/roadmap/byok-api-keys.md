# BYOK — Bring Your Own API Key

Allow users to supply their own Claude API key so they get unlimited Huginn access at no cost to the server operator.

---

## Approach: Option A (localStorage + per-request header)

- User enters their key once in a settings panel in the UI
- Key is stored in browser `localStorage` — never written to server disk
- Every chat request sends it as `X-User-Api-Key` header over HTTPS
- Backend uses it for that request only, then discards it
- Server key remains the fallback for users who don't opt in

**Privacy guarantee:** Key is never stored on the server. Operator commits to not logging that header. In-transit exposure mitigated by HTTPS.

**localStorage persistence:** Survives browser restarts, tab closes, weeks of inactivity. Only wiped if user manually clears browser data or reinstalls game client. No re-entry needed between sessions.

---

## Files to Change (3 total)

| File | Change | Lines |
|---|---|---|
| `src/endpoints/companion.py` | Read `X-User-Api-Key` header, pass to `_stream_companion`, use when instantiating `AsyncAnthropic` | ~15 |
| `frontend/src/hooks/useCompanionStream.ts` | Read key from localStorage, inject as header in fetch call | ~5 |
| `frontend/src/components/TerminalUI.tsx` | `/apikey` slash command + inline settings panel | ~50 |

No new files. No schema changes. No database changes. No other endpoints touched.

---

## Backend Change (companion.py)

Endpoint at line 724 gains one new header parameter:

```python
async def companion_stream_endpoint(
    req: CompanionChatRequest,
    x_api_key: Optional[str] = Header(default=None),
    x_user_api_key: Optional[str] = Header(default=None),  # NEW
):
```

In `_stream_companion` at line 590, client instantiation becomes:

```python
api_key = x_user_api_key or os.environ.get("ANTHROPIC_API_KEY")
client = AsyncAnthropic(api_key=api_key)
```

Same pattern for the sync client at line 553.

Invalid key errors surface naturally as `{"error": "..."}` SSE events — no special handling needed.

---

## Frontend Change (useCompanionStream.ts)

```typescript
const userApiKey = localStorage.getItem('huginn_user_api_key');
headers: {
  'Content-Type': 'application/json',
  ...(userApiKey ? { 'X-User-Api-Key': userApiKey } : {}),
}
```

---

## Frontend Change (TerminalUI.tsx)

`/apikey` command renders an inline panel:
- Password-type input (masked)
- Save / Clear buttons
- Status line: "Using your API key" or "Using shared key"

Fits the existing terminal slash-command metaphor.

---

## Open Decisions (resolve before implementing)

1. **Provider scope.** Claude-only first pass, or also OpenAI/Grok? OpenAI requires adding the `openai` Python package. Recommend Claude-only for now.

2. **BYOK + tier policy.** Does BYOK still respect tier-gated tools, or does it unlock everything? Simplest: tier still applies. Alternative: BYOK users get a VETTED floor automatically.

3. **Logging hygiene.** Check whether FastAPI middleware logs request headers. If so, add an explicit exclusion for `X-User-Api-Key` before shipping.

---

## What Stays Untouched

Session system, tier system, tool registry, system prompt, all other endpoints, signal/broadcast system, session files.

---

## Future Upgrade Path (Option B)

If users demand stronger privacy guarantees, Option B uses wallet-signature-derived encryption:
- Browser prompts wallet to sign a fixed message (`"huginn-api-key-v1"`)
- 64-byte signature becomes the AES-GCM key
- Encrypted blob stored in session file on server
- Operator mathematically cannot read the plaintext key
- Cost: one wallet-sign interaction per session
