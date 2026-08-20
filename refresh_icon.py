import os
import sys
import ctypes
from win32com.client import Dispatch
import win32gui, win32con

def update_shortcut_and_refresh():
    sys.stdout.reconfigure(encoding='utf-8')
    
    project_dir = r"C:\Users\Admin\OneDrive\Tài liệu\ERP BOT\erp_automation"
    icon_path = os.path.join(project_dir, "app_icon.ico")
    bat_path = os.path.join(project_dir, "ERP_Bot_Launcher.bat")
    pyw_path = r"C:\Users\Admin\AppData\Local\Programs\Python\Python312\pythonw.exe"
    script_path = os.path.join(project_dir, "main.py")

    shell = Dispatch('WScript.Shell')
    desktop = shell.SpecialFolders("Desktop")
    shortcut_path = os.path.join(desktop, "ERP Bot iGP.lnk")

    shortcut = shell.CreateShortcut(shortcut_path)
    shortcut.TargetPath = pyw_path
    shortcut.Arguments = f'"{script_path}" --gui'
    shortcut.WorkingDirectory = project_dir
    shortcut.IconLocation = f"{icon_path},0"
    shortcut.WindowStyle = 1
    shortcut.Description = "Ứng dụng Tự Động Hóa Nhập Liệu WorkFlow ERP iGP"
    shortcut.Save()

    print(f"✅ ĐÃ CẬP NHẬT LỐI TẮT VỚI ICON VÀO: '{shortcut_path}'")

    # Notify Windows Explorer shell to refresh icons immediately
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
    print("✅ ĐÃ NẠP LẠI BỘ NHỚ ICON CHO WINDOWS EXPLORER!")

if __name__ == '__main__':
    update_shortcut_and_refresh()
