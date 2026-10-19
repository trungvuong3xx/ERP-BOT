import sys
import os
import json
import time
import argparse
import logging

# Thiết lập đường dẫn import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Heavy modules are lazy-loaded inside run_automation() to speed up app startup

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
    
        for p in candidates:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        config_data = json.load(f)
                    break
                except Exception:
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


def run_automation(dry_run=False, login_only=False, sheet_only=False, process_name=None, category=None, day=None, sheet_name=None, skip_open=False, month=8, year=2026):
    from google_sheets import GoogleSheetsHandler
    from erp_gui import ERPGUIController
    
    
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

    if sys.stdout is not None:
        print("=" * 65)
        print("  CẢNH BÁO DỪNG KHẨN CẤP (EMERGENCY STOP):")
        print("  1. Di chuyển nhanh con trỏ chuột về GÓC TRÊN BÊN TRÁI MÀN HÌNH (0,0)")
        print("  2. Hoặc bấm tổ hợp phím Ctrl + C trong cửa sổ Command Prompt này.")
        print("=" * 65)

    if not dry_run and not sheet_only:
        logger.info("Robot sẽ bắt đầu thao tác sau 3 giây. Vui lòng không chạm chuột/bàn phím...")
        time.sleep(3)

    # Determine configuration based on process_name
    is_copmi08 = (process_name == "COPMI08" or sheet_name == "BTP")
    is_custom_macro = process_name not in ["Xuất kho (INVI08)", "Nhập kho (PURMI09)", "INVI08", "PURMI09", "COPMI08"]
    is_import = (process_name in ["Nhập kho (PURMI09)", "PURMI09"])
    
    gs_title_key = "import_spreadsheet_title" if is_import else "spreadsheet_title"
    gs_sheets_key = "import_sheets" if is_import else "sheets"
    
    chi_items = []
    nhua_items = []
    btp_items = []
    btp_date_str = "2026/10/19"

    # 1. Đọc dữ liệu từ Google Sheets
    if is_copmi08:
        sheets_handler = GoogleSheetsHandler(
            credentials_path=config.get("google_credentials_path", "credentials.json"),
            spreadsheet_title="BTP"
        )
        btp_id = config.get("btp_spreadsheet_id", "1KlAdGFca-FCmTrzPrjCMUMK2pTOfMHxFFH-keCkdr1A")
        btp_sheet = config.get("btp_sheet_name", "Tổng Hợp")
        try:
            btp_date_str, btp_items = sheets_handler.fetch_btp_items(spreadsheet_id=btp_id, sheet_name=btp_sheet)
            logger.info(f"[COPMI08] Đã lấy thành công {len(btp_items)} mục từ bảng 'BTP' (Ngày: {btp_date_str}).")
        except Exception as e:
            logger.error(f"Lỗi khi đọc bảng BTP: {e}")
            if not login_only and not dry_run:
                raise RuntimeError(f"Không thể kết nối hoặc đọc Google Sheets BTP: {e}")
    else:
        sheets_handler = GoogleSheetsHandler(
            credentials_path=config.get("google_credentials_path", "credentials.json"),
            spreadsheet_title=config.get(gs_title_key, "ERP và BÁO CÁO")
        )
        
        sheet_chi_name = config.get(gs_sheets_key, {}).get("chi", "ERP Chỉ")
        sheet_nhua_name = config.get(gs_sheets_key, {}).get("nhua", "ERP Nhựa")
        
        try:
            sheets_handler.connect()
            
            import concurrent.futures
            
            def fetch_chi():
                if not sheet_name or sheet_name == sheet_chi_name:
                    return sheets_handler.fetch_unprocessed_items(sheet_chi_name, category_filter=category, day_filter=day)
                return []
                
            def fetch_nhua():
                if not sheet_name or sheet_name == sheet_nhua_name:
                    return sheets_handler.fetch_unprocessed_items(sheet_nhua_name, category_filter=category, day_filter=day)
                return []

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                future_chi = executor.submit(fetch_chi)
                future_nhua = executor.submit(fetch_nhua)
                
                chi_items = future_chi.result()
                nhua_items = future_nhua.result()
            
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
        exe_path=config.get("erp_exe_path", "C:\\ERP\\ERP.exe"),
        account=config.get("erp_account", ""),
        password=config.get("erp_password", "")
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

    # 3. Thực thi nhập chứng từ
    if is_copmi08:
        default_coords_copmi08 = {
            "header_doc_type": [167, 198],
            "first_row_code": [341, 513],
            "doc_type_val": "A234",
            "customer_val": "VN0003"
        }
        coords = config.get("coords_copmi08", default_coords_copmi08)
        if dry_run:
            logger.info(f"--> [Dry-run COPMI08] Tìm thấy {len(btp_items)} dòng cho ngày {btp_date_str}. Bỏ qua bấm phím thực tế.")
            return

        gui_controller.process_copmi08_voucher(
            date_str=btp_date_str,
            items=btp_items,
            coords=coords
        )
        logger.info("=== HOÀN TẤT TOÀN BỘ QUY TRÌNH TỰ ĐỘNG HÓA COPMI08 ===")
        return

    default_coords_invi08 = {
        "open_invi08": [1095, 337],
        "btn_add": [21, 126],
        "transfer_type_field": [197, 202],
        "item_code_first": [166, 535],
        "item_qty_first": [500, 535],
        "item_warehouse_first": [1440, 535]
    }
    
    default_coords_purmi09 = {
        "open_purmi09": [800, 250],
        "btn_add": [27, 130],
        "supplier_field": [170, 197],
        "item_code_first": [377, 482],
        "item_qty_first": [638, 482]
    }

    coords = config.get("coords_purmi09", default_coords_purmi09) if is_import else config.get("coords_invi08", default_coords_invi08)
    defaults = config.get("purmi09_defaults", {}) if is_import else config.get("invi08_defaults", {})

    # Nhóm danh sách theo từng ngày
    days_map = {}
    for item in chi_items + nhua_items:
        d = item["day"]
        if d not in days_map:
            days_map[d] = []
        days_map[d].append(item)

    for d in sorted(days_map.keys()):
        day_items = days_map[d]
        date_str = day_items[0].get('date_str', f"{year}/{int(month):02d}/{d:02d}")
        logger.info(f"--> Bắt đầu tạo chứng từ cho Ngày {d} (Ngày thực tế từ Sheet: {date_str}) với {len(day_items)} dòng...")
        
        if dry_run:
            logger.info(f"--> Dry-run Ngày {d}: Bỏ qua bấm phím thực tế.")
            continue

        try:
            if is_import:
                gui_controller.process_purmi09_voucher(
                    date_str=date_str,
                    items_for_day=day_items,
                    coords=coords,
                    defaults=defaults,
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
        except Exception as e:
            logger.error(f"Lỗi khi xử lý chứng từ ngày {d}: {e}")
            raise e

    logger.info("=== HOÀN TẤT TOÀN BỘ QUY TRÌNH TỰ ĐỘNG HÓA ===")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chương trình tự động hóa nhập liệu Google Sheets vào WorkFlow ERP iGP")
    parser.add_argument("--process", type=str, default=None, help="Tên quy trình (INVI08, PURMI09, COPMI08)")
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
        run_automation(process_name=args.process, dry_run=args.dry_run, login_only=args.login_only, sheet_only=args.sheet_only, category=args.category, day=args.day, sheet_name=args.sheet_name, skip_open=args.skip_open, month=args.month, year=args.year)
