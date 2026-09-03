# Agent Experience Log

A candid record of what was attempted, what broke, what was learned, and what remains
unverified. Every claim of verification names the command that produced it.

---

## M0 — Research & Planning (2026-09-03)

### What I set out to do

Choose between the four named toolkits (Qt6, Flutter, Tauri, GTK4/GSK) on evidence
rather than preference, research what a JARVIS HUD actually is, and produce a plan
before writing any product code.

### Challenges encountered

**1. The repository was effectively empty.**
`git log` showed a single "Initial commit" and the tree contained one file, a two-line
`README.md`. There was no existing architecture, dependency set, configuration or test
suite to inspect — so guideline 12 ("inspect before modifying") resolved to
"there is nothing to preserve, and every decision is still open". That raised the bar
on guideline 9: with no precedent, the stack choice must be justified from scratch.

**2. The sandbox has no system package manager access.**
`apt-get update` failed on every Debian mirror; `deb.debian.org`, `ftp.debian.org`,
`mirrors.kernel.org` and `snapshot.debian.org` all returned connection failures, while
PyPI and GitHub were reachable. `apt-get install libgl1` returns *Unable to locate
package*. This single fact eliminated three of the four candidate toolkits from being
*verifiable* here: Tauri needs a Rust toolchain (`static.rust-lang.org` blocked),
Flutter needs its SDK (`storage.googleapis.com` blocked) plus CMake/GTK dev packages,
and GTK4 needs `pkg-config` and dev headers. Qt 6 survived only because PySide6 ships
self-contained manylinux wheels.

The important discipline here was **not to let convenience masquerade as architecture**
(guideline 20). "Qt is the only one I can build" is a real and decisive constraint, but
it is not by itself a good technical reason — so I went and found the independent
technical case too, and the strongest one turned out to be about GTK: `GskGLShader` was
deprecated in GTK 4.16 because the 4.14 renderer rewrite dropped support for it. For a
glow-and-scanline HUD that is a deprecated critical path, which is a genuine
architectural disqualifier independent of this sandbox. I have written both reasons
into `docs/RESEARCH.md` and still escalated the decision rather than assuming it.

**3. Qt would not import: four missing shared libraries.**
`from PySide6.QtGui import QGuiApplication` failed with
`ImportError: libGL.so.1: cannot open shared object file`. `ldd libQt6Gui.so.6` showed
four unresolved: `libGL.so.1`, `libEGL.so.1`, `libdbus-1.so.3`, `libxkbcommon.so.0`.

My first attempt — trivial one-symbol stub `.so` files — got further but then failed
with `undefined symbol: dbus_server_get_address, version LIBDBUS_1_3`. The lesson: the
loader checks *symbol versions*, not just soname. The fix that worked was to extract
every undefined `gl*`/`egl*`/`dbus_*`/`xkb_*` symbol from all the Qt shared objects and
plugins with `nm -D --undefined-only --with-symbol-versions`, generate no-op C stubs
(41 GL, 26 EGL, 89 dbus, 42 xkb), and link each with a matching `--version-script`.

**This shim is a sandbox artefact and must never touch product code.** Real Linux
desktops have these libraries. I am recording it because a future maintainer running
tests in a minimal container will hit exactly this wall — and because silently shipping
stubbed graphics libraries would be precisely the kind of thing guideline 1 forbids.

**4. Verifying the stack for real rather than assuming it.**
With the shim in place I ran a genuine end-to-end check: a QML file using
`Shape`/`ShapePath`/`PathAngleArc` — the exact primitive the reactor gauges will be
built from — loaded through `QQuickView` under `QT_QPA_PLATFORM=offscreen` with the
software backend, then `grabWindow()` to a PNG. It produced a correct 400×300 image
with a clean cyan arc and letter-spaced type. That is the difference between "Qt should
work" and "Qt works here, and here is the picture".

**5. `pyside6-qsb` is broken in this venv.** It tracebacks on `--help`. Qt 6 removed
inline GLSL and requires shaders pre-baked to `.qsb`, so custom shaders are simply not
available to me right now. Rather than write shader code I cannot compile or test, I
scoped v1 to achieve glow with layered `Shape` strokes and opacity, and recorded shaders
as an honestly-deferred future milestone.

### Learning moments

- **Deprecation notices are architecture signals.** The GTK 4.16 `GskGLShader`
  deprecation was worth more to this decision than any framework benchmark blog post.
- **Cinema research changed the requirements, not just the palette.** Reading the
  designers' own accounts surfaced two things I would not have invented: the HUD is
  *mode-driven* (it recomposes wholesale between Analysis and Flight modes), and the
  critical literature identifies a real usability flaw — unlabelled cryptic telemetry
  like `N -8 W -97 RNG EL`. So R4 now mandates a label and unit on every readout. The
  reference is the *inspiration*, not the specification.
- **Surveying prior art paid off twice**: it produced a genuinely reusable pattern (the
  explicit eight-state assistant machine from Open.Jarvis, credited) and it justified
  the project's existence — almost every JARVIS GUI out there is Electron/web or
  Windows-first, so a Linux-native GPU HUD is an unoccupied niche rather than
  another showcase.
- **Licensing is a design input.** PySide6's LGPLv3 vs PyQt6's GPLv3 is a real
  downstream constraint, and choosing the binding on licence rather than habit costs
  nothing now and can save a lot later.

### Explicitly NOT verified

- Any rendering on real GPU hardware, X11, or Wayland — this sandbox has no `$DISPLAY`
  and no GL driver.
- Any frame-rate or performance claim. **The 60 fps target in the plan is a target,
  not a measurement.**
- Flutter, Tauri and GTK4 were evaluated from documentation only; none could be built
  or benchmarked here, and I make no first-hand performance claim about any of them.
- The plan's architecture is designed, not implemented. Nothing in `src/` exists yet.

### Where things stand

Three questions are blocking implementation and have been put to the stakeholder:
the toolkit confirmation, the v1 scope boundary (HUD shell with real telemetry vs.
integrating an assistant backend), and Python vs C++. No product code until then.

---

## M1-M6 — Implementation (2026-09-03)

### What I set out to do

Build the HUD the plan described: real telemetry, two modes, an enforced state
machine, honest failure states, and a quality gate that actually runs.

### Challenges encountered

**1. The QML `id: root` shadowing bug — the subtlest defect of the session.**

Every mode file declared `id: root`, and the shell instantiated them inside a
`Component` with `controller: root.controller`. That reads naturally, and it is wrong:
inside a `Component`, an unqualified `root` resolves to the *component's own* root
object, not the enclosing file's. So each mode was binding its `controller` property
to itself, and every child then read properties of `undefined`.

What made this dangerous is that **it rendered anyway**. The layout appeared, the frame
grabbed successfully, and the only evidence was `TypeError` lines in stderr that were
easy to dismiss as noise. Had I judged by the screenshot alone, I would have shipped a
HUD where an entire mode silently showed nothing.

The fix was to give the shell a distinct id (`hudSurface`) so the reference is
unambiguous. The general lesson: in QML, never reuse `root` across files that
instantiate one another, and treat `TypeError` in output as a failure, not as noise.

**2. `required property` fights `Loader`.**

The plan called for a `Loader` to swap modes. But a `Loader` evaluates the component's
bindings *before* applying initial properties, so a `required property var controller`
is still unset on the first evaluation pass and every binding sees null. I tried
gating with `active:` and a `ready` flag; both still produced a null pass.

I stopped working around it and removed the `Loader`. Both modes are now instantiated
directly and cross-faded by opacity. That is simpler, eliminates the entire bug class,
costs nothing (both modes are cheap), and makes switching instant since there is no
re-layout. A case where the simpler design was also the correct one.

**3. Context properties are invisible to the tooling.**

`setContextProperty("hudController", ...)` works at runtime but `qmllint` cannot see
it, so every single reference was reported as an unqualified access — six warnings I
could not fix without either suppressing them or changing the approach.

Suppression would have been the easy call. Instead I migrated to
`qmlRegisterSingletonInstance`, the modern Qt 6 mechanism, and wrote
`tools/generate_qmltypes.py` to emit the QML type description **from the live
`QMetaObject`** rather than by hand, so the description cannot drift from the code.
That got qmllint to *zero* warnings across all ten QML files and gave the linter real
type information about the Python object. It also forced renaming `Hud.qml` to
`HudSurface.qml`, since `Hud` now names the singleton.

Two follow-on details: the generated file needs `exportMetaObjectRevisions` encoding
the same version as the export (`(major << 8) | minor`) or the tooling complains that
they differ; and PySide6 6.11's type stub declares the singleton name parameter as
`bytes` while the runtime rejects bytes and demands `str`. The stub is simply wrong —
I used the runtime-correct value with a documented, narrowly-scoped `type: ignore`.

**4. A test that was wrong, not code that was wrong.**

`test_format_percent` asserted `format_percent(42.55) == "42.6"` and failed with
`"42.5"`. The temptation is to "fix" the code. But 42.55 is not representable in binary
floating point — it is stored as 42.549999…, so `.1f` correctly rounds down. The code
was right and my expectation was wrong. I rewrote the test with values that do not
depend on float representation. Worth recording because the reflex to make the failing
assertion pass by changing the implementation is exactly how a real rounding bug gets
introduced.

**5. Layout bugs a screenshot caught that no unit test would.**

Rendering to PNG and actually *looking* at it caught three defects that were invisible
to property assertions: values in the vitals rail overlapping their own labels (a `Row`
has no baseline of its own, so baseline-anchoring one silently misaligns); panels in
monitor mode clipped, because callers were computing panel height from the panel's own
children — a circular binding; and the reactor core rendering as a flat disc, which
looked like a sticker rather than an instrument.

This is why the headless render is in the gate even though Qt's own guidance says not
to use bitmaps as a pass/fail assertion. The image is not the test; it is the thing
that tells a human where to point the tests.

**6. Getting Qt to import at all in a container with no graphics stack.**

Covered in M0, but it bit again during CI design. The stub libraries are now generated
by a committed, documented script rather than existing as loose binaries I built by
hand, and the gate opts into them explicitly with `JAVRIS_GL_STUBS=1`. They are clearly
marked as never-for-production. A future maintainer hitting `ImportError: libGL.so.1`
in a minimal container now has an answer instead of a mystery.

### Learning moments

- **A rendering that appears is not a rendering that is correct.** The shadowing bug
  produced a plausible screenshot and a broken binding. Warnings in output deserve the
  same seriousness as a failed assertion.
- **Fighting the framework is a signal.** Both the `Loader` and the context-property
  problems dissolved when I stopped working around the framework and adopted the
  mechanism it actually intends. The workaround attempts were strictly worse code.
- **Generate descriptions, never hand-write them.** The `.qmltypes` file could have
  been written by hand in ten minutes and would have started rotting immediately.
  Deriving it from the `QMetaObject` makes drift structurally impossible.
- **`state` is a `QQuickItem` property.** Naming a custom property `state` compiles,
  runs, and misbehaves. qmllint caught the analogous `radius` shadowing on a
  `Rectangle`; the linter earns its place in the gate.
- **Designing for absent data changed the whole architecture.** Deciding early that a
  missing sensor must render as `--` and never as `0` propagated everywhere: `None`
  throughout the models, `-1` sentinels at the QML boundary, a distinct `unavailable`
  colour, and `degraded_sources` on every snapshot. Retrofitting that honesty later
  would have been a rewrite. The sandbox has no thermal zone, so the degraded path was
  exercised constantly rather than being theoretical.

### Explicitly NOT verified

- **No rendering on real GPU hardware, X11 or Wayland.** No `$DISPLAY` and no GL
  driver here; everything used the software rasteriser via `-platform offscreen`.
- **No frame-rate measurement whatsoever.** The 60 fps figure in the plan is a target,
  not a result. Animation smoothness, GPU behaviour and compositor interaction are all
  unverified and need testing on real hardware.
- **Full-screen and frameless window behaviour is untested** — it cannot be exercised
  offscreen and varies by window manager.
- **Keyboard interaction (Tab, Esc) and the console are untested end to end** through
  real input events; the command router beneath them has full unit coverage.
- Flutter, Tauri and GTK4 remain evaluated from documentation only.

### Where things stand

The gate passes end to end: ruff, ruff format, mypy `--strict`, 120 unit tests,
qmllint clean on all 10 QML files, 18 QML tests, and a headless render. The honest
next step is for a human to run it on a real Linux desktop, because the one thing I
cannot do from here is look at it moving.

## M7 — attention escalation

### Research that actually changed the product

The first research round gathered *appearance*: cyan, wireframes, cut corners.
Useful, but it produced a themed dashboard. The second round asked a different
question — what does the system *do* — and the answer reframed the work. The
single most valuable sentence found was the source analysis criticising its own
subject: little gauges wiggling in the periphery will not get the operator's
attention, so escalate the problem into the main display.

That is a *behaviour*, and it is what makes the thing feel like an assistant
rather than a monitor. Lesson: when researching a visual reference, deliberately
spend a pass looking for critique of it, not just description of it. The
criticism is where the design requirements are.

### The gaze proxy

The reference behaviour depends on eye tracking. We have none. The temptation
was to skip the feature or, worse, to imply capability we lack. Instead the
substitute — is this metric already central in the active mode? — is named
`Prominence`, documented as a proxy in three places, and never described as
attention sensing. It also turned out to be *better* than a hack: "don't escalate
what is already big and central" is genuinely correct on its own merits.

The cost is a coupling that will rot silently: `_CENTRAL_METRICS` in Python has
to match the mode QML layouts. That is called out in the design system, because
nothing enforces it.

### Hysteresis was not optional, and I got its scope wrong

Escalation dims the entire HUD, so a metric hovering at 0.70 would strobe the
whole display once per second. Streak counters plus a release margin fixed that.

But I applied the recovery streak to *every* release path, including "the
operator switched to a mode where this metric is central". A test asserting
immediate release failed, and the failure was right and the code was wrong. The
distinction I had missed: hysteresis exists to damp an oscillating **value**. A
mode change is not an oscillation, and neither is a sensor disappearing —
delaying those just leaves something untrue on the screen. Both now bypass the
streak entirely.

Worth noting the test caught this only because it was written from the docstring
I had already written, which described the intended behaviour correctly. Writing
the rationale first made the bug visible.

### The screenshot found what 158 tests did not

Every gate was green, and the rendered frame showed the header cheerfully
reporting **NOMINAL** next to a **CRITICAL** 96.0% memory alert. No test covered
"the header and the banner must agree" because it had not occurred to me that
they could disagree.

Same frame, two more: the mode surface was still at full brightness fighting the
alert, and the reactor core was ghosting straight through the hero number at
0.88 backdrop opacity — the precise low-contrast failure the research had warned
about, reintroduced by my own tasteful transparency.

This is the second milestone running where rendering an image caught a class of
bug the test suite structurally could not. The suite asserts that components
behave; it never asserts that they are *coherent with each other*. Rendering the
unhappy path is now a step, not an afterthought — which is why
`--simulate-alert` exists as a tool rather than as a throwaway snippet.

### Small things

- A `Behavior` cannot animate a `readonly property`. The error message
  ("Invalid property assignment") does not mention `Behavior`, so it reads like a
  binding mistake.
- `ruff` removes `# noqa: SLF001` when the rule is not enabled, and the fix
  suggestion silently discards the explanatory comment attached to it. Prefer a
  real comment over a `noqa` when the rule is not on.
- `.venv/` and `build/` are excluded from workspace snapshots, so both must be
  rebuilt at the start of a session. `pip install -e ".[dev]"` plus
  `tools/sandbox_gl_stubs.py` takes about 20 seconds. Worth checking before
  assuming a tool is broken.
