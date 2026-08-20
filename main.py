import sys
import os
import json
import time
import argparse
import logging

# Thiết lập đường dẫn import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from google_sheets import GoogleSheetsHandler
from erp_gui import ERPGUIController
from notifier import TelegramNotifier
from database import BotDatabase

def setup_logging(log_file="app.log"):
    """Cấu hình ghi nhật ký (logging) tiêu chuẩn."""
    log_format = "%(asctime)s [%(levelname)s] [%(name)s]: %(message)s"
    handlers = [logging.FileHandler(log_file, encoding="utf-8")]
    if sys.stdout is not None:
        handlers.append(logging.StreamHandler(sys.stdout))
    
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(level=logging.INFO, format=log_format, handlers=handlers)

def load_config(config_path="config.json", profile_name=None):
    """Tải tệp cấu hình JSON với cơ chế tìm kiếm thông minh nhiều vị trí."""
    config_data = None
    if os.path.isabs(config_path) and os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
    else:
        candidates = []
        if hasattr(sys, "_MEIPASS"):
            candidates.append(os.path.join(sys._MEIPASS, config_path))
        if hasattr(sys, "executable") and sys.executable:
            candidates.append(os.path.join(os.path.dirname(sys.executable), config_path))
        candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), config_path))
        candidates.append(os.path.join(os.getcwd(), config_path))
        candidates.append(r"C:\Users\Admin\OneDrive\Tài liệu\ERP BOT\erp_automation\config.json")
    
        for p in candidates:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        config_data = json.load(f)
                    break
                except Exception as e:
                    continue

    if config_data is None:
        return {}

    # Xử lý Multi-Profiles
    if "profiles" in config_data:
        active = profile_name or config_data.get("active_profile", list(config_data["profiles"].keys())[0])
        merged = config_data.get("global_settings", {}).copy()
        merged.update(config_data["profiles"].get(active, {}))
        merged["_full_config"] = config_data # keep raw for saving
        merged["_active_profile"] = active
        return merged
    return config_data

def run_automation(dry_run=False, login_only=False, sheet_only=False, category=None, day=None, sheet_name=None, skip_open=False, month=8, year=2026):
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    setup_logging()
    logger = logging.getLogger("ERPAutomation.Main")
    
    logger.info("=== BẮT ĐẦU QUY TRÌNH TỰ ĐỘNG HÓA NHẬP LIỆU ERP IGP ===")
    logger.info(f"Cấu hình ngày tháng: Tháng {month}/{year}")
    if category:
        logger.info(f"Lọc danh mục: '{category}'")
    if day:
        logger.info(f"Lọc riêng Ngày: {day}")
    if sheet_name:
        logger.info(f"Lọc riêng Trang tính: '{sheet_name}'")
    if skip_open:
        logger.info("Chế độ --skip-open: Màn hình INVI08 đã mở sẵn toàn màn hình.")

    config = load_config()

    # Khởi tạo Notifier
    bot_token = config.get("telegram_bot_token", "")
    chat_id = config.get("telegram_chat_id", "")
    notifier = TelegramNotifier(bot_token, chat_id)

    if sys.stdout is not None:
        print("=" * 65)
        print("  CẢNH BÁO DỪNG KHẨN CẤP (EMERGENCY STOP):")
        print("  1. Di chuyển nhanh con trỏ chuột về GÓC TRÊN BÊN TRÁI MÀN HÌNH (0,0)")
        print("  2. Hoặc bấm tổ hợp phím Ctrl + C trong cửa sổ Command Prompt này.")
        print("=" * 65)

    if not dry_run and not sheet_only:
        logger.info("Robot sẽ bắt đầu thao tác sau 3 giây. Vui lòng không chạm chuột/bàn phím...")
        time.sleep(3)

    # 1. Đọc dữ liệu từ Google Sheets
    sheets_handler = GoogleSheetsHandler(
        credentials_path=config["google_credentials_path"],
        spreadsheet_title=config["spreadsheet_title"]
    )
    
    chi_items = []
    nhua_items = []
    
    try:
        sheets_handler.connect()
        if not sheet_name or sheet_name == config["sheets"]["chi"]:
            chi_items = sheets_handler.fetch_unprocessed_items(config["sheets"]["chi"], category_filter=category)
        if not sheet_name or sheet_name == config["sheets"]["nhua"]:
            nhua_items = sheets_handler.fetch_unprocessed_items(config["sheets"]["nhua"], category_filter=category)
        
        if day:
            chi_items = [it for it in chi_items if it.get("day") == int(day)]
            nhua_items = [it for it in nhua_items if it.get("day") == int(day)]

        logger.info(f"Đã lấy thành công {len(chi_items)} mục 'ERP Chỉ' và {len(nhua_items)} mục 'ERP Nhựa'.")
    except Exception as e:
        logger.error(f"Lỗi khi đọc dữ liệu từ Google Sheets: {e}")
        if not login_only and not dry_run:
            raise RuntimeError(f"Không thể kết nối hoặc đọc Google Sheets: {e}")

    if sheet_only:
        logger.info("Chế độ --sheet-only: Đã hoàn tất việc kiểm tra dữ liệu Google Sheet.")
        return

    # 2. Khởi chạy và đăng nhập ERP
    gui_controller = ERPGUIController(
        exe_path=config["erp_exe_path"],
        account=config["erp_account"],
        password=config["erp_password"]
    )

    if not dry_run:
        try:
            _, is_running = gui_controller.launch_or_connect()
            gui_controller.auto_login(was_already_running=is_running)
        except Exception as e:
            logger.error(f"Lỗi khi thao tác ứng dụng ERP: {e}")
            raise RuntimeError(f"Không thể kết nối hoặc đăng nhập ERP: {e}")

    if login_only:
        logger.info("Chế độ --login-only: Hoàn tất đăng nhập ứng dụng ERP.")
        return

    # 3. Thực thi nhập chứng từ INVI08 cho XUẤT
    coords = config.get("coords_invi08", {})
    defaults = config.get("invi08_defaults", {})

    # Nhóm danh sách theo từng ngày và filter bằng DB (Smart Resume)
    db = BotDatabase()
    days_map = {}
    total_skipped = 0
    for item in chi_items + nhua_items:
        date_for_db = item.get('date_str', f"{year}/{int(month):02d}/{item['day']:02d}")
        
        # Check if already processed successfully today
        if db.check_if_success_today(date_for_db, item["sheet_name"], item["code"]):
            logger.info(f"Smart Resume: Bỏ qua mã {item['code']} (Đã thành công trước đó)")
            total_skipped += 1
            continue

        d = item["day"]
        if d not in days_map:
            days_map[d] = []
        days_map[d].append(item)
    
    if total_skipped > 0:
        logger.info(f"Đã bỏ qua {total_skipped} dòng thành công theo lịch sử.")

    for d in sorted(days_map.keys()):
        day_items = days_map[d]
        date_str = day_items[0].get('date_str', f"{year}/{int(month):02d}/{d:02d}")
        logger.info(f"--> Bắt đầu tạo chứng từ cho Ngày {d} (Ngày thực tế từ Sheet: {date_str}) với {len(day_items)} dòng...")
        
        if dry_run:
            logger.info(f"--> Dry-run Ngày {d}: Bỏ qua bấm phím thực tế.")
            continue

        try:
            if category and ("NHẬP FOR" in category.upper() or "FOR NHẬP" in category.upper()):
                gui_controller.process_purmi09_voucher(
                    date_str=date_str,
                    items_for_day=day_items,
                    skip_open=skip_open
                )
            else:
                gui_controller.process_invi08_voucher(
                    date_str=date_str,
                    items_for_day=day_items,
                    coords=coords,
                    defaults=defaults,
                    skip_open=skip_open
                )
            
            # Log success
            for item in day_items:
                _date = item.get('date_str', f"{year}/{int(month):02d}/{d:02d}")
                db.log_item(_date, item["sheet_name"], category or "XUẤT", item["code"], "SUCCESS")
                
        except Exception as e:
            logger.error(f"Lỗi khi xử lý chứng từ ngày {d}: {e}")
            # Log failure
            for item in day_items:
                _date = item.get('date_str', f"{year}/{int(month):02d}/{d:02d}")
                db.log_item(_date, item["sheet_name"], category or "XUẤT", item["code"], "FAILED", str(e))
            raise e

    logger.info("=== HOÀN TẤT TOÀN BỘ QUY TRÌNH TỰ ĐỘNG HÓA ===")
    
    # Gửi báo cáo Telegram
    if not dry_run and not login_only and not sheet_only:
        total = len(chi_items) + len(nhua_items)
        notifier.send_report(
            date_str=f"Tháng {month}/{year}",
            total=total,
            success=total,  # Todo: update success/error count when real tracking is implemented
            error=0
        )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chương trình tự động hóa nhập liệu Google Sheets vào WorkFlow ERP iGP")
    parser.add_argument("--dry-run", action="store_true", help="Chạy thử nghiệm kiểm tra luồng không bấm phím thật trên ERP")
    parser.add_argument("--login-only", action="store_true", help="Chỉ thử nghiệm mở ERP và tự động đăng nhập")
    parser.add_argument("--sheet-only", action="store_true", help="Chỉ thử nghiệm kết nối và đọc dữ liệu Google Sheet")
    parser.add_argument("--category", type=str, default=None, help="Lọc riêng mục 'XUẤT' hoặc 'NHẬP'")
    parser.add_argument("--day", type=int, default=None, help="Chỉ chạy riêng 1 ngày cụ thể (VD: --day 24)")
    parser.add_argument("--sheet-name", type=str, default=None, help="Lọc riêng 1 tab sheet cụ thể (VD: 'ERP Chỉ')")
    parser.add_argument("--skip-open", action="store_true", help="Bỏ qua bước click mở INVI08 và Maximize nếu INVI08 đã mở sẵn lớn toàn màn hình")
    parser.add_argument("--gui", action="store_true", help="Khởi chạy giao diện ứng dụng Desktop GUI")
    parser.add_argument("--month", type=int, default=8, help="Tháng nhập chứng từ (Mặc định: 8)")
    parser.add_argument("--year", type=int, default=2026, help="Năm nhập chứng từ (Mặc định: 2026)")
    args = parser.parse_args()

    # Nếu truyền --gui hoặc không truyền tham số CLI nào -> Mở giao diện App Desktop GUI
    if args.gui or len(sys.argv) == 1:
        from app_gui import main as launch_gui
        launch_gui()
    else:
        run_automation(dry_run=args.dry_run, login_only=args.login_only, sheet_only=args.sheet_only, category=args.category, day=args.day, sheet_name=args.sheet_name, skip_open=args.skip_open, month=args.month, year=args.year)
