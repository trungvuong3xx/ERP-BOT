import logging
import gspread
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials

logger = logging.getLogger("ERPAutomation.Sheets")

class GoogleSheetsHandler:
    """Xử lý kết nối và đọc/ghi dữ liệu với Google Sheets qua Service Account."""
    
    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    def __init__(self, credentials_path: str, spreadsheet_title: str):
        self.credentials_path = credentials_path
        self.spreadsheet_title = spreadsheet_title
        self.client = None
        self.spreadsheet = None

    def connect(self):
        """Khởi tạo kết nối tới Google Sheets API."""
        try:
            logger.info(f"Đang kết nối Google Sheets với tệp xác thực: {self.credentials_path}")
            creds = Credentials.from_service_account_file(self.credentials_path, scopes=self.SCOPES)
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open(self.spreadsheet_title)
            logger.info(f"Kết nối thành công tới bảng tính: '{self.spreadsheet.title}'")
            return True
        except Exception as e:
            logger.error(f"Lỗi kết nối Google Sheets: {e}", exc_info=True)
            raise

    def fetch_unprocessed_items(self, sheet_name: str, category_filter: str = None):
        """
        Đọc và phân tích danh sách dữ liệu từ trang tính ERP.
        Mỗi cột Ngày (1..31) tương ứng với 3 cột: Mã, Quy cách/Tên, Số lượng/Khối lượng.
        Có thể lọc theo loại danh mục (ví dụ: 'XUẤT' hoặc 'NHẬP').
        """
        if not self.spreadsheet:
            self.connect()

        try:
            ws = self.spreadsheet.worksheet(sheet_name)
            all_rows = ws.get_all_values()
            logger.info(f"Đã tải {len(all_rows)} dòng từ trang tính '{sheet_name}'")

            if len(all_rows) < 3:
                logger.warning(f"Trang tính '{sheet_name}' không đủ dữ liệu.")
                return []

            all_unfmt_rows = ws.get_all_values(value_render_option='UNFORMATTED_VALUE')
            
            # Đọc giá trị Ngày / Tháng / Năm thực tế từ Hàng 2 (Row 2)
            row2_unfmt = all_unfmt_rows[1] if len(all_unfmt_rows) > 1 else []
            day_dates = {}
            for d in range(1, 32):
                c_idx = 1 + (d - 1) * 3
                if c_idx < len(row2_unfmt):
                    raw_val = row2_unfmt[c_idx]
                    try:
                        # Chuyển đổi số sê-ri ngày của Excel/Google Sheets (VD: 46227 -> 2026/07/24)
                        if isinstance(raw_val, (int, float)) and raw_val > 40000:
                            dt = datetime(1899, 12, 30) + timedelta(days=int(raw_val))
                            day_dates[d] = dt.strftime("%Y/%m/%d")
                        elif isinstance(raw_val, str) and "/" in raw_val:
                            day_dates[d] = raw_val.strip()
                    except Exception:
                        pass
                
                # Giá trị dự phòng nếu không đọc được số sê-ri
                if d not in day_dates:
                    day_dates[d] = f"2026/07/{d:02d}"

            all_formulas = ws.get_all_values(value_render_option='FORMULA')

            items = []
            day_cols = {d: 1 + (d - 1) * 3 for d in range(1, 32)}

            # Quản lý tập hợp các ngày đã chạm công thức TỔNG (=SUM...) của danh mục hiện tại
            stopped_days_by_cat = {}

            current_category = "NHẬP"
            for r_idx, row in enumerate(all_rows[2:], start=3):
                if not row:
                    continue

                first_cell = row[0].strip() if len(row) > 0 else ""
                # Danh sách đầy đủ tất cả các tên Danh mục trên sheet ERP Chỉ và ERP Nhựa
                KNOWN_CATEGORIES = [
                    "NHẬP", "XUẤT", "XUẤT TRẢ X1", "XUẤT TRẢ XI", "XUẤT TRẢ", "XUẤT BÁN",
                    "NHẬP FOR", "FOR XUẤT", "XUẤT FOR", "FOR NHẬP", "XUẤT BÌNH THUẬN",
                    "NHẬP TRẢ X5", "NHẬP TRẢ X1", "GIA CÔNG", "BÁN PHẾ",
                    "NHẬP NHỰA", "NHẬP TÁI CHẾ", "NHẬP MÀU", "NHẬP TOYO", "NHẬP VẢI PP", "NHẬP TƠ",
                    "XUẤT VẢI PP", "XUẤT TƠ"
                ]
                if first_cell in KNOWN_CATEGORIES:
                    current_category = first_cell

                if current_category not in stopped_days_by_cat:
                    stopped_days_by_cat[current_category] = set()

                if category_filter and current_category != category_filter:
                    continue

                for day, c_idx in day_cols.items():
                    # Nếu ngày này trong danh mục này đã đụng công thức TỔNG thì dừng không đọc nữa
                    if day in stopped_days_by_cat[current_category]:
                        continue

                    if c_idx + 2 < len(row):
                        code = row[c_idx].strip()
                        spec = row[c_idx + 1].strip()
                        qty = row[c_idx + 2].strip()

                        # Kiểm tra xem ô Số lượng có chứa công thức TỔNG (SUM hoặc SUMPRODUCT) hay không
                        qty_formula = ""
                        if r_idx - 1 < len(all_formulas) and c_idx + 2 < len(all_formulas[r_idx - 1]):
                            qty_formula = str(all_formulas[r_idx - 1][c_idx + 2]).strip().upper()

                        if "SUM(" in qty_formula or "SUMPRODUCT(" in qty_formula or "=SUM" in qty_formula:
                            logger.info(f"--> DỪNG LẤY DỮ LIỆU NGÀY {day} TRÊN {sheet_name} FOR '{current_category}' (HÀNG {r_idx}) VÌ GẶP CÔNG THỨC TỔNG: '{qty_formula}'")
                            stopped_days_by_cat[current_category].add(day)
                            continue

                        # Bỏ qua dòng trống, 'Không có', hoặc giá trị lỗi công thức (#N/A, #REF!, v.v.)
                        if code and code not in ["Không có", "#N/A", "#REF!", "#VALUE!", "#NAME?", "#DIV/0!"]:
                            
                            # --- Data Validation ---
                            is_valid = True
                            try:
                                qty_val = float(str(qty).replace(',', ''))
                                if qty_val <= 0:
                                    is_valid = False
                            except ValueError:
                                is_valid = False
                            
                            if not is_valid:
                                logger.warning(f"Bỏ qua dòng {r_idx} do Lỗi Dữ Liệu: Mã='{code}', Số lượng='{qty}' không hợp lệ (phải > 0).")
                                # Ghi chú lỗi trực tiếp vào ô số lượng hoặc ô ghi chú (ở đây ghi đè tạm vào ô SL)
                                # self.mark_as_imported(sheet_name, r_idx, c_idx + 3, f"LỖI: {qty}")
                                continue
                            # -----------------------

                            items.append({
                                "sheet_name": sheet_name,
                                "category": current_category,
                                "day": day,
                                "date_str": day_dates.get(day, f"2026/07/{day:02d}"),
                                "row": r_idx,
                                "col_code": c_idx + 1,
                                "col_spec": c_idx + 2,
                                "col_qty": c_idx + 3,
                                "code": code,
                                "spec_or_name": spec,
                                "quantity": qty,
                                "status": "Chờ nhập"
                            })

            logger.info(f"Tìm thấy tổng cộng {len(items)} mục dữ liệu trên '{sheet_name}'")
            return items

        except Exception as e:
            logger.error(f"Lỗi khi đọc dữ liệu từ sheet '{sheet_name}': {e}", exc_info=True)
            return []

    def mark_as_imported(self, sheet_name: str, row: int, col: int, note: str = "Đã nhập ERP"):
        """Đánh dấu trạng thái 'Đã nhập ERP' lên Google Sheet."""
        try:
            ws = self.spreadsheet.worksheet(sheet_name)
            ws.update_cell(row, col, note)
            logger.info(f"Đã cập nhật trạng thái '{note}' tại Sheet '{sheet_name}' Row {row}, Col {col}")
            return True
        except Exception as e:
            logger.error(f"Lỗi cập nhật trạng thái lên Google Sheet: {e}", exc_info=True)
            return False

    def write_erp_export_data(self, data_list, sheet_name="Báo Cáo Tồn Kho ERP"):
        """Tính năng đồng bộ ngược (ERP -> Google Sheets)"""
        if not self.spreadsheet:
            self.connect()
            
        try:
            # Kiểm tra xem sheet đã tồn tại chưa, nếu chưa thì tạo mới
            try:
                ws = self.spreadsheet.worksheet(sheet_name)
                # Clear content
                ws.clear()
            except Exception:
                ws = self.spreadsheet.add_worksheet(title=sheet_name, rows="1000", cols="20")
                
            # Ghi dữ liệu dạng bảng
            if data_list:
                ws.update('A1', data_list)
                logger.info(f"Đã đồng bộ {len(data_list)} dòng báo cáo lên Google Sheets '{sheet_name}'")
            return True
        except Exception as e:
            logger.error(f"Lỗi đồng bộ báo cáo lên Google Sheets: {e}", exc_info=True)
            return False
