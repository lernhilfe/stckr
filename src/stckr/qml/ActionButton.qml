import QtQuick
import QtQuick.Controls

Button {
    id: control
    property bool primary: false
    property bool quiet: false
    property bool selected: false
    implicitHeight: 36
    implicitWidth: Math.max(36, label.implicitWidth + 26)
    hoverEnabled: true
    font.pixelSize: 12
    font.weight: Font.Medium
    contentItem: Text {
        id: label
        text: control.text
        color: !control.enabled ? "#536069" : control.primary ? "#092a25" : control.selected ? "#71ddc6" : "#d6e0e5"
        font: control.font
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        radius: 7
        color: control.primary ? (control.down ? "#54bda6" : control.hovered ? "#94ebd6" : "#75ddc4") :
               control.selected ? "#213c38" : control.down ? "#2d3b43" : control.hovered ? "#28353d" :
               control.quiet ? "transparent" : "#202c33"
        border.width: control.primary || control.quiet ? 0 : 1
        border.color: control.selected ? "#38675d" : "#344149"
        opacity: control.enabled ? 1 : .5
    }
}
