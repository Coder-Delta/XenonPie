import pytesseract
from pdf2image import convert_from_path
from pathlib import Path
from loguru import logger
from typing import Optional
import tempfile
import httpx


async def ocr_from_pdf_url(pdf_url: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(pdf_url)
            response.raise_for_status()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name

        return ocr_from_pdf_file(tmp_path)

    except Exception as e:
        logger.error(f"OCR from URL failed {pdf_url}: {e}")
        return None


def ocr_from_pdf_file(pdf_path: str) -> Optional[str]:
    try:
        pages = convert_from_path(pdf_path, dpi=200)
        full_text = []

        for i, page in enumerate(pages):
            text = pytesseract.image_to_string(page, lang="eng")
            full_text.append(text)
            logger.debug(f"OCR page {i+1}/{len(pages)} done")

        result = "\n".join(full_text).strip()
        logger.info(f"OCR extracted {len(result)} chars from {pdf_path}")
        return result

    except Exception as e:
        logger.error(f"OCR failed for {pdf_path}: {e}")
        return None


def ocr_from_image(image_path: str) -> Optional[str]:
    try:
        from PIL import Image
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang="eng")
        return text.strip()
    except Exception as e:
        logger.error(f"OCR image failed {image_path}: {e}")
        return None