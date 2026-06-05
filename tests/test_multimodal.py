"""Tests for commandor.utils.multimodal."""
import base64
from pathlib import Path

import pytest

from commandor.utils.multimodal import (
    MAX_IMAGE_BYTES,
    _guess_mime,
    build_multimodal_message,
    encode_image_to_data_url,
    is_image_file,
)


PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32  # not a real PNG but starts like one


class TestIsImageFile:
    def test_known_extensions(self):
        for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"]:
            assert is_image_file(f"image{ext}") is True

    def test_unknown_extension(self):
        assert is_image_file("script.py") is False
        assert is_image_file("README") is False

    def test_case_insensitive(self):
        assert is_image_file("photo.PNG") is True
        assert is_image_file("photo.JpG") is True


class TestEncodeImage:
    def test_round_trip_data_url(self, tmp_project: Path):
        f = tmp_project / "test.png"
        payload = b"\x89PNG\r\n\x1a\n" + b"hi" * 100
        f.write_bytes(payload)
        url = encode_image_to_data_url(f)
        assert url.startswith("data:")
        assert ";base64," in url
        # payload is recoverable
        encoded = url.split(",", 1)[1]
        assert base64.b64decode(encoded) == payload

    def test_missing_file_raises(self, tmp_project: Path):
        with pytest.raises(FileNotFoundError):
            encode_image_to_data_url(tmp_project / "nope.png")

    def test_directory_raises(self, tmp_project: Path):
        with pytest.raises(ValueError):
            encode_image_to_data_url(tmp_project)

    def test_oversized_file_raises(self, tmp_project: Path, monkeypatch):
        # Patch the constant to keep the test tiny but still exercise the
        # "too large" branch.
        import commandor.utils.multimodal as m

        monkeypatch.setattr(m, "MAX_IMAGE_BYTES", 16)
        f = tmp_project / "big.png"
        f.write_bytes(b"\x89PNG" + b"x" * 100)
        with pytest.raises(ValueError):
            encode_image_to_data_url(f)


class TestBuildMultimodalMessage:
    def test_text_only(self, tmp_project: Path):
        blocks = build_multimodal_message("hello", [])
        assert blocks == [{"type": "text", "text": "hello"}]

    def test_empty_text_with_images(self, tmp_project: Path):
        f = tmp_project / "a.png"
        f.write_bytes(PNG_HEADER)
        blocks = build_multimodal_message("", [f])
        assert len(blocks) == 1
        assert blocks[0]["type"] == "image_url"
        assert blocks[0]["image_url"]["url"].startswith("data:")

    def test_text_plus_images_order(self, tmp_project: Path):
        f1 = tmp_project / "a.png"
        f2 = tmp_project / "b.png"
        f1.write_bytes(PNG_HEADER)
        f2.write_bytes(PNG_HEADER)
        blocks = build_multimodal_message("caption", [f1, f2])
        assert blocks[0] == {"type": "text", "text": "caption"}
        assert blocks[1]["type"] == "image_url"
        assert blocks[2]["type"] == "image_url"

    def test_missing_image_raises(self, tmp_project: Path):
        with pytest.raises(FileNotFoundError):
            build_multimodal_message("hi", [tmp_project / "missing.png"])


class TestGuessMime:
    def test_known_types(self, tmp_project: Path):
        png = tmp_project / "x.png"
        png.touch()
        assert _guess_mime(png) == "image/png"

        txt = tmp_project / "x.txt"
        txt.touch()
        assert _guess_mime(txt) == "text/plain"

    def test_unknown_extension(self, tmp_project: Path):
        f = tmp_project / "x.qwert"
        f.touch()
        assert _guess_mime(f) == "application/octet-stream"
