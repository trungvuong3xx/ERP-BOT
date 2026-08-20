import sys
import ctypes
from ctypes import wintypes
import psutil

def inspect_all_ctypes():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=== INSPECTING ALL VISIBLE WINDOW TITLES ON DESKTOP ===")

    user32 = ctypes.windll.user32
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def enum_cb(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value
                
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                try:
                    pname = psutil.Process(pid.value).name()
                except Exception:
                    pname = 'unknown'

                print(f"HWND {hwnd:8d} | PID {pid.value:5d} ({pname:<20}) | Title: '{title}'")
                
                # Check child windows
                def child_cb(ch_hwnd, ch_lparam):
                    c_len = user32.GetWindowTextLengthW(ch_hwnd)
                    if c_len > 0:
                        c_buf = ctypes.create_unicode_buffer(c_len + 1)
                        user32.GetWindowTextW(ch_hwnd, c_buf, c_len + 1)
                        c_title = c_buf.value
                        print(f"      Child HWND {ch_hwnd}: '{c_title}'")
                    return True

                user32.EnumChildWindows(hwnd, WNDENUMPROC(child_cb), 0)
        return True

    cb = WNDENUMPROC(enum_cb)
    user32.EnumWindows(cb, 0)

if __name__ == '__main__':
    inspect_all_ctypes()
