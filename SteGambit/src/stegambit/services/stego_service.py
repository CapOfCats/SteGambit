"""StegoService — главный Фасад пайплайна сокрытия."""

from pathlib import Path
from typing import Any

import numpy as np
import struct
import time

from stegambit.core.common.format_id import FormatIdentifier
from stegambit.core.formats.jpeg import JpegFormat, JpegContainer
from stegambit.core.formats.png import PngFormat
from stegambit.core.formats.wav import WavFormat
from stegambit.core.stego.strategies import DctProcessor, LsbProcessor
from stegambit.core.crypto.engine import CryptoEngine, FrameLayout
from stegambit.core.stego.spreader import SmartSpreader
from stegambit.models.dto import StegoTaskRequest, StegoResponse
from stegambit.services.analytics.metrics import calculate_psnr

_FORMAT_REGISTRY = {
    "PNG": PngFormat,
    "WAV": WavFormat,
    "JPEG": JpegFormat,
}

_FORMAT_TO_PROCESSOR = {
    "PNG": "LSB",
    "WAV": "LSB",
    "JPEG": "DCT",
}

_EXT_TO_FORMAT = {".png": "PNG", ".wav": "WAV", ".jpeg": "JPEG", ".jpg": "JPEG"}


class CompatibilityError(Exception):
    """Нарушение политики Анти-Конверсии или нехватка ёмкости."""


class StegoService:
    """Синхронный Фасад: валидация → crypto → spread → embed → save.

    Для JPEG: использует JSteg-пайплайн через DctProcessor + JpegContainer.
    Для PNG/WAV: LSB-пайплайн через LsbProcessor + ndarray.
    """

    def __init__(self) -> None:
        self._identifier = FormatIdentifier()
        self._crypto = CryptoEngine()
        self._processor = LsbProcessor()
        self._dct = DctProcessor()

    def hide_data(self, request: StegoTaskRequest) -> StegoResponse:
        """Выполняет полный пайплайн сокрытия по StegoTaskRequest."""
        t0 = time.perf_counter()

        # 1. Определение формата и проверка политики анти-конверсии.
        carrier_fmt = self._identifier.identify(request.carrier_path)
        out_ext = Path(request.output_path).suffix.lower()
        if _EXT_TO_FORMAT.get(out_ext) != carrier_fmt:
            raise CompatibilityError(
                f"Нарушение анти-конверсии: носитель имеет формат {carrier_fmt}, "
                f"но выходящий формат: '{out_ext}'"
            )
        if carrier_fmt not in _FORMAT_REGISTRY:
            raise CompatibilityError(
                f"Формат '{carrier_fmt}' не поддержан. "
                f"Поддержанные форматы: {list(_FORMAT_REGISTRY)}"
            )

        # 2. Загрузка контейнера через фабрику.
        fmt_handler = _FORMAT_REGISTRY[carrier_fmt]()
        original = fmt_handler.load(request.carrier_path)

        # 3. Чтение и шифровка "груза".
        payload_bytes = Path(request.payload_path).read_bytes()
        encrypted = self._crypto.encrypt(payload_bytes, request.passphrase)

        # 4. Выбор процессора и сборка пула координат.
        #    Для LSB пул — все индексы контейнера. Для DCT — только валидные
        #    AC-коэффициенты (фильтрация от DctProcessor). Ветвление LSB/DCT
        #    инкапсулировано в _build_pool, чтобы не засорять основной пайплайн.
        processor_kind = _FORMAT_TO_PROCESSOR[carrier_fmt]
        pool, processor = self._build_pool(processor_kind, original)

        # 5. Ёмкостная валидация (критично для JPEG, тривиально для LSB).
        required_bits = len(encrypted) * 8
        if pool.size < required_bits:
            raise CompatibilityError(
                f"Недостаточно ёмкости носителя: доступно {pool.size} бит, "
                f"требуется {required_bits}. Возьмите более крупный носитель "
                f"или уменьшите payload."
            )

        # 6. Генерация координат. Spreader выбирает конкретные позиции из пула по сиду.
        spreader = SmartSpreader(passphrase=request.passphrase)
        coords = spreader.generate(container=original, payload_size=len(encrypted))

        # 7. Внедрение.
        stego = processor.embed(original, encrypted, coords)

        # 8. Метрики + sanity-check.
        #    PSNR осмыслен только для ndarray-контейнеров (LSB).
        #    Для DCT делаем проверку, что Y-канал реально изменился.
        metrics = self._compute_metrics(processor_kind, original, stego, t0)

        # 9. Сохраняем.
        fmt_handler.save(stego, request.output_path)

        return StegoResponse(success=True, metrics=metrics)
    
    def extract_data(self, request: StegoTaskRequest) -> StegoResponse:
        """Извлекает payload из стего-контейнера.

        Зеркало hide_data:
            1. Загружаем стего-контейнер.
            2. Строим тот же пул координат (формат тот же -> пул тот же).
            3. Spreader с тем же паролем -> те же координаты.
            4. Извлекаем заголовок (57 байт), читаем LENGTH из него.
            5. Извлекаем заголовок + ciphertext полным размером.
            6. CryptoEngine.decrypt -> исходные байты.
            7. Записываем в output_path.

        Args:
            request: StegoTaskRequest. carrier_path тут — это стего-файл,
                     output_path — куда сохранить извлечённый payload.

        Returns:
            StegoResponse(success=True, output_path=...) при успехе.
        """
        t0 = time.perf_counter()

        # 1. Определение формата стего-контейнера.
        carrier_fmt = self._identifier.identify(request.carrier_path)
        if carrier_fmt not in _FORMAT_REGISTRY:
            raise CompatibilityError(
                f"Формат '{carrier_fmt}' не поддержан. "
                f"Поддержанные: {list(_FORMAT_REGISTRY)}"
            )

        # 2. Загрузка стего.
        fmt_handler = _FORMAT_REGISTRY[carrier_fmt]()
        stego = fmt_handler.load(request.carrier_path)

        # 3. Тот же пул, что был при embed.
        processor_kind = _FORMAT_TO_PROCESSOR[carrier_fmt]
        pool, processor = self._build_pool(processor_kind, stego)

        # 4. Извлечение заголовка (57 байт) для определения LENGTH.
        header_size = CryptoEngine.header_size()  # 57 байт, понадобится в отдельной переменной
        header_bits = header_size * 8

        if pool.size < header_bits:
            raise CompatibilityError(
                "Стего-контейнер слишком мал даже для заголовка. "
                "Возможно, файл не содержит payload."
            )

        # Spreader с тем же паролем даст те же координаты, что при embed.
        spreader = SmartSpreader(passphrase=request.passphrase)

        # 5. Извлекаем достаточно бит для парсинга длины.
        #    Сначала тянем минимально нужное (заголовок), читаем LENGTH,
        #    потом тянем полный фрейм.
        coords_for_header = spreader.generate(
            container=stego, payload_size=header_size
        )
        header_bytes = processor.extract(stego, coords_for_header, header_size)

        # 6. Парсим LENGTH из заголовка (поле смещено на MAGIC+FLAGS+SALT+NONCE).
        #    Чтобы не лезть руками, передадим заголовок в CryptoEngine —
        #    он сам ругнётся на MAGIC, если что-то не так.
        

        if header_bytes[:FrameLayout.MAGIC_LEN] != FrameLayout.MAGIC:
            raise RuntimeError(
                "MAGIC bytes не найдены. Возможно, неверный пароль "
                "или файл не содержит данных."
            )

        length_offset = (
            FrameLayout.MAGIC_LEN
            + FrameLayout.FLAGS_LEN
            + FrameLayout.SALT_LEN
            + FrameLayout.NONCE_LEN
        )
        ciphertext_len = struct.unpack(
            ">Q", header_bytes[length_offset:length_offset + FrameLayout.LENGTH_LEN]
        )[0]

        # 7. Извлекаем полный фрейм (заголовок + ciphertext).
        full_frame_size = header_size + ciphertext_len
        full_frame_bits = full_frame_size * 8

        if pool.size < full_frame_bits:
            raise CompatibilityError(
                f"Стего-контейнер не содержит полный фрейм: "
                f"нужно {full_frame_bits} бит, доступно {pool.size}."
            )

        coords_full = spreader.generate(
            container=stego, payload_size=full_frame_size
        )
        full_frame = processor.extract(stego, coords_full, full_frame_size)

        # 8. Расшифровка.
        try:
            payload_bytes = self._crypto.decrypt(full_frame, request.passphrase)
        except Exception as e:
            raise RuntimeError(f"Расшифровка провалилась: неверный пароль или повреждённые данные. ({e})") from e

        # 9. Запись извлечённого payload в файл.
        Path(request.output_path).write_bytes(payload_bytes)

        elapsed = time.perf_counter() - t0
        return StegoResponse(
            success=True,
            output_path=request.output_path,
            metrics={"time": elapsed, "extracted_bytes": len(payload_bytes)},
        )
    
    def identify_format(self, path: Path) -> str:
        """Определяет формат файла по Magic Bytes.

        Публичная обёртка над FormatIdentifier для GUI.
        GUI не должен импортировать core напрямую.

        Returns:
            "PNG" | "WAV" | "JPEG"

        Raises:
            ValueError: если формат не поддержан.
        """
        return self._identifier.identify(path)
    
    def get_algorithm_for_format(self, fmt: str) -> str:
        """Возвращает имя алгоритма для формата ('LSB' / 'DCT')."""
        return _FORMAT_TO_PROCESSOR.get(fmt, "?")

    def _build_pool(self, processor_kind: str, container: Any) -> tuple[np.ndarray, Any]:
        """Удивитесь, но БИЛДИТ ПУЛ. А если серьезно -
        Возвращает (пул координат, процессор) для выбранного пайплайна.

        LSB: пул — все индексы ndarray-контейнера (любой пиксель/семпл валиден).
        DCT: пул строится через DctProcessor.get_embeddable_positions
             (среднечастотные AC, без {-1, 0, 1}).
        """
        if processor_kind == "LSB":
            pool = np.arange(container.size, dtype=np.int64)
            return pool, self._processor
        if processor_kind == "DCT":
            pool = self._dct.get_embeddable_positions(container)
            return pool, self._dct
        raise RuntimeError(f"Неизвестный тип процессора: {processor_kind}")

    def _compute_metrics(self, processor_kind: str, original: Any, stego: Any, t0: float) -> dict:
        """Считает метрики и выполняет sanity-check.

        LSB: PSNR между двумя ndarray. inf → ни один бит не записался - плохо!
        DCT: PSNR на коэффициентах не имеет визуального смысла, считаем
             только время и проверяем, что Y-канал реально изменился.
        """
        elapsed = time.perf_counter() - t0

        if processor_kind == "LSB":
            psnr = calculate_psnr(original, stego)
            if psnr == float("inf"):
                raise RuntimeError(
                    "Проверка внедрения провалена: стего-контейнер идентичен "
                    "исходному. Информация не была внедрена."
                )
            return {"psnr": psnr, "time": elapsed}

        if processor_kind == "DCT":
            assert isinstance(original, JpegContainer)
            assert isinstance(stego, JpegContainer)
            if np.array_equal(original.coef_arrays[0], stego.coef_arrays[0]):
                raise RuntimeError(
                    "Проверка внедрения провалена: Y-канал JPEG не изменился. "
                    "Информация не была внедрена."
                )
            return {"time": elapsed}

        return {"time": elapsed}
    
    # TODO: На проде убрать ассерты!11! 