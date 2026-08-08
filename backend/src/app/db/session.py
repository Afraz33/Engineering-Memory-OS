from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "cockroachdb+psycopg://root@cockroach:26257/knowledgebase?sslmode=disable"

engine = create_engine(
    DATABASE_URL,
    echo=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)