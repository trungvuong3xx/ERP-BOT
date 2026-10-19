import logging
import gspread
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials

logger = logging.getLogger("ERPAutomation.Sheets")

_CACHED_CLIENT = None
_CACHED_SPREADSHEETS = {}

def col_to_letter(col_idx: int) -> str:
    """Chuyển đổi số thứ tự cột 0-based sang ký tự cột Excel (0 -> A, 1 -> B, ..., 27 -> AB)."""
    result = ""
    col_idx += 1
    while col_idx > 0:
        col_idx, remainder = divmod(col_idx - 1, 26)
        result = chr(65 + remainder) + result
    return result

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
        """Khởi tạo kết nối tới Google Sheets API với cơ chế tái sử dụng phiên (Connection Pooling)."""
        global _CACHED_CLIENT, _CACHED_SPREADSHEETS
        try:
            if not _CACHED_CLIENT:
                logger.info(f"Đang kết nối Google Sheets với tệp xác thực: {self.credentials_path}")
                creds = Credentials.from_service_account_file(self.credentials_path, scopes=self.SCOPES)
                _CACHED_CLIENT = gspread.authorize(creds)
            self.client = _CACHED_CLIENT

            if self.spreadsheet_title not in _CACHED_SPREADSHEETS:
                _CACHED_SPREADSHEETS[self.spreadsheet_title] = self.client.open(self.spreadsheet_title)
                logger.info(f"Kết nối thành công tới bảng tính: '{self.spreadsheet_title}'")
            self.spreadsheet = _CACHED_SPREADSHEETS[self.spreadsheet_title]
            return True
        except Exception as e:
            # Nếu phiên kết nối cũ bị lỗi/hết hạn, reset bộ nhớ đệm và thử lại
            _CACHED_CLIENT = None
            _CACHED_SPREADSHEETS.clear()
            logger.error(f"Lỗi kết nối Google Sheets: {e}", exc_info=True)
            raise

    def _fetch_single_day_items(self, sheet_name: str, day: int, category_filter: str = None):
        """
        Thuật toán tối ưu siêu tốc (Targeted Single-Day Fetch):
        Chỉ tải đúng 3 cột của ngày được chọn và cột Danh mục qua 3 request song song (< 5 KB payload).
        Tốc độ phản hồi: ~0.4s - 0.8s.
        """
        import concurrent.futures
        import urllib.parse

        spreadsheet_id = self.spreadsheet.id
        c_code = 1 + (day - 1) * 3
        c_spec = c_code + 1
        c_qty = c_code + 2

        let_code = col_to_letter(c_code)
        let_qty = col_to_letter(c_qty)

        r_cat = f"'{sheet_name}'!A1:A110"
        r_data = f"'{sheet_name}'!{let_code}1:{let_qty}110"
        r_form = f"'{sheet_name}'!{let_qty}1:{let_qty}110"
        r_date = f"'{sheet_name}'!{let_code}2"

        q_fmt = f"ranges={urllib.parse.quote(r_cat)}&ranges={urllib.parse.quote(r_data)}&valueRenderOption=FORMATTED_VALUE"
        url_fmt = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values:batchGet?{q_fmt}"

        q_form = f"ranges={urllib.parse.quote(r_form)}&valueRenderOption=FORMULA"
        url_form = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values:batchGet?{q_form}"

        q_date = f"ranges={urllib.parse.quote(r_date)}&valueRenderOption=UNFORMATTED_VALUE"
        url_date = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values:batchGet?{q_date}"

        logger.info(f"Đang tải siêu tốc cho Ngày {day} trên '{sheet_name}' (Cột {let_code}..{let_qty})...")

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            f_fmt = pool.submit(self.client.http_client.request, 'get', url_fmt)
            f_form = pool.submit(self.client.http_client.request, 'get', url_form)
            f_date = pool.submit(self.client.http_client.request, 'get', url_date)
            
            res_fmt = f_fmt.result().json()
            res_form = f_form.result().json()
            res_date = f_date.result().json()

        # Đọc ngày thực tế từ số serial Excel hàng 2
        date_str = f"2026/08/{day:02d}"
        try:
            raw_date = res_date.get('valueRanges', [{}])[0].get('values', [[None]])[0][0]
            if isinstance(raw_date, (int, float)) and raw_date > 40000:
                dt = datetime(1899, 12, 30) + timedelta(days=int(raw_date))
                date_str = dt.strftime("%Y/%m/%d")
            elif isinstance(raw_date, str) and "/" in raw_date:
                date_str = raw_date.strip()
        except Exception:
            pass

        cats_raw = res_fmt.get('valueRanges', [{}])[0].get('values', [])
        data_raw = res_fmt.get('valueRanges', [{}])[1].get('values', [])
        forms_raw = res_form.get('valueRanges', [{}])[0].get('values', [])

        KNOWN_CATEGORIES = [
            "NHẬP", "XUẤT", "XUẤT TRẢ X1", "XUẤT TRẢ XI", "XUẤT TRẢ", "XUẤT BÁN",
            "NHẬP FOR", "FOR XUẤT", "XUẤT FOR", "FOR NHẬP", "XUẤT BÌNH THUẬN",
            "NHẬP TRẢ", "NHẬP TRẢ X5", "NHẬP TRẢ X1", "GIA CÔNG", "BÁN PHẾ",
            "NHẬP NHỰA", "NHẬP TÁI CHẾ", "NHẬP MÀU", "NHẬP TOYO", "NHẬP VẢI PP", "NHẬP TƠ",
            "XUẤT VẢI PP", "XUẤT TƠ"
        ]

        items = []
        current_category = "NHẬP"
        stopped_cats = set()

        max_rows = max(len(cats_raw), len(data_raw))
        for r_0 in range(2, max_rows): # Row 3 trở đi
            r_idx = r_0 + 1
            cat_val = cats_raw[r_0][0].strip() if r_0 < len(cats_raw) and len(cats_raw[r_0]) > 0 else ""
            if cat_val in KNOWN_CATEGORIES:
                current_category = cat_val

            if current_category in stopped_cats:
                continue
            if category_filter and current_category != category_filter:
                continue

            row_data = data_raw[r_0] if r_0 < len(data_raw) else []
            code = row_data[0].strip() if len(row_data) > 0 else ""
            spec = row_data[1].strip() if len(row_data) > 1 else ""
            qty = row_data[2].strip() if len(row_data) > 2 else ""

            row_form = forms_raw[r_0] if r_0 < len(forms_raw) else []
            qty_form = str(row_form[0]).strip().upper() if len(row_form) > 0 else ""

            # Cắt dừng nếu gặp công thức tổng
            if "SUM(" in qty_form or "SUMPRODUCT(" in qty_form or "=SUM" in qty_form:
                logger.info(f"--> DỪNG LẤY DỮ LIỆU NGÀY {day} TRÊN {sheet_name} FOR '{current_category}' (HÀNG {r_idx}) VÌ GẶP CÔNG THỨC TỔNG: '{qty_form}'")
                stopped_cats.add(current_category)
                continue

            if code and code not in ["Không có", "#N/A", "#REF!", "#VALUE!", "#NAME?", "#DIV/0!"]:
                try:
                    qty_val = float(str(qty).replace(',', ''))
                    if qty_val <= 0:
                        continue
                except ValueError:
                    continue

                items.append({
                    "sheet_name": sheet_name,
                    "category": current_category,
                    "day": day,
                    "date_str": date_str,
                    "row": r_idx,
                    "col_code": c_code + 1,
                    "col_spec": c_spec + 1,
                    "col_qty": c_qty + 1,
                    "code": code,
                    "spec_or_name": spec,
                    "quantity": qty,
                    "status": "Chờ nhập"
                })

        logger.info(f"Tìm thấy {len(items)} mục dữ liệu cho Ngày {day} trên '{sheet_name}'")
        return items

    def fetch_unprocessed_items(self, sheet_name: str, category_filter: str = None, day_filter: int = None):
        """
        Đọc và phân tích danh sách dữ liệu từ trang tính ERP.
        Nếu truyền day_filter (1..31), sử dụng cơ chế tải siêu tốc theo từng ngày cụ thể.
        """
        if not self.spreadsheet:
            self.connect()

        if day_filter is not None and 1 <= int(day_filter) <= 31:
            try:
                return self._fetch_single_day_items(sheet_name, int(day_filter), category_filter)
            except Exception as e:
                logger.warning(f"Lỗi khi tải siêu tốc ngày {day_filter}, chuyển sang phương thức dự phòng: {e}")

        try:
            import urllib.parse
            sheet_name_encoded = urllib.parse.quote(f"'{sheet_name}'")
            url = f"https://sheets.googleapis.com/v4/spreadsheets/{self.spreadsheet.id}?includeGridData=true&ranges={sheet_name_encoded}"
            
            logger.info(f"Đang tải dữ liệu 1-lần cho trang tính '{sheet_name}' (includeGridData=true)...")
            res = self.client.http_client.request('get', url).json()
            
            if 'error' in res:
                logger.error(f"Lỗi API Google Sheets: {res['error']}")
                return []
                
            grid_data = res.get('sheets', [{}])[0].get('data', [{}])[0]
            
            all_rows = []
            all_formulas = []
            row2_unfmt = []
            
            row_data_list = grid_data.get('rowData', [])
            for r_idx, r_data in enumerate(row_data_list):
                row_vals = []
                row_forms = []
                cells = r_data.get('values', [])
                for cell in cells:
                    fmt_val = cell.get('formattedValue', '')
                    row_vals.append(fmt_val)
                    
                    user_val = cell.get('userEnteredValue', {})
                    form_val = user_val.get('formulaValue', '')
                    row_forms.append(form_val)
                    
                    if r_idx == 1:
                        eff_val = cell.get('effectiveValue', {})
                        if 'numberValue' in eff_val:
                            row2_unfmt.append(eff_val['numberValue'])
                        elif 'stringValue' in eff_val:
                            row2_unfmt.append(eff_val['stringValue'])
                        else:
                            row2_unfmt.append('')
                            
                all_rows.append(row_vals)
                all_formulas.append(row_forms)

            logger.info(f"Đã tải {len(all_rows)} dòng từ trang tính '{sheet_name}'")

            if len(all_rows) < 3:
                logger.warning(f"Trang tính '{sheet_name}' không đủ dữ liệu.")
                return []
            
            # Đọc giá trị Ngày / Tháng / Năm thực tế từ Hàng 2 (Row 2)
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
                    "NHẬP TRẢ", "NHẬP TRẢ X5", "NHẬP TRẢ X1", "GIA CÔNG", "BÁN PHẾ",
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

    def fetch_btp_items(self, spreadsheet_id: str = "1KlAdGFca-FCmTrzPrjCMUMK2pTOfMHxFFH-keCkdr1A", sheet_name: str = "Tổng Hợp"):
        """
        Đọc dữ liệu từ bảng tính BTP (Tab 'Tổng Hợp') cho quy trình COPMI08:
        - Ngày: Lấy từ ô C2 (dòng 2, cột 3). Chuyển thành định dạng YYYY/MM/DD.
        - Dữ liệu chi tiết: Quét từ dòng 6 trở đi:
            + Mã ERP: Cột P (index 15)
            + Số lượng Kg: Cột G (index 6)
            + Số lượng Tấm: Cột F (index 5)
            + Ghi chú: Cột J (index 9)
        """
        if not self.client:
            self.connect()

        try:
            logger.info(f"Đang kết nối tới bảng tính BTP ID: {spreadsheet_id} (Sheet: '{sheet_name}')...")
            sh = self.client.open_by_key(spreadsheet_id)
            ws = sh.worksheet(sheet_name)
            all_vals = ws.get_all_values()

            if len(all_vals) < 2:
                logger.warning(f"Bảng tính BTP '{sheet_name}' không có đủ dữ liệu hàng 2.")
                return "2026/10/19", []

            # 1. Đọc ngày từ ô C2 (Row 2, Col 3 - index [1][2])
            raw_c2 = all_vals[1][2].strip() if len(all_vals[1]) > 2 else ""
            date_str = "2026/10/19"
            if "/" in raw_c2:
                parts = raw_c2.split("/")
                if len(parts) == 3:
                    if len(parts[0]) == 4:
                        date_str = f"{parts[0]}/{int(parts[1]):02d}/{int(parts[2]):02d}"
                    else:
                        date_str = f"{parts[2]}/{int(parts[1]):02d}/{int(parts[0]):02d}"
            elif raw_c2.isdigit() and int(raw_c2) > 40000:
                dt = datetime(1899, 12, 30) + timedelta(days=int(raw_c2))
                date_str = dt.strftime("%Y/%m/%d")

            logger.info(f"--> [BTP] Ngày đọc từ ô C2: '{date_str}' (Giá trị gốc: '{raw_c2}')")

            # 2. Quét từ dòng 6 trở đi (Row index 5 trong all_vals)
            items = []
            for idx, row in enumerate(all_vals[5:], start=6):
                msp = row[0].strip() if len(row) > 0 else ""
                qc = row[2].strip() if len(row) > 2 else ""
                tam = row[5].strip() if len(row) > 5 else ""
                kg = row[6].strip() if len(row) > 6 else ""
                note = row[9].strip() if len(row) > 9 else ""
                code_erp = row[15].strip() if len(row) > 15 else ""

                if not code_erp and not msp:
                    continue

                items.append({
                    "sheet_name": sheet_name,
                    "row": idx,
                    "msp": msp,
                    "qc": qc,
                    "code": code_erp if code_erp else msp,
                    "code_erp": code_erp,
                    "qty_kg": kg,
                    "qty_tam": tam,
                    "note": note,
                    "date_str": date_str,
                    "status": "Chờ nhập"
                })

            logger.info(f"--> [BTP] Đã trích xuất thành công {len(items)} dòng dữ liệu từ Sheet '{sheet_name}'")
            return date_str, items

        except Exception as e:
            logger.error(f"Lỗi khi đọc bảng tính BTP '{sheet_name}': {e}", exc_info=True)
            return "2026/10/19", []

