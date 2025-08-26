"""
人體辨識休息提醒系統 - 啟動器
提供簡單的選擇介面來啟動不同版本的程式
"""

import sys
import os
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk

class SystemLauncher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("人體辨識休息提醒系統 - 啟動器")
        self.root.geometry("400x300")
        self.root.resizable(False, False)
        
        self.setup_ui()
    
    def setup_ui(self):
        """建立啟動器介面"""
        # 標題
        title_label = tk.Label(
            self.root,
            text="人體辨識休息提醒系統",
            font=("Microsoft YaHei", 16, "bold"),
            fg="#2E4057"
        )
        title_label.pack(pady=20)
        
        # 副標題
        subtitle_label = tk.Label(
            self.root,
            text="請選擇要啟動的版本",
            font=("Microsoft YaHei", 12),
            fg="#666666"
        )
        subtitle_label.pack(pady=(0, 30))
        
        # 按鈕框架
        button_frame = tk.Frame(self.root)
        button_frame.pack(expand=True)
        
        # 基本版本按鈕
        basic_btn = tk.Button(
            button_frame,
            text="基本版本\n(main.py)",
            command=self.launch_basic,
            font=("Microsoft YaHei", 11),
            bg="#4CAF50",
            fg="white",
            width=15,
            height=3
        )
        basic_btn.pack(pady=10)
        
        # 增強版本按鈕
        enhanced_btn = tk.Button(
            button_frame,
            text="增強版本 (推薦)\n(main_enhanced.py)",
            command=self.launch_enhanced,
            font=("Microsoft YaHei", 11),
            bg="#2196F3",
            fg="white",
            width=15,
            height=3
        )
        enhanced_btn.pack(pady=10)
        
        # 系統測試按鈕
        test_btn = tk.Button(
            button_frame,
            text="系統測試",
            command=self.run_test,
            font=("Microsoft YaHei", 10),
            bg="#FF9800",
            fg="white",
            width=15,
            height=2
        )
        test_btn.pack(pady=(20, 10))
        
        # 說明文字
        info_label = tk.Label(
            self.root,
            text="建議首次使用前先執行系統測試",
            font=("Microsoft YaHei", 9),
            fg="#888888"
        )
        info_label.pack(side="bottom", pady=10)
    
    def launch_basic(self):
        """啟動基本版本"""
        if self.check_file_exists("main.py"):
            self.launch_program("main.py", "基本版本")
    
    def launch_enhanced(self):
        """啟動增強版本"""
        if self.check_file_exists("main_enhanced.py"):
            self.launch_program("main_enhanced.py", "增強版本")
    
    def run_test(self):
        """執行系統測試"""
        if self.check_file_exists("test_system.py"):
            self.launch_program("test_system.py", "系統測試", show_console=True)
    
    def check_file_exists(self, filename):
        """檢查檔案是否存在"""
        if not os.path.exists(filename):
            messagebox.showerror("錯誤", f"檔案不存在: {filename}")
            return False
        return True
    
    def launch_program(self, script_name, program_name, show_console=False):
        """啟動程式"""
        try:
            if show_console:
                # 顯示控制台輸出
                subprocess.run([sys.executable, script_name], check=True)
            else:
                # 在背景執行
                if sys.platform == "win32":
                    subprocess.Popen([sys.executable, script_name], 
                                   creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    subprocess.Popen([sys.executable, script_name])
                
                messagebox.showinfo("啟動成功", f"{program_name} 已啟動")
                self.root.quit()
        
        except subprocess.CalledProcessError as e:
            messagebox.showerror("錯誤", f"啟動 {program_name} 失敗: {e}")
        except Exception as e:
            messagebox.showerror("錯誤", f"執行錯誤: {e}")
    
    def run(self):
        """執行啟動器"""
        self.root.mainloop()

def main():
    """主函數"""
    # 檢查是否在正確的目錄
    required_files = ["main.py", "main_enhanced.py", "config.py", "utils.py"]
    missing_files = [f for f in required_files if not os.path.exists(f)]
    
    if missing_files:
        print("錯誤: 缺少必要檔案:")
        for file in missing_files:
            print(f"  - {file}")
        print("\n請確認您在正確的專案目錄中執行此腳本。")
        input("按 Enter 鍵退出...")
        return
    
    try:
        launcher = SystemLauncher()
        launcher.run()
    except Exception as e:
        print(f"啟動器執行錯誤: {e}")
        input("按 Enter 鍵退出...")

if __name__ == "__main__":
    main()
