import logging
import os
from logging.handlers import RotatingFileHandler

log_dir = "./logs"
os.makedirs(log_dir, exist_ok=True)
log_filepath = os.path.join(log_dir, "fmanager_bot.log")


def setup_logger(logger_name):
    """Настройка логгеров.

    Returns:
        Logger: Логгер.
    """

    if len(logging.getLogger().handlers) > 0:
        return logging.getLogger(logger_name)

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            RotatingFileHandler(
                log_filepath, maxBytes=10 * 1024 * 1024, backupCount=10, encoding="utf-8"
            ),
            logging.StreamHandler(),
        ],
    )

    # Custom
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

    # Aiogram
    logging.getLogger("aiogram").setLevel(logging.INFO)

    # Asyncio
    logging.getLogger("asyncio").setLevel(logging.INFO)

    # SqlAlchemy
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

    # YaDisk
    logging.getLogger("yadisk").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    return logger
