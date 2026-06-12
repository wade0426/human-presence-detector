"""程式進入點：薄轉發至 src.shell.app（保住 ``python -m src.main``）。"""

from __future__ import annotations

from src.shell.app import main

__all__ = ["main"]

if __name__ == "__main__":
    raise SystemExit(main())
