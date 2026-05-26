import json
import random
import re
import os

print("Đang tự động phân chia tập Train / Valid / Test...")

# 1. Đọc tổng hợp dữ liệu
meta_path = r'data\processed\tc\metadata.json'
if not os.path.exists(meta_path):
    print("Không tìm thấy metadata.json. Hãy chạy file binarize trước!")
    exit()

with open(meta_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Lấy danh sách tên các bài hát duy nhất (item_name)
all_items = list(set([item['item_name'] for item in data]))

# Xáo trộn ngẫu nhiên để chọn công bằng
random.seed(1234) # Set seed để kết quả ổn định mỗi lần chạy
random.shuffle(all_items)

total = len(all_items)
print(f"Tổng số dữ liệu (item_name) tìm thấy: {total}")

# 2. Tính toán tỷ lệ (10% Valid, 10% Test)
num_valid = max(1, int(total * 0.1))
num_test = max(1, int(total * 0.1))

if total < 3:
    # Nếu dữ liệu quá ít (chỉ có 1-2 bài), ép lấy bài đầu tiên cho cả test và valid để tránh lỗi
    valid_list = [all_items[0]]
    test_list = [all_items[0]]
else:
    # Cắt danh sách
    valid_list = all_items[:num_valid]
    test_list = all_items[num_valid:num_valid+num_test]

# 3. Mở và sửa file cấu hình YAML
yaml_path = r"egs\tcsinger.yaml"
with open(yaml_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Hàm format list thành chuẩn YAML (mỗi item 1 dòng)
def format_yaml_list(lst):
    if not lst:
        return "[]"
    items_str = ",\n  ".join([f"'{x}'" for x in lst])
    return f"[\n  {items_str}\n]"

str_valid = format_yaml_list(valid_list)
str_test = format_yaml_list(test_list)

# Dùng Regex với cờ re.DOTALL để quét qua cả các dấu xuống dòng \n
content = re.sub(r"valid_prefixes:\s*\[.*?\]", f"valid_prefixes: {str_valid}", content, flags=re.DOTALL)
content = re.sub(r"test_prefixes:\s*\[.*?\]", f"test_prefixes: {str_test}", content, flags=re.DOTALL)

with open(yaml_path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"[THÀNH CÔNG] Đã chia tự động và cập nhật tcsinger.yaml!")
print(f" - Tập Valid ({len(valid_list)} bài): {valid_list}")
print(f" - Tập Test  ({len(test_list)} bài): {test_list}")
print(f" - Tập Train : Các bài còn lại.")