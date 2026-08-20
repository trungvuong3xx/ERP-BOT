import sys
import time
from erp_gui import ERPGUIController

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=========================================================")
    print("  KIỂM TRA TỰ ĐỘNG NHẬN DIỆN MÀN HÌNH ERP INVI08")
    print("=========================================================")

    gui = ERPGUIController("C:\\ConductorX64\\C_dsbin\\MainMenu.exe", "51225", "51225")
    gui.launch_or_connect()

    is_open = gui.is_invi08_open()
    print("\n---------------------------------------------------------")
    if is_open:
        print("✅ PHÁT HIỆN THÀNH CÔNG: CỬA SỔ INVI08 ĐANG MỞ TRÊN MÀN HÌNH!")
        print("--> Robot sẽ BỎ QUA MỞ CỬA SỔ, nhảy thẳng vào bấm NÚT THÊM (Bước 4).")
    else:
        print("ℹ️ CHƯA THẤY CỬA SỔ INVI08 -> BẠN ĐANG Ở TRANG CHỦ ERP.")
        print("--> Robot sẽ MỞ INVI08 (Bước 2) và MAXIMIZE (Bước 3).")
    print("---------------------------------------------------------\n")

if __name__ == '__main__':
    main()
