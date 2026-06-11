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
    ConnectionState.STREAM_ERROR: "影像異常",  # ★ 新增（FR-6）
    ConnectionState.ERROR: "發生錯誤",
}
CONN_NO_SIGNAL = "目前收不到影像。請確認攝影機或串流來源後再試一次。"
CONN_STREAM_ERROR = "影像異常，畫面可能延遲或中斷。"  # ★ 新增（FR-6）
CONN_RECONNECTING = "連線中斷，正在重新連線…"
CONN_RETRY = "重試"
CONN_ERROR_PREFIX = "錯誤："

# Timer states
STATE_TEXT: dict[TimerState, str] = {
    TimerState.IDLE: "待機",
    TimerState.WORKING: "工作中",
    TimerState.AWAY: "短暫離開",
    TimerState.REMINDING: "提醒中",
    TimerState.RESTING: "休息中",
    TimerState.AWAITING_RETURN: "待機",
    TimerState.SUSPENDED: "已暫停",
}


def connection_state_text(state: ConnectionState) -> str:
    return CONN_TEXT[state]


def timer_state_text(state: TimerState) -> str:
    return STATE_TEXT[state]


# Reminders
REMIND_TITLE = "該休息一下了"
# FR-3: 改為 {duration}，由 format_duration_zh 提供動態時長
REMIND_BODY = "你已連續工作 {duration}。"
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

# Presence indicators
PRESENCE_YES = "有人"
PRESENCE_NO = "無人"

# Action bar – quit / ROI edit
ACTION_QUIT = "離開"
ACTION_EDIT_ROI_ACTIVE = "完成編輯"
ROI_HINT = "拖曳以選取偵測區域"
QUIT_CONFIRM_TITLE = "離開"
QUIT_CONFIRM_BODY = "確定要關閉系統嗎？"

# Return prompt (M7)
RETURN_TITLE = "歡迎回來"
RETURN_BODY = "休息結束，要開始新一輪工作嗎？"
RETURN_CONFIRM = "開始新一輪"

# Clear data (M2c)
CLEAR_DATA_BUTTON = "清除資料"
CLEAR_DATA_TITLE = "清除資料"
CLEAR_SCOPE_TODAY = "清除今日紀錄"
CLEAR_SCOPE_ALL = "清除全部紀錄"
CLEAR_SCOPE_RESET = "清除全部紀錄並重設設定"
CLEAR_RESET_WARNING = "此選項將清空所有紀錄，並將設定回復為預設值，此操作無法復原。"
CLEAR_CONFIRM_BODY = "此操作無法復原，確定要繼續嗎？"
CLEAR_DONE = "已清除 {count} 筆紀錄。"

# Sound preview (需求三 FR-3.1～3.7、FR-2.7)
SOUND_PREVIEW_PLAY = "試聽"
SOUND_PREVIEW_STOP = "停止"
SOUND_PREVIEW_ERROR = "無法播放此音檔"
SOUND_FILE_FILTER = "音訊檔 (*.mp3 *.wav);;所有檔案 (*)"
FILE_DIALOG_TITLE = "選擇檔案"
FILE_DIALOG_ALL_FILES = "所有檔案 (*)"

# Force lock (M3)
FORCE_LOCK_COUNTDOWN = "{seconds} 秒後將鎖定畫面，請準備休息。"
FORCE_LOCK_CANCEL = "取消本次鎖定"

# GPU CUDA 檢查（需求一 FR-1.1～1.6）
CUDA_CHECK_BUTTON = "檢查"
CUDA_CHECK_RUNNING = "檢查中…"
CUDA_CHECK_TITLE = "GPU CUDA 檢查"
CUDA_CHECK_OK = "✓ 本機可使用 GPU CUDA"
CUDA_CHECK_FAIL = "✗ 本機目前無法使用 GPU CUDA"
CUDA_SUGGEST = "建議的運算裝置：{device}"
CUDA_FALLBACK_NOTICE = "CUDA 初始化失敗，已改用 CPU 繼續偵測。"
CUDA_STATE_NO_TORCH = "未安裝 PyTorch，請先安裝 PyTorch 後再使用 GPU。"
CUDA_STATE_CPU_ONLY = "目前安裝的是 CPU 版 PyTorch，需改裝 CUDA 版 PyTorch 才能使用 GPU。"
CUDA_STATE_CUDA_UNAVAILABLE = (
    "PyTorch 具備 CUDA 支援，但目前無法使用 GPU，請檢查 NVIDIA 驅動程式與顯示卡。"
)
CUDA_STATE_OK = "CUDA 環境正常，可使用 GPU 加速偵測。"
CUDA_TORCH_VERSION = "PyTorch 版本：{value}"
CUDA_BUILD_VERSION = "CUDA build 版本：{value}"
CUDA_BUILD_NONE = "無（CPU 版 PyTorch）"
CUDA_AVAILABLE = "CUDA 可用：{value}"
CUDA_DEVICE_COUNT = "GPU 數量：{value}"
CUDA_CUDNN_VERSION = "cuDNN 版本：{value}"
CUDA_ERROR = "錯誤訊息：{value}"
CUDA_VALUE_NONE = "無"
CUDA_VALUE_NOT_INSTALLED = "未安裝"
CUDA_VALUE_YES = "是"
CUDA_VALUE_NO = "否"
