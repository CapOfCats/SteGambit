"""StegoWorker — слой совместимости между GUI и StegoService.

ВАЖНО в рамках (MVP):
    Сейчас Worker работает СИНХРОННО — start() блокирует UI на время
    операции. Это сознательное упрощение для MVP/защиты.
    Контракт сигналов (finished/error) и метод start() уже соответствуют
    будущему асинхронному API на QThread. При апгрейде до настоящих
    потоков GUI-код менять не потребуется — только тело Worker'а.

Зачем такой контракт уже сейчас:
    - UI пишется один раз и не ломается при будущей миграции на QThread.
    - Логика передачи DTO (Request -> Service -> Response) отлаживается
      на синхронной версии, без рисков из-за гонок потоков.
"""
from PyQt6.QtCore import QObject, pyqtSignal

from stegambit.infrastructure.stegano_logger import get_logger
from stegambit.models.dto import StegoTaskRequest, StegoResponse
from stegambit.services.stego_service import StegoService, CompatibilityError


logger = get_logger(__name__)


class StegoWorker(QObject):
    """Воркер для операций сокрытия/извлечения.

    Сигналы:
        finished(StegoResponse): Операция завершилась (успех ИЛИ еррор в виде response.success=False).
        error(str): Неожиданная ошибка уровня инфраструктуры.

    UI подписывается на оба сигнала, на основе finished показывает метрики или текст ошибки.
    """

    finished = pyqtSignal(StegoResponse)
    error = pyqtSignal(str)

    def __init__(self, request: StegoTaskRequest, mode: str) -> None:
        """
        Args:
            request: DTO с параметрами операции.
            mode:    "encode" или "decode".
        """
        super().__init__()
        self._request = request
        self._mode = mode
        self._service = StegoService()

    def start(self) -> None:
        """Запуск операции.

        В MVP-версии работает синхронно (блокирует поток вызова).
        В ПРОДе будет перенаправлено в QThread.run().
        """
        try:
            if self._mode == "encode":
                logger.info(
                    f"Encode start: carrier={self._request.carrier_path.name}, "
                    f"payload={self._request.payload_path.name}"
                )
                response = self._service.hide_data(self._request)
                logger.info(
                    f"Encode OK: out={self._request.output_path.name}, "
                    f"metrics={response.metrics}"
                )
            elif self._mode == "decode":
                logger.info(f"Decode start: stego={self._request.carrier_path.name}")
                response = self._service.extract_data(self._request)
                logger.info(
                    f"Decode OK: out={self._request.output_path.name}, "
                    f"metrics={response.metrics}"
                )
            else:
                raise ValueError(f"Unknown mode: {self._mode}")

            self.finished.emit(response)

        except CompatibilityError as e:
            logger.warning(f"{self._mode} compatibility error: {e}")
            self.finished.emit(StegoResponse(success=False, error=str(e)))

        except Exception as e:
            logger.exception(f"{self._mode} crashed")
            self.error.emit(f"Внутренняя ошибка: {e}")