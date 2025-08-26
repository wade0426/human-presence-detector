"""
人體辨識休息提醒系統 - 增強版主程式
整合工作記錄和設定管理功能
"""

import cv2
import time
import threading
from datetime import datetime, timedelta
from ultralytics import YOLO
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import os
import sys

# 匯入自定義模組
import config
from utils import WorkLogger, ConfigManager, format_duration, validate_camera_access, get_system_info

class EnhancedPersonDetectionSystem:
    def __init__(self):
        """初始化增強版人體檢測系統"""
        # 初始化設定管理器
        self.config_manager = ConfigManager(config.SETTINGS_FILE)
        
        # 初始化工作記錄器
        if config.ENABLE_WORK_LOGGING:
            self.work_logger = WorkLogger(config.WORK_LOG_FILE)
        else:
            self.work_logger = None
        
        # 從設定檔載入參數
        timing_settings = self.config_manager.get_timing_settings()
        self.WORK_DURATION = timing_settings['work_duration']
        self.AWAY_THRESHOLD = timing_settings['away_threshold']
        
        try:
            # 初始化YOLO模型
            model_path = self.config_manager.get_setting('MODEL', 'model_path', config.MODEL_PATH)
            if not os.path.exists(model_path):
                model_path = config.FALLBACK_MODEL
                print("指定的模型路徑不存在，正在下載YOLO模型...")
            
            self.model = YOLO(model_path)
            print("YOLO模型載入成功")
        except Exception as e:
            print(f"載入YOLO模型失敗: {e}")
            messagebox.showerror("錯誤", f"載入YOLO模型失敗: {e}")
            sys.exit(1)
        
        # 初始化攝像頭
        camera_index = self.config_manager.get_int_setting('CAMERA', 'camera_index', config.CAMERA_INDEX)
        self.cap = cv2.VideoCapture(camera_index)
        if not self.cap.isOpened():
            messagebox.showerror("錯誤", "無法開啟攝像頭，請確認攝像頭連接正常")
            sys.exit(1)
        
        self.is_running = False
        
        # 狀態變數
        self.person_detected = False
        self.work_start_time = None
        self.away_start_time = None
        self.last_away_start = None  # 用於記錄中斷
        
        # 統計資料
        self.session_stats = {
            'work_sessions': 0,
            'total_work_time': 0,
            'total_breaks': 0,
            'session_start': None
        }
        
        self.setup_ui()
    
    def setup_ui(self):
        """建立增強版使用者介面"""
        self.root = tk.Tk()
        self.root.title(config.WINDOW_TITLE)
        self.root.geometry(config.WINDOW_SIZE)
        self.root.resizable(config.WINDOW_RESIZABLE, config.WINDOW_RESIZABLE)
        
        # 建立選單
        self.create_menu()
        
        # 主框架
        main_frame = tk.Frame(self.root, padx=20, pady=20)
        main_frame.pack(fill="both", expand=True)
        
        # 標題
        title_label = tk.Label(
            main_frame, 
            text="休息提醒系統", 
            font=config.TITLE_FONT,
            fg=config.COLORS['primary']
        )
        title_label.pack(pady=(0, 20))
        
        # 建立標籤頁
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill="both", expand=True, pady=(0, 15))
        
        # 主要監控標籤頁
        self.main_tab = tk.Frame(self.notebook)
        self.notebook.add(self.main_tab, text="監控")
        self.create_main_tab()
        
        # 統計標籤頁
        self.stats_tab = tk.Frame(self.notebook)
        self.notebook.add(self.stats_tab, text="統計")
        self.create_stats_tab()
        
        # 設定標籤頁
        self.settings_tab = tk.Frame(self.notebook)
        self.notebook.add(self.settings_tab, text="設定")
        self.create_settings_tab()
        
        # 控制按鈕框架
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(10, 0))
        
        # 開始監控按鈕
        self.start_btn = tk.Button(
            button_frame, 
            text="開始監控", 
            command=self.start_monitoring,
            font=config.BUTTON_FONT,
            bg=config.COLORS['success'],
            fg="white",
            width=config.BUTTON_WIDTH,
            height=config.BUTTON_HEIGHT
        )
        self.start_btn.pack(side="left", padx=(0, 10))
        
        # 停止監控按鈕
        self.stop_btn = tk.Button(
            button_frame, 
            text="停止監控", 
            command=self.stop_monitoring,
            font=config.BUTTON_FONT,
            bg=config.COLORS['danger'],
            fg="white",
            width=config.BUTTON_WIDTH,
            height=config.BUTTON_HEIGHT,
            state="disabled"
        )
        self.stop_btn.pack(side="left")
    
    def create_menu(self):
        """建立選單列"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # 檔案選單
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="檔案", menu=file_menu)
        file_menu.add_command(label="匯出工作記錄", command=self.export_work_log)
        file_menu.add_command(label="匯出設定", command=self.export_settings)
        file_menu.add_separator()
        file_menu.add_command(label="匯入設定", command=self.import_settings)
        file_menu.add_separator()
        file_menu.add_command(label="離開", command=self.on_closing)
        
        # 工具選單
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="工具", menu=tools_menu)
        tools_menu.add_command(label="系統資訊", command=self.show_system_info)
        tools_menu.add_command(label="攝像頭測試", command=self.test_camera)
        
        # 說明選單
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="說明", menu=help_menu)
        help_menu.add_command(label="使用說明", command=self.show_help)
        help_menu.add_command(label="關於", command=self.show_about)
    
    def create_main_tab(self):
        """建立主要監控標籤頁"""
        # 狀態顯示框架
        status_frame = tk.LabelFrame(self.main_tab, text="系統狀態", font=config.SETTINGS_FONT)
        status_frame.pack(fill="x", pady=(10, 15), padx=10)
        
        # 狀態顯示
        self.status_label = tk.Label(
            status_frame, 
            text=config.STATUS_MESSAGES['standby'], 
            font=config.LABEL_FONT,
            fg=config.COLORS['text_normal'],
            pady=10
        )
        self.status_label.pack()
        
        # 計時顯示框架
        time_frame = tk.LabelFrame(self.main_tab, text="工作時間", font=config.SETTINGS_FONT)
        time_frame.pack(fill="x", pady=(0, 15), padx=10)
        
        # 計時顯示
        self.time_label = tk.Label(
            time_frame, 
            text="00:00:00", 
            font=config.TIME_FONT,
            fg=config.COLORS['text_success'],
            pady=10
        )
        self.time_label.pack()
        
        # 今日統計框架
        today_frame = tk.LabelFrame(self.main_tab, text="今日統計", font=config.SETTINGS_FONT)
        today_frame.pack(fill="x", pady=(0, 10), padx=10)
        
        self.today_stats_label = tk.Label(
            today_frame,
            text="今日工作時間: 0分鐘\n工作時段: 0次",
            font=config.SETTINGS_FONT,
            justify="left",
            pady=10
        )
        self.today_stats_label.pack()
    
    def create_stats_tab(self):
        """建立統計標籤頁"""
        # 日期選擇框架
        date_frame = tk.Frame(self.stats_tab, pady=10)
        date_frame.pack(fill="x", padx=10)
        
        tk.Label(date_frame, text="選擇日期:", font=config.SETTINGS_FONT).pack(side="left")
        
        self.date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self.date_entry = tk.Entry(date_frame, textvariable=self.date_var, width=12)
        self.date_entry.pack(side="left", padx=(10, 5))
        
        tk.Button(date_frame, text="查詢", command=self.update_stats_display,
                 font=config.SETTINGS_FONT).pack(side="left")
        
        # 統計顯示框架
        stats_display_frame = tk.LabelFrame(self.stats_tab, text="工作統計", font=config.SETTINGS_FONT)
        stats_display_frame.pack(fill="both", expand=True, pady=(10, 0), padx=10)
        
        # 建立文字區域和捲軸
        text_frame = tk.Frame(stats_display_frame)
        text_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.stats_text = tk.Text(text_frame, height=15, wrap=tk.WORD)
        scrollbar = tk.Scrollbar(text_frame, orient="vertical", command=self.stats_text.yview)
        self.stats_text.configure(yscrollcommand=scrollbar.set)
        
        self.stats_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def create_settings_tab(self):
        """建立設定標籤頁"""
        # 時間設定框架
        time_settings_frame = tk.LabelFrame(self.settings_tab, text="時間設定", font=config.SETTINGS_FONT)
        time_settings_frame.pack(fill="x", pady=(10, 15), padx=10)
        
        # 工作時間設定
        work_frame = tk.Frame(time_settings_frame, pady=10)
        work_frame.pack(fill="x", padx=10)
        
        tk.Label(work_frame, text="工作提醒時間 (分鐘):", font=config.SETTINGS_FONT).grid(row=0, column=0, sticky="w")
        self.work_var = tk.IntVar(value=self.WORK_DURATION // 60)
        tk.Spinbox(work_frame, from_=1, to=120, textvariable=self.work_var, width=10).grid(row=0, column=1, padx=(10, 0))
        
        # 離開閾值設定
        tk.Label(work_frame, text="離開重置時間 (分鐘):", font=config.SETTINGS_FONT).grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.away_var = tk.IntVar(value=self.AWAY_THRESHOLD // 60)
        tk.Spinbox(work_frame, from_=1, to=30, textvariable=self.away_var, width=10).grid(row=1, column=1, padx=(10, 0), pady=(10, 0))
        
        # 儲存按鈕
        tk.Button(time_settings_frame, text="儲存時間設定", command=self.save_timing_settings,
                 font=config.SETTINGS_FONT, bg=config.COLORS['success'], fg="white").pack(pady=10)
        
        # 系統設定框架
        system_frame = tk.LabelFrame(self.settings_tab, text="系統設定", font=config.SETTINGS_FONT)
        system_frame.pack(fill="x", pady=(0, 10), padx=10)
        
        self.logging_var = tk.BooleanVar(value=config.ENABLE_WORK_LOGGING)
        tk.Checkbutton(system_frame, text="啟用工作記錄", variable=self.logging_var,
                      font=config.SETTINGS_FONT).pack(anchor="w", padx=10, pady=5)
    
    def detect_person(self, frame):
        """人體檢測函數"""
        try:
            confidence = self.config_manager.get_float_setting('MODEL', 'confidence_threshold', config.CONFIDENCE_THRESHOLD)
            results = self.model(frame, classes=config.DETECTION_CLASSES, conf=confidence, verbose=False)
            
            if len(results) > 0 and len(results[0].boxes) > 0:
                return True
            return False
        except Exception as e:
            print(f"人體檢測錯誤: {e}")
            return False
    
    def monitoring_loop(self):
        """主要監控循環"""
        while self.is_running:
            try:
                ret, frame = self.cap.read()
                if not ret:
                    print("無法讀取攝像頭畫面")
                    time.sleep(1)
                    continue
                
                # 檢測人體
                current_person_detected = self.detect_person(frame)
                
                # 狀態轉換邏輯
                self.handle_detection_state(current_person_detected)
                
                # 更新UI
                self.update_ui()
                
                time.sleep(config.DETECTION_INTERVAL)
            except Exception as e:
                print(f"監控循環錯誤: {e}")
                time.sleep(1)
    
    def handle_detection_state(self, current_detected):
        """處理檢測狀態變化"""
        now = datetime.now()
        
        if current_detected:
            # 檢測到人
            if not self.person_detected:
                # 人剛回來
                self.person_detected = True
                
                # 記錄中斷結束
                if self.work_logger and self.last_away_start:
                    self.work_logger.add_interruption(self.last_away_start, now)
                    self.last_away_start = None
                
                if self.work_start_time is None:
                    # 開始新的工作計時
                    self.work_start_time = now
                    if self.work_logger:
                        self.work_logger.start_work_session()
                    print(f"開始工作計時: {now.strftime('%H:%M:%S')}")
                
                self.away_start_time = None
        else:
            # 沒檢測到人
            if self.person_detected:
                # 人剛離開
                self.person_detected = False
                self.away_start_time = now
                self.last_away_start = now
                print(f"檢測到離開: {now.strftime('%H:%M:%S')}")
        
        # 檢查離開時間是否超過閾值
        if (not self.person_detected and 
            self.away_start_time and 
            (now - self.away_start_time).total_seconds() > self.AWAY_THRESHOLD):
            print("離開超過設定時間，重置工作計時")
            self.reset_work_timer()
        
        # 檢查工作時間是否達到設定時間
        if (self.person_detected and 
            self.work_start_time and 
            (now - self.work_start_time).total_seconds() >= self.WORK_DURATION):
            self.show_rest_reminder()
    
    def reset_work_timer(self):
        """重置工作計時器"""
        if self.work_logger and self.work_start_time:
            self.work_logger.end_work_session()
        
        self.work_start_time = None
        self.away_start_time = None
        self.last_away_start = None
    
    def show_rest_reminder(self):
        """顯示休息提醒"""
        if self.work_logger:
            self.work_logger.add_break(datetime.now(), datetime.now())
        
        messagebox.showwarning(
            config.REST_REMINDER_TITLE, 
            config.REST_REMINDER_MESSAGE
        )
        print("顯示休息提醒")
        self.reset_work_timer()
    
    def update_ui(self):
        """更新使用者介面"""
        try:
            # 更新狀態
            if self.person_detected:
                status_text = config.STATUS_MESSAGES['working']
                status_color = config.COLORS['text_success']
            else:
                if self.away_start_time:
                    away_time = int((datetime.now() - self.away_start_time).total_seconds())
                    status_text = config.STATUS_MESSAGES['away_with_time'].format(time=away_time)
                    status_color = config.COLORS['warning']
                else:
                    status_text = config.STATUS_MESSAGES['away']
                    status_color = config.COLORS['text_danger']
            
            # 更新工作時間
            if self.work_start_time:
                elapsed = datetime.now() - self.work_start_time
                time_str = format_duration(elapsed.total_seconds())
            else:
                time_str = "00:00:00"
            
            # 更新今日統計
            if self.work_logger:
                today_stats = self.work_logger.get_daily_stats()
                today_work_minutes = int(today_stats['total_work_time'] / 60)
                today_sessions = today_stats['total_sessions']
                today_text = f"今日工作時間: {today_work_minutes}分鐘\n工作時段: {today_sessions}次"
            else:
                today_text = "今日工作時間: 0分鐘\n工作時段: 0次"
            
            # 在主執行緒更新UI
            def update_labels():
                self.status_label.config(text=status_text, fg=status_color)
                self.time_label.config(text=time_str)
                if hasattr(self, 'today_stats_label'):
                    self.today_stats_label.config(text=today_text)
            
            self.root.after(0, update_labels)
        except Exception as e:
            print(f"UI更新錯誤: {e}")
    
    def start_monitoring(self):
        """開始監控"""
        if not self.is_running:
            self.is_running = True
            self.monitoring_thread = threading.Thread(target=self.monitoring_loop)
            self.monitoring_thread.daemon = True
            self.monitoring_thread.start()
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            print("開始監控")
    
    def stop_monitoring(self):
        """停止監控"""
        self.is_running = False
        self.reset_work_timer()
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        
        # 重置狀態顯示
        self.status_label.config(text=config.STATUS_MESSAGES['standby'], fg=config.COLORS['text_normal'])
        self.time_label.config(text="00:00:00")
        print("停止監控")
    
    def save_timing_settings(self):
        """儲存時間設定"""
        work_minutes = self.work_var.get()
        away_minutes = self.away_var.get()
        
        self.WORK_DURATION = work_minutes * 60
        self.AWAY_THRESHOLD = away_minutes * 60
        
        self.config_manager.update_timing_settings(self.WORK_DURATION, self.AWAY_THRESHOLD)
        messagebox.showinfo("設定", "時間設定已儲存")
    
    def update_stats_display(self):
        """更新統計顯示"""
        if not self.work_logger:
            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(tk.END, "工作記錄功能未啟用")
            return
        
        date_str = self.date_var.get()
        stats = self.work_logger.get_daily_stats(date_str)
        
        self.stats_text.delete(1.0, tk.END)
        
        if stats['total_sessions'] == 0:
            self.stats_text.insert(tk.END, f"日期: {date_str}\n\n沒有工作記錄")
            return
        
        # 顯示統計摘要
        work_hours = stats['total_work_time'] / 3600
        break_minutes = stats['total_break_time'] / 60
        
        summary = f"""日期: {date_str}
總工作時間: {work_hours:.1f} 小時
休息時間: {break_minutes:.1f} 分鐘
工作時段: {stats['total_sessions']} 次

詳細記錄:
"""
        self.stats_text.insert(tk.END, summary)
        
        # 顯示每個工作時段
        for i, session in enumerate(stats['sessions'], 1):
            start_time = datetime.fromisoformat(session['start']).strftime('%H:%M:%S')
            end_time = datetime.fromisoformat(session['end']).strftime('%H:%M:%S')
            work_minutes = session['actual_work_time'] / 60
            
            session_info = f"\n時段 {i}:  {start_time} - {end_time}\n"
            session_info += f"實際工作: {work_minutes:.1f} 分鐘\n"
            
            if session['breaks']:
                session_info += f"休息次數: {len(session['breaks'])} 次\n"
            
            if session['interruptions']:
                session_info += f"中斷次數: {len(session['interruptions'])} 次\n"
            
            self.stats_text.insert(tk.END, session_info)
    
    def export_work_log(self):
        """匯出工作記錄"""
        if not self.work_logger:
            messagebox.showwarning("警告", "工作記錄功能未啟用")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="匯出工作記錄"
        )
        
        if filename:
            try:
                import shutil
                shutil.copy2(self.work_logger.log_file, filename)
                messagebox.showinfo("成功", f"工作記錄已匯出到: {filename}")
            except Exception as e:
                messagebox.showerror("錯誤", f"匯出失敗: {e}")
    
    def export_settings(self):
        """匯出設定"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".ini",
            filetypes=[("INI files", "*.ini"), ("All files", "*.*")],
            title="匯出設定"
        )
        
        if filename:
            if self.config_manager.export_settings(filename):
                messagebox.showinfo("成功", f"設定已匯出到: {filename}")
            else:
                messagebox.showerror("錯誤", "匯出設定失敗")
    
    def import_settings(self):
        """匯入設定"""
        filename = filedialog.askopenfilename(
            filetypes=[("INI files", "*.ini"), ("All files", "*.*")],
            title="匯入設定"
        )
        
        if filename:
            if self.config_manager.import_settings(filename):
                messagebox.showinfo("成功", "設定匯入成功，請重新啟動程式以套用新設定")
            else:
                messagebox.showerror("錯誤", "匯入設定失敗")
    
    def show_system_info(self):
        """顯示系統資訊"""
        info = get_system_info()
        info_text = "\n".join([f"{key}: {value}" for key, value in info.items()])
        messagebox.showinfo("系統資訊", info_text)
    
    def test_camera(self):
        """測試攝像頭"""
        camera_index = self.config_manager.get_int_setting('CAMERA', 'camera_index', config.CAMERA_INDEX)
        if validate_camera_access(camera_index):
            messagebox.showinfo("攝像頭測試", f"攝像頭 {camera_index} 運作正常")
        else:
            messagebox.showerror("攝像頭測試", f"攝像頭 {camera_index} 無法使用")
    
    def show_help(self):
        """顯示使用說明"""
        help_text = """人體辨識休息提醒系統 使用說明

1. 點擊「開始監控」開始監控
2. 系統會檢測您是否在電腦前
3. 持續工作達到設定時間後會提醒休息
4. 離開超過設定時間會自動重置計時器
5. 可在「統計」頁面查看工作記錄
6. 可在「設定」頁面調整參數

快捷鍵:
- 無特殊快捷鍵

注意事項:
- 請確保攝像頭正常運作
- 請確保良好的光線條件
- 建議定期休息保護健康"""
        
        messagebox.showinfo("使用說明", help_text)
    
    def show_about(self):
        """顯示關於資訊"""
        about_text = """人體辨識休息提醒系統 v2.0

基於 YOLO 深度學習模型的智能健康提醒工具

技術特色:
• 即時人體檢測
• 智能工作時間統計
• 自動休息提醒
• 工作記錄管理
• 可自訂設定

開發語言: Python 3.8+
核心技術: YOLO v8, OpenCV, Tkinter

祝您工作愉快，身體健康！"""
        
        messagebox.showinfo("關於", about_text)
    
    def run(self):
        """執行應用程式"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        print("人體辨識休息提醒系統啟動 (增強版)")
        
        # 初始化統計顯示
        self.root.after(1000, self.update_stats_display)
        
        self.root.mainloop()
    
    def on_closing(self):
        """關閉應用程式"""
        self.is_running = False
        
        # 結束當前工作時段
        if self.work_logger and self.work_start_time:
            self.work_logger.end_work_session()
        
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()
        self.root.destroy()
        print("系統已關閉")

if __name__ == "__main__":
    try:
        app = EnhancedPersonDetectionSystem()
        app.run()
    except KeyboardInterrupt:
        print("\n程式被使用者中斷")
    except Exception as e:
        print(f"程式執行錯誤: {e}")
        messagebox.showerror("錯誤", f"程式執行錯誤: {e}")
