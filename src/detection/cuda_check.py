"""GPU CUDA 環境檢查（需求一 FR-1.3～1.5）。

純邏輯模組、與 Qt 分離：設定頁的「檢查」按鈕在背景執行緒呼叫
:func:`check_cuda`，將結果（:class:`CudaCheckResult`）以 signal 送回主執行緒
後再呈現診斷對話框。
"""

from __future__ import annotations

from dataclasses import dataclass

_GIB = 1024**3


@dataclass(frozen=True)
class CudaCheckResult:
    state: str  # "no_torch" | "cpu_only" | "cuda_unavailable" | "ok"
    torch_version: str | None  # 如 "2.9.1+cu128"；no_torch 時 None
    cuda_build_version: str | None  # torch.version.cuda；CPU-only 為 None
    cuda_available: bool
    device_count: int
    devices: tuple[str, ...]  # "NVIDIA GeForce RTX 5060 Laptop GPU (8.0 GB)" 形式
    cudnn_version: int | None
    suggested_device: str  # "auto" | "cpu"
    error: str | None  # 例外訊息（含 ImportError）


def check_cuda() -> CudaCheckResult:
    """檢查 PyTorch / CUDA 狀態，區分四種狀態（FR-1.4）。

    不得拋例外（FR-1.5）：所有例外（含 ImportError）收進 ``error`` 欄位。
    """
    try:
        import torch
    except Exception as exc:  # 狀態 1：torch 未安裝（或載入失敗）
        return CudaCheckResult(
            state="no_torch",
            torch_version=None,
            cuda_build_version=None,
            cuda_available=False,
            device_count=0,
            devices=(),
            cudnn_version=None,
            suggested_device="cpu",
            error=str(exc),
        )

    torch_version: str | None = None
    cuda_build_version: str | None = None
    try:
        torch_version = str(torch.__version__)
        raw_build = getattr(torch.version, "cuda", None)
        if raw_build is None:
            # 狀態 2：CPU-only build（torch.version.cuda is None）
            return CudaCheckResult(
                state="cpu_only",
                torch_version=torch_version,
                cuda_build_version=None,
                cuda_available=False,
                device_count=0,
                devices=(),
                cudnn_version=None,
                suggested_device="cpu",
                error=None,
            )
        cuda_build_version = str(raw_build)

        if not bool(torch.cuda.is_available()):
            # 狀態 3：CUDA build 但不可用（驅動／GPU 問題）
            return CudaCheckResult(
                state="cuda_unavailable",
                torch_version=torch_version,
                cuda_build_version=cuda_build_version,
                cuda_available=False,
                device_count=0,
                devices=(),
                cudnn_version=None,
                suggested_device="cpu",
                error=None,
            )

        # 狀態 4：正常可用
        device_count = int(torch.cuda.device_count())
        devices: list[str] = []
        for index in range(device_count):
            name = str(torch.cuda.get_device_name(index))
            properties = torch.cuda.get_device_properties(index)
            vram_gb = float(properties.total_memory) / _GIB
            devices.append(f"{name} ({vram_gb:.1f} GB)")
        raw_cudnn = torch.backends.cudnn.version()  # type: ignore[no-untyped-call]
        return CudaCheckResult(
            state="ok",
            torch_version=torch_version,
            cuda_build_version=cuda_build_version,
            cuda_available=True,
            device_count=device_count,
            devices=tuple(devices),
            cudnn_version=int(raw_cudnn) if raw_cudnn is not None else None,
            suggested_device="auto",
            error=None,
        )
    except Exception as exc:  # FR-1.5：任何內部例外不可外洩
        return CudaCheckResult(
            state="cuda_unavailable",
            torch_version=torch_version,
            cuda_build_version=cuda_build_version,
            cuda_available=False,
            device_count=0,
            devices=(),
            cudnn_version=None,
            suggested_device="cpu",
            error=str(exc),
        )
