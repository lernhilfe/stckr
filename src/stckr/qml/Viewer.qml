import QtQuick
import STCKR 1.0

Item {
    id: viewer
    property bool source: false
    property bool retouch: false
    property bool erase: false
    property real brushRadius: 35
    property real hardness: .5
    property real brushOpacity: 1
    PhotoCanvas { id: photo; anchors.fill: parent; source: viewer.source; view: studio.view }
    MouseArea {
        id: mouse
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
        hoverEnabled: true
        cursorShape: viewer.retouch && !viewer.source ? Qt.CrossCursor : pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
        property real px: 0
        property real py: 0
        property bool drawing: false
        onPressed: function(event) {
            px = event.x; py = event.y
            drawing = viewer.retouch && !viewer.source && event.button === Qt.LeftButton && !(event.modifiers & Qt.ControlModifier)
            if (drawing) photo.brush(event.x, event.y, viewer.brushRadius, viewer.hardness, viewer.brushOpacity, viewer.erase)
        }
        onPositionChanged: function(event) {
            if (pressed) {
                if (drawing) photo.brush(event.x, event.y, viewer.brushRadius, viewer.hardness, viewer.brushOpacity, viewer.erase)
                else photo.pan(event.x - px, event.y - py)
                px = event.x; py = event.y
            }
        }
        onReleased: { if (drawing) studio.endStroke(); drawing = false }
        onCanceled: { studio.endStroke(); drawing = false }
        onWheel: function(event) { photo.zoomAt(event.angleDelta.y > 0 ? 1.15 : 1 / 1.15, event.x, event.y) }
        onDoubleClicked: studio.view.fit()
        Rectangle {
            visible: viewer.retouch && !viewer.source && mouse.containsMouse
            x: mouse.mouseX - viewer.brushRadius; y: mouse.mouseY - viewer.brushRadius
            width: viewer.brushRadius * 2; height: width; radius: width / 2
            color: "transparent"; border.width: 1; border.color: "#e5fff6"
        }
    }
    Connections { target: studio; function onImagesChanged() { photo.update() } }
}
