import sys
import gspread

def inspect_nhua():
    sys.stdout.reconfigure(encoding='utf-8')
    credentials_path = r'C:\Users\Admin\Downloads\credentials.json'
    gc = gspread.service_account(filename=credentials_path)
    sh = gc.open('ERP và BÁO CÁO')

    ws_nhua = sh.worksheet('ERP Nhựa')
    all_vals = ws_nhua.get_all_values(value_render_option='FORMATTED_VALUE')
    all_forms = ws_nhua.get_all_values(value_render_option='FORMULA')

    print(f"=== ĐỌC CẤU TRÚC TOÀN BỘ CÁC DANH MỤC TRÊN TAB 'ERP Nhựa' ({len(all_vals)} HÀNG) ===")

    for r_i, row in enumerate(all_vals):
        r_num = r_i + 1
        label = row[0].strip() if len(row) > 0 else ''
        # Let's inspect Column A, B, C or any column that contains section headers or formulas
        col_b = row[1].strip() if len(row) > 1 else ''
        col_c = row[2].strip() if len(row) > 2 else ''
        
        # Check Day 24 column (c_idx = 1 + (24-1)*3 = 70)
        qty_form = all_forms[r_i][72].strip() if r_i < len(all_forms) and len(all_forms[r_i]) > 72 else ''
        qty_val = row[72].strip() if len(row) > 72 else ''

        if label or any(k in qty_form.upper() for k in ['SUM(', 'SUMPRODUCT(']):
            print(f"Hàng {r_num:3d} | Cột A: '{label:<22}' | Cột B: '{col_b:<15}' | Cột C: '{col_c:<15}' | Form Ngày 24: '{qty_form:<25}' | Val: '{qty_val}'")

if __name__ == '__main__':
    inspect_nhua()
