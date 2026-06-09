# 開發環境與專案骨架

> **前置條件**：無

## 任務

- [ ] **E1** 建立 `environment.yml`，包含以下套件：
  ```yaml
  name: project
  channels:
    - conda-forge
    - defaults
  dependencies:
    - python=3.11
    - pip
    - pip:
      - pyside6
      - opencv-python
      - ultralytics
      - pyyaml
      - pytest
      - pytest-qt
  ```

- [ ] **E2** 建立 `config.yaml`，使用 `docs/proposal.md` §9.1 的完整預設值（source / detection / presence / timer / reminder / logging / ui 全區塊）

- [ ] **E3** 建立 `data/assets/rest_placeholder.png`（任意一張 PNG 小圖即可，用於測試彈窗提醒）

- [ ] **E4** 建立以下空目錄（含 `__init__.py`）：
  - `src/`
  - `src/capture/`
  - `src/detection/`
  - `src/app/`
  - `src/reminder/`
  - `src/ui/`
  - `tests/`

- [ ] **E5** 建立 `tests/conftest.py`，加入 `tmp_path` 相關 fixture 備用（目前可為空）

- [ ] **E6** 確認 `rtk pytest` 可在空 `tests/` 下執行不報錯（collected 0 items）

- [ ] **E7** `git commit -m "chore: project skeleton and config"`
