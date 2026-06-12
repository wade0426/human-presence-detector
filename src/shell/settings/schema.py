"""設定頁 schema v2：欄位規格、分類與 AppConfig 取值/寫值。

自舊 ``src/ui/settings_schema.py`` 移植並改為 v2 鍵空間：

- 分類改為（基本／偵測／提醒／休息流程／紀錄／進階），移除「強制休息」。
- ``force_lock.*`` 欄位移除（被升級階梯吸收，spec §12）。
- 新增 ``rest_flow.*`` 欄位；``stage_after_sec`` 以三個虛擬鍵
  （``stage1_sec``／``stage2_sec``／``stage3_sec``）對映 tuple 索引，
  ``get_value``／``set_value`` 負責索引對映，存檔時由 dataclass 序列化組回 list。
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.infra.config import MINUTE_MAX, MINUTE_MIN, AppConfig


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


CATEGORIES: tuple[str, ...] = ("基本", "偵測", "提醒", "休息流程", "紀錄", "進階")

# stage_after_sec 的三個虛擬鍵 → tuple 索引（v2 設定頁以三欄呈現）。
STAGE_FIELD_KEYS: dict[str, int] = {
    "rest_flow.escalation.stage1_sec": 0,
    "rest_flow.escalation.stage2_sec": 1,
    "rest_flow.escalation.stage3_sec": 2,
}

# CHOICE widget 取值為字串、dataclass 欄位為 int 的鍵（set_value 需轉型）。
_MAX_STAGE_KEY = "rest_flow.escalation.max_stage"

# 秒數欄位的 QSpinBox 上限（未設上限時 Qt 預設 99，會砍掉預設值 120/180）。
_SECONDS_MAX = 86400.0


SCHEMA: tuple[FieldSpec, ...] = (
    # ------------------------------------------------------------------ 基本
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
        tooltip=(
            "presence＝必須離開鏡頭前方才算休息，回來即結束休息；"
            "fixed＝休息時間到就結束，不論是否仍在鏡頭前。"
        ),
    ),
    # ------------------------------------------------------------------ 偵測
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
        "detection.min_box_height_ratio",
        "最小人體高度比例",
        "人體框需占畫面高度的最小比例，用來濾掉遠處的人。",
        WidgetKind.FLOAT,
        "偵測",
        minimum=0.05,
        maximum=1.0,
        step=0.05,
        decimals=2,
        tooltip=(
            "例如設為 0.3 表示偵測框高度需達畫面高度的 30% 以上，"
            "可過濾掉遠處或誤判的小框。"
        ),
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
    # ------------------------------------------------------------------ 提醒
    FieldSpec(
        "reminder.method",
        "提醒方式",
        "提醒呈現方式：彈出視窗、系統通知、置頂懸浮倒數。",
        WidgetKind.CHOICE,
        "提醒",
        choices=("popup", "toast", "floating"),
        tooltip=(
            "popup＝畫面中央彈出視窗；toast＝右下角系統通知；"
            "floating＝畫面角落的小型置頂倒數視窗。"
        ),
    ),
    FieldSpec(
        "reminder.reminding_display_mode",
        "提醒中顯示",
        "提醒中要顯示「超時時間」還是「工作時間＋提醒持續時間」。",
        WidgetKind.CHOICE,
        "提醒",
        choices=("overtime", "work_and_reminder"),
        tooltip=(
            "overtime＝只顯示超過工作門檻多久；"
            "work_and_reminder＝同時顯示本次工作時間與提醒已持續時間。"
        ),
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
        "reminder.return_sound.enabled",
        "回來提示音效",
        "離開後返回時，是否在「歡迎回來」視窗播放提示音效。",
        WidgetKind.BOOL,
        "提醒",
        tooltip=(
            "開啟後，系統判定你回到座位並彈出「歡迎回來」視窗時，"
            "會循環播放下方音效檔，直到按下確認鈕為止。"
        ),
    ),
    FieldSpec(
        "reminder.return_sound.sound_path",
        "回來提示音效檔",
        "「歡迎回來」視窗播放的音效檔路徑。",
        WidgetKind.PATH,
        "提醒",
        tooltip="留空或檔案不存在時會自動靜音，不會造成錯誤或當機。",
    ),
    # -------------------------------------------------------------- 休息流程
    FieldSpec(
        "rest_flow.pending_accounting",
        "等待離席記帳",
        "按下「開始休息」但還沒離席時，這段等待時間怎麼記。",
        WidgetKind.CHOICE,
        "休息流程",
        choices=("work", "none"),
        tooltip=(
            "work＝等待離席期間仍算工作時間，工作紀錄持續到真正離席才結算（預設）；"
            "none＝按下按鈕當下就結算工作，之後的等待時間不計入任何統計。"
        ),
    ),
    FieldSpec(
        "rest_flow.interrupt_behavior",
        "休息中斷處理",
        "休息還沒滿額就回到座位太久時，系統如何處理。",
        WidgetKind.CHOICE,
        "休息流程",
        choices=("remind", "new_work"),
        tooltip=(
            "remind＝結算這段不完整的休息並立刻回到提醒狀態，繼續催促你補休息（預設）；"
            "new_work＝視為開始新一輪工作，等工作門檻到了再提醒。"
        ),
    ),
    FieldSpec(
        "rest_flow.rest_interrupt_after_sec",
        "休息中斷門檻（秒）",
        "休息中連續在座位上超過此秒數，視為休息被中斷。",
        WidgetKind.INT,
        "休息流程",
        minimum=1,
        maximum=_SECONDS_MAX,
        tooltip=(
            "僅「休息計算方式」為 presence（必須離席）時有效；"
            "fixed 固定倒數模式不受是否在座位影響。"
        ),
    ),
    FieldSpec(
        "rest_flow.escalation.max_stage",
        "升級上限",
        "等待離席／提醒超時的升級階梯最高升到第幾階。",
        WidgetKind.CHOICE,
        "休息流程",
        choices=("0", "1", "2", "3"),
        tooltip=(
            "0＝只顯示角落小提示；1＝可放大置中提醒；2＝可進到半透明全螢幕休息教練；"
            "3＝最終可鎖定螢幕。數字越大施壓越強。"
        ),
    ),
    FieldSpec(
        "rest_flow.escalation.stage1_sec",
        "第 1 階門檻（秒）",
        "滯留多久後升到第 1 階（提醒視窗放大置中）。",
        WidgetKind.INT,
        "休息流程",
        minimum=1,
        maximum=_SECONDS_MAX,
        tooltip="三個門檻必須嚴格遞增（第 1 階 < 第 2 階 < 第 3 階），且皆大於 0 秒。",
    ),
    FieldSpec(
        "rest_flow.escalation.stage2_sec",
        "第 2 階門檻（秒）",
        "滯留多久後升到第 2 階（半透明全螢幕休息教練）。",
        WidgetKind.INT,
        "休息流程",
        minimum=1,
        maximum=_SECONDS_MAX,
        tooltip="三個門檻必須嚴格遞增（第 1 階 < 第 2 階 < 第 3 階），且皆大於 0 秒。",
    ),
    FieldSpec(
        "rest_flow.escalation.stage3_sec",
        "第 3 階門檻（秒）",
        "滯留多久後升到第 3 階（鎖定螢幕）。",
        WidgetKind.INT,
        "休息流程",
        minimum=1,
        maximum=_SECONDS_MAX,
        tooltip=(
            "三個門檻必須嚴格遞增（第 1 階 < 第 2 階 < 第 3 階）。"
            "升級上限未達 3 時，此門檻不會觸發鎖屏。"
        ),
    ),
    FieldSpec(
        "rest_flow.escalation.apply_to_reminding",
        "提醒超時也升級",
        "提醒中遲遲不休息時，是否套用同一條升級階梯。",
        WidgetKind.BOOL,
        "休息流程",
        tooltip=(
            "開啟後，提醒狀態下的超時時間也會推進升級階梯"
            "（角落提示→放大→全螢幕→鎖屏）；關閉則升級只發生在「等待離席」狀態。"
        ),
    ),
    # ------------------------------------------------------------------ 紀錄
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
    # ------------------------------------------------------------------ 進階
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
)


def fields_for(category: str) -> tuple[FieldSpec, ...]:
    return tuple(field for field in SCHEMA if field.category == category)


def tooltip_for(spec: FieldSpec) -> str:
    return spec.tooltip or spec.hint


def get_value(cfg: AppConfig, key: str) -> Any:
    index = STAGE_FIELD_KEYS.get(key)
    if index is not None:
        return cfg.rest_flow.escalation.stage_after_sec[index]

    parts = key.split(".")
    obj: Any = cfg
    for part in parts:
        obj = getattr(obj, part)
    return obj


def set_value(cfg: AppConfig, key: str, value: Any) -> AppConfig:
    index = STAGE_FIELD_KEYS.get(key)
    if index is not None:
        stages = list(cfg.rest_flow.escalation.stage_after_sec)
        stages[index] = float(value)
        new_stages = (stages[0], stages[1], stages[2])
        return _replace_nested(
            cfg, "rest_flow", "escalation", {"stage_after_sec": new_stages}
        )

    if key == _MAX_STAGE_KEY:
        value = int(value)

    parts = key.split(".")
    if len(parts) == 2:
        section, field = parts
        sub = getattr(cfg, section)
        new_sub = dataclasses.replace(sub, **{field: value})
        return dataclasses.replace(cfg, **{section: new_sub})

    if len(parts) == 3:
        section, subsection, field = parts
        return _replace_nested(cfg, section, subsection, {field: value})

    raise ValueError(f"Unsupported key depth: {key}")


def _replace_nested(
    cfg: AppConfig, section: str, subsection: str, changes: dict[str, Any]
) -> AppConfig:
    sub = getattr(cfg, section)
    subsub = getattr(sub, subsection)
    new_subsub = dataclasses.replace(subsub, **changes)
    new_sub = dataclasses.replace(sub, **{subsection: new_subsub})
    return dataclasses.replace(cfg, **{section: new_sub})
