"""需求一：GPU CUDA 檢查（FR-1.1～1.5）。

涵蓋：check_cuda 純函式四種狀態與例外封裝。
worker 的 device_fallback 通知與 app 接線測試已遷移至
tests/shell/test_worker.py 與 tests/shell/test_app.py（T11 切換）。
"""

from __future__ import annotations

import dataclasses
import types

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
