"""Unit/IO tests for WavFormat in wav.py.

IMPORTANT: WavFormat is hardcoded to 1 ch / 16-bit / 44100 Hz (a TODO exists).
All save/round-trip tests use exactly these parameters.
"""
from pathlib import Path
import wave

import numpy as np
from numpy.random._generator import Generator
import pytest

from stegambit.core.formats.wav import WavFormat, WavContainer


@pytest.fixture
def wav_format():
    return WavFormat()


@pytest.mark.io
class TestLoad:

    def test_load_returns_container(self, wav_format: WavFormat, wav_carrier):
        """Property: load returns a WavContainer (not a bare ndarray)."""
        from stegambit.core.formats.wav import WavContainer
        result = wav_format.load(wav_carrier)
        assert isinstance(result, WavContainer)

    def test_load_samples_is_ndarray(self, wav_format: WavFormat, wav_carrier):
        """Property: container.samples is an np.ndarray."""
        container = wav_format.load(wav_carrier)
        assert isinstance(container.samples, np.ndarray)

    def test_load_samples_dtype_is_int16(self, wav_format: WavFormat, wav_carrier):
        """Property: WAV samples are int16."""
        container = wav_format.load(wav_carrier)
        assert container.samples.dtype == np.int16

    def test_load_samples_is_1d(self, wav_format: WavFormat, wav_carrier):
        """Property: samples are returned as a 1D array."""
        container = wav_format.load(wav_carrier)
        assert container.samples.ndim == 1

    def test_load_preserves_metadata(self, wav_format: WavFormat, wav_carrier):
        """Property: metadata is preserved."""
        container = wav_format.load(wav_carrier)
        assert container.n_channels >= 1
        assert container.sampwidth in (1, 2, 4)
        assert container.framerate > 0

    def test_container_array_protocol(self, wav_format: WavFormat, wav_carrier):
        """Property: np.asarray(container) works (the ndarray-like contract)."""
        container = wav_format.load(wav_carrier)
        arr = np.asarray(container)
        assert isinstance(arr, np.ndarray)
        np.testing.assert_array_equal(arr, container.samples)

    def test_load_missing_file_raises(self, wav_format: WavFormat, tmp_path: Path):
        """Negative case: a file that does not exist."""
        with pytest.raises(FileNotFoundError):
            wav_format.load(tmp_path / "ghost.wav")

    def test_load_corrupt_file_raises(self, wav_format: WavFormat, tmp_path: Path):
        """Negative case: a corrupted WAV -> an exception from the wave module."""
        broken = tmp_path / "broken.wav"
        broken.write_bytes(b"RIFFnot_a_real_wav_file")
        with pytest.raises(Exception):
            wav_format.load(broken)


@pytest.mark.io
class TestSave:

    def test_save_from_container_creates_file(self, wav_format: WavFormat, rng: Generator, tmp_path: Path):
        """save from a WavContainer creates a WAV file."""
        samples = rng.integers(-32768, 32767, size=4410, dtype=np.int16)
        container = WavContainer(samples=samples, n_channels=1, sampwidth=2, framerate=44100)
        out = tmp_path / "out.wav"
        wav_format.save(container, out)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_save_from_ndarray_uses_defaults(self, wav_format: WavFormat, rng: Generator, tmp_path: Path):
        """The saved WAV has 1 channel, 16 bits, 44100 Hz."""
        samples = rng.integers(-32768, 32767, size=4410, dtype=np.int16)
        out = tmp_path / "out.wav"
        wav_format.save(samples, out)

        with wave.open(str(out), "rb") as w:
            assert w.getnchannels() == 1
            assert w.getsampwidth() == 2
            assert w.getframerate() == 44100
    
    def test_save_preserves_stereo_48khz(self, wav_format: WavFormat, rng: Generator, tmp_path: Path):
        """Property: stereo 48kHz keeps its parameters after save."""
        samples = rng.integers(-32768, 32767, size=96000, dtype=np.int16)
        container = WavContainer(samples=samples, n_channels=2, sampwidth=2, framerate=48000)
        out = tmp_path / "stereo.wav"
        wav_format.save(container, out)

        with wave.open(str(out), "rb") as w:
            assert w.getnchannels() == 2
            assert w.getsampwidth() == 2
            assert w.getframerate() == 48000


@pytest.mark.io
class TestRoundTrip:

    def test_round_trip_preserves_samples_and_metadata(self, wav_format: WavFormat, wav_carrier, tmp_path: Path):
        """PCM int16 WAV is lossless; samples are identical."""
        original = wav_format.load(wav_carrier)
        out = tmp_path / "rt.wav"
        wav_format.save(original, out)
        loaded = wav_format.load(out)

        np.testing.assert_array_equal(original.samples, loaded.samples)
        assert original.n_channels == loaded.n_channels
        assert original.sampwidth == loaded.sampwidth
        assert original.framerate == loaded.framerate
    
    def test_round_trip_after_lsb_modification_preserves_metadata(self, wav_format: WavFormat, wav_carrier, tmp_path: Path):
        """Modifying the array does not lose metadata on save."""
        container = wav_format.load(wav_carrier)
        original_channels = container.n_channels
        original_framerate = container.framerate

        # Simulate an LSB modification.
        container.samples[0] ^= 1
        container.samples[100] ^= 1

        out = tmp_path / "modified.wav"
        wav_format.save(container, out)
        reloaded = wav_format.load(out)

        assert reloaded.n_channels == original_channels
        assert reloaded.framerate == original_framerate


class TestMagic:

    def test_magic_is_riff(self, wav_format: WavFormat):
        """magic is RIFF."""
        assert wav_format.magic == b"RIFF"