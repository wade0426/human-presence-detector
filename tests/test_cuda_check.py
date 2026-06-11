"""需求一：GPU CUDA 檢查（FR-1.1～1.6）。

涵蓋：check_cuda 純函式四種狀態與例外封裝、worker 的 device_fallback 通知、
main.py 接線（以 QObject slot 連線，§4.6）。
"""

from __future__ import annotations

import dataclasses
import inspect
import itertools
import threading
import types
from typing import Any

import numpy as np
import pytest

from src.detection.cuda_check import CudaCheckResult, check_cuda

GIB = 1024**3


def _fake_torch(
    *,
    torch_version: str = "2.9.1+cu128",
    cuda_build: str | None = "12.8",
    available: bool = True,
    device_count: int = 1,
    cudnn: int | None = 91002,
) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        __version__=torch_version,
        version=types.SimpleNamespace(cuda=cuda_build),
        cuda=types.SimpleNamespace(
            is_available=lambda: available,
            device_count=lambda: device_count,
            get_device_name=lambda index: "NVIDIA GeForce RTX 5060 Laptop GPU",
            get_device_properties=lambda index: types.SimpleNamespace(total_memory=8 * GIB),
        ),
        backends=types.SimpleNamespace(cudnn=types.SimpleNamespace(version=lambda: cudnn)),
    )


# ---------------------------------------------------------------------------
# FR-1.4：四種狀態各回傳正確 state 與 suggested_device
# ---------------------------------------------------------------------------


def test_check_cuda_no_torch(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    # sys.modules 設 None → `import torch` 觸發 ImportError（狀態 1）。
    monkeypatch.setitem(sys.modules, "torch", None)

    result = check_cuda()

    assert result.state == "no_torch"
    assert result.torch_version is None
    assert result.cuda_build_version is None
    assert result.cuda_available is False
    assert result.device_count == 0
    assert result.devices == ()
    assert result.cudnn_version is None
    assert result.suggested_device == "cpu"
    assert result.error is not None


def test_check_cuda_cpu_only_build(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    monkeypatch.setitem(
        sys.modules, "torch", _fake_torch(torch_version="2.9.1+cpu", cuda_build=None)
    )

    result = check_cuda()

    assert result.state == "cpu_only"
    assert result.torch_version == "2.9.1+cpu"
    assert result.cuda_build_version is None
    assert result.cuda_available is False
    assert result.suggested_device == "cpu"


def test_check_cuda_build_but_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    monkeypatch.setitem(sys.modules, "torch", _fake_torch(available=False))

    result = check_cuda()

    assert result.state == "cuda_unavailable"
    assert result.torch_version == "2.9.1+cu128"
    assert result.cuda_build_version == "12.8"
    assert result.cuda_available is False
    assert result.device_count == 0
    assert result.suggested_device == "cpu"


def test_check_cuda_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    monkeypatch.setitem(sys.modules, "torch", _fake_torch())

    result = check_cuda()

    assert result.state == "ok"
    assert result.torch_version == "2.9.1+cu128"
    assert result.cuda_build_version == "12.8"
    assert result.cuda_available is True
    assert result.device_count == 1
    assert result.devices == ("NVIDIA GeForce RTX 5060 Laptop GPU (8.0 GB)",)
    assert result.cudnn_version == 91002
    assert result.suggested_device == "auto"
    assert result.error is None


# ---------------------------------------------------------------------------
# FR-1.5：任何內部例外不可外洩，收進 error 欄位
# ---------------------------------------------------------------------------


def test_check_cuda_internal_exception_is_contained(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    fake = _fake_torch()

    def _explode() -> bool:
        raise RuntimeError("driver wedged")

    fake.cuda.is_available = _explode
    monkeypatch.setitem(sys.modules, "torch", fake)

    result = check_cuda()  # 不得拋例外

    assert result.error is not None
    assert "driver wedged" in result.error
    assert result.suggested_device == "cpu"
    assert result.cuda_available is False


def test_cuda_check_result_is_frozen() -> None:
    result = CudaCheckResult(
        state="ok",
        torch_version="2.9.1+cu128",
        cuda_build_version="12.8",
        cuda_available=True,
        device_count=1,
        devices=("GPU (8.0 GB)",),
        cudnn_version=91002,
        suggested_device="auto",
        error=None,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.state = "cpu_only"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# FR-1.6（worker 端）：偵測啟動後 fallback 發生 → emit device_fallback 一次
# ---------------------------------------------------------------------------


from src.app.worker import DetectionWorker  # noqa: E402
from src.presence import PresenceEvaluator  # noqa: E402
from src.timer_engine import TimerEngine  # noqa: E402
from src.types import BBox, Detection, Frame, ReminderContext  # noqa: E402

_TS_COUNTER = itertools.count()


class _LiveFrames:
    """每次 latest() 皆回傳新 timestamp 的影格（§4.2 新鮮度判定）。"""

    @property
    def is_opened(self) -> bool:
        return True

    def latest(self) -> Frame:
        image = np.zeros((10, 10, 3), dtype=np.uint8)
        return Frame(image=image, width=10, height=10, timestamp=float(next(_TS_COUNTER)))


class _FallbackDetector:
    device_fallback = True

    def detect(self, frame: Frame) -> list[Detection]:
        del frame
        return []


class _PlainDetector:
    """無 device_fallback 屬性的偵測器（向後相容）。"""

    def detect(self, frame: Frame) -> list[Detection]:
        del frame
        return []


class _NullStore:
    def init_schema(self) -> None:
        return None

    def log_session(self, *args: Any, **kwargs: Any) -> int:
        del args, kwargs
        return 1

    def close(self) -> None:
        return None


def _make_worker(detector: Any) -> DetectionWorker:
    return DetectionWorker(
        frames=_LiveFrames(),
        detector=detector,
        presence_evaluator=PresenceEvaluator(BBox(0.0, 0.0, 1.0, 1.0), 0.2, 1),
        timer_engine=TimerEngine(100.0, 5.0, 5.0, 3.0),
        store=_NullStore(),
        detection_interval_sec=0.0,
        reminder_context=ReminderContext(45, "", "image", ""),
    )


@pytest.mark.qt
def test_worker_emits_device_fallback_once(qtbot: pytest.QtBot) -> None:
    worker = _make_worker(_FallbackDetector())
    emissions: list[str] = []
    worker.device_fallback.connect(emissions.append)

    thread = threading.Thread(target=worker.run, daemon=True)
    with qtbot.waitSignal(worker.device_fallback, timeout=3000):
        thread.start()
    qtbot.wait(150)  # 再跑幾輪偵測迴圈，確認不重複通知
    worker.stop()
    thread.join(timeout=1.0)

    assert emissions == ["cpu"]


@pytest.mark.qt
def test_worker_without_fallback_does_not_emit(qtbot: pytest.QtBot) -> None:
    worker = _make_worker(_PlainDetector())
    emissions: list[str] = []
    worker.device_fallback.connect(emissions.append)

    worker._notify_device_fallback_once()
    worker._notify_device_fallback_once()

    assert emissions == []


# ---------------------------------------------------------------------------
# main.py 接線：device_fallback 連到 QObject slot（§4.6，不可 lambda）
# ---------------------------------------------------------------------------


def test_main_wires_device_fallback_to_qobject_slot() -> None:
    import src.main

    source = inspect.getsource(src.main.main)
    assert "worker.device_fallback.connect(fallback_notifier.on_device_fallback)" in source
    assert "device_fallback.connect(lambda" not in source
