from __future__ import annotations
import logging, os, sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logging(name: str = "agentic-ai", log_dir: str = ".logs"):
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S")

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    sh.setLevel(logging.INFO)

    fh = RotatingFileHandler(os.path.join(log_dir, f"{name}.log"), maxBytes=5_000_000, backupCount=2)
    fh.setFormatter(fmt)
    fh.setLevel(logging.INFO)

    if not logger.handlers:
        logger.addHandler(sh)
        logger.addHandler(fh)
    return logger

logger = setup_logging()
