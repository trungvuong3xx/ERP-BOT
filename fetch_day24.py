import sys
import gspread

def fetch_day24():
    sys.stdout.reconfigure(encoding='utf-8')
    credentials_path = r'C:\Users\Admin\Downloads\credentials.json'
    gc = gspread.service_account(filename=credentials_path)
    sh = gc.open('ERP và BÁO CÁO')
    ws = sh.worksheet('ERP Chỉ')
    all_vals = ws.get_all_values()

    day = 24
    col_idx = 1 + (day - 1) * 3  # Index 70 (1-based: Col 70, 71, 72)

    print(f"=== CHI TIẾT DỮ LIỆU XUẤT - TAB 'ERP Chỉ' - NGÀY {day} ===")
    
    items = []
    for r_idx in range(19, min(35, len(all_vals))):
        row = all_vals[r_idx]
        code = row[col_idx].strip() if col_idx < len(row) else ''
        spec = row[col_idx + 1].strip() if col_idx + 1 < len(row) else ''
        qty = row[col_idx + 2].strip() if col_idx + 2 < len(row) else ''

        if code and code not in ['Không có', '#N/A', '#REF!', '#VALUE!', '#NAME?', '#DIV/0!']:
            items.append({
                'row': r_idx + 1,
                'code': code,
                'spec': spec,
                'qty': qty
            })

    print(f"Tổng số mã XUẤT trong Ngày {day}: {len(items)} mã\n")
    print(f"{'STT':<4} | {'HÀNG':<6} | {'MÃ SẢN PHẨM':<18} | {'QUY CÁCH':<30} | {'SỐ LƯỢNG'}")
    print("-" * 75)
    for idx, item in enumerate(items, start=1):
        print(f"{idx:<4} | {item['row']:<6} | {item['code']:<18} | {item['spec']:<30} | {item['qty']}")

if __name__ == "__main__":
    fetch_day24()
