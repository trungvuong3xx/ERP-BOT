import sys
import gspread

def check_both():
    sys.stdout.reconfigure(encoding='utf-8')
    credentials_path = r'C:\Users\Admin\Downloads\credentials.json'
    gc = gspread.service_account(filename=credentials_path)
    sh = gc.open('ERP và BÁO CÁO')

    print("=== TAB: ERP Chỉ (XUẤT NGÀY 24) ===")
    ws1 = sh.worksheet('ERP Chỉ')
    v1 = ws1.get_all_values()
    for r in range(19, 30):
        print(f"Hàng {r+1:2d}: Mã='{v1[r][70]}', Qty='{v1[r][72]}'")

    print("\n=== TAB: ERP Nhựa (XUẤT NGÀY 24) ===")
    ws2 = sh.worksheet('ERP Nhựa')
    v2 = ws2.get_all_values()
    for r in range(35, 46):
        print(f"Hàng {r+1:2d}: Mã='{v2[r][70]}', Qty='{v2[r][72]}'")

if __name__ == '__main__':
    check_both()
