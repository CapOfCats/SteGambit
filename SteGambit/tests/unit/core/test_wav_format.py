"""Unit/IO тесты для WavFormat wav.py.

ВАЖНО: WavFormat захардкожен на 1 ch / 16-bit / 44100 Hz (TODO имеется).
Все тесты save/round-trip используют именно эти параметры.
"""
from pathlib import Path
import wave

import numpy as np
import pytest

from stegambit.core.formats.wav import WavFormat


@pytest.fixture
def wav_format():
    return WavFormat()


@pytest.mark.io
class TestLoad:

    def test_load_returns_ndarray(self, wav_format, wav_carrier):
        """load возвращает np.ndarray."""
        arr = wav_format.load(wav_carrier)
        assert isinstance(arr, np.ndarray)

    def test_load_dtype_is_int16(self, wav_format, wav_carrier):
        """WAV семплы — int16 (контракт нашего пайплайна)."""
        arr = wav_format.load(wav_carrier)
        assert arr.dtype == np.int16

    def test_load_is_1d(self, wav_format, wav_carrier):
        """Cемплы возвращаются как 1D-массив."""
        arr = wav_format.load(wav_carrier)
        assert arr.ndim == 1

    def test_load_missing_file_raises(self, wav_format, tmp_path):
        """Негативный кейз: несуществующий файл."""
        with pytest.raises(FileNotFoundError):
            wav_format.load(tmp_path / "ghost.wav")

    def test_load_corrupt_file_raises(self, wav_format, tmp_path):
        """Негативный кейз: битый WAV - исключение от wave-модуля."""
        broken = tmp_path / "broken.wav"
        broken.write_bytes(b"RIFFnot_a_real_wav_file")
        with pytest.raises(Exception):
            wav_format.load(broken)


@pytest.mark.io
class TestSave:

    def test_save_creates_file(self, wav_format, rng, tmp_path):
        """save создаёт WAV-файл."""
        samples = rng.integers(-32768, 32767, size=4410, dtype=np.int16)
        out = tmp_path / "out.wav"
        wav_format.save(samples, out)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_save_writes_expected_params(self, wav_format, rng, tmp_path):
        """Cохранённый WAV имеет 1 канал, 16 бит, 44100 Hz."""
        samples = rng.integers(-32768, 32767, size=4410, dtype=np.int16)
        out = tmp_path / "out.wav"
        wav_format.save(samples, out)

        with wave.open(str(out), "rb") as w:
            assert w.getnchannels() == 1
            assert w.getsampwidth() == 2
            assert w.getframerate() == 44100


@pytest.mark.io
class TestRoundTrip:

    def test_round_trip_preserves_samples(self, wav_format, rng, tmp_path):
        """PCM int16 WAV - lossless, семплы идентичны."""
        original = rng.integers(-32768, 32767, size=4410, dtype=np.int16)
        out = tmp_path / "rt.wav"
        wav_format.save(original, out)
        loaded = wav_format.load(out)
        np.testing.assert_array_equal(original, loaded)


class TestMagic:

    def test_magic_is_riff(self, wav_format):
        """magic - RIFF."""
        assert wav_format.magic == b"RIFF"