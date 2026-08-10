import os

from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

# Loaded here rather than relying on app.main: this module is imported *by* the
# routers, which app.main imports before it calls load_dotenv() — so reading the
# environment at that point would miss .env entirely and silently fall back to
# localhost. load_dotenv is idempotent, so calling it twice costs nothing.
load_dotenv()

# The real connection string lives in backend/.env, which is gitignored. Never
# inline a cloud credential here — this file is tracked, so a password in the
# default would be committed and would need rotating.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://root@localhost:26257/engineering_memory?sslmode=disable"
)

# dict_row so callers can index rows by column name (`row["id"]`), which is what
# every call site already assumes.
pool = ConnectionPool(
    conninfo=DATABASE_URL,
    max_size=10,
    kwargs={"row_factory": dict_row},
)

def get_conn():
    """A pooled connection, as a context manager.

    `with get_conn() as conn:` checks the connection back into the pool on exit
    and commits (or rolls back) the transaction. Do not call `pool.getconn()`
    here — that hands out a raw connection whose `with` block closes it instead
    of returning it, which drains the pool after ten requests.
    """
    return pool.connection()
