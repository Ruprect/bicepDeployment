# tests/gui/test_app.py
from pathlib import Path


def test_main_window_instantiates(qtbot):
    from gui.main_window import MainWindow
    window = MainWindow(project_dir=Path("d:/repos/NewBicep"))
    qtbot.addWidget(window)
    assert window.windowTitle() == "Bicep Deploy"


def test_main_window_has_four_pages(qtbot):
    from gui.main_window import MainWindow
    window = MainWindow(project_dir=Path("d:/repos/NewBicep"))
    qtbot.addWidget(window)
    assert window.stack.count() == 4


def test_sidebar_switches_page(qtbot):
    from gui.main_window import MainWindow
    window = MainWindow(project_dir=Path("d:/repos/NewBicep"))
    qtbot.addWidget(window)
    window.show()

    # Click Config (index 1)
    window.sidebar._select(1)
    assert window.stack.currentIndex() == 1

    # Click Deploy (index 0)
    window.sidebar._select(0)
    assert window.stack.currentIndex() == 0


def test_template_row_instantiates(qtbot):
    from gui.widgets.template_row import TemplateRowWidget
    from unittest.mock import MagicMock
    from pathlib import Path

    tpl = MagicMock()
    tpl.name = "01"
    tpl.file = Path("workflows-bc.bicep")
    tpl.enabled = True
    tpl.needs_redeployment = False
    tpl.last_deployment_success = True
    tpl.last_file_hash = "abc"

    row = TemplateRowWidget(tpl)
    qtbot.addWidget(row)
    assert not row._expanded
    row.toggle_log()
    assert row._expanded


def test_deploy_view_loads_templates(qtbot):
    from gui.views.deploy_view import DeployView
    from unittest.mock import MagicMock
    from pathlib import Path

    bicep_manager = MagicMock()
    bicep_manager.get_bicep_files.return_value = []
    config_manager = MagicMock()
    config_manager.get_validation_mode.return_value = "Changed"

    view = DeployView(Path("d:/repos/NewBicep"), config_manager, bicep_manager)
    qtbot.addWidget(view)
    assert len(view._rows) == 0
    bicep_manager.get_bicep_files.assert_called_once()


def test_reorder_view_loads(qtbot):
    from gui.views.reorder_view import ReorderView
    from unittest.mock import MagicMock
    from pathlib import Path

    bm = MagicMock()
    bm.get_bicep_files.return_value = []
    view = ReorderView(Path("d:/repos/NewBicep"), MagicMock(), bm)
    qtbot.addWidget(view)
    assert view._list.count() == 0


def test_export_view_loads(qtbot):
    from gui.views.export_view import ExportView
    from unittest.mock import MagicMock
    from pathlib import Path

    view = ExportView(
        Path("d:/repos/NewBicep"),
        MagicMock(), MagicMock(), MagicMock()
    )
    qtbot.addWidget(view)
    assert view._list.count() == 0
    assert not view._export_btn.isEnabled()
