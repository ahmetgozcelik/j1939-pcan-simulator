"""Main window: message list, center editor, detail panel, log dock, toolbar."""

from __future__ import annotations

import functools
import traceback
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QAction,
    QDockWidget,
    QFileDialog,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QToolBar,
    QToolButton,
)

from j1939_pcan_simulator.config import workspace as cfg
from j1939_pcan_simulator.transport.can_bus import PCanInterface
from j1939_pcan_simulator.config.workspace import (
    AdapterSettings,
    DEFAULT_CONFIG,
    ConfigIOWorker,
    DM1Config,
    Message,
    Workspace,
    workspace_to_dict,
)
from j1939_pcan_simulator.gui.dm1_panel import DM1Panel
from j1939_pcan_simulator.gui.icons import hmi_icon
from j1939_pcan_simulator.gui.log_panel import LogPanel
from j1939_pcan_simulator.gui.message_panel import MessagePanel
from j1939_pcan_simulator.gui.signal_detail import SignalDetail
from j1939_pcan_simulator.gui.signal_panel import SignalPanel
from j1939_pcan_simulator.gui.validation_panel import ValidationPanel
from j1939_pcan_simulator.simulation.engine import DM1State, SimulatorEngine
from j1939_pcan_simulator.validation.workspace import ValidationIssue, validate_workspace


def safe_action(fn):
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        try:
            return fn(self, *args, **kwargs)
        except Exception:
            tb = traceback.format_exc()
            try:
                self._report_error(f"{fn.__qualname__}:\n{tb}")
            except Exception:
                import sys
                sys.__stderr__.write(tb)
    return wrapper


def validation_status_text(workspace: Workspace) -> str:
    issues = validate_workspace(workspace)
    errors = sum(1 for issue in issues if issue.severity == "error")
    warnings = sum(1 for issue in issues if issue.severity == "warning")
    if errors:
        return f"Validation: {errors} error(s), {warnings} warning(s)"
    if warnings:
        return f"Validation: OK, {warnings} warning(s)"
    return "Validation: OK"


class MainWindow(QMainWindow):
    def __init__(self, reporter=None):
        super().__init__()
        self.setWindowTitle("J1939 PCAN Simulator")
        self.resize(1700, 900)

        self._reporter = reporter
        self.workspace: Workspace = Workspace()
        self.current_path: Optional[str] = None
        self.adapter_settings = cfg.load_adapter_settings()

        self.pcan = PCanInterface(
            backend=self.adapter_settings.backend,
            channel=self.adapter_settings.channel,
            bitrate=self.adapter_settings.bitrate,
        )
        self.pcan.start()
        self.engine = SimulatorEngine(self.pcan)

        self.io_worker = ConfigIOWorker()
        self.io_worker.start()

        self._build_panels()
        self._build_menus()
        self._build_toolbar()
        self._build_status_bar()
        self._apply_adapter_settings_to_ui()
        self._refresh_validation_status()

        self.engine.frame_sent.connect(self.log_panel.append_frame, Qt.QueuedConnection)
        self.engine.frame_sent.connect(self._on_frame_sent_refresh_panels, Qt.QueuedConnection)
        self.engine.error_logged.connect(self._on_engine_error, Qt.QueuedConnection)
        self.engine.frame_send_error.connect(self.log_panel.send_error, Qt.QueuedConnection)
        self.pcan.connection_changed.connect(self._on_connection_changed, Qt.QueuedConnection)

        if self._reporter is not None:
            self._reporter.error_logged.connect(self.log_panel.error, Qt.QueuedConnection)

        self.io_worker.loaded.connect(self._on_loaded, Qt.QueuedConnection)
        self.io_worker.saved.connect(self._on_saved, Qt.QueuedConnection)
        self.io_worker.failed.connect(self._on_io_failed, Qt.QueuedConnection)

        self.message_panel.message_selected.connect(self._on_message_selected)
        self.message_panel.workspace_modified.connect(self._on_workspace_modified)
        self.message_panel.request_start_all.connect(self._start_active)
        self.message_panel.request_stop_all.connect(self._stop_all)
        self.message_panel.request_active_changed.connect(self._on_active_changed)
        self.message_panel.request_reconnect.connect(self._reconnect)

        self.signal_panel.signal_selected.connect(self._on_signal_selected)
        self.signal_panel.message_modified.connect(self._on_workspace_modified)

        self.signal_detail.signal_modified.connect(self._on_signal_detail_changed)
        self.validation_panel.issue_activated.connect(self._focus_validation_issue)

        self._kickoff_initial_load()
        self.pcan.request_connect.emit()

    def _report_error(self, message: str) -> None:
        if self._reporter is not None:
            self._reporter.error_logged.emit(message)
        else:
            try:
                self.log_panel.error(message)
            except Exception:
                pass

    def _build_panels(self) -> None:
        self.message_panel = MessagePanel()
        self.signal_panel = SignalPanel()
        self.dm1_panel = DM1Panel(self.engine)
        self.signal_detail = SignalDetail()

        self.dm1_scroll = QScrollArea()
        self.dm1_scroll.setObjectName("DiagnosticScroll")
        self.dm1_scroll.setWidgetResizable(True)
        self.dm1_scroll.setFrameShape(QScrollArea.NoFrame)
        self.dm1_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.dm1_scroll.setWidget(self.dm1_panel)

        self.center_stack = QStackedWidget()
        self.center_stack.addWidget(self.signal_panel)  # 0
        self.center_stack.addWidget(self.dm1_scroll)    # 1
        self.message_panel.setMinimumWidth(620)
        self.center_stack.setMinimumWidth(480)
        self.signal_detail.setMinimumWidth(500)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setObjectName("WorkspaceSplitter")
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setOpaqueResize(True)
        self.splitter.setHandleWidth(10)
        self.splitter.addWidget(self.message_panel)
        self.splitter.addWidget(self.center_stack)
        self.splitter.addWidget(self.signal_detail)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 3)
        self.splitter.setStretchFactor(2, 3)
        self.splitter.setSizes([760, 560, 620])

        self.setCentralWidget(self.splitter)

        self.log_panel = LogPanel()
        self.log_dock = QDockWidget("Log", self)
        self.log_dock.setObjectName("LogDock")
        self.log_dock.setWidget(self.log_panel)
        self.log_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)

        self.validation_panel = ValidationPanel()
        self.validation_dock = QDockWidget("Validation", self)
        self.validation_dock.setObjectName("ValidationDock")
        self.validation_dock.setWidget(self.validation_panel)
        self.validation_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.validation_dock)
        self.tabifyDockWidget(self.log_dock, self.validation_dock)
        self.log_dock.raise_()

    def _build_menus(self) -> None:
        self.view_menu = self.menuBar().addMenu("View")
        self.panels_menu = self.view_menu.addMenu("Panels")

        self.act_show_log = self.log_dock.toggleViewAction()
        self.act_show_log.setText("Frame Log")
        self.act_show_log.setToolTip("Show the frame log panel")
        self.panels_menu.addAction(self.act_show_log)

        self.act_show_validation = self.validation_dock.toggleViewAction()
        self.act_show_validation.setText("Validation Issues")
        self.act_show_validation.setToolTip("Show workspace validation details")
        self.panels_menu.addAction(self.act_show_validation)

        self.panels_menu.addSeparator()
        self.act_reset_layout = QAction("Reset Layout", self)
        self.act_reset_layout.setToolTip("Restore the default panel layout")
        self.act_reset_layout.triggered.connect(self._reset_layout)
        self.panels_menu.addAction(self.act_reset_layout)
        self.view_menu.addAction(self.act_reset_layout)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main")
        tb.setObjectName("MainToolBar")
        tb.setIconSize(QSize(19, 19))
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        tb.setMovable(False)
        self.addToolBar(tb)

        act_new = QAction("New", self)
        act_new.setIcon(hmi_icon("new"))
        act_new.setShortcut(QKeySequence.New)
        act_new.setToolTip("New configuration")
        act_new.triggered.connect(self._action_new)
        tb.addAction(act_new)

        act_open = QAction("Open...", self)
        act_open.setIcon(hmi_icon("open"))
        act_open.setShortcut(QKeySequence.Open)
        act_open.setToolTip("Open configuration")
        act_open.triggered.connect(self._action_open)
        tb.addAction(act_open)

        act_save = QAction("Save", self)
        act_save.setIcon(hmi_icon("save"))
        act_save.setShortcut(QKeySequence.Save)
        act_save.setToolTip("Save configuration")
        act_save.triggered.connect(self._action_save)
        tb.addAction(act_save)

        act_save_as = QAction("Save As...", self)
        act_save_as.setIcon(hmi_icon("save_as"))
        act_save_as.setToolTip("Save configuration as a new file")
        act_save_as.triggered.connect(self._action_save_as)
        tb.addAction(act_save_as)

        # Recent menu.
        self.recent_btn = QToolButton()
        self.recent_btn.setText("Recent")
        self.recent_btn.setIcon(hmi_icon("recent"))
        self.recent_btn.setToolTip("Open a recent configuration")
        self.recent_btn.setPopupMode(QToolButton.InstantPopup)
        self.recent_menu = QMenu(self.recent_btn)
        self.recent_btn.setMenu(self.recent_menu)
        tb.addWidget(self.recent_btn)
        self._rebuild_recent_menu()

        self.panels_btn = QToolButton()
        self.panels_btn.setText("Panels")
        self.panels_btn.setIcon(hmi_icon("recent"))
        self.panels_btn.setToolTip("Show, hide, or reset dock panels")
        self.panels_btn.setPopupMode(QToolButton.InstantPopup)
        self.panels_btn.setMenu(self.panels_menu)
        tb.addWidget(self.panels_btn)

        tb.addSeparator()

        act_reconnect = QAction("Reconnect PCAN", self)
        act_reconnect.setIcon(hmi_icon("reconnect"))
        act_reconnect.setToolTip("Reconnect selected CAN backend")
        act_reconnect.triggered.connect(self._reconnect)
        tb.addAction(act_reconnect)

    def _build_status_bar(self) -> None:
        self.validation_status_btn = QPushButton("Validation: OK")
        self.validation_status_btn.setObjectName("ValidationStatusButton")
        self.validation_status_btn.setFlat(True)
        self.validation_status_btn.setToolTip("Show validation details")
        self.validation_status_btn.clicked.connect(self._show_validation_dock)
        self.statusBar().addPermanentWidget(self.validation_status_btn, 1)

    def _rebuild_recent_menu(self) -> None:
        self.recent_menu.clear()
        for p in cfg.get_recent_files():
            act = QAction(p, self)
            act.triggered.connect(lambda checked=False, path=p: self._open_path(path))
            self.recent_menu.addAction(act)

    def _show_dock(self, dock: QDockWidget) -> None:
        dock.setFloating(False)
        dock.show()
        dock.raise_()

    def _show_validation_dock(self) -> None:
        self._show_dock(self.validation_dock)

    def _reset_layout(self) -> None:
        self.log_dock.setFloating(False)
        self.validation_dock.setFloating(False)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.validation_dock)
        self.tabifyDockWidget(self.log_dock, self.validation_dock)
        self.log_dock.show()
        self.validation_dock.show()
        self.log_dock.raise_()
        self.splitter.setSizes([760, 560, 620])

    # ------------------------------------------------------------------
    # DM state <-> workspace synchronization.
    # ------------------------------------------------------------------

    def _sync_dm1_states_to_workspace(self) -> None:
        """Copy engine DM state into the workspace before saving."""
        with self.engine.lock:
            for msg in self.workspace.messages:
                if msg.is_diagnostic_dtc():
                    state = self.engine.dm1_states.get(msg.can_id)
                    if state is not None:
                        msg.dm1_config = DM1Config(
                            lamp_status=state.lamp_status,
                            flash_lamp_status=state.flash_lamp_status,
                            lamp_mode=state.lamp_mode,
                            auto_lamp_interval_s=state.auto_lamp_interval_s,
                            fmi=state.fmi,
                            occurrence=state.occurrence,
                            spn=state.spn,
                            spn_mode=state.spn_mode,
                            spn_list=list(state.spn_list),
                            spn_list_interval_s=state.spn_list_interval_s,
                            spn_range_min=state.spn_range_min,
                            spn_range_max=state.spn_range_max,
                            spn_range_interval_s=state.spn_range_interval_s,
                        )

    def _load_dm1_states_from_workspace(self) -> None:
        """Copy workspace DM configs into the engine after loading."""
        for msg in self.workspace.messages:
            if msg.is_diagnostic_dtc() and msg.dm1_config is not None:
                c = msg.dm1_config
                state = DM1State(
                    lamp_status=c.lamp_status,
                    flash_lamp_status=c.flash_lamp_status,
                    lamp_mode=c.lamp_mode,
                    auto_lamp_interval_s=c.auto_lamp_interval_s,
                    fmi=c.fmi,
                    occurrence=c.occurrence,
                    spn=c.spn,
                    spn_mode=c.spn_mode,
                    spn_list=list(c.spn_list),
                    spn_list_interval_s=c.spn_list_interval_s,
                    spn_range_min=c.spn_range_min,
                    spn_range_max=c.spn_range_max,
                    spn_range_interval_s=c.spn_range_interval_s,
                )
                self.engine.set_dm1_state(msg.can_id, state)

    # ------------------------------------------------------------------
    # File actions
    # ------------------------------------------------------------------

    @safe_action
    def _action_new(self, checked=False) -> None:
        backup_path = cfg.save_recovery_backup(
            self.workspace,
            "before_new",
            self.current_path,
        )
        self._stop_all()
        self.workspace = Workspace()
        self.current_path = None
        self._refresh_workspace_ui()
        self._refresh_validation_status()
        if backup_path:
            self.statusBar().showMessage(f"Recovery backup saved: {backup_path}")
        self._set_window_title("untitled")

    @safe_action
    def _action_open(self, checked=False) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Configuration",
            str(Path.home()),
            "JSON Files (*.json);;All Files (*)",
        )
        if path:
            self._open_path(path)

    @safe_action
    def _action_save(self, checked=False) -> None:
        if self.current_path:
            self._save_to(self.current_path)
        else:
            self._action_save_as()

    @safe_action
    def _action_save_as(self, checked=False) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Configuration As",
            str(Path.home() / "j1939_config.json"),
            "JSON Files (*.json);;All Files (*)",
        )
        if path:
            self._save_to(path)

    @safe_action
    def _open_path(self, path: str) -> None:
        cfg.save_recovery_backup(self.workspace, "before_open", self.current_path)
        self.io_worker.request_load.emit(str(Path(path)))

    @safe_action
    def _save_to(self, path: str) -> None:
        # Synchronize DM state into the workspace before saving.
        self._sync_dm1_states_to_workspace()
        ws_dict = workspace_to_dict(self.workspace)
        self.io_worker.request_save.emit(str(Path(path)), ws_dict)
        self.current_path = str(Path(path).resolve())
        self._set_window_title(f"{Path(self.current_path).name} (saving...)")

    # ------------------------------------------------------------------
    # IO worker callbacks
    # ------------------------------------------------------------------

    @safe_action
    def _on_loaded(self, path: str, ws) -> None:
        self._stop_all()
        self.workspace = ws
        self.current_path = str(Path(path).resolve())
        # Apply loaded DM configs to the engine.
        self._load_dm1_states_from_workspace()
        self._refresh_workspace_ui()
        self._refresh_validation_status()
        cfg.remember_path(self.current_path)
        self._rebuild_recent_menu()
        self._set_window_title(Path(self.current_path).name)

    @safe_action
    def _on_saved(self, path: str) -> None:
        self.current_path = str(Path(path).resolve())
        cfg.remember_path(self.current_path)
        self._rebuild_recent_menu()
        self._set_window_title(Path(self.current_path).name)

    @safe_action
    def _on_io_failed(self, op: str, path: str, error: str) -> None:
        msg = f"Config {op} failed: {path}\n{error}"
        self._report_error(msg)
        if op == "load":
            QMessageBox.critical(self, "Load Failed", error)

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    @safe_action
    def _reconnect(self, checked=False) -> None:
        bitrate_map = {
            '125 kbps': 125000,
            '250 kbps': 250000,
            '500 kbps': 500000,
            '1 Mbps': 1000000,
        }
        bitrate = bitrate_map.get(
            self.message_panel.combo_bitrate.currentText(), 250000
        )
        backend = self.message_panel.combo_backend.currentData() or "pcan"
        channel = self.message_panel.combo_channel.currentText()
        self.adapter_settings = AdapterSettings(
            backend=backend,
            channel=channel,
            bitrate=bitrate,
        )
        cfg.save_adapter_settings(self.adapter_settings)
        self.pcan.backend = backend
        self.pcan.bitrate = bitrate
        self.pcan.channel = channel
        self.pcan.request_disconnect.emit()
        self.pcan.request_connect.emit()

    @safe_action
    def _on_connection_changed(self, connected: bool, info: str) -> None:
        self.message_panel.update_connection_status(connected, info)

    def _apply_adapter_settings_to_ui(self) -> None:
        backend_idx = self.message_panel.combo_backend.findData(
            self.adapter_settings.backend
        )
        if backend_idx >= 0:
            self.message_panel.combo_backend.setCurrentIndex(backend_idx)

        channel_idx = self.message_panel.combo_channel.findText(
            self.adapter_settings.channel
        )
        if channel_idx >= 0:
            self.message_panel.combo_channel.setCurrentIndex(channel_idx)

        bitrate_text = {
            125000: "125 kbps",
            250000: "250 kbps",
            500000: "500 kbps",
            1000000: "1 Mbps",
        }.get(self.adapter_settings.bitrate)
        if bitrate_text:
            bitrate_idx = self.message_panel.combo_bitrate.findText(bitrate_text)
            if bitrate_idx >= 0:
                self.message_panel.combo_bitrate.setCurrentIndex(bitrate_idx)

    # ------------------------------------------------------------------
    # Engine control
    # ------------------------------------------------------------------

    @safe_action
    def _start_active(self, checked=False) -> None:
        for msg in self.workspace.messages:
            if msg.active and not self.engine.is_running(msg.can_id):
                self.engine.start_message(msg)

    def _start_all(self, checked=False) -> None:
        self._start_active(checked)

    @safe_action
    def _stop_all(self, checked=False) -> None:
        self.engine.stop_all()

    @safe_action
    def _on_active_changed(self, msg: Message) -> None:
        if msg.active:
            self.engine.start_message(msg)
        else:
            self.engine.stop_message(msg.can_id)

    @safe_action
    def _on_engine_error(self, message: str) -> None:
        self._report_error(message)

    # ------------------------------------------------------------------
    # Selection plumbing
    # ------------------------------------------------------------------

    @safe_action
    def _on_message_selected(self, msg: Optional[Message]) -> None:
        if msg is None:
            self.center_stack.setCurrentWidget(self.signal_panel)
            self.signal_panel.set_message(None)
            self.signal_detail.set_signal(None, None)
            return
        if msg.is_diagnostic_dtc():
            self.dm1_panel.set_message(msg)
            self.center_stack.setCurrentWidget(self.dm1_scroll)
            self.signal_detail.set_signal(msg, None)
        else:
            self.center_stack.setCurrentWidget(self.signal_panel)
            self.signal_panel.set_message(msg)

    @safe_action
    def _on_signal_selected(self, msg, sig) -> None:
        self.signal_detail.set_signal(msg, sig)

    @safe_action
    def _focus_validation_issue(self, issue: ValidationIssue) -> None:
        self._show_validation_dock()
        if issue.message_index is None:
            return
        if not (0 <= issue.message_index < len(self.workspace.messages)):
            return

        self.message_panel.table.selectRow(issue.message_index)
        self.message_panel.table.scrollTo(self.message_panel.model.index(issue.message_index, 0))
        msg = self.workspace.messages[issue.message_index]
        self._on_message_selected(msg)

        if issue.signal_index is None or msg.is_diagnostic_dtc():
            return
        if not (0 <= issue.signal_index < len(msg.signals)):
            return

        self.center_stack.setCurrentWidget(self.signal_panel)
        self.signal_panel.table.selectRow(issue.signal_index)
        self.signal_panel.table.scrollTo(self.signal_panel.model.index(issue.signal_index, 0))
        self.signal_detail.set_signal(msg, msg.signals[issue.signal_index])

    @safe_action
    def _on_signal_detail_changed(self) -> None:
        self.signal_panel.refresh()
        self._on_workspace_modified()

    @safe_action
    def _on_workspace_modified(self) -> None:
        if self.current_path:
            self._set_window_title(f"{Path(self.current_path).name} *")
        self._refresh_validation_status()

    @safe_action
    def _on_frame_sent_refresh_panels(self, ts, can_id, data, decoded, sent_ok) -> None:
        sel = self.message_panel.selected_message()
        if sel is not None and sel.can_id == can_id and not sel.is_diagnostic_dtc():
            self.signal_panel.refresh()
            self.signal_panel.flash_value_cells()

    # ------------------------------------------------------------------
    # Workspace UI refresh
    # ------------------------------------------------------------------

    def _refresh_workspace_ui(self) -> None:
        self.message_panel.set_workspace(self.workspace)
        self._refresh_validation_status()

    def _set_window_title(self, detail: str = "") -> None:
        title = "J1939 PCAN Simulator"
        if detail:
            title = f"{title} - {detail}"
        self.setWindowTitle(title)

    def _refresh_validation_status(self) -> None:
        issues = validate_workspace(self.workspace)
        text = validation_status_text(self.workspace)
        self.validation_panel.set_issues(self.workspace, issues)
        self.validation_status_btn.setText(text)
        errors = sum(1 for issue in issues if issue.severity == "error")
        warnings = sum(1 for issue in issues if issue.severity == "warning")
        state = "error" if errors else "warn" if warnings else "ok"
        self.validation_status_btn.setProperty("state", state)
        self.validation_status_btn.style().unpolish(self.validation_status_btn)
        self.validation_status_btn.style().polish(self.validation_status_btn)
        self.statusBar().showMessage("")

    def _kickoff_initial_load(self) -> None:
        last = cfg.get_last_config_path()
        path: Optional[str] = None
        if last and Path(last).exists():
            path = last
        elif DEFAULT_CONFIG.exists():
            path = str(DEFAULT_CONFIG)
        if path:
            self.io_worker.request_load.emit(str(Path(path)))
        else:
            self._refresh_workspace_ui()

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def closeEvent(self, ev) -> None:
        try:
            self.engine.stop_all()
        except Exception:
            pass
        try:
            # Synchronize DM state before closing.
            self._sync_dm1_states_to_workspace()
            target = self.current_path or str(cfg.AUTOSAVE_PATH)
            cfg.save(target, self.workspace)
            cfg.remember_path(str(Path(target).resolve()))
        except Exception:
            pass
        try:
            self.pcan.shutdown(wait_ms=1500)
        except Exception:
            pass
        try:
            self.io_worker.shutdown(wait_ms=2000)
        except Exception:
            pass
        super().closeEvent(ev)

