from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from ui.animations import apply_glow, update_glow
from ui.components import ChatBubble, QuickActionButton, StatusPanel


class MainWindow(QMainWindow):
    command_submitted = pyqtSignal(str)
    listen_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Myra - Advanced Desktop AI")
        self.resize(1280, 780)
        self._status_mode = "online"
        self._glow_tick = 0
        self._mini_mode = False
        self._message_count = 0
        self._build_ui()
        self._setup_tray()

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()

        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._animate_state)
        self._animation_timer.start(140)

        self._battery_timer = QTimer(self)
        self._battery_timer.timeout.connect(self._update_battery)
        self._battery_timer.start(30000)
        self._update_battery()

        self.secondary_clear_button.clicked.connect(self._clear_history)

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)

        page_layout = QVBoxLayout(root)
        page_layout.setContentsMargins(16, 16, 16, 16)
        page_layout.setSpacing(0)

        self.shell = QFrame()
        self.shell.setObjectName("ShellFrame")
        shell_layout = QVBoxLayout(self.shell)
        shell_layout.setContentsMargins(20, 18, 20, 18)
        shell_layout.setSpacing(16)

        shell_layout.addLayout(self._build_top_bar())
        shell_layout.addLayout(self._build_status_row())

        content_row = QHBoxLayout()
        content_row.setSpacing(16)
        content_row.addWidget(self._build_sidebar(), 2)
        content_row.addWidget(self._build_center_zone(), 5)
        content_row.addWidget(self._build_chat_panel(), 4)
        shell_layout.addLayout(content_row, 1)

        self.footer_bar = self._build_footer_bar()
        shell_layout.addWidget(self.footer_bar)

        page_layout.addWidget(self.shell)

    def _build_top_bar(self):
        top_bar = QHBoxLayout()
        top_bar.setSpacing(12)

        brand_wrap = QFrame()
        brand_wrap.setObjectName("TopCard")
        brand_layout = QVBoxLayout(brand_wrap)
        brand_layout.setContentsMargins(16, 12, 16, 12)
        brand_layout.setSpacing(2)

        self.brand_label = QLabel("Myra")
        self.brand_label.setObjectName("BrandLabel")
        self.brand_label.setFont(QFont("Segoe UI", 24, 800))
        self.tagline_label = QLabel("Advanced Desktop AI")
        self.tagline_label.setObjectName("TaglineLabel")
        brand_layout.addWidget(self.brand_label)
        brand_layout.addWidget(self.tagline_label)

        status_wrap = QFrame()
        status_wrap.setObjectName("TopCard")
        status_layout = QHBoxLayout(status_wrap)
        status_layout.setContentsMargins(14, 12, 14, 12)
        status_layout.setSpacing(10)
        status_dot = QLabel()
        status_dot.setObjectName("StatusDot")
        status_dot.setFixedSize(10, 10)
        self.status_indicator = QLabel("Online")
        self.status_indicator.setObjectName("StatusIndicator")
        status_layout.addWidget(status_dot, 0, Qt.AlignmentFlag.AlignVCenter)
        status_layout.addWidget(self.status_indicator)

        right_wrap = QFrame()
        right_wrap.setObjectName("TopCard")
        right_layout = QHBoxLayout(right_wrap)
        right_layout.setContentsMargins(12, 10, 12, 10)
        right_layout.setSpacing(10)

        self.clock_label = QLabel()
        self.clock_label.setObjectName("ClockLabel")
        self.battery_label = QLabel("Battery --")
        self.battery_label.setObjectName("BatteryLabel")

        self.minimize_button = QPushButton("_")
        self.minimize_button.setObjectName("WindowButton")
        self.minimize_button.clicked.connect(self.showMinimized)

        self.close_button = QPushButton("X")
        self.close_button.setObjectName("WindowButton")
        self.close_button.clicked.connect(self.close)

        right_layout.addWidget(self.clock_label)
        right_layout.addWidget(self.battery_label)
        right_layout.addWidget(self.minimize_button)
        right_layout.addWidget(self.close_button)

        top_bar.addWidget(brand_wrap, 4)
        top_bar.addWidget(status_wrap, 2)
        top_bar.addWidget(right_wrap, 4)
        return top_bar

    def _build_status_row(self):
        row = QHBoxLayout()
        row.setSpacing(12)
        self.engine_panel = StatusPanel("Voice Engine", "Ready")
        self.mode_panel = StatusPanel("Mode", "Dashboard")
        self.sync_panel = StatusPanel("Memory", "Synced")
        row.addWidget(self.engine_panel)
        row.addWidget(self.mode_panel)
        row.addWidget(self.sync_panel)
        return row

    def _build_sidebar(self):
        self.sidebar = QFrame()
        self.sidebar.setObjectName("SidebarPanel")
        layout = QVBoxLayout(self.sidebar)
        layout.setContentsMargins(14, 16, 14, 16)
        layout.setSpacing(12)

        title = QLabel("Quick Controls")
        title.setObjectName("SectionMiniTitle")
        layout.addWidget(title)

        quick_grid = QGridLayout()
        quick_grid.setHorizontalSpacing(8)
        quick_grid.setVerticalSpacing(8)
        self.quick_buttons = []
        quick_actions = [
            ("C", "Chrome", "open chrome", "Open Chrome"),
            ("V", "VS Code", "open vs code", "Open VS Code"),
            ("S", "Shot", "take screenshot", "Take screenshot"),
            ("+", "Volume", "volume up", "Volume up"),
            ("G", "Mouse", "mouse position", "Mouse position"),
            ("M", "Memory", "save note demo note", "Save note"),
            ("F", "Files", "organize downloads", "Organize Downloads"),
            ("P", "Power", "lock screen", "Lock screen"),
            ("T", "Tasks", "show tasks", "Show tasks"),
        ]
        for index, (icon_text, title_text, command, tooltip) in enumerate(quick_actions):
            button = QuickActionButton(icon_text, title_text, command, tooltip)
            button.clicked.connect(self._handle_quick_action)
            quick_grid.addWidget(button, index // 2, index % 2)
            self.quick_buttons.append(button)

        divider = QFrame()
        divider.setObjectName("DividerLine")
        divider.setFixedHeight(1)

        quick_note = QLabel(
            "Use quick controls for one-tap actions. For complex commands, use voice or the input bar."
        )
        quick_note.setObjectName("SidebarNote")
        quick_note.setWordWrap(True)

        layout.addLayout(quick_grid)
        layout.addWidget(divider)
        layout.addWidget(quick_note)
        layout.addStretch()
        return self.sidebar

    def _build_center_zone(self):
        self.center_panel = QFrame()
        self.center_panel.setObjectName("CenterPanel")
        layout = QVBoxLayout(self.center_panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)
        self.center_kicker = QLabel("AI CORE")
        self.center_kicker.setObjectName("SectionMiniTitle")
        self.center_title = QLabel("Professional Desktop Control")
        self.center_title.setObjectName("HeroTitle")
        self.center_title.setWordWrap(True)
        self.center_body = QLabel(
            "Myra handles desktop tasks, web actions, and memory workflows while keeping live voice feedback active."
        )
        self.center_body.setObjectName("BodyLabel")
        self.center_body.setWordWrap(True)
        header_layout.addWidget(self.center_kicker)
        header_layout.addWidget(self.center_title)
        header_layout.addWidget(self.center_body)

        self.notification_banner = QLabel("All systems stable.")
        self.notification_banner.setObjectName("InfoBanner")
        self.activity_indicator = QLabel("Voice Activity: Idle")
        self.activity_indicator.setObjectName("ActivityLabel")

        core_row = QHBoxLayout()
        core_row.setSpacing(14)

        self.mic_shell = QFrame()
        self.mic_shell.setObjectName("MicShell")
        mic_layout = QVBoxLayout(self.mic_shell)
        mic_layout.setContentsMargins(18, 18, 18, 18)
        mic_layout.setSpacing(12)

        self.mic_core = QFrame()
        self.mic_core.setObjectName("MicCore")
        self.mic_core.setFixedSize(200, 200)
        core_layout = QVBoxLayout(self.mic_core)
        core_layout.setContentsMargins(0, 0, 0, 0)
        core_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mic_glow = apply_glow(self.mic_core, "#74d8ff", 40)
        self.mic_label = QLabel("A")
        self.mic_label.setObjectName("MicLabel")
        core_layout.addWidget(self.mic_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.wave_panel = QFrame()
        self.wave_panel.setObjectName("WavePanel")
        wave_layout = QHBoxLayout(self.wave_panel)
        wave_layout.setContentsMargins(14, 10, 14, 10)
        wave_layout.setSpacing(8)
        self.wave_bars = []
        for object_name in ["WaveBar1", "WaveBar2", "WaveBar3", "WaveBar4", "WaveBar5"]:
            bar = QFrame()
            bar.setObjectName(object_name)
            bar.setFixedWidth(10)
            wave_layout.addWidget(bar, alignment=Qt.AlignmentFlag.AlignBottom)
            self.wave_bars.append(bar)

        mic_layout.addWidget(self.mic_core, alignment=Qt.AlignmentFlag.AlignCenter)
        mic_layout.addWidget(self.wave_panel)

        diagnostics = QFrame()
        diagnostics.setObjectName("DiagnosticsCard")
        diag_layout = QVBoxLayout(diagnostics)
        diag_layout.setContentsMargins(16, 16, 16, 16)
        diag_layout.setSpacing(10)

        diag_title = QLabel("Live Diagnostics")
        diag_title.setObjectName("SectionMiniTitle")

        telemetry_grid = QGridLayout()
        telemetry_grid.setHorizontalSpacing(8)
        telemetry_grid.setVerticalSpacing(8)
        self.signal_chip = QLabel("Signal Stable")
        self.signal_chip.setObjectName("TelemetryChip")
        self.input_chip = QLabel("Input: Voice + Text")
        self.input_chip.setObjectName("TelemetryChip")
        self.reply_chip = QLabel("Replies: Live")
        self.reply_chip.setObjectName("TelemetryChip")
        self.session_chip = QLabel("Session: Active")
        self.session_chip.setObjectName("TelemetryChip")
        chips = [self.signal_chip, self.input_chip, self.reply_chip, self.session_chip]
        for index, chip in enumerate(chips):
            telemetry_grid.addWidget(chip, index // 2, index % 2)

        prompts_title = QLabel("Suggested Commands")
        prompts_title.setObjectName("SectionMiniTitle")
        prompts_grid = QGridLayout()
        prompts_grid.setHorizontalSpacing(8)
        prompts_grid.setVerticalSpacing(8)
        self.prompt_cards = []
        prompts = [
            "Myra open Chrome",
            "YouTube par Python search",
            "Move mouse to 500 300",
            "Schedule open vscode at 18:30",
        ]
        for index, text in enumerate(prompts):
            prompt = QLabel(text)
            prompt.setObjectName("PromptCard")
            prompt.setWordWrap(True)
            prompts_grid.addWidget(prompt, index // 2, index % 2)
            self.prompt_cards.append(prompt)

        center_actions = QHBoxLayout()
        center_actions.setSpacing(8)
        self.listen_button = QPushButton("Start Listening")
        self.listen_button.setObjectName("PrimaryButton")
        self.listen_button.clicked.connect(self.listen_requested.emit)
        self.secondary_clear_button = QPushButton("Clear Chat")
        self.secondary_clear_button.setObjectName("SecondaryButton")
        center_actions.addWidget(self.listen_button)
        center_actions.addWidget(self.secondary_clear_button)

        diag_layout.addWidget(diag_title)
        diag_layout.addLayout(telemetry_grid)
        diag_layout.addWidget(prompts_title)
        diag_layout.addLayout(prompts_grid)
        diag_layout.addStretch()
        diag_layout.addLayout(center_actions)

        core_row.addWidget(self.mic_shell, 3)
        core_row.addWidget(diagnostics, 4)

        layout.addLayout(header_layout)
        layout.addWidget(self.notification_banner)
        layout.addWidget(self.activity_indicator)
        layout.addLayout(core_row, 1)
        return self.center_panel

    def _build_chat_panel(self):
        self.chat_panel = QFrame()
        self.chat_panel.setObjectName("ChatPanel")
        layout = QVBoxLayout(self.chat_panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)
        title_wrap = QVBoxLayout()
        title_wrap.setSpacing(2)
        self.chat_title = QLabel("Command History")
        self.chat_title.setObjectName("SectionTitle")
        self.chat_subtitle = QLabel("Conversation timeline with Myra")
        self.chat_subtitle.setObjectName("BodyLabel")
        title_wrap.addWidget(self.chat_title)
        title_wrap.addWidget(self.chat_subtitle)

        toggles_wrap = QVBoxLayout()
        toggles_wrap.setSpacing(6)
        toggles_row = QHBoxLayout()
        toggles_row.setSpacing(10)
        self.top_pin_checkbox = QCheckBox("Always On Top")
        self.top_pin_checkbox.toggled.connect(self._toggle_on_top)
        self.mini_mode_checkbox = QCheckBox("Mini Mode")
        self.mini_mode_checkbox.toggled.connect(self._toggle_mini_mode)
        toggles_row.addWidget(self.top_pin_checkbox)
        toggles_row.addWidget(self.mini_mode_checkbox)
        toggles_row.addStretch()
        toggles_wrap.addLayout(toggles_row)

        header.addLayout(title_wrap)
        header.addStretch()
        header.addLayout(toggles_wrap)

        self.history_meta_row = QHBoxLayout()
        self.history_meta_row.setSpacing(8)
        self.history_count_label = QLabel("Messages: 0")
        self.history_count_label.setObjectName("MetaPill")
        self.history_state_label = QLabel("State: Idle")
        self.history_state_label.setObjectName("MetaPill")
        self.history_meta_row.addWidget(self.history_count_label)
        self.history_meta_row.addWidget(self.history_state_label)
        self.history_meta_row.addStretch()

        self.history_hint = QLabel("No commands yet. Start listening or type below.")
        self.history_hint.setObjectName("HistoryHint")

        self.history_list = QListWidget()
        self.history_list.setObjectName("HistoryList")
        self.history_list.setSpacing(8)
        self.history_list.setUniformItemSizes(False)
        self.history_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.history_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.history_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.history_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.history_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        layout.addLayout(header)
        layout.addLayout(self.history_meta_row)
        layout.addWidget(self.history_hint)
        layout.addWidget(self.history_list, 1)
        return self.chat_panel

    def _build_footer_bar(self):
        footer = QFrame()
        footer.setObjectName("FooterBar")
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        self.input_field = QLineEdit()
        self.input_field.setObjectName("CommandInput")
        self.input_field.setPlaceholderText("Type a command for Myra...")
        self.input_field.returnPressed.connect(self._submit_input)

        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("PrimaryButton")
        self.send_button.clicked.connect(self._submit_input)

        self.clear_button = QPushButton("Clear")
        self.clear_button.setObjectName("SecondaryButton")
        self.clear_button.clicked.connect(self._clear_history)

        self.mic_toggle_button = QPushButton("Mic")
        self.mic_toggle_button.setObjectName("SecondaryButton")
        self.mic_toggle_button.clicked.connect(self.listen_requested.emit)

        layout.addWidget(self.input_field, 1)
        layout.addWidget(self.send_button)
        layout.addWidget(self.clear_button)
        layout.addWidget(self.mic_toggle_button)
        return footer

    def _setup_tray(self):
        tray_icon = self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon)
        self.tray = QSystemTrayIcon(tray_icon, self)
        self.setWindowIcon(tray_icon)

        menu = QMenu(self)
        show_action = QAction("Show Dashboard", self)
        show_action.triggered.connect(self._restore_dashboard)
        mini_action = QAction("Mini Mode", self)
        mini_action.triggered.connect(lambda: self._toggle_mini_mode(True))
        quit_action = QAction("Exit", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(show_action)
        menu.addAction(mini_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._restore_dashboard()

    def _restore_dashboard(self):
        self._toggle_mini_mode(False)
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def keep_dashboard_on_top(self, enabled=True):
        self.top_pin_checkbox.setChecked(bool(enabled))

    def _submit_input(self):
        text = self.input_field.text().strip()
        if not text:
            return
        self.command_submitted.emit(text)
        self.input_field.clear()

    def _handle_quick_action(self):
        button = self.sender()
        if isinstance(button, QuickActionButton):
            self.command_submitted.emit(button.command)

    def _clear_history(self):
        self.history_list.clear()
        self._message_count = 0
        self.history_count_label.setText("Messages: 0")
        self.history_hint.show()

    def _toggle_on_top(self, enabled):
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)
        self.show()

    def _toggle_mini_mode(self, enabled):
        enabled = bool(enabled)
        self._mini_mode = enabled
        self.mini_mode_checkbox.blockSignals(True)
        self.mini_mode_checkbox.setChecked(enabled)
        self.mini_mode_checkbox.blockSignals(False)
        self.mode_panel.set_value("Mini" if enabled else "Dashboard")

        if enabled:
            self.resize(240, 240)
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            self.sidebar.hide()
            self.chat_panel.hide()
            self.engine_panel.hide()
            self.mode_panel.hide()
            self.sync_panel.hide()
            self.center_kicker.hide()
            self.center_title.hide()
            self.center_body.hide()
            self.notification_banner.hide()
            self.wave_panel.hide()
            self.secondary_clear_button.hide()
            self.footer_bar.hide()
            self.show()
        else:
            self.resize(1280, 780)
            self.sidebar.show()
            self.chat_panel.show()
            self.engine_panel.show()
            self.mode_panel.show()
            self.sync_panel.show()
            self.center_kicker.show()
            self.center_title.show()
            self.center_body.show()
            self.notification_banner.show()
            self.wave_panel.show()
            self.secondary_clear_button.show()
            self.footer_bar.show()
            if not self.top_pin_checkbox.isChecked():
                self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
            self.show()

    def _update_clock(self):
        self.clock_label.setText(datetime.now().strftime("%d %b %Y | %I:%M:%S %p"))

    def _update_battery(self):
        try:
            import psutil
        except ImportError:
            self.battery_label.setText("Battery --")
            return

        battery = psutil.sensors_battery()
        if battery is None:
            self.battery_label.setText("Battery --")
            return

        self.battery_label.setText(f"Battery {int(battery.percent)}%")

    def _animate_state(self):
        self._glow_tick = (self._glow_tick + 1) % 6
        base_patterns = {
            "online": ([24, 18, 14, 18, 24], "#95a7b8", 26),
            "listening": ([22, 38, 54, 38, 22], "#44c7ff", 42),
            "processing": ([30, 22, 16, 22, 30], "#9d63ff", 50),
            "speaking": ([18, 28, 42, 28, 18], "#5fe4ff", 36),
            "error": ([18, 18, 18, 18, 18], "#ff6464", 38),
        }
        heights, color, blur = base_patterns.get(self._status_mode, base_patterns["online"])
        update_glow(
            self.mic_glow,
            color,
            blur + (self._glow_tick * 2 if self._status_mode != "online" else 0),
        )
        for index, bar in enumerate(self.wave_bars):
            wobble = ((self._glow_tick + index) % 3) * 5
            bar.setFixedHeight(heights[index] + wobble)

    def set_status(self, status):
        mapping = {
            "online": ("Online", "online", "Ready"),
            "listening": ("Listening", "listening", "Listening"),
            "processing": ("Processing", "processing", "Thinking"),
            "speaking": ("Speaking", "speaking", "Responding"),
            "error": ("Error", "error", "Attention"),
        }
        key = status.lower()
        label, mode, engine_value = mapping.get(key, (status, "online", "Ready"))
        self.status_indicator.setText(label)
        self.status_indicator.setProperty("state", mode)
        self.status_indicator.style().unpolish(self.status_indicator)
        self.status_indicator.style().polish(self.status_indicator)
        self._status_mode = mode
        self.engine_panel.set_value(engine_value)
        self.history_state_label.setText(f"State: {label}")

        if mode == "listening":
            self.listen_button.setText("Listening On")
            self.mic_toggle_button.setText("Mic On")
            self.notification_banner.setText("Listening for your next instruction.")
            self.activity_indicator.setText("Voice Activity: Capturing audio")
        elif mode == "processing":
            self.listen_button.setText("Processing...")
            self.mic_toggle_button.setText("Mic On")
            self.notification_banner.setText("Myra is processing the request.")
            self.activity_indicator.setText("Voice Activity: Analyzing command")
        elif mode == "speaking":
            self.listen_button.setText("Speaking...")
            self.mic_toggle_button.setText("Mic On")
            self.notification_banner.setText("Myra is replying now.")
            self.activity_indicator.setText("Voice Activity: Delivering response")
        elif mode == "error":
            self.listen_button.setText("Retry")
            self.mic_toggle_button.setText("Mic")
            self.notification_banner.setText("An issue needs attention.")
            self.activity_indicator.setText("Voice Activity: Error state")
        else:
            self.listen_button.setText("Start Listening")
            self.mic_toggle_button.setText("Mic")
            self.notification_banner.setText("All systems stable.")
            self.activity_indicator.setText("Voice Activity: Idle")

    def add_history(self, text):
        timestamp = datetime.now().strftime("%I:%M %p")
        role = "assistant"
        message = text
        if text.startswith("You: "):
            role = "user"
            message = text.replace("You: ", "", 1)
        elif text.startswith("Myra: "):
            message = text.replace("Myra: ", "", 1)

        item = QListWidgetItem()
        bubble = ChatBubble(role, message, timestamp)
        item.setSizeHint(bubble.sizeHint())
        self.history_list.addItem(item)
        self.history_list.setItemWidget(item, bubble)
        self.history_list.scrollToBottom()
        self._message_count += 1
        self.history_count_label.setText(f"Messages: {self._message_count}")
        self.history_hint.hide()

    def show_notification(self, message, level="info"):
        self.notification_banner.setText(message)
        self.notification_banner.setProperty("level", level)
        self.notification_banner.style().unpolish(self.notification_banner)
        self.notification_banner.style().polish(self.notification_banner)
        if level == "error":
            self.set_status("Error")
        self.tray.showMessage("Myra", message, QSystemTrayIcon.MessageIcon.Information, 2500)

    def load_theme(self):
        theme_path = Path(__file__).resolve().parent / "theme.qss"
        self.setStyleSheet(theme_path.read_text(encoding="utf-8"))
