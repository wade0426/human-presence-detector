"""
人體辨識休息提醒系統 - 配置檔案
包含所有系統參數設定
"""

import os

# ==================== 時間設定 ====================
# 工作時間閾值 (秒) - 達到此時間後提醒休息
WORK_DURATION = 3600  # 1小時 = 3600秒

# 離開時間閾值 (秒) - 離開超過此時間自動重置計時器
AWAY_THRESHOLD = 300  # 5分鐘 = 300秒

# 檢測間隔 (秒) - 多久檢測一次
DETECTION_INTERVAL = 1  # 1秒檢測一次

# ==================== 攝像頭設定 ====================
# 攝像頭索引 (通常0為預設攝像頭)
CAMERA_INDEX = 0

# 攝像頭解析度設定
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

# 攝像頭FPS設定
CAMERA_FPS = 30

# ==================== YOLO模型設定 ====================
# YOLO模型路徑 (優先使用指定路徑，若不存在則下載到當前目錄)
MODEL_PATH = r'D:\Code\Models\yolov8n.pt'

# 備用模型名稱 (當指定路徑不存在時使用)
FALLBACK_MODEL = 'yolov8n.pt'

# 檢測信心度閾值
CONFIDENCE_THRESHOLD = 0.5

# 檢測類別 (0 = 人體)
DETECTION_CLASSES = [0]

# 是否顯示詳細輸出
VERBOSE_OUTPUT = False

# ==================== UI設定 ====================
# 主視窗設定
WINDOW_TITLE = "人體辨識休息提醒系統"
WINDOW_SIZE = "450x350"
WINDOW_RESIZABLE = False

# 字體設定
TITLE_FONT = ("Microsoft YaHei", 18, "bold")
LABEL_FONT = ("Microsoft YaHei", 12)
BUTTON_FONT = ("Microsoft YaHei", 11)
TIME_FONT = ("Courier New", 16, "bold")
SETTINGS_FONT = ("Microsoft YaHei", 10)

# 顏色設定
COLORS = {
    'primary': '#2E4057',      # 主色調
    'success': '#4CAF50',      # 成功/開始按鈕
    'danger': '#f44336',       # 危險/停止按鈕
    'info': '#2196F3',         # 資訊/設定按鈕
    'warning': '#FF8C00',      # 警告色
    'text_normal': '#666666',   # 一般文字
    'text_success': '#2E8B57',  # 成功狀態文字
    'text_danger': '#CD5C5C',   # 危險狀態文字
}

# 按鈕尺寸
BUTTON_WIDTH = 12
BUTTON_HEIGHT = 2
SETTINGS_BUTTON_WIDTH = 25

# ==================== 提醒設定 ====================
# 提醒訊息
REST_REMINDER_TITLE = "休息提醒"
REST_REMINDER_MESSAGE = """您已經持續工作1小時了！
該起來休息一下囉～

建議休息5-10分鐘，活動一下身體"""

# 狀態訊息
STATUS_MESSAGES = {
    'standby': '系統待機中...',
    'working': '✅ 檢測到使用者在工作',
    'away': '❌ 使用者不在電腦前',
    'away_with_time': '⏰ 使用者離開 ({time}秒)',
}

# ==================== 記錄檔設定 ====================
# 工作記錄檔案名稱
WORK_LOG_FILE = "work_log.json"

# 設定檔案名稱
SETTINGS_FILE = "settings.ini"

# 記錄檔格式
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# ==================== 進階設定 ====================
# 是否啟用工作記錄功能
ENABLE_WORK_LOGGING = True

# 是否啟用設定檔管理
ENABLE_CONFIG_MANAGEMENT = True

# 最大記錄保存天數
MAX_LOG_DAYS = 30

# 自動儲存間隔 (秒)
AUTO_SAVE_INTERVAL = 300  # 5分鐘

# ==================== 偵錯設定 ====================
# 是否啟用偵錯模式
DEBUG_MODE = False

# 是否顯示攝像頭畫面 (偵錯用)
SHOW_CAMERA_PREVIEW = False

# 是否記錄詳細日誌
DETAILED_LOGGING = False

# ==================== 設定驗證函數 ====================
def validate_config():
    """驗證配置設定的合理性"""
    errors = []
    
    # 檢查時間設定
    if WORK_DURATION <= 0:
        errors.append("工作時間必須大於0")
    
    if AWAY_THRESHOLD <= 0:
        errors.append("離開閾值必須大於0")
    
    if DETECTION_INTERVAL <= 0:
        errors.append("檢測間隔必須大於0")
    
    # 檢查攝像頭設定
    if CAMERA_INDEX < 0:
        errors.append("攝像頭索引不能為負數")
    
    if FRAME_WIDTH <= 0 or FRAME_HEIGHT <= 0:
        errors.append("畫面解析度必須大於0")
    
    # 檢查檔案路徑
    if MODEL_PATH and not os.path.exists(os.path.dirname(MODEL_PATH)) and os.path.dirname(MODEL_PATH):
        print(f"警告: 模型目錄不存在: {os.path.dirname(MODEL_PATH)}")
    
    return errors

def get_work_duration_minutes():
    """取得工作時間(分鐘)"""
    return WORK_DURATION // 60

def get_away_threshold_minutes():
    """取得離開閾值(分鐘)"""
    return AWAY_THRESHOLD // 60

def set_work_duration_minutes(minutes):
    """設定工作時間(分鐘)"""
    global WORK_DURATION
    WORK_DURATION = minutes * 60

def set_away_threshold_minutes(minutes):
    """設定離開閾值(分鐘)"""
    global AWAY_THRESHOLD
    AWAY_THRESHOLD = minutes * 60

# ==================== 配置載入 ====================
if __name__ == "__main__":
    # 驗證配置
    config_errors = validate_config()
    if config_errors:
        print("配置錯誤:")
        for error in config_errors:
            print(f"  - {error}")
    else:
        print("配置驗證通過")
        
    # 顯示當前配置
    print(f"\n當前配置:")
    print(f"  工作提醒時間: {get_work_duration_minutes()} 分鐘")
    print(f"  離開重置時間: {get_away_threshold_minutes()} 分鐘")
    print(f"  檢測間隔: {DETECTION_INTERVAL} 秒")
    print(f"  攝像頭索引: {CAMERA_INDEX}")
    print(f"  模型路徑: {MODEL_PATH}")
