# tests/gui/test_deploy_worker.py
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_deploy_worker_emits_signals_on_success(qtbot):
    from gui.workers.deploy_worker import DeployWorker

    worker = DeployWorker(
        templates=[Path("fake.bicep")],
        resource_group="rg-test",
        parameters_file="params.json",
        mode="Incremental",
    )

    started, lines, finished = [], [], []
    worker.template_started.connect(lambda i: started.append(i))
    worker.line_output.connect(lambda i, l: lines.append((i, l)))
    worker.template_finished.connect(lambda i, s: finished.append((i, s)))

    mock_proc = MagicMock()
    mock_proc.stdout.__iter__ = lambda self: iter(["output line 1\n", "output line 2\n"])
    mock_proc.wait.return_value = None
    mock_proc.returncode = 0

    with patch("gui.workers.deploy_worker.subprocess.Popen", return_value=mock_proc):
        with qtbot.waitSignal(worker.all_finished, timeout=5000):
            worker.start()

    assert started == [0]
    assert lines == [(0, "output line 1"), (0, "output line 2")]
    assert finished == [(0, True)]


def test_deploy_worker_emits_failure_on_nonzero_exit(qtbot):
    from gui.workers.deploy_worker import DeployWorker

    worker = DeployWorker(
        templates=[Path("fake.bicep")],
        resource_group="rg-test",
        parameters_file="params.json",
        mode="Incremental",
    )

    finished = []
    worker.template_finished.connect(lambda i, s: finished.append((i, s)))

    mock_proc = MagicMock()
    mock_proc.stdout.__iter__ = lambda self: iter(["ERROR: deploy failed\n"])
    mock_proc.wait.return_value = None
    mock_proc.returncode = 1

    with patch("gui.workers.deploy_worker.subprocess.Popen", return_value=mock_proc):
        with qtbot.waitSignal(worker.all_finished, timeout=5000):
            worker.start()

    assert finished == [(0, False)]


def test_deploy_worker_sequences_multiple_templates(qtbot):
    from gui.workers.deploy_worker import DeployWorker

    worker = DeployWorker(
        templates=[Path("a.bicep"), Path("b.bicep")],
        resource_group="rg-test",
        parameters_file="params.json",
        mode="Incremental",
    )

    started, finished = [], []
    worker.template_started.connect(lambda i: started.append(i))
    worker.template_finished.connect(lambda i, s: finished.append(i))

    mock_proc = MagicMock()
    mock_proc.stdout.__iter__ = lambda self: iter([])
    mock_proc.wait.return_value = None
    mock_proc.returncode = 0

    with patch("gui.workers.deploy_worker.subprocess.Popen", return_value=mock_proc):
        with qtbot.waitSignal(worker.all_finished, timeout=5000):
            worker.start()

    assert started == [0, 1]
    assert finished == [0, 1]


def test_deploy_worker_builds_correct_az_command(qtbot):
    from gui.workers.deploy_worker import DeployWorker

    worker = DeployWorker(
        templates=[Path("my.bicep")],
        resource_group="rg-prod",
        parameters_file="/path/params.json",
        mode="Complete",
    )

    captured_cmd = []

    def fake_popen(cmd, **kwargs):
        captured_cmd.extend(cmd)
        m = MagicMock()
        m.stdout.__iter__ = lambda self: iter([])
        m.wait.return_value = None
        m.returncode = 0
        return m

    with patch("gui.workers.deploy_worker.subprocess.Popen", side_effect=fake_popen):
        with qtbot.waitSignal(worker.all_finished, timeout=5000):
            worker.start()

    assert "--resource-group" in captured_cmd
    assert "rg-prod" in captured_cmd
    assert "--mode" in captured_cmd
    assert "Complete" in captured_cmd
    assert "--template-file" in captured_cmd
    assert "@/path/params.json" in captured_cmd
