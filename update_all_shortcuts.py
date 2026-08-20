import os
import sys
import ctypes
from win32com.client import Dispatch

def fix_all_desktops():
    sys.stdout.reconfigure(encoding='utf-8')
    project_dir = r"C:\Users\Admin\OneDrive\Tài liệu\ERP BOT\erp_automation"
    icon_path = os.path.join(project_dir, "app_icon.ico")
    pyw_path = r"C:\Users\Admin\AppData\Local\Programs\Python\Python312\pythonw.exe"
    script_path = os.path.join(project_dir, "main.py")

    desktops = [
        os.path.expanduser(r"~\Desktop"),
        os.path.expanduser(r"~\OneDrive\Desktop")
    ]

    shell = Dispatch('WScript.Shell')

    for d in desktops:
        if os.path.exists(d):
            lnk_path = os.path.join(d, "ERP Bot iGP.lnk")
            shortcut = shell.CreateShortcut(lnk_path)
            shortcut.TargetPath = pyw_path
            shortcut.Arguments = f'"{script_path}" --gui'
            shortcut.WorkingDirectory = project_dir
            shortcut.IconLocation = f"{icon_path},0"
            shortcut.WindowStyle = 1
            shortcut.Description = "Ứng dụng Tự Động Hóa Nhập Liệu WorkFlow ERP iGP"
            shortcut.Save()
            print(f"✅ Đã làm mới Icon tệp Lối tắt tại: '{lnk_path}'")

    # Refresh Windows Shell
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
    print("✅ Đã làm mới Icon Cache toàn hệ thống thành công!")

if __name__ == '__main__':
    fix_all_desktops()
