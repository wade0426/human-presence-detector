"""T9：音檔試聽（FR-3.1～3.7）、FR-2.7 瀏覽過濾、§4.7 settings 以磁碟為基底（移植）。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QComboBox

from src.infra.config import AppConfig, load_config, save_config
from src.shell import strings
from src.shell.settings.preview import SoundPathField
from src.shell.settings.window import SOUND_FIELD_KEYS, SettingsWindow
from src.types import BBox


class FakePlayer:
    def __init__(self) -> None:
        self.play_calls: list[str] = []
        self.stop_calls: int = 0

    def play(self, sound_path: str) -> None:
        self.play_calls.append(sound_path)

    def stop(self) -> None:
        self.stop_calls += 1


def _make_window(
    qtbot: pytest.QtBot, tmp_path: Path, player: FakePlayer | None = None
) -> SettingsWindow:
    window = SettingsWindow(
        AppConfig(),
        config_path=str(tmp_path / "cfg.yaml"),
        preview_player=player,
    )
    qtbot.addWidget(window)
    return window


def _sound_file(tmp_path: Path, name: str = "beep.wav") -> str:
    path = tmp_path / name
    path.write_bytes(b"RIFF0000WAVE")
    return str(path)


# ---------------------------------------------------------------------------
# FR-3.1：兩個音檔欄位各含試聽按鈕
# ---------------------------------------------------------------------------


@pytest.mark.qt
def test_sound_fields_have_preview_button(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    window = _make_window(qtbot, tmp_path)

    for key in SOUND_FIELD_KEYS:
        widget = window._widgets.get(key)
        assert isinstance(widget, SoundPathField), f"{key} should be a SoundPathField"
        assert widget.preview_button.text() == strings.SOUND_PREVIEW_PLAY


@pytest.mark.qt
def test_preview_button_has_speaker_icon(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    window = _make_window(qtbot, tmp_path)

    for key in SOUND_FIELD_KEYS:
        field = window._widgets[key]
        assert isinstance(field, SoundPathField)
        play_icon = field.preview_button.icon()
        assert not play_icon.isNull(), f"{key} preview button must carry an icon"

        field.set_previewing(True)
        stop_icon = field.preview_button.icon()
        assert not stop_icon.isNull()
        assert stop_icon.cacheKey() != play_icon.cacheKey()

        field.set_previewing(False)
        assert field.preview_button.icon().cacheKey() == play_icon.cacheKey()


# ---------------------------------------------------------------------------
# FR-3.2 / FR-3.3：按下播放欄位目前輸入值；播放中再按即停止
# ---------------------------------------------------------------------------


@pytest.mark.qt
def test_preview_plays_current_field_text(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    fake = FakePlayer()
    window = _make_window(qtbot, tmp_path, fake)
    sound = _sound_file(tmp_path)

    for key in SOUND_FIELD_KEYS:
        fake.play_calls.clear()
        field = window._widgets[key]
        assert isinstance(field, SoundPathField)
        field.line_edit.setText(sound)  # 未儲存的修改（FR-3.3）
        field.preview_button.click()
        assert fake.play_calls == [sound]
        assert field.preview_button.text() == strings.SOUND_PREVIEW_STOP
        field.preview_button.click()  # 停掉，避免影響下一輪


@pytest.mark.qt
def test_preview_toggle_stops_playback(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    fake = FakePlayer()
    window = _make_window(qtbot, tmp_path, fake)
    sound = _sound_file(tmp_path)

    key = SOUND_FIELD_KEYS[0]
    field = window._widgets[key]
    assert isinstance(field, SoundPathField)
    field.line_edit.setText(sound)

    field.preview_button.click()
    assert fake.play_calls == [sound]

    field.preview_button.click()  # 播放中再按 → 停止
    assert fake.stop_calls >= 1
    assert fake.play_calls == [sound]  # 不應再播第二次
    assert field.preview_button.text() == strings.SOUND_PREVIEW_PLAY


# ---------------------------------------------------------------------------
# FR-3.4：同時僅一個試聽；FR-3.5：視窗關閉自動停止
# ---------------------------------------------------------------------------


@pytest.mark.qt
def test_second_preview_stops_first(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    fake = FakePlayer()
    window = _make_window(qtbot, tmp_path, fake)
    sound_a = _sound_file(tmp_path, "a.wav")
    sound_b = _sound_file(tmp_path, "b.wav")

    field_a = window._widgets[SOUND_FIELD_KEYS[0]]
    field_b = window._widgets[SOUND_FIELD_KEYS[1]]
    assert isinstance(field_a, SoundPathField)
    assert isinstance(field_b, SoundPathField)
    field_a.line_edit.setText(sound_a)
    field_b.line_edit.setText(sound_b)

    field_a.preview_button.click()
    assert fake.play_calls == [sound_a]

    field_b.preview_button.click()  # A 播放中啟動 B
    assert fake.stop_calls >= 1
    assert fake.play_calls == [sound_a, sound_b]
    assert field_a.preview_button.text() == strings.SOUND_PREVIEW_PLAY
    assert field_b.preview_button.text() == strings.SOUND_PREVIEW_STOP


@pytest.mark.qt
def test_close_window_stops_preview(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    fake = FakePlayer()
    window = _make_window(qtbot, tmp_path, fake)
    sound = _sound_file(tmp_path)

    field = window._widgets[SOUND_FIELD_KEYS[0]]
    assert isinstance(field, SoundPathField)
    field.line_edit.setText(sound)
    field.preview_button.click()
    assert fake.play_calls == [sound]

    window.reject()  # 取消關閉（done() 路徑）
    assert fake.stop_calls >= 1
    assert field.preview_button.text() == strings.SOUND_PREVIEW_PLAY


# ---------------------------------------------------------------------------
# FR-3.6：無效路徑 → 不播放、hint 顯示錯誤（role=danger）；成功播放時清除
# ---------------------------------------------------------------------------


@pytest.mark.qt
def test_invalid_path_shows_error_hint(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    fake = FakePlayer()
    window = _make_window(qtbot, tmp_path, fake)

    key = SOUND_FIELD_KEYS[0]
    field = window._widgets[key]
    assert isinstance(field, SoundPathField)
    hint = window._hint_labels[key]

    field.line_edit.setText(str(tmp_path / "missing.mp3"))
    field.preview_button.click()  # 不應拋例外
    assert fake.play_calls == []
    assert hint.text() == strings.SOUND_PREVIEW_ERROR
    assert hint.property("role") == "danger"
    assert field.preview_button.text() == strings.SOUND_PREVIEW_PLAY


@pytest.mark.qt
def test_empty_path_shows_error_hint(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    fake = FakePlayer()
    window = _make_window(qtbot, tmp_path, fake)

    key = SOUND_FIELD_KEYS[1]
    field = window._widgets[key]
    assert isinstance(field, SoundPathField)
    field.line_edit.setText("")
    field.preview_button.click()
    assert fake.play_calls == []
    assert window._hint_labels[key].text() == strings.SOUND_PREVIEW_ERROR
    assert window._hint_labels[key].property("role") == "danger"


@pytest.mark.qt
def test_successful_preview_clears_error_hint(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    fake = FakePlayer()
    window = _make_window(qtbot, tmp_path, fake)
    sound = _sound_file(tmp_path)

    key = SOUND_FIELD_KEYS[0]
    field = window._widgets[key]
    assert isinstance(field, SoundPathField)
    hint = window._hint_labels[key]

    field.line_edit.setText("nope/does-not-exist.mp3")
    field.preview_button.click()
    assert hint.property("role") == "danger"

    field.line_edit.setText(sound)
    field.preview_button.click()  # 成功播放 → 清除錯誤
    assert fake.play_calls == [sound]
    assert hint.text() == window._hint_texts[key]
    assert hint.property("role") == "secondary"


# ---------------------------------------------------------------------------
# FR-3.6：檔案存在但無法解碼 → errorOccurred → hint 顯示錯誤、按鈕復原
# ---------------------------------------------------------------------------


@pytest.mark.qt
def test_undecodable_file_shows_error_hint_via_real_player(
    qtbot: pytest.QtBot, tmp_path: Path
) -> None:
    """不注入替身：預設 QtSoundPlayer 的 errorOccurred 必須驅動 hint 與按鈕復原。"""
    window = _make_window(qtbot, tmp_path)  # preview_player=None → 真 QtSoundPlayer

    bad = tmp_path / "garbage.mp3"
    bad.write_bytes(b"this is definitely not valid mp3 audio data" * 64)

    key = SOUND_FIELD_KEYS[0]
    field = window._widgets[key]
    assert isinstance(field, SoundPathField)
    hint = window._hint_labels[key]

    field.line_edit.setText(str(bad))
    field.preview_button.click()  # 檔案存在 → 通過 exists() 檢查，play() 真正執行

    qtbot.waitUntil(lambda: hint.text() == strings.SOUND_PREVIEW_ERROR, timeout=5000)
    assert hint.property("role") == "danger"
    assert field.preview_button.text() == strings.SOUND_PREVIEW_PLAY
    assert window._preview.active_key is None


@pytest.mark.qt
def test_preview_natural_finish_restores_button(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    """單次播放自然結束（StoppedState）→ 按鈕復原、active_key 清除。"""
    fake = FakePlayer()
    window = _make_window(qtbot, tmp_path, fake)
    sound = _sound_file(tmp_path)

    key = SOUND_FIELD_KEYS[0]
    field = window._widgets[key]
    assert isinstance(field, SoundPathField)
    field.line_edit.setText(sound)
    field.preview_button.click()
    assert field.preview_button.text() == strings.SOUND_PREVIEW_STOP

    window._preview._on_playback_state(QMediaPlayer.PlaybackState.StoppedState)

    assert field.preview_button.text() == strings.SOUND_PREVIEW_PLAY
    assert window._preview.active_key is None


@pytest.mark.qt
def test_preview_error_callback_restores_button_and_sets_hint(
    qtbot: pytest.QtBot, tmp_path: Path
) -> None:
    fake = FakePlayer()
    window = _make_window(qtbot, tmp_path, fake)
    sound = _sound_file(tmp_path)

    key = SOUND_FIELD_KEYS[1]
    field = window._widgets[key]
    assert isinstance(field, SoundPathField)
    hint = window._hint_labels[key]
    field.line_edit.setText(sound)
    field.preview_button.click()

    window._preview._on_error(QMediaPlayer.Error.FormatError, "boom")

    assert hint.text() == strings.SOUND_PREVIEW_ERROR
    assert hint.property("role") == "danger"
    assert field.preview_button.text() == strings.SOUND_PREVIEW_PLAY
    assert window._preview.active_key is None


@pytest.mark.qt
def test_preview_error_after_stop_state_still_shows_hint(
    qtbot: pytest.QtBot, tmp_path: Path
) -> None:
    """QMediaPlayer 可能先發 StoppedState 再發 errorOccurred：hint 仍須標示錯誤欄位。"""
    fake = FakePlayer()
    window = _make_window(qtbot, tmp_path, fake)
    sound = _sound_file(tmp_path)

    key = SOUND_FIELD_KEYS[0]
    field = window._widgets[key]
    assert isinstance(field, SoundPathField)
    field.line_edit.setText(sound)
    field.preview_button.click()

    window._preview._on_playback_state(QMediaPlayer.PlaybackState.StoppedState)
    assert field.preview_button.text() == strings.SOUND_PREVIEW_PLAY

    window._preview._on_error(QMediaPlayer.Error.FormatError, "boom")

    assert window._hint_labels[key].text() == strings.SOUND_PREVIEW_ERROR
    assert window._hint_labels[key].property("role") == "danger"


# ---------------------------------------------------------------------------
# FR-2.7：音檔欄位的瀏覽對話框需帶副檔名過濾
# ---------------------------------------------------------------------------


@pytest.mark.qt
def test_sound_field_browse_uses_audio_filter(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    window = _make_window(qtbot, tmp_path)

    for key in SOUND_FIELD_KEYS:
        field = window._widgets[key]
        assert isinstance(field, SoundPathField)
        with patch(
            "src.shell.settings.preview.QFileDialog.getOpenFileName", return_value=("", "")
        ) as mock_open:
            field._browse()
        filter_arg = mock_open.call_args.args[-1]
        assert "*.mp3 *.wav" in filter_arg


@pytest.mark.qt
def test_non_sound_path_field_browse_has_no_audio_filter(
    qtbot: pytest.QtBot, tmp_path: Path
) -> None:
    window = _make_window(qtbot, tmp_path)

    field = window._widgets["logging.db_path"]
    assert not isinstance(field, SoundPathField)
    with patch(
        "src.shell.settings.preview.QFileDialog.getOpenFileName", return_value=("", "")
    ) as mock_open:
        field._browse()  # type: ignore[attr-defined]
    filter_arg = mock_open.call_args.args[-1]
    assert "*.mp3" not in filter_arg


# ---------------------------------------------------------------------------
# §4.7：儲存時以磁碟 config 為基底，SCHEMA 外欄位（presence.roi）不被舊值覆寫
# ---------------------------------------------------------------------------


@pytest.mark.qt
def test_save_preserves_disk_roi_over_stale_config(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    cfg_path = tmp_path / "cfg.yaml"
    disk_roi = BBox(0.1, 0.1, 0.5, 0.5)

    disk_cfg = AppConfig()
    disk_cfg.source.type = "webcam"
    disk_cfg.presence.roi = disk_roi
    save_config(disk_cfg, str(cfg_path))

    stale_cfg = AppConfig()  # 啟動時注入的舊 config（roi 為預設值）
    assert stale_cfg.presence.roi != disk_roi

    window = SettingsWindow(stale_cfg, config_path=str(cfg_path))
    qtbot.addWidget(window)

    combo = window._widgets["source.type"]
    assert isinstance(combo, QComboBox)
    combo.setCurrentText("webcam")

    with patch("src.shell.settings.window.QMessageBox.information"):
        window._on_save()

    reloaded = load_config(str(cfg_path))
    assert reloaded.presence.roi == disk_roi
