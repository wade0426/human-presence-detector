from __future__ import annotations

from datetime import datetime

from src.app.clear_data import ClearDataService, ClearScope
from src.config import AppConfig, TimerConfig, save_config
from src.logging_store import SessionStore


def _make_store(tmp_path) -> SessionStore:
    store = SessionStore(str(tmp_path / "records.sqlite"))
    store.init_schema()
    return store


def test_clear_today_scope(tmp_path) -> None:
    store = _make_store(tmp_path)
    config_path = str(tmp_path / "config.yaml")
    service = ClearDataService(store, config_path)

    # 寫今日一筆、非今日一筆
    today = datetime.now()
    store.log_session("work", today, today, 100, "auto")
    # 手動插入昨日一筆
    conn = store._get_connection()
    conn.execute(
        "INSERT INTO sessions (type, start_ts, end_ts, duration_sec, ended_by) VALUES (?,?,?,?,?)",
        ("work", "2020-01-01T10:00:00", "2020-01-01T10:01:00", 60, "auto"),
    )
    conn.commit()

    result = service.clear(ClearScope.TODAY)

    assert result.deleted == 1
    assert result.reset_config is False
    # 昨日列仍在
    count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    assert count == 1


def test_clear_all_scope(tmp_path) -> None:
    store = _make_store(tmp_path)
    config_path = str(tmp_path / "config.yaml")
    service = ClearDataService(store, config_path)

    today = datetime.now()
    store.log_session("work", today, today, 100, "auto")
    store.log_session("rest", today, today, 60, "auto")

    result = service.clear(ClearScope.ALL)

    assert result.deleted == 2
    assert result.reset_config is False
    summary = store.today_summary()
    assert summary.work_seconds == 0
    assert summary.rest_count == 0


def test_clear_all_and_reset_writes_default_config(tmp_path) -> None:
    store = _make_store(tmp_path)
    config_path = str(tmp_path / "config.yaml")

    # 寫入非預設設定（使用 webcam 避免 rtsp_url 驗證問題）
    custom = AppConfig(timer=TimerConfig(work_threshold_min=99.0))
    custom.source.type = "webcam"
    save_config(custom, config_path)

    today = datetime.now()
    store.log_session("work", today, today, 100, "auto")

    service = ClearDataService(store, config_path)
    result = service.clear(ClearScope.ALL_AND_RESET)

    assert result.reset_config is True
    # 驗證 YAML 已被重寫為預設值
    from pathlib import Path

    import yaml
    raw = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    # timer.work_threshold_min 應已恢復預設值 45.0
    assert raw["timer"]["work_threshold_min"] == TimerConfig().work_threshold_min
    # source.type 應已恢復預設值 "rtsp"
    assert raw["source"]["type"] == "rtsp"
