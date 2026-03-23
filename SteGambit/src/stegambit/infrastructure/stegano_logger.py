import logging
import time
from datetime import datetime
from pathlib import Path


class SteganoLogger:
    """
    Класс для логирования происходящего в приложении.
    Обеспечивает отслеживание метрик файлов, времени выполнения операций и пр.
    """

    def __init__(self, log_window, log_dir: str = "logs", create_file: bool = False):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        log_file = self.log_dir / f"stegambit_{datetime.now().strftime('%Y-%m-%d')}.log"

        self.logger = logging.getLogger("SteGambit")
        self.logger.setLevel(logging.INFO)

        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', '%H:%M:%S')

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        self.logger.info("--- SteGambit Logger Initialized ---")

    def log_operation_start(self, op_type, container_path):
        """Регистрирует начало операции (внедрение или извлечение)"""
        path = Path(container_path)
        stats = path.stat()

        self.logger.info(f"Начало операции: {op_type.upper()}")
        self.logger.info(f"Файл-носитель: {path.name}")
        self.logger.info(f"Расположение: {path.absolute()}")
        self.logger.info(f"Формат: {path.suffix.upper()}")
        self.logger.info(f"Размер контейнера: {self._format_size(stats.st_size)}")

        return time.time()

    def log_operation_end(self, start_time, secret_info=None):
        """Регистрирует завершение операции и затраченное время"""
        duration = time.time() - start_time

        if secret_info:
            self.logger.info(f"Объект: {secret_info.get('name', 'Unknown')}")
            self.logger.info(f"Размер секрета: {self._format_size(secret_info.get('size', 0))}")

        self.logger.info(f"Продолжительность: {duration:.4f} сек.")
        self.logger.info("Операция успешно завершена.\n" + "-" * 40)

    def log_error(self, error_msg):
        """Регистрирует ошибки в процессе работы"""
        self.logger.error(f"ОШИБКА: {error_msg}")

    def _format_size(self, size_bytes):
        """Вспомогательная функция для форматирования размера файлов"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} TB"