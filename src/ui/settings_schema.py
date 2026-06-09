from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.config import MINUTE_MAX, MINUTE_MIN, AppConfig
from src.types import ResetMode


class WidgetKind(Enum):
    TEXT = "text"
    INT = "int"
    FLOAT = "float"
    CHOICE = "choice"
    PATH = "path"
    BOOL = "bool"


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    hint: str
    widget: WidgetKind
    category: str
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    decimals: int | None = None
    choices: tuple[str, ...] | None = None


CATEGORIES: tuple[str, ...] = ("基本", "偵測", "提醒", "紀錄", "進階")


SCHEMA: tuple[FieldSpec, ...] = (
    FieldSpec(
        "source.type",
        "影像來源",
        "選擇影像來源：網路串流（RTSP）或本機 Webcam。",
        WidgetKind.CHOICE,
        "基本",
        choices=("rtsp", "webcam"),
    ),
    FieldSpec(
        "source.rtsp_url",
        "RTSP 位址",
        "RTSP 串流位址，例 rtsp://帳號:密碼@主機:554/stream。",
        WidgetKind.TEXT,
        "基本",
    ),
    FieldSpec(
        "source.webcam_index",
        "Webcam 編號",
        "本機攝影機編號，通常 0 是內建鏡頭。",
        WidgetKind.INT,
        "基本",
        minimum=0,
    ),
    FieldSpec(
        "timer.work_threshold_min",
        "工作門檻（分鐘）",
        "連續工作達此時間就提醒休息。",
        WidgetKind.FLOAT,
        "基本",
        minimum=MINUTE_MIN,
        maximum=MINUTE_MAX,
        step=0.1,
        decimals=1,
    ),
    FieldSpec(
        "timer.reset_threshold_min",
        "重置門檻（分鐘）",
        "離開超過此時間，才把工作計時歸零。",
        WidgetKind.FLOAT,
        "基本",
        minimum=MINUTE_MIN,
        maximum=MINUTE_MAX,
        step=0.1,
        decimals=1,
    ),
    FieldSpec(
        "timer.required_rest_min",
        "休息門檻（分鐘）",
        "離開達此時間才算真正完成休息。",
        WidgetKind.FLOAT,
        "基本",
        minimum=MINUTE_MIN,
        maximum=MINUTE_MAX,
        step=0.1,
        decimals=1,
    ),
    FieldSpec(
        "detection.confidence",
        "偵測把握度",
        "人體偵測的最低把握度，越高越嚴格、誤判越少但可能漏抓。",
        WidgetKind.FLOAT,
        "偵測",
        minimum=0.05,
        maximum=1.0,
        step=0.05,
        decimals=2,
    ),
    FieldSpec(
        "presence.min_box_height_ratio",
        "最小人體高度比例",
        "人體框需占畫面高度的最小比例，用來濾掉遠處的人。",
        WidgetKind.FLOAT,
        "偵測",
        minimum=0.05,
        maximum=1.0,
        step=0.05,
        decimals=2,
    ),
    FieldSpec(
        "presence.debounce_count",
        "去抖動次數",
        "連續幾次判定一致才改變在場狀態，避免閃爍誤判。",
        WidgetKind.INT,
        "偵測",
        minimum=1,
    ),
    FieldSpec(
        "detection.interval_sec",
        "偵測間隔（秒）",
        "每隔幾秒做一次偵測，越短越即時但越耗資源。",
        WidgetKind.FLOAT,
        "偵測",
        minimum=0.1,
        step=0.1,
        decimals=1,
    ),
    FieldSpec(
        "reminder.method",
        "提醒方式",
        "提醒呈現方式：彈出視窗、系統通知、置頂懸浮倒數。",
        WidgetKind.CHOICE,
        "提醒",
        choices=("popup", "toast", "floating"),
    ),
    FieldSpec(
        "reminder.reset_mode",
        "提醒重置方式",
        "提醒後如何重置：離開才重置 / 按掉即重置 / 先貪睡。",
        WidgetKind.CHOICE,
        "提醒",
        choices=tuple(mode.value for mode in ResetMode),
    ),
    FieldSpec(
        "reminder.repeat_interval_min",
        "重複提醒間隔（分鐘）",
        "未處理時，每隔多久再提醒一次。",
        WidgetKind.FLOAT,
        "提醒",
        minimum=MINUTE_MIN,
        maximum=MINUTE_MAX,
        step=0.1,
        decimals=1,
    ),
    FieldSpec(
        "reminder.snooze_min",
        "貪睡時間（分鐘）",
        "按下貪睡後，延後多久再次提醒。",
        WidgetKind.FLOAT,
        "提醒",
        minimum=MINUTE_MIN,
        maximum=MINUTE_MAX,
        step=0.1,
        decimals=1,
    ),
    FieldSpec(
        "reminder.popup.media_path",
        "提醒媒體路徑",
        "提醒時顯示的圖片或影片檔路徑。",
        WidgetKind.PATH,
        "提醒",
    ),
    FieldSpec(
        "reminder.popup.media_type",
        "媒體類型",
        "上面媒體的類型。",
        WidgetKind.CHOICE,
        "提醒",
        choices=("image", "video"),
    ),
    FieldSpec(
        "reminder.popup.sound_path",
        "音效路徑",
        "提醒時播放的音效檔，留空則不播放。",
        WidgetKind.PATH,
        "提醒",
    ),
    FieldSpec(
        "reminder.floating.position",
        "懸浮視窗位置",
        "置頂懸浮倒數視窗出現的位置。",
        WidgetKind.CHOICE,
        "提醒",
        choices=("top-right", "top-left", "bottom-right", "bottom-left"),
    ),
    FieldSpec(
        "logging.enabled",
        "啟用紀錄",
        "是否把工作 / 休息紀錄寫入資料庫。",
        WidgetKind.BOOL,
        "紀錄",
    ),
    FieldSpec(
        "logging.db_path",
        "資料庫路徑",
        "紀錄資料庫（SQLite）檔案位置。",
        WidgetKind.PATH,
        "紀錄",
    ),
    FieldSpec(
        "detection.model_path",
        "模型路徑",
        "YOLOv8 模型權重檔路徑。",
        WidgetKind.PATH,
        "進階",
    ),
    FieldSpec(
        "detection.device",
        "運算裝置",
        "運算裝置：自動 / CPU / GPU（CUDA）。",
        WidgetKind.CHOICE,
        "進階",
        choices=("auto", "cpu", "cuda"),
    ),
    FieldSpec(
        "source.reconnect_interval_sec",
        "重連間隔（秒）",
        "串流斷線後，每隔幾秒嘗試重新連線。",
        WidgetKind.FLOAT,
        "進階",
        minimum=0.5,
        step=0.5,
        decimals=1,
    ),
    FieldSpec(
        "ui.start_minimized",
        "啟動時最小化",
        "啟動時直接最小化到系統匣。",
        WidgetKind.BOOL,
        "進階",
    ),
)


def fields_for(category: str) -> tuple[FieldSpec, ...]:
    return tuple(field for field in SCHEMA if field.category == category)


def get_value(cfg: AppConfig, key: str) -> Any:
    parts = key.split(".")
    obj: Any = cfg
    for part in parts:
        obj = getattr(obj, part)
    return obj


def set_value(cfg: AppConfig, key: str, value: Any) -> AppConfig:
    parts = key.split(".")
    if len(parts) == 2:
        section, field = parts
        sub = getattr(cfg, section)
        new_sub = dataclasses.replace(sub, **{field: value})
        return dataclasses.replace(cfg, **{section: new_sub})

    if len(parts) == 3:
        section, subsection, field = parts
        sub = getattr(cfg, section)
        subsub = getattr(sub, subsection)
        new_subsub = dataclasses.replace(subsub, **{field: value})
        new_sub = dataclasses.replace(sub, **{subsection: new_subsub})
        return dataclasses.replace(cfg, **{section: new_sub})

    raise ValueError(f"Unsupported key depth: {key}")
