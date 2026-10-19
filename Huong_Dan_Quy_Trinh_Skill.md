# HƯỚNG DẪN QUY TRÌNH & ĐÓNG GÓI SKILL: AUTOMATION WORKFLOW ERP iGP

Tài liệu này tổng hợp chi tiết toàn bộ kiến trúc, thuật toán, quy trình xử lý và mã nguồn đóng gói Skill tự động hóa cho hệ thống WorkFlow ERP iGP và Google Sheets.

---

## 📋 MỤC LỤC

1. [Tổng Quan Hệ Thống](#1-tổng-quan-hệ-thống)
2. [Cấu Trúc Bảng Tính & Thuật Toán Đọc Dữ Liệu](#2-cấu-trúc-bảng-tính--thuật-toán-đọc-dữ-liệu)
3. [Thuật Toán Nhận Diện Cửa Sổ MDI INVI08 Cấp Thấp](#3-thuật-toán-nhận-diện-cửa-sổ-mdi-invi08-cấp-thấp)
4. [Tự Động Hóa Thao Tác Win32 GUI ERP](#4-tự-động-hóa-thao-tác-win32-gui-erp)
5. [Ứng Dụng Desktop GUI & Đóng Gói PyInstaller](#5-ứng-dụng-desktop-gui--đóng-gói-pyinstaller)
6. [Tệp Cấu Hình Skill `.agents/skills/erp-igp-automation/SKILL.md`](#6-tệp-cấu-hình-skill)

---

## 1. TỔNG QUAN HỆ THỐNG

- **Tên Phần Mềm**: WorkFlow ERP iGP (`MainMenu.exe`).
- **Nguồn Dữ Liệu**: Google Sheets (`ERP và BÁO CÁO`), 2 Trang tính: `ERP Chỉ` và `ERP Nhựa`.
- **Tệp Thực Thi Độc Lập**: `ERP Bot iGP.exe` (Thả ngoài màn hình Desktop).

---

## 2. CẤU TRÚC BẢNG TÍNH & THUẬT TOÁN ĐỌC DỮ LIỆU

### A. Xử Lý Định Dạng Ngày Row 2 (Excel Serial Date)
- Hàng 2 trong Google Sheets chứa giá trị Ngày tháng dưới dạng số Serial (ví dụ `46227`).
- Công thức chuyển đổi trong `google_sheets.py`:
  ```python
  from datetime import datetime, timedelta
  base_date = datetime(1899, 12, 30)
  date_obj = base_date + timedelta(days=int(serial_number))
  date_str = date_obj.strftime("%Y/%m/%d")
  ```

### B. Thuật Toán Cắt Dừng Công Thức TỔNG (`=SUM...`)
- Ô Số lượng ở cuối mỗi danh mục chứa công thức tổng (ví dụ `=SUM(D20:D35)` hoặc `=SUMPRODUCT(...)`).
- Ngay khi kiểm tra thấy chuỗi công thức bắt đầu bằng `SUM(` hoặc `SUMPRODUCT(`, robot dừng đọc dữ liệu cho ngày đó, loại bỏ hoàn toàn khả năng đọc dư sang các danh mục phía dưới.

---

## 3. THUẬT TOÁN NHẬN DIỆN CỬA SỔ MDI INVI08 CẤP THẤP

Sử dụng thư viện `ctypes` gọi API Windows `user32.dll` để quét danh sách các cửa sổ con MDI mà không bị gián đoạn hay đơ crash lỗi `Error 122`:

```python
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

def is_invi08_open():
    found = []
    def enum_win_cb(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value
                if "INVI08" in title or "chuyển kho" in title.lower():
                    found.append(title)
                    return False
        return True
    user32.EnumWindows(WNDENUMPROC(enum_win_cb), 0)
    return len(found) > 0
```

---

## 4. TỰ ĐỘNG HÓA THAO TÁC WIN32 GUI ERP

### Bảng So Sánh Quy Tắc Giữa Các Quy Trình:

| Bước Thao Tác | Trang `ERP Chỉ` (INVI08) | Trang `ERP Nhựa` (INVI08) | Bảng `BTP` - Tab `Tổng Hợp` (COPMI08) |
| :--- | :---: | :---: | :---: |
| **Loại Phiếu** | `1201` | `1201` | `A234` (tại X=167, Y=198) |
| **Mã Bộ Phận / Khách hàng** | `3820` | `3810` | `VN0003` (Khách hàng) |
| **Mã Kho Nhập** | `C21` | `C11` | N/A |
| **Chi Tiết Dòng 1** | Mã SP tại (166, 535) | Mã SP tại (166, 535) | Mã SP (Cột P) tại (341, 513) |
| **Thao Tác Nhảy Dòng** | Phím Down ($Y_k = 535 + (k-1) \times 20$) | Phím Down ($Y_k = 535 + (k-1) \times 20$) | P(i) -> TABx2 -> G(i) [Kg] -> TABx2 -> F(i) [Tấm] -> TABx1 -> J(i) [Ghi chú] -> Phím Down -> TAB |


---

## 5. ỨNG DỤNG DESKTOP GUI & ĐÓNG GÓI PYINSTALLER

Ứng dụng được thiết kế bằng `tkinter` + `ttk` (Dark Theme), hỗ trợ đa luồng `threading.Thread` để tránh treo giao diện và đóng gói thành 1 tệp độc lập bằng `PyInstaller`:

```cmd
pyinstaller --noconfirm --onefile --windowed --icon="app_icon.ico" --name "ERP Bot iGP" --collect-all gspread --collect-all google.oauth2 main.py
```

---

## 6. TỆP CẤU HÌNH SKILL

Skill đã được đăng ký hệ thống tại đường dẫn:
- [SKILL.md](file:///c:/Users/Admin/OneDrive/T%C3%A0i%20li%E1%BB%87u/Code%20g%E1%BB%91c/.agents/skills/erp-igp-automation/SKILL.md)
