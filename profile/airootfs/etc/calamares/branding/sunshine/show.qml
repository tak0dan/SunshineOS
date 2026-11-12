import QtQuick 2.0
import calamares.slideshow 1.0

Presentation {
    id: presentation
    Rectangle { anchors.fill: parent; color: "#1d1526"; z: -10 }   // no white margin around the slides
    Timer { interval: 6000; running: true; repeat: true; onTriggered: presentation.goToNextSlide() }
    Slide { anchors.fill: parent; Rectangle { anchors.fill: parent; color: "#1d1526"
        Column { anchors.centerIn: parent; spacing: 14
            Image { source: "logo.png"; width: 200; height: 200; fillMode: Image.PreserveAspectFit; anchors.horizontalCenter: parent.horizontalCenter }
            Text { text: "Welcome to Sunshine OS"; color: "#ffb86b"; font.pixelSize: 30; anchors.horizontalCenter: parent.horizontalCenter }
            Text { text: "A friendly start with everything you need."; color: "#f6ead6"; font.pixelSize: 16; anchors.horizontalCenter: parent.horizontalCenter } } } }
    Slide { anchors.fill: parent; Rectangle { anchors.fill: parent; color: "#1d1526"
        Column { anchors.centerIn: parent; spacing: 14
            Text { text: "Get apps in one click"; color: "#ffb86b"; font.pixelSize: 28; anchors.horizontalCenter: parent.horizontalCenter }
            Text { text: "Open \"Get apps\" to browse and install programs.\nUpdates are one button: \"Update System\"."; color: "#f6ead6"; font.pixelSize: 16; horizontalAlignment: Text.AlignHCenter; anchors.horizontalCenter: parent.horizontalCenter } } } }
    Slide { anchors.fill: parent; Rectangle { anchors.fill: parent; color: "#1d1526"
        Column { anchors.centerIn: parent; spacing: 14
            Text { text: "Restore points"; color: "#ffb86b"; font.pixelSize: 28; anchors.horizontalCenter: parent.horizontalCenter }
            Text { text: "Something went wrong? Roll the system back\nto an earlier day from Sunshine Welcome."; color: "#f6ead6"; font.pixelSize: 16; horizontalAlignment: Text.AlignHCenter; anchors.horizontalCenter: parent.horizontalCenter } } } }
}
