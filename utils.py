"""
人體辨識休息提醒系統 - 工具模組
包含資料記錄、設定管理等進階功能
"""

import json
import configparser
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import config

class WorkLogger:
    """工作時段記錄器"""
    
    def __init__(self, log_file: str = "work_log.json"):
        """
        初始化工作記錄器
        
        Args:
            log_file: 記錄檔案路徑
        """
        self.log_file = log_file
        self.current_session = None
        
    def start_work_session(self) -> None:
        """開始工作時段記錄"""
        self.current_session = {
            "start_time": datetime.now(),
            "breaks": [],  # 記錄中間的休息時段
            "interruptions": []  # 記錄中斷(離開)時段
        }
        print(f"開始記錄工作時段: {self.current_session['start_time'].strftime('%H:%M:%S')}")
    
    def add_break(self, break_start: datetime, break_end: datetime) -> None:
        """
        添加休息時段記錄
        
        Args:
            break_start: 休息開始時間
            break_end: 休息結束時間
        """
        if self.current_session:
            break_duration = (break_end - break_start).total_seconds()
            self.current_session["breaks"].append({
                "start": break_start.isoformat(),
                "end": break_end.isoformat(),
                "duration": break_duration
            })
            print(f"記錄休息時段: {break_duration:.0f}秒")
    
    def add_interruption(self, interruption_start: datetime, interruption_end: datetime) -> None:
        """
        添加中斷時段記錄
        
        Args:
            interruption_start: 中斷開始時間
            interruption_end: 中斷結束時間
        """
        if self.current_session:
            interruption_duration = (interruption_end - interruption_start).total_seconds()
            self.current_session["interruptions"].append({
                "start": interruption_start.isoformat(),
                "end": interruption_end.isoformat(),
                "duration": interruption_duration
            })
            print(f"記錄中斷時段: {interruption_duration:.0f}秒")
    
    def end_work_session(self, end_time: Optional[datetime] = None) -> None:
        """
        結束工作時段記錄
        
        Args:
            end_time: 結束時間，預設為當前時間
        """
        if not self.current_session:
            return
        
        if end_time is None:
            end_time = datetime.now()
        
        # 計算總工作時間
        total_duration = (end_time - self.current_session["start_time"]).total_seconds()
        
        # 計算實際工作時間 (扣除休息和中斷)
        break_time = sum(b["duration"] for b in self.current_session["breaks"])
        interruption_time = sum(i["duration"] for i in self.current_session["interruptions"])
        actual_work_time = total_duration - break_time - interruption_time
        
        # 建立完整的工作時段記錄
        session_record = {
            "start": self.current_session["start_time"].isoformat(),
            "end": end_time.isoformat(),
            "total_duration": total_duration,
            "actual_work_time": actual_work_time,
            "break_time": break_time,
            "interruption_time": interruption_time,
            "breaks": self.current_session["breaks"],
            "interruptions": self.current_session["interruptions"],
            "date": self.current_session["start_time"].strftime("%Y-%m-%d")
        }
        
        self.log_work_session(session_record)
        self.current_session = None
        print(f"結束工作時段記錄，實際工作時間: {actual_work_time/60:.1f}分鐘")
    
    def log_work_session(self, session_data: Dict) -> None:
        """
        記錄工作時段到檔案
        
        Args:
            session_data: 工作時段資料
        """
        try:
            # 讀取現有記錄
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
            else:
                logs = []
            
            # 添加新記錄
            logs.append(session_data)
            
            # 清理舊記錄 (超過指定天數)
            self._cleanup_old_logs(logs)
            
            # 儲存到檔案
            with open(self.log_file, 'w', encoding='utf-8') as f:
                json.dump(logs, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"記錄工作時段失敗: {e}")
    
    def _cleanup_old_logs(self, logs: List[Dict]) -> None:
        """清理超過指定天數的舊記錄"""
        cutoff_date = datetime.now() - timedelta(days=config.MAX_LOG_DAYS)
        
        # 過濾掉舊記錄
        valid_logs = []
        for log in logs:
            try:
                log_date = datetime.fromisoformat(log["start"]).date()
                if log_date >= cutoff_date.date():
                    valid_logs.append(log)
            except (KeyError, ValueError):
                # 保留格式不正確的記錄，避免資料遺失
                valid_logs.append(log)
        
        logs[:] = valid_logs
    
    def get_daily_stats(self, date: str = None) -> Dict:
        """
        取得指定日期的工作統計
        
        Args:
            date: 日期字串 (YYYY-MM-DD)，預設為今天
        
        Returns:
            包含工作統計的字典
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        try:
            if not os.path.exists(self.log_file):
                return self._empty_stats()
            
            with open(self.log_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
            
            # 篩選指定日期的記錄
            daily_logs = [log for log in logs if log.get("date") == date]
            
            if not daily_logs:
                return self._empty_stats()
            
            # 計算統計資料
            total_work_time = sum(log["actual_work_time"] for log in daily_logs)
            total_break_time = sum(log["break_time"] for log in daily_logs)
            total_sessions = len(daily_logs)
            
            return {
                "date": date,
                "total_work_time": total_work_time,
                "total_break_time": total_break_time,
                "total_sessions": total_sessions,
                "sessions": daily_logs
            }
            
        except Exception as e:
            print(f"取得日統計失敗: {e}")
            return self._empty_stats()
    
    def _empty_stats(self) -> Dict:
        """回傳空的統計資料"""
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_work_time": 0,
            "total_break_time": 0,
            "total_sessions": 0,
            "sessions": []
        }


class ConfigManager:
    """設定檔管理器"""
    
    def __init__(self, config_file: str = "settings.ini"):
        """
        初始化設定管理器
        
        Args:
            config_file: 設定檔案路徑
        """
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.load_config()
    
    def load_config(self) -> None:
        """載入設定檔"""
        try:
            if os.path.exists(self.config_file):
                self.config.read(self.config_file, encoding='utf-8')
                print(f"載入設定檔: {self.config_file}")
            else:
                print("設定檔不存在，建立預設設定")
                self.create_default_config()
        except Exception as e:
            print(f"載入設定檔失敗: {e}")
            self.create_default_config()
    
    def create_default_config(self) -> None:
        """建立預設設定"""
        self.config['TIMING'] = {
            'work_duration': str(config.WORK_DURATION),
            'away_threshold': str(config.AWAY_THRESHOLD),
            'detection_interval': str(config.DETECTION_INTERVAL)
        }
        
        self.config['CAMERA'] = {
            'camera_index': str(config.CAMERA_INDEX),
            'frame_width': str(config.FRAME_WIDTH),
            'frame_height': str(config.FRAME_HEIGHT)
        }
        
        self.config['MODEL'] = {
            'model_path': config.MODEL_PATH,
            'confidence_threshold': str(config.CONFIDENCE_THRESHOLD)
        }
        
        self.config['UI'] = {
            'window_title': config.WINDOW_TITLE,
            'window_size': config.WINDOW_SIZE
        }
        
        self.config['LOGGING'] = {
            'enable_work_logging': str(config.ENABLE_WORK_LOGGING),
            'work_log_file': config.WORK_LOG_FILE,
            'max_log_days': str(config.MAX_LOG_DAYS)
        }
        
        self.save_config()
    
    def save_config(self) -> None:
        """儲存設定檔"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
            print(f"設定已儲存: {self.config_file}")
        except Exception as e:
            print(f"儲存設定檔失敗: {e}")
    
    def get_setting(self, section: str, key: str, fallback=None):
        """
        取得設定值
        
        Args:
            section: 設定區段
            key: 設定鍵
            fallback: 預設值
        
        Returns:
            設定值
        """
        try:
            return self.config.get(section, key, fallback=fallback)
        except Exception:
            return fallback
    
    def get_int_setting(self, section: str, key: str, fallback: int = 0) -> int:
        """取得整數設定值"""
        try:
            return self.config.getint(section, key, fallback=fallback)
        except Exception:
            return fallback
    
    def get_float_setting(self, section: str, key: str, fallback: float = 0.0) -> float:
        """取得浮點數設定值"""
        try:
            return self.config.getfloat(section, key, fallback=fallback)
        except Exception:
            return fallback
    
    def get_boolean_setting(self, section: str, key: str, fallback: bool = False) -> bool:
        """取得布林值設定值"""
        try:
            return self.config.getboolean(section, key, fallback=fallback)
        except Exception:
            return fallback
    
    def set_setting(self, section: str, key: str, value: str) -> None:
        """
        設定設定值
        
        Args:
            section: 設定區段
            key: 設定鍵
            value: 設定值
        """
        if section not in self.config:
            self.config.add_section(section)
        
        self.config.set(section, key, str(value))
    
    def update_timing_settings(self, work_duration: int, away_threshold: int) -> None:
        """
        更新時間設定
        
        Args:
            work_duration: 工作時間(秒)
            away_threshold: 離開閾值(秒)
        """
        self.set_setting('TIMING', 'work_duration', str(work_duration))
        self.set_setting('TIMING', 'away_threshold', str(away_threshold))
        self.save_config()
    
    def get_timing_settings(self) -> Dict[str, int]:
        """取得時間設定"""
        return {
            'work_duration': self.get_int_setting('TIMING', 'work_duration', config.WORK_DURATION),
            'away_threshold': self.get_int_setting('TIMING', 'away_threshold', config.AWAY_THRESHOLD),
            'detection_interval': self.get_int_setting('TIMING', 'detection_interval', config.DETECTION_INTERVAL)
        }
    
    def export_settings(self, export_file: str) -> bool:
        """
        匯出設定到檔案
        
        Args:
            export_file: 匯出檔案路徑
        
        Returns:
            是否成功匯出
        """
        try:
            with open(export_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
            print(f"設定已匯出到: {export_file}")
            return True
        except Exception as e:
            print(f"匯出設定失敗: {e}")
            return False
    
    def import_settings(self, import_file: str) -> bool:
        """
        從檔案匯入設定
        
        Args:
            import_file: 匯入檔案路徑
        
        Returns:
            是否成功匯入
        """
        try:
            if not os.path.exists(import_file):
                print(f"匯入檔案不存在: {import_file}")
                return False
            
            new_config = configparser.ConfigParser()
            new_config.read(import_file, encoding='utf-8')
            
            # 驗證設定檔格式
            required_sections = ['TIMING', 'CAMERA', 'MODEL']
            for section in required_sections:
                if section not in new_config:
                    print(f"匯入檔案缺少必要區段: {section}")
                    return False
            
            # 備份當前設定
            backup_file = f"{self.config_file}.backup"
            self.export_settings(backup_file)
            
            # 匯入新設定
            self.config = new_config
            self.save_config()
            
            print(f"設定已從 {import_file} 匯入")
            return True
            
        except Exception as e:
            print(f"匯入設定失敗: {e}")
            return False


# ==================== 工具函數 ====================

def format_duration(seconds: float) -> str:
    """
    格式化時間長度
    
    Args:
        seconds: 秒數
    
    Returns:
        格式化的時間字串 (HH:MM:SS)
    """
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def validate_camera_access(camera_index: int = 0) -> bool:
    """
    驗證攝像頭是否可用
    
    Args:
        camera_index: 攝像頭索引
    
    Returns:
        是否可用
    """
    try:
        import cv2
        cap = cv2.VideoCapture(camera_index)
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            return ret and frame is not None
        return False
    except Exception:
        return False

def get_system_info() -> Dict[str, str]:
    """
    取得系統資訊
    
    Returns:
        系統資訊字典
    """
    import platform
    import sys
    
    try:
        import cv2
        opencv_version = cv2.__version__
    except ImportError:
        opencv_version = "未安裝"
    
    try:
        from ultralytics import YOLO
        yolo_available = "可用"
    except ImportError:
        yolo_available = "未安裝"
    
    return {
        "作業系統": platform.system(),
        "作業系統版本": platform.version(),
        "Python版本": sys.version,
        "OpenCV版本": opencv_version,
        "YOLO可用性": yolo_available,
        "攝像頭可用性": "可用" if validate_camera_access() else "不可用"
    }


if __name__ == "__main__":
    # 測試功能
    print("測試工作記錄器...")
    logger = WorkLogger("test_work_log.json")
    
    print("\n測試設定管理器...")
    config_manager = ConfigManager("test_settings.ini")
    
    print("\n系統資訊:")
    for key, value in get_system_info().items():
        print(f"  {key}: {value}")
    
    print("\n測試完成")
