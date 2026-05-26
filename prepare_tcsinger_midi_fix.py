import os
import textgrid
import json
import argparse
import soundfile as sf
import pretty_midi
import glob

def process_and_split_with_midi(tg_path, midi_path, wav_path, output_dir, item_prefix="bai1"):
    word_dict_list = []
    
    # 1. Đọc TextGrid
    tg = textgrid.TextGrid.fromFile(tg_path)
    word_intervals = tg[0]
    ph_intervals = tg[1]
    
    for word in word_intervals:
        mark = word.mark.strip()
        if not mark: continue
        
        word_dict = {
            "word": mark,
            "start_time": round(float(word.minTime), 3),
            "end_time": round(float(word.maxTime), 3),
            "note": [], 
            "note_dur": [],
            "ph": [],
            "ph_start": [],
            "ph_end": []
        }
        word_dict_list.append(word_dict)

    # Gióng hàng Phoneme vào Word
    idx = 0
    for ph in ph_intervals:
        mark = ph.mark.strip()
        if not mark: continue
        
        min_time = round(float(ph.minTime), 3)
        max_time = round(float(ph.maxTime), 3)
        
        while idx < len(word_dict_list) and min_time >= word_dict_list[idx]['end_time']:
            idx += 1
            
        if idx < len(word_dict_list) and min_time >= word_dict_list[idx]['start_time'] and max_time <= word_dict_list[idx]['end_time']:
            word_dict_list[idx]['ph'].append(mark)
            word_dict_list[idx]['ph_start'].append(min_time)
            word_dict_list[idx]['ph_end'].append(max_time)

    # 2. Đọc file MIDI và gióng hàng nốt nhạc
    midi_data = pretty_midi.PrettyMIDI(midi_path)
    # Lấy track đầu tiên có chứa nốt nhạc (giả định đây là track vocal)
    vocal_track = None
    for instrument in midi_data.instruments:
        if len(instrument.notes) > 0:
            vocal_track = instrument.notes
            break
            
    if not vocal_track:
        raise ValueError("Không tìm thấy nốt nhạc nào trong file MIDI!")

    # Thuật toán tìm nốt MIDI khớp với từ dựa trên độ giao nhau (overlap) về thời gian
    for word in word_dict_list:
        w_start = word['start_time']
        w_end = word['end_time']
        
        matched_note = None
        max_overlap = 0
        
        for note in vocal_track:
            overlap_start = max(w_start, note.start)
            overlap_end = min(w_end, note.end)
            overlap = max(0, overlap_end - overlap_start)
            
            if overlap > max_overlap:
                max_overlap = overlap
                matched_note = note
        
        if matched_note and max_overlap > 0.05: # Cần trùng khớp ít nhất 50ms
            word['note'].append(matched_note.pitch)
            word['note_dur'].append(round(matched_note.end - matched_note.start, 3))
        else:
            # Nếu là khoảng lặng hoặc không tìm thấy nốt
            word['note'].append(0)
            word['note_dur'].append(round(w_end - w_start, 3))

    # Load audio gốc để cắt
    audio, sr = sf.read(wav_path)
    
    metadata_list = []
    unique_phones = set()
    os.makedirs(output_dir, exist_ok=True)

    # Tạo list chứa 1 chunk duy nhất (toàn bài hát)
    chunks = [word_dict_list]
    
    for i, chunk in enumerate(chunks):
        if not chunk: continue
        
        segment_name = f"{item_prefix}"
        start_time = chunk[0]['start_time']
        end_time = chunk[-1]['end_time']
        
        # Cắt file WAV (dù là cả bài thì vẫn phải lưu ra thư mục processed)
        start_sample = int(start_time * sr)
        end_sample = int(end_time * sr)
        audio_chunk = audio[start_sample:end_sample]
        
        chunk_wav_path = os.path.abspath(os.path.join(output_dir, f"{segment_name}.wav"))
        sf.write(chunk_wav_path, audio_chunk, sr)
        
        # Chuẩn bị metadata JSON
        ph_seq = []
        ph_durs = []
        ep_pitches = []
        ep_types = []
        ep_notedurs = []
        text_seq = []
        
        for word in chunk:
            text_seq.append(word['word'])
            
            notes = word['note']
            note_durs = word['note_dur']
            phones = word['ph']
            ph_starts = word['ph_start']
            ph_ends = word['ph_end']
            
            # TRƯỜNG HỢP 1: Khoảng lặng hoặc lỗi không có nốt
            if not notes or not phones or notes[0] == 0:
                word_pitch = 0
                word_notedur = round(word['end_time'] - word['start_time'], 3)
                for p_idx, p in enumerate(phones):
                    ph_seq.append(p)
                    unique_phones.add(p)
                    ph_durs.append(round(ph_ends[p_idx] - ph_starts[p_idx], 3))
                    ep_pitches.append(0)
                    ep_notedurs.append(word_notedur)
                    ep_types.append(1) # Type 1: Lặng
                continue

            # TRƯỜNG HỢP 2: Có nốt nhạc (Xử lý nốt chính)
            first_pitch = notes[0]
            first_dur = note_durs[0]
            
            for p_idx, p in enumerate(phones):
                ph_seq.append(p)
                unique_phones.add(p)
                p_dur = ph_ends[p_idx] - ph_starts[p_idx]
                ph_durs.append(round(p_dur, 3))
                
                ep_pitches.append(first_pitch)
                ep_notedurs.append(round(first_dur, 3))
                
                ep_type = 1 if p in ['SP', 'AP'] else 2
                ep_types.append(ep_type) # Type 2: Nốt hát bình thường
                
            # TRƯỜNG HỢP 3: Hát luyến (Slur - Có từ 2 nốt trở lên)
            if len(notes) > 1 and ep_types[-1] == 2:
                last_phone = phones[-1] # Lấy nguyên âm cuối cùng để kéo dài
                total_slur_dur = sum(note_durs[1:])
                last_ph_idx = len(ph_durs) - 1
                
                # Thuật toán chia lại thời gian
                if ph_durs[last_ph_idx] > total_slur_dur:
                    ph_durs[last_ph_idx] = round(ph_durs[last_ph_idx] - total_slur_dur, 3)
                    slur_durs_to_use = note_durs[1:]
                else:
                    avg_dur = round(ph_durs[last_ph_idx] / len(notes), 3)
                    ph_durs[last_ph_idx] = avg_dur
                    slur_durs_to_use = [avg_dur] * (len(notes) - 1)
                
                # Nhân bản nguyên âm cho các nốt luyến tiếp theo
                for i in range(1, len(notes)):
                    slur_pitch = notes[i]
                    slur_dur = slur_durs_to_use[i-1]
                    
                    ph_seq.append(last_phone)
                    ph_durs.append(slur_dur)
                    
                    ep_pitches.append(slur_pitch)
                    ep_notedurs.append(round(note_durs[i], 3))
                    ep_types.append(3) # Type 3: Đánh dấu là NỐT LUYẾN

        metadata_list.append({
            "item_name": segment_name,
            "wav_fn": chunk_wav_path,
            "txt": " ".join(text_seq),
            "ph": " ".join(ph_seq),
            "ph_durs": ph_durs,
            "ep_pitches": ep_pitches,
            "ep_notedurs": ep_notedurs,
            "ep_types": ep_types,
            "singer": "Singer1"
        })

    return metadata_list, list(unique_phones)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="TCSinger Batch Data Preprocessor")
    parser.add_argument('--raw_dir', type=str, required=True, help='Thư mục chứa toàn bộ file .wav, .mid, .TextGrid')
    parser.add_argument('--output_dir', type=str, default='data/processed/tc', help='Thư mục xuất dữ liệu')
    args = parser.parse_args()

    print(f"Bắt đầu quét thư mục: {args.raw_dir} để xử lý hàng loạt...")
    
    # Tìm tất cả file .wav trong thư mục
    wav_files = glob.glob(os.path.join(args.raw_dir, "*.wav"))
    
    if not wav_files:
        print(f"Không tìm thấy file .wav nào trong thư mục {args.raw_dir}")
        exit()
        
    all_metadata = []
    global_phone_set = set()
    success_count = 0

    for wav_path in wav_files:
        base_name = os.path.splitext(os.path.basename(wav_path))[0]
        
        tg_path = os.path.join(args.raw_dir, f"{base_name}.TextGrid")
        # Hỗ trợ cả đuôi .mid và .midi
        midi_path = os.path.join(args.raw_dir, f"{base_name}.mid")
        if not os.path.exists(midi_path):
            midi_path = os.path.join(args.raw_dir, f"{base_name}.midi")
        
        if os.path.exists(tg_path) and os.path.exists(midi_path):
            print(f" [V] Đang xử lý: {base_name}")
            try:
                metadata, phone_set = process_and_split_with_midi(
                    tg_path=tg_path, 
                    midi_path=midi_path,
                    wav_path=wav_path, 
                    output_dir=args.output_dir,
                    item_prefix=base_name
                )
                all_metadata.extend(metadata)
                global_phone_set.update(phone_set)
                success_count += 1
            except Exception as e:
                print(f" [!] Bỏ qua {base_name} vì lỗi trong quá trình xử lý: {e}")
        else:
            print(f" [-] Bỏ qua {base_name}: Thiếu file TextGrid hoặc MIDI đi kèm.")

    if success_count > 0:
        # Xuất metadata.json (Ghi đè thay vì ghi nối, vì ta đã quét toàn bộ thư mục một lần)
        metadata_path = os.path.join(args.output_dir, 'metadata.json')
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(all_metadata, f, indent=4, ensure_ascii=False)

        # Cấu hình phone_set.json
        phone_set_path = os.path.join(args.output_dir, 'phone_set.json')
        final_phones = list(global_phone_set)
        
        if 'SP' not in final_phones: final_phones.insert(0, 'SP')
        if 'AP' not in final_phones: final_phones.insert(0, 'AP')
        
        with open(phone_set_path, 'w', encoding='utf-8') as f:
            json.dump(final_phones, f, indent=4, ensure_ascii=False)

        print(f"Hoàn tất xử lý thành công {success_count}/{len(wav_files)} file! Dữ liệu đã lưu tại: {os.path.abspath(args.output_dir)}")
    else:
        print("Không có file nào được xử lý thành công. Vui lòng kiểm tra lại dữ liệu thô.")