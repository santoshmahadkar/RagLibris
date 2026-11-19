import pymupdf
import pytesseract

from PIL import Image
from io import BytesIO


TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


def extract_pdf_text(file_content):

    text_pages = []

    # ======================================================
    # FIRST: NORMAL PDF TEXT EXTRACTION
    # ======================================================

    with pymupdf.open(
        stream=file_content,
        filetype="pdf"
    ) as pdf:

        for page_number, page in enumerate(
            pdf,
            start=1
        ):

            page_text = page.get_text("text")

            if page_text.strip():

                text_pages.append(
                    page_text
                )

    text = "\n\n".join(
        text_pages
    ).strip()

    # ======================================================
    # IF TEXT FOUND → RETURN IT
    # ======================================================

    if text:

        print(
            f"PDF text extraction completed: "
            f"{len(text)} characters",
            flush=True
        )

        return text

    # ======================================================
    # OCR FALLBACK
    # ======================================================

    print(
        "PDF contains no extractable text. "
        "Trying OCR...",
        flush=True
    )

    return extract_pdf_with_ocr(
        file_content
    )


def extract_pdf_with_ocr(file_content):

    extracted_pages = []

    try:

        with pymupdf.open(
            stream=file_content,
            filetype="pdf"
        ) as pdf:

            total_pages = len(pdf)

            print(
                f"Running OCR on "
                f"{total_pages} PDF page(s)...",
                flush=True
            )

            for page_number, page in enumerate(
                pdf,
                start=1
            ):

                print(
                    f"OCR page "
                    f"{page_number}/{total_pages}...",
                    flush=True
                )

                # ------------------------------------------
                # Render PDF page to image
                # ------------------------------------------

                pix = page.get_pixmap(
                    matrix=pymupdf.Matrix(2, 2),
                    alpha=False
                )

                image_bytes = pix.tobytes(
                    "png"
                )

                image = Image.open(
                    BytesIO(image_bytes)
                )

                # ------------------------------------------
                # OCR
                # ------------------------------------------

                page_text = pytesseract.image_to_string(
                    image
                )

                page_text = page_text.strip()

                if page_text:

                    extracted_pages.append(
                        page_text
                    )

                    print(
                        f"Page {page_number}: "
                        f"{len(page_text)} characters",
                        flush=True
                    )

                else:

                    print(
                        f"Page {page_number}: "
                        f"no text detected",
                        flush=True
                    )

        text = "\n\n".join(
            extracted_pages
        ).strip()

        print(
            f"PDF OCR completed: "
            f"{len(text)} characters",
            flush=True
        )

        return text

    except Exception as exc:

        print(
            f"WARNING: PDF OCR failed: "
            f"{type(exc).__name__}: {exc}",
            flush=True
        )

        return ""