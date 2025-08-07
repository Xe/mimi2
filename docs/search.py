import os
from typing import List, Optional
import lancedb
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.path.join("docs", "var", "lancedb")
TABLE_NAME = "docs"


def connect_table():
    db = lancedb.connect(DB_PATH)
    return db.open_table(TABLE_NAME)


def search(query: str, limit: int = 5, select: Optional[List[str]] = None):
    """
    Vector search against the docs table created by import.py.
    Returns top-k rows including file_path, section, text and distance.
    """
    table = connect_table()
    sel = select or ["file_path", "section", "text"]
    res = (
        table.search(query)
        .select(sel)
        .limit(limit)
        .to_pandas()
    )
    return res


def cli():
    import argparse

    parser = argparse.ArgumentParser(description="Search LanceDB docs table")
    parser.add_argument("query", help="natural language query")
    parser.add_argument("--k", type=int, default=5, help="number of results")
    args = parser.parse_args()

    df = search(args.query, limit=args.k)
    if df is None or len(df) == 0:
        print("No results.")
        return
    for i, row in enumerate(df.itertuples(index=False), start=1):
        file_path = str(getattr(row, "file_path", ""))
        section = int(getattr(row, "section", 0))
        text_val = getattr(row, "text", "")
        text_str = text_val.decode("utf-8", errors="ignore") if isinstance(text_val, (bytes, bytearray)) else str(text_val)
        print(f"[{i}] {file_path}#section-{section}")
        print(text_str)
        print()


if __name__ == "__main__":
    cli()
