import sys
import os
import time
import logging
from datetime import datetime

# Configure PySide6
from PySide6.QtCore import Qt, QThread, Signal, Slot, QObject, QSize, QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QSpinBox, QTextEdit, QFrame,
    QMessageBox, QGraphicsDropShadowEffect, QSizePolicy, QGridLayout,
    QCheckBox, QTabWidget, QLineEdit
)
from PySide6.QtGui import QColor, QFont, QIcon, QShortcut, QKeySequence, QTextCursor, QFontDatabase

# Import core modules
from main import run_automation, load_config
from google_sheets import GoogleSheetsHandler

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

    def __init__(self, sheet_name, category, days_to_run, dry_run=False, skip_open=False):
        super().__init__()
        self.sheet_name = sheet_name
        self.category = category
        self.days_to_run = days_to_run
        self.dry_run = dry_run
        self.skip_open = skip_open
        self.is_stop_requested = False

    def run(self):
        try:
            import pyautogui
            if self.days_to_run and len(self.days_to_run) == 1:
                run_automation(
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
                        dry_run=self.dry_run,
                        category=self.category,
                        day=d,
                        sheet_name=self.sheet_name,
                        skip_open=self.skip_open
                    )
            else:
                run_automation(
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
        self.close()

# ==============================================================================
# MAIN PYSIDE6 GUI DASHBOARD
# ==============================================================================
class ERPBotApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WorkFlow ERP iGP - Automation Suite v3.0 (PySide6 Edition)")
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
        self._apply_qss_stylesheet()
        self._build_ui()
        self._setup_profiles()
        self._setup_shortcuts()

        logging.info("🚀 Giao diện PySide6 Dashboard đã khởi tạo thành công. Hệ thống sẵn sàng!")

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
        self.combo_profile.setFixedWidth(200)
        self.combo_profile.currentIndexChanged.connect(self._on_profile_changed)
        top_bar.addWidget(self.combo_profile)
        
        top_bar.addStretch()
        
        self.btn_update = QPushButton("🔄 Cập Nhật (Update)")
        self.btn_update.setFixedWidth(150)
        self.btn_update.clicked.connect(self._check_for_updates)
        top_bar.addWidget(self.btn_update)
        
        main_vbox.addLayout(top_bar)

        self.tabs = QTabWidget()
        main_vbox.addWidget(self.tabs)

        # ======================================================================
        # TAB 1: ĐIỀU KHIỂN
        # ======================================================================
        tab_control = QWidget()
        main_layout = QVBoxLayout(tab_control)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)
        self.tabs.addTab(tab_control, "Điều khiển")

        # ----------------------------------------------------------------------
        # 1. HEADER BANNER CARD
        # ----------------------------------------------------------------------
        header_card = QFrame()
        header_card.setObjectName("HeaderCard")
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(20, 16, 20, 16)

        title_box = QVBoxLayout()
        title_box.setSpacing(4)

        lbl_title = QLabel("⚡ WorkFlow ERP iGP - Automation Bot v3.0")
        lbl_title.setObjectName("HeaderTitle")
        lbl_sub = QLabel("Hệ thống tự động hóa nhập chứng từ Google Sheets (Chỉ & Nhựa) • Tài khoản: 51225")
        lbl_sub.setObjectName("HeaderSub")

        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        header_layout.addLayout(title_box)

        header_layout.addStretch()

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

        lbl_sec1 = QLabel("📊 Spreadsheet Configuration")
        lbl_sec1.setObjectName("SectionTitle")
        sheets_layout.addWidget(lbl_sec1)

        # Segmented Pills: Sheet Select
        lbl_sheet_tag = QLabel("Target Sheet:")
        lbl_sheet_tag.setObjectName("FormLabel")
        sheets_layout.addWidget(lbl_sheet_tag)

        pill_sheet_layout = QHBoxLayout()
        pill_sheet_layout.setSpacing(10)

        self.btn_sheet_chi = QPushButton("📄 ERP Chỉ")
        self.btn_sheet_chi.setObjectName("PillActive")
        self.btn_sheet_chi.setCursor(Qt.PointingHandCursor)
        self.btn_sheet_chi.clicked.connect(lambda: self._set_sheet("ERP Chỉ"))

        self.btn_sheet_nhua = QPushButton("📦 ERP Nhựa")
        self.btn_sheet_nhua.setObjectName("PillInactive")
        self.btn_sheet_nhua.setCursor(Qt.PointingHandCursor)
        self.btn_sheet_nhua.clicked.connect(lambda: self._set_sheet("ERP Nhựa"))

        pill_sheet_layout.addWidget(self.btn_sheet_chi)
        pill_sheet_layout.addWidget(self.btn_sheet_nhua)
        sheets_layout.addLayout(pill_sheet_layout)

        # Category Dropdown
        lbl_cat_tag = QLabel("Category Filter:")
        lbl_cat_tag.setObjectName("FormLabel")
        sheets_layout.addWidget(lbl_cat_tag)

        self.cbo_category = QComboBox()
        self.cbo_category.setCursor(Qt.PointingHandCursor)
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

        lbl_sec2 = QLabel("📅 Execution Range")
        lbl_sec2.setObjectName("SectionTitle")
        range_layout.addWidget(lbl_sec2)

        # Segmented Pills: Mode Select
        lbl_mode_tag = QLabel("Mode Selection:")
        lbl_mode_tag.setObjectName("FormLabel")
        range_layout.addWidget(lbl_mode_tag)

        pill_mode_layout = QHBoxLayout()
        pill_mode_layout.setSpacing(8)

        self.btn_mode_single = QPushButton("📌 1 Ngày")
        self.btn_mode_single.setObjectName("PillActive")
        self.btn_mode_single.setCursor(Qt.PointingHandCursor)
        self.btn_mode_single.clicked.connect(lambda: self._set_date_mode("single"))

        self.btn_mode_range = QPushButton("📅 Khoảng Ngày")
        self.btn_mode_range.setObjectName("PillInactive")
        self.btn_mode_range.setCursor(Qt.PointingHandCursor)
        self.btn_mode_range.clicked.connect(lambda: self._set_date_mode("range"))

        self.btn_mode_all = QPushButton("🗓️ Cả Tháng")
        self.btn_mode_all.setObjectName("PillInactive")
        self.btn_mode_all.setCursor(Qt.PointingHandCursor)
        self.btn_mode_all.clicked.connect(lambda: self._set_date_mode("all"))

        pill_mode_layout.addWidget(self.btn_mode_single)
        pill_mode_layout.addWidget(self.btn_mode_range)
        pill_mode_layout.addWidget(self.btn_mode_all)
        range_layout.addLayout(pill_mode_layout)

        # Stepper Row
        self.stepper_container = QWidget()
        stepper_layout = QHBoxLayout(self.stepper_container)
        stepper_layout.setContentsMargins(0, 4, 0, 0)
        stepper_layout.setSpacing(10)

        self.lbl_day_start = QLabel("Ngày chọn:")
        self.lbl_day_start.setObjectName("FormLabel")
        self.spn_start = QSpinBox()
        self.spn_start.setRange(1, 31)
        self.spn_start.setValue(24)
        self.spn_start.setFixedWidth(70)

        self.lbl_day_end = QLabel("Đến ngày:")
        self.lbl_day_end.setObjectName("FormLabel")
        self.spn_end = QSpinBox()
        self.spn_end.setRange(1, 31)
        self.spn_end.setValue(31)
        self.spn_end.setFixedWidth(70)

        stepper_layout.addWidget(self.lbl_day_start)
        stepper_layout.addWidget(self.spn_start)
        stepper_layout.addWidget(self.lbl_day_end)
        stepper_layout.addWidget(self.spn_end)
        stepper_layout.addStretch()

        range_layout.addWidget(self.stepper_container)
        
        # Checkbox: Bỏ qua các bước mở màn hình (Chạy thẳng Bước 4)
        self.chk_skip_open = QCheckBox(" Đã mở sẵn màn hình nhập liệu (Chạy thẳng Bước 4)")
        self.chk_skip_open.setObjectName("FormLabel")
        self.chk_skip_open.setStyleSheet("QCheckBox { font-weight: bold; color: #E0E0E0; margin-top: 5px; } QCheckBox::indicator { width: 16px; height: 16px; }")
        self.chk_skip_open.setChecked(True)
        range_layout.addWidget(self.chk_skip_open)

        self._update_stepper_visibility()

        range_layout.addStretch()
        grid_config.addWidget(card_range)

        main_layout.addLayout(grid_config)

        # ----------------------------------------------------------------------
        # 3. THREE SLEEK ACTION BUTTONS
        # ----------------------------------------------------------------------
        action_layout = QHBoxLayout()
        action_layout.setSpacing(12)

        self.btn_run = QPushButton("🚀   BẮT ĐẦU CHẠY BOT")
        self.btn_run.setObjectName("BtnRun")
        self.btn_run.setCursor(Qt.PointingHandCursor)
        self.btn_run.clicked.connect(self.start_bot)

        self.btn_dry_run = QPushButton("🧪   CHẠY THỬ (DRY-RUN)")
        self.btn_dry_run.setObjectName("BtnDryRun")
        self.btn_dry_run.setCursor(Qt.PointingHandCursor)
        self.btn_dry_run.clicked.connect(self.start_dry_run)

        self.btn_stop = QPushButton("🛑   DỪNG KHẨN CẤP (Esc / Ctrl+Q)")
        self.btn_stop.setObjectName("BtnStop")
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.clicked.connect(self.stop_bot)

        self.btn_pause = QPushButton("⏸   TẠM DỪNG (Pause)")
        self.btn_pause.setObjectName("BtnPause")
        self.btn_pause.setCursor(Qt.PointingHandCursor)
        self.btn_pause.clicked.connect(self.pause_resume_bot)
        self.btn_pause.setEnabled(False)

        action_layout.addWidget(self.btn_run, 2)
        action_layout.addWidget(self.btn_dry_run, 2)
        action_layout.addWidget(self.btn_stop, 2)
        action_layout.addWidget(self.btn_pause, 2)

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
        lbl_log_title = QLabel("💻 Nhật Ký Thực Thi Trực Tiếp (Live Console Stream)")
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

        # Token Telegram
        lbl_tele = QLabel("Cài đặt Telegram (Token & Chat ID):")
        lbl_tele.setFont(QFont("Segoe UI", 11, QFont.Bold))
        settings_layout.addWidget(lbl_tele)
        
        tele_form = QGridLayout()
        tele_form.addWidget(QLabel("Bot Token:"), 0, 0)
        self.txt_tele_token = QLineEdit()
        self.txt_tele_token.setPlaceholderText("Nhập HTTP API Token của Bot...")
        tele_form.addWidget(self.txt_tele_token, 0, 1)

        tele_form.addWidget(QLabel("Chat ID:"), 1, 0)
        self.txt_tele_chatid = QLineEdit()
        self.txt_tele_chatid.setPlaceholderText("Nhập ID người nhận báo cáo...")
        tele_form.addWidget(self.txt_tele_chatid, 1, 1)
        
        settings_layout.addLayout(tele_form)
        
        lbl_snip = QLabel("Công cụ Ảnh Mẫu & Tọa Độ (Snipping Tool):")
        lbl_snip.setFont(QFont("Segoe UI", 11, QFont.Bold))
        settings_layout.addWidget(lbl_snip)
        
        btn_snip = QPushButton("✂  Chụp Ảnh / Lấy Tọa Độ")
        btn_snip.setFixedSize(200, 36)
        btn_snip.clicked.connect(self._start_snipping)
        settings_layout.addWidget(btn_snip)
        
        
        btn_save_config = QPushButton("Lưu Cài Đặt")
        btn_save_config.setFixedSize(120, 36)
        btn_save_config.clicked.connect(self._save_config)
        settings_layout.addWidget(btn_save_config)
        settings_layout.addStretch()

        self.tabs.addTab(tab_settings, "Cài đặt (Settings)")
        
        # Load existing config into text boxes
    def _setup_profiles(self):
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
        self._load_config_to_ui()

    def _on_profile_changed(self, index):
        profile_name = self.combo_profile.currentText()
        if not profile_name:
            return
            
        # Update config active profile
        config = load_config()
        full_config = config.get("_full_config", {})
        full_config["active_profile"] = profile_name
        
        with open("config.json", "w", encoding="utf-8") as f:
            import json
            json.dump(full_config, f, indent=4, ensure_ascii=False)
            
        # Tải lại UI cho profile mới
        self._load_config_to_ui()
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
                    self.btn_update.setText("🔄 Cập Nhật (Update)")
                    self.btn_update.setEnabled(True)
            else:
                QMessageBox.information(self, "Auto-Update", "Bạn đang sử dụng phiên bản mới nhất!")
                self.btn_update.setText("🔄 Cập Nhật (Update)")
                self.btn_update.setEnabled(True)
        except Exception as e:
            QMessageBox.warning(self, "Lỗi", f"Không thể kiểm tra cập nhật: {e}")
            self.btn_update.setText("🔄 Cập Nhật (Update)")
            self.btn_update.setEnabled(True)

    def _load_config_to_ui(self):
        config = load_config()
        self.txt_tele_token.setText(config.get("telegram_bot_token", ""))
        self.txt_tele_chatid.setText(config.get("telegram_chat_id", ""))

    def _save_config(self):
        config = load_config()
        full_config = config.get("_full_config", config)
        active = config.get("_active_profile")
        
        if "profiles" in full_config and active in full_config["profiles"]:
            full_config["profiles"][active]["telegram_bot_token"] = self.txt_tele_token.text().strip()
            full_config["profiles"][active]["telegram_chat_id"] = self.txt_tele_chatid.text().strip()
        else:
            full_config["telegram_bot_token"] = self.txt_tele_token.text().strip()
            full_config["telegram_chat_id"] = self.txt_tele_chatid.text().strip()
            
        with open("config.json", "w", encoding="utf-8") as f:
            import json
            json.dump(full_config, f, indent=4, ensure_ascii=False)
        QMessageBox.information(self, "Thành công", f"Đã lưu cài đặt Telegram cho Profile: {active or 'Mặc định'}!")

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
        if sheet_name == "ERP Chỉ":
            self.btn_sheet_chi.setObjectName("PillActive")
            self.btn_sheet_nhua.setObjectName("PillInactive")
        else:
            self.btn_sheet_chi.setObjectName("PillInactive")
            self.btn_sheet_nhua.setObjectName("PillActive")

        self.btn_sheet_chi.setStyle(self.btn_sheet_chi.style())
        self.btn_sheet_nhua.setStyle(self.btn_sheet_nhua.style())
        self._update_category_options(sheet_name)

    def _update_category_options(self, sheet_name):
        self.cbo_category.clear()
        if sheet_name == "ERP Chỉ":
            cats = ["XUẤT", "NHẬP", "XUẤT TRẢ X1", "XUẤT TRẢ", "XUẤT BÁN", "GIA CÔNG", "NHẬP FOR", "FOR XUẤT"]
        else:
            cats = ["XUẤT", "NHẬP NHỰA", "NHẬP TÁI CHẾ", "NHẬP MÀU", "XUẤT FOR", "FOR NHẬP"]
        self.cbo_category.addItems(cats)

    def _set_date_mode(self, mode):
        self.date_mode = mode
        buttons = [
            ("single", self.btn_mode_single),
            ("range", self.btn_mode_range),
            ("all", self.btn_mode_all)
        ]
        for m_name, btn in buttons:
            btn.setObjectName("PillActive" if m_name == mode else "PillInactive")
            btn.setStyle(btn.style())

        self._update_stepper_visibility()

    def _update_stepper_visibility(self):
        if self.date_mode == "single":
            self.stepper_container.setVisible(True)
            self.lbl_day_start.setText("Ngày chọn:")
            self.spn_start.setVisible(True)
            self.lbl_day_end.setVisible(False)
            self.spn_end.setVisible(False)
        elif self.date_mode == "range":
            self.stepper_container.setVisible(True)
            self.lbl_day_start.setText("Từ ngày:")
            self.spn_start.setVisible(True)
            self.lbl_day_end.setVisible(True)
            self.spn_end.setVisible(True)
        else:
            self.stepper_container.setVisible(False)

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

    def start_bot(self):
        self._execute(dry_run=False)

    def start_dry_run(self):
        self._execute(dry_run=True)

    def pause_resume_bot(self):
        if hasattr(self, 'is_paused') and self.is_paused:
            self.is_paused = False
            self.btn_pause.setText("⏸   TẠM DỪNG (Pause)")
            self.update_status_badge("running")
            # Note: actual pause requires worker thread to check this flag
        else:
            self.is_paused = True
            self.btn_pause.setText("▶   TIẾP TỤC (Resume)")
            self.update_status_badge("paused")

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
        days_to_run = []
        if self.date_mode == "single":
            days_to_run = [self.spn_start.value()]
        elif self.date_mode == "range":
            d_start = self.spn_start.value()
            d_end = self.spn_end.value()
            if d_start > d_end:
                QMessageBox.critical(self, "Error", "Start Day cannot be greater than End Day!")
                return
            days_to_run = list(range(d_start, d_end + 1))
        else:
            days_to_run = None

        skip_open = self.chk_skip_open.isChecked()

        self.is_running = True
        self.update_status_badge("running")
        self.btn_run.setEnabled(False)
        self.btn_dry_run.setEnabled(False)
        self.btn_pause.setEnabled(True)

        self.worker = AutomationWorker(
            sheet_name=sheet_name,
            category=category,
            days_to_run=days_to_run,
            dry_run=dry_run,
            skip_open=skip_open
        )
        self.worker.status_signal.connect(self.update_status_badge)
        self.worker.finished_signal.connect(self._on_worker_finished)
        
        if skip_open:
            # Thu nhỏ cửa sổ Bot xuống Taskbar để nhường không gian cho ERP
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

    def _apply_qss_stylesheet(self):
        qss = """
        /* Main Window & Central Widget */
        QMainWindow, QWidget#CentralWidget {
            background-color: #0A0E17;
        }

        /* Card Containers */
        QFrame#HeaderCard, QFrame#ConfigCard, QFrame#LogCard {
            background-color: #111827;
            border: 1px solid #1E293B;
            border-radius: 12px;
        }

        /* Typography */
        QLabel#HeaderTitle {
            color: #F8FAFC;
            font-size: 17px;
            font-weight: bold;
        }
        QLabel#HeaderSub {
            color: #64748B;
            font-size: 11px;
        }
        QLabel#SectionTitle {
            color: #F8FAFC;
            font-size: 13px;
            font-weight: bold;
        }
        QLabel#FormLabel {
            color: #94A3B8;
            font-size: 12px;
        }
        QLabel#FooterTip {
            color: #64748B;
            font-size: 11px;
        }

        /* Status Badges */
        QLabel#StatusBadgeReady {
            background-color: #064E3B;
            color: #00E5FF;
            font-size: 12px;
            font-weight: bold;
            padding: 6px 14px;
            border-radius: 14px;
        }
        QLabel#StatusBadgeRunning {
            background-color: #1E3A8A;
            color: #60A5FA;
            font-size: 12px;
            font-weight: bold;
            padding: 6px 14px;
            border-radius: 14px;
        }
        QLabel#StatusBadgeStopped {
            background-color: #7F1D1D;
            color: #FCA5A5;
            font-size: 12px;
            font-weight: bold;
            padding: 6px 14px;
            border-radius: 14px;
        }

        /* Segmented Toggle Pills */
        QPushButton#PillActive {
            background-color: #042F2E;
            color: #00E5FF;
            border: 1px solid #00E5FF;
            border-radius: 8px;
            font-size: 12px;
            font-weight: bold;
            padding: 7px 14px;
        }
        QPushButton#PillInactive {
            background-color: #0F172A;
            color: #94A3B8;
            border: 1px solid #1E293B;
            border-radius: 8px;
            font-size: 12px;
            padding: 7px 14px;
        }
        QPushButton#PillInactive:hover {
            border-color: #334155;
            color: #F8FAFC;
        }

        /* Inputs: Dropdown & SpinBox */
        QComboBox, QSpinBox {
            background-color: #0F172A;
            color: #F8FAFC;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 6px 10px;
            font-size: 12px;
            font-weight: bold;
        }
        QComboBox:hover, QSpinBox:hover {
            border-color: #00E5FF;
        }
        QComboBox::drop-down {
            border: none;
            width: 24px;
        }
        QComboBox QAbstractItemView {
            background-color: #0F172A;
            color: #F8FAFC;
            selection-background-color: #1E293B;
            selection-color: #00E5FF;
            border: 1px solid #334155;
            padding: 4px;
        }

        /* Main Action Buttons */
        QPushButton#BtnRun {
            background-color: #042F2E;
            color: #00E5FF;
            border: 1px solid #00E5FF;
            border-radius: 10px;
            font-size: 13px;
            font-weight: bold;
            padding: 12px;
        }
        QPushButton#BtnRun:hover {
            background-color: #0F766E;
            color: #FFFFFF;
        }
        QPushButton#BtnRun:disabled {
            background-color: #1E293B;
            color: #64748B;
            border-color: #334155;
        }

        QPushButton#BtnDryRun {
            background-color: #0F172A;
            color: #94A3B8;
            border: 1px solid #334155;
            border-radius: 10px;
            font-size: 13px;
            font-weight: bold;
            padding: 12px;
        }
        QPushButton#BtnDryRun:hover {
            background-color: #1E293B;
            color: #FFFFFF;
            border-color: #64748B;
        }
        QPushButton#BtnDryRun:disabled {
            background-color: #1E293B;
            color: #64748B;
            border-color: #334155;
        }

        QPushButton#BtnStop {
            background-color: #450A0A;
            color: #FCA5A5;
            border: 1px solid #EF4444;
            border-radius: 10px;
            font-size: 13px;
            font-weight: bold;
            padding: 12px;
        }
        QPushButton#BtnStop:hover {
            background-color: #991B1B;
            color: #FFFFFF;
        }

        /* Console Stream */
        QTextEdit#ConsoleStream {
            background-color: #060911;
            color: #F8FAFC;
            border: 1px solid #1E293B;
            border-radius: 8px;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 12px;
            padding: 10px;
        }
        """
        self.setStyleSheet(qss)


def main():
    # Windows Taskbar Icon Fix
    try:
        import ctypes
        myappid = 'mycompany.botmanager.igp.pyside.3.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
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
