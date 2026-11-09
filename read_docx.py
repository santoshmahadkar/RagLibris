"""Download DOCX files from Google Drive and extract paragraph/table text."""

from googleapiclient.http import MediaIoBaseDownload
from docx import Document
from io import BytesIO

def read_docx_from_drive(service, file_id):
    """Fetch a Drive DOCX and return its paragraph and table contents as text.

    The download is streamed into memory, then parsed by ``python-docx``.
    Non-empty paragraphs are kept in document order; table rows are rendered
    with cell values separated by ``" | "`` and appended after the paragraphs.

    Args:
        service: Authorized Google Drive API service.
        file_id: ID of the DOCX file to download.

    Returns:
        Extracted paragraph and table text joined with newline separators.

    Side effects:
        Downloads the file and prints transfer progress. Drive, download, and
        DOCX parsing errors are not caught and propagate to the caller.
    """

    # Download DOCX file from Google Drive
    request = service.files().get_media(
        fileId=file_id,
        supportsAllDrives=True
    )

    file_buffer = BytesIO()

    downloader = MediaIoBaseDownload(
        file_buffer,
        request
    )

    done = False

    while not done:
        status, done = downloader.next_chunk()
        print(f"Download progress: {int(status.progress() * 100)}%")

    # Move buffer position to beginning
    file_buffer.seek(0)

    # Read DOCX content
    doc = Document(file_buffer)

    extracted_text = []

    # Extract paragraphs
    for paragraph in doc.paragraphs:
        if paragraph.text.strip():
            extracted_text.append(paragraph.text)

    # Extract tables
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(
                cell.text.strip() for cell in row.cells
            )
            extracted_text.append(row_text)

    return "\n".join(extracted_text)