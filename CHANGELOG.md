# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
