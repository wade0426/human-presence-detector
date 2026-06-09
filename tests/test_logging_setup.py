from __future__ import annotations

import builtins
import logging
import os
from logging.handlers import RotatingFileHandler

import pytest


@pytest.fixture(autouse=True)
def clean_root_handlers() -> None:
    yield
    logging.root.handlers.clear()


def test_setup_logging_creates_file_handler(tmp_path: object) -> None:
    from src.logging_setup import setup_logging

    logger = setup_logging(log_dir=str(tmp_path), level=logging.DEBUG)
    handlers = [handler for handler in logger.handlers if isinstance(handler, RotatingFileHandler)]

    assert len(handlers) >= 1
    assert (tmp_path / "app.log").exists()


def test_setup_logging_level(tmp_path: object) -> None:
    from src.logging_setup import setup_logging

    logger = setup_logging(log_dir=str(tmp_path), level=logging.WARNING)

    assert logger.level == logging.WARNING


def test_setup_logging_reuses_existing_rotating_handler(tmp_path: object) -> None:
    from src.logging_setup import setup_logging

    logger = setup_logging(log_dir=str(tmp_path), level=logging.INFO)
    logger = setup_logging(log_dir=str(tmp_path), level=logging.DEBUG)
    handlers = [handler for handler in logger.handlers if isinstance(handler, RotatingFileHandler)]

    assert len(handlers) == 1
    assert logger.level == logging.DEBUG


def test_suppress_decoder_noise_sets_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENCV_FFMPEG_LOGLEVEL", raising=False)

    from src.logging_setup import suppress_decoder_noise

    suppress_decoder_noise()

    assert os.environ.get("OPENCV_FFMPEG_LOGLEVEL") == "-8"


def test_suppress_decoder_noise_no_cv2(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def mock_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "cv2":
            raise ImportError("no cv2")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    from src.logging_setup import suppress_decoder_noise

    suppress_decoder_noise()
