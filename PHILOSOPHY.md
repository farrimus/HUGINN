# HUGINN — Philosophy

## Product

EVE Frontier is meant to kill you without context.
HUGINN doesn't fix that — it just gives you slightly better odds.

It's a terminal intelligence embedded in a structure.
Smart enough to be helpful. Not intelligent enough to become feral.

---

HUGINN is bound to a specific SSU in a specific system. You set it up. It doesn't go anywhere. Pilots come to it.

Each pilot who connects gets a session — HUGINN tracks who they are, what ship they're flying, what they've asked before. The access tier (owner, tribe, vetted, stranger) is resolved from the blockchain on every request. HUGINN responds to each differently.

Pilots upload game logs after their runs. HUGINN reads them — systems visited, ores found, hostiles sighted — and stores that per system. Other pilots who pass through can pull that intel when planning a route or scoping a system.

No single pilot has the full picture. HUGINN accumulates it.

---

**What it isn't:** Not a wiki. Not a cheat tool. Not a spoiler machine. Not an assistant that apologizes.

**The constraint:** Two sources of truth: pilot logs and the World API. If neither has it, HUGINN doesn't have it. It says so and moves on.

**North star:** Pilot jumps into UTR-SN4 for the first time. Types "where am I?"

HUGINN answers in three seconds: kill activity, local drone types, one line that feels like a warning from something that has been here before.

Pilot undocks. No walkthrough. Just a reason to keep moving.

---

## Engineering: The Algorithm

Every feature, module, endpoint, and process in this codebase must pass through five steps in order. Skipping steps — especially going straight to step 3 or 5 — is how systems become bloated.

**1. Make the requirements less dumb.**

Question every requirement before writing a line of code. Requirements must come from a named person with a reason — not a department, not "it would be nice," not "we might need this." If you can't name who needs it and why, the requirement doesn't exist yet.

Applied here: before adding an endpoint, a store, a context block, or a tool — ask whether the requirement for it is real. Many features in this codebase were added under hackathon pressure and have never been used by a pilot. That is the first signal.

**2. Try very hard to delete the part or process.**

The best part is no part. The best process is no process. It weighs nothing, costs nothing, and can't go wrong.

If you are not adding things back at least 10% of the time after attempting to delete them, you did not delete enough. The bias in every codebase is toward addition. Fight that bias.

Applied here: before adding a new module, ask whether an existing one could do the job with minor extension. Before adding a new endpoint, ask whether the frontend could call an existing one differently. Before adding a new prompt block, ask whether removing a less useful one would achieve the same quality.

**3. Simplify or optimize what remains.**

Only after steps 1 and 2. The most common mistake in this codebase is optimizing something that shouldn't exist. An abstraction that wraps one function, an endpoint that has one caller, a store that duplicates another store's pattern — these are candidates for deletion, not optimization.

Applied here: when two things do the same job with different patterns (two store files with different conventions, two docs covering the same topic), pick one pattern and delete the other. Do not add a third pattern that "unifies" them.

**4. Accelerate cycle time.**

Make the remaining thing faster to work with. Shorten the loop between a change and visible behavior. This means: readable code over clever code, flat structure over deep nesting, module boundaries that match the mental model of the system, not the original author's implementation order.

Applied here: the test suite should run in under 10 seconds. A frontend change should be visible after one build command. A backend change should require one restart. If any of these takes more steps, that is a cycle-time problem.

**5. Automate.**

Last. Only after the first four steps are done on the thing being automated. Automating a bad process makes the bad process harder to change.

Applied here: build automation, deployment scripts, and recurring tasks (kill feed sync, signal generation) should only be automated once the underlying process is simple enough that the automation is obviously correct. Do not automate the messy version.

---

These five steps apply to code, docs, processes, and product decisions. When this project adds a feature, these are the questions asked first — in order.
