import os
import time
from stegano_logger import SteganoLogger


# Пример использования (для тестирования первого дня)
if __name__ == "__main__":
    stego_log = SteganoLogger()

    # Эмуляция процесса
    # 1. Допустим, пользователь выбрал файл
    start = stego_log.log_operation_start("внедрение", "test_image.png")  # файл должен существовать для замера размера

    # 2. Имитируем задержку работы алгоритма
    time.sleep(1.2)

    # 3. Завершаем лог
    stego_log.log_operation_end(start, {"name": "secret_message.txt", "size": 1024})


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    print_hi('PyCharm')

