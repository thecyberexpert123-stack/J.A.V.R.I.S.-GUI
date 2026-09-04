pragma ComponentBehavior: Bound

import QtQuick
import javris.ui

/*!
    The owner's consent decision for a tier-2 action.

    This is the only surface in the GUI that can authorise a change to the
    machine. Every design choice here follows from that:

    \list
    \li \b{No default action.} Neither button is focused or activated by Enter.
        A dialog that can be dismissed into "yes" by a stray keypress is not
        consent.
    \li \b{The request is quoted verbatim} and is the largest text in the
        panel. The owner approves the exact words that will be sent, never a
        paraphrase of them.
    \li \b{Decline is the calm path} and reads first; approve is deliberately
        weighted with the warning colour, because it is the consequential one.
    \li \b{Escape declines.} The cheap, reflexive exit must be the safe one.
    \endlist

    The prompt carries no timeout: an unattended machine must not drift into
    either answer.
*/
Item {
    id: root

    /*! The request text awaiting a decision. Empty means no prompt. */
    property string request: ""

    /*! The kernel's own next-step hint, shown verbatim when present. */
    property string hint: ""

    signal approved
    signal declined

    readonly property bool active: root.request.length > 0

    visible: opacity > 0
    opacity: root.active ? 1 : 0

    Behavior on opacity {
        NumberAnimation { duration: Theme.durationNormal; easing.type: Theme.easing }
    }

    // Opaque backdrop. Also swallows every click and key that is not one of
    // the two answers, so nothing behind the prompt can be operated while a
    // consent decision is outstanding.
    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(Theme.backgroundDeep.r, Theme.backgroundDeep.g,
                       Theme.backgroundDeep.b, 0.88)

        MouseArea {
            anchors.fill: parent
            enabled: root.active
            // Clicking the backdrop does nothing: dismissing by misclick is
            // neither approval nor an informed refusal.
            onClicked: { /* intentionally inert */ }
        }
    }

    FocusScope {
        id: scope

        anchors.centerIn: parent
        width: Math.min(parent.width - Theme.spaceXl * 2, 620)
        height: body.height + Theme.spaceXl * 2
        focus: root.active

        Keys.onEscapePressed: root.declined()

        Rectangle {
            anchors.fill: parent
            color: Theme.panel
            border.width: Theme.strokeMedium
            border.color: Theme.warn
        }

        CornerBrackets {
            anchors.fill: parent
            inset: -Theme.spaceXs
            armLength: 20
            color: Theme.warn
            thickness: Theme.strokeMedium
        }

        Column {
            id: body

            anchors.centerIn: parent
            width: parent.width - Theme.spaceXl * 2
            spacing: Theme.spaceMd

            Text {
                text: "CONSENT REQUIRED"
                color: Theme.warn
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeMd
                font.letterSpacing: Theme.letterSpacingWide
            }

            Text {
                width: parent.width
                text: "The agent will not perform this action without your "
                      + "explicit approval."
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSm
                wrapMode: Text.WordWrap
            }

            // The exact request, quoted. Bordered and set apart so it cannot be
            // confused with the surrounding explanatory text.
            Rectangle {
                width: parent.width
                height: requestText.height + Theme.spaceMd * 2
                color: Theme.backgroundDeep
                border.width: Theme.strokeThin
                border.color: Theme.primaryFaint

                Text {
                    id: requestText
                    anchors.centerIn: parent
                    width: parent.width - Theme.spaceMd * 2
                    text: root.request
                    color: Theme.textPrimary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeMd
                    wrapMode: Text.WordWrap
                }
            }

            Text {
                width: parent.width
                text: root.hint
                visible: root.hint.length > 0
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSm
                wrapMode: Text.WordWrap
            }

            Row {
                anchors.right: parent.right
                spacing: Theme.spaceMd

                ConsentButton {
                    id: declineButton
                    label: "DECLINE"
                    accent: Theme.primary
                    onTriggered: root.declined()
                }

                ConsentButton {
                    label: "APPROVE AND RUN"
                    accent: Theme.warn
                    onTriggered: root.approved()
                }
            }
        }
    }
}
