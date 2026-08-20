import sqlite3
import os
import logging
from datetime import datetime

logger = logging.getLogger("ERPAutomation.Database")

class BotDatabase:
    def __init__(self, db_path="erp_history.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Bảng lưu lịch sử từng mã sản phẩm
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS run_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        run_date TEXT NOT NULL,
                        sheet_name TEXT,
                        category TEXT,
                        item_code TEXT,
                        status TEXT,
                        message TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.commit()
        except Exception as e:
            logger.error(f"Lỗi khởi tạo database: {e}")

    def log_item(self, run_date: str, sheet_name: str, category: str, item_code: str, status: str, message: str = ""):
        """Ghi nhận lịch sử chạy cho 1 mã."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO run_logs (run_date, sheet_name, category, item_code, status, message)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (run_date, sheet_name, category, item_code, status, message))
                conn.commit()
        except Exception as e:
            logger.error(f"Lỗi ghi log DB: {e}")

    def check_if_success_today(self, run_date: str, sheet_name: str, item_code: str) -> bool:
        """Kiểm tra xem mã này đã được nhập thành công trong ngày hôm nay chưa (Phục vụ Smart Resume)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT 1 FROM run_logs 
                    WHERE run_date = ? AND sheet_name = ? AND item_code = ? AND status = 'SUCCESS'
                    LIMIT 1
                ''', (run_date, sheet_name, item_code))
                result = cursor.fetchone()
                return bool(result)
        except Exception as e:
            logger.error(f"Lỗi kiểm tra DB: {e}")
            return False

    def get_run_history(self, limit=100):
        """Lấy lịch sử chạy gần đây."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT timestamp, run_date, sheet_name, item_code, status, message
                    FROM run_logs
                    ORDER BY id DESC
                    LIMIT ?
                ''', (limit,))
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Lỗi truy xuất lịch sử DB: {e}")
            return []
