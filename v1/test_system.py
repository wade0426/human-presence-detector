"""
人體辨識休息提醒系統 - 系統測試腳本
用於驗證各模組功能是否正常
"""

import sys
import os

def test_imports():
    """測試模組匯入"""
    print("測試模組匯入...")
    
    try:
        import config
        print("✅ config.py 匯入成功")
    except ImportError as e:
        print(f"❌ config.py 匯入失敗: {e}")
        return False
    
    try:
        import utils
        print("✅ utils.py 匯入成功")
    except ImportError as e:
        print(f"❌ utils.py 匯入失敗: {e}")
        return False
    
    return True

def test_config():
    """測試配置功能"""
    print("\n測試配置功能...")
    
    try:
        import config
        
        # 驗證配置
        errors = config.validate_config()
        if errors:
            print("❌ 配置驗證失敗:")
            for error in errors:
                print(f"   {error}")
            return False
        else:
            print("✅ 配置驗證通過")
        
        # 測試配置函數
        minutes = config.get_work_duration_minutes()
        print(f"✅ 工作時間: {minutes} 分鐘")
        
        return True
        
    except Exception as e:
        print(f"❌ 配置測試失敗: {e}")
        return False

def test_utils():
    """測試工具模組"""
    print("\n測試工具模組...")
    
    try:
        from utils import WorkLogger, ConfigManager, format_duration
        
        # 測試時間格式化
        time_str = format_duration(3661)  # 1小時1分1秒
        if time_str == "01:01:01":
            print("✅ 時間格式化功能正常")
        else:
            print(f"❌ 時間格式化錯誤: 預期 '01:01:01'，得到 '{time_str}'")
            return False
        
        # 測試WorkLogger
        logger = WorkLogger("test_log.json")
        print("✅ WorkLogger 初始化成功")
        
        # 測試ConfigManager
        config_mgr = ConfigManager("test_config.ini")
        print("✅ ConfigManager 初始化成功")
        
        # 清理測試檔案
        for test_file in ["test_log.json", "test_config.ini"]:
            if os.path.exists(test_file):
                os.remove(test_file)
                print(f"✅ 清理測試檔案: {test_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ 工具模組測試失敗: {e}")
        return False

def test_dependencies():
    """測試依賴套件"""
    print("\n測試依賴套件...")
    
    # 必要套件列表
    required_packages = [
        ('cv2', 'OpenCV'),
        ('numpy', 'NumPy'),
        ('PIL', 'Pillow'),
        ('tkinter', 'Tkinter'),
    ]
    
    all_ok = True
    
    for module_name, package_name in required_packages:
        try:
            __import__(module_name)
            print(f"✅ {package_name} 可用")
        except ImportError:
            print(f"❌ {package_name} 未安裝或不可用")
            all_ok = False
    
    # 測試 YOLO (可能需要下載模型)
    try:
        from ultralytics import YOLO
        print("✅ Ultralytics YOLO 可用")
    except ImportError:
        print("❌ Ultralytics YOLO 未安裝")
        all_ok = False
    
    return all_ok

def test_camera_access():
    """測試攝像頭存取"""
    print("\n測試攝像頭存取...")
    
    try:
        from utils import validate_camera_access
        
        if validate_camera_access(0):
            print("✅ 攝像頭 0 可用")
            return True
        else:
            print("❌ 攝像頭 0 無法使用")
            return False
    except Exception as e:
        print(f"❌ 攝像頭測試失敗: {e}")
        return False

def test_system_info():
    """測試系統資訊"""
    print("\n系統資訊:")
    
    try:
        from utils import get_system_info
        
        info = get_system_info()
        for key, value in info.items():
            print(f"  {key}: {value}")
        
        return True
    except Exception as e:
        print(f"❌ 取得系統資訊失敗: {e}")
        return False

def run_all_tests():
    """執行所有測試"""
    print("🔍 開始系統測試...\n")
    
    tests = [
        ("模組匯入", test_imports),
        ("配置功能", test_config),
        ("工具模組", test_utils),
        ("依賴套件", test_dependencies),
        ("攝像頭存取", test_camera_access),
        ("系統資訊", test_system_info),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"=" * 50)
        if test_func():
            passed += 1
            print(f"✅ {test_name} 測試通過")
        else:
            print(f"❌ {test_name} 測試失敗")
    
    print(f"\n" + "=" * 50)
    print(f"🎯 測試結果: {passed}/{total} 項測試通過")
    
    if passed == total:
        print("🎉 所有測試都通過！系統可以正常運行。")
        print("\n建議執行順序:")
        print("1. 基本版本: python main.py")
        print("2. 增強版本: python main_enhanced.py (推薦)")
    else:
        print("⚠️  部分測試失敗，請檢查相關問題。")
        print("\n可能的解決方案:")
        print("1. 執行: pip install -r requirements.txt")
        print("2. 確認攝像頭連接正常")
        print("3. 檢查 Python 版本 (需要 3.8+)")
    
    return passed == total

if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n測試被使用者中斷")
    except Exception as e:
        print(f"\n測試執行錯誤: {e}")
        sys.exit(1)
