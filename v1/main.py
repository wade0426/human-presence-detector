import cv2
import time
import threading
from datetime import datetime, timedelta
from ultralytics import YOLO
import tkinter as tk
from tkinter import messagebox, ttk
import os
import sys

class PersonDetectionSystem:
    def __init__(self):
        """初始化人體檢測系統"""
        try:
            # 初始化YOLO模型
            model_path = r'D:\Code\Models\yolov8n.pt'
            if not os.path.exists(model_path):
                # 如果指定路徑不存在，嘗試下載模型到當前目錄
                model_path = 'yolov8n.pt'
                print("指定的模型路徑不存在，正在下載YOLO模型...")
            
            self.model = YOLO(model_path)
            print("YOLO模型載入成功")
        except Exception as e:
            print(f"載入YOLO模型失敗: {e}")
            sys.exit(1)
        
        # 初始化攝像頭
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            messagebox.showerror("錯誤", "無法開啟攝像頭，請確認攝像頭連接正常")
            sys.exit(1)
        
        self.is_running = False
        
        # 狀態變數
        self.person_detected = False
        self.work_start_time = None
        self.away_start_time = None
        
        # 時間設定 (秒)
        self.WORK_DURATION = 3600  # 1小時 = 3600秒
        self.AWAY_THRESHOLD = 300  # 5分鐘 = 300秒
        
        self.setup_ui()
    
    def setup_ui(self):
        """建立使用者介面"""
        self.root = tk.Tk()
        self.root.title("人體辨識休息提醒系統")
        self.root.geometry("450x350")
        self.root.resizable(False, False)
        
        # 主框架
        main_frame = tk.Frame(self.root, padx=20, pady=20)
        main_frame.pack(fill="both", expand=True)
        
        # 標題
        title_label = tk.Label(
            main_frame, 
            text="休息提醒系統", 
            font=("Microsoft YaHei", 18, "bold"),
            fg="#2E4057"
        )
        title_label.pack(pady=(0, 20))
        
        # 狀態顯示框架
        status_frame = tk.LabelFrame(main_frame, text="系統狀態", font=("Microsoft YaHei", 10))
        status_frame.pack(fill="x", pady=(0, 15))
        
        # 狀態顯示
        self.status_label = tk.Label(
            status_frame, 
            text="系統待機中...", 
            font=("Microsoft YaHei", 12),
            fg="#666666",
            pady=10
        )
        self.status_label.pack()
        
        # 計時顯示框架
        time_frame = tk.LabelFrame(main_frame, text="工作時間", font=("Microsoft YaHei", 10))
        time_frame.pack(fill="x", pady=(0, 15))
        
        # 計時顯示
        self.time_label = tk.Label(
            time_frame, 
            text="00:00:00", 
            font=("Courier New", 16, "bold"),
            fg="#2E8B57",
            pady=10
        )
        self.time_label.pack()
        
        # 控制按鈕框架
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(0, 10))
        
        # 開始監控按鈕
        self.start_btn = tk.Button(
            button_frame, 
            text="開始監控", 
            command=self.start_monitoring,
            font=("Microsoft YaHei", 11),
            bg="#4CAF50",
            fg="white",
            width=12,
            height=2
        )
        self.start_btn.pack(side="left", padx=(0, 10))
        
        # 停止監控按鈕
        self.stop_btn = tk.Button(
            button_frame, 
            text="停止監控", 
            command=self.stop_monitoring,
            font=("Microsoft YaHei", 11),
            bg="#f44336",
            fg="white",
            width=12,
            height=2,
            state="disabled"
        )
        self.stop_btn.pack(side="left")
        
        # 設定按鈕
        self.settings_btn = tk.Button(
            main_frame, 
            text="時間設定", 
            command=self.open_settings,
            font=("Microsoft YaHei", 10),
            bg="#2196F3",
            fg="white",
            width=25
        )
        self.settings_btn.pack(pady=(10, 0))
    
    def detect_person(self, frame):
        """人體檢測函數"""
        try:
            # YOLO檢測，classes=[0]表示只檢測人體
            results = self.model(frame, classes=[0], verbose=False)
            
            # 檢查是否檢測到人體
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
                
                time.sleep(1)  # 每秒檢測一次
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
                if self.work_start_time is None:
                    # 開始新的工作計時
                    self.work_start_time = now
                    print(f"開始工作計時: {now.strftime('%H:%M:%S')}")
                self.away_start_time = None
        else:
            # 沒檢測到人
            if self.person_detected:
                # 人剛離開
                self.person_detected = False
                self.away_start_time = now
                print(f"檢測到離開: {now.strftime('%H:%M:%S')}")
        
        # 檢查離開時間是否超過閾值
        if (not self.person_detected and 
            self.away_start_time and 
            (now - self.away_start_time).total_seconds() > self.AWAY_THRESHOLD):
            # 重置工作計時
            print("離開超過5分鐘，重置工作計時")
            self.reset_work_timer()
        
        # 檢查工作時間是否達到1小時
        if (self.person_detected and 
            self.work_start_time and 
            (now - self.work_start_time).total_seconds() >= self.WORK_DURATION):
            self.show_rest_reminder()
    
    def reset_work_timer(self):
        """重置工作計時器"""
        self.work_start_time = None
        self.away_start_time = None
    
    def show_rest_reminder(self):
        """顯示休息提醒"""
        messagebox.showwarning(
            "休息提醒", 
            "您已經持續工作1小時了！\n該起來休息一下囉～\n\n建議休息5-10分鐘，活動一下身體"
        )
        print("顯示休息提醒")
        self.reset_work_timer()
    
    def update_ui(self):
        """更新使用者介面"""
        try:
            # 更新狀態
            if self.person_detected:
                status_text = "✅ 檢測到使用者在工作"
                status_color = "#2E8B57"
            else:
                if self.away_start_time:
                    away_time = int((datetime.now() - self.away_start_time).total_seconds())
                    status_text = f"⏰ 使用者離開 ({away_time}秒)"
                    status_color = "#FF8C00"
                else:
                    status_text = "❌ 使用者不在電腦前"
                    status_color = "#CD5C5C"
            
            # 更新工作時間
            if self.work_start_time:
                elapsed = datetime.now() - self.work_start_time
                hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                time_str = "00:00:00"
            
            # 在主執行緒更新UI
            def update_labels():
                self.status_label.config(text=status_text, fg=status_color)
                self.time_label.config(text=time_str)
            
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
        self.status_label.config(text="系統待機中...", fg="#666666")
        self.time_label.config(text="00:00:00")
        print("停止監控")
    
    def open_settings(self):
        """開啟設定視窗"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("時間設定")
        settings_window.geometry("300x200")
        settings_window.resizable(False, False)
        
        # 工作時間設定
        work_frame = tk.Frame(settings_window, padx=20, pady=10)
        work_frame.pack(fill="x")
        
        tk.Label(work_frame, text="工作提醒時間 (分鐘):", font=("Microsoft YaHei", 10)).pack(anchor="w")
        work_var = tk.IntVar(value=self.WORK_DURATION // 60)
        work_spinbox = tk.Spinbox(work_frame, from_=1, to=120, textvariable=work_var, width=10)
        work_spinbox.pack(anchor="w", pady=(5, 0))
        
        # 離開閾值設定
        away_frame = tk.Frame(settings_window, padx=20, pady=10)
        away_frame.pack(fill="x")
        
        tk.Label(away_frame, text="離開重置時間 (分鐘):", font=("Microsoft YaHei", 10)).pack(anchor="w")
        away_var = tk.IntVar(value=self.AWAY_THRESHOLD // 60)
        away_spinbox = tk.Spinbox(away_frame, from_=1, to=30, textvariable=away_var, width=10)
        away_spinbox.pack(anchor="w", pady=(5, 0))
        
        # 確認按鈕
        def save_settings():
            self.WORK_DURATION = work_var.get() * 60
            self.AWAY_THRESHOLD = away_var.get() * 60
            messagebox.showinfo("設定", "設定已儲存")
            settings_window.destroy()
        
        button_frame = tk.Frame(settings_window, pady=20)
        button_frame.pack()
        
        tk.Button(button_frame, text="儲存", command=save_settings, 
                 font=("Microsoft YaHei", 10), bg="#4CAF50", fg="white", width=8).pack(side="left", padx=5)
        tk.Button(button_frame, text="取消", command=settings_window.destroy, 
                 font=("Microsoft YaHei", 10), bg="#f44336", fg="white", width=8).pack(side="left", padx=5)
    
    def run(self):
        """執行應用程式"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        print("人體辨識休息提醒系統啟動")
        self.root.mainloop()
    
    def on_closing(self):
        """關閉應用程式"""
        self.is_running = False
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()
        self.root.destroy()
        print("系統已關閉")

if __name__ == "__main__":
    try:
        app = PersonDetectionSystem()
        app.run()
    except KeyboardInterrupt:
        print("\n程式被使用者中斷")
    except Exception as e:
        print(f"程式執行錯誤: {e}")
