import sqlite3
import json
import os
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "council.db")

def init_db(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            original_question TEXT NOT NULL,
            neutral_question TEXT NOT NULL,
            selected_agent_ids TEXT NOT NULL,
            agent_outputs TEXT NOT NULL,
            verdict TEXT,
            model_config_used TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_session(
    session_id: str,
    original_question: str,
    neutral_question: str,
    selected_agent_ids: List[str],
    agent_outputs: Dict[str, Any],
    verdict: Optional[Dict[str, Any]] = None,
    model_config_used: Optional[Dict[str, Any]] = None,
    db_path: str = DB_PATH
):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO sessions 
        (id, original_question, neutral_question, selected_agent_ids, agent_outputs, verdict, model_config_used)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id,
        original_question,
        neutral_question,
        json.dumps(selected_agent_ids),
        json.dumps(agent_outputs),
        json.dumps(verdict) if verdict else None,
        json.dumps(model_config_used) if model_config_used else None
    ))
    conn.commit()
    conn.close()

def get_session(session_id: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, created_at, original_question, neutral_question, selected_agent_ids, agent_outputs, verdict, model_config_used FROM sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "created_at": row[1],
        "original_question": row[2],
        "neutral_question": row[3],
        "selected_agent_ids": json.loads(row[4]),
        "agent_outputs": json.loads(row[5]),
        "verdict": json.loads(row[6]) if row[6] else None,
        "model_config_used": json.loads(row[7]) if row[7] else None
    }

def list_sessions(limit: int = 50, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, created_at, original_question, neutral_question, selected_agent_ids, verdict 
        FROM sessions 
        ORDER BY created_at DESC 
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    results = []
    for r in rows:
        verdict_obj = json.loads(r[5]) if r[5] else None
        results.append({
            "id": r[0],
            "created_at": r[1],
            "original_question": r[2],
            "neutral_question": r[3],
            "selected_agent_ids": json.loads(r[4]),
            "verdict": verdict_obj
        })
    return results
