import os
import sys
import shutil
import ctypes
from win32com.client import Dispatch

def setup_exe_shortcut():
    sys.stdout.reconfigure(encoding='utf-8')

    project_dir = r"C:\Users\Admin\OneDrive\Tài liệu\ERP BOT\erp_automation"
    dist_dir = os.path.join(project_dir, "dist", "ERP Bot iGP")
    target_exe = os.path.join(dist_dir, "ERP Bot iGP.exe")

    # Copy config.json to dist directory if needed
    config_src = os.path.join(project_dir, "config.json")
    config_dst = os.path.join(dist_dir, "config.json")
    if os.path.exists(config_src):
        shutil.copy(config_src, config_dst)
        print(f"✅ Đã copy config.json vào thư mục app: '{config_dst}'")

    # Copy icon to dist directory
    icon_src = os.path.join(project_dir, "app_icon.ico")
    icon_dst = os.path.join(dist_dir, "app_icon.ico")
    if os.path.exists(icon_src):
        shutil.copy(icon_src, icon_dst)

    desktops = [
        os.path.expanduser(r"~\Desktop"),
        os.path.expanduser(r"~\OneDrive\Desktop")
    ]

    shell = Dispatch('WScript.Shell')

    for d in desktops:
        if os.path.exists(d):
            lnk_path = os.path.join(d, "ERP Bot iGP.lnk")
            # Delete old shortcut if exists
            if os.path.exists(lnk_path):
                try:
                    os.remove(lnk_path)
                except Exception:
                    pass

            shortcut = shell.CreateShortcut(lnk_path)
            shortcut.TargetPath = target_exe
            shortcut.WorkingDirectory = dist_dir
            shortcut.IconLocation = f"{target_exe},0"
            shortcut.WindowStyle = 1
            shortcut.Description = "Ứng dụng Tự Động Hóa Nhập Liệu WorkFlow ERP iGP"
            shortcut.Save()
            print(f"✅ ĐÃ TẠO LỐI TẮT FILE .EXE NGUYÊN KHỐI TẠI: '{lnk_path}'")

    # Refresh Windows Shell Icon Cache
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
    print("✅ ĐÃ NẠP LẠI BỘ NHỚ ICON CHO WINDOWS EXPLORER!")

if __name__ == '__main__':
    setup_exe_shortcut()
