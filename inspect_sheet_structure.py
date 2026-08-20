import sys
import gspread

def inspect_structure():
    sys.stdout.reconfigure(encoding='utf-8')
    credentials_path = r'C:\Users\Admin\Downloads\credentials.json'
    gc = gspread.service_account(filename=credentials_path)
    sh = gc.open('ERP và BÁO CÁO')

    ws_chi = sh.worksheet('ERP Chỉ')
    all_vals = ws_chi.get_all_values(value_render_option='FORMATTED_VALUE')
    all_forms = ws_chi.get_all_values(value_render_option='FORMULA')

    print(f"=== ĐỌC CẤU TRÚC TOÀN BỘ CÁC DANH MỤC TRÊN TAB 'ERP Chỉ' ({len(all_vals)} HÀNG) ===")

    sections = []
    current_sec = None
    start_row = None

    for r_i, row in enumerate(all_vals):
        r_num = r_i + 1
        label = row[0].strip() if len(row) > 0 else ''
        qty_form = all_forms[r_i][72].strip() if r_i < len(all_forms) and len(all_forms[r_i]) > 72 else ''
        qty_val = row[72].strip() if len(row) > 72 else ''

        if label:
            print(f"Hàng {r_num:3d} | Cột A: '{label:<20}' | Cột Ngày 24 Form: '{qty_form:<25}' | Value: '{qty_val}'")

if __name__ == '__main__':
    inspect_structure()
