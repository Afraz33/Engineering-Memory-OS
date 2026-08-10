from psycopg_pool import ConnectionPool

pool = ConnectionPool(
    conninfo="postgresql://root@localhost:26257/ai_system?sslmode=disable",
    max_size=10
)

def get_conn():
    return pool.getconn()

def put_conn(conn):
    pool.putconn(conn)