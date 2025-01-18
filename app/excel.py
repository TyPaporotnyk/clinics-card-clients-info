import time

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from app.utils import retry_request


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
    def write_row(self, row):
        all_values = self.sheet.col_values(3)
        last_row_index = len(all_values)
        self.sheet.insert_row(row, last_row_index + 1)
        time.sleep(1)

    @retry_request()
    def get_column_values(self) -> list[str]:
        value = self.sheet.col_values(1)
        time.sleep(1)
        return value

    @retry_request()
    def insert_element_at(self, row: int, col: int, value):
        self.sheet.update_cell(row, col, value)
        time.sleep(1)

    @retry_request()
    def get_element_at(self, col: int, row: int):
        value = self.sheet.cell(row, col).value
        time.sleep(1)
        return value

    @retry_request()
    def update_element_at(self, col: int, row: int, value):
        self.sheet.update_cell(row, col, f"{value}")
        time.sleep(1)

    @retry_request()
    def find(self, value: str) -> tuple[int, int]:
        cell = self.sheet.find(value)
        time.sleep(1)

        if cell:
            return cell.col, cell.row
        else:
            raise ValueError(f"Value '{value}' not found in the sheet")

    @retry_request()
    def find_last(self, value: str):
        cells = self.sheet.findall(value)
        time.sleep(1)

        if cells:
            last_cell = cells[-1]
            return last_cell.col, last_cell.row
        else:
            raise ValueError(f"Value '{value}' not found in the sheet")

    @retry_request()
    def insert_row_at(self, row_index: int, values: list):
        self.sheet.insert_row(values, row_index)
        time.sleep(1)

    @retry_request()
    def insert_column_at(self, col_index: int, values: list):
        self.sheet.insert_col(values, col_index)
        time.sleep(1)
