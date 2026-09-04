# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **ASSISTANT mode** — a modal takeover in which the assistant itself, rather
  than the machine, owns the display. Reachable with `mode assistant` or by
  cycling with TAB. The instrument rail is withdrawn while it is up.
- **`AssistantOrb` component** — a per-state presence modelled on the Voice HUD
  in the user's own web project (`docs/RESEARCH.md` §17-21): a travelling-wave
  rim for LISTENING, counter-rotating scanners for PROCESSING, staggered
  ripples for SPEAKING, and a determinate arc for EXECUTING. One shared 1500 ms
  phase clock drives every derived animation rather than one animator per bar.
- Plain-language caption under the orb naming what each state means, which is
  the corrective to the unlabelled-telemetry problem recorded as D8.

### Changed
- A fault is now coherent across the whole orb: the standing arcs follow the
  fault colour instead of staying cyan, which previously read as "partly fine".
- Faulted states are **still**. A fault is not a mood.

### Fixed
- `tools/headless_render.py` walked illegal state transitions (e.g. straight
  from STANDBY to SPEAKING), which the state machine correctly refused, so it
  silently captured the wrong state. It now follows a legal route and fails
  loudly if it does not arrive.

### Added — M8: motion language (2026-09-04)

A third research round, this time into how the reference material *moves*, plus
a study of the user's own earlier JARVIS GUI
(`github.com/Anish932-hash/JARVIS_GUI`, Next.js). Principles D15-D19 in
`docs/RESEARCH.md`. The governing finding is from the original HUD team: depth
came from *how elements moved*, not from perspective — which means a flat
monitor loses nothing.

- `AmbientField.qml` — the atmosphere layer: area-scaled drifting motes
  (`QtQuick.Particles`), one slow scanline, and a vignette that also raises
  central contrast for escalated alerts.
- `BootSequence.qml` — power-on choreography in three phases: energy streaks
  converge from beyond the frame, three rings trace themselves in at different
  rates, then the name assembles letter by letter. Implemented as a **pure
  function of `progress`** rather than a timer chain, so any frame is
  reproducible and testable.
- **Alpha events** (`ReactorCore.pulse()`): every assistant state change now
  emits one outward-travelling ring, so a transition is felt rather than merely
  relabelled.
- **Breathing halo** and a **PROCESSING radar sweep** on the core — the sweep
  runs only while the assistant is actually working, so the motion means
  something.
- **Pointer parallax** across three depth layers, and **staggered entrances**
  via `HudSurface.entrance()`.
- Motion tokens in `Theme.qml`, with mutually non-harmonic periods so the
  ambient field never visibly loops.
- `javris --no-ambient` and `Theme.ambientMotion` — a real off switch for all
  decorative motion.
- `tools/headless_render.py --boot-progress`, to capture any frame of the boot
  sequence for review.

### Changed
- Every pre-existing infinite animation (ring rotation, inner-ring pulse) is now
  gated on `Theme.ambientMotion`, so the off switch is genuinely complete rather
  than covering only the new work.

### Fixed
- The boot title used a `Row`, which sizes itself to its *visible* children, so
  the word crept sideways as letters revealed. Letters are now placed at fixed
  offsets measured from the font.
- The boot overlay had no backdrop, so the live HUD showed through and the two
  competed. It now owns the screen and clears just before the title lands.
- The boot streaks were short and dim enough to read as tick marks rather than
  converging energy.
- Header chrome was fully visible during boot, over the overlay. It now enters
  on the same stagger as the rest of the HUD.
- `--boot-progress` silently rendered a *different* frame than requested,
  because `bootProgress` carries a `Behavior` and assigning it retargets an
  animation rather than setting a value. The tool now reasserts the value at
  capture time and prints what it actually captured.

### Verified
- `QtQuick.Particles` and `QtQuick.Effects` were confirmed available and loading
  under the software backend by rendering a probe file — not assumed.
- All seven gates pass: ruff, mypy strict (12 files), 158 unit tests, qmllint
  clean on 14 QML files, **48 Qt Quick tests** (up from 29), headless render.
- `set_ambient_motion()` was exercised against the real `Theme` singleton and
  observed to toggle and restore.
- Boot frames at progress 0.30 / 0.80 / 0.85 / 1.00 rendered and visually
  inspected, plus the escalation and PROCESSING frames re-checked for
  regressions.

### Not verified
- No GPU, X11 or Wayland rendering; software backend only. **No frame-rate
  measurement was taken, so no claim is made that the particle field, parallax
  or boot sequence hold 60 fps on real hardware.** This is the change most
  likely to cost performance and it is the one thing that could not be measured
  here.
- Pointer parallax has not been exercised with a real mouse; only the binding
  path was verified.

### Fixed (docs)
- `docs/images/hud-diagnostics.png` — the README's lead screenshot — was still
  the M6 render, predating both attention escalation and the motion language.
  Regenerated, so the first image a reader sees matches the current build.
- `docs/images/hud-monitor.png` was committed but referenced by no document.
  Now shown in the README with the reactor core in `PROCESSING`.

### Considered and rejected
- The `waveform-bar` audio visualiser from the reference project. We have no
  audio input, so animating it would be fabricating a signal.
- The Orbitron webfont used by that project — no bundled fonts, and only DejaVu
  is available here.
- A full scanline raster over the whole HUD: it reduces glyph legibility, which
  D14 rules out for a tool. One soft travelling band is used instead.

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
