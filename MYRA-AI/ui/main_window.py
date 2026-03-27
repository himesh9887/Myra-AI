import socket
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QAction
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
    QProgressBar,
    QSizePolicy,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from ui.animations import apply_glow, update_glow
from ui.components import (
    BodyScanWidget,
    CameraFeedWidget,
    ChatBubble,
    HudFaceWidget,
    JarvisCoreWidget,
    QuickActionButton,
    RadarWidget,
    StatusPanel,
)


class MainWindow(QMainWindow):
    command_submitted = pyqtSignal(str)
    listen_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MYRA | Tactical Dashboard")
        self.resize(1520, 860)
        self.setMinimumSize(1360, 780)
        self._status_mode = "online"
        self._glow_tick = 0
        self._mini_mode = False
        self._message_count = 0
        self._build_ui()
        self._setup_tray()

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)

        self._system_timer = QTimer(self)
        self._system_timer.timeout.connect(self._update_system_metrics)
        self._system_timer.start(2500)

        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._animate_state)
        self._animation_timer.start(140)

        self._network_timer = QTimer(self)
        self._network_timer.timeout.connect(self._update_network_info)
        self._network_timer.start(5000)

        self._update_clock()
        self._update_system_metrics()
        self._update_network_info()

        self.secondary_clear_button.clicked.connect(self._clear_history)

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)

        page_layout = QVBoxLayout(root)
        page_layout.setContentsMargins(8, 8, 8, 8)
        page_layout.setSpacing(0)

        self.shell = QFrame()
        self.shell.setObjectName("ShellFrame")
        shell_layout = QVBoxLayout(self.shell)
        shell_layout.setContentsMargins(16, 14, 16, 14)
        shell_layout.setSpacing(12)

        shell_layout.addLayout(self._build_top_bar())

        main_row = QHBoxLayout()
        main_row.setSpacing(10)
        main_row.addWidget(self._build_sidebar(), 16)
        main_row.addWidget(self._build_center_zone(), 50)
        main_row.addWidget(self._build_right_panel(), 34)
        shell_layout.addLayout(main_row, 1)

        self.footer_bar = self._build_footer_bar()
        shell_layout.addWidget(self.footer_bar)
        page_layout.addWidget(self.shell)

    def _build_top_bar(self):
        row = QHBoxLayout()
        row.setSpacing(10)

        left = QFrame()
        left.setObjectName("TopStrip")
        left_layout = QHBoxLayout(left)
        left_layout.setContentsMargins(12, 8, 12, 8)
        left_layout.setSpacing(12)

        self.brand_orb = QLabel("AI")
        self.brand_orb.setObjectName("BrandOrb")
        self.brand_orb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brand_orb.setFixedSize(44, 44)

        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        brand = QLabel("MYRA // J.A.R.V.I.S. HUD")
        brand.setObjectName("BrandLabel")
        subtitle = QLabel("TACTICAL AI CONSOLE")
        subtitle.setObjectName("TaglineLabel")
        brand_text.addWidget(brand)
        brand_text.addWidget(subtitle)

        left_layout.addWidget(self.brand_orb)
        left_layout.addLayout(brand_text)
        left_layout.addStretch()

        self.status_indicator = QLabel("ONLINE")
        self.status_indicator.setObjectName("StatusIndicator")
        left_layout.addWidget(self.status_indicator)

        self.engine_panel = StatusPanel("VOICE CORE", "READY")
        self.mode_panel = StatusPanel("GOD MODE", "HYBRID")
        self.sync_panel = StatusPanel("MEMORY", "SYNCED")

        right = QFrame()
        right.setObjectName("TopStrip")
        right_layout = QHBoxLayout(right)
        right_layout.setContentsMargins(12, 8, 12, 8)
        right_layout.setSpacing(10)

        self.clock_label = QLabel()
        self.clock_label.setObjectName("ClockLabel")
        self.battery_label = QLabel("PWR --")
        self.battery_label.setObjectName("BatteryLabel")
        self.day_label = QLabel()
        self.day_label.setObjectName("BatteryLabel")

        self.minimize_button = QPushButton("_")
        self.minimize_button.setObjectName("WindowButton")
        self.minimize_button.clicked.connect(self.showMinimized)

        self.close_button = QPushButton("X")
        self.close_button.setObjectName("WindowButton")
        self.close_button.clicked.connect(self.close)

        for widget in (
            self.clock_label,
            self.battery_label,
            self.day_label,
            self.minimize_button,
            self.close_button,
        ):
            right_layout.addWidget(widget)

        row.addWidget(left, 28)
        row.addWidget(self.engine_panel, 11)
        row.addWidget(self.mode_panel, 11)
        row.addWidget(self.sync_panel, 11)
        row.addWidget(right, 22)
        return row

    def _build_sidebar(self):
        self.sidebar = QFrame()
        self.sidebar.setObjectName("HudPanel")
        layout = QVBoxLayout(self.sidebar)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        side_title = QLabel("COMMAND RAIL")
        side_title.setObjectName("SectionMiniTitle")
        layout.addWidget(side_title)

        self.quick_buttons = []
        quick_grid = QGridLayout()
        quick_grid.setHorizontalSpacing(8)
        quick_grid.setVerticalSpacing(8)
        quick_actions = [
            ("WEB", "Chrome", "open chrome", "Open Chrome"),
            ("IDE", "VS Code", "open vs code", "Open VS Code"),
            ("CAP", "Shot", "take screenshot", "Take screenshot"),
            ("VOL", "Volume", "volume up", "Volume up"),
            ("WA", "WhatsApp", "send whatsapp message Rahul hello bro", "Send WhatsApp Message"),
            ("MEM", "Memory", "what do you know about me", "Show Memory"),
            ("DIR", "Files", "open downloads", "Open Downloads"),
            ("PWR", "Lock", "lock screen", "Lock screen"),
            ("MED", "YouTube", "play Kesariya song", "Play Song"),
            ("NET", "NetCtrl", "open netcontrol dashboard", "Open NetControl Dashboard"),
        ]
        for index, (icon_text, title_text, command, tooltip) in enumerate(quick_actions):
            button = QuickActionButton(icon_text, title_text, command, tooltip)
            button.clicked.connect(self._handle_quick_action)
            quick_grid.addWidget(button, index // 2, index % 2)
            self.quick_buttons.append(button)
        layout.addLayout(quick_grid)

        info = QFrame()
        info.setObjectName("InfoCard")
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(12, 12, 12, 12)
        info_layout.setSpacing(8)

        info_title = QLabel("READY PATHS")
        info_title.setObjectName("InfoCardTitle")
        info_layout.addWidget(info_title)

        for text in (
            "Continuous listening active",
            "Say stop listening to pause",
            "Quick rail commands directly routed",
        ):
            label = QLabel(text)
            label.setObjectName("SidebarNote")
            label.setWordWrap(True)
            info_layout.addWidget(label)

        info_value = QLabel("VOICE | WEB | FILES | SYSTEM")
        info_value.setObjectName("InfoCardValue")
        info_layout.addWidget(info_value)

        layout.addWidget(info)
        layout.addStretch()
        return self.sidebar

    def _build_center_zone(self):
        self.center_panel = QFrame()
        self.center_panel.setObjectName("HudPanel")
        layout = QVBoxLayout(self.center_panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)

        title_wrap = QVBoxLayout()
        title_wrap.setSpacing(3)
        self.center_kicker = QLabel("AI CORE")
        self.center_kicker.setObjectName("SectionMiniTitle")
        self.center_title = QLabel("TACTICAL ASSISTANT INTERFACE")
        self.center_title.setObjectName("HeroTitle")
        self.center_body = QLabel(
            "Voice control, desktop automation, live diagnostics, memory recall, messaging, and visual tools in one operational dashboard."
        )
        self.center_body.setObjectName("BodyLabel")
        self.center_body.setWordWrap(True)
        title_wrap.addWidget(self.center_kicker)
        title_wrap.addWidget(self.center_title)
        title_wrap.addWidget(self.center_body)

        self.notification_banner = QLabel("Standing by, Boss.")
        self.notification_banner.setObjectName("InfoBanner")
        self.notification_banner.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        title_row.addLayout(title_wrap, 7)
        title_row.addWidget(self.notification_banner, 4)
        layout.addLayout(title_row)

        core_row = QHBoxLayout()
        core_row.setSpacing(10)

        core_left = QFrame()
        core_left.setObjectName("InnerPanel")
        left_layout = QVBoxLayout(core_left)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)

        network_title = QLabel("NETWORK")
        network_title.setObjectName("SectionMiniTitle")
        self.network_status_label = QLabel("IP // --")
        self.network_status_label.setObjectName("MetricText")
        self.net_upload_label = QLabel("UPLOAD // --")
        self.net_upload_label.setObjectName("MetricText")
        self.net_download_label = QLabel("DOWNLOAD // --")
        self.net_download_label.setObjectName("MetricText")
        self.activity_indicator = QLabel("Voice Activity: Standby")
        self.activity_indicator.setObjectName("ActivityLabel")
        left_layout.addWidget(network_title)
        left_layout.addWidget(self.network_status_label)
        left_layout.addWidget(self.net_upload_label)
        left_layout.addWidget(self.net_download_label)
        left_layout.addStretch()
        left_layout.addWidget(self.activity_indicator)

        core_mid = QFrame()
        core_mid.setObjectName("CenterCorePanel")
        mid_layout = QVBoxLayout(core_mid)
        mid_layout.setContentsMargins(8, 8, 8, 8)
        mid_layout.setSpacing(8)

        self.face_widget = HudFaceWidget()
        self.face_widget.setMinimumHeight(420)

        reactor_row = QHBoxLayout()
        reactor_row.setSpacing(12)

        self.mic_shell = QFrame()
        self.mic_shell.setObjectName("InnerPanel")
        mic_layout = QVBoxLayout(self.mic_shell)
        mic_layout.setContentsMargins(10, 10, 10, 10)
        mic_layout.setSpacing(10)

        self.mic_core = QFrame()
        self.mic_core.setObjectName("MicCore")
        self.mic_core.setFixedSize(210, 210)
        self.mic_glow = apply_glow(self.mic_core, "#4de0ff", 42)
        mic_core_layout = QVBoxLayout(self.mic_core)
        mic_core_layout.setContentsMargins(10, 10, 10, 10)
        mic_core_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.jarvis_logo = JarvisCoreWidget(self.mic_core)
        mic_core_layout.addWidget(self.jarvis_logo, alignment=Qt.AlignmentFlag.AlignCenter)

        self.wave_panel = QFrame()
        self.wave_panel.setObjectName("WavePanel")
        wave_layout = QHBoxLayout(self.wave_panel)
        wave_layout.setContentsMargins(14, 12, 14, 12)
        wave_layout.setSpacing(8)
        self.wave_bars = []
        for object_name in ("WaveBar1", "WaveBar2", "WaveBar3", "WaveBar4", "WaveBar5"):
            bar = QFrame()
            bar.setObjectName(object_name)
            bar.setFixedWidth(12)
            bar.setFixedHeight(18)
            wave_layout.addWidget(bar, alignment=Qt.AlignmentFlag.AlignBottom)
            self.wave_bars.append(bar)

        self.wake_hint = QLabel("Continuous listening is active")
        self.wake_hint.setObjectName("WakeHint")

        mic_layout.addWidget(self.mic_core, alignment=Qt.AlignmentFlag.AlignCenter)
        mic_layout.addWidget(self.wave_panel)
        mic_layout.addWidget(self.wake_hint)

        self.telemetry_panel = QFrame()
        self.telemetry_panel.setObjectName("InnerPanel")
        telemetry_layout = QGridLayout(self.telemetry_panel)
        telemetry_layout.setContentsMargins(10, 10, 10, 10)
        telemetry_layout.setSpacing(8)

        self.signal_chip = QLabel("SIGNAL STABLE")
        self.signal_chip.setObjectName("TelemetryChip")
        self.input_chip = QLabel("INPUT // VOICE + TEXT")
        self.input_chip.setObjectName("TelemetryChip")
        self.reply_chip = QLabel("REPLY // NATURAL")
        self.reply_chip.setObjectName("TelemetryChip")
        self.session_chip = QLabel("SESSION // BOSS MODE")
        self.session_chip.setObjectName("TelemetryChip")
        self.history_state_label = QLabel("State: Standby")
        self.history_state_label.setObjectName("TelemetryChip")
        self.history_count_label = QLabel("Messages: 0")
        self.history_count_label.setObjectName("TelemetryChip")

        chips = [
            self.signal_chip,
            self.input_chip,
            self.reply_chip,
            self.session_chip,
            self.history_state_label,
            self.history_count_label,
        ]
        for index, chip in enumerate(chips):
            telemetry_layout.addWidget(chip, index // 2, index % 2)

        reactor_row.addWidget(self.mic_shell, 4)
        reactor_row.addWidget(self.telemetry_panel, 5)

        mid_layout.addWidget(self.face_widget, 1)
        mid_layout.addLayout(reactor_row)

        core_right = QFrame()
        core_right.setObjectName("InnerPanel")
        right_layout = QVBoxLayout(core_right)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(10)

        system_title = QLabel("SYSTEM")
        system_title.setObjectName("SectionMiniTitle")
        right_layout.addWidget(system_title)

        self.cpu_label = QLabel("CPU // 0%")
        self.cpu_label.setObjectName("MetricText")
        self.cpu_bar = self._make_progress()
        self.ram_label = QLabel("RAM // 0%")
        self.ram_label.setObjectName("MetricText")
        self.ram_bar = self._make_progress()
        self.disk_label = QLabel("DISK // 0%")
        self.disk_label.setObjectName("MetricText")
        self.disk_bar = self._make_progress()
        for widget in (
            self.cpu_label,
            self.cpu_bar,
            self.ram_label,
            self.ram_bar,
            self.disk_label,
            self.disk_bar,
        ):
            right_layout.addWidget(widget)

        self.system_time_label = QLabel("--")
        self.system_time_label.setObjectName("MetricText")
        self.weather_label = QLabel("Environment // Stable")
        self.weather_label.setObjectName("MetricText")
        self.sync_label = QLabel("Data Link // Active")
        self.sync_label.setObjectName("MetricText")
        self.ai_status_label = QLabel("AI Brain // LOCAL [OFFLINE SAFE]")
        self.ai_status_label.setObjectName("MetricText")
        self.task_status_label = QLabel("Task Monitor // Standby")
        self.task_status_label.setObjectName("MetricText")
        right_layout.addWidget(self.system_time_label)
        right_layout.addWidget(self.weather_label)
        right_layout.addWidget(self.sync_label)
        right_layout.addWidget(self.ai_status_label)
        right_layout.addWidget(self.task_status_label)

        self.camera_feed = CameraFeedWidget()
        self.camera_feed.setMinimumHeight(280)
        right_layout.addWidget(self.camera_feed, 1)

        center_actions = QHBoxLayout()
        center_actions.setSpacing(8)
        self.listen_button = QPushButton("Listening On")
        self.listen_button.setObjectName("PrimaryButton")
        self.listen_button.clicked.connect(self.listen_requested.emit)
        self.secondary_clear_button = QPushButton("Clear Chat")
        self.secondary_clear_button.setObjectName("SecondaryButton")
        center_actions.addWidget(self.listen_button)
        center_actions.addWidget(self.secondary_clear_button)
        right_layout.addLayout(center_actions)

        core_row.addWidget(core_left, 14)
        core_row.addWidget(core_mid, 54)
        core_row.addWidget(core_right, 22)
        layout.addLayout(core_row, 1)
        return self.center_panel

    def _build_right_panel(self):
        self.chat_panel = QFrame()
        self.chat_panel.setObjectName("HudPanel")
        layout = QVBoxLayout(self.chat_panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(10)

        left_col = QVBoxLayout()
        left_col.setSpacing(2)
        self.chat_title = QLabel("CONVERSATION DOCK")
        self.chat_title.setObjectName("SectionTitle")
        self.chat_subtitle = QLabel("Live response timeline")
        self.chat_subtitle.setObjectName("BodyLabel")
        left_col.addWidget(self.chat_title)
        left_col.addWidget(self.chat_subtitle)

        toggles = QVBoxLayout()
        toggles.setSpacing(6)
        self.top_pin_checkbox = QCheckBox("Always On Top")
        self.top_pin_checkbox.toggled.connect(self._toggle_on_top)
        self.mini_mode_checkbox = QCheckBox("Mini Mode")
        self.mini_mode_checkbox.toggled.connect(self._toggle_mini_mode)
        toggles.addWidget(self.top_pin_checkbox)
        toggles.addWidget(self.mini_mode_checkbox)

        top.addLayout(left_col, 1)
        top.addLayout(toggles)
        layout.addLayout(top)

        self.history_hint = QLabel("No conversation yet. Speak or type below.")
        self.history_hint.setObjectName("HistoryHint")
        layout.addWidget(self.history_hint)

        mid = QHBoxLayout()
        mid.setSpacing(10)

        self.history_list = QListWidget()
        self.history_list.setObjectName("HistoryList")
        self.history_list.setSpacing(8)
        self.history_list.setUniformItemSizes(False)
        self.history_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.history_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.history_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.history_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.history_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.history_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.history_list.setMinimumWidth(360)

        diagnostics_row = QHBoxLayout()
        diagnostics_row.setSpacing(10)

        self.radar_panel = QFrame()
        self.radar_panel.setObjectName("InnerPanel")
        radar_layout = QVBoxLayout(self.radar_panel)
        radar_layout.setContentsMargins(10, 10, 10, 10)
        radar_layout.setSpacing(8)
        radar_title = QLabel("TARGET RADAR")
        radar_title.setObjectName("SectionMiniTitle")
        self.radar_widget = RadarWidget()
        self.radar_widget.setMinimumSize(240, 240)
        self.radar_widget.set_activity("System standby")
        radar_layout.addWidget(radar_title)
        radar_layout.addWidget(self.radar_widget, 1)

        self.scan_panel = QFrame()
        self.scan_panel.setObjectName("InnerPanel")
        scan_layout = QVBoxLayout(self.scan_panel)
        scan_layout.setContentsMargins(10, 10, 10, 10)
        scan_layout.setSpacing(8)
        scan_title = QLabel("BODY SCAN")
        scan_title.setObjectName("SectionMiniTitle")
        self.scan_widget = BodyScanWidget()
        self.scan_widget.setMinimumHeight(240)
        self.scan_widget.update_metrics(0, 0, 0, 0)
        self.scan_widget.set_summary("System nominal")
        scan_layout.addWidget(scan_title)
        scan_layout.addWidget(self.scan_widget, 1)

        diagnostics_row.addWidget(self.radar_panel, 1)
        diagnostics_row.addWidget(self.scan_panel, 1)

        mid.addWidget(self.history_list, 1)
        layout.addLayout(mid, 1)
        layout.addLayout(diagnostics_row)
        return self.chat_panel

    def _build_footer_bar(self):
        footer = QFrame()
        footer.setObjectName("FooterBar")
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        self.input_field = QLineEdit()
        self.input_field.setObjectName("CommandInput")
        self.input_field.setPlaceholderText("Talk to MYRA... e.g. open chrome, what do you know about me, send whatsapp message Rahul hello")
        self.input_field.returnPressed.connect(self._submit_input)

        self.send_button = QPushButton("EXECUTE")
        self.send_button.setObjectName("PrimaryButton")
        self.send_button.clicked.connect(self._submit_input)

        self.clear_button = QPushButton("CLEAR")
        self.clear_button.setObjectName("SecondaryButton")
        self.clear_button.clicked.connect(self._clear_history)

        self.mic_toggle_button = QPushButton("LISTEN")
        self.mic_toggle_button.setObjectName("SecondaryButton")
        self.mic_toggle_button.clicked.connect(self.listen_requested.emit)

        layout.addWidget(self.input_field, 1)
        layout.addWidget(self.send_button)
        layout.addWidget(self.clear_button)
        layout.addWidget(self.mic_toggle_button)
        return footer

    def _make_progress(self):
        progress = QProgressBar()
        progress.setObjectName("MetricBar")
        progress.setRange(0, 100)
        progress.setValue(0)
        progress.setTextVisible(False)
        progress.setFixedHeight(10)
        return progress

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
        self._refresh_history_item_sizes()
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
        self.mode_panel.set_value("MINI" if enabled else "DASHBOARD")

        if enabled:
            self.resize(420, 360)
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
            self.face_widget.hide()
            self.wave_panel.hide()
            self.telemetry_panel.hide()
            self.secondary_clear_button.hide()
            self.footer_bar.hide()
            self.show()
        else:
            self.resize(1520, 860)
            self.sidebar.show()
            self.chat_panel.show()
            self.engine_panel.show()
            self.mode_panel.show()
            self.sync_panel.show()
            self.center_kicker.show()
            self.center_title.show()
            self.center_body.show()
            self.notification_banner.show()
            self.face_widget.show()
            self.wave_panel.show()
            self.telemetry_panel.show()
            self.secondary_clear_button.show()
            self.footer_bar.show()
            if not self.top_pin_checkbox.isChecked():
                self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
            self.show()

    def _update_clock(self):
        now = datetime.now()
        self.clock_label.setText(now.strftime("%I:%M:%S %p"))
        self.day_label.setText(now.strftime("%d %b %Y"))
        self.system_time_label.setText(now.strftime("Time // %A %I:%M %p"))

    def _update_system_metrics(self):
        try:
            import psutil
        except ImportError:
            self.battery_label.setText("PWR --")
            self.scan_widget.update_metrics(0, 0, 0, 0)
            return

        battery = psutil.sensors_battery()
        battery_percent = int(battery.percent) if battery is not None else 0
        if battery is not None:
            self.battery_label.setText(f"PWR {battery_percent}%")
        else:
            self.battery_label.setText("PWR --")

        cpu = int(psutil.cpu_percent(interval=None))
        ram = int(psutil.virtual_memory().percent)
        disk = int(psutil.disk_usage("C:\\").percent)

        self.cpu_label.setText(f"CPU // {cpu}%")
        self.ram_label.setText(f"RAM // {ram}%")
        self.disk_label.setText(f"DISK // {disk}%")
        self.cpu_bar.setValue(cpu)
        self.ram_bar.setValue(ram)
        self.disk_bar.setValue(disk)
        self.scan_widget.update_metrics(cpu, ram, disk, battery_percent)
        self.scan_widget.set_summary(self._build_scan_summary(cpu, ram, disk, battery_percent))

    def _update_network_info(self):
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
        except Exception:
            ip = "--"

        self.network_status_label.setText(f"IP // {ip}")
        self.radar_widget.set_activity(f"IP {ip}")

        try:
            import psutil
        except ImportError:
            self.net_upload_label.setText("UPLOAD // --")
            self.net_download_label.setText("DOWNLOAD // --")
            return

        counters = psutil.net_io_counters()
        self.net_upload_label.setText(f"UPLOAD // {self._format_bytes(counters.bytes_sent)}")
        self.net_download_label.setText(f"DOWNLOAD // {self._format_bytes(counters.bytes_recv)}")

    def _format_bytes(self, value):
        units = ["B", "KB", "MB", "GB", "TB"]
        amount = float(value)
        for unit in units:
            if amount < 1024 or unit == units[-1]:
                return f"{amount:.1f} {unit}"
            amount /= 1024
        return f"{amount:.1f} TB"

    def _animate_state(self):
        self._glow_tick = (self._glow_tick + 1) % 6
        base_patterns = {
            "online": ([22, 18, 14, 18, 22], "#8db2c9", 28),
            "listening": ([24, 42, 62, 42, 24], "#56ebff", 48),
            "processing": ([32, 24, 18, 24, 32], "#9aa9ff", 52),
            "speaking": ([18, 34, 48, 34, 18], "#75ffda", 42),
            "error": ([18, 18, 18, 18, 18], "#ff6b82", 40),
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
            "online": ("ONLINE", "online", "READY"),
            "listening": ("LISTENING", "listening", "LISTENING"),
            "processing": ("PROCESSING", "processing", "THINKING"),
            "speaking": ("SPEAKING", "speaking", "RESPONDING"),
            "error": ("ERROR", "error", "ATTENTION"),
        }
        key = status.lower()
        label, mode, engine_value = mapping.get(key, (status.upper(), "online", "READY"))
        self.status_indicator.setText(label)
        self.status_indicator.setProperty("state", mode)
        self.status_indicator.style().unpolish(self.status_indicator)
        self.status_indicator.style().polish(self.status_indicator)
        self._status_mode = mode

        self.mic_core.setProperty("state", mode)
        self.mic_core.style().unpolish(self.mic_core)
        self.mic_core.style().polish(self.mic_core)
        self.jarvis_logo.set_state(mode)
        self.face_widget.set_state(mode)
        self.radar_widget.set_state(mode)
        self.scan_widget.set_state(mode)
        self.listen_button.setProperty("state", mode)
        self.listen_button.style().unpolish(self.listen_button)
        self.listen_button.style().polish(self.listen_button)
        self.engine_panel.set_value(engine_value)
        self.history_state_label.setText(f"State: {label.title()}")

        if mode == "listening":
            self.listen_button.setText("Listening")
            self.mic_toggle_button.setText("LISTEN ON")
            self.notification_banner.setText("Boss, main continuously sun rahi hoon. Seedha command bolo.")
            self.activity_indicator.setText("Voice Activity: Capturing audio")
            self.signal_chip.setText("SIGNAL LIVE")
            self.radar_widget.set_activity("Voice lock active")
        elif mode == "processing":
            self.listen_button.setText("Processing")
            self.mic_toggle_button.setText("LISTEN ON")
            self.notification_banner.setText("Boss, request process kar rahi hoon.")
            self.activity_indicator.setText("Voice Activity: Analyzing command")
            self.signal_chip.setText("SIGNAL ANALYZING")
            self.radar_widget.set_activity("Intent analysis")
        elif mode == "speaking":
            self.listen_button.setText("Speaking")
            self.mic_toggle_button.setText("LISTEN ON")
            self.notification_banner.setText("Boss, reply ready hai.")
            self.activity_indicator.setText("Voice Activity: Delivering response")
            self.signal_chip.setText("SIGNAL OUTPUT")
            self.radar_widget.set_activity("Response output")
        elif mode == "error":
            self.listen_button.setText("Retry")
            self.mic_toggle_button.setText("LISTEN")
            self.notification_banner.setText("Boss, ek issue aa gaya hai. Check karte hain.")
            self.activity_indicator.setText("Voice Activity: Error state")
            self.signal_chip.setText("SIGNAL ALERT")
            self.radar_widget.set_activity("Error alert")
        else:
            self.listen_button.setText("Resume Listening")
            self.mic_toggle_button.setText("LISTEN")
            self.notification_banner.setText("Listening paused, Boss.")
            self.activity_indicator.setText("Voice Activity: Paused")
            self.signal_chip.setText("SIGNAL STABLE")
            self.radar_widget.set_activity("System standby")

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
        self._refresh_history_item_sizes()
        self.history_list.scrollToBottom()
        self._message_count += 1
        self.history_count_label.setText(f"Messages: {self._message_count}")
        self.history_hint.hide()
        self._update_diagnostics_from_message(role, message)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_history_item_sizes()

    def _refresh_history_item_sizes(self):
        viewport_width = self.history_list.viewport().width()
        if viewport_width <= 0:
            return
        for index in range(self.history_list.count()):
            item = self.history_list.item(index)
            widget = self.history_list.itemWidget(item)
            if widget is None:
                continue
            widget.setFixedWidth(max(240, viewport_width - 18))
            item.setSizeHint(widget.sizeHint())

    def show_notification(self, message, level="info"):
        self.notification_banner.setText(message)
        self.notification_banner.setProperty("level", level)
        self.notification_banner.style().unpolish(self.notification_banner)
        self.notification_banner.style().polish(self.notification_banner)
        if level == "error":
            self.set_status("Error")
        self.tray.showMessage("Myra", message, QSystemTrayIcon.MessageIcon.Information, 2500)

    def update_camera_frame(self, image_path="", status_text=""):
        self.camera_feed.set_frame(image_path, status_text)

    def update_core_snapshot(self, snapshot):
        payload = snapshot if isinstance(snapshot, dict) else {}
        model = str(payload.get("active_model", "local")).upper()
        route = str(payload.get("route", "offline-safe")).replace("-", " ").upper()
        task = str(payload.get("task_status", "Standby")).strip()
        agent = str(payload.get("active_agent", "brain")).strip().title()
        memory_status = str(payload.get("memory_status", "SYNCED")).upper()
        voice_status = str(payload.get("voice_status", "READY")).upper()
        emotion_voice = str(payload.get("emotion_voice", "neutral")).upper()

        self.mode_panel.set_value(f"{agent}::{model}")
        self.sync_panel.set_value(memory_status)
        self.ai_status_label.setText(f"AI Brain // {model} [{route}]")
        self.task_status_label.setText(f"Task Monitor // {task[:52]}")
        self.chat_subtitle.setText(f"Live response timeline // Agent {agent} // Voice {emotion_voice}")
        self.signal_chip.setText(f"SIGNAL {voice_status[:10]}")

    def handle_dashboard_action(self, action):
        key = str(action).lower().strip()
        if key == "radar_status":
            self.radar_widget.set_activity("Manual radar review")
            self.radar_widget.update_targets(
                [
                    {"angle": 28, "distance": 0.34, "strength": 0.95},
                    {"angle": 146, "distance": 0.62, "strength": 0.52},
                ],
                "Radar status live",
            )
            self.notification_banner.setText("Boss, target radar active view me hai.")
            return

        if key == "body_scan":
            self.scan_widget.set_focus_metric("battery")
            self.scan_widget.set_summary("Body scan focus active")
            self.notification_banner.setText("Boss, body scan panel highlight kar diya hai.")
            return

        if key == "system_scan":
            self.scan_widget.set_focus_metric("cpu")
            self.scan_widget.set_summary("System scan in progress")
            self.radar_widget.update_targets(
                [
                    {"angle": 12, "distance": 0.32, "strength": 0.98},
                    {"angle": 92, "distance": 0.55, "strength": 0.68},
                    {"angle": 244, "distance": 0.74, "strength": 0.46},
                ],
                "System diagnostic",
            )
            self.notification_banner.setText("Boss, system diagnostic scan active hai.")
            return

    def _update_diagnostics_from_message(self, role, message):
        text = " ".join(str(message).lower().split())
        if not text:
            return

        if role == "user":
            targets, activity, focus_metric = self._diagnostic_profile_for_command(text)
            self.radar_widget.update_targets(targets, activity)
            if focus_metric:
                self.scan_widget.set_focus_metric(focus_metric)
        else:
            self.radar_widget.pulse_ping("Reply delivered")

    def _diagnostic_profile_for_command(self, text):
        profiles = [
            (("battery",), [{"angle": 86, "distance": 0.44, "strength": 0.92}], "Battery query", "battery"),
            (("cpu",), [{"angle": 20, "distance": 0.34, "strength": 0.95}], "CPU scan", "cpu"),
            (("ram", "memory"), [{"angle": 160, "distance": 0.5, "strength": 0.88}], "RAM scan", "ram"),
            (("disk", "storage"), [{"angle": 238, "distance": 0.58, "strength": 0.82}], "Disk scan", "disk"),
            (("internet", "wifi", "network", "netcontrol", "focus mode", "block site", "logs"), [{"angle": 318, "distance": 0.72, "strength": 0.76}], "Network trace", "cpu"),
            (("whatsapp", "message", "call"), [{"angle": 128, "distance": 0.62, "strength": 0.9}], "Comms target", "battery"),
            (("youtube", "play", "song", "music"), [{"angle": 300, "distance": 0.4, "strength": 0.86}], "Media lock", "ram"),
            (("screenshot",), [{"angle": 44, "distance": 0.26, "strength": 1.0}], "Screen capture", "disk"),
            (("downloads", "desktop", "documents", "folder", "file"), [{"angle": 210, "distance": 0.66, "strength": 0.74}], "File path scan", "disk"),
            (("volume", "awaz", "sound"), [{"angle": 12, "distance": 0.52, "strength": 0.84}], "Audio control", "cpu"),
            (("brightness", "light"), [{"angle": 348, "distance": 0.46, "strength": 0.84}], "Display control", "battery"),
        ]
        for keywords, targets, activity, focus_metric in profiles:
            if any(token in text for token in keywords):
                return targets, activity, focus_metric
        return [{"angle": 42, "distance": 0.48, "strength": 0.55}], "General command", "cpu"

    def _build_scan_summary(self, cpu, ram, disk, battery):
        levels = [
            ("CPU HIGH" if cpu >= 85 else ""),
            ("RAM HIGH" if ram >= 85 else ""),
            ("DISK HIGH" if disk >= 90 else ""),
            ("BATTERY LOW" if 0 < battery <= 20 else ""),
        ]
        active = [item for item in levels if item]
        if active:
            return " | ".join(active[:2])
        return "System nominal"

    def load_theme(self):
        theme_path = Path(__file__).resolve().parent / "theme.qss"
        self.setStyleSheet(theme_path.read_text(encoding="utf-8"))
