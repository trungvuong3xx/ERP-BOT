import sys
import os
import time
import logging
from datetime import datetime

# Configure PySide6
from PySide6.QtCore import Qt, QThread, Signal, Slot, QObject, QSize, QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QSpinBox, QTextEdit, QFrame, QListView,
    QMessageBox, QGraphicsDropShadowEffect, QSizePolicy, QGridLayout,
    QCheckBox, QTabWidget, QLineEdit, QScrollArea, QStackedLayout,
    QSystemTrayIcon, QMenu
)
from PySide6.QtGui import QColor, QFont, QIcon, QShortcut, QKeySequence, QTextCursor, QFontDatabase

# Import core modules
# Lazy imports are used to speed up application startup
from analytics_widget import AnalyticsWidget
import qtawesome as qta

class ToastNotification(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        
        self.frame = QFrame(self)
        self.frame.setStyleSheet("background-color: rgba(30, 30, 46, 0.9); border: 1px solid #34D399; border-radius: 8px;")
        frame_layout = QVBoxLayout(self.frame)
        
        self.label = QLabel("Khởi động...")
        self.label.setStyleSheet("color: #34D399; font-weight: bold; font-family: 'Segoe UI'; font-size: 13px; border: none; background: transparent;")
        self.label.setWordWrap(True)
        frame_layout.addWidget(self.label)
        
        layout.addWidget(self.frame)
        self.setMaximumWidth(450)
        
    def update_message(self, message):
        self.label.setText(message)
        self.adjustSize()
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.width() - self.width() - 20
        y = screen.height() - self.height() - 20
        self.move(x, y)
        if not self.isVisible():
            self.show()

# ==============================================================================
# LOGGING SIGNAL EMITTER & QT HANDLER
# ==============================================================================
class LogSignalEmitter(QObject):
    log_emitted = Signal(str, str)  # (formatted_message, level_name)

class QtLoggingHandler(logging.Handler):
    """Bridge python standard logging module to PySide6 Qt Thread Safety via Signals."""
    def __init__(self, emitter):
        super().__init__()
        self.emitter = emitter

    def emit(self, record):
        msg = self.format(record)
        level = record.levelname
        self.emitter.log_emitted.emit(msg, level)

# ==============================================================================
# WORKER THREAD FOR BOT AUTOMATION
# ==============================================================================
class AutomationWorker(QThread):
    finished_signal = Signal()
    status_signal = Signal(str)  # 'running', 'stopped', 'ready'

    def __init__(self, process_name, sheet_name, category, days_to_run, dry_run=False, skip_open=False):
        super().__init__()
        self.process_name = process_name
        self.sheet_name = sheet_name
        self.category = category
        self.days_to_run = days_to_run
        self.dry_run = dry_run
        self.skip_open = skip_open
        self.is_stop_requested = False

    def run(self):
        try:
            from main import run_automation
            import pyautogui
            if self.days_to_run and len(self.days_to_run) == 1:
                run_automation(
                    process_name=self.process_name,
                    dry_run=self.dry_run,
                    category=self.category,
                    day=self.days_to_run[0],
                    sheet_name=self.sheet_name,
                    skip_open=self.skip_open
                )
            elif self.days_to_run:
                for d in self.days_to_run:
                    if self.is_stop_requested:
                        logging.warning("🛑 Đã ngắt tiến trình theo yêu cầu Dừng Khẩn Cấp.")
                        break
                    run_automation(
                        process_name=self.process_name,
                        dry_run=self.dry_run,
                        category=self.category,
                        day=d,
                        sheet_name=self.sheet_name,
                        skip_open=self.skip_open
                    )
            else:
                run_automation(
                    process_name=self.process_name,
                    dry_run=self.dry_run,
                    category=self.category,
                    sheet_name=self.sheet_name,
                    skip_open=self.skip_open
                )
        except Exception as e:
            if "FailSafeException" in type(e).__name__:
                logging.warning("🛑 CẢNH BÁO DỪNG KHẨN CẤP: Đã kích hoạt dừng khẩn cấp bằng cách rê chuột về góc (0,0)!")
                self.status_signal.emit("stopped")
            else:
                logging.error(f"Lỗi ngoài dự kiến khi thực thi robot: {e}", exc_info=True)
        finally:
            self.finished_signal.emit()

    def request_stop(self):
        self.is_stop_requested = True

# ==============================================================================
# SNIPPING TOOL WIDGET (CHỤP ẢNH / LẤY TỌA ĐỘ)
# ==============================================================================
from PySide6.QtWidgets import QRubberBand
from PySide6.QtGui import QPainter, QPen, QColor, QScreen
from PySide6.QtCore import QRect


class StepWidget(QFrame):
    def __init__(self, step_number, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("QFrame { background-color: #2a2d3e; border-radius: 5px; border: 1px solid #44475a; }")
        self.layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        self.lbl_title = QLabel(f"Bước {step_number}")
        self.lbl_title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.lbl_title.setStyleSheet("border: none; background: transparent;")
        self.btn_delete = QPushButton("Xóa")
        self.btn_delete.setFixedSize(50, 24)
        self.btn_delete.setStyleSheet("background-color: #ff5555; color: white; border: none; border-radius: 3px;")
        header_layout.addWidget(self.lbl_title)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_delete)
        self.layout.addLayout(header_layout)
        
        # Action Type
        action_layout = QHBoxLayout()
        lbl_act = QLabel("Hành động:")
        lbl_act.setStyleSheet("border: none; background: transparent;")
        action_layout.addWidget(lbl_act)
        self.cb_action = QComboBox()
        self.cb_action.setView(QListView())
        self.cb_action.addItems(["Click Chuột", "Gõ Văn Bản", "Nhấn Phím", "Vòng lặp Y+20"])
        self.cb_action.setStyleSheet("background-color: #1e1e2e; border: 1px solid #555;")
        action_layout.addWidget(self.cb_action)
        self.layout.addLayout(action_layout)
        
        # Action details
        self.action_details_layout = QStackedLayout()
        
        # 0: Click
        w_click = QWidget()
        w_click.setStyleSheet("border: none; background: transparent;")
        l_click = QHBoxLayout(w_click)
        l_click.setContentsMargins(0,0,0,0)
        l_click.addWidget(QLabel("Tọa độ (X, Y):"))
        self.txt_coords = QLineEdit()
        self.txt_coords.setPlaceholderText("VD: 100, 200")
        self.txt_coords.setStyleSheet("background-color: #1e1e2e; border: 1px solid #555;")
        l_click.addWidget(self.txt_coords)
        self.action_details_layout.addWidget(w_click)
        
        # 1: Type Text
        w_type = QWidget()
        w_type.setStyleSheet("border: none; background: transparent;")
        l_type = QHBoxLayout(w_type)
        l_type.setContentsMargins(0,0,0,0)
        l_type.addWidget(QLabel("Nội dung:"))
        self.txt_text = QLineEdit()
        self.txt_text.setStyleSheet("background-color: #1e1e2e; border: 1px solid #555;")
        l_type.addWidget(self.txt_text)
        self.action_details_layout.addWidget(w_type)
        
        # 2: Hotkey
        w_hotkey = QWidget()
        w_hotkey.setStyleSheet("border: none; background: transparent;")
        l_hotkey = QHBoxLayout(w_hotkey)
        l_hotkey.setContentsMargins(0,0,0,0)
        l_hotkey.addWidget(QLabel("Phím:"))
        self.cb_hotkey = QComboBox()
        self.cb_hotkey.setView(QListView())
        self.cb_hotkey.addItems(["tab", "enter", "down", "up", "esc", "space", "ctrl+a", "ctrl+v"])
        self.cb_hotkey.setStyleSheet("background-color: #1e1e2e; border: 1px solid #555;")
        l_hotkey.addWidget(self.cb_hotkey)
        self.action_details_layout.addWidget(w_hotkey)

        # 3: Loop Y+20
        w_loop = QWidget()
        w_loop.setStyleSheet("border: none; background: transparent;")
        l_loop = QVBoxLayout(w_loop)
        l_loop.setContentsMargins(0,0,0,0)
        l_loop.addWidget(QLabel("Tự động lặp qua GSheet. Các bước thụt lề sẽ chạy trong vòng lặp."))
        self.txt_loop_code_xy = QLineEdit()
        self.txt_loop_code_xy.setPlaceholderText("Tọa độ Mã SP (X, Y)")
        self.txt_loop_code_xy.setStyleSheet("background-color: #1e1e2e; border: 1px solid #555;")
        l_loop.addWidget(self.txt_loop_code_xy)
        self.txt_loop_qty_xy = QLineEdit()
        self.txt_loop_qty_xy.setPlaceholderText("Tọa độ Số Lượng (X, Y)")
        self.txt_loop_qty_xy.setStyleSheet("background-color: #1e1e2e; border: 1px solid #555;")
        l_loop.addWidget(self.txt_loop_qty_xy)
        self.action_details_layout.addWidget(w_loop)
        
        self.layout.addLayout(self.action_details_layout)
        self.cb_action.currentIndexChanged.connect(self.action_details_layout.setCurrentIndex)
        
        # GSheet Option
        self.chk_gsheet = QCheckBox("Lấy dữ liệu từ Google Sheets?")
        self.chk_gsheet.setStyleSheet("border: none; background: transparent;")
        self.layout.addWidget(self.chk_gsheet)
        
        self.w_gsheet = QWidget()
        self.w_gsheet.setStyleSheet("border: none; background: transparent;")
        l_gsheet = QGridLayout(self.w_gsheet)
        l_gsheet.setContentsMargins(20, 0, 0, 0)
        l_gsheet.addWidget(QLabel("Tên Spreadsheet:"), 0, 0)
        self.txt_gsheet_link = QLineEdit()
        self.txt_gsheet_link.setStyleSheet("background-color: #1e1e2e; border: 1px solid #555;")
        l_gsheet.addWidget(self.txt_gsheet_link, 0, 1)
        l_gsheet.addWidget(QLabel("Tên Sheet:"), 1, 0)
        self.txt_gsheet_name = QLineEdit()
        self.txt_gsheet_name.setStyleSheet("background-color: #1e1e2e; border: 1px solid #555;")
        l_gsheet.addWidget(self.txt_gsheet_name, 1, 1)
        self.layout.addWidget(self.w_gsheet)
        
        self.w_gsheet.setVisible(False)
        self.chk_gsheet.toggled.connect(self.w_gsheet.setVisible)

    def to_dict(self):
        return {
            "action": self.cb_action.currentIndex(),
            "coords": self.txt_coords.text(),
            "text": self.txt_text.text(),
            "hotkey": self.cb_hotkey.currentText(),
            "loop_code_xy": self.txt_loop_code_xy.text(),
            "loop_qty_xy": self.txt_loop_qty_xy.text(),
            "use_gsheet": self.chk_gsheet.isChecked(),
            "gsheet_link": self.txt_gsheet_link.text(),
            "gsheet_name": self.txt_gsheet_name.text()
        }

    def load_from_dict(self, d):
        self.cb_action.setCurrentIndex(d.get("action", 0))
        self.txt_coords.setText(d.get("coords", ""))
        self.txt_text.setText(d.get("text", ""))
        self.cb_hotkey.setCurrentText(d.get("hotkey", "tab"))
        self.txt_loop_code_xy.setText(d.get("loop_code_xy", ""))
        self.txt_loop_qty_xy.setText(d.get("loop_qty_xy", ""))
        self.chk_gsheet.setChecked(d.get("use_gsheet", False))
        self.txt_gsheet_link.setText(d.get("gsheet_link", ""))
        self.txt_gsheet_name.setText(d.get("gsheet_name", ""))

class SnippingWidget(QWidget):
    snippet_taken = Signal(int, int, int, int, object)  # x, y, w, h, QPixmap

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setCursor(Qt.CrossCursor)
        
        screen = QApplication.primaryScreen()
        self.original_pixmap = screen.grabWindow(0)
        
        self.setGeometry(screen.geometry())
        self.begin = None
        self.end = None
        
        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self)

    def paintEvent(self, event):
        painter = QPainter(self)
        # Vẽ màn hình gốc
        painter.drawPixmap(self.rect(), self.original_pixmap)
        # Làm tối màn hình
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        
        # Làm sáng vùng chọn
        if self.begin and self.end:
            rect = QRect(self.begin, self.end).normalized()
            painter.drawPixmap(rect, self.original_pixmap, rect)
            
            # Vẽ viền
            painter.setPen(QPen(QColor(255, 0, 0), 2))
            painter.drawRect(rect)

    def mousePressEvent(self, event):
        self.begin = event.position().toPoint()
        self.end = self.begin
        self.rubber_band.setGeometry(QRect(self.begin, self.end).normalized())
        self.rubber_band.show()

    def mouseMoveEvent(self, event):
        self.end = event.position().toPoint()
        self.rubber_band.setGeometry(QRect(self.begin, self.end).normalized())
        self.update()

    def mouseReleaseEvent(self, event):
        self.end = event.position().toPoint()
        self.rubber_band.hide()
        
        rect = QRect(self.begin, self.end).normalized()
        captured_pixmap = self.original_pixmap.copy(rect)
        
        self.snippet_taken.emit(rect.x(), rect.y(), rect.width(), rect.height(), captured_pixmap)
        slogger = logging.getLogger("ERPAutomation.GUI")
        self.close()

# ==============================================================================
# ANTI-AFK WORKER (RESTORED)
# ==============================================================================
class AntiAFKWorker(QThread):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_running = False

    def run(self):
        self.is_running = True
        while self.is_running:
            self.perform_anti_afk_click()
            for _ in range(4200): # 7 minutes (420 seconds) in 100ms chunks
                if not self.is_running:
                    break
                QThread.msleep(100)

    def perform_anti_afk_click(self):
        try:
            import win32gui
            import win32api
            import win32con
            from PySide6.QtCore import QThread
            
            target_hwnd = None
            def enum_win_cb(hwnd, _):
                nonlocal target_hwnd
                if win32gui.IsWindowVisible(hwnd):
                    length = win32gui.GetWindowTextLength(hwnd)
                    if length > 0:
                        title = win32gui.GetWindowText(hwnd).lower()
                        if "workflow erp igp" in title and "automation" not in title and "bot" not in title and "đăng nhập" not in title and "invi08" not in title and "thiết lập" not in title:
                            target_hwnd = hwnd
                            return False
                return True

            win32gui.EnumWindows(enum_win_cb, 0)

            if target_hwnd:
                logging.getLogger("ERPAutomation.Worker").info(f"Đã gửi tín hiệu click ngầm (Anti-AFK) tới ERP (HWND: {target_hwnd}) tại tọa độ 216, 296.")
                
                x, y = 216, 296
                
                # Cần tìm chính xác cửa sổ con (Child Window) tại vị trí đó để gửi lệnh
                # Vì các ứng dụng ERP thường dùng Chromium/Webview bọc bên trong
                target_child = target_hwnd
                children = []
                try:
                    win32gui.EnumChildWindows(target_hwnd, lambda hwnd, param: param.append(hwnd) or True, children)
                    for child in reversed(children):
                        if win32gui.IsWindowVisible(child):
                            rect = win32gui.GetWindowRect(child)
                            if rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]:
                                target_child = child
                                break
                except:
                    pass
                
                try:
                    client_pt = win32gui.ScreenToClient(target_child, (x, y))
                    lparam = win32api.MAKELONG(client_pt[0], client_pt[1])
                except:
                    lparam = win32api.MAKELONG(x, y)
                
                # Gửi tín hiệu đánh thức (MouseMove) và Click ngầm tới cửa sổ con
                win32gui.PostMessage(target_child, win32con.WM_MOUSEMOVE, 0, lparam)
                QThread.msleep(50)
                win32gui.PostMessage(target_child, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
                QThread.msleep(50)
                win32gui.PostMessage(target_child, win32con.WM_LBUTTONUP, 0, lparam)
                
                # Gửi thêm phím Shift ảo để đánh thức
                win32gui.PostMessage(target_child, win32con.WM_KEYDOWN, win32con.VK_SHIFT, 0)
                QThread.msleep(50)
                win32gui.PostMessage(target_child, win32con.WM_KEYUP, win32con.VK_SHIFT, 0)
                
        except Exception as e:
            logging.getLogger("ERPAutomation.Worker").error(f"Lỗi Anti-AFK: {e}")

# ==============================================================================
# MAIN GUI APPLICATION
# ==============================================================================
class ERPBotApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ERP Bot iGP - Automation Suite v3.0 (PySide6 Edition)")
        self.resize(920, 780)
        self.setMinimumSize(840, 680)

        # State Variables
        self.selected_sheet = "ERP Chỉ"
        self.date_mode = "single"  # 'single', 'range', 'all'
        self.is_running = False
        self.worker = None

        # Setup Log Emitter & Handler
        self.log_emitter = LogSignalEmitter()
        self.log_emitter.log_emitted.connect(self._on_log_emitted)
        self._setup_logging()

        # Build UI
        self.toast = ToastNotification()
        self._apply_qss_stylesheet()
        self._build_ui()
        self._setup_profiles()
        self._setup_shortcuts()
        self._load_processes_to_ui()
        self._setup_tray_icon()
        
    def _setup_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "app_icon.ico"))
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            self.tray_icon.setIcon(self.style().standardIcon(self.style().SP_ComputerIcon))
        
        tray_menu = QMenu()
        restore_action = tray_menu.addAction("Mở lại bảng điều khiển")
        restore_action.triggered.connect(self.showNormal)
        quit_action = tray_menu.addAction("Thoát Bot")
        quit_action.triggered.connect(QApplication.instance().quit)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

        logging.info("🚀 Giao diện PySide6 Dashboard đã khởi tạo thành công. Hệ thống sẵn sàng!")

        # Initialize Anti-AFK Worker
        self.afk_worker = AntiAFKWorker()

    def _on_dashboard_toggle_afk(self):
        if not self.afk_worker.is_running:
            self.afk_worker.start()
            self.btn_dashboard_afk.setText(" Tắt Chống AFK")
            self.btn_dashboard_afk.setIcon(qta.icon('fa5s.shield-alt', color='#1e1e2e'))
            self.btn_dashboard_afk.setStyleSheet("background-color: #50fa7b; color: #1e1e2e; padding: 6px 12px; border-radius: 4px; font-weight: bold;")
            QMessageBox.information(self, "Anti-AFK", "Đã BẬT Chống AFK! Mỗi 7 phút bot sẽ tự click ngầm 1 lần.")
        else:
            self.afk_worker.is_running = False
            self.btn_dashboard_afk.setText(" Bật Chống AFK")
            self.btn_dashboard_afk.setIcon(qta.icon('fa5s.shield-alt', color='white'))
            self.btn_dashboard_afk.setStyleSheet("background-color: #2e2e2e; color: white; padding: 6px 12px; border-radius: 4px; font-weight: bold;")
            QMessageBox.information(self, "Anti-AFK", "Đã TẮT Chống AFK.")

    def _setup_logging(self):
        handler = QtLoggingHandler(self.log_emitter)
        formatter = logging.Formatter('%(asctime)s %(message)s', datefmt='%H:%M:%S')
        handler.setFormatter(formatter)
        
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.INFO)

    def _build_ui(self):
        central_widget = QWidget(self)
        central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(central_widget)

        main_vbox = QVBoxLayout(central_widget)
        main_vbox.setContentsMargins(0, 0, 0, 0)

        # Top Bar: Profile Selector & Auto Update
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(10, 5, 10, 5)
        
        lbl_profile = QLabel("👤 Profile:")
        lbl_profile.setFont(QFont("Segoe UI", 10, QFont.Bold))
        top_bar.addWidget(lbl_profile)
        
        self.combo_profile = QComboBox()
        self.combo_profile.setView(QListView())
        self.combo_profile.setFixedWidth(200)
        self.combo_profile.currentIndexChanged.connect(self._on_profile_changed)
        top_bar.addWidget(self.combo_profile)
        
        top_bar.addStretch()
        
        self.btn_update = QPushButton(" Cập Nhật")
        self.btn_update.setIcon(qta.icon('fa5s.sync-alt', color='white'))
        self.btn_update.setFixedWidth(150)
        self.btn_update.clicked.connect(self._check_for_updates)
        top_bar.addWidget(self.btn_update)
        
        main_vbox.addLayout(top_bar)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("MainTabs")
        main_vbox.addWidget(self.tabs)

        # ======================================================================
        # TAB 1: ĐIỀU KHIỂN
        # ======================================================================
        tab_control = QWidget()
        main_layout = QVBoxLayout(tab_control)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)
        self.tabs.addTab(tab_control, qta.icon('fa5s.sliders-h', color='white'), " ĐIỀU KHIỂN")
        
        # ======================================================================
        # TAB 2: THỐNG KÊ (ANALYTICS)
        # ======================================================================
        self.tab_analytics = AnalyticsWidget()
        self.tabs.addTab(self.tab_analytics, qta.icon('fa5s.chart-pie', color='white'), " THỐNG KÊ")

        # ----------------------------------------------------------------------
        # 1. HEADER BANNER CARD
        # ----------------------------------------------------------------------
        header_card = QFrame()
        header_card.setObjectName("HeaderCard")
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(20, 16, 20, 16)

        title_box = QVBoxLayout()
        title_box.setSpacing(4)

        lbl_title = QLabel("WorkFlow ERP iGP - Automation Bot v3.0")
        lbl_title.setObjectName("HeaderTitle")
        lbl_sub = QLabel("Hệ thống tự động hóa nhập chứng từ Google Sheets (Chỉ & Nhựa) • Tài khoản: 51225")
        lbl_sub.setObjectName("HeaderSub")

        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        header_layout.addLayout(title_box)

        header_layout.addStretch()

        self.btn_dashboard_afk = QPushButton(" Bật Chống AFK")
        self.btn_dashboard_afk.setIcon(qta.icon('fa5s.shield-alt', color='white'))
        self.btn_dashboard_afk.setCursor(Qt.PointingHandCursor)
        self.btn_dashboard_afk.setStyleSheet("background-color: #2e2e2e; color: white; padding: 6px 12px; border-radius: 4px; font-weight: bold;")
        self.btn_dashboard_afk.clicked.connect(self._on_dashboard_toggle_afk)
        header_layout.addWidget(self.btn_dashboard_afk)

        self.lbl_status_badge = QLabel("● System Ready")
        self.lbl_status_badge.setObjectName("StatusBadgeReady")
        self.lbl_status_badge.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(self.lbl_status_badge)

        main_layout.addWidget(header_card)

        # ----------------------------------------------------------------------
        # 2. DUAL CONFIGURATION CARDS (Grid Layout)
        # ----------------------------------------------------------------------
        grid_config = QHBoxLayout()
        grid_config.setSpacing(16)

        # --- Card 1: Spreadsheet Configuration ---
        card_sheets = QFrame()
        card_sheets.setObjectName("ConfigCard")
        sheets_layout = QVBoxLayout(card_sheets)
        sheets_layout.setContentsMargins(18, 18, 18, 18)
        sheets_layout.setSpacing(12)


        lbl_sec1 = QLabel("Configuration")
        lbl_sec1.setObjectName("SectionTitle")
        sheets_layout.addWidget(lbl_sec1)

        # Process Selection
        lbl_process_tag = QLabel("Quy Trình (Process):")
        lbl_process_tag.setObjectName("FormLabel")
        sheets_layout.addWidget(lbl_process_tag)

        self.cbo_process = QComboBox()
        self.cbo_process.setView(QListView())
        self.cbo_process.setCursor(Qt.PointingHandCursor)
        self.cbo_process.currentIndexChanged.connect(self._on_process_changed)
        sheets_layout.addWidget(self.cbo_process)

        # Segmented Pills: Sheet Select
        lbl_sheet_tag = QLabel("Nguồn Dữ Liệu (Target Sheet):")

        lbl_sheet_tag.setObjectName("FormLabel")
        sheets_layout.addWidget(lbl_sheet_tag)

        pill_sheet_layout = QHBoxLayout()
        pill_sheet_layout.setSpacing(10)

        self.btn_sheet_chi = QPushButton(" ERP Chỉ")
        self.btn_sheet_chi.setIcon(qta.icon('fa5s.file-alt', color='white'))
        self.btn_sheet_chi.setObjectName("SegmentPillActive")
        self.btn_sheet_chi.setCursor(Qt.PointingHandCursor)
        self.btn_sheet_chi.clicked.connect(lambda: self._set_sheet("ERP Chỉ"))

        self.btn_sheet_nhua = QPushButton(" ERP Nhựa")
        self.btn_sheet_nhua.setIcon(qta.icon('fa5s.box', color='white'))
        self.btn_sheet_nhua.setObjectName("PillInactive")
        self.btn_sheet_nhua.setCursor(Qt.PointingHandCursor)
        self.btn_sheet_nhua.clicked.connect(lambda: self._set_sheet("ERP Nhựa"))

        self.btn_sheet_btp = QPushButton(" BTP")
        self.btn_sheet_btp.setIcon(qta.icon('fa5s.layer-group', color='white'))
        self.btn_sheet_btp.setObjectName("PillInactive")
        self.btn_sheet_btp.setCursor(Qt.PointingHandCursor)
        self.btn_sheet_btp.clicked.connect(lambda: self._set_sheet("BTP"))

        pill_sheet_layout.addWidget(self.btn_sheet_chi)
        pill_sheet_layout.addWidget(self.btn_sheet_nhua)
        pill_sheet_layout.addWidget(self.btn_sheet_btp)
        sheets_layout.addLayout(pill_sheet_layout)

        # Category Dropdown
        lbl_cat_tag = QLabel("Category Filter:")
        lbl_cat_tag.setObjectName("FormLabel")
        sheets_layout.addWidget(lbl_cat_tag)

        self.cbo_category = QComboBox()
        self.cbo_category.setView(QListView())
        self.cbo_category.setCursor(Qt.PointingHandCursor)
        self._load_processes_to_ui()
        self._update_category_options("ERP Chỉ")
        sheets_layout.addWidget(self.cbo_category)

        sheets_layout.addStretch()
        grid_config.addWidget(card_sheets)

        # --- Card 2: Execution Range ---
        card_range = QFrame()
        card_range.setObjectName("ConfigCard")
        range_layout = QVBoxLayout(card_range)
        range_layout.setContentsMargins(18, 18, 18, 18)
        range_layout.setSpacing(12)

        lbl_sec2 = QLabel("Chọn Ngày Nhập Liệu (1 - 31)")
        lbl_sec2.setObjectName("SectionTitle")
        range_layout.addWidget(lbl_sec2)

        lbl_day_tag = QLabel("Chọn ngày cụ thể để nạp dữ liệu siêu tốc:")
        lbl_day_tag.setObjectName("FormLabel")
        range_layout.addWidget(lbl_day_tag)

        stepper_layout = QHBoxLayout()
        stepper_layout.setContentsMargins(0, 4, 0, 0)
        stepper_layout.setSpacing(10)

        self.lbl_day_start = QLabel("Ngày chọn:")
        self.lbl_day_start.setObjectName("FormLabel")
        self.spn_start = QSpinBox()
        self.spn_start.setRange(1, 31)
        self.spn_start.setValue(24)
        self.spn_start.setFixedWidth(80)

        stepper_layout.addWidget(self.lbl_day_start)
        stepper_layout.addWidget(self.spn_start)
        stepper_layout.addStretch()

        range_layout.addLayout(stepper_layout)

        range_layout.addStretch()
        grid_config.addWidget(card_range)

        main_layout.addLayout(grid_config)

        # ----------------------------------------------------------------------
        # 3. THREE SLEEK ACTION BUTTONS
        # ----------------------------------------------------------------------
        action_layout = QHBoxLayout()
        action_layout.setSpacing(12)

        self.btn_run = QPushButton("  BẮT ĐẦU CHẠY BOT")
        self.btn_run.setIcon(qta.icon('fa5s.rocket', color='white'))
        self.btn_run.setObjectName("BtnRun")
        self.btn_run.setCursor(Qt.PointingHandCursor)
        self.btn_run.clicked.connect(self.start_bot)

        self.btn_dry_run = QPushButton("  CHẠY THỬ (DRY-RUN)")
        self.btn_dry_run.setIcon(qta.icon('fa5s.vial', color='white'))
        self.btn_dry_run.setObjectName("BtnDryRun")
        self.btn_dry_run.setCursor(Qt.PointingHandCursor)
        self.btn_dry_run.clicked.connect(self.start_dry_run)

        self.btn_stop = QPushButton("  DỪNG KHẨN CẤP (Esc / Ctrl+Q)")
        self.btn_stop.setIcon(qta.icon('fa5s.stop-circle', color='white'))
        self.btn_stop.setObjectName("BtnEmergencyStop")
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.clicked.connect(self.stop_bot)

        action_layout.addWidget(self.btn_run, 2)
        action_layout.addWidget(self.btn_dry_run, 2)
        action_layout.addWidget(self.btn_stop, 2)

        main_layout.addLayout(action_layout)

        # ----------------------------------------------------------------------
        # 4. LIVE CONSOLE STREAM CARD (With MacOS Control Dots)
        # ----------------------------------------------------------------------
        log_card = QFrame()
        log_card.setObjectName("LogCard")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(16, 12, 16, 14)
        log_layout.setSpacing(10)

        log_header = QHBoxLayout()
        lbl_log_title = QLabel(" Nhật Ký Thực Thi Trực Tiếp (Live Console Stream)")
        lbl_log_title.setObjectName("SectionTitle")

        dots_layout = QHBoxLayout()
        dots_layout.setSpacing(6)
        for color_code in ["#FF5F56", "#FFBD2E", "#27C93F"]:
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color_code}; font-size: 12px;")
            dots_layout.addWidget(dot)

        log_header.addWidget(lbl_log_title)
        log_header.addStretch()
        log_header.addLayout(dots_layout)
        log_layout.addLayout(log_header)

        self.txt_console = QTextEdit()
        self.txt_console.setObjectName("ConsoleStream")
        self.txt_console.setReadOnly(True)
        log_layout.addWidget(self.txt_console)

        main_layout.addWidget(log_card, 1)

        # Footer Tip
        lbl_footer = QLabel("💡 Mẹo phím tắt: Bấm phím ESC, Ctrl+Q, F12 hoặc rê chuột về góc (0,0) màn hình để ngắt robot khẩn cấp ngay lập tức.")
        lbl_footer.setObjectName("FooterTip")
        main_layout.addWidget(lbl_footer)

        # ======================================================================
        # TAB 2: CÀI ĐẶT
        # ======================================================================
        tab_settings = QWidget()
        settings_layout = QVBoxLayout(tab_settings)
        settings_layout.setContentsMargins(20, 20, 20, 20)
        settings_layout.setSpacing(16)


        
        lbl_snip = QLabel("Công cụ Ảnh Mẫu & Tọa Độ (Snipping Tool):")
        lbl_snip.setFont(QFont("Segoe UI", 11, QFont.Bold))
        settings_layout.addWidget(lbl_snip)
        
        btn_snip = QPushButton("✂  Chụp Ảnh / Lấy Tọa Độ")
        btn_snip.setFixedSize(200, 36)
        btn_snip.clicked.connect(self._start_snipping)
        settings_layout.addWidget(btn_snip)
        

        lbl_macro = QLabel("Trình Tạo Kịch Bản Tự Do (Macro Builder):")
        lbl_macro.setFont(QFont("Segoe UI", 11, QFont.Bold))
        settings_layout.addWidget(lbl_macro)

        macro_form = QGridLayout()
        macro_form.addWidget(QLabel("Tên Quy trình:"), 0, 0)
        self.txt_macro_name = QLineEdit()
        self.txt_macro_name.setPlaceholderText("Nhập tên quy trình mới...")
        macro_form.addWidget(self.txt_macro_name, 0, 1)
        settings_layout.addLayout(macro_form)

        # Scroll Area cho các bước
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumHeight(300)
        
        self.macro_steps_container = QWidget()
        self.macro_steps_layout = QVBoxLayout(self.macro_steps_container)
        self.macro_steps_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.macro_steps_container)
        
        settings_layout.addWidget(self.scroll_area)
        
        self.step_widgets = []
        
        btn_layout = QHBoxLayout()
        self.btn_add_step = QPushButton("+ Thêm Bước")
        self.btn_add_step.setObjectName("BtnSecondary")
        self.btn_add_step.clicked.connect(self.add_macro_step)
        btn_layout.addWidget(self.btn_add_step)
        
        self.btn_save_macro = QPushButton("💾 Lưu Quy Trình Mới")
        self.btn_save_macro.setObjectName("BtnPrimary")
        self.btn_save_macro.clicked.connect(self.save_macro)
        btn_layout.addWidget(self.btn_save_macro)
        
        settings_layout.addLayout(btn_layout)
        settings_layout.addStretch()

        self.tabs.addTab(tab_settings, "Cài đặt (Settings)")
        
        # Load existing config into text boxes
    
    def add_macro_step(self):
        step_number = len(self.step_widgets) + 1
        widget = StepWidget(step_number)
        widget.btn_delete.clicked.connect(lambda checked=False, w=widget: self.remove_macro_step(w))
        self.macro_steps_layout.addWidget(widget)
        self.step_widgets.append(widget)

    def remove_macro_step(self, widget):
        self.macro_steps_layout.removeWidget(widget)
        widget.deleteLater()
        self.step_widgets.remove(widget)
        # Re-number
        for i, w in enumerate(self.step_widgets):
            w.lbl_title.setText(f"Bước {i + 1}")

    def save_macro(self):
        macro_name = self.txt_macro_name.text().strip()
        if not macro_name:
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập tên quy trình!")
            return
            
        steps = [w.to_dict() for w in self.step_widgets]
        if not steps:
            QMessageBox.warning(self, "Lỗi", "Quy trình không có bước nào!")
            return
            
        # Lưu vào config
        from main import load_config
        import json
        config = load_config()
        custom_processes = config.get("custom_processes", {})
        custom_processes[macro_name] = steps
        config["custom_processes"] = custom_processes
        
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
            
        QMessageBox.information(self, "Thành công", f"Đã lưu quy trình '{macro_name}' thành công!")
        
        # Cập nhật lại danh sách trên UI chính nếu cần
        self._update_category_options("ERP Chỉ") # Tạm thời gọi để trigger update


    def _setup_profiles(self):
        from main import load_config
        config = load_config()
        self.combo_profile.blockSignals(True)
        self.combo_profile.clear()
        
        full_config = config.get("_full_config", {})
        profiles = full_config.get("profiles", {})
        if not profiles:
            self.combo_profile.addItem("Default")
        else:
            for profile_name in profiles.keys():
                self.combo_profile.addItem(profile_name)
            
            active = config.get("_active_profile")
            if active in profiles:
                self.combo_profile.setCurrentText(active)
                
        self.combo_profile.blockSignals(False)

    def _on_profile_changed(self, index):
        profile_name = self.combo_profile.currentText()
        if not profile_name:
            return
            
        # Update config active profile
        from main import load_config
        config = load_config()
        full_config = config.get("_full_config", {})
        full_config["active_profile"] = profile_name
        
        with open("config.json", "w", encoding="utf-8") as f:
            import json
            json.dump(full_config, f, indent=4, ensure_ascii=False)
            
        logger.info(f"Đã chuyển sang Profile: {profile_name}")

    def _check_for_updates(self):
        try:
            import updater
            QMessageBox.information(self, "Auto-Update", "Đang kiểm tra cập nhật trên Github... Vui lòng đợi.")
            self.btn_update.setEnabled(False)
            self.btn_update.setText("Đang kiểm tra...")
            
            # Should really be done in a QThread to avoid freezing UI, but for simplicity:
            has_update = updater.check_for_updates()
            if has_update:
                reply = QMessageBox.question(self, "Cập Nhật Mới", "Có bản cập nhật mới! Bạn có muốn tải về và khởi động lại không?",
                                             QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.btn_update.setText("Đang tải...")
                    updater.apply_update_and_restart()
                else:
                    self.btn_update.setText("🔄 Cập Nhật")
                    self.btn_update.setEnabled(True)
            else:
                QMessageBox.information(self, "Auto-Update", "Bạn đang sử dụng phiên bản mới nhất!")
                self.btn_update.setText("🔄 Cập Nhật")
                self.btn_update.setEnabled(True)
        except Exception as e:
            QMessageBox.warning(self, "Lỗi", f"Không thể kiểm tra cập nhật: {e}")
            self.btn_update.setText("🔄 Cập Nhật")
            self.btn_update.setEnabled(True)


    def _start_snipping(self):
        self.setWindowState(Qt.WindowMinimized) # Thu nhỏ ERPBotApp
        # Đợi 1 chút để app thu nhỏ hẳn
        QTimer.singleShot(200, self._show_snipping_widget)

    def _show_snipping_widget(self):
        self.snipping_widget = SnippingWidget()
        self.snipping_widget.snippet_taken.connect(self._on_snippet_taken)
        self.snipping_widget.show()

    def _on_snippet_taken(self, x, y, w, h, pixmap):
        self.setWindowState(Qt.WindowNoState) # Hiện lại app
        
        reply = QMessageBox.question(self, "Lưu Mẫu",
                                     f"Bạn đã quét vùng: X={x}, Y={y}, W={w}, H={h}.\n\nBạn muốn:\n"
                                     f"Yes: Lưu ảnh mẫu (cho OpenCV)\nNo: Chỉ lấy tọa độ X,Y\nCancel: Hủy",
                                     QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        if reply == QMessageBox.Yes:
            import os
            os.makedirs("templates", exist_ok=True)
            import uuid
            filename = f"templates/snip_{uuid.uuid4().hex[:6]}.png"
            pixmap.save(filename)
            QMessageBox.information(self, "Lưu Ảnh", f"Đã lưu ảnh tại:\n{filename}")
        elif reply == QMessageBox.No:
            # Clipboard the coordinate
            import pyperclip
            pyperclip.copy(f"{x}, {y}")
            QMessageBox.information(self, "Lấy Tọa Độ", f"Đã copy tọa độ ({x}, {y}) vào Clipboard.")

    def _setup_shortcuts(self):
        shortcut_esc = QShortcut(QKeySequence(Qt.Key_Escape), self)
        shortcut_esc.activated.connect(self.stop_bot)

        shortcut_ctrl_q = QShortcut(QKeySequence("Ctrl+Q"), self)
        shortcut_ctrl_q.activated.connect(self.stop_bot)

        shortcut_f12 = QShortcut(QKeySequence(Qt.Key_F12), self)
        shortcut_f12.activated.connect(self.stop_bot)

    def _set_sheet(self, sheet_name):
        self.selected_sheet = sheet_name
        self.btn_sheet_chi.setObjectName("PillActive" if sheet_name == "ERP Chỉ" else "PillInactive")
        self.btn_sheet_nhua.setObjectName("PillActive" if sheet_name == "ERP Nhựa" else "PillInactive")
        if hasattr(self, 'btn_sheet_btp'):
            self.btn_sheet_btp.setObjectName("PillActive" if sheet_name == "BTP" else "PillInactive")

        self.btn_sheet_chi.setStyle(self.btn_sheet_chi.style())
        self.btn_sheet_nhua.setStyle(self.btn_sheet_nhua.style())
        if hasattr(self, 'btn_sheet_btp'):
            self.btn_sheet_btp.setStyle(self.btn_sheet_btp.style())
        self._update_category_options(sheet_name)


    def _update_category_options(self, sheet_name):
        self.cbo_category.clear()
        
        process_name = self.cbo_process.currentText()
        
        if process_name == "COPMI08" or sheet_name == "BTP":
            cats = ["BTP"]
        elif process_name == "INVI08":
            if sheet_name == "ERP Chỉ":
                cats = ["XUẤT", "XUẤT TRẢ X1", "XUẤT TRẢ XI", "XUẤT TRẢ", "XUẤT BÁN", "GIA CÔNG", "FOR XUẤT", "XUẤT FOR", "XUẤT BÌNH THUẬN", "BÁN PHẾ", "XUẤT VẢI PP", "XUẤT TƠ", "NHẬP TRẢ", "NHẬP TRẢ X1", "NHẬP TRẢ X5"]
            else:
                cats = ["XUẤT", "XUẤT FOR", "FOR XUẤT", "NHẬP TRẢ", "NHẬP TRẢ X1", "NHẬP TRẢ X5"]
        elif process_name == "PURMI09":
            if sheet_name == "ERP Chỉ":
                cats = ["NHẬP", "NHẬP FOR", "FOR NHẬP"]
            else:
                cats = ["NHẬP NHỰA", "NHẬP TÁI CHẾ", "NHẬP MÀU", "FOR NHẬP", "NHẬP FOR", "NHẬP TOYO", "NHẬP VẢI PP", "NHẬP TƠ"]
        else:
            # Custom process -> show all or empty
            cats = ["Tất cả", "XUẤT", "NHẬP"]
            
        self.cbo_category.addItems(cats)

    def _on_process_changed(self, index):
        p_name = self.cbo_process.currentText()
        if p_name == "COPMI08":
            self._set_sheet("BTP")
        elif hasattr(self, 'selected_sheet'):
            if self.selected_sheet == "BTP":
                self._set_sheet("ERP Chỉ")
            else:
                self._update_category_options(self.selected_sheet)

    def _load_processes_to_ui(self):
        self.cbo_process.clear()
        self.cbo_process.addItems(["INVI08", "PURMI09", "COPMI08"])
        
        from main import load_config
        config = load_config()
        custom_processes = config.get("custom_processes", {})
        if custom_processes:
            for p_name in custom_processes.keys():
                self.cbo_process.addItem(p_name)


    def _set_date_mode(self, mode="single"):
        self.date_mode = "single"

    def _update_stepper_visibility(self):
        pass

    def update_status_badge(self, state: str):
        if state == "running":
            self.lbl_status_badge.setText("● Executing Bot...")
            self.lbl_status_badge.setObjectName("StatusBadgeRunning")
        elif state == "stopped":
            self.lbl_status_badge.setText("● Emergency Stopped")
            self.lbl_status_badge.setObjectName("StatusBadgeStopped")
        else:
            self.lbl_status_badge.setText("● System Ready")
            self.lbl_status_badge.setObjectName("StatusBadgeReady")

        self.lbl_status_badge.setStyle(self.lbl_status_badge.style())

    @Slot(str, str)
    def _on_log_emitted(self, msg, level):
        color = "#38BDF8"  # Default INFO Sky Blue
        tag = f"[{level[:3]}]"

        if level == "INFO":
            if "HOÀN TẤT" in msg or "thành công" in msg.lower() or "PHÁT HIỆN" in msg:
                color = "#34D399"  # Neon Green
                tag = "[SUC]"
        elif level == "WARNING":
            color = "#FBBF24"  # Amber Yellow
            tag = "[WRN]"
        elif level == "ERROR":
            color = "#F87171"  # Bright Red
            tag = "[ERR]"

        formatted_html = f'<span style="color: {color}; font-weight: bold;">&gt;{tag}</span> <span style="color: #F8FAFC;">{msg}</span>'
        self.txt_console.append(formatted_html)
        self.txt_console.moveCursor(QTextCursor.End)
        
        # Hiện popup (toast) quá trình ở góc phải dưới màn hình y như log chạy (ẩn log Anti-AFK)
        if hasattr(self, 'toast') and "Anti-AFK" not in msg:
            # Chỉ lấy phần nội dung (bỏ thời gian HH:MM:SS ở 8 ký tự đầu)
            raw_msg = msg[9:] if len(msg) > 9 and msg[8] == ' ' else msg
            self.toast.update_message(raw_msg)

    def start_bot(self):
        self._execute(dry_run=False)

    def start_dry_run(self):
        self._execute(dry_run=True)

    def stop_bot(self):
        if self.is_running and self.worker:
            self.worker.request_stop()
            self.update_status_badge("stopped")
            logging.warning("🛑 BẠN ĐÃ BẤM NÚT DỪNG KHẨN CẤP! Đang ngắt tiến trình robot...")
            QMessageBox.warning(self, "Emergency Stop", "Đã gửi lệnh ngắt robot. Vui lòng kiểm tra lại thao tác trên ERP!")
        else:
            QMessageBox.information(self, "Notice", "Robot is currently idle.")

    def _execute(self, dry_run=False):
        if self.is_running:
            QMessageBox.warning(self, "Warning", "Robot is currently executing. Please wait or press Emergency Stop!")
            return

        category = self.cbo_category.currentText()
        sheet_name = self.selected_sheet
        days_to_run = [self.spn_start.value()]

        skip_open = False

        self.is_running = True
        self.update_status_badge("running")
        self.btn_run.setEnabled(False)
        self.btn_dry_run.setEnabled(False)
        self.btn_stop.setEnabled(True)

        self.worker = AutomationWorker(
            process_name=self.cbo_process.currentText(),
            sheet_name=sheet_name,
            category=category,
            days_to_run=days_to_run,
            dry_run=dry_run,
            skip_open=skip_open
        )
        self.worker.status_signal.connect(self.update_status_badge)
        self.worker.finished_signal.connect(self._on_worker_finished)
        
        # Luôn thu nhỏ cửa sổ Bot xuống Taskbar để nhường không gian cho ERP
        self.showMinimized()
        # Đợi một chút để OS kịp thu nhỏ và trả focus cho cửa sổ ERP nằm dưới
        QThread.msleep(500)
            
        self.worker.start()

    def _on_worker_finished(self):
        self.is_running = False
        self.btn_run.setEnabled(True)
        self.btn_dry_run.setEnabled(True)
        if self.lbl_status_badge.text() != "● Emergency Stopped":
            self.update_status_badge("ready")
        logging.info("=== HOÀN TẤT CÔNG VIỆC TRÊN PYSIDE6 DASHBOARD ===")
        
        # Khôi phục cửa sổ nếu trước đó bị thu nhỏ
        if self.isMinimized():
            self.showNormal()
            self.activateWindow()
            
        # Không dùng QMessageBox ở giữa màn hình nữa, Toast sẽ tự báo
        QTimer.singleShot(5000, self.toast.hide)

    def _apply_qss_stylesheet(self):
        try:
            with open("style.qss", "r", encoding="utf-8") as f:
                qss = f.read()
            self.setStyleSheet(qss)
        except Exception as e:
            logging.error(f"Lỗi nạp style.qss: {e}")


def main():
    # Windows Taskbar Icon Fix & Single Instance Check
    try:
        import ctypes
        import sys
        from PySide6.QtWidgets import QApplication, QMessageBox
        
        myappid = 'mycompany.botmanager.igp.pyside.3.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        
        # Prevent multiple instances
        mutex_name = "ERP_BOT_AUTOMATION_MUTEX_v3"
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
        if ctypes.windll.kernel32.GetLastError() == 183: # ERROR_ALREADY_EXISTS
            app = QApplication(sys.argv)
            QMessageBox.warning(None, "Cảnh Báo", "ERP BOT đã đang được chạy! Vui lòng kiểm tra dưới thanh Taskbar.")
            sys.exit(0)
    except Exception:
        pass

    app = QApplication(sys.argv)
    
    # High-DPI Scaling Policy
    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

    icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "app_icon.ico"))
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = ERPBotApp()
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))

    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
