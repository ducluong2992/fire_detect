# ==============================================================================
# VÁ LỖI TƯƠNG THÍCH PATHLIB / POSIXPATH GIỮA LINUX (COLAB) VÀ WINDOWS
# ==============================================================================
import sys
import types
import pathlib

if 'pathlib._local' not in sys.modules:
    try:
        import pathlib._local
    except ModuleNotFoundError:
        fake_mod = types.ModuleType('pathlib._local')
        for attr in dir(pathlib):
            setattr(fake_mod, attr, getattr(pathlib, attr))
        sys.modules['pathlib._local'] = fake_mod

pathlib.PosixPath = pathlib.WindowsPath
if 'pathlib._local' in sys.modules:
    sys.modules['pathlib._local'].PosixPath = pathlib.WindowsPath
# ==============================================================================

import cv2
import torch
import time
import requests
import os
import json
import threading
from datetime import datetime
import tkinter as tk
from tkinter import filedialog

# ==============================================================================
# CẤU HÌNH & QUẢN LÝ MODEL
# ==============================================================================
CONFIG_FILE = "telegram_config.json"

default_token = "9035536125:AAEzvuzuk3nHjYtkj261ci4FiF0HRVR6D-s"
default_chat_id = "5085162901"
selected_model_name = "exp2_best.pt"

if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            default_token = cfg.get("bot_token", default_token)
            default_chat_id = cfg.get("chat_id", default_chat_id)
            selected_model_name = cfg.get("selected_model", selected_model_name)
    except Exception:
        pass

TELEGRAM_BOT_TOKEN = default_token
TELEGRAM_CHAT_ID = default_chat_id

CONF_THRESHOLD = 0.20  # Ngưỡng tin cậy nhận diện lửa tối ưu cho video (0.20)
ALERT_COOLDOWN = 10    # Đúng 10 giây nếu vẫn phát hiện lửa thì gửi thông báo tiếp

def get_models_list():
    """Quét và lấy danh sách các file .pt trong thư mục models"""
    base_dir = "models" if os.path.exists("models") else "fire_app_deployment/models"
    models = []
    if os.path.exists(base_dir):
        for f in os.listdir(base_dir):
            if f.endswith(".pt"):
                models.append((f, os.path.join(base_dir, f)))
    return models

# ==============================================================================
# HÀM GỬI CẢNH BÁO TELEGRAM (CHẠY ĐA LUỒNG KHÔNG GÂY ĐƠ VIDEO)
# ==============================================================================
def _send_tele_worker(image_path, fire_count, timestamp_str, model_name):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    caption = (
        f"🚨 CẢNH BÁO KHẨN CẤP: PHÁT HIỆN ĐÁM CHÁY!\n\n"
        f"📍 Nguồn: Hệ Thống Giám Sát Camera\n"
        f"🧠 Mô hình: {model_name}\n"
        f"🔥 Số vị trí lửa phát hiện: {fire_count}\n"
        f"⏰ Thời gian: {timestamp_str}\n\n"
        f"⚠️ Chú ý: Đám cháy vẫn đang tiếp diễn (Cảnh báo mỗi 10s)!"
    )
    try:
        with open(image_path, "rb") as photo:
            files = {"photo": photo}
            data = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption}
            res = requests.post(url, files=files, data=data, timeout=15)
            if res.status_code == 200:
                print(f"\n[✅ Telegram] Đã gửi ảnh cảnh báo thành công lúc {timestamp_str}!")
            else:
                print(f"\n[❌ Telegram] Gửi thất bại: {res.text}")
    except Exception as e:
        print(f"\n[❌ Telegram] Lỗi kết nối API: {e}")
    finally:
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception:
                pass

def trigger_telegram_alert(frame, fire_count, model_name):
    if TELEGRAM_BOT_TOKEN == "DIEN_BOT_TOKEN_CUA_BAN_VAO_DAY" or not TELEGRAM_BOT_TOKEN:
        print("\n[!] Bạn chưa cấu hình Token và Chat ID. Hãy cấu hình ở mục 4 trong menu!")
        return

    now_str = datetime.now().strftime("%H:%M:%S ngày %d/%m/%Y")
    temp_img_name = f"alert_{int(time.time())}.jpg"
    cv2.imwrite(temp_img_name, frame)

    t = threading.Thread(target=_send_tele_worker, args=(temp_img_name, fire_count, now_str, model_name), daemon=True)
    t.start()

def test_telegram_connection(token, chat_id):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    msg = "🔔 [TEST] Kết nối Hệ thống Phát Hiện Cháy với Telegram thành công!"
    try:
        r = requests.post(url, json={"chat_id": chat_id, "text": msg}, timeout=15)
        return r.status_code == 200, r.json()
    except Exception as e:
        return False, str(e)

# ==============================================================================
# MENU LỰA CHỌN MODEL & NGUỒN VIDEO
# ==============================================================================
def choose_model():
    global selected_model_name
    models = get_models_list()
    print("\n" + "=" * 65)
    print("🧠 DANH SÁCH MÔ HÌNH (MODEL) ĐANG CÓ SẴN ĐỂ TEST:")
    print("=" * 65)
    for idx, (m_file, m_path) in enumerate(models):
        curr_mark = " (ĐANG CHỌN)" if m_file == selected_model_name else ""
        desc = ""
        if "exp1" in m_file:
            desc = " -> Thí nghiệm 1: Baseline (mAP: 70.40%)"
        elif "exp2" in m_file:
            desc = " -> Thí nghiệm 2: Tuning (mAP: 70.80%)"
        elif m_file == "best.pt":
            desc = " -> Mô hình tốt nhất mặc định"
        print(f"  [{idx + 1}] {m_file}{desc}{curr_mark}")

    print(f"  [{len(models) + 1}] Chọn file .pt khác từ máy tính (Browse File)...")
    print(f"  [0] Quay lại menu chính")
    print("-" * 65)

    ans = input(f"👉 Chọn mô hình bạn muốn dùng (0 - {len(models) + 1}): ").strip()
    if ans == "0":
        return

    if ans == str(len(models) + 1):
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        fpath = filedialog.askopenfilename(
            title="Chọn file model weights (.pt)",
            filetypes=[("PyTorch Model", "*.pt"), ("All Files", "*.*")]
        )
        root.destroy()
        if fpath and os.path.exists(fpath):
            selected_model_name = os.path.basename(fpath)
            # Lưu cấu hình
            _save_config()
            print(f"✅ Đã chọn model từ: {fpath}")
        return

    try:
        idx_chosen = int(ans) - 1
        if 0 <= idx_chosen < len(models):
            selected_model_name = models[idx_chosen][0]
            _save_config()
            print(f"✅ Đã chuyển sang sử dụng mô hình: {selected_model_name}")
        else:
            print("[!] Lựa chọn không hợp lệ.")
    except ValueError:
        print("[!] Vui lòng nhập số hợp lệ.")

def _save_config():
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "bot_token": TELEGRAM_BOT_TOKEN,
            "chat_id": TELEGRAM_CHAT_ID,
            "selected_model": selected_model_name
        }, f, indent=2)

def select_options():
    global TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, selected_model_name

    while True:
        # Xác định đường dẫn model đang chọn
        models_dict = dict(get_models_list())
        current_model_path = models_dict.get(selected_model_name, os.path.join("models", selected_model_name))
        if not os.path.exists(current_model_path):
            # Nếu không tìm thấy, lấy file đầu tiên có sẵn
            if models_dict:
                selected_model_name = list(models_dict.keys())[0]
                current_model_path = models_dict[selected_model_name]

        print("\n" + "=" * 65)
        print("🔥 HỆ THỐNG PHÁT HIỆN CHÁY & CẢNH BÁO TELEGRAM (YOLOv5)")
        print("=" * 65)
        print(f"🧠 Model đang dùng : {selected_model_name} (Sẵn sàng test)")
        print(f"📌 Telegram Bot    : {TELEGRAM_BOT_TOKEN[:10]}... (Chat ID: {TELEGRAM_CHAT_ID})")
        print(f"⏱️ Cooldown        : {ALERT_COOLDOWN} giây / lần gửi thông báo")
        print("-" * 65)
        print("Lựa chọn chức năng:")
        print("  [1] Chạy kiểm thử với WEBCAM LAPTOP (Realtime)")
        print("  [2] Chạy kiểm thử với UPLOAD VIDEO (.mp4, .avi, .mov...)")
        print("  [3] THAY ĐỔI MÔ HÌNH MODEL (Đổi giữa exp1_best.pt / exp2_best.pt)")
        print("  [4] Cài đặt / Cập nhật Telegram Bot Token & Chat ID")
        print("  [5] Thoát chương trình")
        print("=" * 65)

        choice = input("👉 Nhập lựa chọn của bạn (1/2/3/4/5): ").strip()

        if choice == "3":
            choose_model()
            continue

        elif choice == "4":
            print("\n--- CÀI ĐẶT TELEGRAM ---")
            new_token = input("Nhập Bot Token (Enter để giữ nguyên): ").strip()
            new_chat_id = input("Nhập Chat ID   (Enter để giữ nguyên): ").strip()
            if new_token:
                TELEGRAM_BOT_TOKEN = new_token
            if new_chat_id:
                TELEGRAM_CHAT_ID = new_chat_id
            _save_config()
            print("Đang kiểm tra kết nối Telegram...")
            ok, res = test_telegram_connection(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
            if ok:
                print("✅ Kết nối Telegram thành công! Bot đã gửi tin nhắn chào mừng.")
            else:
                print(f"⚠️ Kiểm tra thất bại: {res}")
            continue

        elif choice == "1":
            print(f"\n[+] Đang mở Webcam laptop với model: {selected_model_name}...")
            return 0, "Webcam Laptop", current_model_path

        elif choice == "2":
            print("\n[+] Đang mở cửa sổ chọn file video từ máy tính...")
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            file_path = filedialog.askopenfilename(
                title="Chọn file video để test nhận diện cháy",
                filetypes=[("Video Files", "*.mp4 *.avi *.mov *.mkv *.wmv"), ("All Files", "*.*")]
            )
            root.destroy()

            if file_path and os.path.exists(file_path):
                print(f"[+] Đã chọn file video: {file_path}")
                return file_path, f"Video: {os.path.basename(file_path)}", current_model_path
            else:
                fallback_video = "../input.mp4" if os.path.exists("../input.mp4") else "test_samples/test_video.mp4"
                if os.path.exists(fallback_video):
                    print(f"[!] Không chọn file mới, tự động dùng video mẫu: {fallback_video}")
                    return fallback_video, "Video Mẫu Mặc Định", current_model_path
                print("[!] Chưa chọn file video nào!")
                continue

        elif choice == "5":
            exit()
        else:
            print("[!] Lựa chọn không hợp lệ, vui lòng chọn lại!")

# ==============================================================================
# CHƯƠNG TRÌNH CHÍNH
# ==============================================================================
def main():
    video_source, source_label, model_path = select_options()

    print(f"\n[*] Đang nạp mô hình phát hiện cháy từ: {model_path}...")
    try:
        model = torch.hub.load('ultralytics/yolov5', 'custom', path=model_path, force_reload=False)
        model.conf = CONF_THRESHOLD
        print(f"✅ Nạp mô hình [{selected_model_name}] thành công!")
    except Exception as e:
        print(f"❌ Không thể nạp mô hình: {e}")
        return

    cap = cv2.VideoCapture(video_source)
    if not cap.isOpened():
        print(f"❌ Không thể mở nguồn video: {video_source}")
        return

    last_alert_time = 0
    fps_time = time.time()
    frame_count = 0
    fps = 0

    print("\n" + "=" * 65)
    print(f"🚀 HỆ THỐNG ĐANG HOẠT ĐỘNG ({source_label})")
    print(f"🧠 Mô hình sử dụng : {selected_model_name}")
    print(f"👉 Nhấn phím 'q' hoặc phím 'ESC' trên cửa sổ video để THOÁT.")
    print("=" * 65 + "\n")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("\n[!] Đã phát hết video hoặc mất kết nối camera.")
            break

        frame_count += 1
        if time.time() - fps_time >= 1.0:
            fps = frame_count
            frame_count = 0
            fps_time = time.time()

        # Chuyển BGR sang RGB chuẩn của YOLOv5 để tăng độ nhạy nhận diện lửa gấp đôi
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = model(frame_rgb)
        df = results.pandas().xyxy[0]
        fire_count = len(df)

        current_time = time.time()
        elapsed_since_last = current_time - last_alert_time
        # Chuyển kết quả vẽ box từ RGB về lại BGR để hiển thị bằng OpenCV
        annotated_frame = cv2.cvtColor(results.render()[0], cv2.COLOR_RGB2BGR)

        status_text = f"[{selected_model_name}] Trang thai: AN TOAN"
        status_color = (0, 255, 0)

        if fire_count > 0:
            status_text = f"[{selected_model_name}] CANH BAO: {fire_count} DIEM CHAY!"
            status_color = (0, 0, 255)

            if elapsed_since_last >= ALERT_COOLDOWN:
                print(f"\n[🚨 PHÁT HIỆN LỬA] Tìm thấy {fire_count} vị trí cháy (Model: {selected_model_name})! Đang gửi cảnh báo Telegram...")
                trigger_telegram_alert(annotated_frame.copy(), fire_count, selected_model_name)
                last_alert_time = current_time
            else:
                remaining = int(ALERT_COOLDOWN - elapsed_since_last)
                status_text += f" | Gui lai sau: {remaining}s"

        h, w = annotated_frame.shape[:2]
        cv2.rectangle(annotated_frame, (0, 0), (w, 42), (20, 20, 20), -1)
        cv2.putText(annotated_frame, status_text, (15, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, status_color, 2)
        cv2.putText(annotated_frame, f"FPS: {fps}", (w - 110, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        cv2.imshow("He Thong Canh Bao Phat Hien Chay (YOLOv5 + Telegram Alert)", annotated_frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            print("\n[+] Người dùng đã dừng chương trình.")
            break

    cap.release()
    cv2.destroyAllWindows()
    print("[*] Đã đóng chương trình.")

if __name__ == "__main__":
    main()
