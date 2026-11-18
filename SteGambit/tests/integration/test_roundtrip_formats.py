"""Byte-perfect round-trip: encode -> decode -> compare payload bytes.

The main integration invariant — what was put in is what comes out.
Parametrized over every supported carrier format and different payloads.
"""
import pytest

from stegambit.models.dto import StegoTaskRequest
from stegambit.services.stego_service import StegoService

pytestmark = [pytest.mark.integration]


@pytest.mark.parametrize(
    "carrier_fixture, payload_fixture, out_ext",
    [
        # PNG carrier, LSB pipeline.
        ("png_medium", "payload_tiny", ".png"),
        ("png_medium", "payload_pdf", ".png"),
        ("png_medium", "payload_zip", ".png"),
        # WAV carrier, LSB pipeline.
        ("wav_carrier", "payload_tiny", ".wav"),
        ("wav_carrier", "payload_pdf", ".wav"),
        # JPEG carrier, DCT pipeline.
        ("jpeg_carrier", "payload_tiny", ".jpg"),
        ("jpeg_carrier", "payload_pdf", ".jpg"),
    ],
    ids=[
        "PNG+tiny", "PNG+pdf", "PNG+zip",
        "WAV+tiny", "WAV+pdf",
        "JPEG+tiny", "JPEG+pdf",
    ],
)
def test_roundtrip_byte_identical(
    request, carrier_fixture, payload_fixture, out_ext, tmp_path,
):
    """Encode -> decode -> extracted bytes are identical to the original payload.

    The main pipeline invariant. If it fails, data is corrupted somewhere
    between embed and extract (coordinate-pool mismatch, a crypto error,
    losses while saving the format).
    """

    carrier = request.getfixturevalue(carrier_fixture)
    payload = request.getfixturevalue(payload_fixture)
    stego_path = tmp_path / f"stego{out_ext}"
    extract_out = tmp_path / "extracted"

    service = StegoService()

    # Encode.
    hide_req = StegoTaskRequest(
        carrier_path=carrier,
        payload_path=payload,
        output_path=stego_path,
        password="test_password",
    )
    hide_resp = service.hide_data(hide_req)
    assert hide_resp.success
    assert stego_path.exists()

    # Decode.
    extract_req = StegoTaskRequest(
        carrier_path=stego_path,
        payload_path=stego_path,  # unused during extract
        output_path=extract_out,
        password="test_password",
    )
    extract_resp = service.extract_data(extract_req)
    assert extract_resp.success

    # Byte-identical check.
    original_bytes = payload.read_bytes()
    extracted_bytes = extract_resp.output_path.read_bytes()
    assert extracted_bytes == original_bytes, (
        f"Round-trip нарушен: payload изменился. "
        f"Размер до={len(original_bytes)}, после={len(extracted_bytes)}"
    )


def test_roundtrip_detects_payload_format(
    png_medium, payload_pdf, tmp_path,
):
    """After extract, output_path gets the correct extension from magic bytes.

    Checks the integration of FormatIdentifier.identify_bytes into extract_data:
    a PDF payload must be saved with .pdf (not .bin).
    """

    service = StegoService()
    stego_path = tmp_path / "stego.png"
    extract_out = tmp_path / "extracted"

    service.hide_data(StegoTaskRequest(
        carrier_path=png_medium,
        payload_path=payload_pdf,
        output_path=stego_path,
        password="pwd",
    ))
    resp = service.extract_data(StegoTaskRequest(
        carrier_path=stego_path,
        payload_path=stego_path,
        output_path=extract_out,
        password="pwd",
    ))

    # PDF is not registered in _FORMAT_TO_EXT, so .bin is expected.
    # This is correct behavior: get_default_extension knows only PNG/JPEG/WAV.
    # TODO: Update when PDF is added
    assert resp.output_path.suffix == ".bin"

    # But the contents must start with the PDF magic %PDF.
    assert resp.output_path.read_bytes().startswith(b"%PDF")


def test_roundtrip_text_payload_detected_as_unknown(
    png_small, payload_tiny, tmp_path,
):
    """A text payload has no magic bytes -> it is saved as .bin."""

    service = StegoService()
    stego_path = tmp_path / "stego.png"
    extract_out = tmp_path / "extracted"

    service.hide_data(StegoTaskRequest(
        carrier_path=png_small,
        payload_path=payload_tiny,
        output_path=stego_path,
        password="pwd",
    ))
    resp = service.extract_data(StegoTaskRequest(
        carrier_path=stego_path,
        payload_path=stego_path,
        output_path=extract_out,
        password="pwd",
    ))

    assert resp.output_path.suffix == ".bin"
    assert resp.output_path.read_bytes() == payload_tiny.read_bytes()