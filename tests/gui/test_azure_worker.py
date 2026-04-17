# tests/gui/test_azure_worker.py

def test_azure_worker_emits_result(qtbot):
    from gui.workers.azure_worker import AzureWorker

    worker = AzureWorker(callable=lambda: "hello", args=())
    results = []
    worker.result.connect(lambda d: results.append(d))

    with qtbot.waitSignal(worker.finished, timeout=5000):
        worker.start()

    assert results == ["hello"]


def test_azure_worker_emits_error_on_exception(qtbot):
    from gui.workers.azure_worker import AzureWorker

    def bad():
        raise ValueError("broke")

    worker = AzureWorker(callable=bad, args=())
    errors = []
    worker.error.connect(lambda msg: errors.append(msg))

    with qtbot.waitSignal(worker.finished, timeout=5000):
        worker.start()

    assert len(errors) == 1
    assert "broke" in errors[0]


def test_azure_worker_passes_args_to_callable(qtbot):
    from gui.workers.azure_worker import AzureWorker

    results = []
    worker = AzureWorker(callable=lambda a, b: a + b, args=(2, 3))
    worker.result.connect(lambda d: results.append(d))

    with qtbot.waitSignal(worker.finished, timeout=5000):
        worker.start()

    assert results == [5]
