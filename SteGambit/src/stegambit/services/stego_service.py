"""StegoService — main facade of the concealment pipeline."""
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
from stegambit.core.stego.dct_spreader import DctSpreader
from stegambit.core.exceptions import CompatibilityError
from stegambit.models.dto import (
    StegoTaskRequest,
    StegoResponse,
    CapacityReport,
)
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
    """Synchronous facade: validation → crypto → spread → embed → save.

    For JPEG: uses the JSteg pipeline via DctProcessor + JpegContainer.
    For PNG/WAV: LSB pipeline via LsbProcessor + ndarray.
    """

    def __init__(self) -> None:
        self._identifier = FormatIdentifier()
        self._crypto = CryptoEngine()
        self._processor = LsbProcessor()
        self._dct = DctProcessor()
        self._lsb_spreader = SmartSpreader()
        self._dct_spreader = DctSpreader()

    def hide_data(self, request: StegoTaskRequest) -> StegoResponse:
        """Runs the full concealment pipeline for a StegoTaskRequest."""
        t0 = time.perf_counter()

        # 1. Detect the format and enforce the anti-conversion policy.
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

        # 2. Load the container via the factory.
        fmt_handler = _FORMAT_REGISTRY[carrier_fmt]()
        original = fmt_handler.load(request.carrier_path)

        # 3. Read and encrypt the payload.
        payload_bytes = Path(request.payload_path).read_bytes()
        encrypted = self._crypto.encrypt(payload_bytes, request.password)

        # 4. Select the processor and build the coordinate pool.
        #    For LSB the pool is every container index. For DCT only valid
        #    AC coefficients (filtered by DctProcessor). LSB/DCT branching
        #    is encapsulated in _build_pool so the main pipeline stays clean.
        processor_kind = _FORMAT_TO_PROCESSOR[carrier_fmt]
        pool, processor = self._build_pool(processor_kind, original)

        # 5. Capacity validation (critical for JPEG, not critical for LSB).
        required_bits = len(encrypted) * 8
        if pool.size < required_bits:
            raise CompatibilityError(
                f"Недостаточно ёмкости носителя: доступно {pool.size} бит, "
                f"требуется {required_bits}. Возьмите более крупный носитель или уменьшите payload."
            )

        # 6. Generate coordinates. The spreader knows how to turn its pool into a deterministic permutation under the seed.
        spreader = self._lsb_spreader if processor_kind == "LSB" else self._dct_spreader
        coords = spreader.generate_coords(
            container=original,
            payload_bits_len=required_bits,
            password_seed=request.password,
        )

        # Snapshot for the sanity check (DCT only — LSB sanity uses PSNR=inf).
        pre_embed_snapshot = None
        if processor_kind == "DCT":
            pre_embed_snapshot = original.coef_arrays[0].copy()

        # 7. Embedding.
        stego = processor.embed(original, encrypted, coords)

        # 8. Save.
        fmt_handler.save(stego, request.output_path)

        # 9. Metrics + sanity check.
        metrics = self._compute_metrics(
            processor_kind, original, stego, t0,
            pre_embed_snapshot=pre_embed_snapshot,
            original_path=request.carrier_path,
            output_path=request.output_path,
            compute_visual_metrics=request.compute_visual_metrics,
        )

        return StegoResponse(
            success=True,
            output_path=request.output_path,
            metrics=metrics,
        )
    
    def extract_data(self, request: StegoTaskRequest) -> StegoResponse:
        """Extracts the payload from a stego container.

        Mirror of hide_data:
            1. Load the stego container.
            2. Build the same coordinate pool (same format -> same pool).
            3. Spreader with the same password -> the same coordinates.
            4. Extract the header (57 bytes) and read LENGTH from it.
            5. Extract the header + ciphertext at full size.
            6. CryptoEngine.decrypt -> original bytes.
            7. Write them to output_path.

        Args:
            request: StegoTaskRequest. carrier_path is the stego file,
                     output_path is where to save the extracted payload.

        Returns:
            StegoResponse(success=True, output_path=...) on success.
        """
        t0 = time.perf_counter()

        # 1. Detect the stego container format.
        carrier_fmt = self._identifier.identify(request.carrier_path)
        if carrier_fmt not in _FORMAT_REGISTRY:
            raise CompatibilityError(
                f"Формат '{carrier_fmt}' не поддержан. "
                f"Поддержанные: {list(_FORMAT_REGISTRY)}"
            )

        # 2. Load the stego container.
        fmt_handler = _FORMAT_REGISTRY[carrier_fmt]()
        stego = fmt_handler.load(request.carrier_path)

        # 3. Same pool as at embed time.
        processor_kind = _FORMAT_TO_PROCESSOR[carrier_fmt]
        pool, processor = self._build_pool(processor_kind, stego)

        # 4. Extract the header (57 bytes) to determine LENGTH.
        header_size = CryptoEngine.header_size()  # 57 bytes; kept in its own variable
        header_bits = header_size * 8

        if pool.size < header_bits:
            raise CompatibilityError(
                "Стего-контейнер слишком мал даже для заголовка. "
                "Возможно, файл не содержит payload."
            )

        # The same password on the spreader yields the same coordinates as embed.
        spreader = self._lsb_spreader if processor_kind == "LSB" else self._dct_spreader
        coords_for_header = spreader.generate_coords(
            container=stego,
            payload_bits_len=header_bits,
            password_seed=request.password,
        )

        header_bytes = processor.extract(stego, coords_for_header, header_size)

        # 6. Parse LENGTH from the header (offset is MAGIC+FLAGS+SALT+NONCE).
        #    To avoid hand-parsing, pass the header to CryptoEngine —
        #    it raises on a bad MAGIC itself.
        

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

        # 7. Extract the full frame (header + ciphertext).
        full_frame_size = header_size + ciphertext_len
        full_frame_bits = full_frame_size * 8

        if pool.size < full_frame_bits:
            raise CompatibilityError(
                f"Стего-контейнер не содержит полный фрейм: "
                f"нужно {full_frame_bits} бит, доступно {pool.size}."
            )

        coords_full = spreader.generate_coords(
            container=stego,
            payload_bits_len=full_frame_bits,
            password_seed=request.password,
        )

        full_frame = processor.extract(stego, coords_full, full_frame_size)

        # 8. Write the extracted payload to a file.
        payload_bytes = self._crypto.decrypt(full_frame, request.password)

        # Try to detect the original payload format from magic bytes so the file gets the right extension.
        # If the format is unrecognized (text, unsupported binary) it defaults to .bin.
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
        """Detects the file format from magic bytes.

        Public wrapper over FormatIdentifier for the GUI.
        The GUI must not import core directly.

        Returns:
            "PNG" | "WAV" | "JPEG"

        Raises:
            ValueError: if the format is not supported.
        """
        return self._identifier.identify(path)
    

    def analyze_capacity(self, request: StegoTaskRequest) -> CapacityReport:
        """Estimates capacity WITHOUT actually hiding data.

        Used by the UI before the operation so the user sees
        real numbers and Hide can be blocked when needed.

        Steps:
            1. Detect the container format (magic bytes).
            2. Load the container.
            3. Build the coordinate pool the same way as hide_data
               (for LSB — every pixel, for DCT — filtered AC).
            4. Compute and compare with the payload size.

        Returns:
            CapacityReport with the fits flag.

        Raises:
            CompatibilityError: if the format is not supported.
            FileNotFoundError:  if the files do not exist.
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
        spreader = self._lsb_spreader if processor_kind == "LSB" else self._dct_spreader
        capacity_bits = spreader.get_max_capacity_bits(container)

        payload_size = Path(request.payload_path).stat().st_size
        header_size = CryptoEngine.header_size()
        # Crypto frame = header (57 bytes) + ciphertext (= payload + GCM tag).
        # The GCM tag is already included in header_size per our FrameLayout,
        # so we count header + payload in bits.
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
        """Returns the algorithm name for a format ('LSB' / 'DCT')."""
        return _FORMAT_TO_PROCESSOR.get(fmt, "?")

    def _build_pool(self, processor_kind: str, container: Any) -> tuple[np.ndarray, Any]:
        """Builds the coordinate pool.
        Returns (coordinate pool, processor) for the selected pipeline.

        LSB: the pool is every ndarray index (any pixel/sample is valid).
        DCT: the pool is built via DctProcessor.get_embeddable_positions
             (mid-frequency AC, excluding {-1, 0, 1}).
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
        compute_visual_metrics: bool = False,
    ) -> dict:
        """Computes metrics and runs the sanity check.

        LSB: PSNR + SSIM between two ndarrays. PSNR=inf means no bit
             was written (sanity fail).
        DCT: PSNR/SSIM on coefficients is not visually meaningful; we
             only time the operation and check that the Y channel changed.
        Shared: size_deviation is computed when paths are present,
                quality_status is based on the available metrics.

        Returns:
            dict with keys: psnr, ssim, time, size_deviation, quality_status — temporarily strings.
            Some keys may be absent depending on the pipeline.
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

            # SSIM is a psychovisual metric, optional (~1.5s on a 2MB PNG).
            # Computed only when the front end explicitly requested a detailed report.
            # PSNR above already ran the sanity check; repeating it via SSIM is unnecessary.
            if compute_visual_metrics:
                metrics["ssim"] = calculate_ssim(original_arr, stego_arr)

        #  DCT sanity check — no PSNR/SSIM
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

        #  File size deviation
        # Computed AFTER save(), so paths must ALWAYS be passed.
        size_dev: Optional[float] = None
        if original_path is not None and output_path is not None:
            try:
                size_dev = calculate_size_deviation(original_path, output_path)
                metrics["size_deviation"] = size_dev
            except (FileNotFoundError, OSError):
                # The file may be missing because of an OS error
                pass

        # Quality trigger
        metrics["quality_status"] = evaluate_quality(
            psnr=metrics.get("psnr"),
            size_deviation=size_dev,
        )

        return metrics
