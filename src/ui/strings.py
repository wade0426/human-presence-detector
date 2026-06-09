from __future__ import annotations

from src.app.connection_state import ConnectionState
from src.types import TimerState

# Settings
SETTINGS_TITLE = "設定"
SETTINGS_SAVED_RESTART = "設定已儲存。部分變更需要重新啟動程式後才會生效。"
SETTINGS_SAVED_OK = "知道了"
SETTINGS_SAVE = "儲存變更"
SETTINGS_CANCEL = "取消"

# Validation
ERR_RTSP_URL_EMPTY = "請先填入 RTSP 串流位址。"
ERR_CONFIDENCE_RANGE = "把握度必須介於 0（不含）到 1 之間。"
ERR_BOX_RATIO_RANGE = "高度比例必須介於 0（不含）到 1 之間。"
ERR_DEBOUNCE_MIN = "去抖動次數必須為大於等於 1 的整數。"
ERR_MINUTE_RANGE = "分鐘數必須介於 0.1 到 9999 之間。"

# Connection
CONN_TEXT: dict[ConnectionState, str] = {
    ConnectionState.IDLE: "待機",
    ConnectionState.CONNECTING: "連線中",
    ConnectionState.CONNECTED: "已連線",
    ConnectionState.RECONNECTING: "重新連線中",
    ConnectionState.NO_SIGNAL: "收不到影像",
    ConnectionState.ERROR: "發生錯誤",
}
CONN_NO_SIGNAL = "目前收不到影像。請確認攝影機或串流來源後再試一次。"
CONN_RECONNECTING = "連線中斷，正在重新連線…"
CONN_RETRY = "重試"
CONN_ERROR_PREFIX = "錯誤："

# Timer states
STATE_TEXT: dict[TimerState, str] = {
    TimerState.IDLE: "待機",
    TimerState.WORKING: "工作中",
    TimerState.PAUSED: "短暫離開",
    TimerState.REMINDING: "提醒中",
}


def connection_state_text(state: ConnectionState) -> str:
    return CONN_TEXT[state]


def timer_state_text(state: TimerState) -> str:
    return STATE_TEXT[state]


# Reminders
REMIND_TITLE = "該休息一下了"
REMIND_BODY = "你已連續工作 {minutes} 分鐘。"
REMIND_START_REST = "開始休息"
REMIND_ACK = "我知道了"
REMIND_SNOOZE = "再 {minutes} 分鐘"
REMIND_CLOSE = "關閉"

# Tray
TRAY_OPEN = "開啟主視窗"
TRAY_PAUSE = "暫停偵測"
TRAY_RESUME = "繼續偵測"
TRAY_SETTINGS = "設定"
TRAY_QUIT = "結束"

# Today summary
TODAY_EMPTY = "今天還沒有紀錄，開始工作後就會出現在這裡。"
TODAY_WORK_LABEL = "今日工作"
TODAY_REST_LABEL = "休息次數"

# Action bar
ACTION_EDIT_ROI = "編輯 ROI"
ACTION_PAUSE = "暫停"
ACTION_RESUME = "繼續"
ACTION_SETTINGS = "設定"
