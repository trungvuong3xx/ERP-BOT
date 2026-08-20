import sys
import gspread

def check_day28():
    sys.stdout.reconfigure(encoding='utf-8')
    credentials_path = r'C:\Users\Admin\Downloads\credentials.json'
    gc = gspread.service_account(filename=credentials_path)
    sh = gc.open('ERP và BÁO CÁO')

    ws2 = sh.worksheet('ERP Nhựa')
    v2 = ws2.get_all_values()
    c_idx = 82  # Day 28: 1 + (28-1)*3 = 82 (0-indexed)

    print("=== TAB: ERP Nhựa (XUẤT NGÀY 28) ===")
    count = 0
    for r in range(35, 46):
        code = v2[r][c_idx].strip() if len(v2[r]) > c_idx else ''
        qty = v2[r][c_idx+2].strip() if len(v2[r]) > c_idx+2 else ''
        if code:
            count += 1
            print(f"Dòng {count}: Hàng {r+1:2d} | Mã='{code}' | Qty='{qty}'")

if __name__ == '__main__':
    check_day28()
