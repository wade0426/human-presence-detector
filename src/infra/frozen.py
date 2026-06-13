"""PyInstaller 凍結執行環境輔助（工作目錄／資源根目錄）。

凍結成 onedir 後,從開始功能表或釘選圖示啟動時,行程的工作目錄可能是
``C:\\Windows\\System32`` 之類,使得 CWD 相對路徑(``config.yaml``、
``data/model/yolov8n.pt``、``data/records.sqlite``)讀不到而啟動即失敗。
於進入點呼叫 :func:`chdir_to_bundle` 先把工作目錄切到 exe 所在資料夾即可
穩定解析。開發模式(未凍結)一律為 no-op,不影響 ``python -m src.main``。
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def is_frozen() -> bool:
    """是否以 PyInstaller 凍結後執行(``sys.frozen`` 由 bootloader 設定)。"""
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    """凍結時回傳 exe 所在資料夾;開發時回傳專案根目錄。

    開發模式以本模組位置定錨(frozen.py 在 src/infra/,parents[2] 為專案根),
    與 CWD 無關。
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def chdir_to_bundle() -> bool:
    """凍結時把工作目錄切到 exe 所在資料夾,回傳是否實際切換(未凍結為 False)。"""
    if not is_frozen():
        return False
    target = bundle_dir()
    os.chdir(target)
    logger.info("frozen: 工作目錄切至 bundle 資料夾 %s", target)
    return True
