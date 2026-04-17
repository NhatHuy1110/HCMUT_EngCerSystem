# English Certificate Document AI

Ứng dụng web hỗ trợ OCR, phân loại và trích xuất thông tin từ chứng chỉ tiếng Anh như IELTS, TOEIC, TOEFL và Cambridge. Dự án dùng Flask cho backend, giao diện HTML/CSS/JavaScript thuần cho frontend, SQLite để lưu lịch sử xử lý và pipeline OCR có thể chạy bằng docTR hoặc EasyOCR.

## Tính năng chính

- Đăng ký, xác thực OTP qua email và đăng nhập theo session.
- Upload một hoặc nhiều ảnh/PDF chứng chỉ, hoặc chọn cả folder.
- OCR tài liệu bằng docTR, có tùy chọn fallback sang EasyOCR.
- Phân loại chứng chỉ: IELTS, TOEIC, TOEFL, Cambridge hoặc Unknown.
- Trích xuất các trường quan trọng như tên thí sinh, mã thí sinh, ngày thi, điểm thành phần, tổng điểm, CEFR, số chứng chỉ và đơn vị cấp.
- Review kết quả theo từng field, xem confidence, cảnh báo và bằng chứng OCR.
- Lưu chứng chỉ đã xác nhận, xem lịch sử, chỉnh sửa/xóa bản ghi và xem thống kê tổng quan.

## Công nghệ sử dụng

- Backend: Python, Flask, Flask-SQLAlchemy, Flask-CORS.
- OCR: python-doctr, EasyOCR, OpenCV, Pillow.
- Database: SQLite mặc định, có thể đổi bằng biến môi trường `DATABASE_URL`.
- Frontend: HTML, CSS, JavaScript module.

## Cấu trúc thư mục

```text
EnglishCerProject/
├── backend/
│   ├── core/              # tiền xử lý, phân loại, pipeline tổng
│   ├── extraction/        # schema field và logic trích xuất
│   ├── ocr/               # engine docTR/EasyOCR và model OCR chung
│   ├── validation/        # validate field, quality score, warning
│   ├── requirements.txt
│   └── server.py          # Flask app, auth API, certificate API
├── frontend/
│   ├── auth.html          # trang đăng nhập/đăng ký
│   ├── index.html         # workspace xử lý chứng chỉ
│   ├── main.js
│   └── styles.css
├── .env.example
├── .gitignore
├── README.md
└── run.sh
```

## Cài đặt

Yêu cầu khuyến nghị:

- Python 3.10 hoặc 3.11.
- Máy Windows/Linux/macOS có đủ dung lượng để tải model OCR trong lần chạy đầu.

Tạo môi trường ảo và cài thư viện:

```bash
python -m venv venv
```

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
```

Linux/macOS:

```bash
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
```

Sao chép file cấu hình mẫu:

```bash
cp .env.example .env
```

Trên Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

## Cấu hình môi trường

Các biến có thể cấu hình trong `.env` hoặc export trực tiếp:

```env
SECRET_KEY=change-me
DATABASE_URL=sqlite:///certificates.db
OCR_ENGINE=doctr
EMAIL_SENDER=YOUR_GMAIL@gmail.com
EMAIL_PASSWORD=YOUR_APP_PASSWORD
```

Ghi chú:

- Nếu `EMAIL_SENDER` và `EMAIL_PASSWORD` vẫn là giá trị `YOUR_*`, hệ thống không gửi email thật mà in OTP ra console để test.
- `OCR_ENGINE` có thể là `doctr`, `easyocr` hoặc `auto`.
- SQLite mặc định sẽ tạo file `backend/certificates.db` khi server chạy. File này là dữ liệu runtime và không nên commit lên GitHub.

## Chạy ứng dụng

Từ thư mục gốc dự án:

```bash
python backend/server.py
```

Hoặc trên Linux/macOS:

```bash
./run.sh
```

Mở trình duyệt tại:

- `http://localhost:8000/` để đăng nhập/đăng ký.
- `http://localhost:8000/app` để vào workspace sau khi đăng nhập.

## API chính

- `POST /api/register-step1`: tạo tài khoản và gửi OTP.
- `POST /api/register-verify`: xác thực OTP.
- `POST /api/login`: đăng nhập.
- `POST /api/logout`: đăng xuất.
- `GET /api/session`: kiểm tra session hiện tại.
- `POST /api/process`: OCR, phân loại và trích xuất field từ file upload.
- `POST /api/confirm`: lưu kết quả đã xác nhận.
- `GET /api/my-certificates`: lấy lịch sử chứng chỉ.
- `GET /api/get-certificate/<id>`: lấy chi tiết một chứng chỉ.
- `PUT /api/update-certificate/<id>`: cập nhật dữ liệu đã lưu.
- `DELETE /api/delete-certificate/<id>`: xóa một chứng chỉ.
- `GET /api/analytics`: thống kê dữ liệu đã lưu.

