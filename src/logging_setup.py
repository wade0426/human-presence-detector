from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(
    log_dir: str = "data/logs",
    level: int = logging.INFO,
    max_bytes: int = 1_000_000,
    backup_count: int = 3,
) -> logging.Logger:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    log_path = (Path(log_dir) / "app.log").resolve()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    for handler in list(root_logger.handlers):
        if (
            isinstance(handler, RotatingFileHandler)
            and Path(handler.baseFilename).resolve() == log_path
        ):
            root_logger.removeHandler(handler)
            handler.close()
    root_logger.addHandler(file_handler)
    log_path.touch(exist_ok=True)
    return root_logger


def suppress_decoder_noise() -> None:
    os.environ.setdefault("OPENCV_FFMPEG_LOGLEVEL", "-8")
    try:
        import cv2

        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
    except Exception:
        pass
