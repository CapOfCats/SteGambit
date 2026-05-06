"""StegoService — главный Фасад пайплайна сокрытия."""
import time
from pathlib import Path

from stegambit.core.common.format_id import FormatIdentifier
from stegambit.core.formats.jpeg import JpegFormat
from stegambit.core.formats.png import PngFormat
from stegambit.core.formats.wav import WavFormat
from stegambit.core.stego.strategies import LsbProcessor
from stegambit.core.crypto.engine import CryptoEngine
from stegambit.core.stego.spreader import SmartSpreader
from stegambit.models.dto import StegoTaskRequest, StegoResponse
from stegambit.services.analytics.metrics import calculate_psnr

_FORMAT_REGISTRY = {
    "PNG": PngFormat,
    "WAV": WavFormat,
    "JPEG": JpegFormat,
}

_EXT_TO_FORMAT = {".png": "PNG", ".wav": "WAV", ".jpeg": "JPEG", ".jpg": "JPEG"}


class CompatibilityError(Exception):
    """Нарушение политики Анти-Конверсии!"""


class StegoService:
    """Синхронный Фасад: валидация → crypto → spread → embed → save."""

    def __init__(self) -> None:
        self._identifier = FormatIdentifier()
        self._crypto = CryptoEngine()
        self._processor = LsbProcessor()

    def hide_data(self, request: StegoTaskRequest) -> StegoResponse:
        """Выполняет полный пайплайн сокрытия по StegoTaskRequest."""
        t0 = time.perf_counter()

        # 1. Определение формата и проверка политики анти-конверсии.
        carrier_fmt = self._identifier.identify(request.carrier_path)
        out_ext = Path(request.output_path).suffix.lower()
        if _EXT_TO_FORMAT.get(out_ext) != carrier_fmt:
            raise CompatibilityError(
                f"Нарушение анти-конверсии: носитель имеет формат {carrier_fmt}, но выходящий формат: '{out_ext}'"
            )
        if carrier_fmt not in _FORMAT_REGISTRY:
            # TODO(#next-ticket): JPEG будет роутиться в DctProcessor.
            # Сейчас StegoService обслуживает только LSB-ветку пайплайна.
            raise CompatibilityError(
                f"Формат '{carrier_fmt}' пока что не связан с процессором (не поддержан). "
                f"Поддержаные на данный момент форматы: {list(_FORMAT_REGISTRY)}"
            )

        # 2. Загрузка контейнера через фабрику
        fmt_handler = _FORMAT_REGISTRY[carrier_fmt]()
        original = fmt_handler.load(request.carrier_path)

        # 3. Чтение и шифровка "груза"
        payload_bytes = Path(request.payload_path).read_bytes()
        encrypted = self._crypto.encrypt(payload_bytes, request.passphrase)

        # 4. Генерация координат!
        spreader = SmartSpreader(passphrase=request.passphrase)
        coords = spreader.generate(container=original, payload_size=len(encrypted))

        # 5. Внедрение
        stego = self._processor.embed(original, encrypted, coords)

        # 6. Метрики!
        psnr = calculate_psnr(original, stego)
        if psnr == float("inf"):
            raise RuntimeError(
                "Проверка внедрения провалена: Стего-контейнер идентичен изначальному. Информация не была внедрена"
            )

        # 7. Сохраняем
        fmt_handler.save(stego, request.output_path)

        return StegoResponse(
            success=True,
            metrics={"psnr": psnr, "time": time.perf_counter() - t0},
        )