from __future__ import annotations

import inspect

import src.main
from src.main import _shutdown_worker_thread


class FakeWorker:
    def __init__(self) -> None:
        self.stop_calls = 0

    def stop(self) -> None:
        self.stop_calls += 1


class FakeThread:
    def __init__(self, *, wait_result: bool) -> None:
        self.quit_calls = 0
        self.wait_calls: list[int] = []
        self.terminate_calls = 0
        self._wait_result = wait_result

    def quit(self) -> None:
        self.quit_calls += 1

    def wait(self, timeout: int) -> bool:
        self.wait_calls.append(timeout)
        return self._wait_result

    def terminate(self) -> None:
        self.terminate_calls += 1


def test_shutdown_worker_thread_stops_worker_and_quits_thread() -> None:
    worker = FakeWorker()
    thread = FakeThread(wait_result=True)

    _shutdown_worker_thread(worker, thread)

    assert worker.stop_calls == 1
    assert thread.quit_calls == 1
    assert thread.wait_calls == [1500]
    assert thread.terminate_calls == 0


def test_shutdown_worker_thread_terminates_when_thread_does_not_exit() -> None:
    worker = FakeWorker()
    thread = FakeThread(wait_result=False)

    _shutdown_worker_thread(worker, thread)

    assert worker.stop_calls == 1
    assert thread.quit_calls == 1
    assert thread.wait_calls == [1500, 500]
    assert thread.terminate_calls == 1


def test_failed_signal_not_connected_to_quit() -> None:
    source = inspect.getsource(src.main.main)
    assert "worker.failed.connect(lambda _message: app.quit())" not in source


def test_main_imports_new_modules() -> None:
    assert hasattr(src.main, "setup_logging")
    assert hasattr(src.main, "suppress_decoder_noise")
    assert hasattr(src.main, "ThemeManager")


def test_main_uses_request_worker_apis_for_ui_commands() -> None:
    source = inspect.getsource(src.main.main)

    assert "reminder.start_rest.connect(worker.request_start_rest)" in source
    assert "return_prompt_dialog.confirmed.connect(worker.request_confirm_return)" in source
    assert "window.roi_changed.connect(worker.request_set_roi)" in source
    assert "worker.request_pause()" in source
    assert "worker.request_resume()" in source
