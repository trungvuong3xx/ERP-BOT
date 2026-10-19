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
            return []

    def get_daily_stats(self, limit_days=7):
        """Lấy thống kê số lượng thành công/thất bại theo ngày."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT 
                        run_date,
                        SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as success_count,
                        SUM(CASE WHEN status != 'SUCCESS' THEN 1 ELSE 0 END) as fail_count
                    FROM run_logs
                    GROUP BY run_date
                    ORDER BY run_date DESC
                    LIMIT ?
                ''', (limit_days,))
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Lỗi lấy thống kê theo ngày: {e}")
            return []

    def get_total_stats(self):
        """Lấy tổng số lượng xử lý từ trước đến nay."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT 
                        SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as total_success,
                        SUM(CASE WHEN status != 'SUCCESS' THEN 1 ELSE 0 END) as total_fail
                    FROM run_logs
                ''')
                row = cursor.fetchone()
                return (row[0] or 0, row[1] or 0)
        except Exception as e:
            logger.error(f"Lỗi lấy tổng thống kê: {e}")
            return (0, 0)
