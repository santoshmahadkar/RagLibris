import os
import subprocess
import tempfile
from pathlib import Path


# ----------------------------------------------------------
# LibreOffice executable
# ----------------------------------------------------------

LIBREOFFICE_PATH = (
    r"C:\Program Files\LibreOffice\program\soffice.exe"
)


def convert_doc_to_docx(file_content, original_filename):
    """
    Convert a legacy .doc file into .docx format.

    Parameters
    ----------
    file_content : bytes
        Raw bytes downloaded from Google Drive.

    original_filename : str
        Original .doc filename.

    Returns
    -------
    bytes
        Converted .docx file content.

    Raises
    ------
    RuntimeError
        If LibreOffice is not available or conversion fails.
    """

    # ------------------------------------------------------
    # Check LibreOffice
    # ------------------------------------------------------

    if not os.path.exists(LIBREOFFICE_PATH):

        raise RuntimeError(
            f"LibreOffice not found at: "
            f"{LIBREOFFICE_PATH}"
        )

    # ------------------------------------------------------
    # Create temporary working directory
    # ------------------------------------------------------

    with tempfile.TemporaryDirectory(
        prefix="raglibris_doc_"
    ) as temp_dir:

        temp_dir_path = Path(temp_dir)

        # --------------------------------------------------
        # Prepare filename
        # --------------------------------------------------

        original_name = Path(
            original_filename
        ).name

        if not original_name.lower().endswith(".doc"):

            original_name = (
                f"{original_name}.doc"
            )

        doc_path = (
            temp_dir_path /
            original_name
        )

        # --------------------------------------------------
        # Write .doc file
        # --------------------------------------------------

        with open(
            doc_path,
            "wb"
        ) as file:

            file.write(file_content)

        print(
            f"Temporary DOC file created: "
            f"{doc_path}",
            flush=True
        )

        # --------------------------------------------------
        # LibreOffice conversion
        # --------------------------------------------------

        command = [
            LIBREOFFICE_PATH,
            "--headless",
            "--convert-to",
            "docx:MS Word 2007 XML",
            "--outdir",
            str(temp_dir_path),
            str(doc_path),
        ]

        print(
            "Converting DOC → DOCX...",
            flush=True
        )

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
        )

        print(
            f"LibreOffice output: "
            f"{result.stdout.strip()}",
            flush=True
        )

        if result.stderr.strip():

            print(
                f"LibreOffice error: "
                f"{result.stderr.strip()}",
                flush=True
            )

        # --------------------------------------------------
        # Find converted DOCX
        # --------------------------------------------------

        expected_docx = (
            temp_dir_path /
            f"{doc_path.stem}.docx"
        )

        if not expected_docx.exists():

            # Fallback: search for any generated DOCX
            converted_files = list(
                temp_dir_path.glob("*.docx")
            )

            if converted_files:

                expected_docx = (
                    converted_files[0]
                )

        # --------------------------------------------------
        # Validate conversion
        # --------------------------------------------------

        if not expected_docx.exists():

            raise RuntimeError(
                "DOC → DOCX conversion failed. "
                f"Return code: {result.returncode}. "
                f"stdout: {result.stdout}. "
                f"stderr: {result.stderr}"
            )

        # --------------------------------------------------
        # Read converted DOCX bytes
        # --------------------------------------------------

        with open(
            expected_docx,
            "rb"
        ) as file:

            docx_content = file.read()

        print(
            f"DOC → DOCX conversion completed. "
            f"DOCX size: {len(docx_content)} bytes",
            flush=True
        )

        return docx_content