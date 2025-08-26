# 人員監測系統配置檔案
# 
# 時間設定 (秒)
WORK_DURATION = 3600        # 1小時 - 工作時長統計和長時間工作提醒
REST_INTERVAL = 1800        # 30分鐘 - 定期休息提醒的週期
REST_DURATION = 300         # 5分鐘 - 建議的休息時長
AWAY_THRESHOLD = 300        # 5分鐘 - 離開座位的判定閾值
DETECTION_INTERVAL = 1      # 1秒 - 攝像頭檢測頻率

# 攝像頭設定
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

# 休息提醒模式設定
REST_REMINDER_MODE = "TIMER"    # "TIMER" 或 "IMAGE"

# 圖片提醒設定
REST_IMAGE_PATH = "images/image.png"
IMAGE_DISPLAY_MODE = "WINDOW"   # "WINDOW" 或 "FULLSCREEN"

# 計時器模式設定
TIMER_WINDOW_SIZE = (400, 200)
TIMER_ALWAYS_ON_TOP = True
TIMER_ALLOW_CLOSE = True

# 圖片模式設定
IMAGE_WINDOW_SIZE = (800, 600)
IMAGE_ALLOW_CLOSE = True
IMAGE_FADE_EFFECT = False
