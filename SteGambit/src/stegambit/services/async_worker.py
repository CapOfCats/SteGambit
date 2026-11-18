"""StegoWorker — background thread for heavy StegoService operations.

Architectural basis: ADR 008 "Threading model and GUI isolation".

Contract with the GUI:
    Signals:
        - finished(StegoResponse) — the operation finished.
        - error(str) — infrastructure failure (an exception not caught
          by business logic). Used for critical failures such as OOM, a broken dependency install, and similar.
    Start: worker.start() — the standard QThread method, queues the thread
      on the Qt event loop. The body runs in run().

    Base class QObject -> QThread.
    The GUI is not blocked during the operation — the main Qt event loop keeps processing events.
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
    """Signals:
        finished: a successful operation OR an expected error (CompatibilityError, wrong password).
        error: an unexpected infrastructure-level exception.
    """

    finished = pyqtSignal(StegoResponse)
    error = pyqtSignal(str)

    def __init__(self, request: StegoTaskRequest, mode: str) -> None:
        """Initializes the worker on the main thread.

        Args:
            request: Frozen DTO with operation parameters.
            mode:    "encode" or "decode".

        Note:
            Heavy objects (StegoService) are created in run(), not here,
            so worker creation on the UI thread stays cheap.
        """
        super().__init__()
        self._request = request
        self._mode = mode

    def run(self) -> None:
        """Entry point of the background thread.

        Called automatically after QThread.start(). Runs on a
        separate OS thread — no direct UI access from here.

        Any result (success, expected error, failure) is delivered to
        the main thread via signals.
        """
        # The service is created INSIDE run(), already on the background thread.
        # This keeps worker startup light and guarantees that
        # any internal service resources (if they appear later) belong
        # to this thread.
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
            # Expected business error: bad format, anti-conversion violation, insufficient capacity.
            logger.warning(f"{self._mode} compatibility error: {e}")
            self.finished.emit(StegoResponse(success=False, error=str(e)))

        except InvalidFrameError as e:
            # Expected extraction error: wrong password, file with no hidden data, corrupted carrier.
            logger.warning(f"{self._mode} invalid frame: {e}")
            self.finished.emit(StegoResponse(success=False, error=str(e)))
        
        except InvalidPasswordError as e:
            # Expected error: AES-GCM MAC mismatch. Wrong password or corrupt data.
            logger.warning(f"{self._mode} invalid password: {e}")
            self.finished.emit(StegoResponse(success=False, error=str(e)))

        except CorruptedCarrierError as e:
            # Expected error: corrupted file.
            logger.warning(f"{self._mode} corrupted carrier: {e}")
            self.finished.emit(StegoResponse(success=False, error=str(e)))

        except Exception as e:
            # Corrupted file, crypto error, core bug. Critical error via a separate signal.
            logger.exception(f"{self._mode} crashed")
            self.error.emit(f"Внутренняя ошибка: {e}")