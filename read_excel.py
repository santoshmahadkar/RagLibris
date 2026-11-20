from io import BytesIO
from openpyxl import load_workbook


def extract_excel_text(file_content):
    workbook = load_workbook(
        filename=BytesIO(file_content),
        data_only=True
    )

    extracted_text = []

    for sheet in workbook.worksheets:
        extracted_text.append(f"Sheet: {sheet.title}")

        for row in sheet.iter_rows(values_only=True):
            values = []

            for value in row:
                if value is not None:
                    values.append(str(value))

            if values:
                extracted_text.append(" | ".join(values))

    return "\n".join(extracted_text).strip()


def read_excel_from_drive(service, file_id):
    request = service.files().get_media(fileId=file_id)
    file_content = request.execute()

    return extract_excel_text(file_content)