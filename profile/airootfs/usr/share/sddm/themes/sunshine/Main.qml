// Sunshine OS login screen. Plain QtQuick only (no Controls), so it loads under any style or renderer.
import QtQuick 2.15

Rectangle {
    id: root
    width: 1920; height: 1080
    color: "#0b111d"
    property int sessionIndex: (typeof sessionModel !== "undefined" && sessionModel.lastIndex >= 0) ? sessionModel.lastIndex : 0
    property string sessionName: ""
    property color gold: "#ffc98a"
    property color ink: "#fdf0dc"
    property color panel: "#c0140f1c"

    Image { anchors.fill: parent; source: config.background; fillMode: Image.PreserveAspectCrop; asynchronous: true }
    Rectangle { anchors.fill: parent; gradient: Gradient {
        GradientStop { position: 0.0; color: "#10000000" }
        GradientStop { position: 0.5; color: "#18000000" }
        GradientStop { position: 1.0; color: "#e00b0713" } } }

    Text { id: clock; anchors.top: parent.top; anchors.topMargin: 40; anchors.horizontalCenter: parent.horizontalCenter
        color: root.ink; font.pixelSize: 60; font.weight: Font.Light
        text: Qt.formatTime(new Date(), "hh:mm")
        Timer { interval: 10000; running: true; repeat: true; onTriggered: clock.text = Qt.formatTime(new Date(), "hh:mm") } }

    Column {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom; anchors.bottomMargin: 80
        spacing: 12; width: 380

        Text { text: "Welcome back"; anchors.horizontalCenter: parent.horizontalCenter
            color: root.gold; font.pixelSize: 28; font.italic: true }

        Rectangle { width: parent.width; height: 44; radius: 8; color: root.panel
            border.color: user.activeFocus ? root.gold : "#80ffc98a"; border.width: 1
            TextInput { id: user; anchors.fill: parent; anchors.margins: 10; verticalAlignment: TextInput.AlignVCenter
                horizontalAlignment: TextInput.AlignHCenter; color: root.ink; font.pixelSize: 16; clip: true
                text: (typeof userModel !== "undefined") ? userModel.lastUser : ""
                KeyNavigation.tab: pass; Keys.onReturnPressed: pass.forceActiveFocus() }
            Text { anchors.centerIn: parent; text: "Username"; color: "#80fdf0dc"; font.pixelSize: 16; visible: user.text === "" && !user.activeFocus } }

        Rectangle { width: parent.width; height: 44; radius: 8; color: root.panel
            border.color: pass.activeFocus ? root.gold : "#80ffc98a"; border.width: 1
            TextInput { id: pass; anchors.fill: parent; anchors.margins: 10; verticalAlignment: TextInput.AlignVCenter
                horizontalAlignment: TextInput.AlignHCenter; color: root.ink; font.pixelSize: 16; clip: true
                echoMode: TextInput.Password; passwordCharacter: "•"; focus: true
                KeyNavigation.backtab: user
                Keys.onReturnPressed: sddm.login(user.text, pass.text, root.sessionIndex)
                Keys.onEnterPressed: sddm.login(user.text, pass.text, root.sessionIndex) }
            Text { anchors.centerIn: parent; text: "Password"; color: "#80fdf0dc"; font.pixelSize: 16; visible: pass.text === "" && !pass.activeFocus } }

        Text { id: err; anchors.horizontalCenter: parent.horizontalCenter; color: "#ff9a8a"; font.pixelSize: 14; text: "" }

        Row { spacing: 12; anchors.horizontalCenter: parent.horizontalCenter
            Rectangle { width: 180; height: 42; radius: 8; color: loginArea.pressed ? "#e0801f" : "#ff9e3d"
                Text { anchors.centerIn: parent; text: "Log in"; color: "#2a1a0e"; font.pixelSize: 16; font.bold: true }
                MouseArea { id: loginArea; anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                    onClicked: sddm.login(user.text, pass.text, root.sessionIndex) } }
            Rectangle { width: 180; height: 42; radius: 8; color: root.panel; border.color: "#80ffc98a"
                Text { anchors.centerIn: parent; color: root.ink; font.pixelSize: 14; elide: Text.ElideRight; width: parent.width - 16
                    horizontalAlignment: Text.AlignHCenter
                    text: root.sessionName !== "" ? root.sessionName : "Session" }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                    onClicked: { if (sessionModel.count > 0) root.sessionIndex = (root.sessionIndex + 1) % sessionModel.count } } }
        }
        Text { anchors.horizontalCenter: parent.horizontalCenter; color: "#a0fdf0dc"; font.pixelSize: 12
            text: "Click the session button to switch between Hyprland and Plasma" }
    }

    // First boot has no "last user": pre-fill the first account so only the password is needed.
    Repeater { model: (typeof userModel !== "undefined") ? userModel : 0; delegate: Item { visible: false
        Component.onCompleted: if (index === 0 && user.text === "") user.text = model.name } }

    // Session name comes from the model; ask for it whenever the index changes.
    Repeater { model: sessionModel; delegate: Item { visible: false
        property bool current: index === root.sessionIndex
        onCurrentChanged: if (current) root.sessionName = model.name
        Component.onCompleted: if (current) root.sessionName = model.name } }

    Row { anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 24; spacing: 12
        Rectangle { width: 96; height: 34; radius: 8; color: root.panel; border.color: "#80ffc98a"
            Text { anchors.centerIn: parent; text: "Restart"; color: root.ink; font.pixelSize: 13 }
            MouseArea { anchors.fill: parent; onClicked: sddm.reboot() } }
        Rectangle { width: 96; height: 34; radius: 8; color: root.panel; border.color: "#80ffc98a"
            Text { anchors.centerIn: parent; text: "Shut down"; color: root.ink; font.pixelSize: 13 }
            MouseArea { anchors.fill: parent; onClicked: sddm.powerOff() } }
    }

    Connections { target: sddm
        function onLoginFailed() { err.text = "That did not work. Check the password and try again."; pass.text = ""; pass.forceActiveFocus() } }
    Component.onCompleted: pass.forceActiveFocus()
}
