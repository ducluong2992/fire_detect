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

import streamlit as st
import torch
import cv2
import numpy as np
import tempfile
import time
import requests
import os
import json
from datetime import datetime
from PIL import Image

st.set_page_config(page_title="Hệ Thống Phát Hiện Cháy & Cảnh Báo Telegram", page_icon="🔥", layout="wide")

st.markdown("<h2 style='text-align: center; color: #ff4b4b;'>🔥 HỆ THỐNG PHÁT HIỆN CHÁY & CẢNH BÁO TELEGRAM (YOLOv5)</h2>", unsafe_allow_html=True)

# ==============================================================================
# QUẢN LÝ CẤU HÌNH TELEGRAM
# ==============================================================================
CONFIG_FILE = "telegram_config.json"
default_token = "9035536125:AAEzvuzuk3nHjYtkj261ci4FiF0HRVR6D-s"
default_chat_id = "5085162901"
saved_model = "exp2_best.pt"

if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            default_token = cfg.get("bot_token", default_token)
            default_chat_id = cfg.get("chat_id", default_chat_id)
            saved_model = cfg.get("selected_model", saved_model)
    except Exception:
        pass

# Sidebar
st.sidebar.header("⚙️ Cấu hình Telegram Bot")
bot_token = st.sidebar.text_input("Telegram Bot Token:", value=default_token, type="password")
chat_id = st.sidebar.text_input("Telegram Chat ID:", value=default_chat_id)

if st.sidebar.button("💾 Lưu cấu hình & Test kết nối"):
    if bot_token and chat_id:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"bot_token": bot_token, "chat_id": chat_id, "selected_model": saved_model}, f, indent=2)
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            r = requests.post(url, json={"chat_id": chat_id, "text": "🔔 [TEST] Kết nối từ Web App Phát Hiện Cháy thành công!"}, timeout=15)
            if r.status_code == 200:
                st.sidebar.success("✅ Kết nối Telegram thành công! Bot đã gửi tin nhắn.")
            else:
                st.sidebar.error(f"❌ Lỗi: {r.text}")
        except Exception as e:
            st.sidebar.error(f"❌ Lỗi kết nối: {e}")
    else:
        st.sidebar.warning("Vui lòng điền đủ Token và Chat ID!")

# ==============================================================================
# QUẢN LÝ VÀ CHỌN MODEL LINH HOẠT
# ==============================================================================
st.sidebar.markdown("---")
st.sidebar.header("🧠 Chọn Mô Hình (Model) Để Test")

base_dir = "models" if os.path.exists("models") else "fire_app_deployment/models"
available_model_files = []
if os.path.exists(base_dir):
    for f in sorted(os.listdir(base_dir)):
        if f.endswith('.pt'):
            available_model_files.append(f)

if not available_model_files:
    available_model_files = ["best.pt"]

# Tìm index của model đang lưu
default_idx = 0
if saved_model in available_model_files:
    default_idx = available_model_files.index(saved_model)

selected_model_file = st.sidebar.selectbox(
    "Mô hình muốn thử nghiệm:",
    available_model_files,
    index=default_idx,
    help="Chọn exp1_best.pt (Baseline: 70.40%) hoặc exp2_best.pt (Tuning: 70.80%)"
)

# Hiển thị chú thích model
if "exp1" in selected_model_file:
    st.sidebar.info("📌 Exp 1 (Baseline): 30 epochs, img 640, mAP@0.5 = 70.40%")
elif "exp2" in selected_model_file:
    st.sidebar.info("📌 Exp 2 (Tuning): 40 epochs, img 768, mAP@0.5 = 70.80% (Tốt nhất)")
elif selected_model_file == "best.pt":
    st.sidebar.info("📌 best.pt: Mô hình chiến thắng tối ưu mặc định")

model_path = os.path.join(base_dir, selected_model_file)

st.sidebar.markdown("---")
st.sidebar.header("🎛️ Tùy chọn Nhận diện")
conf_thresh = st.sidebar.slider("Ngưỡng tin cậy (Confidence):", 0.05, 1.0, 0.20, 0.05)
cooldown_seconds = st.sidebar.slider("Thời gian Cooldown gửi lại (giây):", 5, 60, 10, 1)

# Hàm gửi ảnh qua Telegram
def send_telegram_alert(image_np, fire_count, model_name):
    if not bot_token or not chat_id:
        return False
    now_str = datetime.now().strftime("%H:%M:%S ngày %d/%m/%Y")
    caption = (
        f"🚨 CẢNH BÁO KHẨN CẤP: PHÁT HIỆN ĐÁM CHÁY!\n\n"
        f"📍 Nguồn: Ứng dụng Web Giám Sát\n"
        f"🧠 Mô hình: {model_name}\n"
        f"🔥 Số vị trí cháy: {fire_count}\n"
        f"⏰ Thời gian: {now_str}\n\n"
        f"⚠️ Chú ý: Đám cháy đang tiếp diễn (Cảnh báo mỗi {cooldown_seconds}s)!"
    )
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    try:
        _, buffer = cv2.imencode(".jpg", image_np)
        files = {"photo": ("alert.jpg", buffer.tobytes(), "image/jpeg")}
        data = {"chat_id": chat_id, "caption": caption}
        res = requests.post(url, files=files, data=data, timeout=15)
        return res.status_code == 200
    except Exception as e:
        print("Lỗi Telegram:", e)
        return False

# Load Model
@st.cache_resource
def load_yolo_model(m_path):
    model = torch.hub.load('ultralytics/yolov5', 'custom', path=m_path, force_reload=False)
    return model

try:
    model = load_yolo_model(model_path)
    model.conf = conf_thresh
except Exception as e:
    st.error(f"Lỗi nạp mô hình: {e}")
    st.stop()

# Hiển thị thanh trạng thái mô hình trên màn hình chính
st.info(f"🎯 Đang hoạt động với mô hình: **{selected_model_file}** | Ngưỡng tin cậy: **{conf_thresh}** | Cooldown: **{cooldown_seconds}s**")

# Chọn chế độ
mode = st.radio("👉 Chọn chế độ kiểm thử:", ("1. Dùng Webcam Laptop (Camera trực tiếp)", "2. Tải lên file Video (MP4, AVI, MOV)"), horizontal=True)

# Chế độ 1: Webcam
if mode == "1. Dùng Webcam Laptop (Camera trực tiếp)":
    st.subheader(f"📹 Giám sát trực tiếp qua Webcam Laptop [Model: {selected_model_file}]")
    run_cam = st.checkbox("Bật Camera", value=False)
    frame_window = st.image([])
    status_box = st.empty()

    if run_cam:
        cap = cv2.VideoCapture(0)
        last_alert_time = 0

        while run_cam and cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                st.error("Không thể kết nối với Webcam laptop!")
                break

            # Chuyển BGR sang RGB chuẩn của YOLOv5 để tăng độ nhạy nhận diện lửa gấp đôi
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = model(frame_rgb)
            df = results.pandas().xyxy[0]
            fire_count = len(df)
            annotated_frame = results.render()[0]

            curr_time = time.time()
            elapsed = curr_time - last_alert_time

            if fire_count > 0:
                if elapsed >= cooldown_seconds:
                    status_box.error(f"🚨 PHÁT HIỆN {fire_count} ĐIỂM CHÁY! [Model: {selected_model_file}] Đang gửi cảnh báo Telegram...")
                    send_telegram_alert(annotated_frame, fire_count, selected_model_file)
                    last_alert_time = curr_time
                else:
                    rem = int(cooldown_seconds - elapsed)
                    status_box.warning(f"🚨 Phát hiện {fire_count} đám cháy! Đang trong thời gian giãn cách (Gửi lại sau: {rem}s)")
            else:
                status_box.success(f"✅ Trạng thái: An toàn (Không phát hiện đám cháy) | Model: {selected_model_file}")

            frame_window.image(annotated_frame, use_container_width=True)
            time.sleep(0.01)

        cap.release()

# Chế độ 2: Upload Video
else:
    st.subheader(f"🎥 Nhận diện trên file Video [Model: {selected_model_file}]")
    uploaded_video = st.file_uploader("Tải lên file video:", type=["mp4", "avi", "mov", "mkv"])

    if uploaded_video is not None:
        tfile = tempfile.NamedTemporaryFile(delete=False)
        tfile.write(uploaded_video.read())
        tfile.close()

        cap = cv2.VideoCapture(tfile.name)
        run_video = st.button("▶️ Bắt đầu phát hiện cháy trên Video")
        video_placeholder = st.image([])
        status_box = st.empty()

        if run_video:
            last_alert_time = 0
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    st.info("Đã xem hết video.")
                    break

                # Chuyển BGR sang RGB chuẩn của YOLOv5 để tăng độ nhạy nhận diện lửa gấp đôi
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = model(frame_rgb)
                df = results.pandas().xyxy[0]
                fire_count = len(df)
                annotated_frame = results.render()[0]

                curr_time = time.time()
                elapsed = curr_time - last_alert_time

                if fire_count > 0:
                    if elapsed >= cooldown_seconds:
                        status_box.error(f"🚨 PHÁT HIỆN {fire_count} ĐIỂM CHÁY! [Model: {selected_model_file}] Đã gửi thông báo Telegram.")
                        send_telegram_alert(annotated_frame, fire_count, selected_model_file)
                        last_alert_time = curr_time
                    else:
                        rem = int(cooldown_seconds - elapsed)
                        status_box.warning(f"🚨 Đám cháy đang diễn ra! (Gửi lại thông báo sau: {rem}s)")
                else:
                    status_box.success(f"✅ Trạng thái: Bình thường | Model: {selected_model_file}")

                video_placeholder.image(annotated_frame, use_container_width=True)
                time.sleep(0.02)

            cap.release()
            try:
                os.remove(tfile.name)
            except Exception:
                pass
