# E:\MeteoraMeme\meteora_bot\src\utils\logger.py

import logging
import sys

def get_logger(name: str) -> logging.Logger:
    """
    Возвращает объект логгера с заданным именем.
    В данный момент логгер пишет в консоль, но можно расширить (лог-файл и т.д.).
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Устанавливаем уровень логирования

    if not logger.handlers:
        # Формат сообщений
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # Обработчик вывода в консоль
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger
