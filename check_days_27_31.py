import sys
import gspread

def check_range():
    sys.stdout.reconfigure(encoding='utf-8')
    credentials_path = r'C:\Users\Admin\Downloads\credentials.json'
    gc = gspread.service_account(filename=credentials_path)
    sh = gc.open('ERP và BÁO CÁO')

    ws1 = sh.worksheet('ERP Chỉ')
    v1 = ws1.get_all_values()
    forms1 = ws1.get_all_values(value_render_option='FORMULA')

    for day in range(27, 32):
        c_idx = 1 + (day - 1) * 3
        items = []
        for r in range(19, 35):
            code = v1[r][c_idx].strip() if len(v1[r]) > c_idx else ''
            qty = v1[r][c_idx+2].strip() if len(v1[r]) > c_idx+2 else ''
            form = forms1[r][c_idx+2].strip() if r < len(forms1) and len(forms1[r]) > c_idx+2 else ''
            if 'SUM(' in form.upper():
                break
            if code and code not in ['Không có', '#N/A', '#REF!']:
                items.append((r+1, code, qty))
        
        date_str = f"2026/07/{day:02d}"
        print(f"=== NGÀY {day} ({date_str}): {len(items)} DÒNG ===")
        for idx, it in enumerate(items, start=1):
            print(f"  {idx}. Hàng {it[0]:2d}: Mã='{it[1]}', SL='{it[2]}'")

if __name__ == '__main__':
    check_range()
