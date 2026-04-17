# gui/workers/deploy_worker.py
import subprocess
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal


class DeployWorker(QThread):
    line_output = pyqtSignal(int, str)         # (template_index, line)
    template_started = pyqtSignal(int)         # template_index
    template_finished = pyqtSignal(int, bool)  # (template_index, success)
    all_finished = pyqtSignal()

    def __init__(
        self,
        templates: list,
        resource_group: str,
        parameters_file: str,
        mode: str,
        az_command: str = "az",
        parent=None,
    ):
        super().__init__(parent)
        self.templates = templates
        self.resource_group = resource_group
        self.parameters_file = parameters_file
        self.mode = mode
        self.az_command = az_command

    def run(self):
        for i, template in enumerate(self.templates):
            self.template_started.emit(i)
            cmd = [
                self.az_command, "deployment", "group", "create",
                "--resource-group", self.resource_group,
                "--mode", self.mode,
                "--template-file", str(template),
                "--parameters", f"@{self.parameters_file}",
            ]
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                )
                for line in proc.stdout:
                    self.line_output.emit(i, line.rstrip())
                proc.wait()
                success = proc.returncode == 0
            except Exception as exc:
                self.line_output.emit(i, f"ERROR: {exc}")
                success = False
            self.template_finished.emit(i, success)
        self.all_finished.emit()
