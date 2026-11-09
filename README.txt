# HƯỚNG DẪN CÀI ĐẶT & CHẠY ỨNG DỤNG TRÊN MÁY TÍNH

### 1. Cài đặt các thư viện cần thiết:
pip install torch torchvision opencv-python requests streamlit pillow pandas

### 2. Chạy Hệ Thống Cảnh Báo Cháy Qua TELEGRAM:
1. Mở file `app_telegram_alert.py`.
2. Điền `TELEGRAM_BOT_TOKEN` và `TELEGRAM_CHAT_ID` của bạn (Xem hướng dẫn tạo bot bên dưới).
3. Chạy lệnh:
   python app_telegram_alert.py
-> Khi camera thấy lửa, hệ thống sẽ tự động khoanh vùng đỏ và bắn ngay bức ảnh cảnh báo về điện thoại bạn qua Telegram!

### 3. Cách lấy Token & Chat ID Telegram trong 1 phút:
- Lấy Token: Tìm bot @BotFather trên Telegram -> gửi lệnh /newbot -> đặt tên bot -> copy chuỗi Token.
- Lấy Chat ID: Tìm bot @userinfobot trên Telegram -> bấm Start -> copy dãy số Id của bạn.

### 4. Chạy Giao Diện Web (Streamlit):
streamlit run app_streamlit.py
