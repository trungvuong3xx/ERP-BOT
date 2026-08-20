import os
import sys
import shutil
import ctypes

def deploy_exe():
    sys.stdout.reconfigure(encoding='utf-8')

    project_dir = r"C:\Users\Admin\OneDrive\Tài liệu\ERP BOT\erp_automation"
    built_exe = os.path.join(project_dir, "dist", "ERP Bot iGP.exe")

    if not os.path.exists(built_exe):
        print(f"❌ KHÔNG TÌM THẤY TỆP BUILD: '{built_exe}'")
        return

    desktops = [
        os.path.expanduser(r"~\Desktop"),
        os.path.expanduser(r"~\OneDrive\Desktop")
    ]

    for d in desktops:
        if os.path.exists(d):
            # 1. Remove old broken shortcuts if any
            old_lnk = os.path.join(d, "ERP Bot iGP.lnk")
            if os.path.exists(old_lnk):
                try:
                    os.remove(old_lnk)
                    print(f"🧹 Đã dọn dẹp Lối tắt cũ: '{old_lnk}'")
                except Exception as e:
                    print(f"Lỗi khi xóa shortcut cũ: {e}")

            # 2. Copy the standalone .exe file directly to Desktop
            target_desktop_exe = os.path.join(d, "ERP Bot iGP.exe")
            try:
                shutil.copy2(built_exe, target_desktop_exe)
                print(f"✅ ĐÃ ĐẶT TỆP .EXE NGUYÊN KHỐI TRỰC TIẾP TRÊN DESKTOP: '{target_desktop_exe}'")
            except Exception as e:
                print(f"Lỗi khi copy file exe: {e}")

    # Force Windows Shell icon refresh
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
    print("✅ ĐÃ NẠP LẠI BỘ NHỚ ICON CHO WINDOWS EXPLORER!")

if __name__ == '__main__':
    deploy_exe()
