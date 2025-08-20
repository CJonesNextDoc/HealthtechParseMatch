# tools/ensure_db.py
import anyio
from app.db_manage import ensure_database

if __name__ == "__main__":
    anyio.run(ensure_database)
