import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

ApplicationWindow {
    id: window
    width: 1480; height: 940
    minimumWidth: 1120; minimumHeight: 760
    visible: true
    title: "STCKR — Focus Stacking Studio"
    color: "#121a20"
    font.family: Qt.platform.os === "windows" ? "Segoe UI" : "DejaVu Sans"
    property bool compare: false
    property bool split: false
    property bool erase: false
    property string notice: ""
    property string errorText: ""
    property bool advanced: false
    property bool isRetouch: studio.workspace === "Retuschieren"

    Shortcut { sequence: "Ctrl+O"; onActivated: studio.chooseFiles() }
    Shortcut { sequence: "Ctrl+S"; onActivated: studio.saveProject() }
    Shortcut { sequence: "Ctrl+Z"; onActivated: studio.undo() }
    Shortcut { sequence: "Ctrl+Shift+Z"; onActivated: studio.redo() }
    Shortcut { sequence: "Ctrl+Y"; onActivated: studio.redo() }
    Shortcut { sequence: "Escape"; onActivated: studio.cancel() }
    Shortcut { sequence: "PageDown"; onActivated: studio.selectSource(Math.min(studio.files.length - 1, studio.selected + 1)) }
    Shortcut { sequence: "PageUp"; onActivated: studio.selectSource(Math.max(0, studio.selected - 1)) }
    Shortcut { sequence: "B"; onActivated: { studio.workspace = "Retuschieren"; erase = false } }
    Shortcut { sequence: "E"; onActivated: { studio.workspace = "Retuschieren"; erase = true } }

    Connections {
        target: studio
        function onErrorRaised(message) { errorText = message; errorDialog.open() }
        function onNoteRaised(message) { notice = message; toastTimer.restart() }
    }
    Timer { id: toastTimer; interval: 6500; onTriggered: notice = "" }
    Dialog {
        id: errorDialog
        title: "Hinweis zur Verarbeitung"
        anchors.centerIn: parent
        width: 500
        modal: true
        standardButtons: Dialog.Ok
        contentItem: Text { text: window.errorText; wrapMode: Text.WordWrap; color: "#182830"; font.pixelSize: 14 }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        Rectangle {
            Layout.fillWidth: true; Layout.preferredHeight: 76; color: "#182229"
            RowLayout {
                anchors.fill: parent; anchors.leftMargin: 26; anchors.rightMargin: 22; spacing: 14
                Rectangle {
                    width: 32; height: 32; radius: 8; color: "#75ddc4"
                    Text { anchors.centerIn: parent; text: "≋"; font.pixelSize: 28; font.bold: true; color: "#133a32" }
                }
                ColumnLayout {
                    spacing: 1
                    Text { text: "STCKR"; color: "#f0f5f6"; font.pixelSize: 21; font.weight: Font.Bold; font.letterSpacing: 3 }
                    Text { text: "FOCUS STACKING STUDIO"; color: "#78909d"; font.pixelSize: 8; font.letterSpacing: 1.7 }
                }
                Rectangle { Layout.leftMargin: 10; width: 1; height: 28; color: "#324049" }
                Text { text: "Jede Fokusebene. Ein Bild."; color: "#91a6b1"; font.pixelSize: 12 }
                Item { Layout.fillWidth: true }
                ActionButton { text: "Projekt öffnen"; quiet: true; enabled: !studio.busy; onClicked: studio.openProject() }
                ActionButton { text: "Projekt speichern"; enabled: !studio.busy && studio.files.length > 0; onClicked: studio.saveProject() }
            }
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: "#2b3841" }
        }
        Rectangle {
            Layout.fillWidth: true; Layout.preferredHeight: 54; color: "#151e25"
            RowLayout {
                anchors.fill: parent; anchors.leftMargin: 22; anchors.rightMargin: 22; spacing: 8
                Repeater {
                    model: ["Stacken", "Retuschieren", "Exportieren"]
                    delegate: ActionButton {
                        required property string modelData
                        required property int index
                        text: "0" + (index + 1) + "   " + modelData
                        quiet: true; selected: studio.workspace === modelData
                        enabled: index === 0 || studio.results.length > 0
                        onClicked: studio.workspace = modelData
                    }
                }
                Item { Layout.fillWidth: true }
                Rectangle { width: 6; height: 6; radius: 3; color: "#75ddc4" }
                Text { text: "LOKAL · OFFLINE · VOLLE AUFLÖSUNG"; color: "#8399a5"; font.pixelSize: 9; font.letterSpacing: 1 }
            }
        }
        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 1
            Rectangle {
                Layout.preferredWidth: 258; Layout.fillHeight: true; color: "#19232b"
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 16; spacing: 13
                    RowLayout {
                        Layout.fillWidth: true
                        Eyebrow { text: "QUELLAUFNAHMEN"; Layout.fillWidth: true }
                        Text { text: studio.files.length.toString().padStart(2, "0"); color: "#8ba0ab"; font.pixelSize: 12 }
                    }
                    ActionButton { text: "+  Aufnahmen hinzufügen"; Layout.fillWidth: true; enabled: !studio.busy; onClicked: studio.chooseFiles() }
                    RowLayout {
                        spacing: 5; Layout.fillWidth: true
                        ActionButton { text: "↑"; implicitWidth: 34; enabled: !studio.busy && studio.selected > 0; onClicked: studio.moveSource(studio.selected, -1) }
                        ActionButton { text: "↓"; implicitWidth: 34; enabled: !studio.busy && studio.selected >= 0; onClicked: studio.moveSource(studio.selected, 1) }
                        ActionButton { text: "Umkehren"; Layout.fillWidth: true; enabled: !studio.busy; onClicked: studio.reverseSources() }
                    }
                    ListView {
                        id: sources
                        Layout.fillHeight: true; Layout.fillWidth: true
                        spacing: 5; clip: true
                        model: studio.files
                        delegate: Rectangle {
                            id: sourceRow
                            required property var modelData
                            required property int index
                            width: sources.width; height: 62; radius: 7
                            color: studio.selected === index ? "#263e42" : "#1e2a32"
                            border.width: 1; border.color: studio.selected === index ? "#4f9c8f" : "#293741"
                            RowLayout {
                                anchors.fill: parent; anchors.margins: 7; spacing: 9
                                Rectangle {
                                    width: 47; height: 45; radius: 4; color: "#2c3c46"; clip: true
                                    Image { anchors.fill: parent; source: sourceRow.modelData.thumb; fillMode: Image.PreserveAspectCrop }
                                    Text { anchors.centerIn: parent; visible: !sourceRow.modelData.thumb; text: (sourceRow.index + 1).toString().padStart(2, "0"); color: "#6b8593"; font.pixelSize: 15 }
                                }
                                ColumnLayout {
                                    spacing: 4; Layout.fillWidth: true
                                    Text { Layout.fillWidth: true; text: sourceRow.modelData.name; elide: Text.ElideMiddle; color: "#d2e0e6"; font.pixelSize: 11 }
                                    Text { text: sourceRow.modelData.missing ? "Original fehlt" : sourceRow.modelData.format + " · " + (sourceRow.modelData.enabled ? "Aktiv" : "Ausgeschlossen"); color: sourceRow.modelData.missing ? "#e5b180" : "#829ba8"; font.pixelSize: 10 }
                                }
                                Rectangle {
                                    width: 15; height: 15; radius: 4
                                    color: sourceRow.modelData.enabled ? "#70cbb5" : "transparent"
                                    border.width: 1; border.color: "#628277"
                                    Text { anchors.centerIn: parent; text: sourceRow.modelData.enabled ? "✓" : ""; font.pixelSize: 11; color: "#173c32" }
                                    MouseArea { anchors.fill: parent; onClicked: studio.toggleSource(sourceRow.index) }
                                }
                            }
                            MouseArea { anchors.fill: parent; anchors.rightMargin: 30; onClicked: studio.selectSource(sourceRow.index) }
                        }
                        ScrollBar.vertical: ScrollBar { }
                    }
                    Text {
                        visible: studio.files.length === 0
                        Layout.fillWidth: true; text: "Ziehe deine Fokusserie ins Fenster. CR3, RAW, TIFF, PNG und JPEG."; wrapMode: Text.WordWrap; color: "#7c94a2"; font.pixelSize: 12; lineHeight: 1.4
                    }
                    ActionButton { visible: studio.selected >= 0 && studio.files[studio.selected] !== undefined && studio.files[studio.selected].missing; text: "Original neu zuordnen"; onClicked: studio.relinkSource() }
                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "NATÜRLICHE DATEIREIHENFOLGE"; color: "#627b89"; font.pixelSize: 8; Layout.fillWidth: true }
                        ActionButton { text: "Leeren"; quiet: true; enabled: !studio.busy; onClicked: studio.clearSources() }
                    }
                }
            }
            Rectangle {
                Layout.fillWidth: true; Layout.fillHeight: true; color: "#11171b"
                ColumnLayout {
                    anchors.fill: parent; spacing: 0
                    Rectangle {
                        Layout.fillWidth: true; Layout.preferredHeight: 49; color: "#182128"
                        RowLayout {
                            anchors.fill: parent; anchors.leftMargin: 17; anchors.rightMargin: 12; spacing: 6
                            Text { text: studio.activeResult < 0 ? "QUELLENVORSCHAU" : "ERGEBNIS " + (studio.activeResult + 1).toString().padStart(2, "0"); color: "#93aab7"; font.pixelSize: 9; font.letterSpacing: 1.2; Layout.fillWidth: true }
                            ActionButton { text: "Einpassen"; quiet: true; onClicked: studio.view.fit() }
                            ActionButton { text: "100 %"; quiet: true; onClicked: studio.view.actual() }
                            ActionButton { text: "Vergleich"; selected: window.compare; enabled: studio.results.length > 0; onClicked: { window.compare = !window.compare; window.split = false } }
                            ActionButton { text: "Quelle | Bild"; selected: window.split; enabled: studio.results.length > 0; onClicked: { window.split = !window.split; window.compare = false } }
                        }
                    }
                    Item {
                        id: stage
                        Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                        Viewer {
                            id: resultViewer
                            width: window.split ? parent.width / 2 : parent.width
                            x: window.split ? parent.width / 2 : 0; height: parent.height
                            visible: studio.hasImage
                            retouch: window.isRetouch && !studio.busy
                            erase: window.erase; brushRadius: brushSize.value; hardness: brushHardness.value; brushOpacity: brushOpacity.value
                        }
                        Viewer { x: 0; y: 0; width: parent.width / 2; height: parent.height; source: true; visible: window.split && studio.hasImage }
                        Item {
                            visible: window.compare && studio.hasImage
                            width: stage.width * compareSlider.value; height: stage.height; clip: true
                            Viewer { width: stage.width; height: stage.height; source: true }
                        }
                        Rectangle { visible: window.compare; x: stage.width * compareSlider.value; width: 1; height: parent.height; color: "#75ddc4" }
                        Slider { id: compareSlider; visible: window.compare; anchors.bottom: parent.bottom; anchors.horizontalCenter: parent.horizontalCenter; anchors.bottomMargin: 22; width: parent.width * .45; from: .02; to: .98; value: .5 }
                        Rectangle {
                            visible: studio.hasImage && (window.compare || window.split)
                            x: 18; y: 17; width: 64; height: 25; color: "#cc1d2e33"; radius: 5
                            Text { anchors.centerIn: parent; text: "QUELLE"; color: "#d3e9e5"; font.pixelSize: 9; font.letterSpacing: 1 }
                        }
                        ColumnLayout {
                            anchors.centerIn: parent; width: Math.min(parent.width - 70, 430); spacing: 19
                            visible: !studio.hasImage
                            Rectangle {
                                Layout.alignment: Qt.AlignHCenter; width: 102; height: 102; radius: 26; color: "#1a2b30"; border.color: "#2e514d"
                                Text { anchors.centerIn: parent; text: "≋"; font.pixelSize: 70; color: "#78dbc3" }
                            }
                            Eyebrow { text: "DEIN MOTIV. JEDE EBENE."; Layout.alignment: Qt.AlignHCenter }
                            Text { Layout.fillWidth: true; text: "Schärfe, die weitergeht."; color: "#e4edf0"; font.pixelSize: 28; font.weight: Font.DemiBold; horizontalAlignment: Text.AlignHCenter }
                            Text { Layout.fillWidth: true; text: "Ziehe deine Aufnahmen hierher und vereine\nsie zu einem detailreichen Focus Stack."; color: "#839ba8"; font.pixelSize: 13; lineHeight: 1.5; horizontalAlignment: Text.AlignHCenter }
                            ActionButton { Layout.alignment: Qt.AlignHCenter; text: "Fokusserie öffnen   ↗"; primary: true; onClicked: studio.chooseFiles() }
                            Text { Layout.alignment: Qt.AlignHCenter; text: "CR3 / RAW     ·     16-BIT TIFF     ·     JPEG / PNG"; color: "#546f7e"; font.pixelSize: 9; font.letterSpacing: .7 }
                        }
                        Rectangle {
                            visible: window.notice !== ""
                            anchors.bottom: parent.bottom; anchors.horizontalCenter: parent.horizontalCenter; anchors.bottomMargin: 20
                            width: Math.min(parent.width - 28, noticeLabel.implicitWidth + 32); height: noticeLabel.implicitHeight + 22
                            radius: 8; color: "#263e3b"; border.color: "#45776b"
                            Text { id: noticeLabel; anchors.centerIn: parent; width: parent.width - 30; text: window.notice; color: "#c6e8dc"; font.pixelSize: 12; wrapMode: Text.WordWrap; horizontalAlignment: Text.AlignHCenter }
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true; Layout.preferredHeight: 33; color: "#151e24"
                        Text { anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 17; text: studio.imageInfo; color: "#6e8999"; font.pixelSize: 10 }
                    }
                }
            }
            Rectangle {
                Layout.preferredWidth: 290; Layout.fillHeight: true; color: "#19232b"
                ScrollView {
                    anchors.fill: parent; anchors.margins: 20; anchors.bottomMargin: studio.workspace === "Stacken" ? 130 : 20; clip: true; contentWidth: availableWidth
                    ColumnLayout {
                        width: parent.width; spacing: 18
                        ColumnLayout {
                            visible: studio.workspace === "Stacken"; Layout.fillWidth: true; spacing: 15
                            Eyebrow { text: "STACKING-VERFAHREN" }
                            Text { text: "Der richtige Fokus."; color: "#e1ebee"; font.pixelSize: 21; font.weight: Font.DemiBold }
                            Repeater {
                                model: [
                                    {key:"A", title:"Gewichteter Mittelwert", subtitle:"Sanfte Übergänge · kurze Serien"},
                                    {key:"B", title:"Tiefenkarte", subtitle:"Klare Flächen · geordnete Serie"},
                                    {key:"C", title:"Pyramide", subtitle:"Feine Strukturen · komplexe Motive"}
                                ]
                                delegate: Rectangle {
                                    required property var modelData
                                    Layout.fillWidth: true; height: 75; radius: 9
                                    color: studio.method === modelData.key ? "#203b38" : "#1e2c35"
                                    border.width: 1; border.color: studio.method === modelData.key ? "#538e7f" : "#32424c"
                                    RowLayout {
                                        anchors.fill: parent; anchors.margins: 12; spacing: 12
                                        Text { text: modelData.key; color: studio.method === modelData.key ? "#80e1c7" : "#718c9b"; font.pixelSize: 24; font.weight: Font.Light }
                                        ColumnLayout {
                                            spacing: 5; Layout.fillWidth: true
                                            Text { text: modelData.title; color: "#d9e7eb"; font.pixelSize: 12; font.weight: Font.DemiBold }
                                            Text { text: modelData.subtitle; color: "#8da6af"; font.pixelSize: 9 }
                                        }
                                    }
                                    MouseArea { anchors.fill: parent; enabled: !studio.busy; cursorShape: Qt.PointingHandCursor; onClicked: studio.method = modelData.key }
                                }
                            }
                            Text { visible: studio.method === "B"; text: "Für B: Bilder in durchgehender Fokusreihenfolge anordnen."; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: "#d5b988"; font.pixelSize: 11 }
                            Rectangle { Layout.fillWidth: true; height: 1; color: "#30404a" }
                            Eyebrow { text: "FEINABSTIMMUNG" }
                            Parameter { id: radius; label: "Schärferadius"; from: 1; to: 25; value: 5; stepSize: 1; visible: studio.method !== "C"; Layout.fillWidth: true; enabled: !studio.busy }
                            Parameter { id: smoothing; label: "Glättung"; from: 0; to: 6; value: 1.2; stepSize: .1; decimals: 1; Layout.fillWidth: true; enabled: !studio.busy }
                            Parameter { id: levels; label: "Pyramidenstufen"; from: 2; to: 10; value: 7; stepSize: 1; visible: studio.method === "C"; Layout.fillWidth: true; enabled: !studio.busy }
                            CheckBox { id: alignment; text: "Automatisch ausrichten"; checked: true; palette.windowText: "#b6c9d1"; font.pixelSize: 12; enabled: !studio.busy }
                            ActionButton { text: window.advanced ? "−  Expertenoptionen" : "+  Expertenoptionen"; quiet: true; onClicked: window.advanced = !window.advanced }
                            ColumnLayout {
                                visible: window.advanced; spacing: 4
                                CheckBox { id: affine; text: "Affine Ausrichtung"; palette.windowText: "#a6bcc7"; font.pixelSize: 11; enabled: !studio.busy && alignment.checked }
                                CheckBox { id: refSelected; text: "Gewählte Quelle als Referenz"; palette.windowText: "#a6bcc7"; font.pixelSize: 11; enabled: !studio.busy && alignment.checked }
                                Text { text: "Standard: mittleres Bild, Rotation,\nVerschiebung und Focus Breathing."; color: "#728f9e"; font.pixelSize: 10; lineHeight: 1.4 }
                            }
                            Text { text: "Volle Auflösung · Lineare Verarbeitung\nOriginaldateien bleiben unverändert."; color: "#6f8b9a"; font.pixelSize: 10; lineHeight: 1.5; Layout.fillWidth: true }
                        }
                        ColumnLayout {
                            visible: window.isRetouch; Layout.fillWidth: true; spacing: 17
                            Eyebrow { text: "PRÄZISE RETUSCHE" }
                            Text { text: "Das letzte Detail."; color: "#e1ebee"; font.pixelSize: 21; font.weight: Font.DemiBold }
                            Text { text: "Wähle links die schärfste Quelle. Male anschließend im Ergebnis über die Stelle, die du ersetzen möchtest."; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: "#92aab7"; font.pixelSize: 12; lineHeight: 1.4 }
                            RowLayout {
                                ActionButton { text: "Quellenpinsel"; selected: !window.erase; onClicked: window.erase = false }
                                ActionButton { text: "Radierer"; selected: window.erase; onClicked: window.erase = true }
                            }
                            Parameter { id: brushSize; label: "Pinselgröße"; from: 3; to: 160; value: 35; stepSize: 1; Layout.fillWidth: true }
                            Parameter { id: brushHardness; label: "Härte"; from: 0; to: 1; value: .5; decimals: 2; Layout.fillWidth: true }
                            Parameter { id: brushOpacity; label: "Deckkraft"; from: .05; to: 1; value: 1; decimals: 2; Layout.fillWidth: true }
                            RowLayout {
                                ActionButton { text: "↶  Undo"; onClicked: studio.undo(); enabled: !studio.busy }
                                ActionButton { text: "↷  Redo"; onClicked: studio.redo(); enabled: !studio.busy }
                            }
                            Text { text: "B Pinsel · E Radierer\nStrg + Ziehen zum Verschieben\nBild ↑ / ↓ wechselt die Quelle\nRechtsklick auf ein Ergebnis: Pinselquelle"; color: "#738f9e"; font.pixelSize: 10; lineHeight: 1.6 }
                        }
                        ColumnLayout {
                            visible: studio.workspace === "Exportieren"; Layout.fillWidth: true; spacing: 17
                            Eyebrow { text: "DEIN FERTIGES BILD" }
                            Text { text: "Bereit für mehr."; color: "#e1ebee"; font.pixelSize: 21; font.weight: Font.DemiBold }
                            Text { text: "Linear-DNG erhält den Kamerafarbraum. Entwickle Weißabgleich und Tonwerte anschließend in Lightroom oder Camera Raw."; color: "#92aab7"; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true; lineHeight: 1.4 }
                            ActionButton { text: "Linear-DNG exportieren   ↗"; primary: true; Layout.fillWidth: true; enabled: !studio.busy && studio.canDng; onClicked: studio.export("dng") }
                            ActionButton { text: "16-Bit-TIFF exportieren"; Layout.fillWidth: true; enabled: !studio.busy && studio.results.length > 0; onClicked: studio.export("tif") }
                            ActionButton { text: "JPEG exportieren"; Layout.fillWidth: true; enabled: !studio.busy && studio.results.length > 0; onClicked: studio.export("jpg") }
                            Text { text: "DNG benötigt einen RAW-Stack in voller Auflösung. TIFF und JPEG übernehmen die Vorschaueinstellungen."; color: "#738f9e"; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                        }
                        Rectangle { Layout.fillWidth: true; height: 1; color: "#30404a" }
                        Eyebrow { text: "ANZEIGE / TIFF / JPEG" }
                        Parameter { id: exposure; label: "Belichtung (EV)"; from: -3; to: 3; value: 0; stepSize: .1; decimals: 1; Layout.fillWidth: true; onEdited: studio.displaySettings(value, warmth.value) }
                        Parameter { id: warmth; label: "Wärmer / kühler"; from: -.5; to: .5; value: 0; stepSize: .01; decimals: 2; Layout.fillWidth: true; onEdited: studio.displaySettings(exposure.value, value) }
                        Text { text: "DNG bleibt ohne eingebrannte Entwicklung."; color: "#6e8b99"; font.pixelSize: 9; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                        Item { Layout.preferredHeight: 10 }
                    }
                }
                Rectangle {
                    visible: studio.workspace === "Stacken"
                    anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right
                    height: 119; color: "#19232b"
                    ColumnLayout {
                        anchors.fill: parent; anchors.margins: 17; spacing: 8
                        ActionButton { text: "Schnelle Vorschau"; Layout.fillWidth: true; enabled: !studio.busy && studio.files.length >= 2; onClicked: studio.render(radius.value, smoothing.value, levels.value, alignment.checked, affine.checked, refSelected.checked, true) }
                        ActionButton { text: "Stack berechnen   ↗"; primary: true; implicitHeight: 44; Layout.fillWidth: true; enabled: !studio.busy && studio.files.length >= 2; onClicked: studio.render(radius.value, smoothing.value, levels.value, alignment.checked, affine.checked, refSelected.checked, false) }
                    }
                }
            }
        }
        Rectangle {
            Layout.fillWidth: true; Layout.preferredHeight: 139; color: "#172129"
            ColumnLayout {
                anchors.fill: parent; anchors.leftMargin: 22; anchors.rightMargin: 22; anchors.topMargin: 13; anchors.bottomMargin: 12; spacing: 10
                RowLayout {
                    Layout.fillWidth: true
                    Eyebrow { text: "ERGEBNISSE" }
                    Text { text: studio.results.length + " Varianten"; color: "#617f8f"; font.pixelSize: 10 }
                    Item { Layout.fillWidth: true }
                    Text { text: "Neue Berechnungen bleiben als eigene Variante erhalten."; color: "#6f8a99"; font.pixelSize: 10 }
                }
                ListView {
                    id: outputs; Layout.fillWidth: true; Layout.fillHeight: true; orientation: ListView.Horizontal; spacing: 10; clip: true
                    model: studio.results
                    delegate: Rectangle {
                        required property var modelData
                        required property int index
                        width: 256; height: outputs.height; radius: 8
                        color: studio.activeResult === index ? "#243d3b" : "#1d2b34"
                        border.color: studio.activeResult === index ? "#5e9d8b" : "#32434d"
                        RowLayout {
                            anchors.fill: parent; anchors.margins: 7; spacing: 12
                            Image { source: modelData.thumb; Layout.preferredWidth: 82; Layout.fillHeight: true; fillMode: Image.PreserveAspectCrop; clip: true }
                            ColumnLayout {
                                Layout.fillWidth: true; spacing: 6
                                Text { text: modelData.label + (modelData.preview ? " · Vorschau" : ""); color: "#d9e8e9"; font.pixelSize: 12; font.weight: Font.DemiBold }
                                Text { text: modelData.detail; color: "#8aacae"; font.pixelSize: 10 }
                            }
                        }
                        MouseArea {
                            anchors.fill: parent; acceptedButtons: Qt.LeftButton | Qt.RightButton
                            enabled: !studio.busy
                            onClicked: function(mouse) { if (mouse.button === Qt.RightButton) studio.useResultAsSource(index); else studio.selectResult(index) }
                        }
                    }
                    Text { anchors.centerIn: parent; visible: studio.results.length === 0; text: "Deine Ergebnisse erscheinen hier — bereit zum Vergleichen und Verfeinern."; color: "#4f6c7c"; font.pixelSize: 11 }
                }
            }
        }
        Rectangle {
            Layout.fillWidth: true; Layout.preferredHeight: 40; color: "#10191f"
            RowLayout {
                anchors.fill: parent; anchors.leftMargin: 22; anchors.rightMargin: 22; spacing: 12
                Rectangle { width: 5; height: 5; radius: 3; color: studio.busy ? "#dab886" : "#71c5ae" }
                Text { text: studio.phase; color: "#91a8b6"; font.pixelSize: 10; Layout.fillWidth: true; elide: Text.ElideRight }
                ProgressBar { visible: studio.busy; indeterminate: !studio.canCancel; value: studio.progress; Layout.preferredWidth: 180 }
                ActionButton { visible: studio.busy && studio.canCancel; text: "Abbrechen"; quiet: true; implicitHeight: 28; onClicked: studio.cancel() }
                Text { visible: !studio.busy; text: "STCKR 0.1  /  CPU ENGINE"; color: "#526f80"; font.pixelSize: 9; font.letterSpacing: .7 }
            }
        }
    }
    DropArea {
        anchors.fill: parent
        onDropped: function(drop) { if (drop.hasUrls) { studio.dropFiles(drop.urls); drop.acceptProposedAction() } }
        Rectangle {
            anchors.fill: parent; anchors.margins: 6; visible: parent.containsDrag
            color: "#bb142b28"; border.width: 2; border.color: "#80ddc4"; radius: 12
            Text { anchors.centerIn: parent; text: "Loslassen, um deine Fokusserie zu laden"; color: "#bdf6e3"; font.pixelSize: 24 }
        }
    }
}
