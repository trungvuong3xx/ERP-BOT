import sys
import gspread

def check_chi_day25():
    sys.stdout.reconfigure(encoding='utf-8')
    credentials_path = r'C:\Users\Admin\Downloads\credentials.json'
    gc = gspread.service_account(filename=credentials_path)
    sh = gc.open('ERP và BÁO CÁO')

    ws1 = sh.worksheet('ERP Chỉ')
    v1 = ws1.get_all_values()
    c_idx = 73  # Day 25: 1 + (25-1)*3 = 73 (0-indexed)

    print("=== TAB: ERP Chỉ (XUẤT NGÀY 25) ===")
    count = 0
    for r in range(19, 35):
        code = v1[r][c_idx].strip() if len(v1[r]) > c_idx else ''
        qty = v1[r][c_idx+2].strip() if len(v1[r]) > c_idx+2 else ''
        if code:
            count += 1
            print(f"Dòng {count}: Hàng {r+1:2d} | Mã='{code}' | Qty='{qty}'")

if __name__ == '__main__':
    check_chi_day25()
