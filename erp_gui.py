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
pyautogui.PAUSE = 0.05

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

        if os.path.isdir(self.exe_path):
            possible_lnk = os.path.join(self.exe_path, "WorkFlow ERP iGP.lnk")
            if os.path.exists(possible_lnk):
                self.exe_path = possible_lnk

        if not os.path.exists(self.exe_path):
            raise FileNotFoundError(f"Không tìm thấy tệp thực thi ERP tại: {self.exe_path}")

        logger.info(f"Đang khởi chạy ERP từ đường dẫn: {self.exe_path}")
        if self.exe_path.lower().endswith(".lnk"):
            os.startfile(self.exe_path)
        else:
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
                win32process.AttachThreadInput(current_thread, target_thread, True)
                
            # Không dùng SW_SHOWMAXIMIZED vì sẽ ép Windows kéo khung làm vỡ giao diện bên trong (Cửa sổ vô hình)
            if maximize:
                show_cmd = win32con.SW_RESTORE
                win32gui.ShowWindow(hwnd, show_cmd)
                
            win32gui.SetForegroundWindow(hwnd)
            
            if current_thread != target_thread:
                win32process.AttachThreadInput(current_thread, target_thread, False)
                
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
        """Kích hoạt và đưa cửa sổ Trang chủ ERP hiển thị lên phía trước (Sử dụng ctypes thay cho click mù)."""
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            erp_pid = self.find_running_erp()
            
            found_hwnd = []
            def enum_win_cb(hwnd, lparam):
                if user32.IsWindowVisible(hwnd):
                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    
                    if not erp_pid or pid.value == erp_pid:
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buf = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buf, length + 1)
                            title = buf.value.lower()
                            # Lọc chỉ lấy Trang chủ ERP (Tránh cửa sổ con)
                            if "workflow erp igp" in title and "đăng nhập" not in title and "invi08" not in title and "purmi09" not in title and "thiết lập" not in title and "nhập kho" not in title and "nhap kho" not in title and "nhập mua" not in title:
                                found_hwnd.append(hwnd)
                                return False
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            user32.EnumWindows(WNDENUMPROC(enum_win_cb), 0)
            
            if found_hwnd:
                logger.info("--> TỰ ĐỘNG PHÁT HIỆN: Đang ở Trang chủ ERP, Đang tiến hành Focus...")
                self.focus_window_by_hwnd(found_hwnd[0], maximize=True)
                return True
        except Exception as e:
            logger.warning(f"Lỗi khi Focus cửa sổ ERP bằng ctypes: {e}")
        return False

    def is_login_dialog_open(self) -> bool:
        """Tự động nhận diện xem cửa sổ Đăng nhập ERP có đang mở hay không."""
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            
            erp_pid = self.find_running_erp()

            found_login = []
            found_hwnd = []

            def enum_win_cb(hwnd, lparam):
                if user32.IsWindowVisible(hwnd):
                    # Lọc triệt để: Chỉ chấp nhận cửa sổ thuộc về MainMenu.exe
                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        title = buf.value
                        title_lower = title.lower()
                        
                        # Bỏ qua các cửa sổ rác (trình duyệt, Zalo, thư mục...)
                        if "chrome" in title_lower or "cốc cốc" in title_lower or "edge" in title_lower or "code" in title_lower:
                            return True
                        if "quên mật khẩu" in title_lower or "mở khóa" in title_lower:
                            return True
                            
                        if "đăng nhập" in title_lower or "login" in title_lower or "mật khẩu" in title_lower:
                            # Đảm bảo không bắt nhầm các cửa sổ không liên quan
                            if "thiết lập" not in title_lower and "thiet lap" not in title_lower:
                                # Nếu erp_pid có tồn tại thì ép buộc PID phải khớp
                                if not erp_pid or pid.value == erp_pid:
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
                        title_lower = title.lower()
                        # Loại trừ các cửa sổ trình duyệt, thư mục, hoặc cửa sổ bot
                        if "chrome" in title_lower or "cốc cốc" in title_lower or "edge" in title_lower or "code" in title_lower:
                            return True
                        if "automation suite" in title_lower or "pycharm" in title_lower:
                            return True
                            
                        # Kiểm tra xem có chứa từ khóa INVI08 không
                        if "invi08" in title_lower or "chuyển kho" in title_lower or "chuyen kho" in title_lower:
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
            # Focus ERP Home Page bằng API an toàn
            self.focus_erp_window()
            time.sleep(0.5)
            self.smart_click(fallback_xy=(x_open, y_open), image_path="templates/btn_invi08.png")
            time.sleep(2)

            # Bước 3: Click Maximize (Khách hàng yêu cầu dùng chuột click tọa độ cũ để tránh lỗi)
            logger.info("Bước 3: Khôi phục lệnh click Maximize tại [1417, 251] theo yêu cầu.")
            pyautogui.click(1417, 251)
            time.sleep(1)
        else:
            logger.info("--> TỰ ĐỘNG PHÁT HIỆN: Màn hình INVI08 ĐÃ MỞ SẴN! Đang tiến hành Focus...")
            if invi08_hwnd:
                self.focus_window_by_hwnd(invi08_hwnd, maximize=False)
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
        
        category_name = items_for_day[0].get("category", "").upper() if items_for_day else ""
        is_nhap_tra_x5 = (category_name == "NHẬP TRẢ X5")

        # Bước 7 & 8: Bấm TAB nhảy vào Mã bộ phận -> gõ (3820 cho ERP Chỉ, 3810 cho ERP Nhựa, hoặc 3350 cho NHẬP TRẢ X5)
        if is_nhap_tra_x5:
            dept_code = "3350"
        else:
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
            time.sleep(0.02)
            pyperclip.copy(item['code'])
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.02)

            # Click & Dán Số lượng tại (500, Y_curr)
            pyautogui.click(x_qty1, y_curr)
            time.sleep(0.02)
            pyperclip.copy(str(qty_val))
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.02)

            if is_nhap_tra_x5:
                # Custom logic for Nhập trả X5
                pyautogui.click(880, y_curr)
                time.sleep(0.02)
                pyperclip.copy("C21")
                pyautogui.hotkey('ctrl', 'v')
                time.sleep(0.02)
                
                if is_first:
                    # Tab and H10
                    pyautogui.press('tab')
                    time.sleep(0.02)
                    pyperclip.copy("H10")
                    pyautogui.hotkey('ctrl', 'v')
                    time.sleep(0.02)
            else:
                # Chỉ dòng 1 mới nhập ô Nhập kho tại (1440, 535)
                if is_first:
                    pyautogui.click(x_wh1, y_wh1)
                    time.sleep(0.02)
                    pyperclip.copy(wh_code)
                    pyautogui.hotkey('ctrl', 'v')
                    time.sleep(0.02)

            # Bấm phím Mũi tên xuống (Down Arrow) để tạo/chuyển dòng
            pyautogui.press('down')
            time.sleep(0.05)

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
                        title_lower = title.lower()
                        # Loại trừ các cửa sổ trình duyệt, thư mục, hoặc cửa sổ bot
                        if "chrome" in title_lower or "cốc cốc" in title_lower or "edge" in title_lower or "code" in title_lower:
                            return True
                        if "automation suite" in title_lower or "pycharm" in title_lower:
                            return True
                            
                        if "purmi09" in title_lower or "nhập mua" in title_lower or "nhap mua" in title_lower or "nhập kho" in title_lower or "nhap kho" in title_lower:
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

    def process_purmi09_voucher(self, date_str: str, items_for_day: list, coords: dict, defaults: dict, skip_open: bool = False):
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
            # Bước 1: Click mở PURMI09
            x_open, y_open = coords.get("open_purmi09", [800, 250])
            logger.info(f"Bước 1: Click mở PURMI09 tại tọa độ ({x_open}, {y_open})")
            # Focus ERP Home Page bằng API an toàn
            self.focus_erp_window()
            time.sleep(0.5)
            self.smart_click(fallback_xy=(x_open, y_open), image_path="templates/btn_purmi09.png")
            time.sleep(2)

            logger.info("Bước 2: Click Maximize tại [1448, 216] để tránh lỗi cửa sổ ẩn.")
            pyautogui.click(1448, 216)
            time.sleep(1)
        else:
            logger.info("--> TỰ ĐỘNG PHÁT HIỆN: Màn hình PURMI09 ĐÃ MỞ SẴN! Đang tiến hành Focus...")
            if purmi09_hwnd:
                self.focus_window_by_hwnd(purmi09_hwnd, maximize=False)
            time.sleep(0.5)

        # Bước 3: Click nút Thêm
        x_add, y_add = coords.get("btn_add", [27, 130])
        logger.info(f"Bước 3: Click nút Thêm tại tọa độ ({x_add}, {y_add})")
        pyautogui.click(x_add, y_add)
        time.sleep(1.5)

        # Bước 4: Click ô Loại chứng từ -> dán A343 -> Bấm Tab
        x_sup, y_sup = coords.get("supplier_field", [170, 197])
        logger.info(f"Bước 4: Click ô Loại chứng từ/NCC tại ({x_sup}, {y_sup}) -> Gõ 'A343' -> Bấm TAB")
        pyautogui.click(x_sup, y_sup)
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
        x_code_base, y_first_row = coords.get("item_code_first", [377, 482])
        x_qty_base, _ = coords.get("item_qty_first", [638, 482])
        x_dept_base = 175
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

            # Tự động kiểm tra và xử lý bổ sung nếu cửa sổ cảnh báo vẫn còn
            self.dismiss_warning_dialog_if_any()

        logger.info(f"✅ ĐÃ NHẬP XONG HOÀN TẤT PHIẾU PURMI09 CHO NGÀY: {date_str}!")
        return True

    def dismiss_warning_dialog_if_any(self) -> bool:
        """
        Tự động kiểm tra và xử lý các hộp thoại Cảnh báo/Lỗi.
        Sử dụng ctypes siêu tốc để quét mọi cửa sổ (bao gồm cả cửa sổ con) nhằm đảm bảo không bỏ sót hộp thoại nào.
        """
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            
            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            
            # Biến lưu trạng thái
            state = {"dismissed": False}
            
            def enum_win_cb(hwnd, lparam):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        title = buf.value.lower()
                        
                        if any(k in title for k in ["lỗi", "cảnh báo", "w-100", "thiếu", "nguyên vật liệu", "thao tác", "error", "warning", "confirm", "xác nhận"]):
                            rect = wintypes.RECT()
                            user32.GetWindowRect(hwnd, ctypes.byref(rect))
                            width = rect.right - rect.left
                            height = rect.bottom - rect.top
                            
                            # Hộp thoại cảnh báo thường nhỏ (bỏ qua cửa sổ chính ERP > 800)
                            if 0 < width < 800 and 0 < height < 600:
                                logger.info(f"--> [Smart Dialog] Phát hiện popup '{buf.value}' (Kích thước: {width}x{height}). Đang xử lý tự động...")
                                try:
                                    user32.SetForegroundWindow(hwnd)
                                except:
                                    pass
                                # Click trực tiếp Nút OK tại tọa độ do người dùng cung cấp
                                pyautogui.click(1022, 606)
                                time.sleep(0.02)
                                state["dismissed"] = True
                                return False  # Dừng quét
                return True
            
            cb = WNDENUMPROC(enum_win_cb)
            user32.EnumWindows(cb, 0)
            
            return state["dismissed"]
            
        except Exception as e:
            logger.warning(f"Lỗi khi xử lý Smart Dialog: {e}")
            return False

    def save_voucher(self):
        """Lưu chứng từ (Ctrl + S hoặc F2)."""
        logger.info("Thực hiện bấm nút Lưu chứng từ (Ctrl+S)...")
        pyautogui.hotkey('ctrl', 's')
        time.sleep(1.5)

    def focus_copmi08_window(self):
        """Kích hoạt và đưa cửa sổ COPMI08 lên foreground mà không làm thay đổi trạng thái kích thước hay ẩn cửa sổ."""
        try:
            import ctypes
            from ctypes import wintypes
            import win32gui, win32process, win32api
            user32 = ctypes.windll.user32
            
            found_hwnd = []
            def enum_win_cb(hwnd, lparam):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        title = buf.value.lower()
                        if "copmi08" in title or ("đơn bán hàng" in title and "thiết lập" in title):
                            found_hwnd.append(hwnd)
                            return False
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            user32.EnumWindows(WNDENUMPROC(enum_win_cb), 0)

            if found_hwnd:
                hwnd = found_hwnd[0]
                logger.info(f"--> Đã tìm thấy cửa sổ COPMI08 (HWND={hwnd}), đưa lên Foreground...")
                
                # Chỉ khôi phục phóng to nếu cửa sổ đang bị thu nhỏ (IsIconic)
                if user32.IsIconic(hwnd):
                    user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
                
                current_thread = win32api.GetCurrentThreadId()
                target_thread, _ = win32process.GetWindowThreadProcessId(hwnd)
                if current_thread != target_thread:
                    win32process.AttachThreadInput(current_thread, target_thread, True)
                
                user32.SetForegroundWindow(hwnd)
                user32.BringWindowToTop(hwnd)
                
                if current_thread != target_thread:
                    win32process.AttachThreadInput(current_thread, target_thread, False)
                
                time.sleep(0.3)
                return True
            else:
                logger.info("--> Không tìm thấy HWND tiêu đề COPMI08, tiếp tục thực hiện trực tiếp...")
        except Exception as e:
            logger.warning(f"Lỗi khi focus cửa sổ COPMI08: {e}")
        return False

    def dismiss_copmi08_dialog_if_any(self) -> bool:
        """
        Tự động phát hiện và bấm OK khi xuất hiện hộp thoại cảnh báo trên COPMI08:
        (ví dụ: W-100091: Cảnh báo tồn kho, L-000002: Lỗi mã không tồn tại, v.v...)
        """
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            
            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            state = {"dismissed": False}
            
            def enum_win_cb(hwnd, lparam):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        title = buf.value.lower()
                        
                        # Nhận diện các popup của COPMI08 hoặc hộp thoại cảnh báo của ERP
                        if any(k in title for k in ["copmi08", "đơn bán hàng", "thao tác", "w-100", "l-000", "cảnh báo", "lỗi", "warning", "confirm"]):
                            rect = wintypes.RECT()
                            user32.GetWindowRect(hwnd, ctypes.byref(rect))
                            width = rect.right - rect.left
                            height = rect.bottom - rect.top
                            
                            # Hộp thoại cảnh báo thường nhỏ (150 < width < 800 và 80 < height < 500)
                            if 150 < width < 800 and 80 < height < 500:
                                logger.info(f"--> [COPMI08 Dialog] Phát hiện popup '{buf.value}' ({width}x{height}). Đang bấm OK...")
                                
                                try:
                                    user32.SetForegroundWindow(hwnd)
                                except Exception:
                                    pass
                                
                                # Tính toán tọa độ nút OK theo vị trí hộp thoại thực tế trên màn hình
                                ok_x = rect.left + int(width * 0.55)
                                ok_y = rect.top + int(height * 0.75)
                                if not (rect.left < ok_x < rect.right and rect.top < ok_y < rect.bottom):
                                    ok_x, ok_y = 1015, 588
                                
                                # Click chính xác nút OK, không gửi phím Enter tránh ảnh hưởng tiêu điểm của lưới dữ liệu
                                pyautogui.click(ok_x, ok_y)
                                
                                # Chờ cho đến khi popup biến mất hoàn toàn
                                t_wait = time.time()
                                while time.time() - t_wait < 0.6:
                                    if not user32.IsWindow(hwnd) or not user32.IsWindowVisible(hwnd):
                                        break
                                    time.sleep(0.04)
                                
                                time.sleep(0.08)
                                state["dismissed"] = True
                                return False
                return True
            
            user32.EnumWindows(WNDENUMPROC(enum_win_cb), 0)
            return state["dismissed"]
        except Exception as e:
            logger.warning(f"Lỗi kiểm tra dialog COPMI08: {e}")
            return False

    def wait_and_dismiss_copmi08_dialogs(self, timeout: float = 0.8) -> bool:
        """
        Chờ và tắt mọi hộp thoại cảnh báo/thông báo phát sinh trên COPMI08.
        Nếu có hộp thoại xuất hiện, sẽ bấm OK và chờ cho đến khi tắt hết sạch.
        Trả về True nếu có ít nhất 1 hộp thoại được đóng.
        """
        dismissed_any = False
        t_start = time.time()
        while time.time() - t_start < timeout:
            if self.dismiss_copmi08_dialog_if_any():
                dismissed_any = True
                t_start = time.time()
                timeout = 0.5
                time.sleep(0.1)
            else:
                time.sleep(0.04)
        return dismissed_any

    def process_copmi08_voucher(self, date_str: str, items: list, coords: dict = None):
        """
        Quy trình tự động hóa cho chứng từ COPMI08 trên ERP.
        Người dùng luôn mở full cửa sổ sẵn.
        Các bước:
        Bước 1: Nhấp vào X 167 Y 198 -> Nhập A234 -> Bấm TAB
        Bước 2: Nhập ngày ở cột C2 Ví dụ 2026/10/19 -> Bấm TAB
        Bước 3: Nhập VN0003
        Bước 4: Nhấp vào X 341 Y 513 -> Nhập ô P6 -> TAB 2 lần
        Bước 5: Nhập ô G6 -> TAB 2 lần
        Bước 6: Nhập ô F6 -> TAB 1 lần
        Bước 7: Nhập ô J6 -> Nhấn phím mũi tên xuống -> Chờ tắt cảnh báo -> Nhấn phím TAB sang ô Mã SP
        Bước 8+: Nhập ô P(i) -> tiếp tục lặp lại bước 5 đến bước 7 cho đến hết dữ liệu
        """
        if not items:
            logger.warning("[COPMI08] Không có dữ liệu sản phẩm để nhập!")
            return False

        coords = coords or {}
        x_head, y_head = coords.get("header_doc_type", [167, 198])
        doc_type = coords.get("doc_type_val", "A234")
        cust_code = coords.get("customer_val", "VN0003")
        x_row1, y_row1 = coords.get("first_row_code", [341, 513])

        logger.info(f"=== BẮT ĐẦU TẠO PHIẾU COPMI08 CHO NGÀY: {date_str} ({len(items)} DÒNG SẢN PHẨM) ===")
        
        # Focus trực tiếp cửa sổ COPMI08 đã mở sẵn max size mà không làm ẩn/thu nhỏ cửa sổ
        self.focus_copmi08_window()
        time.sleep(0.2)
        self.wait_and_dismiss_copmi08_dialogs(timeout=0.3)

        # Bước 1: Nhấp vào X 167 Y 198 -> Nhập A234 -> Bấm TAB
        logger.info(f"Bước 1: Click ô Loại phiếu tại ({x_head}, {y_head}) -> Gõ '{doc_type}' -> Bấm TAB")
        pyautogui.click(x_head, y_head)
        time.sleep(0.3)
        pyperclip.copy(doc_type)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.2)
        pyautogui.press('tab')
        time.sleep(0.2)

        # Bước 2: Nhập ngày ở cột C2 (Ví dụ 2026/10/19) -> Bấm TAB
        logger.info(f"Bước 2: Gõ Ngày: '{date_str}' -> Bấm TAB")
        pyperclip.copy(date_str)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.2)
        pyautogui.press('tab')
        time.sleep(0.2)

        # Bước 3: Nhập VN0003
        logger.info(f"Bước 3: Gõ Mã Khách hàng: '{cust_code}'")
        pyperclip.copy(cust_code)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.3)

        # Bước 4: Nhấp vào X 341 Y 513
        logger.info(f"Bước 4: Click ô Mã SP Dòng 1 tại ({x_row1}, {y_row1})")
        pyautogui.click(x_row1, y_row1)
        time.sleep(0.4)

        # Lặp các dòng dữ liệu
        for idx, item in enumerate(items, start=1):
            code_erp = item.get("code_erp", item.get("code", ""))
            qty_kg = item.get("qty_kg", "")
            qty_tam = item.get("qty_tam", "")
            note = item.get("note", "")

            logger.info(f"--> Nhập Dòng {idx}/{len(items)}: Mã(P)='{code_erp}' | Kg(G)='{qty_kg}' | Tấm(F)='{qty_tam}' | Ghi chú(J)='{note}'")

            # Đảm bảo không có popup nào che khuất trước khi paste Mã SP
            self.wait_and_dismiss_copmi08_dialogs(timeout=0.1)

            # Nhập ô P (Mã SP) -> TAB 2 lần sang ô G
            pyperclip.copy(str(code_erp))
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.08)
            pyautogui.press('tab')
            time.sleep(0.04)
            pyautogui.press('tab')
            time.sleep(0.08)
            self.wait_and_dismiss_copmi08_dialogs(timeout=0.15)

            # Bước 5: Nhập ô G (Kg) -> TAB 2 lần sang ô F
            pyperclip.copy(str(qty_kg))
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.08)
            pyautogui.press('tab')
            time.sleep(0.04)
            pyautogui.press('tab')
            time.sleep(0.08)
            self.wait_and_dismiss_copmi08_dialogs(timeout=0.15)

            # Bước 6: Nhập ô F (Tấm) -> TAB 1 lần sang ô J
            pyperclip.copy(str(qty_tam))
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.08)
            pyautogui.press('tab')
            time.sleep(0.08)
            self.wait_and_dismiss_copmi08_dialogs(timeout=0.15)

            # Bước 7: Nhập ô J (Ghi chú)
            pyperclip.copy(str(note))
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.1)

            # Chỉ cần chuyển dòng nếu chưa phải dòng cuối cùng
            if idx < len(items):
                # 1. Bấm phím mũi tên xuống để tạo/chuyển sang dòng mới
                logger.info(f"--> Bấm mũi tên xuống (Down) để sang Dòng {idx + 1}...")
                pyautogui.press('down')

                # 2. Chờ ERP kiểm tra dữ liệu và hiển thị hộp thoại cảnh báo (W-100091) nếu có (chờ tối đa 0.8s)
                had_dialog = self.wait_and_dismiss_copmi08_dialogs(timeout=0.8)

                # 3. Kích hoạt lại cửa sổ COPMI08 để đảm bảo nhận phím chuẩn xác
                self.focus_copmi08_window()
                if had_dialog:
                    logger.info("--> Đã đóng hộp thoại cảnh báo sau khi xuống dòng. Chờ 0.3s để lưới dữ liệu ổn định...")
                    time.sleep(0.3)
                else:
                    time.sleep(0.18)

                # 4. Tiêu điểm hiện tại đang ở ô đầu tiên ('Mã SP nghiệp vụ')
                # Bấm TAB để chuyển sang ô 'Mã SP' cho dòng tiếp theo
                logger.info("--> Bấm phím TAB để chuyển sang ô 'Mã SP'...")
                pyautogui.press('tab')
                time.sleep(0.25)

                # 5. Kiểm tra dự phòng nếu có thông báo phát sinh sau khi TAB
                if self.wait_and_dismiss_copmi08_dialogs(timeout=0.3):
                    self.focus_copmi08_window()
                    time.sleep(0.2)

        logger.info(f"✅ ĐÃ NHẬP XONG HOÀN TẤT PHIẾU COPMI08 CHO NGÀY: {date_str} ({len(items)} DÒNG)!")
        return True

