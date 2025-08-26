import cv2
import time
import tkinter as tk
from tkinter import messagebox, ttk
from ultralytics import YOLO
from datetime import datetime, timedelta
import json
import os
from threading import Thread, Timer
from PIL import Image, ImageTk
import math

# === 配置參數 ===
class Config:
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
    REST_IMAGE_PATH = "v2/images/image.png"
    IMAGE_DISPLAY_MODE = "WINDOW"   # "WINDOW" 或 "FULLSCREEN"
    
    # 計時器模式設定
    TIMER_WINDOW_SIZE = (400, 200)
    TIMER_ALWAYS_ON_TOP = True
    TIMER_ALLOW_CLOSE = True
    
    # 圖片模式設定
    IMAGE_WINDOW_SIZE = (716, 1075)
    IMAGE_ALLOW_CLOSE = True
    IMAGE_FADE_EFFECT = False

def create_default_rest_image():
    """創建預設的休息提醒圖片"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # 確保目錄存在
        os.makedirs(os.path.dirname(Config.REST_IMAGE_PATH), exist_ok=True)
        
        # 創建圖片
        width, height = 800, 600
        image = Image.new('RGB', (width, height), color='lightblue')
        draw = ImageDraw.Draw(image)
        
        # 添加文字
        try:
            # 嘗試使用系統字體
            font_large = ImageFont.truetype("arial.ttf", 48)
            font_medium = ImageFont.truetype("arial.ttf", 24)
        except:
            # 如果找不到字體，使用預設字體
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
        
        # 繪製主標題
        title_text = "休息時間"
        title_bbox = draw.textbbox((0, 0), title_text, font=font_large)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (width - title_width) // 2
        title_y = height // 3
        draw.text((title_x, title_y), title_text, fill='darkblue', font=font_large)
        
        # 繪製副標題
        subtitle_text = "保護眼睛，適當休息"
        subtitle_bbox = draw.textbbox((0, 0), subtitle_text, font=font_medium)
        subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
        subtitle_x = (width - subtitle_width) // 2
        subtitle_y = title_y + 80
        draw.text((subtitle_x, subtitle_y), subtitle_text, fill='darkblue', font=font_medium)
        
        # 繪製簡單圖形
        center_x, center_y = width // 2, height // 2 + 50
        radius = 80
        
        # 繪製太陽
        draw.ellipse([center_x - radius, center_y - radius, 
                     center_x + radius, center_y + radius], fill='yellow', outline='orange', width=3)
        
        # 繪製太陽光線
        for i in range(8):
            angle = i * 45
            x1 = center_x + radius * 1.3 * math.cos(math.radians(angle))
            y1 = center_y + radius * 1.3 * math.sin(math.radians(angle))
            x2 = center_x + radius * 1.6 * math.cos(math.radians(angle))
            y2 = center_y + radius * 1.6 * math.sin(math.radians(angle))
            draw.line([x1, y1, x2, y2], fill='orange', width=4)
        
        # 保存圖片
        image.save(Config.REST_IMAGE_PATH)
        return True
        
    except Exception as e:
        print(f"⚠️ 創建預設圖片失敗: {e}")
        return False

class WorkSession:
    """工作時段記錄"""
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.total_work_time = 0
        self.break_times = []
        self.away_times = []

class PresenceDetector:
    """人員檢測和工作時間監控系統"""
    
    def __init__(self):
        self.model = None
        self.cap = None
        self.camera_index = None
        
        # 狀態追蹤
        self.is_present = False
        self.work_start_time = None
        self.last_present_time = None
        self.total_work_time = 0
        self.session_work_time = 0
        self.last_rest_reminder = None
        self.last_work_reminder = None
        
        # 記錄
        self.current_session = WorkSession()
        self.daily_log = []
        
        # GUI相關
        self.rest_window = None
        self.timer_var = None
        self.rest_timer = None
        self.countdown_duration = 0
        self.root = None
        
        # 載入歷史記錄
        self.load_daily_log()

    def load_daily_log(self):
        """載入每日工作記錄"""
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = f"work_log_{today}.json"
        
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.daily_log = data.get('sessions', [])
                    self.total_work_time = data.get('total_work_time', 0)
            except Exception as e:
                print(f"載入記錄失敗: {e}")
                self.daily_log = []
                self.total_work_time = 0

    def save_daily_log(self):
        """保存每日工作記錄"""
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = f"work_log_{today}.json"
        
        try:
            data = {
                'date': today,
                'total_work_time': self.total_work_time,
                'sessions': self.daily_log
            }
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存記錄失敗: {e}")

    def format_time(self, seconds):
        """格式化時間顯示"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def show_timer_reminder(self):
        """顯示計時器模式的休息提醒"""
        try:
            if self.rest_window:
                self.rest_window.destroy()
            
            # 檢查是否有有效的 Tkinter root
            try:
                root_test = tk._default_root
                if root_test is None:
                    print("⚠️ Tkinter 根視窗不存在，無法顯示計時器")
                    return
            except:
                print("⚠️ Tkinter 不可用，使用控制台提醒")
                print("⏰ 建議休息 5 分鐘！")
                return
            
            self.rest_window = tk.Toplevel()
            self.rest_window.title("休息時間")
            self.rest_window.geometry(f"{Config.TIMER_WINDOW_SIZE[0]}x{Config.TIMER_WINDOW_SIZE[1]}")
            self.rest_window.configure(bg='lightblue')
            
            if Config.TIMER_ALWAYS_ON_TOP:
                self.rest_window.attributes('-topmost', True)
            
            # 居中顯示
            self.rest_window.update_idletasks()
            x = (self.rest_window.winfo_screenwidth() // 2) - (Config.TIMER_WINDOW_SIZE[0] // 2)
            y = (self.rest_window.winfo_screenheight() // 2) - (Config.TIMER_WINDOW_SIZE[1] // 2)
            self.rest_window.geometry(f"+{x}+{y}")
            
            # 標題
            title_label = tk.Label(self.rest_window, text="該休息了！", font=("Arial", 16, "bold"), bg='lightblue')
            title_label.pack(pady=10)
            
            # 倒數計時器
            self.timer_var = tk.StringVar()
            timer_label = tk.Label(self.rest_window, textvariable=self.timer_var, font=("Arial", 24), bg='lightblue')
            timer_label.pack(pady=10)
            
            # 按鈕
            button_frame = tk.Frame(self.rest_window, bg='lightblue')
            button_frame.pack(pady=10)
            
            if Config.TIMER_ALLOW_CLOSE:
                close_btn = tk.Button(button_frame, text="提前結束", command=self.close_rest_reminder)
                close_btn.pack(side=tk.LEFT, padx=5)
            
            pause_btn = tk.Button(button_frame, text="暫停", command=self.toggle_rest_timer)
            pause_btn.pack(side=tk.LEFT, padx=5)
            
            # 開始倒數計時
            self.start_rest_countdown(Config.REST_DURATION)
            
        except Exception as e:
            print(f"顯示計時器提醒時發生錯誤: {e}")
            print("⏰ 建議休息 5 分鐘！")
            self.last_rest_reminder = time.time()

    def show_image_reminder(self):
        """顯示圖片模式的休息提醒"""
        if not os.path.exists(Config.REST_IMAGE_PATH):
            print(f"圖片檔案不存在: {Config.REST_IMAGE_PATH}")
            print("正在創建預設休息圖片...")
            if not create_default_rest_image():
                print("使用控制台提醒")
                duration_display = f"{Config.REST_DURATION//60} 分鐘" if Config.REST_DURATION >= 60 else f"{Config.REST_DURATION} 秒"
                print(f"⏰ 建議休息 {duration_display}！")
                # 重要：設定 last_rest_reminder 避免重複觸發
                self.last_rest_reminder = time.time()
                return
        
        try:
            # 檢查是否有有效的 Tkinter root
            try:
                root_test = tk._default_root
                if root_test is None:
                    print("⚠️ Tkinter 根視窗不存在，無法顯示圖片提醒")
                    duration_display = f"{Config.REST_DURATION//60} 分鐘" if Config.REST_DURATION >= 60 else f"{Config.REST_DURATION} 秒"
                    print(f"⏰ 建議休息 {duration_display}！")
                    return
            except:
                print("⚠️ Tkinter 不可用，使用控制台提醒")
                duration_display = f"{Config.REST_DURATION//60} 分鐘" if Config.REST_DURATION >= 60 else f"{Config.REST_DURATION} 秒"
                print(f"⏰ 建議休息 {duration_display}！")
                return
            
            if self.rest_window:
                self.rest_window.destroy()
            
            self.rest_window = tk.Toplevel()
            self.rest_window.title("休息提醒")
            
            # 載入圖片
            image = Image.open(Config.REST_IMAGE_PATH)
            
            if Config.IMAGE_DISPLAY_MODE == "FULLSCREEN":
                self.rest_window.attributes('-fullscreen', True)
                screen_width = self.rest_window.winfo_screenwidth()
                screen_height = self.rest_window.winfo_screenheight()
                image = image.resize((screen_width, screen_height), Image.Resampling.LANCZOS)
            else:
                self.rest_window.geometry(f"{Config.IMAGE_WINDOW_SIZE[0]}x{Config.IMAGE_WINDOW_SIZE[1]}")
                image = image.resize(Config.IMAGE_WINDOW_SIZE, Image.Resampling.LANCZOS)
                # 居中顯示
                self.rest_window.update_idletasks()
                x = (self.rest_window.winfo_screenwidth() // 2) - (Config.IMAGE_WINDOW_SIZE[0] // 2)
                y = (self.rest_window.winfo_screenheight() // 2) - (Config.IMAGE_WINDOW_SIZE[1] // 2)
                self.rest_window.geometry(f"+{x}+{y}")
                
            # 設定視窗屬性
            self.rest_window.attributes('-topmost', True)  # 置頂顯示
            
            photo = ImageTk.PhotoImage(image)
            label = tk.Label(self.rest_window, image=photo)
            label.image = photo  # 保持引用
            label.pack()
            
            # 添加標題和倒數計時器
            info_frame = tk.Frame(self.rest_window, bg='white')
            info_frame.pack(pady=10)
            
            title_label = tk.Label(info_frame, text="休息時間", font=("Arial", 16, "bold"), bg='white')
            title_label.pack()
            
            # 倒數計時器顯示
            self.timer_var = tk.StringVar()
            timer_label = tk.Label(info_frame, textvariable=self.timer_var, font=("Arial", 14), bg='white')
            timer_label.pack()
            
            # 開始倒數計時
            self.start_rest_countdown(Config.REST_DURATION)
            
            # 綁定關閉事件
            if Config.IMAGE_ALLOW_CLOSE:
                self.rest_window.bind('<Button-1>', lambda e: self.close_rest_reminder())
                self.rest_window.bind('<Escape>', lambda e: self.close_rest_reminder())
                self.rest_window.bind('<Return>', lambda e: self.close_rest_reminder())
                self.rest_window.bind('<space>', lambda e: self.close_rest_reminder())
                label.bind('<Button-1>', lambda e: self.close_rest_reminder())
                
                # 添加關閉按鈕
                close_btn = tk.Button(info_frame, text="結束休息", command=self.close_rest_reminder)
                close_btn.pack(pady=5)
            
            # 設定視窗焦點
            self.rest_window.focus_set()
            
        except Exception as e:
            print(f"顯示圖片失敗: {e}")
            print(f"錯誤詳情：{type(e).__name__}: {str(e)}")
            duration_display = f"{Config.REST_DURATION//60} 分鐘" if Config.REST_DURATION >= 60 else f"{Config.REST_DURATION} 秒"
            print(f"⏰ 建議休息 {duration_display}！")

    def start_rest_countdown(self, duration):
        """開始休息倒數計時"""
        self.countdown_duration = duration
        self.update_countdown()
    
    def update_countdown(self):
        """更新倒數計時（在主線程中安全執行）"""
        if self.countdown_duration > 0 and self.rest_window:
            try:
                minutes = self.countdown_duration // 60
                seconds = self.countdown_duration % 60
                self.timer_var.set(f"{minutes:02d}:{seconds:02d}")
                self.countdown_duration -= 1
                # 使用 after 方法在主線程中調度下次更新
                self.rest_window.after(1000, self.update_countdown)
            except Exception as e:
                print(f"計時器更新錯誤: {e}")
                self.close_rest_reminder()
        else:
            self.close_rest_reminder()

    def toggle_rest_timer(self):
        """暫停/繼續休息計時器"""
        # 這裡可以實現暫停/繼續功能
        pass

    def close_rest_reminder(self):
        """關閉休息提醒"""
        try:
            # 停止計時器
            if self.rest_timer:
                self.rest_timer.cancel()
                self.rest_timer = None
            
            # 重置倒數計時
            self.countdown_duration = 0
            
            # 關閉視窗
            if self.rest_window:
                self.rest_window.destroy()
                self.rest_window = None
                self.timer_var = None
            
            # 重要：重置休息提醒時間，避免立即重複觸發
            # 這裡設定為當前時間，確保下次休息提醒要等完整的 REST_INTERVAL
            self.last_rest_reminder = time.time()
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🟢 休息結束，繼續工作")
            
        except Exception as e:
            print(f"關閉休息提醒時發生錯誤: {e}")
            # 即使發生錯誤也要更新時間，避免重複觸發
            self.last_rest_reminder = time.time()

    def show_work_reminder(self):
        """顯示工作時長提醒"""
        try:
            work_hours = self.session_work_time // 3600
            # 使用控制台輸出代替 messagebox，避免線程安全問題
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] ⚠️ 工作提醒：您已連續工作 {work_hours} 小時，請注意適當休息！")
        except Exception as e:
            print(f"顯示工作提醒時發生錯誤: {e}")

    def update_presence_status(self, person_detected):
        """更新人員在座狀態"""
        current_time = time.time()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if person_detected:
            # 檢測到人員
            if not self.is_present:
                # 從離開狀態變為在座狀態
                self.is_present = True
                self.work_start_time = current_time
                self.last_present_time = current_time
                
                # 開始新的工作時段
                if self.current_session.start_time is None:
                    self.current_session.start_time = datetime.now()
                
                print(f"[{timestamp}] ✅ 檢測到人員，開始計時")
                print(f"    今日總工作時間: {self.format_time(self.total_work_time)}")
                
                # 初始化提醒時間
                if self.last_rest_reminder is None:
                    self.last_rest_reminder = current_time
                if self.last_work_reminder is None:
                    self.last_work_reminder = current_time
            else:
                # 持續在座
                self.last_present_time = current_time
                
                # 計算本次工作時間
                if self.work_start_time:
                    self.session_work_time = current_time - self.work_start_time
                    
                    # 檢查是否需要休息提醒 (每 REST_INTERVAL 秒)
                    if (current_time - self.last_rest_reminder) >= Config.REST_INTERVAL:
                        self.trigger_rest_reminder()
                        # 重要：立即更新 last_rest_reminder 避免重複觸發
                        self.last_rest_reminder = current_time
                    
                    # 檢查是否需要工作時長提醒 (每1小時)
                    if (current_time - self.last_work_reminder) >= Config.WORK_DURATION:
                        self.show_work_reminder()
                        self.last_work_reminder = current_time
                
                # 定期顯示狀態 (每30秒)
                if int(current_time) % 30 == 0:
                    work_time_str = self.format_time(self.session_work_time)
                    total_time_str = self.format_time(self.total_work_time + self.session_work_time)
                    print(f"[{timestamp}] 📊 本次工作: {work_time_str} | 今日總計: {total_time_str}")
        else:
            # 未檢測到人員
            if self.is_present:
                # 從在座狀態變為離開狀態
                away_duration = current_time - self.last_present_time if self.last_present_time else 0
                
                if away_duration >= Config.AWAY_THRESHOLD:
                    # 確認離開 - 重置計時器
                    self.handle_away_state()
                    print(f"[{timestamp}] ❌ 確認離開 (超過 {Config.AWAY_THRESHOLD} 秒)")
                else:
                    # 暫時離開 - 繼續計時
                    print(f"[{timestamp}] ⏸️ 暫時離開 ({int(away_duration)} 秒)")
            else:
                # 持續離開
                print(f"[{timestamp}] ❌ 鏡頭前沒有人")

    def handle_away_state(self):
        """處理確認離開狀態"""
        current_time = time.time()
        
        # 保存本次工作時段
        if self.work_start_time and self.session_work_time > 0:
            self.total_work_time += self.session_work_time
            
            # 記錄工作時段
            session_record = {
                'start_time': self.current_session.start_time.isoformat() if self.current_session.start_time else None,
                'end_time': datetime.now().isoformat(),
                'duration': self.session_work_time,
                'total_work_time': self.total_work_time
            }
            self.daily_log.append(session_record)
            
            # 保存記錄
            self.save_daily_log()
            
            print(f"    本次工作時長: {self.format_time(self.session_work_time)}")
            print(f"    今日總工作時間: {self.format_time(self.total_work_time)}")
        
        # 重置狀態
        self.is_present = False
        self.work_start_time = None
        self.session_work_time = 0
        self.current_session = WorkSession()
        
        # 關閉任何打開的休息提醒
        if self.rest_window:
            self.close_rest_reminder()

    def trigger_rest_reminder(self):
        """觸發休息提醒"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        interval_display = f"{Config.REST_INTERVAL//60} 分鐘" if Config.REST_INTERVAL >= 60 else f"{Config.REST_INTERVAL} 秒"
        print(f"[{timestamp}] 🔔 休息提醒 - 您已工作 {interval_display}")
        
        # 如果已經有休息視窗打開，不要重複觸發
        if self.rest_window:
            print("   休息提醒視窗已存在，跳過重複觸發")
            return
        
        try:
            if Config.REST_REMINDER_MODE == "IMAGE":
                self.show_image_reminder()
            else:
                self.show_timer_reminder()
        except Exception as e:
            print(f"顯示休息提醒時發生錯誤: {e}")
            # 降級為簡單的控制台提醒
            duration_display = f"{Config.REST_DURATION//60} 分鐘" if Config.REST_DURATION >= 60 else f"{Config.REST_DURATION} 秒"
            print(f"⏰ 建議休息 {duration_display}！")

    def validate_config(self):
        """驗證配置參數"""
        print("🔍 正在驗證配置...")
        
        # 檢查休息提醒模式
        if Config.REST_REMINDER_MODE not in ["TIMER", "IMAGE"]:
            print(f"⚠️ 無效的休息提醒模式: {Config.REST_REMINDER_MODE}，使用預設值 TIMER")
            Config.REST_REMINDER_MODE = "TIMER"
        
        # 檢查圖片檔案
        if Config.REST_REMINDER_MODE == "IMAGE":
            if not os.path.exists(Config.REST_IMAGE_PATH):
                print(f"⚠️ 圖片檔案不存在: {Config.REST_IMAGE_PATH}")
                print("   正在創建預設休息圖片...")
                # 嘗試創建預設圖片
                if create_default_rest_image():
                    print(f"✅ 已創建預設休息圖片，將使用圖片模式")
                else:
                    print("   創建失敗，將自動切換為計時器模式")
                    Config.REST_REMINDER_MODE = "TIMER"
            else:
                print(f"✅ 找到休息提醒圖片: {Config.REST_IMAGE_PATH}")
        
        # 檢查時間參數
        if Config.DETECTION_INTERVAL <= 0:
            print("⚠️ 檢測間隔必須大於 0，使用預設值 1 秒")
            Config.DETECTION_INTERVAL = 1
        
        if Config.REST_INTERVAL <= 0:
            print("⚠️ 休息提醒間隔必須大於 0，使用預設值 30 分鐘")
            Config.REST_INTERVAL = 1800
        
        print("✅ 配置驗證完成")

    def initialize_camera_and_model(self):
        """初始化攝像頭和模型"""
        try:
            # 驗證配置
            self.validate_config()
            
            # 載入模型
            model_path = r'D:\Code\Models\yolov8n.pt'
            print(f"🤖 正在載入 YOLO 模型: {model_path}")
            
            if not os.path.exists(model_path):
                print(f"❌ 模型檔案不存在: {model_path}")
                print("請確保 YOLO 模型檔案存在於指定路徑")
                return False
            
            self.model = YOLO(model_path)
            
            # 嘗試使用 GPU
            try:
                self.model.to('cuda')
                print(f"✅ 模型運行設備: {self.model.device}")
            except Exception as e:
                print(f"⚠️ GPU 不可用，使用 CPU: {e}")
            
            # 選擇攝像頭
            print("📷 正在初始化攝像頭...")
            self.camera_index = select_camera()
            if self.camera_index is None:
                print("❌ 未找到可用攝像頭")
                return False
            
            # 開啟攝像頭
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            
            if not self.cap.isOpened():
                print(f"❌ 無法開啟攝像頭 {self.camera_index}")
                return False
            
            # 設定攝像頭參數
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, Config.FRAME_WIDTH)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, Config.FRAME_HEIGHT)
            
            # 驗證攝像頭設定
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"✅ 攝像頭 {self.camera_index} 初始化成功")
            print(f"   解析度: {actual_width}x{actual_height}")
            
            return True
            
        except Exception as e:
            print(f"❌ 初始化過程中發生錯誤: {e}")
            return False

    def setup_detection_timer(self, root):
        """設置基於 Tkinter 的檢測定時器"""
        self.root = root
        self.last_detection_time = 0
        
        print("開始人員監測...")
        print(f"檢測間隔: {Config.DETECTION_INTERVAL} 秒")
        print(f"休息提醒間隔: {Config.REST_INTERVAL//60 if Config.REST_INTERVAL >= 60 else Config.REST_INTERVAL} {'分鐘' if Config.REST_INTERVAL >= 60 else '秒'}")
        print(f"工作提醒間隔: {Config.WORK_DURATION//60 if Config.WORK_DURATION >= 60 else Config.WORK_DURATION} {'分鐘' if Config.WORK_DURATION >= 60 else '秒'}")
        print(f"離開判定閾值: {Config.AWAY_THRESHOLD} 秒")
        print("=" * 50)
        
        # 開始檢測循環
        self.detection_step()
    
    def detection_step(self):
        """單次檢測步驟（非阻塞）"""
        try:
            ret, frame = self.cap.read()
            if not ret:
                print("攝像頭讀取失敗")
                self.cleanup()
                return
            
            current_time = time.time()
            
            # 根據設定的檢測間隔進行檢測
            if current_time - self.last_detection_time >= Config.DETECTION_INTERVAL:
                self.last_detection_time = current_time
                
                # YOLO 人員檢測
                results = self.model(frame, verbose=False)
                person_detected = False
                
                if results[0].boxes is not None:
                    detected_classes = results[0].boxes.cls.tolist()
                    person_detected = 0 in detected_classes  # 0 是 'person' 類別
                
                # 更新人員狀態
                self.update_presence_status(person_detected)
            
            # 顯示攝像頭畫面 (可選)
            # cv2.imshow(f'攝像頭 {self.camera_index}', frame)
            
            # 檢查 OpenCV 視窗事件
            cv2.waitKey(1)
            
            # 調度下次檢測（非阻塞）
            if hasattr(self, 'root') and self.root:
                self.root.after(50, self.detection_step)  # 50ms 後執行下次檢測
            
        except Exception as e:
            print(f"檢測步驟錯誤: {e}")
            self.cleanup()

    def run_detection_loop(self):
        """運行主要檢測循環（已廢棄，使用 setup_detection_timer 替代）"""
        print("⚠️ 使用 setup_detection_timer 方法替代")
        pass

    def cleanup(self):
        """清理資源"""
        try:
            # 保存最終記錄
            if self.is_present and self.session_work_time > 0:
                self.handle_away_state()
            
            # 關閉攝像頭
            if hasattr(self, 'cap') and self.cap:
                self.cap.release()
            
            # 關閉所有 OpenCV 視窗
            cv2.destroyAllWindows()
            
            # 關閉休息提醒視窗
            if self.rest_window:
                self.close_rest_reminder()
            
            print("程式已正常結束")
            print(f"今日總工作時間: {self.format_time(self.total_work_time)}")
            
        except Exception as e:
            print(f"清理資源時發生錯誤: {e}")

    def show_daily_summary(self):
        """顯示每日工作統計"""
        print("\n" + "=" * 50)
        print("📊 今日工作統計")
        print("=" * 50)
        print(f"總工作時間: {self.format_time(self.total_work_time)}")
        print(f"工作時段數量: {len(self.daily_log)}")
        
        if self.daily_log:
            print("\n工作時段詳細:")
            for i, session in enumerate(self.daily_log, 1):
                start = datetime.fromisoformat(session['start_time']).strftime("%H:%M:%S")
                end = datetime.fromisoformat(session['end_time']).strftime("%H:%M:%S")
                duration = self.format_time(session['duration'])
                print(f"  {i}. {start} - {end} ({duration})")
        
        # 顯示效率分析
        if self.total_work_time > 0:
            print(self.get_work_efficiency_analysis())
        
        print("=" * 50)

    def print_usage_instructions(self):
        """顯示使用說明"""
        print("\n" + "=" * 50)
        print("📋 使用說明")
        print("=" * 50)
        print("• 系統會自動檢測您是否在攝像頭前")
        print("• 只有檢測到人員時才會計算工作時間")
        print(f"• 每 {Config.REST_INTERVAL//60 if Config.REST_INTERVAL >= 60 else Config.REST_INTERVAL} {'分鐘' if Config.REST_INTERVAL >= 60 else '秒'} 會提醒您休息")
        print(f"• 離開座位超過 {Config.AWAY_THRESHOLD} 秒會自動暫停計時")
        print("• 休息提醒支援兩種模式：")
        print("  - TIMER: 倒數計時器模式")
        print("  - IMAGE: 圖片提醒模式")
        print("• 所有工作記錄會自動保存為 JSON 檔案")
        print("• 按 'q' 鍵退出程式")
        print("=" * 50)

    def create_sample_config_file(self):
        """創建範例配置檔案"""
        config_content = '''# 人員監測系統配置檔案
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
'''
        
        config_file = "config_sample.py"
        if not os.path.exists(config_file):
            try:
                with open(config_file, 'w', encoding='utf-8') as f:
                    f.write(config_content)
                print(f"✅ 已創建範例配置檔案: {config_file}")
            except Exception as e:
                print(f"⚠️ 無法創建配置檔案: {e}")

    def get_work_efficiency_analysis(self):
        """獲取工作效率分析"""
        if not self.daily_log:
            return "暫無數據可分析"
        
        total_sessions = len(self.daily_log)
        total_time = self.total_work_time
        avg_session_length = total_time / total_sessions if total_sessions > 0 else 0
        
        # 計算今日工作強度
        current_hour = datetime.now().hour
        if current_hour > 8:  # 假設 8 點開始工作
            work_hours_today = current_hour - 8
            efficiency_score = (total_time / 3600) / work_hours_today * 100 if work_hours_today > 0 else 0
        else:
            efficiency_score = 0
        
        analysis = f"""
工作效率分析:
• 工作時段數: {total_sessions}
• 平均時段長度: {self.format_time(avg_session_length)}
• 今日工作效率: {efficiency_score:.1f}%
• 建議: {'保持良好工作節奏！' if efficiency_score > 50 else '可以適當增加專注時間'}
"""
        return analysis

    def export_daily_report(self):
        """匯出每日工作報告"""
        today = datetime.now().strftime("%Y-%m-%d")
        report_file = f"work_report_{today}.txt"
        
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(f"工作時間報告 - {today}\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"總工作時間: {self.format_time(self.total_work_time)}\n")
                f.write(f"工作時段數: {len(self.daily_log)}\n\n")
                
                if self.daily_log:
                    f.write("詳細工作時段:\n")
                    for i, session in enumerate(self.daily_log, 1):
                        start = datetime.fromisoformat(session['start_time']).strftime("%H:%M:%S")
                        end = datetime.fromisoformat(session['end_time']).strftime("%H:%M:%S")
                        duration = self.format_time(session['duration'])
                        f.write(f"{i}. {start} - {end} ({duration})\n")
                
                f.write("\n" + self.get_work_efficiency_analysis())
                f.write(f"\n\n報告生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            print(f"✅ 已匯出工作報告: {report_file}")
        except Exception as e:
            print(f"⚠️ 匯出報告失敗: {e}")

def select_camera():
    """
    自動檢測並讓使用者選擇攝像頭
    """
    available = []
    working = []
    
    print("正在檢測攝像頭...")
    for i in range(5):  # 檢測前5個索引
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                print(f"攝像頭 {i}: {width}x{height}")
                working.append(i)
        cap.release()
    
    if not working:
        print("未找到可用攝像頭")
        return None
    
    if len(working) == 1:
        selected = working[0]
        print(f"自動選擇攝像頭: {selected}")
    else:
        print("可用攝像頭:", working)
        try:
            selected = int(input("請選擇攝像頭索引: "))
            if selected not in working:
                print("無效索引，使用預設攝像頭")
                selected = working[0]
        except:
            selected = working[0]
    
    return selected

# 主程式
def main():
    print("=" * 60)
    print("🚀 人員監測與工作時間管理系統")
    print("=" * 60)
    print("功能特色:")
    print("• 自動計時：只在檢測到使用者時計算工作時間")
    print("• 智能重置：離開超過設定時間自動重置計時器")
    print("• 工作記錄：詳細記錄每日工作時段和休息情況")
    print("• 休息提醒：支援計時器和圖片兩種提醒模式")
    print("• 統計分析：提供工作時間統計和分析功能")
    print("=" * 60)
    
    # 初始化 Tkinter (用於 GUI 提醒)
    root = tk.Tk()
    root.withdraw()  # 隱藏主視窗
    
    # 創建檢測器實例
    detector = PresenceDetector()
    
    # 創建範例配置檔案
    detector.create_sample_config_file()
    
    # 顯示使用說明
    detector.print_usage_instructions()
    
    # 初始化攝像頭和模型
    if not detector.initialize_camera_and_model():
        print("❌ 初始化失敗，程式結束")
        return
    
    print(f"\n✅ 系統初始化完成")
    print(f"休息提醒模式: {Config.REST_REMINDER_MODE}")
    if Config.REST_REMINDER_MODE == "IMAGE":
        print(f"圖片路徑: {Config.REST_IMAGE_PATH}")
    print("\n按 'q' 鍵或 Ctrl+C 退出程式")
    
    # 顯示今日已有的工作記錄
    if detector.total_work_time > 0:
        print(f"\n📊 今日已累計工作時間: {detector.format_time(detector.total_work_time)}")
        detector.show_daily_summary()
    
    try:
        # 設置基於 Tkinter 的檢測定時器
        detector.setup_detection_timer(root)
        
        # 設置 Tkinter 視窗關閉事件
        def on_closing():
            print("\n正在關閉程式...")
            try:
                # 顯示最終統計
                detector.show_daily_summary()
                
                # 匯出每日報告
                if detector.total_work_time > 0:
                    detector.export_daily_report()
                
                # 清理資源
                detector.cleanup()
            except Exception as e:
                print(f"清理時發生錯誤: {e}")
            finally:
                root.quit()
                root.destroy()
        
        root.protocol("WM_DELETE_WINDOW", on_closing)
        
        # 綁定鍵盤事件
        def on_key_press(event):
            if event.char == 'q':
                on_closing()
        
        root.bind('<Key>', on_key_press)
        root.focus_set()  # 確保視窗可以接收鍵盤事件
        
        print("\n按 'q' 鍵或關閉視窗退出程式")
        
        # 運行 Tkinter 主循環
        root.mainloop()
        
    except KeyboardInterrupt:
        print("\n使用者中斷程式")
        try:
            detector.show_daily_summary()
            if detector.total_work_time > 0:
                detector.export_daily_report()
            detector.cleanup()
        except:
            pass
    except Exception as e:
        print(f"程式錯誤: {e}")
        try:
            detector.cleanup()
        except:
            pass

if __name__ == "__main__":
    main()
