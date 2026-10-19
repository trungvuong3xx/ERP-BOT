---
name: erp-igp-automation
description: "Quy trình tự động hóa nhập liệu chứng từ WorkFlow ERP iGP từ Google Sheets (Chỉ & Nhựa) sử dụng PyAutoGUI, pywinauto, gspread, ctypes window detection và PyInstaller GUI App."
---

# ERP iGP Automation Skill Guidelines & Architecture

Tài liệu hướng dẫn quy trình tự động hóa nhập liệu chứng từ cho hệ thống WorkFlow ERP iGP từ bảng tính Google Sheets ("ERP và BÁO CÁO").

---

## 1. Kiến Trúc Hệ Thống (Architecture)

### 📁 Cấu Trúc Mã Nguồn Project:
- [main.py](file:///C:/Users/Admin/OneDrive/T%C3%A0i%20li%E1%BB%87u/ERP%20BOT/erp_automation/main.py): Luồng điều khiển trung tâm (CLI Runner & GUI Launcher).
- [app_gui.py](file:///C:/Users/Admin/OneDrive/T%C3%A0i%20li%E1%BB%87u/ERP%20BOT/erp_automation/app_gui.py): Giao diện ứng dụng PC (Desktop GUI App - Dark Mode, Live Log Console, Multi-threading).
- [erp_gui.py](file:///C:/Users/Admin/OneDrive/T%C3%A0i%20li%E1%BB%87u/ERP%20BOT/erp_automation/erp_gui.py): Điều khiển tự động hóa Win32 GUI ERP (PyWinAuto, PyAutoGUI, ctypes window detector).
- [google_sheets.py](file:///C:/Users/Admin/OneDrive/T%C3%A0i%20li%E1%BB%87u/ERP%20BOT/erp_automation/google_sheets.py): Kết nối API Google Sheets, xử lý Excel Serial Date Row 2 và cắt dừng ở Dòng Công Thức TỔNG.
- [config.json](file:///C:/Users/Admin/OneDrive/T%C3%A0i%20li%E1%BB%87u/ERP%20BOT/erp_automation/config.json): Lưu trữ tọa độ click chuột và cấu hình mặc định (Bộ phận, Kho).

---

## 2. Quy Trình Xử Lý Dữ Liệu Google Sheets (`google_sheets.py`)

1. **Xử Lý Ngày Tháng (Row 2 Date Formatting)**:
   - Row 2 chứa các giá trị ngày dạng Excel Serial Number (ví dụ: `46227` = `2026/07/24`).
   - Tự động convert: `datetime(1899, 12, 30) + timedelta(days=int(serial))` $\rightarrow$ `YYYY/MM/DD`.
2. **Quy Tắc Cắt Dừng Bằng Dòng Công Thức TỔNG**:
   - Khi quét cột Số lượng cho từng ngày, nếu phát hiện ô chứa công thức bắt đầu bằng `=SUM(` hoặc `=SUMPRODUCT(`, robot ngắt dừng đọc cho ngày đó.
3. **Phân Loại Định Danh 2 Trang Tính**:
   - **Sheet `ERP Chỉ`**: Sử dụng Mã Bộ Phận `3820` và Mã Kho `C21`.
   - **Sheet `ERP Nhựa`**: Sử dụng Mã Bộ Phận `3810` và Mã Kho `C11`.

---

## 3. Quy Trình Thao Tác Giao Diện ERP iGP (`erp_gui.py`)

1. **Nhận Diện Cửa Sổ Con MDI INVI08 (Real-time Window Detection)**:
   - Dùng `ctypes.windll.user32.EnumWindows` và `EnumChildWindows` để soi tiêu đề các cửa sổ con chứa `"INVI08"` hoặc `"chuyển kho"`.
   - **Nếu INVI08 đã mở**: Bỏ qua Bước 2 (Mở INVI08) & Bước 3 (Maximize), bắt đầu trực tiếp từ **Bước 4 (Nút Thêm `21, 126`)**.
   - **Nếu chưa mở**: Click `(1095, 337)` mở INVI08 $\rightarrow$ Click `(1417, 251)` Maximize cửa sổ $\rightarrow$ Click `(21, 126)` nút Thêm.
2. **Điền Thông Tin Chứng Từ Đầu Phân Đoạn**:
   - Click ô Loại phiếu `(197, 202)` $\rightarrow$ Gõ `1201`.
   - Bấm `Tab` $\rightarrow$ Gõ Ngày thực tế `YYYY/MM/DD`.
   - Bấm `Tab` $\rightarrow$ Gõ Mã Bộ Phận (`3820` cho Chỉ, `3810` cho Nhựa).
3. **Nhập Chi Tiết Sản Phẩm & Nhảy Tọa Độ $Y+20\text{px}$**:
   - Tọa độ chi tiết sử dụng Click trực tiếp (Thay vì Tab để tránh lỗi cột): Mã SP `(166, 535)`, Số lượng `(500, 535)`, Nhập Kho `(1440, 535)`.
   - **Dòng 1**: Click Ô Mã SP $\rightarrow$ Gõ Mã SP. Click Ô Số Lượng $\rightarrow$ Gõ SL. Click Ô Nhập Kho $\rightarrow$ Gõ Mã Kho (`C21` hoặc `C11`).
   - **Dòng 2+**: Bấm phím Down Arrow (`↓`) để tạo dòng mới. Tính toán $Y_k = 535 + (k-1) \times 20$. Click Ô Mã SP ở $Y_k$ $\rightarrow$ Gõ Mã SP. Click Ô Số Lượng ở $Y_k$ $\rightarrow$ Gõ SL. Khônng cần nhập lại Ô Nhập Kho (ERP tự động copy).

---

## 4. Cơ Chế Dừng Khẩn Cấp (Emergency Stop)

- **Failsafe Mouse Corner**: Rê con trỏ chuột thật nhanh về góc trên bên trái màn hình `(0,0)`.
- **Keyboard Shortcut**: Bấm `Ctrl + C` trong cửa sổ lệnh.
- **GUI Stop Button**: Bấm nút **`[ 🛑 DỪNG KHẨN CẤP ]`** trên ứng dụng Desktop.

---

## 5. Đóng Gói Ứng Dụng GUI App PC

- Tệp chạy chính: `dist/ERP Bot iGP.exe` (Single standalone executable).
- Cài đặt Icon nhúng trực tiếp: `app_icon.ico` (256x256 HD Robot Icon).
- Thư mục đặt Lối tắt: `C:\Users\Admin\Desktop\ERP Bot iGP.exe` (cho phép Right-click chọn Pin to Taskbar).
