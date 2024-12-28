import gspread
from oauth2client.service_account import ServiceAccountCredentials


class GoogleSheetsClient:
    def __init__(self, google_sheets_key: str, worksheet_name: str, token_path: str):
        self.google_sheets_key = google_sheets_key
        self.worksheet_name = worksheet_name
        self.token_path = token_path
        self.client = self._get_google_sheets_client()
        self.sheet = self.client.open_by_key(self.google_sheets_key).worksheet(
            self.worksheet_name
        )

    def _get_google_sheets_client(self):
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            self.token_path, scope
        )
        return gspread.authorize(credentials)

    def write_row(self, row):
        self.sheet.append_row(row)

    def get_column_values(self) -> list[str]:
        return self.sheet.col_values(1)

    def insert_element_at(self, row: int, col: int, value):
        self.sheet.update_cell(row, col, value)

    def get_element_at(self, col: int, row: int):
        return self.sheet.cell(row, col).value

    def update_element_at(self, col: int, row: int, value):
        self.sheet.update_cell(row, col, f"{value}")

    def find(self, value: str) -> tuple[int, int]:
        cell = self.sheet.find(value)
        if cell:
            return cell.col, cell.row
        else:
            raise ValueError(f"Value '{value}' not found in the sheet")

    def find_last(self, value: str):
        cells = self.sheet.findall(value)
        if cells:
            last_cell = cells[-1]
            return last_cell.col, last_cell.row
        else:
            raise ValueError(f"Value '{value}' not found in the sheet")

    def insert_row_at(self, row_index: int, values: list):
        self.sheet.insert_row(values, row_index)

    def insert_column_at(self, col_index: int, values: list):
        self.sheet.insert_col(values, col_index)
