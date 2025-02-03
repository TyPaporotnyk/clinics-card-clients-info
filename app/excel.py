import gspread
from gspread.cell import Cell
from oauth2client.service_account import ServiceAccountCredentials

from app.utils import rate_limit, retry_request


class GoogleSheetsClient:
    def __init__(self, google_sheets_key: str, worksheet_name: str, token_path: str):
        self.google_sheets_key = google_sheets_key
        self.worksheet_name = worksheet_name
        self.token_path = token_path
        self.client = self._get_google_sheets_client()
        self.sheet = self.client.open_by_key(self.google_sheets_key).worksheet(self.worksheet_name)

        # Кеш для значений
        self._row_cache = {}
        self._col_cache = {}
        self._cell_cache = {}
        self._find_cache = {}

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
            # Инвалидируем кеш для затронутых строк
            self._row_cache.clear()
            self._cell_cache.clear()
        else:
            self.sheet.insert_row(row)
            self._row_cache.clear()
            self._cell_cache.clear()

    @retry_request()
    @rate_limit(max_requests=60, per_seconds=60)
    def get_column_values(self) -> list[str]:
        col_key = 1  # Первая колонка
        if col_key not in self._col_cache:
            self._col_cache[col_key] = self.sheet.col_values(1)
        return self._col_cache[col_key]

    @retry_request()
    @rate_limit(max_requests=60, per_seconds=60)
    def get_row_values(self, row: int) -> list[str]:
        if row not in self._row_cache:
            self._row_cache[row] = self.sheet.row_values(row)
        return self._row_cache[row]

    @retry_request()
    @rate_limit(max_requests=60, per_seconds=60)
    def update_cells(self, updates: list[tuple[int, int, str]]):
        cells = []
        for row, col, value in updates:
            cell = Cell(row=row, col=col, value=str(value))
            cells.append(cell)

            # Обновляем кеш
            cache_key = (row, col)
            self._cell_cache[cache_key] = value

            # Инвалидируем строки и колонки, которые были изменены
            if row in self._row_cache:
                del self._row_cache[row]
            if col in self._col_cache:
                del self._col_cache[col]

        # Обновляем все ячейки одним запросом
        self.sheet.update_cells(cells)

    @retry_request()
    @rate_limit(max_requests=60, per_seconds=60)
    def find(self, value: str, in_column: int | None = None) -> tuple[int, int]:
        cache_key = (value, in_column)
        if cache_key not in self._find_cache:
            if in_column:
                cell = self.sheet.find(str(value), in_column=in_column)
            else:
                cell = self.sheet.find(str(value))

            if cell:
                self._find_cache[cache_key] = (cell.col, cell.row)
            else:
                raise ValueError(f"Value '{value}' not found in the sheet")

        return self._find_cache[cache_key]

    @retry_request()
    @rate_limit(max_requests=60, per_seconds=60)
    def find_last(self, value: str):
        cache_key = f"last_{value}"
        if cache_key not in self._find_cache:
            cells = self.sheet.findall(str(value))

            if cells:
                last_cell = cells[-1]
                self._find_cache[cache_key] = (last_cell.col, last_cell.row)
            else:
                raise ValueError(f"Value '{value}' not found in the sheet")

        return self._find_cache[cache_key]

    def clear_cache(self):
        """Очищает все кеши"""
        self._row_cache.clear()
        self._col_cache.clear()
        self._cell_cache.clear()
        self._find_cache.clear()
