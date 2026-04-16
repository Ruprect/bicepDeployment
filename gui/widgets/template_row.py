# gui/widgets/template_row.py
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QCheckBox,
    QPushButton, QProgressBar, QTextEdit, QSizePolicy, QGraphicsOpacityEffect
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QColor
from ..styles.theme import Color


def _status_text(template) -> tuple[str, str]:
    """Return (label_text, css_color) for a BicepTemplate."""
    if not template.enabled:
        return "— Disabled", Color.MUTED
    if template.last_deployment_success is True and not template.needs_redeployment:
        return "✅ Up to date", Color.SUCCESS
    if template.last_deployment_success is False:
        return "❌ Failed", Color.ERROR
    if template.needs_redeployment or template.last_file_hash is None:
        return "🟡 Changed", Color.WARNING
    return "⚪ Never deployed", Color.MUTED


class TemplateRowWidget(QWidget):
    enabled_changed = pyqtSignal(str, bool)   # template name, new enabled state

    def __init__(self, template, parent=None):
        super().__init__(parent)
        self.template = template
        self._expanded = False
        self._elapsed_seconds = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        self._build_ui()
        self._apply_status()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Header row ──────────────────────────────────────────────────────
        header = QWidget()
        header.setStyleSheet(
            f"background: {Color.SURFACE}; border: 1px solid {Color.OVERLAY};"
            f" border-radius: 6px;"
        )
        self._header_widget = header
        row = QHBoxLayout(header)
        row.setContentsMargins(10, 6, 10, 6)

        self._checkbox = QCheckBox()
        self._checkbox.setChecked(self.template.enabled)
        self._checkbox.stateChanged.connect(
            lambda s: self.enabled_changed.emit(
                self.template.name, s == Qt.CheckState.Checked.value
            )
        )
        row.addWidget(self._checkbox)

        self._num_label = QLabel(f"{self.template.name[:2]}")
        self._num_label.setStyleSheet(f"color: {Color.MUTED}; min-width: 24px;")
        row.addWidget(self._num_label)

        self._name_label = QLabel(self.template.file.name)
        self._name_label.setStyleSheet(f"color: {Color.TEXT};")
        self._name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row.addWidget(self._name_label)

        # Progress bar (hidden until deploying)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)   # indeterminate
        self._progress_bar.setFixedWidth(80)
        self._progress_bar.setFixedHeight(4)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet(
            f"QProgressBar {{ background: {Color.OVERLAY}; border-radius: 2px; }}"
            f"QProgressBar::chunk {{ background: {Color.ACCENT}; border-radius: 2px; }}"
        )
        self._progress_bar.setVisible(False)
        row.addWidget(self._progress_bar)

        self._elapsed_label = QLabel()
        self._elapsed_label.setStyleSheet(f"color: {Color.ACCENT}; min-width: 36px;")
        self._elapsed_label.setVisible(False)
        row.addWidget(self._elapsed_label)

        self._status_label = QLabel()
        row.addWidget(self._status_label)

        self._toggle_btn = QPushButton("▼")
        self._toggle_btn.setFlat(True)
        self._toggle_btn.setFixedWidth(24)
        self._toggle_btn.setStyleSheet(f"color: {Color.MUTED};")
        self._toggle_btn.clicked.connect(self.toggle_log)
        row.addWidget(self._toggle_btn)

        outer.addWidget(header)

        # ── Log panel (hidden by default) ────────────────────────────────────
        self._log_panel = QTextEdit()
        self._log_panel.setReadOnly(True)
        self._log_panel.setFixedHeight(100)
        self._log_panel.setStyleSheet(
            f"background: #11111b; color: {Color.TEXT}; font-family: 'Cascadia Code', 'Consolas', monospace;"
            f" font-size: 10px; border: 1px solid {Color.OVERLAY}; border-top: none;"
            f" border-radius: 0 0 6px 6px; padding: 6px;"
        )
        self._log_panel.setVisible(False)
        outer.addWidget(self._log_panel)

    def _apply_status(self):
        text, color = _status_text(self.template)
        self._status_label.setText(text)
        self._status_label.setStyleSheet(f"color: {color}; min-width: 120px; text-align: right;")

        effect = QGraphicsOpacityEffect(self)
        effect.setOpacity(0.45 if not self.template.enabled else 1.0)
        self.setGraphicsEffect(effect)

    def toggle_log(self):
        self._expanded = not self._expanded
        self._log_panel.setVisible(self._expanded)
        self._toggle_btn.setText("▲" if self._expanded else "▼")

    def append_log(self, line: str):
        self._log_panel.append(line)

    def set_deploying(self, deploying: bool):
        self._progress_bar.setVisible(deploying)
        self._elapsed_label.setVisible(deploying)
        if deploying:
            self._elapsed_seconds = 0
            self._elapsed_label.setText("⏳ 0s")
            self._timer.start(1000)
            self._header_widget.setStyleSheet(
                f"background: {Color.SURFACE}; border: 1px solid {Color.ACCENT}; border-radius: 6px;"
            )
            if not self._expanded:
                self.toggle_log()
        else:
            self._timer.stop()
            self._header_widget.setStyleSheet(
                f"background: {Color.SURFACE}; border: 1px solid {Color.OVERLAY}; border-radius: 6px;"
            )

    def set_failed(self):
        self._header_widget.setStyleSheet(
            f"background: {Color.SURFACE}; border: 1px solid {Color.ERROR}; border-radius: 6px;"
        )
        self._status_label.setText("❌ Failed")
        self._status_label.setStyleSheet(f"color: {Color.ERROR}; min-width: 120px;")
        if not self._expanded:
            self.toggle_log()   # auto-expand on failure

    def set_succeeded(self):
        self._header_widget.setStyleSheet(
            f"background: {Color.SURFACE}; border: 1px solid {Color.OVERLAY}; border-radius: 6px;"
        )
        self._status_label.setText("✅ Up to date")
        self._status_label.setStyleSheet(f"color: {Color.SUCCESS}; min-width: 120px;")

    def _tick(self):
        self._elapsed_seconds += 1
        self._elapsed_label.setText(f"⏳ {self._elapsed_seconds}s")
