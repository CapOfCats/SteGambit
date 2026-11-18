"""Integration tests of the "format conversion forbidden" policy.

Covers the ADR about the carrier format being immutable. Stego output must keep the original carrier format.
Trying to set an output with a different extension leads to CompatibilityError BEFORE embed.
"""
import pytest

from stegambit.core.exceptions import CompatibilityError
from stegambit.models.dto import StegoTaskRequest
from stegambit.services.stego_service import StegoService


pytestmark = [pytest.mark.integration]


@pytest.fixture
def service():
    return StegoService()


class TestForbiddenConversions:
    """Decision table: pairs (carrier_fmt, output_ext) that MUST fail.

    Technique: decision table. Each row is a forbidden combination
    of formats; we check that the service correctly refuses.
    """

    @pytest.mark.parametrize(
        "carrier_fixture, forbidden_ext",
        [
            # A PNG carrier must not be saved into a foreign format.
            ("png_medium", ".jpg"),
            ("png_medium", ".jpeg"),
            ("png_medium", ".wav"),
            ("png_medium", ".bmp"),
            # JPEG carrier.
            ("jpeg_carrier", ".png"),
            ("jpeg_carrier", ".wav"),
            ("jpeg_carrier", ".bin"),
            # WAV carrier.
            ("wav_carrier", ".png"),
            ("wav_carrier", ".mp3"),
            ("wav_carrier", ".jpg"),
        ],
        ids=[
            "PNG->jpg", "PNG->jpeg", "PNG->wav", "PNG->bmp",
            "JPEG->png", "JPEG->wav", "JPEG->bin",
            "WAV->png", "WAV->mp3", "WAV->jpg",
        ],
    )
    def test_forbidden_output_extension_raises(
        self, request, service, carrier_fixture, forbidden_ext,
        payload_tiny, tmp_path,
    ):
        """A mismatch of carrier format and output extension -> CompatibilityError.

        Equivalence: every forbidden extension is one refusal class.
        """
        carrier = request.getfixturevalue(carrier_fixture)
        stego_path = tmp_path / f"stego{forbidden_ext}"

        with pytest.raises(CompatibilityError):
            service.hide_data(StegoTaskRequest(
                carrier_path=carrier,
                payload_path=payload_tiny,
                output_path=stego_path,
                password="pwd",
            ))

        # Conversion is forbidden — the file must not be created.
        assert not stego_path.exists(), (
            "Файл создан, хотя политика запрещает конвертацию формата."
        )


class TestAllowedFormats:
    """Sanity block: positive cases of the policy must pass.

    Technique: positive representatives of the equivalence classes from the decision table.
    """

    @pytest.mark.parametrize(
        "carrier_fixture, allowed_ext",
        [
            ("png_medium", ".png"),
            ("jpeg_carrier", ".jpg"),
            ("jpeg_carrier", ".jpeg"),
            ("wav_carrier", ".wav"),
        ],
        ids=["PNG->png", "JPEG->jpg", "JPEG->jpeg", "WAV->wav"],
    )
    def test_matching_extension_succeeds(
        self, request, service, carrier_fixture, allowed_ext,
        payload_tiny, tmp_path,
    ):
        """A match of carrier format and output extension -> embed succeeds."""
        carrier = request.getfixturevalue(carrier_fixture)
        stego_path = tmp_path / f"stego{allowed_ext}"

        resp = service.hide_data(StegoTaskRequest(
            carrier_path=carrier,
            payload_path=payload_tiny,
            output_path=stego_path,
            password="pwd",
        ))

        assert resp.success
        assert stego_path.exists()


class TestCaseSensitivity:
    """Behavior with different extension casings."""

    @pytest.mark.parametrize(
        "ext_variant",
        [".PNG", ".Png", ".pNg"],
        ids=["upper", "title", "mixed"],
    )
    def test_extension_case_insensitive_for_png(
        self, service, png_medium, payload_tiny, tmp_path, ext_variant,
    ):
        """The extension must be compared case-insensitively.

        Boundary case: the user saves as "stego.PNG" from a Save Dialog
        on Windows — it must work the same as ".png".
        """
        stego_path = tmp_path / f"stego{ext_variant}"

        resp = service.hide_data(StegoTaskRequest(
            carrier_path=png_medium,
            payload_path=payload_tiny,
            output_path=stego_path,
            password="pwd",
        ))

        assert resp.success
        assert stego_path.exists()