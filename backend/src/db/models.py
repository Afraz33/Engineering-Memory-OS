from db.session import get_conn
from typing import Optional, List, Dict


# --- MESSAGES ---

def create_message(session_id: str, role: str, content: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO messages (session_id, role, content)
                VALUES (%s, %s, %s)
                RETURNING id;
                """,
                (session_id, role, content),
            )
            return cur.fetchone()["id"]


def get_messages(session_id: str, limit: int = 50) -> List[Dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM messages
                WHERE session_id = %s
                ORDER BY created_at DESC
                LIMIT %s;
                """,
                (session_id, limit),
            )
            return cur.fetchall()


# --- DOCUMENTS ---

def create_document(content: str, metadata: Optional[dict] = None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (content, metadata)
                VALUES (%s, %s)
                RETURNING id;
                """,
                (content, metadata),
            )
            return cur.fetchone()["id"]


# --- EMBEDDINGS ---

def insert_embedding(content: str, vector: list):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO embeddings (content, vector)
                VALUES (%s, %s)
                RETURNING id;
                """,
                (content, vector),
            )
            return cur.fetchone()["id"]


def semantic_search(
    query_vec: list,
    workspace_id: str,
    k: int = 5
):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT m.*, e.vector <#> %s AS dist
                FROM memories m
                JOIN embeddings e ON e.memory_id = m.id
                WHERE m.workspace_id = %s
                ORDER BY dist ASC
                LIMIT %s;
                """,
                (query_vec, workspace_id, k),
            )
            return cur.fetchall()