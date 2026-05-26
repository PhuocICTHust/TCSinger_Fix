import csv
import json
import os
import re
import argparse

def note_to_midi(note_str):
    """Chuyển đổi nốt nhạc (VD: F#3+5, A3-4, rest) sang mã số MIDI"""
    if note_str.lower() == 'rest':
        return 0
    
    # Dùng Regex để bóc tách chính xác Tên nốt (VD: F#) và Quãng tám (VD: 3), bỏ qua phần Cents (+5)
    match = re.match(r'([A-G]#?)(-?\d+)', note_str)
    if not match:
        return 0
        
    note_base, octave = match.groups()
    notes_map = {'C':0, 'C#':1, 'D':2, 'D#':3, 'E':4, 'F':5, 'F#':6, 'G':7, 'G#':8, 'A':9, 'A#':10, 'B':11}
    
    # Công thức tính chuẩn MIDI
    return 12 * (int(octave) + 1) + notes_map[note_base.upper()]

def convert_csv_to_metadata(csv_path, wav_dir, output_dir):
    if not os.path.exists(csv_path):
        print(f"[!] Không tìm thấy file: {csv_path}")
        return

    os.makedirs(output_dir, exist_ok=True)
    metadata = []
    unique_phones = set()
    global_singer_dict = {}
    singer_id_counter = 0
    success_count = 0

    print(f"Đang đọc dữ liệu từ {csv_path} ...")

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=',') 
        
        for row in reader:
            try:
                name = row['name'].strip()
                
                # 1. Xử lý Ca sĩ
                parts = name.rsplit('_', 1)
                singer = parts[0] if len(parts) == 2 else 'Singer1'
                if singer not in global_singer_dict:
                    global_singer_dict[singer] = singer_id_counter
                    singer_id_counter += 1

                # Đường dẫn file Wav (Hỗ trợ đường dẫn tuyệt đối nếu file wav nằm chỗ khác)
                wav_fn = os.path.abspath(os.path.join(wav_dir, f"{name}.wav"))
                
                # 2. Xử lý Âm vị tiếng Anh (Xóa số 0, 1, 2)
                ph_seq_raw = row['ph_seq'].strip().split()
                ph_seq_clean = [re.sub(r'\d', '', p) for p in ph_seq_raw]
                unique_phones.update(ph_seq_clean)
                
                ph_durs = [float(x) for x in row['ph_dur'].strip().split()]
                
                # 3. Lấy Dữ liệu Nhạc lý
                note_seq = row['note_seq'].strip().split()
                note_durs = [float(x) for x in row['note_dur'].strip().split()]
                note_slurs = [int(x) for x in row['note_slur'].strip().split()]
                
                ep_pitches = []
                ep_notedurs = []
                ep_types = []
                
                # 4. Thuật toán Đồng bộ & Gán Type
                for i in range(len(ph_seq_clean)):
                    ph = ph_seq_clean[i]
                    
                    # Nếu là khoảng lặng (SP, AP)
                    if ph in ['SP', 'AP'] or (i < len(note_seq) and note_seq[i].lower() == 'rest'):
                        ep_pitches.append(0)
                        ep_types.append(1) # Type 1: Silence
                        ep_notedurs.append(ph_durs[i])
                    else:
                        # Đọc nốt và chuyển sang MIDI
                        note_str = note_seq[i] if i < len(note_seq) else "rest"
                        ep_pitches.append(note_to_midi(note_str))
                        
                        # Đọc nốt luyến
                        slur_val = note_slurs[i] if i < len(note_slurs) else 0
                        ep_types.append(3 if slur_val == 1 else 2) # Type 3: Slur, Type 2: Normal
                        
                        # Thời lượng nốt
                        ep_notedurs.append(note_durs[i] if i < len(note_durs) else ph_durs[i])

                # Đóng gói 1 bài hát
                metadata.append({
                    "item_name": name,
                    "wav_fn": wav_fn,
                    "txt": row['raw_lyrics'].strip(),
                    "ph": " ".join(ph_seq_clean),
                    "ph_durs": [round(d, 5) for d in ph_durs],
                    "ep_pitches": ep_pitches,
                    "ep_notedurs": [round(d, 5) for d in ep_notedurs],
                    "ep_types": ep_types,
                    "singer": singer
                })
                success_count += 1
                
            except Exception as e:
                print(f"[!] Bỏ qua dòng {row.get('name', 'Unknown')} do lỗi: {e}")

    # ===== GHI FILE XUẤT =====
    # 1. metadata.json
    with open(os.path.join(output_dir, 'metadata.json'), 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)
        
    # 2. phone_set.json (Đảm bảo SP, AP luôn ở đầu)
    final_phones = list(unique_phones)
    for token in ['SP', 'AP']:
        if token in final_phones: final_phones.remove(token)
    final_phones = ['SP', 'AP'] + sorted(final_phones)
    
    with open(os.path.join(output_dir, 'phone_set.json'), 'w', encoding='utf-8') as f:
        json.dump(final_phones, f, indent=4, ensure_ascii=False)
        
    # 3. spker_set.json
    with open(os.path.join(output_dir, 'spker_set.json'), 'w', encoding='utf-8') as f:
        json.dump(global_singer_dict, f, indent=4, ensure_ascii=False)

    print("-" * 50)
    print(f"✅ Hoàn tất! Đã xử lý thành công: {success_count} bài hát.")
    print(f"✅ Danh sách ca sĩ: {global_singer_dict}")
    print(f"✅ Các file JSON đã được lưu an toàn tại: {os.path.abspath(output_dir)}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="TCSinger CSV to JSON Preprocessor")
    parser.add_argument('--csv_path', type=str, required=True, help='Đường dẫn tới file transcription.txt (CSV)')
    parser.add_argument('--wav_dir', type=str, required=True, help='Thư mục chứa các file âm thanh .wav')
    parser.add_argument('--output_dir', type=str, default='data/processed/tc', help='Thư mục xuất file JSON')
    
    args = parser.parse_args()
    convert_csv_to_metadata(args.csv_path, args.wav_dir, args.output_dir)