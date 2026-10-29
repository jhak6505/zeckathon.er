"""
app/db.py
─────────
Top-level entry for database utilities, exposing functions from app.data.db.
"""

from app.data.db import (
    DEFAULT_CSV_PATH,
    DEFAULT_DB_PATH,
    TABLE_NAME,
    DatabaseError,
    get_connection,
    get_records,
    get_records_df,
    get_summary,
    import_csv,
    init_db,
)

__all__ = [
    "DEFAULT_DB_PATH",
    "DEFAULT_CSV_PATH",
    "TABLE_NAME",
    "DatabaseError",
    "get_connection",
    "init_db",
    "import_csv",
    "get_records",
    "get_records_df",
    "get_summary",
]

