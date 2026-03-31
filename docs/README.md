# Documentation

## ⚡ For AI Agents (Primary Reference)

**For frontend work specifically:** See `/frontend/CLAUDE.md` for React dApp setup and dapp-kit documentation.

**[AI_AGENT_REFERENCE.md](AI_AGENT_REFERENCE.md)** ← **START HERE FOR BACKEND AGENTS**
- Complete, verified reference from source code
- Hook signatures, API contracts, type definitions
- CLI commands, build process, troubleshooting
- Task-focused with code examples
- 2,300+ lines of accurate, agent-ready content

**[TRUTH_FACTS.md](TRUTH_FACTS.md)** — Verified facts only
- What's actually in the code (not claims)
- Corrects outdated documentation
- Technology stack, APIs, types, build process

**[VERIFICATION_REPORT.md](VERIFICATION_REPORT.md)** — Audit trail
- What was wrong in original docs
- Corrections made
- Verification checklist

**[NEW_DOCS_SUMMARY.md](NEW_DOCS_SUMMARY.md)** — Overview of new docs
- What problems were found
- What was created
- Quality assurance results

---

## 📚 For Humans (Learning the Project)

1. **[QUICK_START.md](QUICK_START.md)** ← Read this first (5 min)
   - Overview, file locations, how to modify the app
   - Answers: "What is this? How do I change it?"

2. **[SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md)** (15 min)
   - Big picture: React → Vite → Static files → FastAPI → Browser
   - Technology choices and why
   - File flow and concepts

3. ⚠️ **[FRONTEND_ARCHITECTURE.md](FRONTEND_ARCHITECTURE.md)** — PARTIALLY OUTDATED
   - Wallet section (lines 48-62) is incorrect — use AI_AGENT_REFERENCE instead
   - Rest of document is mostly accurate
   - Will be rewritten

4. **[FRONTEND_DEPLOYMENT.md](FRONTEND_DEPLOYMENT.md)** (10 min)
   - Build and deployment step-by-step
   - Troubleshooting common issues
   - Development workflow

---

## Memory (Persistent Context for Next Agents)

See `/root/.claude/projects/-opt-eve-frontier/memory/MEMORY.md` for:
- Frontend setup completion notes
- Architecture decisions
- Known issues and solutions
- Documentation standards

---

## Key Points

- **Frontend is React + Vite,** deployed as static files to `/static/companion/`
- **No Node.js server needed.** FastAPI serves the files.
- **Wallet connection via EIP-6963 standard.** No custom auth.
- **To modify:** Edit `src/`, run `npm run build`, copy to `/static/companion/`
- **To test locally:** `npm run dev` for hot reload
- **Production access:** `http://135.181.95.84:8745/static/companion/index.html`

---

For other topics (backend, game integration, etc.), check git history and commits for context.
