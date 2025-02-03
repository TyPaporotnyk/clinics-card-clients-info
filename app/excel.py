import gspread
from oauth2client.service_account import ServiceAccountCredentials

from app.utils import rate_limit, retry_request


class GoogleSheetsClient:
    def __init__(self, google_sheets_key: str, worksheet_name: str, token_path: str):
        self.google_sheets_key = google_sheets_key
        self.worksheet_name = worksheet_name
        self.token_path = token_path
        self.client = self._get_google_sheets_client()
        self.sheet = self.client.open_by_key(self.google_sheets_key).worksheet(self.worksheet_name)

    def _get_google_sheets_client(self):
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = ServiceAccountCredentials.from_json_keyfile_name(self.token_path, scope)
        return gspread.authorize(credentials)

    @retry_request()
    @rate_limit(max_requests=60, per_seconds=60)
    def write_row(self, row, position: int | None = None):
        if position:
            self.sheet.insert_row(row, position)
        else:
            self.sheet.insert_row(row)

    @retry_request()
    @rate_limit(max_requests=60, per_seconds=60)
    def get_column_values(self) -> list[str]:
        return self.sheet.col_values(1)

    @retry_request()
    @rate_limit(max_requests=60, per_seconds=60)
    def insert_element_at(self, row: int, col: int, value):
        self.sheet.update_cell(row, col, value)

    @retry_request()
    @rate_limit(max_requests=60, per_seconds=60)
    def get_element_at(self, col: int, row: int):
        return self.sheet.cell(row, col).value

    @retry_request()
    @rate_limit(max_requests=60, per_seconds=60)
    def update_element_at(self, col: int, row: int, value):
        self.sheet.update_cell(row, col, f"{value}")

    @retry_request()
    @rate_limit(max_requests=60, per_seconds=60)
    def find(self, value: str, in_column: int | None = None) -> tuple[int, int]:
        if in_column:
            cell = self.sheet.find(str(value), in_column=in_column)
        else:
            cell = self.sheet.find(str(value))

        if cell:
            return cell.col, cell.row
        else:
            raise ValueError(f"Value '{value}' not found in the sheet")

    @retry_request()
    @rate_limit(max_requests=60, per_seconds=60)
    def find_last(self, value: str):
        cells = self.sheet.findall(str(value))

        if cells:
            last_cell = cells[-1]
            return last_cell.col, last_cell.row
        else:
            raise ValueError(f"Value '{value}' not found in the sheet")

    @retry_request()
    @rate_limit(max_requests=60, per_seconds=60)
    def insert_row_at(self, row_index: int, values: list):
        self.sheet.insert_row(values, row_index)

    @retry_request()
    @rate_limit(max_requests=60, per_seconds=60)
    def insert_column_at(self, col_index: int, values: list):
        self.sheet.insert_col(values, col_index)

    @retry_request()
    @rate_limit(max_requests=60, per_seconds=60)
    def update_cells(self, updates: list[tuple[int, int, str]]):
        cells = []
        for row, col, value in updates:
            cell = self.sheet.cell(row, col)
            cell.value = str(value)
            cells.append(cell)

        self.sheet.update_cells(cells)

    @retry_request()
    @rate_limit(max_requests=60, per_seconds=60)
    def get_row_values(self, row: int) -> list[str]:
        return self.sheet.row_values(row)
