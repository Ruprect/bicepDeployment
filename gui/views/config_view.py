# gui/views/config_view.py
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QFormLayout, QFrame
)
from PyQt6.QtCore import Qt
from ..workers.azure_worker import AzureWorker
from ..styles.theme import Color


class ConfigView(QWidget):
    def __init__(self, project_dir: Path, config_manager, azure_client, parent=None):
        super().__init__(parent)
        self.project_dir = project_dir
        self.config_manager = config_manager
        self.azure_client = azure_client
        self._workers: list[AzureWorker] = []
        self._build_ui()
        self._load_initial()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Login status banner
        self._login_banner = QLabel()
        self._login_banner.setStyleSheet(
            f"background: #1e3a2e; color: {Color.SUCCESS}; padding: 8px 12px;"
            f" border-radius: 4px; border: 1px solid {Color.SUCCESS};"
        )
        layout.addWidget(self._login_banner)

        form = QFormLayout()
        form.setSpacing(10)

        # Subscription
        self._sub_combo = QComboBox()
        sub_row = self._combo_with_refresh(self._sub_combo, self._refresh_subscriptions)
        form.addRow("Subscription", sub_row)

        # Resource Group
        self._rg_combo = QComboBox()
        rg_row = self._combo_with_refresh(self._rg_combo, self._refresh_resource_groups)
        form.addRow("Resource Group", rg_row)

        # Parameter File
        self._params_combo = QComboBox()
        params_row = self._combo_with_browse(self._params_combo)
        form.addRow("Parameter File", params_row)

        # Deployment Mode
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["Incremental", "Complete"])
        form.addRow("Deployment Mode", self._mode_combo)

        # Validation
        self._validation_combo = QComboBox()
        self._validation_combo.addItems(["All", "Changed", "Skip"])
        form.addRow("Validation", self._validation_combo)

        layout.addLayout(form)

        # Re-login button
        self._login_btn = QPushButton("🔑  Re-login to Azure")
        self._login_btn.clicked.connect(self._relogin)
        layout.addWidget(self._login_btn)

        # Wire changes to config
        self._rg_combo.currentTextChanged.connect(
            lambda t: self.config_manager.set_resource_group(t) if t else None
        )
        self._sub_combo.currentTextChanged.connect(self._on_subscription_changed)
        self._mode_combo.currentTextChanged.connect(
            lambda t: self.config_manager.set_validation_mode(t) if t else None
        )

    def _combo_with_refresh(self, combo: QComboBox, refresh_fn) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(combo)
        btn = QPushButton("🔄")
        btn.setFixedWidth(32)
        btn.clicked.connect(refresh_fn)
        row.addWidget(btn)
        return w

    def _combo_with_browse(self, combo: QComboBox) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(combo)
        btn = QPushButton("📁")
        btn.setFixedWidth(32)
        btn.clicked.connect(self._browse_params)
        row.addWidget(btn)
        return w

    def _load_initial(self):
        # Login status
        w = AzureWorker(callable=self.azure_client.test_azure_login, args=())
        w.result.connect(self._on_login_checked)
        w.finished.connect(lambda: self._workers.remove(w) if w in self._workers else None)
        self._workers.append(w)
        w.start()

        # Populate parameter files (local scan, fast)
        params = self.config_manager.get_parameter_files()
        self._params_combo.clear()
        for p in params:
            self._params_combo.addItem(p.name, userData=p)

    def _on_login_checked(self, logged_in: bool):
        if logged_in:
            self._login_banner.setText("● Logged in to Azure")
            self._login_banner.setStyleSheet(
                f"background: #1e3a2e; color: {Color.SUCCESS}; padding: 8px 12px;"
                f" border-radius: 4px;"
            )
            self._refresh_subscriptions()
        else:
            self._login_banner.setText("● Not logged in")
            self._login_banner.setStyleSheet(
                f"background: #3a1e1e; color: {Color.ERROR}; padding: 8px 12px;"
                f" border-radius: 4px;"
            )

    def _refresh_subscriptions(self):
        w = AzureWorker(callable=self.azure_client.get_azure_subscriptions, args=())
        w.result.connect(self._on_subscriptions_loaded)
        w.finished.connect(lambda: self._workers.remove(w) if w in self._workers else None)
        self._workers.append(w)
        w.start()

    def _on_subscriptions_loaded(self, subs):
        current = self.config_manager.get_subscription() or ""
        self._sub_combo.blockSignals(True)
        self._sub_combo.clear()
        for sub in subs:
            self._sub_combo.addItem(f"{sub.name}", userData=sub.subscription_id)
            if sub.subscription_id == current:
                self._sub_combo.setCurrentText(sub.name)
        self._sub_combo.blockSignals(False)

    def _refresh_resource_groups(self):
        w = AzureWorker(callable=self.azure_client.get_azure_resource_groups, args=())
        w.result.connect(self._on_resource_groups_loaded)
        w.finished.connect(lambda: self._workers.remove(w) if w in self._workers else None)
        self._workers.append(w)
        w.start()

    def _on_resource_groups_loaded(self, rgs):
        current = self.config_manager.get_resource_group() or ""
        self._rg_combo.blockSignals(True)
        self._rg_combo.clear()
        for rg in rgs:
            self._rg_combo.addItem(rg.name)
        if current:
            self._rg_combo.setCurrentText(current)
        self._rg_combo.blockSignals(False)

    def _on_subscription_changed(self, name: str):
        idx = self._sub_combo.currentIndex()
        sub_id = self._sub_combo.itemData(idx)
        if sub_id:
            self.config_manager.set_subscription(sub_id)
            self._refresh_resource_groups()

    def _browse_params(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Select parameter file", str(self.project_dir), "JSON files (*.json)"
        )
        if path:
            self._params_combo.addItem(Path(path).name, userData=Path(path))
            self._params_combo.setCurrentIndex(self._params_combo.count() - 1)

    def _relogin(self):
        self._login_btn.setEnabled(False)
        self._login_btn.setText("🔑  Logging in…")

        def do_login():
            proc = subprocess.Popen(["az", "login"])
            proc.wait()
            return proc.returncode == 0

        w = AzureWorker(callable=do_login, args=())
        w.result.connect(self._on_login_checked)
        w.finished.connect(self._on_relogin_done)
        w.finished.connect(lambda: self._workers.remove(w) if w in self._workers else None)
        self._workers.append(w)
        w.start()

    def _on_relogin_done(self):
        self._login_btn.setEnabled(True)
        self._login_btn.setText("🔑  Re-login to Azure")
