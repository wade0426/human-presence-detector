# 打包成 Windows 應用程式（PyInstaller / onedir）

把專案打包成帶自家圖示、可直接執行的 Windows 桌面應用程式。

## 一鍵打包

於專案根目錄執行：

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```

腳本會：

1. 確認 `PyInstaller` 已安裝（缺則依 `requirements-build.txt` 安裝）。
2. 依 `human_presence_detector.spec` 打包（onedir）。
3. 把 `config.yaml`（取自 `config.dist.yaml`）與 `data/`（`model`、`assets`）
   補到輸出資料夾。

產物在 **`dist/HumanPresenceDetector/`**，整包壓縮即可發佈。

## 手動打包（等同腳本第 2 步）

```powershell
python -m pip install -r packaging\requirements-build.txt
python -m PyInstaller packaging\human_presence_detector.spec --noconfirm --clean
```

之後需自行把 `packaging\config.dist.yaml` 複製為
`dist\HumanPresenceDetector\config.yaml`，並把 `data\model\yolov8n.pt`、
`data\assets\*` 複製到 `dist\HumanPresenceDetector\data\` 下（`build.ps1`
已自動處理）。

## 輸出資料夾結構

```text
dist/HumanPresenceDetector/
├─ HumanPresenceDetector.exe   ← 檔案圖示取自 data/assets/icon.ico
├─ _internal/                  ← 直譯器、相依套件、bundle 內的 data/assets
├─ config.yaml                 ← 可編輯，第一次使用請依實機調整
└─ data/
   ├─ model/yolov8n.pt
   ├─ assets/                  ← rest.jpg、Radar.mp3、icon.png …
   └─ records.sqlite           ← 執行時自動產生
```

## 圖示如何生效

- **exe 檔案圖示**：spec 的 `EXE(icon=…/icon.ico)` 指定，顯示在檔案總管。
- **視窗 / 工作列 / Alt-Tab 圖示**：程式啟動時 `app.setWindowIcon(load_app_icon())`
  載入 `data/assets/icon.png`；該檔以 `--add-data` 收進 `_internal/data/assets`，
  凍結後仍由 `icons.py` 的 `__file__` 定錨路徑解析得到。
- **工作列不沿用 python 圖示**：程式以 `AppUserModelID` 設定自家身分。

## 路徑解析設計（為何 config/model 放在 exe 旁）

程式有兩種資源路徑：

| 類型 | 例子 | 凍結後解析位置 | 處置 |
| --- | --- | --- | --- |
| `__file__` 定錨 | `icon.png`、`trumpet.png` | bundle 根（`_internal`） | spec `--add-data` 收進 bundle |
| CWD 相對 | `config.yaml`、`yolov8n.pt`、`records.sqlite` | 工作目錄 | 放在 exe 旁；程式啟動時 `chdir` 到 exe 資料夾 |

`src/infra/frozen.py` 的 `chdir_to_bundle()` 確保即使從「開始功能表／釘選」
啟動（此時 CWD 可能是 `System32`）也能讀到 `config.yaml` 與模型。

## 疑難排解

- **想看 traceback**：spec 內 `console=False` 暫改 `True` 重新打包，或從
  終端機執行 exe 觀察輸出。
- **缺模組（ModuleNotFoundError）**：把模組名加進 spec 的 `hiddenimports`。
- **JPG 提醒圖無法顯示**：確認 PySide6 的 `imageformats`（qjpeg）外掛有被收進
  `_internal/PySide6/plugins/imageformats`（PySide6 hook 通常會自動處理）。
- **體積過大**：可在 spec 的 `excludes` 加上未使用的大型套件再測試。
- **CUDA**：預設打包的是 CPU 版 PyTorch（除非你的環境已裝 CUDA 版）；要
  GPU 推論請在打包環境先安裝對應的 CUDA PyTorch。
