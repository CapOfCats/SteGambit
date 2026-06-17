"""StegoService — главный Фасад пайплайна сокрытия."""
from pathlib import Path
from typing import Any, Optional

import numpy as np
import struct
import time

from stegambit.core.exceptions import InvalidFrameError
from stegambit.core.common.format_id import FormatIdentifier, get_default_extension
from stegambit.core.formats.jpeg import JpegFormat, JpegContainer
from stegambit.core.formats.png import PngFormat
from stegambit.core.formats.wav import WavFormat
from stegambit.core.stego.strategies import DctProcessor, LsbProcessor
from stegambit.core.crypto.engine import CryptoEngine, FrameLayout
from stegambit.core.stego.spreader import SmartSpreader
from stegambit.core.exceptions import CompatibilityError
from stegambit.models.dto import (
    StegoTaskRequest,
    StegoResponse,
    CapacityReport,
)
from stegambit.core.common.seeding import shuffle_pool_by_password
from stegambit.services.analytics.metrics import (
    calculate_psnr,
    calculate_ssim,
    calculate_size_deviation,
    evaluate_quality,
)

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
        encrypted = self._crypto.encrypt(payload_bytes, request.password)

        # 4. Выбор процессора и сборка пула координат.
        #    Для LSB пул — все индексы контейнера. Для DCT — только валидные
        #    AC-коэффициенты (фильтрация от DctProcessor). Ветвление LSB/DCT
        #    инкапсулировано в _build_pool, чтобы не засорять основной пайплайн.
        processor_kind = _FORMAT_TO_PROCESSOR[carrier_fmt]
        pool, processor = self._build_pool(processor_kind, original)

        # 5. Ёмкостная валидация (критично для JPEG, не критично для LSB).
        required_bits = len(encrypted) * 8
        if pool.size < required_bits:
            raise CompatibilityError(
                f"Недостаточно ёмкости носителя: доступно {pool.size} бит, "
                f"требуется {required_bits}. Возьмите более крупный носитель или уменьшите payload."
            )

        # 6. Генерация координат. Spreader выбирает конкретные позиции из пула по сиду.
        if processor_kind == "LSB":
            spreader = SmartSpreader()
            coords = spreader.generate_coords(
                container=original,
                payload_bits_len=required_bits,
                password_seed=request.password,
            )
        else:
            
            coords = shuffle_pool_by_password(pool, request.password)[:required_bits]

        # Снапшот для sanity-check (только DCT — для LSB sanity на PSNR=inf).
        pre_embed_snapshot = None
        if processor_kind == "DCT":
            pre_embed_snapshot = original.coef_arrays[0].copy()

        # 7. Внедрение.
        stego = processor.embed(original, encrypted, coords)

        # 8. Сохраняем.
        fmt_handler.save(stego, request.output_path)

        # 9. Метрики + sanity-check.
        metrics = self._compute_metrics(
            processor_kind, original, stego, t0,
            pre_embed_snapshot=pre_embed_snapshot,
            original_path=request.carrier_path,
            output_path=request.output_path,
        )

        return StegoResponse(
            success=True,
            output_path=request.output_path,
            metrics=metrics,
        )
    
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
        if processor_kind == "LSB":
            spreader = SmartSpreader()
            coords_for_header = spreader.generate_coords(
                container=stego,
                payload_bits_len=header_bits,
                password_seed=request.password,
            )
        else:
            coords_for_header = shuffle_pool_by_password(pool, request.password)[:header_bits]

        header_bytes = processor.extract(stego, coords_for_header, header_size)

        # 6. Парсим LENGTH из заголовка (поле смещено на MAGIC+FLAGS+SALT+NONCE).
        #    Чтобы не лезть руками, передадим заголовок в CryptoEngine —
        #    он сам ругнётся на MAGIC, если что-то не так.
        

        if header_bytes[:FrameLayout.MAGIC_LEN] != FrameLayout.MAGIC:
            raise InvalidFrameError(
                "MAGIC bytes не найдены. Возможно, неверный пароль или файл не содержит данных."
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

        if processor_kind == "LSB":
            spreader = SmartSpreader()
            coords_full = spreader.generate_coords(
                container=stego,
                payload_bits_len=full_frame_bits,
                password_seed=request.password,
            )
        else:
            coords_full = shuffle_pool_by_password(pool, request.password)[:full_frame_bits]

        full_frame = processor.extract(stego, coords_full, full_frame_size)

        # 8. Запись извлечённого payload в файл.
        payload_bytes = self._crypto.decrypt(full_frame, request.password)

        # Пытаемся определить оригинальный формат payload по magic bytes, чтобы вернуть файл с правильным расширением.
        # Если формат не опознан (текст, неподдерживаемый бинарь) — дефолтуется .bin.
        try:
            payload_fmt = self._identifier.identify_bytes(payload_bytes)
        except ValueError:
            payload_fmt = "UNKNOWN"

        correct_ext = get_default_extension(payload_fmt)
        output_path = Path(request.output_path).with_suffix(correct_ext)

        output_path.write_bytes(payload_bytes)

        elapsed = time.perf_counter() - t0
        return StegoResponse(
            success=True,
            output_path=output_path,
            metrics={
                "time": elapsed,
                "extracted_bytes": len(payload_bytes),
                "detected_format": payload_fmt,
            },
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
    

    def analyze_capacity(self, request: StegoTaskRequest) -> CapacityReport:
        """Предварительная оценка ёмкости БЕЗ фактического сокрытия.

        Используется UI до запуска операции, чтобы показать пользователю
        реальные цифры и при необходимости заблокировать кнопку Hide.

        Шаги:
            1. Определить формат контейнера (Magic Bytes).
            2. Загрузить контейнер.
            3. Построить пул координат тем же способом, что hide_data
               (для LSB — все пиксели, для DCT — отфильтрованные AC).
            4. Посчитать и сравнить с размером payload.

        Returns:
            CapacityReport с флагом fits.

        Raises:
            CompatibilityError: если формат не поддержан.
            FileNotFoundError:  если файлы не существуют.
        """
        carrier_fmt = self._identifier.identify(request.carrier_path)
        if carrier_fmt not in _FORMAT_REGISTRY:
            raise CompatibilityError(
                f"Формат '{carrier_fmt}' не поддержан. "
                f"Поддержанные: {list(_FORMAT_REGISTRY)}"
            )

        fmt_handler = _FORMAT_REGISTRY[carrier_fmt]()
        container = fmt_handler.load(request.carrier_path)

        processor_kind = _FORMAT_TO_PROCESSOR[carrier_fmt]
        if processor_kind == "LSB":
            spreader = SmartSpreader()
            capacity_bits = spreader.get_max_capacity_bits(container)
        else:  # DCT
            pool = self._dct.get_embeddable_positions(container)
            capacity_bits = int(pool.size)

        payload_size = Path(request.payload_path).stat().st_size
        header_size = CryptoEngine.header_size()
        # Crypto-frame = header (57 байт) + ciphertext (= payload + GCM-tag).
        # GCM-tag уже включён в header_size согласно нашему FrameLayout,
        # поэтому считаем как header + payload в битах.
        required_bits = (header_size + payload_size) * 8

        utilization = (
            (required_bits / capacity_bits * 100.0) if capacity_bits > 0 else 0.0
        )

        return CapacityReport(
            fits=required_bits <= capacity_bits,
            format=carrier_fmt,
            algorithm=processor_kind,
            capacity_bits=capacity_bits,
            required_bits=required_bits,
            payload_size_bytes=payload_size,
            header_size_bytes=header_size,
            utilization_percent=utilization,
        )
    
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


    def _compute_metrics(
        self,
        processor_kind: str,
        original: Any,
        stego: Any,
        t0: float,
        pre_embed_snapshot: np.ndarray | None = None,
        original_path: Path | None = None,
        output_path: Path | None = None,
    ) -> dict:
        """Считает метрики и выполняет sanity-check.

        LSB: PSNR + SSIM между двумя ndarray. PSNR=inf -> ни один бит
             не записался (sanity fail).
        DCT: PSNR/SSIM на коэффициентах визуально не осмыслен, считаем
             только время и проверяем, что Y-канал изменился.
        Общее: size_deviation вычисляется при наличии путей,
               quality_status — на основе доступных метрик.

        Returns:
            dict с ключами: psnr, ssim, time, size_deviation, quality_status - временно строками.
            Часть ключей может отсутствовать в зависимости от пайплайна.
        """
        elapsed = time.perf_counter() - t0
        metrics: dict[str, Any] = {"time": elapsed}

        if processor_kind == "LSB":
            original_arr = np.asarray(original)
            stego_arr = np.asarray(stego)

            psnr = calculate_psnr(original_arr, stego_arr)
            if psnr == float("inf"):
                raise RuntimeError(
                    "Проверка внедрения провалена: стего-контейнер идентичен исходному. Информация не была внедрена."
                )
            metrics["psnr"] = psnr
            metrics["ssim"] = calculate_ssim(original_arr, stego_arr)

        #  DCT sanity-check - без PSNR/SSIM 
        elif processor_kind == "DCT":
            if pre_embed_snapshot is None:
                raise RuntimeError(
                    "DCT sanity-check требует pre_embed_snapshot. "
                    "Баг в hide_data — снапшот не передан."
                )
            if np.array_equal(pre_embed_snapshot, stego.coef_arrays[0]):
                raise RuntimeError(
                    "Проверка внедрения провалена: Y-канал JPEG не изменился. "
                    "Информация не была внедрена."
                )

        #  Отклонение размера файла
        # Считается ПОСЛЕ save(), поэтому пути ВСЕГДА должны быть переданы.
        size_dev: Optional[float] = None
        if original_path is not None and output_path is not None:
            try:
                size_dev = calculate_size_deviation(original_path, output_path)
                metrics["size_deviation"] = size_dev
            except (FileNotFoundError, OSError):
                # Файл может быть не записан по ошибке ОС
                pass

        # Триггер качества
        metrics["quality_status"] = evaluate_quality(
            psnr=metrics.get("psnr"),
            size_deviation=size_dev,
        )

        return metrics
