# src/utils/db.py
import sqlite3
import json
from typing import Dict, Optional
from src.utils.logger import get_logger

log = get_logger(__name__)

class Database:
    def __init__(self, db_path: str = "meteora_bot.db"):
        self.conn = sqlite3.connect(db_path)
        self._init_tables()

    def _init_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS coin_states (
                coin_id TEXT PRIMARY KEY,
                stage INTEGER DEFAULT 0,
                current_ratio REAL DEFAULT 0,
                last_checked TIMESTAMP,
                price_history TEXT
            )
        ''')
        self.conn.commit()

    def get_coin_state(self, coin_id: str) -> Optional[Dict]:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT stage, current_ratio, price_history 
            FROM coin_states 
            WHERE coin_id = ?
        ''', (coin_id,))
        row = cursor.fetchone()
        if row:
            return {
                "stage": row[0],
                "current_ratio": row[1],
                "price_history": json.loads(row[2]) if row[2] else []
            }
        return None

    def update_coin_state(self, coin_id: str, stage: int, current_ratio: float, price_history: list):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO coin_states 
            (coin_id, stage, current_ratio, price_history)
            VALUES (?, ?, ?, ?)
        ''', (coin_id, stage, current_ratio, json.dumps(price_history)))
        self.conn.commit()

      
    def clear_all(self):
        """Удаляет все записи из таблицы coin_states."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM coin_states")
        self.conn.commit()
        log.info("База данных очищена.")
       

    def reset_coin_state(self, coin_id: str):
        cursor = self.conn.cursor()
        cursor.execute('''
            DELETE FROM coin_states 
            WHERE coin_id = ?
        ''', (coin_id,))
        self.conn.commit()