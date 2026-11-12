from io import BytesIO
from openpyxl import load_workbook


def read_excel_from_drive(service, file_id):

    print(
        f"Downloading Excel file (ID: {file_id})",
        flush=True
    )

    request = service.files().get_media(fileId=file_id)

    file_content = request.execute()

    print(
        f"Downloaded Excel file: {len(file_content)} bytes",
        flush=True
    )

    workbook = load_workbook(
        filename=BytesIO(file_content),
        read_only=True,
        data_only=True
    )

    sheets = []

    for worksheet in workbook.worksheets:

        rows = []

        for row in worksheet.iter_rows(values_only=True):

            values = [
                str(value).strip()
                for value in row
                if value is not None
            ]

            if values:
                rows.append(" | ".join(values))

        if rows:

            sheet_text = (
                f"Sheet: {worksheet.title}\n\n"
                + "\n".join(rows)
            )

            sheets.append(sheet_text)

    workbook.close()

    text = "\n\n".join(sheets).strip()

    print(
        f"Excel extraction completed: "
        f"{len(text)} characters",
        flush=True
    )

    return text