# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — 人體辨識休息提醒系統（onedir / Windows）。

於專案根目錄執行（建議用 packaging/build.ps1，它會在打包後把 config.yaml
與 data/ 補到輸出資料夾）：

    pyinstaller packaging/human_presence_detector.spec --noconfirm --clean

產物：dist/HumanPresenceDetector/
    HumanPresenceDetector.exe   ← 圖示取自 data/assets/icon.ico
    _internal/                  ← 直譯器、相依套件、bundle 內的 data/assets
    （config.yaml 與 data/ 由 build.ps1 於打包後補上，供 CWD 相對路徑讀取）

路徑解析（與原始碼一致，無需改 app 程式）：
- icon.png / trumpet.png 是 __file__ 定錨（icons.py parents[2]、
  preview.py parents[3]），凍結後解析到 bundle 根（_internal），故以
  add-data 把 data/assets 收進 _internal/data/assets。
- config.yaml、data/model/yolov8n.pt、data/records.sqlite 是 CWD 相對；
  src.shell.app.main() 於凍結時 chdir 到 exe 資料夾，所以這些檔案要放在
  exe 旁（由 build.ps1 複製），不是放進 _internal。
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# SPECPATH 由 PyInstaller 注入＝本 spec 所在資料夾（packaging/），其上層為專案根。
ROOT = Path(SPECPATH).resolve().parent  # noqa: F821 (SPECPATH 為 PyInstaller 全域)
APP_NAME = "HumanPresenceDetector"

# __file__ 定錨資產：凍結後需在 bundle 根找到 data/assets/*（icon.png、trumpet.png）。
datas = [(str(ROOT / "data" / "assets"), "data/assets")]

# ultralytics 以資料檔（預設 .yaml）與動態匯入運作，需明確收集。
datas += collect_data_files("ultralytics")
hiddenimports = collect_submodules("ultralytics")

a = Analysis(  # noqa: F821
    [str(ROOT / "src" / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 不入庫的開發/測試相依，縮小體積；保留 matplotlib（ultralytics 視情況匯入）。
    excludes=["tkinter", "pytest", "pytest_qt", "_pytest"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI 應用，無主控台視窗（除錯時可暫改 True 以看 traceback）
    disable_windowed_traceback=False,
    icon=str(ROOT / "data" / "assets" / "icon.ico"),  # Windows exe 檔案圖示
)
coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)
