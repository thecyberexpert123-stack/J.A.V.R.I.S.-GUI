import QtQuick
import QtQuick.Controls.Basic
import javris.core
import javris.ui
import javris.ui.components
import javris.ui.modes

/*!
    The HUD shell: background field, header, mode surface, telemetry rail and
    console. Composition only - all data and policy live in HudController.
*/
Item {
    id: hudSurface

    /*!
        The controller backing this HUD.

        Defaults to the registered \c Hud singleton rather than being declared
        \c required: a required property is still unset while the component's
        own bindings are first evaluated, so every child binding would resolve
        against null once at construction. A singleton default is resolvable
        from the first pass, and a test can still override it explicitly.
    */
    property var controller: Hud

    focus: true

    /*! 0.0-1.0 boot trace progress, driven while the controller is BOOTING. */
    property real bootProgress: 0

    Behavior on bootProgress {
        NumberAnimation { duration: Theme.durationBoot; easing.type: Easing.OutCubic }
    }

    Component.onCompleted: bootProgress = 1

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: Theme.background }
            GradientStop { position: 1.0; color: Theme.backgroundDeep }
        }
    }

    HudGrid {
        anchors.fill: parent
        scanning: hudSurface.controller.state !== "BOOTING"
        opacity: hudSurface.bootProgress
    }

    // -- header ------------------------------------------------------------
    Item {
        id: header
        anchors { top: parent.top; left: parent.left; right: parent.right }
        anchors.margins: Theme.spaceLg
        height: titleText.height + Theme.spaceSm

        Text {
            id: titleText
            text: "J.A.V.R.I.S."
            color: Theme.primary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeXl
            font.letterSpacing: Theme.letterSpacingWide * 2
            opacity: hudSurface.bootProgress
        }

        Text {
            anchors.left: titleText.right
            anchors.leftMargin: Theme.spaceMd
            anchors.baseline: titleText.baseline
            text: hudSurface.controller.mode
            color: Theme.accent
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeMd
            font.letterSpacing: Theme.letterSpacingWide
        }

        Row {
            anchors.right: parent.right
            anchors.baseline: titleText.baseline
            spacing: Theme.spaceMd

            Text {
                text: hudSurface.controller.degraded
                      ? "DEGRADED: " + hudSurface.controller.degradedText : "NOMINAL"
                color: hudSurface.controller.degraded ? Theme.warn : Theme.ok
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSm
                font.letterSpacing: Theme.letterSpacingLabel
            }

            Text {
                text: hudSurface.controller.state
                color: Theme.textPrimary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSm
                font.letterSpacing: Theme.letterSpacingLabel
            }
        }
    }

    Rectangle {
        id: headerRule
        anchors { top: header.bottom; left: parent.left; right: parent.right }
        anchors.margins: Theme.spaceLg
        anchors.topMargin: 0
        height: Theme.strokeThin
        color: Theme.primaryFaint
        opacity: hudSurface.bootProgress
    }

    // -- mode surface --------------------------------------------------------
    Item {
        id: surface
        anchors {
            top: headerRule.bottom
            bottom: footer.top
            left: parent.left
            right: rail.left
        }
        anchors.margins: Theme.spaceLg

        // Both modes are instantiated and cross-faded rather than swapped
        // through a Loader. A Loader evaluates a component's bindings before
        // its initial properties are applied, so a required 'controller'
        // reads as null on the first pass; instantiating directly binds it
        // correctly from the start. Both modes are inexpensive, and keeping
        // them alive means switching costs no re-layout.
        DiagnosticsMode {
            anchors.fill: parent
            controller: hudSurface.controller
            opacity: hudSurface.controller.mode === "DIAGNOSTICS" ? 1 : 0
            visible: opacity > 0

            Behavior on opacity {
                NumberAnimation { duration: Theme.durationSlow; easing.type: Theme.easing }
            }
        }

        MonitorMode {
            anchors.fill: parent
            controller: hudSurface.controller
            bootProgress: hudSurface.bootProgress
            opacity: hudSurface.controller.mode === "MONITOR" ? 1 : 0
            visible: opacity > 0

            Behavior on opacity {
                NumberAnimation { duration: Theme.durationSlow; easing.type: Theme.easing }
            }
        }
    }

    // -- telemetry rail ------------------------------------------------------
    Panel {
        id: rail
        anchors {
            top: headerRule.bottom
            bottom: footer.top
            right: parent.right
        }
        anchors.margins: Theme.spaceLg
        width: 250
        title: "Vitals"
        opacity: hudSurface.bootProgress

        Column {
            width: parent.width
            spacing: Theme.spaceMd

            TelemetryRow {
                width: parent.width
                label: "Processor"
                value: hudSurface.controller.cpuText
                unit: "%"
                fraction: hudSurface.controller.cpuPercent < 0 ? -1 : hudSurface.controller.cpuPercent / 100
            }

            TelemetryRow {
                width: parent.width
                label: "Memory"
                value: hudSurface.controller.memoryText
                fraction: hudSurface.controller.memoryFraction
            }

            TelemetryRow {
                width: parent.width
                label: "Swap"
                value: hudSurface.controller.swapFraction < 0
                       ? "--" : (hudSurface.controller.swapFraction * 100).toFixed(1)
                unit: hudSurface.controller.swapFraction < 0 ? "" : "%"
                fraction: hudSurface.controller.swapFraction
            }

            TelemetryRow {
                width: parent.width
                label: "Core temp"
                value: hudSurface.controller.temperatureText
                unit: hudSurface.controller.temperatureText === "--" ? "" : "\u00b0C"
            }

            TelemetryRow {
                width: parent.width
                label: "Load avg"
                value: hudSurface.controller.loadText
            }

            TelemetryRow {
                width: parent.width
                label: "Uptime"
                value: hudSurface.controller.uptimeText
            }

            TelemetryRow {
                width: parent.width
                label: "Downlink"
                value: hudSurface.controller.networkRxText
            }

            TelemetryRow {
                width: parent.width
                label: "Uplink"
                value: hudSurface.controller.networkTxText
            }
        }
    }

    // -- console -------------------------------------------------------------
    Panel {
        id: footer
        anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
        anchors.margins: Theme.spaceLg
        height: 168
        title: "Console"
        status: "TAB: cycle mode"
        opacity: hudSurface.bootProgress

        Column {
            anchors.fill: parent
            spacing: Theme.spaceSm

            LogStream {
                id: logView
                width: parent.width
                height: parent.height - inputRow.height - Theme.spaceSm
                lines: hudSurface.controller.log
            }

            Row {
                id: inputRow
                width: parent.width
                spacing: Theme.spaceSm

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: ">"
                    color: Theme.primary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeMd
                }

                TextField {
                    id: input
                    width: parent.width - 20
                    placeholderText: "Enter command. Type 'help' for the list."
                    color: Theme.textPrimary
                    placeholderTextColor: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeMd
                    // Defence in depth: the router also caps length.
                    maximumLength: 200
                    background: Rectangle {
                        color: "transparent"
                        border.width: Theme.strokeThin
                        border.color: input.activeFocus ? Theme.primary : Theme.primaryFaint
                    }

                    onAccepted: {
                        if (text.trim().length > 0) {
                            hudSurface.controller.submitCommand(text);
                            text = "";
                        }
                    }
                }
            }
        }
    }

    Keys.onPressed: function (event) {
        if (event.key === Qt.Key_Tab) {
            hudSurface.controller.cycleMode();
            event.accepted = true;
        } else if (event.key === Qt.Key_Escape) {
            input.focus = true;
            event.accepted = true;
        }
    }
}
