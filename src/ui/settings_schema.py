from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.config import MINUTE_MAX, MINUTE_MIN, AppConfig


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
    tooltip: str | None = None


CATEGORIES: tuple[str, ...] = ("基本", "偵測", "提醒", "紀錄", "進階", "強制休息")


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
        "timer.rest_count_mode",
        "休息計算方式",
        "presence＝必須離座才算休息；fixed＝固定倒數。",
        WidgetKind.CHOICE,
        "基本",
        choices=("presence", "fixed"),
        tooltip="presence＝必須離開鏡頭前方才算休息，回來即結束休息；fixed＝休息時間到就結束，不論是否仍在鏡頭前。",
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
        tooltip=(
            "例如設為 0.5 表示模型信心需達 50% 以上才視為偵測到人；"
            "調高可減少誤判，調低可減少漏判。"
        ),
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
        tooltip="例如設為 0.3 表示偵測框高度需達畫面高度的 30% 以上，可過濾掉遠處或誤判的小框。",
    ),
    FieldSpec(
        "presence.debounce_count",
        "去抖動次數",
        "連續幾次判定一致才改變在場狀態，避免閃爍誤判。",
        WidgetKind.INT,
        "偵測",
        minimum=1,
        tooltip=(
            "例如設為 3，需連續 3 次偵測結果相同才會切換在場／離開狀態，"
            "數值越大越穩定但反應越慢。"
        ),
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
        tooltip="popup＝畫面中央彈出視窗；toast＝右下角系統通知；floating＝畫面角落的小型置頂倒數視窗。",
    ),
    FieldSpec(
        "reminder.reminding_display_mode",
        "提醒中顯示",
        "提醒中要顯示「超時時間」還是「工作時間＋提醒持續時間」。",
        WidgetKind.CHOICE,
        "提醒",
        choices=("overtime", "work_and_reminder"),
        tooltip="overtime＝只顯示超過工作門檻多久；work_and_reminder＝同時顯示本次工作時間與提醒已持續時間。",
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
        tooltip=(
            "auto＝自動偵測並優先使用 GPU；cpu＝強制使用 CPU（較慢但相容性最佳）；"
            "cuda＝強制使用 NVIDIA GPU（需安裝對應 CUDA 驅動）。"
        ),
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
    # 提醒分類 — return_sound
    FieldSpec(
        "reminder.return_sound.enabled",
        "回來提示音效",
        "離開後返回時，是否在「歡迎回來」視窗播放提示音效。",
        WidgetKind.BOOL,
        "提醒",
        tooltip="開啟後，系統判定你回到座位並彈出「歡迎回來」視窗時，"
        "會循環播放下方音效檔，直到按下確認鈕為止。",
    ),
    FieldSpec(
        "reminder.return_sound.sound_path",
        "回來提示音效檔",
        "「歡迎回來」視窗播放的音效檔路徑。",
        WidgetKind.PATH,
        "提醒",
        tooltip="留空或檔案不存在時會自動靜音，不會造成錯誤或當機。",
    ),
    # 強制休息分類 — force_lock
    FieldSpec(
        "force_lock.enabled",
        "啟用強制休息鎖定",
        "是否在達到設定條件時自動鎖定螢幕，強制使用者離開休息。",
        WidgetKind.BOOL,
        "強制休息",
        tooltip="預設關閉。開啟後請依下列欄位設定觸發時機與警示方式。",
    ),
    FieldSpec(
        "force_lock.trigger",
        "觸發時機",
        "overtime＝工作超時達門檻時鎖定；on_rest＝一進入休息狀態就鎖定。",
        WidgetKind.CHOICE,
        "強制休息",
        choices=("overtime", "on_rest"),
        tooltip="overtime＝提醒後持續超時超過下方「超時門檻」才鎖定；"
        "on_rest＝只要進入休息狀態就立刻鎖定，督促確實離開座位。",
    ),
    FieldSpec(
        "force_lock.warning_mode",
        "鎖定前警示方式",
        "immediate＝立即鎖定；countdown_cancel＝倒數並可取消；countdown_only＝倒數但不可取消。",
        WidgetKind.CHOICE,
        "強制休息",
        choices=("immediate", "countdown_cancel", "countdown_only"),
        tooltip="immediate＝直接鎖定螢幕，不另行警示；"
        "countdown_cancel＝顯示倒數視窗，期間可按「取消本次鎖定」中止；"
        "countdown_only＝顯示倒數視窗但無法取消，倒數結束必定鎖定。",
    ),
    FieldSpec(
        "force_lock.overtime_threshold_min",
        "超時門檻（分鐘）",
        "觸發時機為 overtime 時，超過工作門檻多久後觸發鎖定。",
        WidgetKind.FLOAT,
        "強制休息",
        minimum=MINUTE_MIN,
        maximum=MINUTE_MAX,
        step=0.1,
        decimals=1,
        tooltip="僅當「觸發時機」為 overtime 時生效；"
        "計算起點為進入提醒狀態之後累積的超時秒數。",
    ),
    FieldSpec(
        "force_lock.countdown_sec",
        "鎖定倒數秒數",
        "鎖定前警示方式為倒數模式時，鎖定前的倒數秒數。",
        WidgetKind.INT,
        "強制休息",
        minimum=1,
        tooltip="僅當「鎖定前警示方式」為 countdown_cancel 或 countdown_only 時生效。",
    ),
)


def fields_for(category: str) -> tuple[FieldSpec, ...]:
    return tuple(field for field in SCHEMA if field.category == category)


def tooltip_for(spec: FieldSpec) -> str:
    return spec.tooltip or spec.hint


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
