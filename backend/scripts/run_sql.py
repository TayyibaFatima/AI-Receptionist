"""Run a .sql file against DATABASE_URL (no psql needed).

Usage (from the backend folder, venv active):
    python scripts/run_sql.py ../database/seed.sql
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import engine  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Usage: python scripts/run_sql.py <file.sql>")
    sql = Path(sys.argv[1]).read_text(encoding="utf-8")
    raw = engine.raw_connection()  # plain DB-API connection allows several statements at once
    try:
        cur = raw.cursor()
        cur.execute(sql)
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()
    print(f"Executed {sys.argv[1]} successfully.")


if __name__ == "__main__":
    main()
