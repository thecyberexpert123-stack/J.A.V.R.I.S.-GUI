# Backend bridge — the J.A.V.R.I.S. kernel

This GUI is the front-end for the sibling repository
[`J.A.V.R.I.S.`](https://github.com/thecyberexpert123-stack/J.A.V.R.I.S.)
(branch `arena/01a06229-j-a-v-r-i-s`, package `jarvis-agent`). The backend
publishes a front-end contract, `javris-frontend/1`, and this document records
how we consume it — including several places where the live kernel does not
behave the way a first reading of the documentation suggests.

Everything below marked **verified** was observed against a running
`jarvis mcp serve` at kernel version **1.10.2** in this workspace. Nothing here
is inferred from the backend's documentation alone.

## Transport

| Property | Value |
| --- | --- |
| Contract | `javris-frontend/1` |
| Transport | `stdio-newline-jsonrpc-2.0` |
| Spawn | `["jarvis", "mcp", "serve"]` |
| Protocol version | `2025-03-26` |
| Server identity | `{"name": "jarvis", "version": "1.10.2"}` |

One JSON object per line on stdout. stderr carries a human banner and **must
never be parsed as protocol** — we run `QProcess` in `SeparateChannels` mode
precisely so a diagnostic line can never be mistaken for a frame.

`QProcess` is given a program and an argument list separately, so no shell is
involved and nothing in the spawn can be word-split or injected.

### Locating the kernel

`KernelClient.executable()` searches exactly two places: `PATH`, then the bin
directory of the running interpreter. The second case matters because a
virtualenv holding both the GUI and the kernel is usually not on the `PATH` of
the desktop session that launched the GUI, yet it is unambiguously the same
install. No other directory is searched — guessing at locations would let the
GUI execute a binary the operator never pointed it at.

When the kernel cannot be found, the GUI stays **OFFLINE** and keeps showing
local telemetry. A missing agent is a degraded feature, never a fatal error.

## The consent model

This is the part most worth getting right, and the part where the documentation
alone would have misled us.

> **Verified:** the consent gate is per-**tier**, not per-tool.

`jarvis_do` is published as `explicit-allow`, which reads as though every `do`
requires approval. It does not:

| Tier | Behaviour without `allow` | Consent offered? |
| --- | --- | --- |
| 1 | **Executes immediately.** `jarvis_do "install htop"` ran `apt-get install -y -- htop` with no confirmation. | No — there is nothing to confirm |
| 2 | Refused, with `outcome.status = "refused"`, `outcome.tier = 2` and a hint | **Yes** |
| 3 | Refused unconditionally; consent cannot lift it | No |

Two consequences for the UI:

1. **We must not promise that every `do` asks first.** A confirmation dialog on
   every `do` would be a lie in the other direction — it would imply the GUI is
   the thing holding the gate, when the kernel is. The GUI surfaces the kernel's
   decision; it does not invent one.
2. **Tier 3 must never render an approve button.** `Outcome.consent_required`
   is false for tier ≥ 3, so the prompt is never offered for something the
   kernel will refuse no matter what the owner clicks. Offering a button that
   cannot work is a false promise about the owner's authority.

### Refusal is not failure

> **Verified:** a refusal arrives with `isError: true`, exactly like a genuine
> failure. They are distinguished **only** by `payload.outcome.status ==
> "refused"`.

Treating `isError` alone as an error would report the safety kernel working
correctly as a malfunction. `classify_outcome` separates `REFUSED` from
`FAILED`, and the HUD styles a refusal as a warning with the kernel's own hint
attached, not as a fault.

### Where `allow` comes from

`allow: true` is generated in exactly one place in this codebase:
`Controller.approveConsent()`, called from the consent prompt. It is never
defaulted, never remembered, and never inferred from a previous approval.
`build_tool_call` raises if `allow` is passed to a read-only tool, so a confused
call site fails loudly instead of silently over-requesting authority.

The request re-sent after approval is the **verbatim** text the owner was shown
(`_last_do_request`), never a reconstruction of it. The owner approves the exact
words that go to the kernel.

The consent prompt itself has no default action, no timeout, and no keyboard
activation: Escape declines, and approving requires a deliberate pointer click.
An unattended machine must not drift into either answer, and a dialog that a
stray Enter can turn into "yes" is not consent.

## Payload shape

The useful payload is **double-encoded**: `result.content[0].text` is a JSON
*string* that must be parsed again.

Success shapes differ per tool:

- `jarvis_explain` → `{ai_text, claim, fact_id, machine, note, question, sources, status}`
- `jarvis_preview` → `{blast_radius, preview}` with `preview.steps[].description`
- `jarvis_do` → `{outcome}` with `steps[].argv`, `exit_code`, `requires_root`

Kernel text is capped at `MAX_TEXT_LENGTH` (4000 characters) before it reaches
the log renderer. The kernel is trusted, but not trusted to be bounded.

## Console verbs

| Verb | Tool | Notes |
| --- | --- | --- |
| `ask <question>` | `jarvis_explain` | Read-only |
| `plan <request>` | `jarvis_preview` | Read-only; shows the plan without running it |
| `do <request>` | `jarvis_do` | Never pre-authorised; the kernel decides |
| `agent status` | — | Local: connection state and kernel version |
| `agent disconnect` | — | Local: stops the subprocess |

The agent is **not** started automatically. Spawning a process that can change
the machine is the owner's decision, so it takes an explicit `connectAgent()`.

## Layering

`bridge/protocol.py` is pure: no Qt, no I/O. Framing, parsing and — importantly
— consent classification are all testable without spawning a subprocess, which
is why the security invariants in `tests/unit/test_bridge_protocol.py` can be
asserted directly against captured live frames.

`bridge/client.py` owns the `QProcess` and nothing else: line buffering across
chunk boundaries, an id→tag map, a 10 s handshake timeout, a 120 s request
timeout, and SIGTERM→SIGKILL shutdown.

## Verified end-to-end

Against the live kernel, via the real `Controller`:

- handshake → `version = 1.10.2`
- `jarvis_explain` → `OK`
- `jarvis_do "upgrade the whole system"` → `REFUSED`, tier 2, consent offered
- decline → nothing runs, prompt clears
- approve → re-sent with `allow: true`, kernel proceeds
- kernel resolved from the venv with a bare `PATH`
