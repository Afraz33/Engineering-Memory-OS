import os
from psycopg_pool import ConnectionPool

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://root@localhost:26257/engineering_memory?sslmode=disable"
)

pool = ConnectionPool(
    conninfo=DATABASE_URL,
    max_size=10
)

def get_conn():
    return pool.getconn()

def put_conn(conn):
    pool.putconn(conn)