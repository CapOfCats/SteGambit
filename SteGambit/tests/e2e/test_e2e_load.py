"""E2E load tests: stress scenarios on large files.

Run with the flag: -m load -v -s

Artifacts:
     large.png       (3.5 MB, 2K×2K)  capacity 380 KB payload
     long.wav        (68 MB, 16-bit/44.1)  capacity 850 KB payload
     large_photo.jpg (8 MB)              capacity 387 KB payload

Capacity for PNG/WAV is much smaller than the file size because of filtering
of "noisy" pixels/samples in SmartSpreader (edge detection for PNG,
silence cutoff for WAV). For JPEG, capacity is set by the filter of
mid-frequency AC coefficients.

Expected runtime: 3-6 minutes.

Architectural note:
    PNG carriers > 3.5MB can cause OOM on consumer machines. SmartSpreader allocates O(N) memory
    from the container size; on 6K×6K that is 3-5 GB of peak memory.
"""
import time
from pathlib import Path

import pytest

from stegambit.models.dto import StegoTaskRequest
from stegambit.services.stego_service import StegoService
from stegambit.core.exceptions import CompatibilityError

from .conftest import assert_bytes_equal_to_file


# Marker for every test in this module.
pytestmark = pytest.mark.load


class TestE2ELoadPNG:
    """Load testing of PNG-LSB.

    A realistic carrier ceiling is ~3.5MB because of O(N) memory in SmartSpreader.
    Capacity of such a PNG is ~380KB of payload (10-15% of the file after the edge filter).
    """

    def test_png_load_250kb_payload(
        self, png_large: Path, payload_250kb: Path, tmp_path: Path
    ):
        """PNG 3.5MB + 250KB payload (comfortable capacity margin)."""
        service = StegoService()

        t0 = time.perf_counter()
        hide_resp = service.hide_data(StegoTaskRequest(
            carrier_path=png_large,
            payload_path=payload_250kb,
            output_path=tmp_path / "stego.png",
            password="load_pwd",
        ))
        hide_time = time.perf_counter() - t0

        assert hide_resp.success is True
        assert hide_resp.metrics["psnr"] > 40.0
        print(f"\n[LOAD PNG 250KB] hide={hide_time:.2f}s, "
              f"PSNR={hide_resp.metrics['psnr']:.1f}dB")

        t0 = time.perf_counter()
        extract_resp = service.extract_data(StegoTaskRequest(
            carrier_path=hide_resp.output_path,
            payload_path=hide_resp.output_path,
            output_path=tmp_path / "extracted.bin",
            password="load_pwd",
        ))
        extract_time = time.perf_counter() - t0

        assert extract_resp.success is True
        assert_bytes_equal_to_file(extract_resp.output_path.read_bytes(), payload_250kb)
        print(f"[LOAD PNG 250KB] extract={extract_time:.2f}s")

    def test_png_load_350kb_near_capacity(
        self, png_large: Path, payload_350kb: Path, tmp_path: Path
    ):
        """PNG 3.5MB + 350KB payload (at the 380KB capacity boundary).

        Best-effort: if this particular carrier's capacity turns out slightly
        smaller, skip, do not fail. PNG capacity varies by +-10%
        depending on image texture.
        """
        service = StegoService()
        try:
            t0 = time.perf_counter()
            hide_resp = service.hide_data(StegoTaskRequest(
                carrier_path=png_large,
                payload_path=payload_350kb,
                output_path=tmp_path / "stego.png",
                password="load_pwd",
            ))
            hide_time = time.perf_counter() - t0
        except (CompatibilityError, ValueError) as e:
            pytest.skip(f"PNG capacity недостаточна для 350KB payload: {e}")

        assert hide_resp.success is True
        print(f"\n[LOAD PNG 350KB] hide={hide_time:.2f}s, "
              f"PSNR={hide_resp.metrics['psnr']:.1f}dB")

        extract_resp = service.extract_data(StegoTaskRequest(
            carrier_path=hide_resp.output_path,
            payload_path=hide_resp.output_path,
            output_path=tmp_path / "extracted.bin",
            password="load_pwd",
        ))
        assert extract_resp.success is True
        assert_bytes_equal_to_file(extract_resp.output_path.read_bytes(), payload_350kb)


class TestE2ELoadWAV:
    """Load testing of WAV-LSB.

    WAV-LSB handles large files much more cheaply than PNG — there is no
    grayscale conversion or edge detection in the spatial domain. We test
    real loads on a 68MB carrier.
    """

    def test_wav_load_500kb_payload(
        self, wav_long: Path, payload_500kb: Path, tmp_path: Path
    ):
        """WAV ~68MB + 500KB payload."""
        service = StegoService()

        t0 = time.perf_counter()
        hide_resp = service.hide_data(StegoTaskRequest(
            carrier_path=wav_long,
            payload_path=payload_500kb,
            output_path=tmp_path / "stego.wav",
            password="wav_load_pwd",
        ))
        hide_time = time.perf_counter() - t0

        assert hide_resp.success is True
        print(f"\n[LOAD WAV 500KB] hide={hide_time:.2f}s")

        extract_resp = service.extract_data(StegoTaskRequest(
            carrier_path=hide_resp.output_path,
            payload_path=hide_resp.output_path,
            output_path=tmp_path / "extracted.bin",
            password="wav_load_pwd",
        ))
        assert extract_resp.success is True
        assert_bytes_equal_to_file(extract_resp.output_path.read_bytes(), payload_500kb)

    def test_wav_load_750kb_near_capacity(
        self, wav_long: Path, payload_750kb: Path, tmp_path: Path
    ):
        """WAV 68MB + 750KB payload (at the 850KB capacity boundary).

        Best-effort: if this particular WAV contains more silence than
        expected, capacity drops. In that case — skip.
        """
        service = StegoService()
        try:
            t0 = time.perf_counter()
            hide_resp = service.hide_data(StegoTaskRequest(
                carrier_path=wav_long,
                payload_path=payload_750kb,
                output_path=tmp_path / "stego.wav",
                password="wav_pwd",
            ))
            hide_time = time.perf_counter() - t0
        except (CompatibilityError, ValueError) as e:
            pytest.skip(f"WAV capacity недостаточна для 750KB payload: {e}")

        assert hide_resp.success is True
        print(f"\n[LOAD WAV 750KB] hide={hide_time:.2f}s")

        extract_resp = service.extract_data(StegoTaskRequest(
            carrier_path=hide_resp.output_path,
            payload_path=hide_resp.output_path,
            output_path=tmp_path / "extracted.bin",
            password="wav_pwd",
        ))
        assert extract_resp.success is True
        assert_bytes_equal_to_file(extract_resp.output_path.read_bytes(), payload_750kb)


class TestE2ELoadJPEG:
    """Load testing of JPEG-DCT.

    JPEG-DCT capacity is 5-10% of the file size after the filter of
    mid-frequency AC coefficients. For an 8MB file that is a 387KB payload.
    """

    def test_jpeg_load_100kb_payload(
        self, jpeg_large: Path, payload_100kb: Path, tmp_path: Path
    ):
        """JPEG 8MB + 100KB payload (comfortable margin)."""
        service = StegoService()

        t0 = time.perf_counter()
        hide_resp = service.hide_data(StegoTaskRequest(
            carrier_path=jpeg_large,
            payload_path=payload_100kb,
            output_path=tmp_path / "stego.jpg",
            password="jpeg_pwd",
        ))
        hide_time = time.perf_counter() - t0

        assert hide_resp.success is True
        print(f"\n[LOAD JPEG 100KB] hide={hide_time:.2f}s")

        extract_resp = service.extract_data(StegoTaskRequest(
            carrier_path=hide_resp.output_path,
            payload_path=hide_resp.output_path,
            output_path=tmp_path / "extracted.bin",
            password="jpeg_pwd",
        ))
        assert extract_resp.success is True
        assert_bytes_equal_to_file(extract_resp.output_path.read_bytes(), payload_100kb)

    def test_jpeg_load_300kb_near_capacity(
        self, jpeg_large: Path, payload_300kb: Path, tmp_path: Path
    ):
        """JPEG 8MB + 300KB payload (at the 387KB capacity boundary).

        Best-effort: DCT-pool capacity depends on the texture of the particular photo. If it is not enough — skip.
        """
        service = StegoService()
        try:
            t0 = time.perf_counter()
            hide_resp = service.hide_data(StegoTaskRequest(
                carrier_path=jpeg_large,
                payload_path=payload_300kb,
                output_path=tmp_path / "stego.jpg",
                password="jpeg_max_pwd",
            ))
            hide_time = time.perf_counter() - t0
        except (CompatibilityError, ValueError) as e:
            pytest.skip(f"JPEG capacity недостаточна для 300KB payload: {e}")

        assert hide_resp.success is True
        print(f"\n[LOAD JPEG 300KB] hide={hide_time:.2f}s")

        extract_resp = service.extract_data(StegoTaskRequest(
            carrier_path=hide_resp.output_path,
            payload_path=hide_resp.output_path,
            output_path=tmp_path / "extracted.bin",
            password="jpeg_max_pwd",
        ))
        assert extract_resp.success is True
        assert_bytes_equal_to_file(extract_resp.output_path.read_bytes(), payload_300kb)


class TestE2ELoadDynamicCapacity:
    """Dynamic capacity tests.

    Instead of fixed payload sizes they use analyze_capacity()
    to find the real ceiling of a particular carrier and pick a
    payload "at 95% capacity". These tests work on any artifacts and are not tied to exact file sizes.
    """

    def test_png_capacity_95_percent(
        self, png_large: Path, payload_tiny: Path, tmp_path: Path
    ):
        """Picks a payload at 95% of the real capacity of the PNG carrier
        and checks a full roundtrip."""
        service = StegoService()

        # Step 1: ask the service for capacity (pass any existing
        # payload — analyze_capacity uses it only for the size).
        probe_req = StegoTaskRequest(
            carrier_path=png_large,
            payload_path=payload_tiny,
            output_path=tmp_path / "stego.png",
            password="dyn_pwd",
        )
        report = service.analyze_capacity(probe_req)
        target_payload_size = int(report.capacity_bits / 8 * 0.95) - report.header_size_bytes
        assert target_payload_size > 0, "Capacity слишком мала даже для заголовка"

        # Step 2: generate a payload of exactly that size.
        import numpy as np
        rng = np.random.default_rng(seed=42)
        dynamic_payload = tmp_path / "dynamic_payload.bin"
        dynamic_payload.write_bytes(rng.bytes(target_payload_size))

        print(f"\n[DYNAMIC PNG] capacity={report.capacity_bits} bits, "
              f"payload={target_payload_size} bytes (95% load)")

        # Step 3: full roundtrip.
        hide_req = StegoTaskRequest(
            carrier_path=png_large,
            payload_path=dynamic_payload,
            output_path=tmp_path / "stego.png",
            password="dyn_pwd",
        )
        t0 = time.perf_counter()
        hide_resp = service.hide_data(hide_req)
        print(f"[DYNAMIC PNG] hide={time.perf_counter() - t0:.2f}s")

        assert hide_resp.success is True

        extract_resp = service.extract_data(StegoTaskRequest(
            carrier_path=hide_resp.output_path,
            payload_path=hide_resp.output_path,
            output_path=tmp_path / "extracted.bin",
            password="dyn_pwd",
        ))
        assert extract_resp.success is True
        assert_bytes_equal_to_file(extract_resp.output_path.read_bytes(), dynamic_payload)