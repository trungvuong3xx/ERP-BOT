import logging
import time
import os
import subprocess
import psutil
import pyautogui
import pyperclip
import win32gui
import win32con
import win32process
from pywinauto import Application
from cv_engine import CVEngine

# Bật PyAutoGUI FAILSAFE để cho phép người dùng dừng khẩn cấp bằng cách đẩy chuột về góc trên bên trái (0, 0)
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3

logger = logging.getLogger("ERPAutomation.GUI")

class ERPGUIController:
    """Điều khiển giao diện người dùng phần mềm WorkFlow ERP iGP."""

    def __init__(self, exe_path: str, account: str, password: str):
        self.exe_path = exe_path
        self.account = account
        self.password = password
        self.app = None
        self.main_hwnd = None
        self.cv = CVEngine()

    def find_running_erp(self):
        """Tìm tiến trình ERP đang chạy trên Windows (ưu tiên MainMenu.exe)."""
        mainmenu_pid = None
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                name = proc.info.get('name') or ''
                exe = proc.info.get('exe') or ''
                if 'mainmenu' in name.lower():
                    logger.info(f"Đã tìm thấy ứng dụng ERP MainMenu đang chạy: PID={proc.info['pid']}, Exe='{exe}'")
                    return proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        return None

    def launch_or_connect(self):
        """Mở mới hoặc kết nối với ứng dụng ERP. Trả về (success, is_already_running)."""
        pid = self.find_running_erp()
        if pid:
            try:
                logger.info(f"Kết nối tới ứng dụng ERP PID {pid}...")
                self.app = Application(backend="win32").connect(process=pid)
                return True, True
            except Exception as e:
                logger.warning(f"Không thể kết nối trực tiếp PID {pid}: {e}. Sẽ mở ứng dụng mới.")

        if not os.path.exists(self.exe_path):
            raise FileNotFoundError(f"Không tìm thấy tệp thực thi ERP tại: {self.exe_path}")

        logger.info(f"Đang khởi chạy ERP từ đường dẫn: {self.exe_path}")
        exe_dir = os.path.dirname(self.exe_path)
        subprocess.Popen([self.exe_path], cwd=exe_dir)
        time.sleep(4)

        new_pid = self.find_running_erp()
        if new_pid:
            self.app = Application(backend="win32").connect(process=new_pid)
            logger.info("Đã kết nối thành công tới tiến trình ERP mới.")
            return True, False
        else:
            logger.error("Ứng dụng ERP đã mở nhưng chưa tạo được tiến trình ghi nhận.")
            return False, False

    def focus_window_by_hwnd(self, hwnd, maximize=False):
        """Đưa cửa sổ lên trên cùng một cách an toàn mà không làm hỏng layout của ứng dụng."""
        try:
            import win32gui, win32con, win32process, win32api
            
            current_thread = win32api.GetCurrentThreadId()
            target_thread, _ = win32process.GetWindowThreadProcessId(hwnd)
            
            if current_thread != target_thread:
                win32gui.AttachThreadInput(current_thread, target_thread, True)
                
            show_cmd = win32con.SW_SHOWMAXIMIZED if maximize else win32con.SW_SHOW
            win32gui.ShowWindow(hwnd, show_cmd)
            win32gui.SetForegroundWindow(hwnd)
            
            if current_thread != target_thread:
                win32gui.AttachThreadInput(current_thread, target_thread, False)
                
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.warning(f"Không thể focus cửa sổ HWND {hwnd}: {e}")
            return False

    def smart_click(self, fallback_xy=None, image_path=None, timeout=3, double_click=False):
        """
        Click thông minh: Ưu tiên tìm hình ảnh bằng OpenCV, nếu không có ảnh hoặc không tìm thấy thì dùng tọa độ cứng (fallback).
        """
        if image_path and os.path.exists(image_path):
            try:
                self.cv.wait_and_click(image_path, timeout=timeout, double_click=double_click)
                return True
            except TimeoutError:
                logger.warning(f"CV: Không tìm thấy {image_path}, chuyển sang tọa độ dự phòng {fallback_xy}")
        
        if fallback_xy:
            x, y = fallback_xy
            if double_click:
                pyautogui.doubleClick(x, y)
            else:
                pyautogui.click(x, y)
            return True
        return False

    def recover_state(self):
        """Khôi phục trạng thái ERP khi gặp lỗi (Nhấn ESC để thoát các form phụ)."""
        logger.error("Đang thực hiện tự động phục hồi (Auto-Recovery)...")
        for _ in range(3):
            pyautogui.press('esc')
            time.sleep(0.5)

    def focus_erp_window(self):
        """Kích hoạt và đưa cửa sổ ERP hiển thị lên phía trước (giữ nguyên trạng thái Phóng to Trang chủ)."""
        try:
            if self.app:
                top_win = self.app.top_window()
                hwnd = top_win.handle
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.5)
                return True
        except Exception as e:
            logger.warning(f"Không thể Focus cửa sổ ERP bằng win32gui: {e}")
            try:
                if self.app:
                    self.app.top_window().set_focus()
                    time.sleep(0.5)
                    return True
            except Exception as ex:
                logger.warning(f"Không thể set_focus cửa sổ ERP: {ex}")
        return False

    def is_login_dialog_open(self) -> bool:
        """Tự động nhận diện xem cửa sổ Đăng nhập ERP có đang mở hay không."""
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32

            found_login = []
            found_hwnd = []

            def enum_win_cb(hwnd, lparam):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        title = buf.value
                        if "đăng nhập" in title.lower() or "login" in title.lower() or "mật khẩu" in title.lower():
                            found_login.append(title)
                            found_hwnd.append(hwnd)
                            return False
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            user32.EnumWindows(WNDENUMPROC(enum_win_cb), 0)

            if found_login and found_hwnd:
                logger.info(f"--> TỰ ĐỘNG PHÁT HIỆN: Cửa sổ Đăng nhập ERP đang hiển thị ('{found_login[0]}')")
                return True
        except Exception as e:
            logger.warning(f"Lỗi khi kiểm tra cửa sổ đăng nhập ERP: {e}")
        return False

    def auto_login(self, was_already_running: bool = False):
        """
        Tự động quét nhận diện 3 trạng thái của ERP:
        1. Nếu Cửa sổ INVI08 đã mở HOẶC ERP đã mở sẵn ở Trang chủ -> BỎ QUA ĐĂNG NHẬP!
        2. Nếu ERP chưa mở / đang ở Khung Đăng nhập -> Thực hiện 3 bước Đăng nhập bằng tọa độ.
        """
        # Nếu màn hình INVI08 đã mở sẵn hoặc ERP đã đăng nhập sẵn ở Trang chủ -> Bỏ qua bước đăng nhập
        if self.is_invi08_open() or (was_already_running and not self.is_login_dialog_open()):
            logger.info("--> TỰ ĐỘNG PHÁT HIỆN: ERP đã được đăng nhập sẵn (Trang chủ / Cửa sổ INVI08). BỎ QUA BƯỚC ĐĂNG NHẬP!")
            return True

        logger.info("--> TỰ ĐỘNG PHÁT HIỆN: ERP chưa đăng nhập. Thực hiện 3 bước Đăng nhập theo tọa độ...")

        # Bước 1: Click vào icon ERP tại tọa độ X = 707, Y = 14
        logger.info("--> Bước 1: Click Icon ERP tại tọa độ (X=707, Y=14)...")
        pyautogui.click(707, 14)
        time.sleep(1)

        # Bước 2: Click vào ô Mật khẩu tại tọa độ X = 1172, Y = 520 và dán mật khẩu 51225
        logger.info("--> Bước 2: Click ô Mật khẩu tại tọa độ (X=1172, Y=520) và dán 51225...")
        pyautogui.click(1172, 520)
        time.sleep(0.3)
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.press('backspace')
        pyperclip.copy(self.password)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.4)

        # Bước 3: Click vào Nút Đăng nhập tại tọa độ X = 1169, Y = 613
        logger.info("--> Bước 3: Click Nút Đăng nhập tại tọa độ (X=1169, Y=613)...")
        pyautogui.click(1169, 613)
        logger.info("✅ Đã hoàn tất 3 bước Đăng nhập theo đúng tọa độ Hoàng Thượng thiết lập!")
        time.sleep(4)
        return True

    def is_invi08_open(self) -> bool:
        """Tự động nhận diện xem cửa sổ/thẻ chứng từ INVI08 đã được mở trên ERP hay chưa."""
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

            found_title = []
            found_hwnd = []

            def enum_win_cb(hwnd, lparam):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        title = buf.value
                        if "INVI08" in title or "chuyển kho" in title.lower() or "chuyen kho" in title.lower():
                            if "thiết lập" not in title.lower() and "thiet lap" not in title.lower():
                                if "workflow" not in title.lower() and "igp" not in title.lower():
                                    found_title.append(title)
                                    found_hwnd.append(hwnd)
                                    return False  # Dừng quét nếu tìm thấy
                        
                return True

            cb = WNDENUMPROC(enum_win_cb)
            user32.EnumWindows(cb, 0)

            if found_title and found_hwnd:
                logger.info(f"--> TỰ ĐỘNG PHÁT HIỆN: Cửa sổ INVI08 đang mở ('{found_title[0]}')")
                return found_hwnd[0]

        except Exception as e:
            logger.warning(f"Lỗi khi quét nhận diện cửa sổ INVI08: {e}")
        return False

    def process_invi08_voucher(self, date_str: str, items_for_day: list, coords: dict, defaults: dict, skip_open: bool = False):
        """
        Quy trình tự động hóa đầy đủ cho chứng từ XUẤT INVI08 trên ERP.
        Tự động quét nhận diện trạng thái cửa sổ đang ở Trang chủ hay đã ở màn hình INVI08.
        """
        logger.info(f"=== BẮT ĐẦU TẠO PHIẾU INVI08 CHO NGÀY: {date_str} ({len(items_for_day)} MÃ) ===")

        # Tự động nhận diện vị trí hiện tại
        invi08_hwnd = None
        if skip_open:
            already_open = True
        else:
            invi08_hwnd = self.is_invi08_open()
            already_open = bool(invi08_hwnd)

        if not already_open:
            logger.info("--> TỰ ĐỘNG PHÁT HIỆN: Đang ở Trang chủ ERP. Thực hiện Mở INVI08 (Bước 2)...")
            # Bước 2: Click mở INVI08
            x_open, y_open = coords.get("open_invi08", [1095, 337])
            logger.info(f"Bước 2: Click mở INVI08 tại ({x_open}, {y_open})")
            # Click [500, 10] trước để Focus ERP lên trên cùng nếu Bot đang đè
            self.smart_click(fallback_xy=(500, 10))
            time.sleep(0.5)
            self.smart_click(fallback_xy=(x_open, y_open), image_path="templates/btn_invi08.png")
            time.sleep(2)

            # KHÁCH HÀNG XÁC NHẬN: "Cửa sổ INVI08 lúc nào cũng maxsize"
            # TUYỆT ĐỐI KHÔNG CLICK [1417, 251] NỮA, VÌ SẼ BỊ TRÚNG NÚT [X] (ĐÓNG CỬA SỔ)!
            logger.info("Bước 3: Cửa sổ INVI08 luôn tự động Maximize. Bỏ qua lệnh click Maximize để tránh rủi ro.")
            time.sleep(1)
        else:
            logger.info("--> TỰ ĐỘNG PHÁT HIỆN: Màn hình INVI08 ĐÃ MỞ SẴN! Đang dùng API để Focus cửa sổ INVI08 lên trên cùng...")
            if invi08_hwnd:
                self.focus_window_by_hwnd(invi08_hwnd, maximize=True)
            time.sleep(0.5)

        # Bước 4: Click nút Thêm
        x_add, y_add = coords.get("btn_add", [21, 126])
        logger.info(f"Bước 4: Click nút Thêm phiếu mới tại ({x_add}, {y_add})")
        pyautogui.click(x_add, y_add)
        time.sleep(1.5)

        # Bước 5: Click Loại phiếu chuyển -> gõ 1201
        x_type, y_type = coords.get("transfer_type_field", [197, 202])
        transfer_code = defaults.get("transfer_type", "1201")
        logger.info(f"Bước 5: Click ô Loại phiếu chuyển tại ({x_type}, {y_type}) -> Gõ '{transfer_code}'")
        pyautogui.click(x_type, y_type)
        time.sleep(0.3)
        pyperclip.copy(transfer_code)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.3)

        # Bước 6: Bấm TAB nhảy vào ô Ngày -> gõ ngày theo định dạng Năm/Tháng/Ngày
        logger.info(f"Bước 6: Bấm TAB nhảy vào ô Ngày -> Gõ ngày: '{date_str}'")
        pyautogui.press('tab')
        time.sleep(0.3)
        pyperclip.copy(date_str)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.3)

        # Xác định trang tính hiện tại là ERP Chỉ hay ERP Nhựa
        sheet_name_curr = items_for_day[0].get("sheet_name", "ERP Chỉ") if items_for_day else "ERP Chỉ"
        sheet_key = "nhua" if "Nhựa" in sheet_name_curr else "chi"
        cat_defaults = defaults.get(sheet_key, {})

        # Bước 7 & 8: Bấm TAB nhảy vào Mã bộ phận -> gõ (3820 cho ERP Chỉ, 3810 cho ERP Nhựa)
        dept_code = cat_defaults.get("department_code", "3810" if sheet_key == "nhua" else "3820")
        logger.info(f"Bước 7-8: Bấm TAB nhảy vào ô Mã bộ phận (Trang '{sheet_name_curr}') -> Gõ: '{dept_code}'")
        pyautogui.press('tab')
        time.sleep(0.3)
        pyperclip.copy(dept_code)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.3)

        # Bước 9: Bỏ qua bước khoảng trắng

        # Bước 10: Click ô Mã SP trên dòng chi tiết đầu tiên
        x_code1, y_code1 = coords.get("item_code_first", [166, 535])
        x_qty1, y_qty1 = coords.get("item_qty_first", [500, 535])
        x_wh1, y_wh1 = coords.get("item_warehouse_first", [1440, 535])
        
        # Mã kho: C21 cho ERP Chỉ, C11 cho ERP Nhựa
        wh_code = cat_defaults.get("warehouse_code", "C11" if sheet_key == "nhua" else "C21")
        logger.info(f"Mã kho nhập dòng 1 (Trang '{sheet_name_curr}'): '{wh_code}'")

        logger.info(f"Bước 10: Click ô Mã SP dòng 1 tại ({x_code1}, {y_code1})")
        pyautogui.click(x_code1, y_code1)
        time.sleep(0.5)

        # Bước 11 & 12: Nhập từng dòng chứng từ với khoảng cách dòng Delta Y = +20px mỗi khi bấm Down Arrow
        row_delta_y = 20
        for idx, item in enumerate(items_for_day, start=1):
            is_first = (idx == 1)
            qty_val = item.get('quantity') if 'quantity' in item else item.get('qty', '')
            
            # Tính toán tọa độ Y thực tế của dòng hiện tại: Y_curr = Y_dòng_1 + (idx - 1) * 20
            y_curr = y_code1 + (idx - 1) * row_delta_y
            logger.info(f"--> Nhập Dòng {idx}/{len(items_for_day)}: Mã={item['code']}, SL={qty_val} (Tọa độ Y={y_curr})")

            # Click & Dán Mã SP tại (166, Y_curr)
            pyautogui.click(x_code1, y_curr)
            time.sleep(0.1)
            pyperclip.copy(item['code'])
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.1)

            # Click & Dán Số lượng tại (500, Y_curr)
            pyautogui.click(x_qty1, y_curr)
            time.sleep(0.1)
            pyperclip.copy(str(qty_val))
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.1)

            # Chỉ dòng 1 mới nhập ô Nhập kho 'C21' tại (1440, 535)
            if is_first:
                pyautogui.click(x_wh1, y_wh1)
                time.sleep(0.1)
                pyperclip.copy(wh_code)
                pyautogui.hotkey('ctrl', 'v')
                time.sleep(0.1)

            # Bấm phím Mũi tên xuống (Down Arrow) để tạo/chuyển dòng
            pyautogui.press('down')
            time.sleep(0.15)

            # Tự động kiểm tra và kích hoạt bấm OK/Enter nếu xuất hiện Cảnh báo (VD: Cảnh báo hàng xuất/thiếu NVL)
            self.dismiss_warning_dialog_if_any()

        logger.info(f"=== ĐÃ HOÀN TẤT NHẬP {len(items_for_day)} DÒNG CHO PHIẾU NGÀY {date_str} ===")

    def is_purmi09_open(self) -> bool:
        """Tự động nhận diện xem cửa sổ/thẻ chứng từ PURMI09 đã được mở trên ERP hay chưa."""
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

            found_title = []
            found_hwnd = []

            def enum_win_cb(hwnd, lparam):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        title = buf.value
                        if "PURMI09" in title or "nhập mua" in title.lower() or "nhap mua" in title.lower():
                            if "thiết lập" not in title.lower() and "thiet lap" not in title.lower():
                                if "workflow" not in title.lower() and "igp" not in title.lower():
                                    found_title.append(title)
                                    found_hwnd.append(hwnd)
                                    return False  # Dừng quét nếu tìm thấy
                        
                return True

            cb = WNDENUMPROC(enum_win_cb)
            user32.EnumWindows(cb, 0)

            if found_title and found_hwnd:
                logger.info(f"--> TỰ ĐỘNG PHÁT HIỆN: Cửa sổ PURMI09 đang mở ('{found_title[0]}')")
                return found_hwnd[0]
        except Exception as e:
            logger.warning(f"Lỗi khi quét nhận diện cửa sổ PURMI09: {e}")
        return False

    def process_purmi09_voucher(self, date_str: str, items_for_day: list, skip_open: bool = False):
        """
        Quy trình tự động hóa cho chứng từ NHẬP FOR (PURMI09) trên ERP theo đúng chỉ thị của Hoàng Thượng.
        Hỗ trợ tính khoảng cách dòng xuống Y + 20px chính xác.
        """
        logger.info(f"=== BẮT ĐẦU TẠO PHIẾU NHẬP FOR PURMI09 CHO NGÀY: {date_str} ({len(items_for_day)} MÃ) ===")

        purmi09_hwnd = None
        if skip_open:
            already_open = True
        else:
            purmi09_hwnd = self.is_purmi09_open()
            already_open = bool(purmi09_hwnd)

        if not already_open:
            logger.info("--> TỰ ĐỘNG PHÁT HIỆN: Đang ở Trang chủ ERP. Thực hiện Mở PURMI09 (Bước 1)...")
            # Bước 1: Click mở PURMI09 tại (800, 250)
            logger.info("Bước 1: Click mở PURMI09 tại tọa độ (800, 250)")
            # Click [500, 10] trước để Focus ERP lên trên cùng nếu Bot đang đè
            pyautogui.click(500, 10)
            time.sleep(0.5)
            pyautogui.click(800, 250)
            time.sleep(2)

            logger.info("Bước 2: Cửa sổ PURMI09 luôn tự động Maximize. Bỏ qua lệnh click Maximize.")
            time.sleep(1)
        else:
            logger.info("--> TỰ ĐỘNG PHÁT HIỆN: Màn hình PURMI09 ĐÃ MỞ SẴN! Đang dùng API để Focus cửa sổ PURMI09 lên trên cùng...")
            if purmi09_hwnd:
                self.focus_window_by_hwnd(purmi09_hwnd, maximize=True)
            time.sleep(0.5)

        # Bước 3: Click nút Thêm tại (27, 130)
        logger.info("Bước 3: Click nút Thêm tại tọa độ (27, 130)")
        pyautogui.click(27, 130)
        time.sleep(1.5)

        # Bước 4: Click ô Loại chứng từ tại (170, 197) -> dán A343 -> Bấm Tab
        logger.info("Bước 4: Click ô Loại chứng từ tại (170, 197) -> Gõ 'A343' -> Bấm TAB")
        pyautogui.click(170, 197)
        time.sleep(0.3)
        pyperclip.copy("A343")
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.3)
        pyautogui.press('tab')
        time.sleep(0.3)

        # Bước 5: Dán 'VN0586' -> Bấm Tab 2 lần -> Dán Ngày (YYYY/MM/DD)
        logger.info(f"Bước 5: Gõ Mã NCC 'VN0586' -> TAB 2 lần -> Gõ Ngày: '{date_str}'")
        pyperclip.copy("VN0586")
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.3)
        pyautogui.press('tab')
        time.sleep(0.2)
        pyautogui.press('tab')
        time.sleep(0.3)
        pyperclip.copy(date_str)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.3)

        # Tọa độ dòng 1
        x_code_base = 377
        x_qty_base = 638
        x_dept_base = 175
        y_first_row = 482
        row_delta_y = 20  # Mỗi dòng xuống Y + 20px

        # Bước 6, 7, 8 & 9: Nhập từng dòng sản phẩm với Y + 20px mỗi dòng
        for idx, item in enumerate(items_for_day, start=1):
            qty_val = item.get('quantity') if 'quantity' in item else item.get('qty', '')
            y_curr = y_first_row + (idx - 1) * row_delta_y

            logger.info(f"--> Nhập Dòng {idx}/{len(items_for_day)} (PURMI09): Mã={item['code']}, SL={qty_val}, BP=3710 (Tọa độ Y={y_curr})")

            # Bước 6: Click & Dán Mã SP tại (377, Y_curr)
            pyautogui.click(x_code_base, y_curr)
            time.sleep(0.2)
            pyperclip.copy(item['code'])
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.2)

            # Bước 7: Click & Dán Số lượng tại (638, Y_curr)
            pyautogui.click(x_qty_base, y_curr)
            time.sleep(0.2)
            pyperclip.copy(str(qty_val))
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.2)

            # Bước 8: Click & Dán Mã Bộ phận 3710 tại (175, Y_curr)
            pyautogui.click(x_dept_base, y_curr)
            time.sleep(0.2)
            pyperclip.copy("3710")
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.2)

            # Bước 9: Bấm phím Down (mũi tên xuống) để tạo dòng mới
            pyautogui.press('down')
            time.sleep(0.3)

            # Click trực tiếp Nút OK tại tọa độ (1030, 592) do Hoàng Thượng ấn định để đóng Cảnh báo (W-100127) nếu có
            pyautogui.click(1030, 592)
            time.sleep(0.2)
            pyautogui.press('enter')
            time.sleep(0.2)

            # Tự động kiểm tra và xử lý bổ sung nếu cửa sổ cảnh báo vẫn còn
            self.dismiss_warning_dialog_if_any()

        logger.info(f"✅ ĐÃ NHẬP XONG HOÀN TẤT PHIẾU PURMI09 CHO NGÀY: {date_str}!")
        return True

    def dismiss_warning_dialog_if_any(self) -> bool:
        """
        Tự động kiểm tra và xử lý các hộp thoại Cảnh báo/Lỗi bằng PyWinAuto.
        """
        try:
            from pywinauto import Desktop
            desktop = Desktop(backend="win32")
            dialogs = desktop.windows(class_name="#32770", visible_only=True)
            dismissed = False
            for dlg in dialogs:
                title = dlg.window_text().lower()
                if any(k in title for k in ["lỗi", "cảnh báo", "w-100", "thiếu", "nguyên vật liệu", "thao tác", "error", "warning", "confirm", "xác nhận"]):
                    logger.info(f"--> [Smart Dialog] Phát hiện popup '{title}'. Đang xử lý tự động...")
                    try:
                        dlg.set_focus()
                        dlg.send_keystrokes("{ENTER}")
                        time.sleep(0.3)
                        if dlg.exists():
                            dlg.close()
                        dismissed = True
                    except Exception as ex:
                        logger.warning(f"Không thể gửi phím Enter, thử đóng bắt buộc: {ex}")
                        try:
                            dlg.close()
                            dismissed = True
                        except:
                            pass
            return dismissed
        except Exception as e:
            logger.warning(f"Lỗi khi xử lý Smart Dialog: {e}")
            return False

    def save_voucher(self):
        """Lưu chứng từ (Ctrl + S hoặc F2)."""
        logger.info("Thực hiện bấm nút Lưu chứng từ (Ctrl+S)...")
        pyautogui.hotkey('ctrl', 's')
        time.sleep(1.5)
