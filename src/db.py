"""SQLAlchemy engine + small helpers. SQLite by default, Postgres via DATABASE_URL."""
from __future__ import annotations

import pandas as pd
from sqlalchemy import create_engine, text

from config import DATABASE_URL

_engine = create_engine(DATABASE_URL, future=True)


def get_engine():
    return _engine


def write_df(df: pd.DataFrame, table: str, if_exists: str = "replace") -> int:
    df.to_sql(table, _engine, if_exists=if_exists, index=False)
    return len(df)


def read_sql(query: str, **params) -> pd.DataFrame:
    with _engine.connect() as conn:
        return pd.read_sql(text(query), conn, params=params)


def table_exists(table: str) -> bool:
    from sqlalchemy import inspect

    return inspect(_engine).has_table(table)
