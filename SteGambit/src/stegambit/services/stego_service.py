"""StegoService — главный Фасад пайплайна сокрытия."""
import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import struct
import time

from stegambit.core.common.format_id import FormatIdentifier, get_default_extension
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
            # Для JPEG пул — уже отфильтрованные DCT-позиции. Перемешиваем детерминированно по паролю.
            coords = self._shuffle_pool_by_password(pool, request.password)[:required_bits]

        # Снапшот для sanity-check (только DCT — для LSB sanity на PSNR=inf).
        pre_embed_snapshot = None
        if processor_kind == "DCT":
            pre_embed_snapshot = original.coef_arrays[0].copy()

        # 7. Внедрение.
        stego = processor.embed(original, encrypted, coords)

        if processor_kind == "DCT":
            print(f"DEBUG hide: pool size = {pool.size}")
            print(f"DEBUG hide: coords[:10] = {coords[:10]}")
            print(f"DEBUG hide: encrypted[:8].hex() = {encrypted[:8].hex()}")

        # 8. Сохраняем.
        fmt_handler.save(stego, request.output_path)

        # 9. Метрики + sanity-check.
        metrics = self._compute_metrics(
            processor_kind, original, stego, t0,
            pre_embed_snapshot=pre_embed_snapshot,
        )

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
        if processor_kind == "LSB":
            spreader = SmartSpreader()
            coords_for_header = spreader.generate_coords(
                container=stego,
                payload_bits_len=header_bits,
                password_seed=request.password,
            )
        else:
            coords_for_header = self._shuffle_pool_by_password(pool, request.password)[:header_bits]

        header_bytes = processor.extract(stego, coords_for_header, header_size)

        # 6. Парсим LENGTH из заголовка (поле смещено на MAGIC+FLAGS+SALT+NONCE).
        #    Чтобы не лезть руками, передадим заголовок в CryptoEngine —
        #    он сам ругнётся на MAGIC, если что-то не так.
        

        if header_bytes[:FrameLayout.MAGIC_LEN] != FrameLayout.MAGIC:
            raise RuntimeError(
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
            coords_full = self._shuffle_pool_by_password(pool, request.password)[:full_frame_bits]

        full_frame = processor.extract(stego, coords_full, full_frame_size)

        # 8. Запись извлечённого payload в файл.
        try:
            payload_bytes = self._crypto.decrypt(full_frame, request.password)
        except Exception as e:
            raise RuntimeError(
                f"Расшифровка провалилась: неверный пароль или повреждённые данные ({e})."
            ) from e

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

    def _compute_metrics(self, processor_kind: str, original: Any, stego: Any,
                         t0: float, pre_embed_snapshot: np.ndarray | None = None) -> dict:
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
            assert isinstance(stego, JpegContainer)
            if pre_embed_snapshot is None:
                raise RuntimeError(
                    "DCT sanity-check требует наличия pre_embed_snapshot. Баг в hide_data — снапшот не передан."
                )
            if np.array_equal(pre_embed_snapshot, stego.coef_arrays[0]):
                raise RuntimeError(
                    "Проверка внедрения провалена: Y-канал JPEG не изменился. Информация не была внедрена."
                )
            return {"time": elapsed}

        return {"time": elapsed}
    

    @staticmethod
    def _shuffle_pool_by_password(pool: np.ndarray, password: str) -> np.ndarray:
        """Детерминированно перемешивает пул координат seed'ом из пароля.

        Используется для DCT-пайплайна, где SmartSpreader неприменим
        (edge-detection — это пространственный анализ, бессмысленный
        для DCT-коэффициентов в частотном домене).

        TODO [#XX рефакторинг spreading]:
            Этот метод дублирует логику SmartSpreader._seed_rng + rng.shuffle.
            План:
                1. Вынести seed-perestановку в отдельный класс
                   PasswordSeededShuffler в core/stego/.
                2. SmartSpreader = EdgeDetector + Shuffler (композиция).
                3. Для DCT — DctSpreader = Shuffler (без edge-detection),
                   входной пул берётся из DctProcessor.get_embeddable_positions().
                4. StegoService перестаёт знать про шифровку seed'а — это
                   ответственность core/stego, а не сервисного слоя.

            Сейчас оставлено как есть ради скорости MVP. При рефакторинге
            этот метод УДАЛИТЬ полностью, перенеся логику в Shuffler.
        """
        digest = hashlib.sha256(password.encode("utf-8")).digest()
        seed_int = int.from_bytes(digest[:8], "big", signed=False)
        rng = np.random.default_rng(seed_int)
        pool_copy = pool.copy()
        rng.shuffle(pool_copy)
        return pool_copy
    
    # TODO: На проде убрать ассерты!11! 