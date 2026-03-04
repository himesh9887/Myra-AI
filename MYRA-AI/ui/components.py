from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class ChatBubble(QWidget):
    def __init__(self, role, message, timestamp):
        super().__init__()
        self.role = role

        root = QHBoxLayout(self)
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(0)

        left_spacer = QWidget()
        left_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        right_spacer = QWidget()
        right_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        container = QFrame()
        container.setObjectName("UserBubble" if role == "user" else "AssistantBubble")
        container.setMinimumWidth(230)
        container.setMaximumWidth(390)
        container.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        title = QLabel("You" if role == "user" else "Myra")
        title.setObjectName("BubbleTitle")

        body = QLabel(message)
        body.setWordWrap(True)
        body.setObjectName("BubbleBody")
        body.setMinimumWidth(200)
        body.setMaximumWidth(360)

        time_label = QLabel(timestamp)
        time_label.setObjectName("BubbleTime")
        time_label.setAlignment(
            Qt.AlignmentFlag.AlignRight if role == "user" else Qt.AlignmentFlag.AlignLeft
        )

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(time_label)

        if role == "user":
            root.addWidget(left_spacer)
            root.addWidget(container, 0, Qt.AlignmentFlag.AlignRight)
            root.addWidget(right_spacer)
            root.setStretch(0, 3)
            root.setStretch(2, 1)
        else:
            root.addWidget(left_spacer)
            root.addWidget(container, 0, Qt.AlignmentFlag.AlignLeft)
            root.addWidget(right_spacer)
            root.setStretch(0, 1)
            root.setStretch(2, 3)


class QuickActionButton(QPushButton):
    def __init__(self, icon_text, title, command, tooltip):
        super().__init__(f"{icon_text}\n{title}")
        self.command = command
        self.setObjectName("QuickActionButton")
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class StatusPanel(QFrame):
    def __init__(self, title, value):
        super().__init__()
        self.setObjectName("StatCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("StatTitle")

        self.value_label = QLabel(value)
        self.value_label.setObjectName("StatValue")

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value):
        self.value_label.setText(value)
