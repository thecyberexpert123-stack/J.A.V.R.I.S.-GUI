# J.A.V.R.I.S. GUI — Delivery Plan

Owner: engineering (agent, acting as senior front-end/full-stack).
Status: **awaiting stakeholder sign-off. No product code written yet.**
Evidence base: [`docs/RESEARCH.md`](./RESEARCH.md).

---

## 1. Scope and requirements

### 1.1 Product definition

A **native Linux desktop heads-up display** — a serious, GPU-accelerated operations
console in the JARVIS design language, not a wallpaper or a screenshot mock. It
displays *real* data about the machine it runs on and reacts to *real* input.

### 1.2 In scope (proposed — subject to your confirmation)

| ID | Requirement | Acceptance criteria |
|---|---|---|
| R1 | **HUD shell** — frameless, full-screen-capable window; boot sequence; cyan-on-black token-driven theme (RESEARCH D1) | App launches on X11 and Wayland; boot sequence completes deterministically in ≤2 s; every colour/metric/duration comes from one `Theme` singleton, zero hard-coded hex in components |
| R2 | **Mode-driven layout** (RESEARCH D2) — at minimum `DIAGNOSTICS` and `MONITOR` modes that recompose the surface | Mode switch is animated, ≤300 ms, driven by a single state property; unit-tested |
| R3 | **Assistant state machine** (pattern credit: Open.Jarvis) — `BOOTING / STANDBY / LISTENING / PROCESSING / EXECUTING / SPEAKING / ERROR / OFFLINE` | Illegal transitions rejected and unit-tested; every state has a distinct, documented visual signature |
| R4 | **Real telemetry** — CPU per-core, memory, disk, network, thermals, uptime, load, from `/proc` and `/sys` | Values cross-checked against `/proc` ground truth in tests; **every readout labelled with name + unit** (explicitly fixing RESEARCH D8) |
| R5 | **Core reactor widget** — animated concentric rings/gauges bound to live load | Built from `Shape`/`ShapePath` per Qt guidance; holds 60 fps target; degrades gracefully on software rendering |
| R6 | **Command console** — text command entry + severity-coloured streaming log | Commands validated against an explicit allow-list; unknown input rejected with a clear message, never executed |
| R7 | **Failure behaviour** — unreadable `/proc` node, missing sensor, no GPU, no compositor | Each degrades to an explicit `OFFLINE`/`UNAVAILABLE` indicator; app never crashes, never shows a fake number |
| R8 | **Packaging + docs** | `pip install -e .` + single entry point; README, CHANGELOG, AGENT-EXPERIENCE, LICENSE/third-party notices |

### 1.3 Explicitly out of scope for v1 (recorded as recommendations, per Guideline 19)

LLM integration, speech-to-text, text-to-speech, wake word, camera/gesture input,
network/cloud services, desktop automation, plugin system. Each is a separate,
separately-justified milestone. **No API keys, no outbound network calls in v1.**

### 1.4 Non-goals

Not a Windows/macOS app in v1. Not an Electron/web app. Not a screensaver.

## 2. Architecture overview

Strict separation: QML owns *presentation only*; Python owns *data and policy*.
Nothing in QML reads `/proc`; nothing in Python emits colours.

```
┌─────────────────────────── QML presentation layer ───────────────────────────┐
│  Hud.qml (shell)                                                             │
│    ├── Theme (singleton: colour/space/motion/type tokens)                    │
│    ├── components/  ReactorCore · Gauge · Panel · TelemetryRow · LogStream    │
│    └── modes/       DiagnosticsMode.qml · MonitorMode.qml                     │
└──────────────────────────────────▲───────────────────────────────────────────┘
                    Q_PROPERTY / Signal  (read-only to QML)
┌──────────────────────────────────┴─── Python backend (PySide6) ──────────────┐
│  HudController   — owns AssistantState; validates transitions                │
│  TelemetryService— QTimer-polled; async-safe; emits typed snapshots          │
│  ProcReader      — the ONLY module touching /proc and /sys; fully unit-tested│
│  CommandRouter   — allow-list dispatch; no shell execution in v1             │
└──────────────────────────────────────────────────────────────────────────────┘
```

Design rules: one-directional data flow (backend → QML); QML never mutates backend
state except through explicit `@Slot` calls; `ProcReader` is pure and injectable so
telemetry is testable against fixture files with **zero** real `/proc` access.

## 3. Tech stack decisions

| Decision | Choice | Justification | Reversibility |
|---|---|---|---|
| Toolkit | **Qt 6 / Qt Quick (QML)** | RESEARCH §3 — only candidate that is best-in-class for animated GPU UI *and* verifiably buildable/testable here | Expensive — needs your sign-off |
| Binding | **PySide6 (LGPLv3)** | Official Qt binding; LGPL avoids PyQt6's GPL obligations (RESEARCH §3.3); verified working | Low — QML layer is binding-agnostic |
| Shapes | `QtQuick.Shapes` | Scene-graph vector rendering; Qt-recommended over `Canvas` | Low |
| Shaders | Deferred to a later milestone | Qt 6 requires pre-baked `.qsb`; `pyside6-qsb` is **broken in this venv** (`VERIFIED-LOCAL`) — so v1 achieves glow with layered `Shape` strokes + opacity, no fake claims | Low |
| Telemetry | Python stdlib reading `/proc`, `/sys` | Zero new dependencies (Guideline 16); `psutil` deliberately **rejected** — its Linux data comes from the same files | Low |
| Tests | `pytest` (backend) + Qt Quick Test `-platform offscreen` (QML) | Qt-documented headless approach | Low |
| Runtime deps | **PySide6-Essentials only** | Discipline | — |

## 4. Coding standards and quality gates

- **Python:** type-annotated, `ruff` lint + format, `mypy --strict` on `src/`, Google-style docstrings on public API.
- **QML:** `pyside6-qmllint` clean (verified available); one component per file; no magic numbers or literal colours outside `Theme.qml`; no JS business logic in QML.
- **Tests:** every backend module has unit tests; parsers tested against captured `/proc` fixtures *and* malformed input. Per Qt guidance, **no bitmap comparison as a pass/fail gate**; screenshots are review artefacts only.
- **Security:** no shell execution; no network; read-only `/proc` access with explicit path validation; command input allow-listed; no secrets anywhere in the repo.
- **CI gate (must all pass before any commit is proposed as done):** `ruff` → `mypy` → `pytest` → `qmllint` → headless QML render smoke test.
- Conventional Commits; every change lands with a CHANGELOG entry.

## 5. Milestones and deliverables

| M | Deliverable | Acceptance |
|---|---|---|
| **M0** | Research + plan + governance docs *(this commit)* | You sign off on stack + scope |
| **M1** | Repo skeleton, tooling, CI config, `Theme.qml` design-token system, LICENSE/notices | `ruff`/`mypy`/`qmllint` pass on an empty-but-real tree |
| **M2** | `ProcReader` + `TelemetryService` + full unit tests against fixtures | ≥90 % coverage on parsers; malformed-input tests pass |
| **M3** | `HudController` + assistant state machine + transition tests | Illegal transitions provably rejected |
| **M4** | HUD shell, boot sequence, ReactorCore, Gauge, Panel, TelemetryRow | Headless render produces the frame; qmllint clean |
| **M5** | Modes (R2), LogStream, CommandRouter (R6), failure states (R7) | Every failure mode in R7 demonstrated by a test |
| **M6** | Packaging, README, run instructions, final self-review | `pip install -e .` then one command launches it |

## 6. Risks and mitigations

| Risk | Sev | Mitigation |
|---|---|---|
| **No GPU/`$DISPLAY` in this sandbox** — I can render headless but cannot personally observe 60 fps or Wayland behaviour | High | Software-backend headless rendering as the CI gate; I will state explicitly in every report what was *not* verified. **You must run it on real hardware for visual/perf acceptance.** |
| Stub `libGL`/`libEGL` shims needed for headless Qt here | Med | Confined to a labelled `tools/` dev script, never imported by product code; documented in AGENT-EXPERIENCE |
| `Shape` triangulation is CPU-side; over-use tanks perf | Med | Follow Qt guidance: one `Shape`, many `ShapePath`; cap animated path-property changes; `asynchronous: true` |
| `pyside6-qsb` broken here → cannot bake shaders | Med | v1 uses no custom shaders; glow via layered strokes. Shaders are a future milestone, honestly deferred |
| Aesthetic drift into "junk decoration" (Guideline 7) | Med | RESEARCH D6 enforced: every element must carry information or be cut. Component bible per D7 |
| Debian mirrors unreachable → cannot add system packages | Med | Stack chosen to need none (pure pip) |
| Scope creep into a full AI assistant | Med | §1.3 freeze; extras land in a Recommendations section, not in code |

## 7. Changelog & experience workflow

- `CHANGELOG.md` — Keep a Changelog format, semver, one entry per milestone under `[Unreleased]`, written *in the same commit* as the change.
- `AGENT-EXPERIENCE.md` — per-milestone: what was attempted, what broke, what was learned, what remains unverified. Every "verified" claim names the command that produced it.
- `docs/RESEARCH.md` — living; new sources appended with citations.

## 8. Proposed folder structure

```
J.A.V.R.I.S.-GUI/
├── CHANGELOG.md
├── AGENT-EXPERIENCE.md
├── README.md
├── LICENSE                        # + THIRD-PARTY-NOTICES.md (LGPL/Qt)
├── pyproject.toml                 # deps, ruff, mypy, pytest config
├── docs/
│   ├── PLAN.md  RESEARCH.md  ARCHITECTURE.md  DESIGN-SYSTEM.md  CREDITS.md
├── src/javris/
│   ├── __main__.py                # entry point
│   ├── controller.py              # HudController + AssistantState
│   ├── telemetry/  proc_reader.py  service.py  models.py
│   ├── commands/   router.py
│   └── ui/
│       ├── Hud.qml  Theme.qml  qmldir
│       ├── components/  ReactorCore.qml  Gauge.qml  Panel.qml  TelemetryRow.qml  LogStream.qml
│       └── modes/       DiagnosticsMode.qml  MonitorMode.qml
├── tests/
│   ├── unit/       test_proc_reader.py  test_controller.py  test_router.py
│   ├── fixtures/   proc/…            # captured /proc samples + malformed cases
│   └── qml/        tst_Gauge.qml  tst_ReactorCore.qml
└── tools/          headless_render.py   # dev-only; documents the sandbox GL shim
```

## 9. End-to-end starter outline (illustrative — not yet implemented)

M1–M2 vertical slice, smallest thing that is genuinely real end to end:

1. `ProcReader.cpu_times()` parses `/proc/stat` → typed dataclass; unit-tested against a fixture and against a truncated/garbage fixture.
2. `TelemetryService` polls it on a `QTimer` (default 1 000 ms, configurable), computes per-core utilisation from deltas, exposes it as a read-only `Q_PROPERTY`, emits `snapshotChanged`.
3. `Theme.qml` defines the tokens; `Gauge.qml` binds one `ShapePath` arc sweep to one normalised 0–1 value and renders its label + unit.
4. `Hud.qml` composes gauges from the live snapshot.
5. `tests/qml/tst_Gauge.qml` asserts `sweepAngle` for value 0, 0.5, 1 — a property assertion, not a screenshot.
6. `tools/headless_render.py` writes a PNG for human review only.

Only step 6 is proven to work in this sandbox today (`VERIFIED-LOCAL`, RESEARCH §3.2).
Everything else is designed but unwritten.

## 10. Sign-off gate

Per Guidelines 9 and 20, **no product code is written until you confirm**: the toolkit
(§3), the v1 scope boundary (§1.2 / §1.3), and Python vs C++ for the backend.
