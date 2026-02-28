"""Tests for Excel/CSV parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.src.ingestion.excel_parser import parse_csv_file, parse_excel_file

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class TestParseExcelFile:
    def test_parses_xlsx_rows(self, tmp_path: Path) -> None:
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(["metric_name", "metric_value", "unit", "period"])
        ws.append(["Revenue", 1500000, "USD", "2025-Q4"])
        ws.append(["Headcount", 250, "people", "2025-Q4"])
        filepath = tmp_path / "kpis.xlsx"
        wb.save(filepath)

        rows = parse_excel_file(filepath)
        assert len(rows) == 2
        assert rows[0]["metric_name"] == "Revenue"
        assert rows[0]["metric_value"] == 1500000
        assert rows[1]["metric_name"] == "Headcount"

    def test_returns_list_of_parsed_row_dicts(self, tmp_path: Path) -> None:
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(["name", "value"])
        ws.append(["test", 42])
        filepath = tmp_path / "simple.xlsx"
        wb.save(filepath)

        rows = parse_excel_file(filepath)
        assert isinstance(rows, list)
        assert isinstance(rows[0], dict)
        assert "name" in rows[0]

    def test_empty_spreadsheet_returns_empty_list(self, tmp_path: Path) -> None:
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(["col_a", "col_b"])
        filepath = tmp_path / "empty.xlsx"
        wb.save(filepath)

        rows = parse_excel_file(filepath)
        assert rows == []

    def test_skips_rows_with_all_none_values(self, tmp_path: Path) -> None:
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(["name", "value"])
        ws.append([None, None])
        ws.append(["real", 99])
        filepath = tmp_path / "sparse.xlsx"
        wb.save(filepath)

        rows = parse_excel_file(filepath)
        assert len(rows) == 1
        assert rows[0]["name"] == "real"

    def test_raises_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            parse_excel_file(Path("/nonexistent/file.xlsx"))


class TestParseCsvFile:
    def test_parses_csv_rows(self, tmp_path: Path) -> None:
        csv_content = "metric_name,metric_value,unit\nRevenue,1500000,USD\nHeadcount,250,people\n"
        filepath = tmp_path / "data.csv"
        filepath.write_text(csv_content, encoding="utf-8")

        rows = parse_csv_file(filepath)
        assert len(rows) == 2
        assert rows[0]["metric_name"] == "Revenue"
        assert rows[0]["metric_value"] == "1500000"

    def test_empty_csv_returns_empty_list(self, tmp_path: Path) -> None:
        filepath = tmp_path / "empty.csv"
        filepath.write_text("col_a,col_b\n", encoding="utf-8")

        rows = parse_csv_file(filepath)
        assert rows == []

    def test_csv_raises_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            parse_csv_file(Path("/nonexistent/file.csv"))

    def test_csv_handles_quoted_fields(self, tmp_path: Path) -> None:
        csv_content = 'name,description\n"Widget A","A nice, shiny widget"\n'
        filepath = tmp_path / "quoted.csv"
        filepath.write_text(csv_content, encoding="utf-8")

        rows = parse_csv_file(filepath)
        assert len(rows) == 1
        assert rows[0]["description"] == "A nice, shiny widget"
