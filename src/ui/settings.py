from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtGui import QIcon
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from src import config as config_module
from src.config import AppConfig, ConfigError, load_config, save_config, validate
from src.detection.cuda_check import CudaCheckResult, check_cuda
from src.reminder.sound import LoopingSoundPlayer, QtSoundPlayer
from src.ui import strings
from src.ui.settings_schema import (
    CATEGORIES,
    SCHEMA,
    FieldSpec,
    WidgetKind,
    fields_for,
    get_value,
    set_value,
    tooltip_for,
)

# FR-2.7 / FR-3.1：音檔欄位以 key 清單特判（清單內容由 tests/test_settings_schema.py 鎖定）。
SOUND_FIELD_KEYS: tuple[str, ...] = (
    "reminder.popup.sound_path",
    "reminder.return_sound.sound_path",
)

# FR-1.1：運算裝置欄位（下拉選單＋「檢查」按鈕複合 widget）。
DEVICE_FIELD_KEY = "detection.device"

# FR-3.1：試聽按鈕的喇叭圖示資產（與 src/ui/icons.py 相同的模組定錨方式）。
_TRUMPET_ICON_PATH = Path(__file__).resolve().parents[2] / "data" / "assets" / "trumpet.png"


def _speaker_icon(widget: QWidget) -> QIcon:
    """FR-3.1：優先使用出貨資產 trumpet.png；缺檔或無法載入時退回內建喇叭圖示。"""
    if _TRUMPET_ICON_PATH.exists():
        icon = QIcon(str(_TRUMPET_ICON_PATH))
        if not icon.isNull():
            return icon
    return widget.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume)

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


class _CudaCheckBridge(QObject):
    """背景執行緒 → 主執行緒的結果橋接（FR-1.2）。

    bridge 建立於主執行緒，從背景執行緒 emit 時 PySide6 會自動以
    queued connection 把結果送回主執行緒後才碰 UI。
    """

    finished = Signal(object)


class _CudaCheckRunnable(QRunnable):
    def __init__(
        self, checker: Callable[[], CudaCheckResult], bridge: _CudaCheckBridge
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


class PathField(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        file_filter: str | None = None,
    ) -> None:
        super().__init__(parent)
        self._file_filter = file_filter or strings.FILE_DIALOG_ALL_FILES
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.line_edit = QLineEdit()
        self.browse_button = QPushButton("瀏覽")
        self.browse_button.clicked.connect(self._browse)

        layout.addWidget(self.line_edit)
        layout.addWidget(self.browse_button)

    def _browse(self) -> None:
        chosen, _ = QFileDialog.getOpenFileName(
            self, strings.FILE_DIALOG_TITLE, "", self._file_filter
        )
        if chosen:
            self.line_edit.setText(chosen)


class SoundPathField(PathField):
    """音檔欄位：輸入框＋瀏覽＋試聽同列（FR-3.1）；瀏覽帶音訊過濾（FR-2.7）。"""

    preview_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, file_filter=strings.SOUND_FILE_FILTER)
        # FR-3.1：試聽按鈕帶喇叭圖示（非純文字）；播放中換成停止圖示。
        self._play_icon = _speaker_icon(self)
        self._stop_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop)
        self.preview_button = QPushButton(strings.SOUND_PREVIEW_PLAY)
        self.preview_button.setIcon(self._play_icon)
        self.preview_button.clicked.connect(self.preview_requested.emit)
        inner_layout = self.layout()
        if inner_layout is not None:
            inner_layout.addWidget(self.preview_button)

    def set_previewing(self, previewing: bool) -> None:
        self.preview_button.setText(
            strings.SOUND_PREVIEW_STOP if previewing else strings.SOUND_PREVIEW_PLAY
        )
        self.preview_button.setIcon(self._stop_icon if previewing else self._play_icon)


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


class SettingsWindow(QDialog):
    clear_data_requested = Signal()

    def __init__(
        self,
        config: AppConfig,
        config_path: str | QWidget = "config.yaml",
        parent: QWidget | None = None,
        *,
        preview_player: LoopingSoundPlayer | None = None,
        cuda_checker: Callable[[], CudaCheckResult] | None = None,
    ) -> None:
        super().__init__(parent)
        resolved_parent = parent
        resolved_path = config_path
        if isinstance(config_path, QWidget):
            resolved_parent = config_path
            resolved_path = "config.yaml"
            super().setParent(resolved_parent)
        self._config = config
        self._config_path = str(resolved_path)
        self._widgets: dict[str, object] = {}
        self._hint_labels: dict[str, QLabel] = {}
        self._hint_texts: dict[str, str] = {}

        # 試聽（需求三）：單一共享播放器，同時僅允許一個試聽（FR-3.4、FR-3.7）。
        self._preview_player: LoopingSoundPlayer = (
            preview_player if preview_player is not None else QtSoundPlayer(self)
        )
        self._preview_key: str | None = None
        # FR-3.6：最後一次啟動試聽的欄位 key——QMediaPlayer 可能先發
        # StoppedState（清掉 _preview_key）再發 errorOccurred，錯誤 hint
        # 需要回退到這個 key 才不會漏標。
        self._preview_started_key: str | None = None
        self._wire_preview_player_signals()

        # CUDA 檢查（需求一）：純函式 checker 可注入替身測試（FR-1.2、FR-1.5）。
        self._cuda_checker: Callable[[], CudaCheckResult] = (
            cuda_checker if cuda_checker is not None else check_cuda
        )
        self._cuda_check_running = False
        self._cuda_bridge: _CudaCheckBridge | None = None
        # 已取消檢查的舊 bridge：保留主執行緒參考，避免 runnable 在
        # QThreadPool 執行緒 autoDelete 時跨執行緒銷毀 QObject。
        self._stale_cuda_bridges: list[_CudaCheckBridge] = []

        self.setWindowTitle(strings.SETTINGS_TITLE)
        self.setMinimumSize(640, 480)

        self._build_ui()
        self._populate()

    def _build_ui(self) -> None:
        self._category_list = QListWidget()
        self._category_list.setFixedWidth(120)
        for category in CATEGORIES:
            self._category_list.addItem(category)

        self._stack = QStackedWidget()
        for category in CATEGORIES:
            self._stack.addWidget(self._build_category_page(category))

        self._category_list.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._category_list.setCurrentRow(0)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if save_button is not None:
            save_button.setText(strings.SETTINGS_SAVE)
            save_button.setDefault(True)
        if cancel_button is not None:
            cancel_button.setText(strings.SETTINGS_CANCEL)

        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)

        content_layout = QHBoxLayout()
        content_layout.addWidget(self._category_list)
        content_layout.addWidget(self._stack, stretch=1)

        main_layout = QVBoxLayout(self)
        main_layout.addLayout(content_layout)
        main_layout.addWidget(buttons)

        self._wire_source_type_toggle()

    def _build_category_page(self, category: str) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        container = QWidget()
        form = QFormLayout(container)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        for spec in fields_for(category):
            widget = self._make_widget(spec)
            self._widgets[spec.key] = widget

            tooltip = tooltip_for(spec)
            if isinstance(widget, QWidget):
                widget.setToolTip(tooltip)

            hint = QLabel(spec.hint)
            hint.setProperty("role", "secondary")
            hint.setWordWrap(True)
            self._hint_labels[spec.key] = hint
            self._hint_texts[spec.key] = spec.hint

            field_layout = QVBoxLayout()
            field_layout.setSpacing(2)
            if isinstance(widget, QWidget):
                field_layout.addWidget(widget)
            field_layout.addWidget(hint)

            field_container = QWidget()
            field_container.setLayout(field_layout)

            label = QLabel(spec.label)
            label.setToolTip(tooltip)
            form.addRow(label, field_container)

        if category == "紀錄":
            clear_button = QPushButton(strings.CLEAR_DATA_BUTTON)
            clear_button.clicked.connect(self.clear_data_requested.emit)
            form.addRow(clear_button)

        scroll.setWidget(container)
        return scroll

    def _make_widget(self, spec: FieldSpec) -> object:
        if spec.widget == WidgetKind.FLOAT:
            float_widget = QDoubleSpinBox()
            if spec.minimum is not None:
                float_widget.setMinimum(spec.minimum)
            if spec.maximum is not None:
                float_widget.setMaximum(spec.maximum)
            if spec.step is not None:
                float_widget.setSingleStep(spec.step)
            if spec.decimals is not None:
                float_widget.setDecimals(spec.decimals)
            return float_widget

        if spec.widget == WidgetKind.INT:
            int_widget = QSpinBox()
            if spec.minimum is not None:
                int_widget.setMinimum(int(spec.minimum))
            if spec.maximum is not None:
                int_widget.setMaximum(int(spec.maximum))
            return int_widget

        if spec.widget == WidgetKind.CHOICE:
            if spec.key == DEVICE_FIELD_KEY:
                device_field = DeviceField(spec.choices or ())
                device_field.check_requested.connect(self._on_cuda_check_clicked)
                return device_field
            combo_widget = QComboBox()
            if spec.choices is not None:
                combo_widget.addItems(spec.choices)
            return combo_widget

        if spec.widget == WidgetKind.BOOL:
            return QCheckBox()

        if spec.widget == WidgetKind.PATH:
            if spec.key in SOUND_FIELD_KEYS:
                sound_field = SoundPathField()
                sound_field.preview_requested.connect(
                    lambda key=spec.key: self._on_preview_clicked(key)
                )
                return sound_field
            return PathField()

        return QLineEdit()

    def _populate(self) -> None:
        for spec in SCHEMA:
            widget = self._widgets.get(spec.key)
            if widget is None:
                continue

            value = get_value(self._config, spec.key)
            self._set_widget_value(widget, value)

    def _set_widget_value(self, widget: object, value: object) -> None:
        if isinstance(widget, QDoubleSpinBox):
            widget.setValue(float(str(value)))
        elif isinstance(widget, QSpinBox):
            widget.setValue(int(str(value)))
        elif isinstance(widget, QComboBox):
            index = widget.findText(str(value))
            if index >= 0:
                widget.setCurrentIndex(index)
        elif isinstance(widget, QCheckBox):
            widget.setChecked(bool(value))
        elif isinstance(widget, QLineEdit):
            widget.setText(str(value))
        elif isinstance(widget, PathField):
            widget.line_edit.setText(str(value))
        elif isinstance(widget, DeviceField):
            index = widget.combo.findText(str(value))
            if index >= 0:
                widget.combo.setCurrentIndex(index)

    def _wire_source_type_toggle(self) -> None:
        source_combo = self._widgets.get("source.type")
        if isinstance(source_combo, QComboBox):
            source_combo.currentTextChanged.connect(self._on_source_type_changed)
            self._on_source_type_changed(source_combo.currentText())

    def _on_source_type_changed(self, source_type: str) -> None:
        is_rtsp = source_type == "rtsp"
        for key, enabled in (
            ("source.rtsp_url", is_rtsp),
            ("source.webcam_index", not is_rtsp),
        ):
            widget = self._widgets.get(key)
            if isinstance(widget, QWidget):
                widget.setEnabled(enabled)

    # ------------------------------------------------------------------
    # 試聽（需求三 FR-3.1～3.7）
    # ------------------------------------------------------------------

    def _wire_preview_player_signals(self) -> None:
        """接上共享播放器的播放結束／錯誤通知（僅 QtSoundPlayer 具備）。

        注入的 FakePlayer 等替身沒有底層 QMediaPlayer，安靜略過。
        """
        inner = getattr(self._preview_player, "_player", None)
        if isinstance(inner, QMediaPlayer):
            inner.playbackStateChanged.connect(self._on_preview_playback_state)
            inner.errorOccurred.connect(self._on_preview_error)

    def _on_preview_clicked(self, key: str) -> None:
        field = self._widgets.get(key)
        if not isinstance(field, SoundPathField):
            return

        if self._preview_key == key:
            # FR-3.2：播放中再按 → 立即停止。
            self._stop_preview()
            return

        # FR-3.4：同時僅允許一個試聽。
        self._stop_preview()

        # FR-3.3：以欄位目前輸入值為準（未儲存）。
        path = field.line_edit.text()
        if not path or not Path(path).exists():
            # FR-3.6：不播放、不崩潰，於 hint 區顯示錯誤。
            self._set_preview_hint_error(key)
            return

        self._clear_preview_hint(key)
        self._preview_started_key = key
        self._preview_player.play(path)
        self._preview_key = key
        field.set_previewing(True)

    def _stop_preview(self) -> None:
        key = self._preview_key
        if key is None:
            return
        self._preview_key = None
        self._preview_player.stop()
        field = self._widgets.get(key)
        if isinstance(field, SoundPathField):
            field.set_previewing(False)

    def _on_preview_playback_state(self, state: QMediaPlayer.PlaybackState) -> None:
        # 單次播放自然結束 → 按鈕復原為「試聽」。
        if state != QMediaPlayer.PlaybackState.StoppedState:
            return
        key = self._preview_key
        if key is None:
            return
        self._preview_key = None
        field = self._widgets.get(key)
        if isinstance(field, SoundPathField):
            field.set_previewing(False)

    def _on_preview_error(self, _error: QMediaPlayer.Error, _error_string: str) -> None:
        # FR-3.6：無法解碼等播放錯誤 → 該欄位 hint 顯示錯誤、按鈕復原。
        # StoppedState 可能先於 errorOccurred 抵達並清掉 _preview_key，
        # 此時回退用最後一次啟動試聽的欄位 key。
        key = self._preview_key or self._preview_started_key
        if key is None:
            return
        self._preview_key = None
        field = self._widgets.get(key)
        if isinstance(field, SoundPathField):
            field.set_previewing(False)
        self._set_preview_hint_error(key)

    def _set_preview_hint_error(self, key: str) -> None:
        self._set_hint(key, strings.SOUND_PREVIEW_ERROR, "danger")

    def _clear_preview_hint(self, key: str) -> None:
        self._set_hint(key, self._hint_texts[key], "secondary")

    def _set_hint(self, key: str, text: str, role: str) -> None:
        hint = self._hint_labels.get(key)
        if hint is None:
            return
        hint.setText(text)
        hint.setProperty("role", role)
        style = hint.style()
        style.unpolish(hint)
        style.polish(hint)

    # ------------------------------------------------------------------
    # GPU CUDA 檢查（需求一 FR-1.1～1.5）
    # ------------------------------------------------------------------

    def _on_cuda_check_clicked(self) -> None:
        if self._cuda_check_running:
            return  # FR-1.2：防重入（檢查進行中再點無效）
        field = self._widgets.get(DEVICE_FIELD_KEY)
        if not isinstance(field, DeviceField):
            return

        self._cuda_check_running = True
        field.set_checking(True)

        bridge = _CudaCheckBridge()
        bridge.finished.connect(self._on_cuda_check_finished)
        self._cuda_bridge = bridge  # 保持存活直到結果回來
        QThreadPool.globalInstance().start(_CudaCheckRunnable(self._cuda_checker, bridge))

    def _on_cuda_check_finished(self, result: object) -> None:
        sender = self.sender()
        if sender is not self._cuda_bridge:
            # 已取消／已被新檢查取代的舊 bridge 的遲到結果：忽略，不得復原
            # 按鈕或彈出對話框（防重入語意，FR-1.2）。結果已送達，舊 bridge
            # 可自 stale 清單釋放（在主執行緒銷毀）。
            if isinstance(sender, _CudaCheckBridge) and sender in self._stale_cuda_bridges:
                self._stale_cuda_bridges.remove(sender)
            return
        if not self._cuda_check_running:
            return  # 視窗關閉後的遲到結果：忽略，不對 UI 動作
        self._cuda_check_running = False
        self._cuda_bridge = None
        field = self._widgets.get(DEVICE_FIELD_KEY)
        if isinstance(field, DeviceField):
            field.set_checking(False)
        if isinstance(result, CudaCheckResult):
            QMessageBox.information(self, strings.CUDA_CHECK_TITLE, format_cuda_report(result))

    def _cancel_cuda_check(self) -> None:
        """視窗關閉時取消進行中的檢查：復原按鈕並使遲到結果被忽略。"""
        if not self._cuda_check_running:
            return
        self._cuda_check_running = False
        bridge = self._cuda_bridge
        if bridge is not None:
            # 斷開舊 bridge，遲到結果不再驅動 UI；保留主執行緒參考，避免
            # runnable 在 QThreadPool 執行緒被 autoDelete 時，連帶從背景
            # 執行緒銷毀這個 main-thread affinity 的 QObject。
            bridge.finished.disconnect(self._on_cuda_check_finished)
            self._stale_cuda_bridges.append(bridge)
        self._cuda_bridge = None
        field = self._widgets.get(DEVICE_FIELD_KEY)
        if isinstance(field, DeviceField):
            field.set_checking(False)

    def done(self, result: int) -> None:
        # FR-3.5：設定視窗關閉（儲存或取消）時自動停止試聽。
        self._stop_preview()
        self._cancel_cuda_check()
        super().done(result)

    # ------------------------------------------------------------------
    # 儲存
    # ------------------------------------------------------------------

    def _on_save(self) -> None:
        candidate = self._read_widgets_to_config()
        raw = config_module._serialize_app_config(candidate)
        errors = validate(raw)
        if errors:
            self._show_validation_errors(errors)
            return

        save_config(candidate, self._config_path)
        self._config = candidate
        QMessageBox.information(self, strings.SETTINGS_TITLE, strings.SETTINGS_SAVED_RESTART)
        self.accept()

    def _read_widgets_to_config(self) -> AppConfig:
        # §4.7：以磁碟上的最新 config 為基底，SCHEMA 外的欄位（如 presence.roi）
        # 才不會被啟動時注入的舊值覆寫；磁碟讀取失敗時退回啟動注入值。
        try:
            cfg = load_config(self._config_path)
        except ConfigError:
            cfg = self._config
        for spec in SCHEMA:
            widget = self._widgets.get(spec.key)
            if widget is None:
                continue
            value = self._get_widget_value(widget, spec)
            if value is not None:
                cfg = set_value(cfg, spec.key, value)
        return cfg

    def _get_widget_value(self, widget: object, spec: FieldSpec) -> object | None:
        if isinstance(widget, QDoubleSpinBox):
            return widget.value()
        if isinstance(widget, QSpinBox):
            return widget.value()
        if isinstance(widget, QComboBox):
            value = widget.currentText()
            return value
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QLineEdit):
            return widget.text()
        if isinstance(widget, PathField):
            return widget.line_edit.text()
        if isinstance(widget, DeviceField):
            return widget.combo.currentText()
        return None

    def _show_validation_errors(self, errors: list[str]) -> None:
        for key in self._hint_labels:
            self._set_hint(key, self._hint_texts[key], "secondary")

        for error in errors:
            key_prefix = error.split(" ")[0]
            for field_key in self._hint_labels:
                if field_key.startswith(key_prefix):
                    self._set_hint(field_key, error, "danger")


SettingsDialog = SettingsWindow
