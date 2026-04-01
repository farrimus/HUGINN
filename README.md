# HUGINN

EVE Frontier is a game about survival in a hostile universe.
Dedicated pilots who crave real depth have always had to step outside the game — relying on wikis, spreadsheets, and Discord servers to stay ahead.

HUGINN closes that gap.

Built for the [EVE Frontier × Sui Hackathon 2026](https://evefrontier.com/en/news/eve-frontier-sui-2026-hackathon).

---

## Live Demo

```
http://135.181.95.84:8745/app?itemId=<your-assembly-id>&tenant=utopia
```

Requires EVE Frontier in-game browser + EVE Frontier Client Wallet.

API docs (no wallet required): `http://135.181.95.84:8745/docs`

---

## What it is

HUGINN runs natively inside any SSU, deeply embedded within your structure.
Connect your wallet and unlock a true structure intelligence — one that instantly understands your exact situation: your location, fuel state, active threats, and more.

It speaks in character, as a native entity of this universe rather than an external tool.

---

## The Intelligence Loop

HUGINN advises you on surrounding systems and highlights opportunities.
It plots smart, tailored routes.
You explore, return, and log your findings directly through its interface.
HUGINN processes the logs, learning enemy types, locations, and the ever-changing state of the galaxy.

It grows slowly alongside you and the universe itself.

---

## Additional Features

- **Tribe Board** — A shared space for your Tribe to post vital intel, fully visible to HUGINN.
- **Newsletter** — An automated intelligence update drawn from the collective memory of all connected structures.
- **Build Order Advisor** — Smart recommendations on what to construct next and why.

---

## On-Chain Access Control

Access is enforced directly on-chain for full security and trust.

- Tribe members receive expanded privileges.
- The structure owner enjoys complete access, including the power to vet new players and run admin commands.

**Contract:** `0xf33568afc1a24e7b5de4db95d01b5db1d0ef6a99269251fb9a355dde844255b9`
**Source:** `move/access_registry/`

---

## Stack

- **AI:** Claude Sonnet — streaming, tool-augmented, in-character
- **Backend:** FastAPI (Python 3.12), 24,426-system galaxy DB with full gate topology
- **Frontend:** React 19 + Vite, runs inside the EVE Frontier in-game browser
- **Blockchain:** Sui — wallet identity, on-chain access registry checked on every request

---

## Running it yourself

See [docs/SETUP.md](docs/SETUP.md). Requires an Anthropic API key.

---

## Data

Universe data sourced from CCP Games' EVE Frontier World API.
All EVE Frontier IP belongs to CCP Games. Independent third-party tool, not affiliated with or endorsed by CCP.

MIT — [LICENSE](LICENSE)
