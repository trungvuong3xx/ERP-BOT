import sys
import ctypes
from ctypes import wintypes

def test_detect_ctypes():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=== TESTING CTYPES INVI08 WINDOW DETECTION ===")

    user32 = ctypes.windll.user32
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    found_windows = []

    def enum_desktop_windows(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value
                
                if "INVI08" in title or "chuyển kho" in title.lower() or "chuyen kho" in title.lower():
                    found_windows.append((hwnd, "TopWindow", title))
                
                # Check child windows
                def enum_child(ch_hwnd, ch_lparam):
                    c_len = user32.GetWindowTextLengthW(ch_hwnd)
                    if c_len > 0:
                        c_buf = ctypes.create_unicode_buffer(c_len + 1)
                        user32.GetWindowTextW(ch_hwnd, c_buf, c_len + 1)
                        c_title = c_buf.value
                        if "INVI08" in c_title or "chuyển kho" in c_title.lower() or "chuyen kho" in c_title.lower():
                            found_windows.append((ch_hwnd, "ChildWindow", c_title))
                    return True

                user32.EnumChildWindows(hwnd, WNDENUMPROC(enum_child), 0)
        return True

    cb = WNDENUMPROC(enum_desktop_windows)
    user32.EnumWindows(cb, 0)

    if found_windows:
        print(f"✅ BỘ QUÉT TÌM THẤY {len(found_windows)} CỬA SỔ INVI08 ĐANG MỞ TRÊN MÀN HÌNH:")
        for hw, wtype, t in found_windows:
            print(f"   - [{wtype}] HWND: {hw} | Title: '{t}'")
    else:
        print("❌ KHÔNG TÌM THẤY CỬA SỔ INVI08 NÀO ĐANG MỞ TRÊN MÀN HÌNH.")

if __name__ == '__main__':
    test_detect_ctypes()
