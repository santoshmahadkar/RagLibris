from io import BytesIO
from zipfile import BadZipFile, ZipFile

from docx import Document

import xml.etree.ElementTree as ET

from PIL import Image
import pytesseract


# ==========================================================
# TESSERACT CONFIGURATION
# ==========================================================

# If Tesseract is installed in the default Windows location,
# this path should work.
#
# If you installed it somewhere else, change this path.

TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


# ==========================================================
# DOCX DIAGNOSTIC INSPECTION
# ==========================================================

def inspect_docx_contents(file_content):

    print("--------------------------------------------------")
    print("DOCX diagnostic inspection")
    print("--------------------------------------------------")

    try:

        with ZipFile(
            BytesIO(file_content),
            "r"
        ) as archive:

            files = archive.namelist()

            print(
                f"Total ZIP entries: {len(files)}"
            )

            xml_files = [
                name
                for name in files
                if name.endswith(".xml")
            ]

            media_files = [
                name
                for name in files
                if name.startswith("word/media/")
            ]

            print(
                f"XML files: {len(xml_files)}"
            )

            print(
                f"Media files: {len(media_files)}"
            )

            # --------------------------------------------------
            # Embedded images
            # --------------------------------------------------

            if media_files:

                print("")
                print("Images/media found:")

                for media_file in media_files:

                    info = archive.getinfo(
                        media_file
                    )

                    print(
                        f"  {media_file} "
                        f"({info.file_size} bytes)"
                    )

            # --------------------------------------------------
            # Important XML
            # --------------------------------------------------

            print("")
            print(
                "Important document XML parts:"
            )

            for name in files:

                if name in (
                    "word/document.xml",
                    "word/styles.xml",
                    "word/settings.xml",
                    "word/fontTable.xml",
                ):

                    print(
                        f"  {name}"
                    )

            # --------------------------------------------------
            # Headers / Footers
            # --------------------------------------------------

            print("")
            print(
                "Header/footer XML parts:"
            )

            for name in files:

                if (
                    name.startswith("word/header")
                    or name.startswith("word/footer")
                ):

                    print(
                        f"  {name}"
                    )

            # --------------------------------------------------
            # Drawing / textbox related XML
            # --------------------------------------------------

            print("")
            print(
                "Drawing/textbox related XML files:"
            )

            for name in xml_files:

                if (
                    "document" in name
                    or "header" in name
                    or "footer" in name
                    or "drawing" in name
                ):

                    print(
                        f"  {name}"
                    )

            print(
                "--------------------------------------------------"
            )

    except Exception as exc:

        print(
            f"DOCX diagnostic failed: "
            f"{type(exc).__name__}: {exc}",
            flush=True
        )


# ==========================================================
# DOCX XML FALLBACK
# ==========================================================

def extract_docx_xml(file_content):

    try:

        namespace = {
            "w": (
                "http://schemas.openxmlformats.org/"
                "wordprocessingml/2006/main"
            )
        }

        text_parts = []

        with ZipFile(
            BytesIO(file_content),
            "r"
        ) as archive:

            xml_parts = [
                name
                for name in archive.namelist()
                if (
                    name == "word/document.xml"
                    or (
                        name.startswith("word/header")
                        and name.endswith(".xml")
                    )
                    or (
                        name.startswith("word/footer")
                        and name.endswith(".xml")
                    )
                )
            ]

            for xml_file in xml_parts:

                print(f"Reading XML part: {xml_file}",flush=True)

                xml_content = archive.read(xml_file)

                root = ET.fromstring(xml_content)

                # ------------------------------------------
                # Find every Word paragraph
                # ------------------------------------------

                for paragraph in root.findall(".//w:p",namespace):

                    paragraph_text = []

                    for text_node in paragraph.findall(".//w:t",namespace):

                        if text_node.text:

                            paragraph_text.append(text_node.text)

                    text = "".join(paragraph_text).strip()

                    if text:

                        text_parts.append(text)

        return "\n".join(text_parts).strip()

    except Exception as exc:

        print(
            f"WARNING: DOCX XML fallback extraction failed: "
            f"{type(exc).__name__}: {exc}",
            flush=True
        )

        return ""


# ==========================================================
# EXTRACT IMAGES FROM DOCX
# ==========================================================

def extract_images_from_docx(file_content):

    images = []

    try:

        with ZipFile(
            BytesIO(file_content),
            "r"
        ) as archive:

            media_files = [
                name
                for name in archive.namelist()
                if name.startswith("word/media/")
            ]

            for media_file in media_files:

                try:

                    image_bytes = archive.read(
                        media_file
                    )

                    image = Image.open(
                        BytesIO(image_bytes)
                    )

                    # Force image loading while ZIP is open
                    image.load()

                    images.append(
                        (
                            media_file,
                            image.copy()
                        )
                    )

                except Exception as exc:

                    print(
                        f"WARNING: Unable to open "
                        f"DOCX image {media_file}: "
                        f"{type(exc).__name__}: {exc}",
                        flush=True
                    )

    except Exception as exc:

        print(
            f"WARNING: Unable to extract images from DOCX: "
            f"{type(exc).__name__}: {exc}",
            flush=True
        )

    return images


# ==========================================================
# OCR DOCX IMAGES
# ==========================================================

def ocr_docx_images(file_content):

    print(
        "Starting OCR on embedded DOCX images...",
        flush=True
    )

    images = extract_images_from_docx(file_content)

    if not images:

        print(
            "No embedded images found in DOCX.",
            flush=True
        )

        return ""

    print(
        f"Found {len(images)} embedded image(s).",
        flush=True
    )

    extracted_text = []

    for index, (filename, image) in enumerate(images, start=1):

        print(
            f"Running OCR on image "
            f"{index}/{len(images)}: "
            f"{filename}",
            flush=True
        )

        try:

            # --------------------------------------------------
            # Convert image to RGB
            # --------------------------------------------------

            if image.mode != "RGB":

                image = image.convert("RGB")

            # --------------------------------------------------
            # OCR
            # --------------------------------------------------

            text = pytesseract.image_to_string(image)

            text = text.strip()

            if text:

                print(
                    f"OCR extracted "
                    f"{len(text)} characters "
                    f"from {filename}",
                    flush=True
                )

                extracted_text.append(text)

            else:

                print(
                    f"OCR returned no text "
                    f"for {filename}",
                    flush=True
                )

        except Exception as exc:

            print(
                f"WARNING: OCR failed for "
                f"{filename}: "
                f"{type(exc).__name__}: {exc}",
                flush=True
            )

    return "\n\n".join(extracted_text).strip()


# ==========================================================
# DOCX TEXT EXTRACTION
# ==========================================================

def extract_docx_text(file_content):

    """
    Extract text from DOCX bytes.

    Extraction order:

    1. python-docx paragraphs
    2. python-docx tables
    3. python-docx headers
    4. python-docx footers
    5. DOCX XML fallback
    6. OCR embedded images

    Returns:
        Extracted text as string.
    """

    file_buffer = BytesIO(
        file_content
    )

    # ======================================================
    # OPEN DOCX
    # ======================================================

    try:

        doc = Document(
            file_buffer
        )

    except (
        BadZipFile,
        KeyError,
        ValueError
    ) as exc:

        print(
            "WARNING: Unable to read DOCX file.",
            flush=True
        )

        print(
            f"Reason: "
            f"{type(exc).__name__}: {exc}",
            flush=True
        )

        print(
            "Trying DOCX XML fallback...",
            flush=True
        )

        text = extract_docx_xml(
            file_content
        )

        if text:

            print(
                f"DOCX XML extraction completed: "
                f"{len(text)} characters",
                flush=True
            )

            return text

        print(
            "DOCX XML extraction returned no text.",
            flush=True
        )

        print(
            "Trying OCR...",
            flush=True
        )

        return ocr_docx_images(
            file_content
        )

    sections = []

    # ======================================================
    # EXTRACT NORMAL PARAGRAPHS
    # ======================================================

    paragraphs = []

    for paragraph in doc.paragraphs:

        text = paragraph.text.strip()

        if text:

            paragraphs.append(
                text
            )

    if paragraphs:

        sections.append(
            "\n".join(paragraphs)
        )

    # ======================================================
    # EXTRACT TABLES
    # ======================================================

    tables = []

    for table in doc.tables:

        rows = []

        for row in table.rows:

            cells = []

            for cell in row.cells:

                cell_text = (
                    cell.text.strip()
                )

                if cell_text:

                    cells.append(
                        cell_text
                    )

            if cells:

                rows.append(
                    " | ".join(cells)
                )

        if rows:

            tables.append(
                "\n".join(rows)
            )

    if tables:

        sections.append(
            "\n\n".join(tables)
        )

    # ======================================================
    # EXTRACT HEADERS / FOOTERS
    # ======================================================

    headers_footers = []

    for section in doc.sections:

        # --------------------------------------------------
        # Header
        # --------------------------------------------------

        for paragraph in (
            section.header.paragraphs
        ):

            text = paragraph.text.strip()

            if text:

                headers_footers.append(
                    text
                )

        # --------------------------------------------------
        # Footer
        # --------------------------------------------------

        for paragraph in (
            section.footer.paragraphs
        ):

            text = paragraph.text.strip()

            if text:

                headers_footers.append(
                    text
                )

    if headers_footers:

        sections.append(
            "\n".join(headers_footers)
        )

    # ======================================================
    # COMBINE PYTHON-DOCX CONTENT
    # ======================================================

    text = "\n\n".join(
        section
        for section in sections
        if section.strip()
    ).strip()

    # ======================================================
    # XML FALLBACK
    # ======================================================

    if not text:

        print(
            "python-docx extracted no text. "
            "Trying DOCX XML fallback...",
            flush=True
        )

        text = extract_docx_xml(
            file_content
        )

    # ======================================================
    # OCR FALLBACK
    # ======================================================

    if not text:

        print(
            "DOCX XML extraction returned no text. "
            "Trying OCR on embedded images...",
            flush=True
        )

        text = ocr_docx_images(
            file_content
        )

    # ======================================================
    # FINAL RESULT
    # ======================================================

    print(
        f"DOCX extraction completed: "
        f"{len(text)} characters",
        flush=True
    )

    return text


# ==========================================================
# GOOGLE DRIVE DOCX READER
# ==========================================================

def read_docx_from_drive(service, file_id):

    """
    Download a DOCX file from Google Drive
    and extract its text.
    """

    print(
        f"Downloading DOCX file "
        f"(ID: {file_id})",
        flush=True
    )

    request = service.files().get_media(
        fileId=file_id
    )

    file_content = request.execute()

    print(
        f"Downloaded DOCX file: "
        f"{len(file_content)} bytes",
        flush=True
    )

    # ------------------------------------------------------
    # Diagnostic inspection
    # ------------------------------------------------------

    inspect_docx_contents(
        file_content
    )

    # ------------------------------------------------------
    # Extract text
    # ------------------------------------------------------

    text = extract_docx_text(
        file_content
    )

    return text