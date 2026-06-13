"""Windows AppUserModelID（工作列圖示與分組身分）。

Windows 以 AppUserModelID 決定工作列按鈕的圖示、分組與釘選身分。直接用
``python.exe`` 執行時預設沿用直譯器身分,工作列因此顯示 python 圖示而非自家
圖示。於建立任何視窗前設定明確的 AppUserModelID,工作列即改用
``QApplication.setWindowIcon`` 的圖示。

契約對齊 :mod:`src.infra.screen_lock`:非 Windows 平台為 no-op;失敗時安靜
降級(回傳 ``False``、不丟例外),不影響應用程式啟動。
"""

from __future__ import annotations

import ctypes
import logging
import sys

logger = logging.getLogger(__name__)

# 反向網域式唯一識別字串(Microsoft 建議格式 CompanyName.ProductName)。
APP_USER_MODEL_ID = "HumanPresenceDetector.RestReminder"


def is_supported() -> bool:
    return sys.platform == "win32"


def set_app_user_model_id(app_id: str = APP_USER_MODEL_ID) -> bool:
    """於 Windows 設定本行程的明確 AppUserModelID;非 Windows 為 no-op。

    必須在第一個視窗建立前呼叫才會影響工作列圖示(Microsoft 文件建議盡早)。
    回傳是否成功設定。
    """
    if not is_supported():
        logger.info(
            "app_identity: set_app_user_model_id no-op (unsupported platform: %s)",
            sys.platform,
        )
        return False
    try:
        result = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(  # type: ignore[attr-defined, unused-ignore]
            app_id
        )
    except (AttributeError, OSError):
        logger.warning("app_identity: 設定 AppUserModelID 失敗", exc_info=True)
        return False
    if result != 0:  # 非 S_OK 的 HRESULT
        logger.warning(
            "app_identity: SetCurrentProcessExplicitAppUserModelID 回傳 0x%08X",
            result & 0xFFFFFFFF,
        )
        return False
    return True
