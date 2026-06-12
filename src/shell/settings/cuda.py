"""CUDA 檢查元件（自舊 ``src/ui/settings.py`` 抽出，FR-1.1～1.5）。

- :class:`DeviceField`：下拉選單＋「檢查」按鈕複合 widget。
- :func:`format_cuda_report`：組診斷對話框文字。
- :class:`CudaCheckController`：背景執行緒檢查的啟動／取消／遲到結果忽略，
  結果以 ``result_ready`` signal 回主執行緒（對話框呈現由視窗負責）。
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QWidget

from src.detection.cuda_check import CudaCheckResult, check_cuda
from src.shell import strings

_CUDA_STATE_HINTS: dict[str, str] = {
    "no_torch": strings.CUDA_STATE_NO_TORCH,
    "cpu_only": strings.CUDA_STATE_CPU_ONLY,
    "cuda_unavailable": strings.CUDA_STATE_CUDA_UNAVAILABLE,
    "ok": strings.CUDA_STATE_OK,
}


def format_cuda_report(result: CudaCheckResult) -> str:
    """組 CUDA 診斷對話框文字（FR-1.3、FR-1.4）。"""
    headline = strings.CUDA_CHECK_OK if result.state == "ok" else strings.CUDA_CHECK_FAIL
    lines: list[str] = [headline, ""]
    hint = _CUDA_STATE_HINTS.get(result.state)
    if hint is not None:
        lines.extend([hint, ""])
    lines.append(
        strings.CUDA_TORCH_VERSION.format(
            value=result.torch_version or strings.CUDA_VALUE_NOT_INSTALLED
        )
    )
    lines.append(
        strings.CUDA_BUILD_VERSION.format(
            value=result.cuda_build_version or strings.CUDA_BUILD_NONE
        )
    )
    lines.append(
        strings.CUDA_AVAILABLE.format(
            value=strings.CUDA_VALUE_YES if result.cuda_available else strings.CUDA_VALUE_NO
        )
    )
    lines.append(strings.CUDA_DEVICE_COUNT.format(value=result.device_count))
    lines.extend(f"　• {name}" for name in result.devices)
    lines.append(
        strings.CUDA_CUDNN_VERSION.format(
            value=result.cudnn_version
            if result.cudnn_version is not None
            else strings.CUDA_VALUE_NONE
        )
    )
    if result.error:
        lines.append(strings.CUDA_ERROR.format(value=result.error))
    lines.extend(["", strings.CUDA_SUGGEST.format(device=result.suggested_device)])
    return "\n".join(lines)


class CudaCheckBridge(QObject):
    """背景執行緒 → 主執行緒的結果橋接（FR-1.2）。

    bridge 建立於主執行緒，從背景執行緒 emit 時 PySide6 會自動以
    queued connection 把結果送回主執行緒後才碰 UI。
    """

    finished = Signal(object)


class CudaCheckRunnable(QRunnable):
    def __init__(
        self, checker: Callable[[], CudaCheckResult], bridge: CudaCheckBridge
    ) -> None:
        super().__init__()
        self._checker = checker
        self._bridge = bridge

    def run(self) -> None:
        # FR-1.5：checker 拋例外時 finished 仍必須發出，否則「檢查」按鈕會
        # 永久卡在「檢查中…」（防重入旗標無人重設）；例外訊息納入結果呈現。
        try:
            result = self._checker()
        except Exception as exc:
            result = CudaCheckResult(
                state="cuda_unavailable",
                torch_version=None,
                cuda_build_version=None,
                cuda_available=False,
                device_count=0,
                devices=(),
                cudnn_version=None,
                suggested_device="cpu",
                error=str(exc),
            )
        self._bridge.finished.emit(result)


class DeviceField(QWidget):
    """運算裝置欄位：下拉選單＋「檢查」按鈕同列（FR-1.1，仿 PathField 複合 widget）。"""

    check_requested = Signal()

    def __init__(self, choices: tuple[str, ...], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.combo = QComboBox()
        self.combo.addItems(choices)
        self.check_button = QPushButton(strings.CUDA_CHECK_BUTTON)
        self.check_button.clicked.connect(self.check_requested.emit)

        layout.addWidget(self.combo, stretch=1)
        layout.addWidget(self.check_button)

    def set_checking(self, checking: bool) -> None:
        """FR-1.2：檢查中按鈕停用並顯示「檢查中…」，完成後復原。"""
        self.check_button.setEnabled(not checking)
        self.check_button.setText(
            strings.CUDA_CHECK_RUNNING if checking else strings.CUDA_CHECK_BUTTON
        )


class CudaCheckController(QObject):
    """背景 CUDA 檢查的生命週期：防重入、取消、遲到結果忽略（FR-1.2、FR-1.5）。"""

    result_ready = Signal(object)  # CudaCheckResult（僅「目前這次」檢查的結果）

    def __init__(
        self,
        checker: Callable[[], CudaCheckResult] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._checker: Callable[[], CudaCheckResult] = (
            checker if checker is not None else check_cuda
        )
        self._running = False
        self._bridge: CudaCheckBridge | None = None
        # 已取消檢查的舊 bridge：保留主執行緒參考，避免 runnable 在
        # QThreadPool 執行緒 autoDelete 時跨執行緒銷毀 QObject。
        self._stale_bridges: list[CudaCheckBridge] = []

    @property
    def checker(self) -> Callable[[], CudaCheckResult]:
        return self._checker

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> bool:
        """啟動背景檢查；檢查進行中再呼叫無效（回傳 False，FR-1.2 防重入）。"""
        if self._running:
            return False
        self._running = True
        bridge = CudaCheckBridge()
        bridge.finished.connect(self._on_finished)
        self._bridge = bridge  # 保持存活直到結果回來
        QThreadPool.globalInstance().start(CudaCheckRunnable(self._checker, bridge))
        return True

    def cancel(self) -> None:
        """取消進行中的檢查：遲到結果不再發出 ``result_ready``。

        刻意不 disconnect：遲到結果仍會進 ``_on_finished``，由 sender 比對
        分流忽略，並順手把舊 bridge 自 ``_stale_bridges`` 釋放（quality
        review #4——disconnect 會讓清理分支永不可達，stale bridge 累積到
        視窗銷毀）。保留主執行緒參考的理由不變：避免 runnable 在
        QThreadPool 執行緒被 autoDelete 時，連帶從背景執行緒銷毀這個
        main-thread affinity 的 QObject。checker 永不返回時 bridge 與
        controller 同壽命（與既往行為相同）。
        """
        if not self._running:
            return
        self._running = False
        if self._bridge is not None:
            self._stale_bridges.append(self._bridge)
        self._bridge = None

    def _on_finished(self, result: object) -> None:
        sender = self.sender()
        if sender is not self._bridge:
            # 已取消／已被新檢查取代的舊 bridge 的遲到結果：忽略（防重入
            # 語意，FR-1.2）。結果已送達，舊 bridge 可自 stale 清單釋放。
            if isinstance(sender, CudaCheckBridge) and sender in self._stale_bridges:
                self._stale_bridges.remove(sender)
            return
        if not self._running:
            return  # 視窗關閉後的遲到結果：忽略
        self._running = False
        self._bridge = None
        self.result_ready.emit(result)
