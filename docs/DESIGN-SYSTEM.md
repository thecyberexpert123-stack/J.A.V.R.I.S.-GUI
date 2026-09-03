# Design System — the component bible

Modelled on the "HUD Bible" that governed the original design work: every component is
documented with its purpose, the information it carries, and the rules it must obey
([`CREDITS.md`](./CREDITS.md)).

**The governing rule:** every element must carry information. If it cannot state what
it tells the operator, it does not belong on screen.

## Tokens

All tokens live in `src/javris/ui/Theme.qml`, a QML singleton. **No component may
declare a literal colour, spacing value or duration.** Changing the design language
happens in one file.

### Colour

| Token | Value | Meaning |
|---|---|---|
| `background` / `backgroundDeep` | `#04080c` / `#010305` | Field, top and bottom of the gradient |
| `panel` | `#0a1620` | Panel fill |
| `grid` | `#0e2735` | Background grid rules |
| `primary` | `#3fe0ff` | Active elements, live data |
| `primaryDim` | `#1c7d96` | Idle elements |
| `primaryFaint` | `#0f3d4a` | Frames, unfilled gauge tracks |
| `accent` | `#ffb648` | Current mode indicator |
| `textPrimary` / `textSecondary` / `textMuted` | `#c8f4ff` / `#6f9fb0` / `#40606d` | Values / labels / units |
| `ok` / `warn` / `error` | `#4dffb8` / `#ffb648` / `#ff5f6d` | Severity |
| `unavailable` | `#4a5a63` | **No reading available** — never used for a real value |

Cyan-on-near-black follows the documented palette of the source material
([`RESEARCH.md`](./RESEARCH.md) D1).

### Load colour is semantic, not decorative

`Theme.loadColor(fraction)` maps utilisation to the palette so pressure can be read
without reading digits:

| Range | Colour |
|---|---|
| `< 0` | `unavailable` |
| `0.0 – 0.7` | `primary` |
| `0.7 – 0.9` | `warn` |
| `≥ 0.9` | `error` |

### Spacing, motion, type

- Spacing sits on a 4 px grid: `spaceXs` 4, `spaceSm` 8, `spaceMd` 16, `spaceLg` 24,
  `spaceXl` 40.
- Motion is short and instrument-like: `durationFast` 120 ms, `durationNormal` 220 ms,
  `durationSlow` 300 ms (the mode cross-fade budget), `durationBoot` 1800 ms. Easing is
  `Easing.OutCubic`.
- Type is monospace throughout, so telemetry columns do not reflow as digits change.
  Labels are upper-case with wide tracking; values are plain.

## Components

### `Theme` (singleton)
Design tokens and the two semantic functions `loadColor` and `severityColor`.

### `Panel`
Framed surface with cut corners and a titled header rule. Sizes itself to its content
by default, so a caller never has to compute a height from the very children the panel
contains. Built as one `Shape` with one `ShapePath`, per Qt's guidance that path
geometry is triangulated on the CPU.

### `Gauge`
Radial gauge carrying **label, value and unit** — all three, always. A negative value
means unavailable: the arc is not drawn and the readout shows `--`. It never renders a
fabricated number. `sweepAngle` is exposed and directly unit-tested.

### `ReactorCore`
The central instrument. Every ring means something:

| Ring | Encodes |
|---|---|
| Outer arcs (clockwise) | Assistant state, via rotation rate; stationary when faulted |
| Inner arcs (counter-clockwise) | Depth and activity |
| Tick ring | The fixed scale the load arc is read against |
| Load arc | CPU load, by sweep and by colour |
| Inner ring pulse | Load, by amplitude, for peripheral awareness |
| Centre readout | The exact figure, with its unit |

Rotation periods: `PROCESSING` 2600 ms, `EXECUTING` 3400 ms, `SPEAKING` 4200 ms,
`LISTENING` 5200 ms, `BOOTING` 1800 ms, `STANDBY` 14000 ms, faulted 0 (stopped).

Glow is produced by layering a wide translucent stroke beneath a narrow bright one,
not by a shader: Qt 6 requires shaders pre-baked to `.qsb`, and that toolchain is
unavailable in the development sandbox. Layered strokes are fully scene-graph native.

Note the property is `coreState`, not `state` — `state` is a built-in `QQuickItem`
property and binding to it would have silently misbehaved.

### `TelemetryRow`
One labelled line: name left, value and unit right, optional load bar beneath. The
value elides rather than overlapping the label. `--` renders in `unavailable`.

### `LogStream`
Severity-coloured auto-scrolling console. Lines arrive as `SEVERITY\x1fmessage`; the
router strips control characters from user input, so a message cannot forge a severity
tag.

### `HudGrid`
Background field: faint grid plus a slow vertical scan line. Line count is bounded by
cell size, so cost scales with window size.

## Modes

Modes recompose the entire surface rather than swapping a tab
([`RESEARCH.md`](./RESEARCH.md) D2). Both are instantiated and cross-faded within the
300 ms budget.

- **`DiagnosticsMode`** — "what is loaded right now, and by how much": three large
  gauges, per-core bars with numeric readouts, storage pressure.
- **`MonitorMode`** — sustained ambient awareness: reactor core centred, with storage
  and network panels flanking it.

## Accessibility and honesty rules

1. **Every numeric readout carries a name and a unit.** This directly fixes the
   cognitive-load flaw identified in the source material ([`RESEARCH.md`](./RESEARCH.md) D8).
2. **Unavailable is a distinct visual state**, never zero and never a plausible guess.
3. **Colour is never the only channel.** Load is shown by arc length and bar height as
   well as by hue.
4. **Motion always means something.** Nothing animates purely for effect; a stopped
   ring is itself the signal that the system has faulted.
