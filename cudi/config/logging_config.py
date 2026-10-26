"""Ein gemeinsames Logging für alle CUDI-Module (Datei + optional Konsole)."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging(log_dir: Path, console: bool = False, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("cudi")
    logger.setLevel(level)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = (log_dir / "cudi.log").resolve()

    has_file = any(
        isinstance(h, RotatingFileHandler) and Path(h.baseFilename) == log_file
        for h in logger.handlers
    )
    if not has_file:
        handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
        handler.setFormatter(logging.Formatter(_FORMAT))
        logger.addHandler(handler)
    if console and not any(type(h) is logging.StreamHandler for h in logger.handlers):
        stream = logging.StreamHandler()
        stream.setFormatter(logging.Formatter(_FORMAT))
        stream.setLevel(logging.WARNING)
        logger.addHandler(stream)
    return logger
