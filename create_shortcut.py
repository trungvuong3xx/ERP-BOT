import os
import sys
from win32com.client import Dispatch

def create_desktop_shortcut():
    sys.stdout.reconfigure(encoding='utf-8')
    shell = Dispatch('WScript.Shell')
    desktop = shell.SpecialFolders("Desktop")
    shortcut_path = os.path.join(desktop, "ERP Bot iGP.lnk")
    
    target_bat = os.path.abspath(os.path.join(os.path.dirname(__file__), "ERP_Bot_Launcher.bat"))
    working_dir = os.path.abspath(os.path.dirname(__file__))

    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.TargetPath = target_bat
    shortcut.WorkingDirectory = working_dir
    shortcut.WindowStyle = 1
    shortcut.Description = "Ứng dụng Tự Động Hóa Nhập Liệu WorkFlow ERP iGP"
    shortcut.save()

    print(f"✅ ĐÃ TẠO THÀNH CÔNG LỐI TẮT TRÊN DESKTOP: '{shortcut_path}'")

if __name__ == '__main__':
    create_desktop_shortcut()
