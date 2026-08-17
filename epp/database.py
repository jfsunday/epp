"""Built-in SQLite database for E++."""

from __future__ import annotations

import sqlite3

from .builtins import format_value
from .errors import EppRuntimeError


# Map E++ comparison operators to SQL
_OP_MAP = {
    "eq": "=",
    "ne": "!=",
    "gt": ">",
    "lt": "<",
    "ge": ">=",
    "le": "<=",
}


class EppDatabase:
    """SQLite database wrapper for E++."""

    def __init__(self):
        self.conn: sqlite3.Connection | None = None
        self._tables: dict[str, list[str]] = {}  # table_name -> column names

    def open(self, name: str, line: int) -> None:
        if self.conn is not None:
            self.conn.close()
        # Use .db extension if not provided
        if not name.endswith(".db"):
            name = name + ".db"
        self.conn = sqlite3.connect(name, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        # Load existing table schemas
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        for row in cursor:
            tbl = row[0]
            info = self.conn.execute(f"PRAGMA table_info({tbl})").fetchall()
            self._tables[tbl] = [col[1] for col in info]

    def close(self, line: int) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def _require_open(self, line: int) -> sqlite3.Connection:
        if self.conn is None:
            raise EppRuntimeError("no database is open", line)
        return self.conn

    def create_table(self, table_name: str, columns: list[str], line: int) -> None:
        conn = self._require_open(line)
        col_defs = ", ".join(f'"{c}" TEXT' for c in columns)
        conn.execute(f'CREATE TABLE IF NOT EXISTS "{table_name}" ({col_defs})')
        conn.commit()
        self._tables[table_name] = columns

    def insert(self, table_name: str, values: list[object], line: int) -> None:
        conn = self._require_open(line)
        if table_name not in self._tables:
            raise EppRuntimeError(f"table '{table_name}' does not exist", line)
        cols = self._tables[table_name]
        if len(values) != len(cols):
            raise EppRuntimeError(
                f"table '{table_name}' has {len(cols)} columns but got {len(values)} values",
                line,
            )
        placeholders = ", ".join("?" for _ in values)
        sql_values = [format_value(v) for v in values]
        conn.execute(f'INSERT INTO "{table_name}" VALUES ({placeholders})', sql_values)
        conn.commit()

    def select(
        self,
        table_name: str,
        where_col: str | None,
        where_op: str | None,
        where_val: object | None,
        line: int,
    ) -> list[dict[str, object]]:
        conn = self._require_open(line)
        if table_name not in self._tables:
            raise EppRuntimeError(f"table '{table_name}' does not exist", line)

        sql = f'SELECT * FROM "{table_name}"'
        params: list[object] = []
        if where_col is not None and where_op is not None:
            sql_op = _OP_MAP.get(where_op, "=")
            sql += f' WHERE "{where_col}" {sql_op} ?'
            params.append(format_value(where_val))

        cursor = conn.execute(sql, params)
        cols = self._tables[table_name]
        results: list[dict[str, object]] = []
        for row in cursor:
            d: dict[str, object] = {}
            for i, col in enumerate(cols):
                val = row[i]
                # Try to convert to number
                if isinstance(val, str):
                    try:
                        if "." in val:
                            val = float(val)
                        else:
                            val = float(int(val))
                    except ValueError:
                        pass
                d[col] = val
            results.append(d)
        return results

    def update(
        self,
        table_name: str,
        set_col: str,
        set_val: object,
        where_col: str,
        where_op: str,
        where_val: object,
        line: int,
    ) -> None:
        conn = self._require_open(line)
        if table_name not in self._tables:
            raise EppRuntimeError(f"table '{table_name}' does not exist", line)
        sql_op = _OP_MAP.get(where_op, "=")
        conn.execute(
            f'UPDATE "{table_name}" SET "{set_col}" = ? WHERE "{where_col}" {sql_op} ?',
            [format_value(set_val), format_value(where_val)],
        )
        conn.commit()

    def delete(
        self,
        table_name: str,
        where_col: str,
        where_op: str,
        where_val: object,
        line: int,
    ) -> None:
        conn = self._require_open(line)
        if table_name not in self._tables:
            raise EppRuntimeError(f"table '{table_name}' does not exist", line)
        sql_op = _OP_MAP.get(where_op, "=")
        conn.execute(
            f'DELETE FROM "{table_name}" WHERE "{where_col}" {sql_op} ?',
            [format_value(where_val)],
        )
        conn.commit()
