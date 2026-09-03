pragma Singleton
import QtQuick

/*!
    The single source of truth for every colour, dimension, duration and type
    setting in the HUD. No component may declare a literal colour or magic
    number; changing the design language happens here and nowhere else.

    Palette rationale (see docs/RESEARCH.md, principle D1): cyan wireframe on
    near-black, as documented by the designers of the original HUD.
*/
QtObject {
    id: theme

    // -- colour -----------------------------------------------------------
    readonly property color background:    "#04080c"
    readonly property color backgroundDeep: "#010305"
    readonly property color panel:         "#0a1620"
    readonly property color grid:          "#0e2735"

    readonly property color primary:       "#3fe0ff"
    readonly property color primaryDim:    "#1c7d96"
    readonly property color primaryFaint:  "#0f3d4a"
    readonly property color accent:        "#ffb648"

    readonly property color textPrimary:   "#c8f4ff"
    readonly property color textSecondary: "#6f9fb0"
    readonly property color textMuted:     "#40606d"

    readonly property color ok:            "#4dffb8"
    readonly property color warn:          "#ffb648"
    readonly property color error:         "#ff5f6d"
    readonly property color unavailable:   "#4a5a63"

    // -- spacing (4px base grid) -------------------------------------------
    readonly property int spaceXs: 4
    readonly property int spaceSm: 8
    readonly property int spaceMd: 16
    readonly property int spaceLg: 24
    readonly property int spaceXl: 40

    // -- geometry ----------------------------------------------------------
    readonly property int strokeThin:   1
    readonly property int strokeMedium: 2
    readonly property int strokeThick:  3
    readonly property int cornerCut:    14

    // -- motion ------------------------------------------------------------
    // Durations are deliberately short: the HUD must feel instrument-grade,
    // not decorative. Mode changes stay within the 300ms budget in PLAN R2.
    readonly property int durationFast:   120
    readonly property int durationNormal: 220
    readonly property int durationSlow:   300
    readonly property int durationBoot:   1800
    readonly property int easing:         Easing.OutCubic

    // -- typography --------------------------------------------------------
    // Monospace throughout: telemetry columns must not reflow as digits change.
    readonly property string fontFamily: monoFont.font.family
    readonly property int fontSizeSm: 10
    readonly property int fontSizeMd: 12
    readonly property int fontSizeLg: 16
    readonly property int fontSizeXl: 28
    // Reserved for escalated alerts: research D10 calls for high contrast and
    // large type in the periphery, not more detail.
    readonly property int fontSizeHero: 64
    readonly property real letterSpacingWide: 3.0
    readonly property real letterSpacingLabel: 1.4

    readonly property Text monoFont: Text {
        font.family: "monospace"
        font.styleName: "Regular"
    }

    /*!
        Maps a normalised 0.0-1.0 load to the palette: calm cyan under load,
        amber approaching saturation, red at saturation. This is information,
        not decoration - an operator should read pressure without reading digits.
    */
    function loadColor(fraction) {
        if (fraction < 0)
            return theme.unavailable;
        if (fraction >= 0.9)
            return theme.error;
        if (fraction >= 0.7)
            return theme.warn;
        return theme.primary;
    }

    /*! Maps a log severity token to its colour. */
    function severityColor(severity) {
        switch (severity) {
        case "OK":
            return theme.ok;
        case "WARN":
            return theme.warn;
        case "ERROR":
            return theme.error;
        default:
            return theme.textSecondary;
        }
    }
}
