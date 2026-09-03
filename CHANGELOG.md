# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — M7: attention escalation (2026-09-03)

A second research round focused on HUD *behaviour* rather than appearance. The
findings are recorded as principles D9-D14 in `docs/RESEARCH.md`, and the one
that changed the product is this, from the source analysis itself: small
peripheral gauges cannot capture attention, because foveal vision is narrow, so
a competent assistant hides lower-priority data and promotes the problem into
the main display. "Attention management is crisis management."

- `src/javris/attention.py` — the escalation policy, as pure testable Python
  with no Qt dependency. Classifies each metric, requires a **sustained**
  condition before raising (3 polls), applies **hysteresis** on release so a
  value hovering on a threshold cannot flap the centre of the HUD, and promotes
  **at most one** condition at a time.
- `AlertBanner.qml` — the escalated condition rendered large and high-contrast
  over the mode surface, with the rest of the HUD dimmed to 0.28. Carries one
  number and one sentence; no additional detail, per principle D10.
- `TargetReticle.qml` — four corner brackets that converge from an oversized
  scale, implementing "acquire, then annotate" (D13). Reusable independently of
  alerts.
- `Theme.fontSizeHero` (64 px), reserved for the escalated readout.
- Controller: `alertActive`, `alertLabel`, `alertReadout`, `alertUnit`,
  `alertAdvice`, `alertSeverity`, `alertFraction` and the `alertChanged` signal.
- CPU, memory, swap and every mounted filesystem are escalatable. Uptime,
  throughput and load average deliberately are **not**: they have no saturation
  point, so a "how full is it" fraction would have to be invented.
- `tools/headless_render.py --simulate-alert`, a review-only synthetic reading
  so the overlay can be photographed on an idle machine. Not reachable from the
  application.

### Fixed
- The header claimed `NOMINAL` while a `CRITICAL` alert was on screen — caught
  only by looking at a rendered frame, not by any test. The status now reports
  the escalated severity, which outranks both the degraded notice and
  `NOMINAL`.
- The alert backdrop at 0.88 opacity let the reactor core ghost through the hero
  readout — the exact low-contrast failure the research warns against. Now fully
  opaque.
- Suppression initially dimmed only the vitals rail, leaving the mode surface at
  full brightness competing with the alert. It now dims the mode surface too.
- An alert held inside the hysteresis band classified as `NORMAL` and would have
  rendered with no severity colour; it now reports `WARN`.
- Releasing on "metric became central" or "metric became unavailable" was
  incorrectly subject to the recovery streak. Both now release immediately:
  hysteresis guards against a *value* oscillating, and delaying either would
  leave the HUD displaying something untrue. Caught by a failing test.

### Changed
- Mode switching re-runs the escalation policy synchronously, because prominence
  is mode-dependent. Previously the HUD could be wrong for up to one poll.

### Verified
- All seven quality gates pass: ruff lint + format, mypy strict (12 files),
  **158 unit tests** (up from 120), qmllint clean on 12 QML files, **29 Qt Quick
  tests** (up from 18), headless render at 1440x900.
- The escalation overlay was rendered and visually inspected at
  `build/hud-alert.png`; the unescalated MONITOR frame was re-rendered and
  confirmed unchanged.

### Not verified
- No GPU, X11 or Wayland rendering; the software backend is all that is
  available here. No frame-rate measurement, so no claim is made about the
  animation smoothness of the escalation transition.
- The escalation has not been observed against a *genuinely* saturated machine —
  only against fixture and synthetic readings driven through the real policy.

### Considered and rejected
- Bundling a squared-geometric font (Eurostile, Bank Gothic). Both are
  commercially licensed; the machined feel is obtained instead through wide
  letter-spacing on upper-case labels. Only DejaVu is available in this
  environment (verified).
- Webcam/gesture input, 3D holographic depth, and a location/map panel. The last
  is the important one: with no location data, a map would be fabrication.

### Added — M1-M6: first working HUD (2026-09-03)

#### Telemetry (`src/javris/telemetry/`)
- `ProcReader`, the single module permitted to read `/proc` and `/sys`. Parses
  `/proc/stat` (aggregate and per-core jiffies), `/proc/meminfo`, `/proc/loadavg`,
  `/proc/uptime`, `/proc/net/dev`, `/proc/mounts` and `/sys/class/thermal`.
  The filesystem root is injectable, so the layer is tested entirely against
  fixtures with no access to the real `/proc`.
- Rejects incoherent samples rather than reporting nonsense: counters that move
  backwards across suspend or CPU hotplug, mismatched CPUs, non-positive
  intervals, and thermal readings outside a physically plausible range.
- Excludes pseudo-filesystems from storage reporting and loopback from network
  throughput.
- `TelemetrySampler` converts successive readings into `TelemetrySnapshot`
  values, computing rate-derived metrics from deltas. The first sample after
  start reports rates as unknown rather than inventing them from one reading.
- Every unreadable source is named in `degraded_sources` and surfaced in the UI.

#### State and commands
- `AssistantState` with an explicit eight-state transition table; illegal
  transitions raise `InvalidTransitionError`. `ERROR` and `OFFLINE` are
  reachable from anywhere, and a test proves no state is a dead end.
  Pattern credited to Open.Jarvis (MIT) in `docs/CREDITS.md`.
- `CommandRouter`: allow-list dispatch with no shell execution, no process
  spawning and no network. Input is length-capped and control characters are
  stripped before parsing.

#### Controller
- `HudController`, the single QML-facing object. Owns assistant state, drives
  telemetry polling on a `QTimer`, routes console commands, and performs all
  display formatting so QML holds no business logic.
- Telemetry degradation is logged once on transition rather than on every poll.
- The console log is bounded at 200 lines.
- Polling interval is floored at 200 ms.

#### Interface (`src/javris/ui/`)
- `Theme.qml`, a singleton holding every colour, spacing, duration and type
  token, plus the semantic `loadColor` and `severityColor` functions. No
  component declares a literal colour or magic number.
- Components: `Panel` (self-sizing, cut-corner frame), `Gauge` (labelled radial
  gauge with an explicit unavailable state), `ReactorCore` (state- and
  load-encoding concentric rings with a tick scale), `TelemetryRow`, `LogStream`
  (severity-coloured, auto-scrolling) and `HudGrid`.
- Modes: `DiagnosticsMode` and `MonitorMode`, cross-faded within a 300 ms budget.
- `HudSurface.qml` shell with boot sequence, header, vitals rail and console;
  `Main.qml` frameless full-screen window with a `--windowed` alternative.
- Keyboard: `Tab` cycles mode, `Esc` focuses the console.

#### Tooling and tests
- 120 Python unit tests and 18 Qt Quick Test cases, all passing. 89% total
  coverage; 95-100% on the telemetry, state and command modules.
- `tools/check.sh`, the quality gate: ruff lint, ruff format, mypy `--strict`,
  pytest, qmllint, Qt Quick Test, headless render.
- `tools/generate_qmltypes.py` generates the QML type description from the live
  `QMetaObject`, so tooling cannot drift from the implementation.
- `tools/headless_render.py` renders the HUD offscreen to a PNG for review.
- `tools/sandbox_gl_stubs.py` generates version-scripted stub libraries so Qt can
  be imported in containers lacking `libGL`/`libEGL`/`libdbus`/`libxkbcommon`.
  Development-only and never part of the product.

#### Documentation
- `README.md`, `docs/DESIGN-SYSTEM.md` (the component bible),
  `docs/CREDITS.md`, `THIRD-PARTY-NOTICES.md`, `LICENSE` (MIT).

### Fixed
- `ReactorCore` exposed a property named `state`, shadowing the built-in
  `QQuickItem.state`. Renamed to `coreState`.
- Mode components declared `id: root`, which shadowed the shell's `root` inside
  `Component` scope and silently bound `controller` to the mode itself.
- `Panel` required callers to compute a height from the panel's own children,
  which is a circular binding. It now sizes itself to its content.
- `TelemetryRow` anchored a `Row` by baseline; a `Row` has no baseline of its
  own, so values misaligned and could overlap the label.
- Replaced context properties with a registered QML singleton, eliminating every
  remaining `qmllint` unqualified-access warning.
- `Loader` evaluated mode bindings before initial properties were applied, so a
  `required property` read as null on the first pass.
- The headless renderer destroyed its view during interpreter shutdown, after
  context properties had gone, producing a wall of spurious `TypeError` output.
- Packaging omitted the `qmldir` and `.qmltypes` files, so a clean
  `pip install .` produced an application that could not resolve its own QML
  modules. Caught by installing into a fresh virtualenv and launching it.

### Changed
- Chose Qt 6 / QML with PySide6 over Flutter, Tauri and GTK4/GSK, on the evidence
  recorded in `docs/RESEARCH.md` and confirmed by the stakeholder.
- PySide6 (LGPLv3) over PyQt6 (GPLv3), to avoid imposing source-disclosure terms.
- Zero runtime dependencies beyond PySide6; `psutil` was deliberately rejected,
  since its Linux data comes from the same `/proc` files.

### Verified
- `./tools/check.sh` passes end to end: ruff clean, ruff format clean, mypy
  `--strict` clean on 11 files, 120 unit tests passing, qmllint clean on all 10
  QML files, 18 QML tests passing, headless render producing a 1440x900 frame.
- A clean `pip install .` into a fresh virtualenv, launched via the `javris`
  entry point, starts and exits 0 with no QML errors.

### Not verified
- No rendering on real GPU hardware, X11 or Wayland: the development sandbox has
  no `$DISPLAY` and no GL driver. All rendering used the software rasteriser via
  `-platform offscreen`.
- No frame-rate measurement. Any performance target in the plan is a target, not
  a measurement.

## [Unreleased] — earlier

### Added — M0: Research & Planning (2026-09-03)

- `docs/RESEARCH.md` — structured research with citations covering:
  - the JARVIS/Iron Man HUD design language, sourced from primary interviews with
    its designers (Jayse Hansen, Kent Seki), Cantina Creative/Prologue coverage,
    and the sci-fi-interface critical literature, distilled into eight design
    principles (D1-D8);
  - a survey of six existing open-source JARVIS GUI projects, recording the
    patterns worth adopting, the credits owed, and the gap this project fills;
  - an evidence-based toolkit evaluation of Qt 6, Flutter, Tauri and GTK4/GSK,
    including the GTK 4.16 deprecation of `GskGLShader`;
  - PySide6 (LGPLv3) vs PyQt6 (GPLv3) licensing analysis;
  - a `VERIFIED-LOCAL` record of what was actually executed in this workspace,
    including a successful headless QML render.
- `docs/PLAN.md` — scope and requirements with acceptance criteria, architecture,
  tech-stack decision table, coding standards and quality gates, six milestones,
  risk register, changelog/experience workflow, folder structure, and a starter
  vertical-slice outline.
- `AGENT-EXPERIENCE.md` — development log.

[Unreleased]: https://github.com/thecyberexpert123-stack/J.A.V.R.I.S.-GUI/commits/main
