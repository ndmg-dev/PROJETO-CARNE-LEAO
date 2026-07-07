"""
Módulo de banco de dados SQLite.
Cacheia os resultados da extração para evitar reprocessamento
e permite edição manual dos campos pela interface web.
"""
import sqlite3
import logging

logger = logging.getLogger(__name__)


def get_connection(db_path):
    """Cria e retorna uma conexão com o banco de dados."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path):
    """Cria a tabela de documentos caso não exista."""
    conn = get_connection(db_path)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT NOT NULL,
            month_num TEXT NOT NULL,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL UNIQUE,
            description TEXT,
            date TEXT,
            value REAL,
            status TEXT DEFAULT 'pending',
            confidence TEXT DEFAULT '',
            observation TEXT DEFAULT '',
            processed_at TEXT DEFAULT '',
            manually_edited INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()
    logger.info(f"Database inicializado em: {db_path}")


def upsert_document(db_path, doc):
    """
    Insere ou atualiza um documento.
    Se o documento já foi editado manualmente, preserva data e valor do usuário.
    """
    conn = get_connection(db_path)
    conn.execute('''
        INSERT INTO documents
            (month, month_num, filename, filepath, description,
             date, value, status, confidence, observation, processed_at, manually_edited)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        ON CONFLICT(filepath) DO UPDATE SET
            date = CASE WHEN documents.manually_edited = 1
                        THEN documents.date ELSE excluded.date END,
            value = CASE WHEN documents.manually_edited = 1
                         THEN documents.value ELSE excluded.value END,
            status = excluded.status,
            confidence = excluded.confidence,
            observation = excluded.observation,
            processed_at = excluded.processed_at
    ''', (
        doc['month'], doc['month_num'], doc['filename'], doc['filepath'],
        doc.get('description', ''), doc.get('date'), doc.get('value'),
        doc.get('status', 'pending'), doc.get('confidence', ''),
        doc.get('observation', ''), doc.get('processed_at', '')
    ))
    conn.commit()
    conn.close()


def get_documents(db_path, month=None, status=None):
    """Retorna documentos com filtros opcionais de mês e status."""
    conn = get_connection(db_path)
    query = "SELECT * FROM documents WHERE 1=1"
    params = []

    if month:
        query += " AND month_num = ?"
        params.append(month)
    if status and status != 'all':
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY month_num, date, filename"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_document(db_path, doc_id):
    """Retorna um documento pelo ID."""
    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT * FROM documents WHERE id = ?", (doc_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_document(db_path, doc_id, date=None, value=None):
    """Atualiza manualmente a data e/ou valor de um documento."""
    conn = get_connection(db_path)
    updates = []
    params = []

    if date is not None:
        updates.append("date = ?")
        params.append(date if date != '' else None)
    if value is not None:
        updates.append("value = ?")
        params.append(float(value) if value != '' else None)

    if updates:
        updates.append("manually_edited = 1")
        updates.append("status = 'ok'")
        query = f"UPDATE documents SET {', '.join(updates)} WHERE id = ?"
        params.append(doc_id)
        conn.execute(query, params)
        conn.commit()

    conn.close()


def get_stats(db_path):
    """Retorna estatísticas de processamento."""
    conn = get_connection(db_path)
    total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    ok = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE status = 'ok'"
    ).fetchone()[0]
    review = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE status = 'review'"
    ).fetchone()[0]
    error = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE status = 'error'"
    ).fetchone()[0]
    pending = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE status = 'pending'"
    ).fetchone()[0]
    conn.close()

    return {
        "total": total,
        "processed": total - pending,
        "ok": ok,
        "review": review,
        "error": error,
        "pending": pending
    }


def clear_documents(db_path):
    """Remove todos os documentos do banco."""
    conn = get_connection(db_path)
    conn.execute("DELETE FROM documents")
    conn.commit()
    conn.close()
