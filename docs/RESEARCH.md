# RESEARCH — J.A.V.R.I.S. GUI

Status: **Research complete for Milestone 0 (stack selection + design language).**
Date: 2026-09-03. All statements below are either (a) cited to a source, or (b) marked
`VERIFIED-LOCAL` meaning I executed it in this workspace and observed the result.

---

## 1. What the JARVIS/Iron-Man HUD design language actually is

Findings are drawn from primary interviews with the people who designed the screens
(Jayse Hansen, Kent Seki), the VFX houses (Prologue, Cantina Creative), and the
sci-fi-interface critical literature.

| # | Design principle | Evidence |
|---|---|---|
| D1 | **Cyan/blue wireframe on near-black.** The HUD is "a dizzying mixture of blue wireframe motion graphics"; cyan was the deliberate dominant hue. | [scifiinterfaces — 1st person view](https://scifiinterfaces.com/2015/07/21/iron-man-hud-1-person-view/), [vfxblog oral history](https://vfxblog.com/ironman/) |
| D2 | **Mode-driven layouts, not one static screen.** The HUD reconfigures wholesale between "Analysis Mode", "Flight Mode", etc. — widgets migrate and the whole composition converts. | [vfxblog oral history](https://vfxblog.com/ironman/) |
| D3 | **Three input paths into the same surface:** JARVIS pushes info; Tony asks by voice; gaze/focus promotes a widget forward ("artificial foveation"). | [vfxblog oral history](https://vfxblog.com/ironman/) |
| D4 | **Elements live on concentric invisible spheres around the viewer**, so peripheral panels appear bowed/off-facing rather than flat. | [scifiinterfaces glossary](https://scifiinterfaces.com/category/marvel-cinematic-universe/iron-man/?order=asc) |
| D5 | **Later films moved from "2D elements in 3D space" to volumetric/holographic**, with optical flares and light interaction as a core motif. | [Maxon — Cantina Creative on Iron Man 3](https://www.maxon.net/en/article/cantina-creative-gives-iron-man-3-a-heads-up-with-maxon-cinema-4d) |
| D6 | **Every screen carries one message.** Each HUD beat was designed to say exactly one thing ("he's targeting all the aliens"). Decoration exists to *support* a readable state. | [TNW — interview with Jayse Hansen](https://thenextweb.com/news/jayse-hansen-on-creating-tools-the-avengers-use-to-fight-evil-touch-interfaces-and-project-glass) |
| D7 | **A written design bible governed consistency** — every component documented with purpose and lineage across suit versions. | [TNW — Jayse Hansen](https://thenextweb.com/news/jayse-hansen-on-creating-tools-the-avengers-use-to-fight-evil-touch-interfaces-and-project-glass) |
| D8 | **Documented usability flaw to avoid:** cryptic unlabelled telemetry (`N -8 W -97 RNG EL`) raises cognitive load; the stereoscopic multi-layering is physically impossible. | [scifiinterfaces](https://scifiinterfaces.com/2015/07/21/iron-man-hud-1-person-view/), [scifiinterfaces — impossible thing](https://scifiinterfaces.com/tag/iron-hud/?order=asc) |

**Design conclusions carried into our spec:** adopt D1–D7 as a *token-driven design
system* with a real, documented component bible (mirroring D7). Explicitly reject the
D8 failure mode: every numeric readout in our UI gets a human-readable label and unit.

## 2. Survey of existing JARVIS-GUI projects (what to learn, what to avoid)

| Project | Stack | Useful pattern | Gap we must not repeat |
|---|---|---|---|
| [hzaid01/Jarvis](https://github.com/hzaid01/Jarvis) | Electron + React + Tailwind | Clean split: HUD chrome / arc reactor / system stats / status bar; provider-registry abstraction over LLM backends | Windows-only; heavy Electron footprint |
| [dmrr35/Open.Jarvis](https://github.com/dmrr35/Open.Jarvis) | Python | **Explicit assistant state machine** — BOOTING, STANDBY, LISTENING, PROCESSING, EXECUTING, SPEAKING, ERROR, OFFLINE — driving the UI via a structured event stream. Also: "keyless degraded mode" so the UI is fully usable with no API keys | Windows-first |
| [eadmin2/jarvis_ai](https://github.com/eadmin2/jarvis_ai) | Python + vanilla-JS HUD | Cinematic entrance choreography for panels (Z-depth swoop, frame trace, scanline materialise); barge-in/interrupt handling | Browser-hosted, macOS-tested |
| [jincocodev/openclaw-jarvis-ui](https://github.com/jincocodev/openclaw-jarvis-ui) | Three.js | Three-layer audio visualiser (spectrum / ring / waveform) tied to a central orb reflecting agent state | Web app, not a Linux desktop app |
| [adityam1313/jarvis-hud](https://github.com/adityam1313/jarvis-hud) | React + Vite | Central orb w/ rotating dashed rings + tick marks; CRT scanline overlay; animated grid | Mock data only |
| [MuhammadFahru/jarvis-hud](https://github.com/MuhammadFahru/jarvis-hud) | Three.js + MediaPipe | Holographic globe, streaming severity-coloured terminal log | Simulated telemetry |

**Key gap in the field:** nearly every JARVIS GUI is Electron/web or Windows-first.
A native, GPU-accelerated, *Linux-native* HUD with real telemetry is genuinely
unoccupied ground — which justifies this project (Guideline 2).

**Adopted patterns (credited):** the explicit assistant state machine and
keyless/degraded-mode posture (Open.Jarvis, MIT); mode-driven layout switching (D2);
panel entrance choreography (jarvis_ai, MIT). No source code is copied; these are
architectural patterns, re-implemented in QML. Credits will also appear in
`docs/CREDITS.md` at implementation time.

## 3. Toolkit evaluation — Qt6 vs Flutter vs Tauri vs GTK4/GSK

The brief names four candidates. Only one can be the implementation stack; here is the
evidence-based comparison, including what I could actually verify in this environment.

### 3.1 Capability evidence

- **Qt 6 / Qt Quick.** GPU scene graph over QRhi (Vulkan/Metal/D3D/OpenGL). Custom
  shaders are first-class but must be pre-baked to `.qsb` via the `qsb` tool; inline
  GLSL strings were removed in Qt 6 and `ShaderEffect.fragmentShader` is now a URL
  ([Qt — Changes to Qt Quick](https://doc.qt.io/qt-6/quick-changes-qt6.html),
  [Qt blog — Graphics in Qt 6.0](https://www.qt.io/blog/graphics-in-qt-6.0-qrhi-qt-quick-qt-quick-3d)).
  `Shape`/`ShapePath` gives resolution-independent vector arcs rendered through the
  scene graph rather than software rasterisation, which is the recommended way to
  build animated gauges/rings — with the documented caveat that geometry generation
  is CPU-side, so prefer *one* `Shape` with multiple `ShapePath`s over many `Shape`s
  ([Qt — Shape](https://doc.qt.io/qt-6/qml-qtquick-shapes-shape.html)).
- **GTK4/GSK.** `GskGLShader` — the natural route for HUD glow/scanline effects — was
  **deprecated in GTK 4.16**; the 4.14 renderer rewrite dropped support and Vulkan
  integration made it impractical to keep. GTK now points custom-GL users at
  `GtkGLArea`, i.e. hand-rolled OpenGL outside the scene graph
  ([GTK docs — Gsk.GLShader](https://docs.gtk.org/gsk4/class.GLShader.html)).
  For a shader-heavy HUD this is a **material architectural risk**, not a preference.
- **Flutter.** Owns its renderer (Impeller), giving consistent frame pacing for
  animation-heavy UIs; cost is a ~30–80 MB bundle and Dart
  ([Tauri vs Flutter 2026](https://rustify.rs/articles/rust-tauri-vs-flutter-2026)).
- **Tauri.** Smallest footprint, but rendering is delegated to the OS WebView — on
  Linux that is WebKitGTK, and *"animation smoothness on Linux with WebKitGTK can be
  inconsistent"*. The same source concludes: apps with complex custom animations and
  pixel-critical graphics favour an owned renderer
  ([Tauri vs Flutter 2026](https://rustify.rs/articles/rust-tauri-vs-flutter-2026)).
  A HUD is precisely that category.
- Independent toolkit comparison reaches the same split: *"GTK is better for
  lightweight apps, while Qt excels at complex, animated UIs"*
  ([GTK vs Qt](https://linuxvox.com/blog/what-should-i-choose-gtk-or-qt/)).

### 3.2 Environment evidence — `VERIFIED-LOCAL`

Commands were run in this workspace on 2026-09-03 (Debian 12, x86_64, 2 vCPU, 3 GB RAM,
no `$DISPLAY`). Observed results:

| Check | Result |
|---|---|
| Debian apt mirrors (`deb.debian.org`, `ftp.debian.org`, mirrors.kernel.org, snapshot.d.o) | **unreachable** — `apt-get update` fails, `apt-get install libgl1` → *Unable to locate package* |
| PyPI / `files.pythonhosted.org` | reachable (HTTP 200) |
| `static.rust-lang.org`, `sh.rustup.rs`, `storage.googleapis.com` | **unreachable** |
| `cmake`, `pkg-config`, `cargo`, `rustc`, `flutter`, `qmake6` | not installed, not installable here |
| `gcc` 12.2.0, `node` v22, `python` 3.11.2 | present |
| `pip install PySide6-Essentials` (venv) | **succeeded — PySide6 6.11.2 / Qt 6.11.2** |
| Rendering a QML `Shape`+`PathAngleArc` HUD arc headless (`-platform offscreen`, software backend) and grabbing the frame | **succeeded — 400×300 PNG produced, arc + letter-spaced type rendered correctly** |

Consequences, stated plainly:

- **Tauri is not buildable here** (no Rust toolchain, no way to fetch one).
- **GTK4 is not buildable here** (no apt, no `pkg-config`, no GTK dev headers) — and
  is independently disqualified on the deprecated-shader grounds above.
- **Flutter is not buildable here** (no SDK, `storage.googleapis.com` blocked) and its
  Linux desktop build additionally needs CMake/GTK dev packages we cannot install.
- **Qt 6 is buildable, runnable and testable here today** via the PySide6 wheels.

`libGL.so.1`/`libEGL.so.1`/`libdbus`/`libxkbcommon` are absent from the base image; I
made Qt import by generating version-scripted no-op stub libraries from the exact
undefined symbols in the Qt shared objects. **This is a sandbox-only CI shim for
headless rendering — it is not part of the product and will be confined to a clearly
labelled test-harness script, never to runtime code.** On a real Linux desktop these
libraries are present and no shim is involved.

### 3.3 Licensing

PySide6 is **LGPLv3 / GPLv2 / GPLv3** (commercial optionally available)
([PyPI — PySide6](https://pypi.org/project/PySide6/)). Using it as an unmodified
imported library does not impose source-disclosure on our application code, unlike
PyQt6 which is GPLv3 ([PythonGUIs — PyQt6 vs PySide6 licensing](https://www.pythonguis.com/faq/not-an-open-source-application-which-one-to-use-pyqt5-or-pyside2/)).
**Therefore: PySide6, not PyQt6.** We will dynamically link (normal pip install), keep
Qt unmodified, and ship LGPL notices.

### 3.4 Recommendation

**Qt 6 (Qt Quick / QML + PySide6), targeting Linux.** It is the only named candidate
that is simultaneously (a) documented-best for complex animated GPU UIs, (b) free of a
deprecated-critical-path problem, and (c) verifiably buildable, runnable and testable
in this environment. Flutter/Tauri/GTK4 remain documented alternatives in this file;
the decision is reversible only at high cost, so it is escalated to you before any
product code is written (Guideline 20).

## 4. Testing approach evidence

- Qt Quick Test (`tst_*.qml` + `TestCase`) is the supported QML unit-test harness, and
  Qt documents `-platform offscreen` as the way to run it without a display
  ([Qt Quick Test](https://doc.qt.io/qt-6/qtquicktest-index.html)).
- Qt's own test guidance says to **avoid bitmap capture/comparison** as a primary
  assertion (resolution, theme, fonts make it flaky) and to prefer property assertions
  plus `QTRY_*`-style polling over fixed sleeps
  ([Qt Test Best Practices](https://doc.qt.io/qt-5/qttest-best-practices-qdoc.html)).
  Our plan follows this: property/state assertions are the gate; screenshots are
  review artefacts only, never a pass/fail condition.
- `pyside6-qmllint` 6.11.2 is available in the venv (`VERIFIED-LOCAL`) and will be a
  CI gate.

## 5. Open questions requiring your direction

Recorded here for auditability; asked of you directly in chat.

1. Confirm Qt 6 + QML/PySide6 as the stack (vs. Flutter / Tauri / GTK4).
2. Is this a **standalone HUD shell with real local telemetry**, or must it integrate
   an existing assistant backend (LLM / STT / TTS)?
3. Python (PySide6) or C++ (Qt6 native) for the backend layer — noting only Python is
   verifiable in this sandbox.
