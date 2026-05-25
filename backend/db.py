import sqlite3
import os
import json
import uuid
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'issue_hunter.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create hunts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hunts (
            id TEXT PRIMARY KEY,
            repo_url TEXT NOT NULL,
            issues TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            report_md TEXT
        )
    ''')
    
    # Create logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hunt_id TEXT NOT NULL,
            log_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(hunt_id) REFERENCES hunts(id)
        )
    ''')
    
    conn.commit()
    conn.close()

def create_hunt(repo_url: str, issues: list, provider: str, model: str) -> str:
    hunt_id = str(uuid.uuid4())
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO hunts (id, repo_url, issues, provider, model, status)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (hunt_id, repo_url, json.dumps(issues), provider, model, 'running'))
    conn.commit()
    conn.close()
    return hunt_id

def insert_log(hunt_id: str, log_text: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO logs (hunt_id, log_text)
        VALUES (?, ?)
    ''', (hunt_id, log_text))
    conn.commit()
    conn.close()

def update_hunt_status(hunt_id: str, status: str, report_md: str = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if report_md is not None:
        cursor.execute('''
            UPDATE hunts SET status = ?, completed_at = CURRENT_TIMESTAMP, report_md = ?
            WHERE id = ?
        ''', (status, report_md, hunt_id))
    else:
        cursor.execute('''
            UPDATE hunts SET status = ?, completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (status, hunt_id))
    conn.commit()
    conn.close()

def get_hunts():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM hunts ORDER BY created_at DESC')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_hunt_logs(hunt_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT log_text FROM logs WHERE hunt_id = ? ORDER BY id ASC', (hunt_id,))
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]
