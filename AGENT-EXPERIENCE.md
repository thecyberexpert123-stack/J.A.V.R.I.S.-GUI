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
