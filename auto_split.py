import json
import random
import re
import os

print("Đang tự động phân chia tập Train / Valid / Test...")

# 1. Đọc tổng hợp dữ liệu
meta_path = r'data\processed\tc\metadata.json'
if not os.path.exists(meta_path):
    print("Không tìm thấy metadata.json. Hãy chạy prepare_tcsinger_midi... trước!")
    exit()

with open(meta_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Lấy danh sách tên các bài hát duy nhất
all_items = list(set([item['item_name'] for item in data]))

# Xáo trộn ngẫu nhiên để chọn công bằng
random.shuffle(all_items)

total = len(all_items)
print(f"Tổng số bài hát tìm thấy: {total}")

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

# Chuyển list Python thành chuỗi mảng YAML (đổi nháy đơn thành nháy kép)
str_valid = str(valid_list).replace("'", '"')
str_test = str(test_list).replace("'", '"')

# Dùng Regex tìm và thay thế chính xác dòng cấu hình
content = re.sub(r"valid_prefixes:\s*\[.*?\]", f"valid_prefixes: {str_valid}", content)
content = re.sub(r"test_prefixes:\s*\[.*?\]", f"test_prefixes: {str_test}", content)

with open(yaml_path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"[THÀNH CÔNG] Đã chia tự động và cập nhật tcsinger.yaml!")
print(f" - Tập Valid: {valid_list}")
print(f" - Tập Test : {test_list}")
print(f" - Tập Train: Các bài còn lại.")