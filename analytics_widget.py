from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QFont, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from database import BotDatabase

class BarChartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = [] # List of (date, success, fail)
        self.setMinimumHeight(300)

    def set_data(self, data):
        self.data = data[::-1] # Reverse to show chronological left to right
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect()
        painter.fillRect(rect, QColor("#1e1e2e"))
        
        if not self.data:
            painter.setPen(QColor("#f8f8f2"))
            painter.drawText(rect, Qt.AlignCenter, "Chưa có dữ liệu thống kê")
            return
            
        margin = 40
        width = rect.width() - 2 * margin
        height = rect.height() - 2 * margin
        
        # Max value for scaling
        max_val = max([success + fail for _, success, fail in self.data])
        if max_val == 0: max_val = 1
        
        bar_width = width / max(len(self.data), 1) * 0.6
        spacing = width / max(len(self.data), 1)
        
        painter.setPen(QPen(QColor("#44475a"), 1, Qt.DashLine))
        for i in range(5):
            y = margin + i * (height / 4)
            painter.drawLine(margin, int(y), rect.width() - margin, int(y))
            val = int(max_val * (4 - i) / 4)
            painter.setPen(QColor("#6272a4"))
            painter.drawText(5, int(y) + 5, f"{val}")
            painter.setPen(QPen(QColor("#44475a"), 1, Qt.DashLine))

        for i, (date, success, fail) in enumerate(self.data):
            x = margin + i * spacing + (spacing - bar_width) / 2
            
            # Scale heights
            h_success = (success / max_val) * height
            h_fail = (fail / max_val) * height
            
            # Draw fail bar (on top)
            y_fail = rect.height() - margin - h_success - h_fail
            painter.fillRect(QRectF(x, y_fail, bar_width, h_fail), QColor("#ff5555"))
            
            # Draw success bar
            y_success = rect.height() - margin - h_success
            painter.fillRect(QRectF(x, y_success, bar_width, h_success), QColor("#50fa7b"))
            
            # Draw date text
            painter.setPen(QColor("#f8f8f2"))
            date_short = date[-5:] if len(date) >= 5 else date
            painter.drawText(QRectF(x, rect.height() - margin + 5, bar_width, 20), Qt.AlignCenter, date_short)

class AnalyticsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = BotDatabase()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(20)
        
        # Tiêu đề
        lbl_title = QLabel("Báo Cáo Năng Suất & Thời Gian Tiết Kiệm")
        lbl_title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        lbl_title.setStyleSheet("color: #f8f8f2;")
        self.layout.addWidget(lbl_title)
        
        # Summary Area
        self.summary_layout = QHBoxLayout()
        
        # Card 1
        card1 = QFrame()
        card1.setStyleSheet("background-color: #282a36; border-radius: 8px; border: 1px solid #44475a; padding: 15px;")
        l1 = QVBoxLayout(card1)
        
        lbl_c1 = QLabel("✅ Tổng Số Dòng Thành Công")
        lbl_c1.setStyleSheet("color: #F8FAFC; border: none; font-weight: bold; font-size: 14px;")
        l1.addWidget(lbl_c1)
        
        self.lbl_total_success = QLabel("0")
        self.lbl_total_success.setStyleSheet("font-size: 28px; font-weight: bold; color: #50fa7b; border: none;")
        l1.addWidget(self.lbl_total_success)
        self.summary_layout.addWidget(card1)
        
        # Card 2
        card2 = QFrame()
        card2.setStyleSheet("background-color: #282a36; border-radius: 8px; border: 1px solid #44475a; padding: 15px;")
        l2 = QVBoxLayout(card2)
        
        lbl_c2 = QLabel("⏱️ Thời Gian Tiết Kiệm (ước tính)")
        lbl_c2.setStyleSheet("color: #F8FAFC; border: none; font-weight: bold; font-size: 14px;")
        l2.addWidget(lbl_c2)
        
        self.lbl_time_saved = QLabel("0 giờ")
        self.lbl_time_saved.setStyleSheet("font-size: 28px; font-weight: bold; color: #8be9fd; border: none;")
        l2.addWidget(self.lbl_time_saved)
        self.summary_layout.addWidget(card2)
        
        self.layout.addLayout(self.summary_layout)
        
        # Ghi chú tính thời gian
        lbl_note = QLabel("* Ước tính: Tính từ lúc bắt đầu nhập tay (15s) + mỗi dòng (15s). Trung bình ~ 20 giây/dòng làm việc.")
        lbl_note.setStyleSheet("color: #6272a4; font-style: italic;")
        self.layout.addWidget(lbl_note)
        
        # Chart Area
        lbl_chart_title = QLabel("Biểu đồ số dòng nhập thành công (Xanh) và Lỗi (Đỏ) trong 7 ngày qua:")
        lbl_chart_title.setStyleSheet("color: #F8FAFC; font-weight: bold;")
        self.layout.addWidget(lbl_chart_title)
        self.chart_widget = BarChartWidget()
        self.layout.addWidget(self.chart_widget)
        
        self.btn_refresh = QPushButton("🔄 Làm Mới Dữ Liệu")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.clicked.connect(self.refresh_data)
        self.btn_refresh.setStyleSheet("padding: 10px; background-color: #44475a; color: white; border-radius: 4px; font-weight: bold;")
        self.layout.addWidget(self.btn_refresh, alignment=Qt.AlignRight)
        
        self.refresh_data()

    def refresh_data(self):
        total_success, total_fail = self.db.get_total_stats()
        self.lbl_total_success.setText(f"{total_success:,}")
        
        time_saved_seconds = total_success * 20
        hours = time_saved_seconds / 3600
        self.lbl_time_saved.setText(f"{hours:.1f} giờ làm việc")
        
        daily_stats = self.db.get_daily_stats(limit_days=7)
        self.chart_widget.set_data(daily_stats)
