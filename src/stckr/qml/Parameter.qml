import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ColumnLayout {
    id: root
    property string label: ""
    property alias value: slider.value
    property alias from: slider.from
    property alias to: slider.to
    property alias stepSize: slider.stepSize
    property int decimals: 0
    signal edited()
    spacing: 5
    RowLayout {
        Layout.fillWidth: true
        Text { text: root.label; color: "#acbdc6"; font.pixelSize: 12; Layout.fillWidth: true }
        Text { text: slider.value.toFixed(root.decimals); color: "#e4edef"; font.pixelSize: 11; font.family: "Consolas" }
    }
    Slider {
        id: slider
        Layout.fillWidth: true
        implicitHeight: 22
        onMoved: root.edited()
        background: Rectangle {
            x: slider.leftPadding; y: slider.topPadding + slider.availableHeight / 2 - 2
            width: slider.availableWidth; height: 3; radius: 2; color: "#34434c"
            Rectangle { width: slider.visualPosition * parent.width; height: parent.height; radius: 2; color: "#70cbb5" }
        }
        handle: Rectangle {
            x: slider.leftPadding + slider.visualPosition * (slider.availableWidth - width)
            y: slider.topPadding + slider.availableHeight / 2 - height / 2
            width: 12; height: 12; radius: 6; color: slider.pressed ? "#a5f4df" : "#d1e9e2"
        }
    }
}
