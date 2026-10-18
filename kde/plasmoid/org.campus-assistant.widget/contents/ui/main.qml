import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PlasmaComponents
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    readonly property string apiBase: "http://localhost:8765"
    readonly property int pollInterval: 120  // seconds

    preferredRepresentation: compactRepresentation

    // ── Compact (icon + badge) ────────────────────────────────────────────────
    compactRepresentation: Item {
        Kirigami.Icon {
            anchors.fill: parent
            anchors.margins: 4
            source: "view-calendar-upcoming-events"
        }

        // Deadline badge
        Rectangle {
            visible: upcomingCount > 0
            width: Math.max(18, deadlineBadge.implicitWidth + 6)
            height: 18
            radius: 9
            color: Kirigami.Theme.negativeTextColor
            anchors { top: parent.top; right: parent.right; margins: 2 }

            PlasmaComponents.Label {
                id: deadlineBadge
                anchors.centerIn: parent
                text: upcomingCount
                font.pixelSize: 10
                color: "white"
            }
        }

        MouseArea {
            anchors.fill: parent
            onClicked: root.expanded = !root.expanded
        }
    }

    // ── Full (popup) ──────────────────────────────────────────────────────────
    fullRepresentation: ColumnLayout {
        width: 300
        spacing: 0

        // Header
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: Kirigami.Units.smallSpacing

            Kirigami.Icon {
                source: "view-calendar-upcoming-events"
                Layout.preferredWidth: Kirigami.Units.iconSizes.medium
                Layout.preferredHeight: Kirigami.Units.iconSizes.medium
            }

            PlasmaComponents.Label {
                text: "Campus Assistant"
                font.bold: true
                Layout.fillWidth: true
            }

            Controls.ToolButton {
                icon.name: "view-refresh"
                flat: true
                onClicked: refresh()
                enabled: !busy
            }
        }

        Kirigami.Separator { Layout.fillWidth: true }

        // Status row
        PlasmaComponents.Label {
            visible: statusText !== ""
            text: statusText
            font.pixelSize: 11
            opacity: 0.7
            Layout.margins: Kirigami.Units.smallSpacing
            Layout.fillWidth: true
        }

        // Upcoming items list
        PlasmaComponents.Label {
            visible: upcomingCount === 0 && !busy && !errorText
            text: "No upcoming deadlines in 7 days"
            font.pixelSize: 12
            opacity: 0.7
            Layout.margins: Kirigami.Units.smallSpacing
            horizontalAlignment: Text.AlignHCenter
            Layout.fillWidth: true
        }

        ListView {
            id: listView
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(contentHeight, 240)
            clip: true
            model: upcomingModel

            delegate: ItemDelegate {
                width: listView.width
                contentItem: ColumnLayout {
                    spacing: 1
                    PlasmaComponents.Label {
                        text: modelData.title || "(untitled)"
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                        font.pixelSize: 12
                    }
                    PlasmaComponents.Label {
                        text: formatDue(modelData.due_date)
                        font.pixelSize: 10
                        opacity: 0.7
                        color: overdueTint(modelData.due_date)
                    }
                }
                onClicked: Qt.openUrlExternally(root.apiBase + "/ui/")
            }
        }

        // Error state
        PlasmaComponents.Label {
            visible: errorText !== ""
            text: errorText
            color: Kirigami.Theme.negativeTextColor
            font.pixelSize: 11
            wrapMode: Text.WordWrap
            Layout.margins: Kirigami.Units.smallSpacing
            Layout.fillWidth: true
        }

        Kirigami.Separator { Layout.fillWidth: true }

        // Footer buttons
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: Kirigami.Units.smallSpacing

            Controls.ToolButton {
                text: "Open"
                icon.name: "internet-web-browser"
                flat: true
                onClicked: Qt.openUrlExternally(root.apiBase + "/ui/")
            }

            Item { Layout.fillWidth: true }

            Controls.ToolButton {
                text: "Sync"
                icon.name: "view-refresh"
                flat: true
                enabled: !busy
                onClicked: triggerSync()
            }
        }
    }

    // ── State ─────────────────────────────────────────────────────────────────
    property int upcomingCount: 0
    property var upcomingModel: []
    property string statusText: ""
    property string errorText: ""
    property bool busy: false

    // ── Polling timer ─────────────────────────────────────────────────────────
    Timer {
        id: pollTimer
        interval: pollInterval * 1000
        repeat: true
        running: true
        triggeredOnStart: true
        onTriggered: refresh()
    }

    // ── Network helpers ───────────────────────────────────────────────────────
    function refresh() {
        busy = true
        errorText = ""
        fetchUpcoming()
    }

    function fetchUpcoming() {
        var xhr = new XMLHttpRequest()
        xhr.onreadystatechange = function() {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            busy = false
            if (xhr.status === 200) {
                try {
                    var items = JSON.parse(xhr.responseText)
                    upcomingModel = items.slice(0, 10)
                    upcomingCount = items.length
                    errorText = ""
                    fetchStatus()
                } catch (e) {
                    errorText = "Parse error"
                }
            } else if (xhr.status === 0) {
                errorText = "Service offline"
            } else {
                errorText = "Error " + xhr.status
            }
        }
        xhr.open("GET", apiBase + "/upcoming?days=7")
        xhr.send()
    }

    function fetchStatus() {
        var xhr = new XMLHttpRequest()
        xhr.onreadystatechange = function() {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            if (xhr.status === 200) {
                try {
                    var s = JSON.parse(xhr.responseText)
                    var last = s.sync && s.sync.last ? s.sync.last.finished_at : null
                    statusText = last ? "Last sync: " + formatRelative(last) : ""
                } catch (e) {}
            }
        }
        xhr.open("GET", apiBase + "/status")
        xhr.send()
    }

    function triggerSync() {
        busy = true
        var xhr = new XMLHttpRequest()
        xhr.onreadystatechange = function() {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            busy = false
            statusText = "Sync triggered"
            Qt.callLater(function() { pollTimer.restart() })
        }
        xhr.open("POST", apiBase + "/sync/brightspace")
        xhr.send()
    }

    // ── Formatting helpers ────────────────────────────────────────────────────
    function formatDue(isoDate) {
        if (!isoDate) return "No due date"
        var d = new Date(isoDate)
        var now = new Date()
        var diff = Math.round((d - now) / 86400000)
        if (diff < 0) return "Overdue by " + Math.abs(diff) + "d"
        if (diff === 0) return "Due today"
        if (diff === 1) return "Due tomorrow"
        return "Due in " + diff + "d"
    }

    function overdueTint(isoDate) {
        if (!isoDate) return Kirigami.Theme.textColor
        var d = new Date(isoDate)
        if (d < new Date()) return Kirigami.Theme.negativeTextColor
        return Kirigami.Theme.textColor
    }

    function formatRelative(isoDate) {
        if (!isoDate) return ""
        var d = new Date(isoDate)
        var diff = Math.round((new Date() - d) / 60000)
        if (diff < 2) return "just now"
        if (diff < 60) return diff + "m ago"
        var h = Math.round(diff / 60)
        if (h < 24) return h + "h ago"
        return Math.round(h / 24) + "d ago"
    }
}
