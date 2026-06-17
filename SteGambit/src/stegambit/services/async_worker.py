"""StegoWorker — фоновый поток для тяжёлых операций StegoService.

Архитектурная база: ADR 008 "Модель многопоточности и изоляция GUI".

Контракт с GUI:
    Сигналы:
        - finished(StegoResponse) — операция завершилась.
        - error(str) — инфраструктурная авария (исключение, не пойманное
          бизнес-логикой). Используется для критических сбоев типа OOM, повреждённой инсталляции зависимостей и т.п.
    Запуск: worker.start() — стандартный метод QThread, ставит поток
      в очередь Qt event loop. Тело выполнится в методе run().

    Базовый класс QObject -> QThread.
    GUI не блокируется на время операции — главный event loop Qt продолжает обрабатывать события.
"""
from PyQt6.QtCore import QThread, pyqtSignal

from stegambit.infrastructure.stegano_logger import get_logger
from stegambit.models.dto import StegoTaskRequest, StegoResponse
from stegambit.services.stego_service import StegoService
from stegambit.core.exceptions import (
    InvalidFrameError, CompatibilityError,
    InvalidPasswordError, CorruptedCarrierError,
)

logger = get_logger(__name__)


class StegoWorker(QThread):
    """Сигналы:
        finished: успешная операция ИЛИ ожидаемая ошибка CompatibilityError, неверный пароль.
        erro: неожиданное исключение уровня инфраструктуры.
    """

    finished = pyqtSignal(StegoResponse)
    error = pyqtSignal(str)

    def __init__(self, request: StegoTaskRequest, mode: str) -> None:
        """Инициализация worker'а в главном потоке.

        Args:
            request: Замороженный DTO с параметрами операции.
            mode:    "encode" или "decode".

        Note:
            Тяжёлые объекты (StegoService) создаются в run(), а не здесь,
            чтобы не нагружать момент создания worker'а в UI-потоке.
        """
        super().__init__()
        self._request = request
        self._mode = mode

    def run(self) -> None:
        """Точка входа фонового потока.

        Вызывается автоматически после QThread.start(). Выполняется в
        отдельном потоке OS — никаких прямых обращений к UI отсюда!

        Любой результат (успех, ожидаемая ошибка, авария) уезжает в
        главный поток через сигналы.
        """
        # Сервис создаётся ВНУТРИ run(), уже в фоновом потоке.
        # Это снимает нагрузку с момента старта worker'а и гарантирует,
        # что внутренние ресурсы сервиса (если такие появятся) принадлежат
        # этому потоку.
        service = StegoService()

        try:
            if self._mode == "encode":
                logger.info(
                    f"Encode start: carrier={self._request.carrier_path.name}, "
                    f"payload={self._request.payload_path.name}"
                )
                response = service.hide_data(self._request)
                logger.info(
                    f"Encode OK: out={self._request.output_path.name}, "
                    f"metrics={response.metrics}"
                )
            elif self._mode == "decode":
                logger.info(f"Decode start: stego={self._request.carrier_path.name}")
                response = service.extract_data(self._request)
                logger.info(
                    f"Decode OK: out={self._request.output_path.name}, "
                    f"metrics={response.metrics}"
                )
            else:
                raise ValueError(f"Unknown mode: {self._mode}")

            self.finished.emit(response)

        except CompatibilityError as e:
            # Ожидаемая бизнес-ошибка: некорректный формат, нарушение анти-конверсии, недостаточная ёмкость.
            logger.warning(f"{self._mode} compatibility error: {e}")
            self.finished.emit(StegoResponse(success=False, error=str(e)))

        except InvalidFrameError as e:
            # Ожидаемая ошибка извлечения: неверный пароль, файл без скрытых данных, повреждённый носитель.
            logger.warning(f"{self._mode} invalid frame: {e}")
            self.finished.emit(StegoResponse(success=False, error=str(e)))
        
        except InvalidPasswordError as e:
            # Ожидаемая ошибка: AES-GCM MAC mismatch. Неверный пароль или битые данные.
            logger.warning(f"{self._mode} invalid password: {e}")
            self.finished.emit(StegoResponse(success=False, error=str(e)))

        except CorruptedCarrierError as e:
            # Ожидаемая ошибка: повреждённый файл.
            logger.warning(f"{self._mode} corrupted carrier: {e}")
            self.finished.emit(StegoResponse(success=False, error=str(e)))

        except Exception as e:
            # Повреждённый файл, ошибка крипты, баг в ядре. critical-error через отдельный сигнал.
            logger.exception(f"{self._mode} crashed")
            self.error.emit(f"Внутренняя ошибка: {e}")