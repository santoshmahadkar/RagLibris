from io import BytesIO
from zipfile import BadZipFile
from docx import Document


def read_docx_from_drive(service, file_id):

    print(
        f"Downloading DOCX file (ID: {file_id})",
        flush=True
    )

    request = service.files().get_media(fileId=file_id)

    file_content = request.execute()

    print(
        f"Downloaded DOCX file: {len(file_content)} bytes",
        flush=True
    )

    file_buffer = BytesIO(file_content)

    try:

        doc = Document(file_buffer)

    except (BadZipFile, KeyError, ValueError) as exc:

        print(
            f"WARNING: Unable to read DOCX file. "
            f"Skipping file.",
            flush=True
        )

        print(
            f"Reason: {type(exc).__name__}: {exc}",
            flush=True
        )

        return ""

    sections = []

    # --------------------------------------------------
    # Extract normal paragraphs
    # --------------------------------------------------

    paragraphs = []

    for paragraph in doc.paragraphs:

        text = paragraph.text.strip()

        if text:
            paragraphs.append(text)

    if paragraphs:

        sections.append(
            "\n".join(paragraphs)
        )

    # --------------------------------------------------
    # Extract tables
    # --------------------------------------------------

    tables = []

    for table in doc.tables:

        rows = []

        for row in table.rows:

            cells = []

            for cell in row.cells:

                cell_text = cell.text.strip()

                if cell_text:
                    cells.append(cell_text)

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

    # --------------------------------------------------
    # Extract headers and footers
    # --------------------------------------------------

    headers_footers = []

    for section in doc.sections:

        # Header
        for paragraph in section.header.paragraphs:

            text = paragraph.text.strip()

            if text:
                headers_footers.append(text)

        # Footer
        for paragraph in section.footer.paragraphs:

            text = paragraph.text.strip()

            if text:
                headers_footers.append(text)

    if headers_footers:

        sections.append(
            "\n".join(headers_footers)
        )

    # --------------------------------------------------
    # Combine extracted content
    # --------------------------------------------------

    text = "\n\n".join(
        section
        for section in sections
        if section.strip()
    ).strip()

    print(
        f"DOCX extraction completed: "
        f"{len(text)} characters",
        flush=True
    )

    return text