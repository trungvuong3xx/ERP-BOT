import pyautogui
import time
import os

os.system('color 0A')
print("="*60)
print("   TOOL LẤY TỌA ĐỘ CHUỘT THỜI GIAN THỰC (REAL-TIME MOUSE POS)")
print("   Di chuyển chuột đến vị trí muốn lấy tọa độ trên màn hình.")
print("   Nhấn tổ hợp phím CTRL + C trong cửa sổ này để dừng.")
print("="*60 + "\n")

try:
    while True:
        x, y = pyautogui.position()
        print(f"\r📌 Tọa độ chuột hiện tại: X = {x:4d} | Y = {y:4d}   (Di chuột đến nút/ô cần lấy)", end="", flush=True)
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\n\n✅ Đã dừng lấy tọa độ chuột!")
