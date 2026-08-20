import sys
import gspread

def check_month():
    sys.stdout.reconfigure(encoding='utf-8')
    credentials_path = r'C:\Users\Admin\Downloads\credentials.json'
    gc = gspread.service_account(filename=credentials_path)
    sh = gc.open('ERP và BÁO CÁO')

    ws_chi = sh.worksheet('ERP Chỉ')
    all_vals = ws_chi.get_all_values()

    print("=== CÁC HÀNG ĐẦU CỦA TAB 'ERP Chỉ' ===")
    for idx in range(min(10, len(all_vals))):
        row = all_vals[idx]
        non_empty = [(c_idx + 1, val) for c_idx, val in enumerate(row) if val.strip()]
        if non_empty:
            print(f"Hàng {idx+1}: {non_empty[:10]}")

    print("\n=== QUÉT TÌM THÔNG TIN THÁNG / NĂM TRÊN TẤT CẢ CÁC TAB ===")
    for ws in sh.worksheets():
        v = ws.get_all_values()
        title = ws.title
        found = []
        for r_i, r in enumerate(v[:20]):
            for c_i, c in enumerate(r):
                c_str = c.strip()
                if any(k in c_str.lower() for k in ['tháng', 'thang', '2024', '2025', '2026', 'thg', 'month', 'th']):
                    found.append(f"Hàng {r_i+1} Cột {c_i+1}: '{c_str}'")
        if found:
            print(f"Tab [{title}]: {found[:5]}")

if __name__ == "__main__":
    check_month()
