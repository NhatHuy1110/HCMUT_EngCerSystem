import os
import json
import random
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask,
    request,
    jsonify,
    session,
    send_from_directory,
)
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

from core.pipeline import process_document

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# -------------------- PATH & APP CONFIG --------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
FRONTEND_FOLDER = os.path.join(PROJECT_ROOT, "frontend")

app = Flask(
    __name__,
    static_folder=FRONTEND_FOLDER,
    static_url_path=""
)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-document-ai-secret")

# SQLite (mặc định). Sau sẽ đổi sang MySQL ở phần 2.
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    "sqlite:///" + os.path.join(BASE_DIR, "certificates.db"),
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

db = SQLAlchemy(app)
CORS(app, supports_credentials=True)

# -------------------- EMAIL CONFIG --------------------

# TODO: sửa 2 dòng này thành Gmail & App Password của bạn
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "YOUR_GMAIL@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "YOUR_APP_PASSWORD")


def send_email(to_address: str, subject: str, body: str):
    """
    Gửi email OTP. Nếu bạn chưa setup Gmail/App Password,
    hàm sẽ chỉ in OTP ra console để bạn test.
    """
    if EMAIL_SENDER.startswith("YOUR_") or EMAIL_PASSWORD.startswith("YOUR_"):
        # Dev mode: không gửi thật, chỉ in ra log
        print("---- OTP (dev mode, chưa cấu hình email thật) ----")
        print(f"To: {to_address}")
        print(f"Subject: {subject}")
        print(body)
        print("---------------------------------------------------")
        return

    msg = MIMEMultipart()
    msg["From"] = EMAIL_SENDER
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(EMAIL_SENDER, EMAIL_PASSWORD)
    server.send_message(msg)
    server.quit()

# -------------------- MODELS --------------------


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fullname = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class EmailOTP(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(6), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Certificate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    file_name = db.Column(db.String(255))
    cert_type = db.Column(db.String(50))
    confidence = db.Column(db.Float)
    data_json = db.Column(db.Text)  # lưu FULL JSON entries
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def _payload(self) -> dict:
        try:
            return json.loads(self.data_json or "{}")
        except json.JSONDecodeError:
            return {"entries": {}}

    def to_brief_dict(self):
        payload = self._payload()
        quality = payload.get("quality", {})
        return {
            "id": self.id,
            "file_name": self.file_name,
            "cert_type": self.cert_type,
            "confidence": self.confidence,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "status": payload.get("reviewStatus", "saved"),
            "valid_fields": quality.get("valid_fields", 0),
            "total_fields": quality.get("total_fields", 0),
            "review_fields": quality.get("review_fields", 0),
        }

    def to_full_dict(self):
        return {
            "id": self.id,
            "file_name": self.file_name,
            "cert_type": self.cert_type,
            "confidence": self.confidence,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "payload": self._payload(),
            "data_json": self.data_json,
        }

# -------------------- HELPERS --------------------


def current_user_id():
    return session.get("user_id")


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Unauthorized"}), 401
        return fn(*args, **kwargs)

    return wrapper

# -------------------- AUTH API --------------------


@app.route("/api/register-step1", methods=["POST"])
def register_step1():
    """
    Bước 1: nhận thông tin register + tạo user (verified=False) + tạo OTP + gửi email.
    """
    data = request.get_json()
    fullname = data.get("fullname", "").strip()
    email = data.get("email", "").strip()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    confirm = data.get("confirm", "").strip()

    if not fullname or not email or not username or not password:
        return jsonify({"error": "Vui lòng điền đầy đủ thông tin"}), 400

    if password != confirm:
        return jsonify({"error": "Mật khẩu xác nhận không khớp"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email đã tồn tại"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Tên đăng nhập đã tồn tại"}), 400

    # Tạo user
    user = User(
        fullname=fullname,
        email=email,
        username=username,
        password_hash=generate_password_hash(password),
        verified=False,
    )
    db.session.add(user)

    # Tạo OTP 6 số
    code = str(random.randint(100000, 999999))
    otp = EmailOTP(email=email, code=code)
    db.session.add(otp)

    db.session.commit()

    send_email(email, "Mã xác thực tài khoản", f"Mã OTP của bạn là: {code}")
    response = {"message": "OTP sent"}
    if EMAIL_SENDER.startswith("YOUR_") or EMAIL_PASSWORD.startswith("YOUR_"):
        response["devOtp"] = code
    return jsonify(response)


@app.route("/api/register-verify", methods=["POST"])
def register_verify():
    """
    Bước 2: nhận mã OTP, nếu đúng -> set user.verified = True
    """
    code = request.get_json().get("code", "").strip()
    if not code:
        return jsonify({"error": "Thiếu mã OTP"}), 400

    otp = EmailOTP.query.filter_by(code=code).first()
    if not otp:
        return jsonify({"error": "Mã OTP không đúng"}), 400

    user = User.query.filter_by(email=otp.email).first()
    if not user:
        return jsonify({"error": "Không tìm thấy user tương ứng"}), 400

    user.verified = True
    db.session.commit()

    return jsonify({"message": "Verified"})


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Sai tên đăng nhập hoặc mật khẩu"}), 401

    if not user.verified:
        return jsonify({"error": "Tài khoản chưa xác thực email"}), 403

    session["user_id"] = user.id
    return jsonify({"message": "Login success"})


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})


@app.route("/api/session", methods=["GET"])
def get_session():
    uid = current_user_id()
    if not uid:
        return jsonify({"authenticated": False})
    user = db.session.get(User, uid)
    return jsonify(
        {
            "authenticated": True,
            "user": {
                "id": user.id,
                "fullname": user.fullname,
                "username": user.username,
                "email": user.email,
            },
        }
    )

# -------------------- CERTIFICATE API --------------------


@app.route("/api/process", methods=["POST"])
@login_required
def process_certificate():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    preferred_engine = request.form.get("engine") or request.args.get("engine")

    try:
        result = process_document(file.read(), file.filename, preferred_engine)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(result)


@app.route("/api/confirm", methods=["POST"])
@login_required
def confirm_certificate():
    data = request.get_json() or {}

    file_name = data.get("file_name") or data.get("fileName")
    cert_type = data.get("cert_type") or data.get("certType")
    confidence = data.get("confidence", 0.0)

    if not file_name or not cert_type:
        return jsonify({"error": "Missing file_name/fileName hoặc cert_type/certType"}), 400

    payload = data.get("payload") or data
    payload["reviewStatus"] = data.get("reviewStatus", "confirmed")
    payload["confirmedAt"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    cert = Certificate(
        user_id=current_user_id(),
        file_name=file_name,
        cert_type=cert_type,
        confidence=float(confidence),
        data_json=json.dumps(payload, ensure_ascii=False),
    )
    db.session.add(cert)
    db.session.commit()

    return jsonify({"message": "Saved", "id": cert.id})


@app.route("/api/my-certificates", methods=["GET"])
@login_required
def my_certificates():
    """
    Trả về list certificates đã lưu (brief) cho bảng history.
    """
    uid = current_user_id()
    rows = (
        Certificate.query.filter_by(user_id=uid)
        .order_by(Certificate.created_at.desc())
        .all()
    )
    return jsonify([r.to_brief_dict() for r in rows])


@app.route("/api/get-certificate/<int:cert_id>", methods=["GET"])
@login_required
def get_certificate(cert_id):
    """
    Lấy 1 certificate đầy đủ (dùng cho popup xem chi tiết).
    """
    uid = current_user_id()
    cert = Certificate.query.filter_by(id=cert_id, user_id=uid).first()
    if not cert:
        return jsonify({"error": "Không tìm thấy chứng chỉ"}), 404

    return jsonify(cert.to_full_dict())


@app.route("/api/update-certificate/<int:cert_id>", methods=["PUT"])
@login_required
def update_certificate(cert_id):
    """
    Cập nhật data_json (sau khi user sửa trong popup).
    Body: { <key>: <value>, ... }
    """
    uid = current_user_id()
    cert = Certificate.query.filter_by(id=cert_id, user_id=uid).first()
    if not cert:
        return jsonify({"error": "Không tìm thấy chứng chỉ"}), 404

    payload = request.get_json() or {}
    cert.data_json = json.dumps(payload, ensure_ascii=False)
    cert.cert_type = payload.get("certType", cert.cert_type)
    cert.confidence = float(payload.get("confidence", cert.confidence or 0.0))
    db.session.commit()

    return jsonify({"message": "Đã cập nhật"})


@app.route("/api/delete-certificate/<int:cert_id>", methods=["DELETE"])
@login_required
def delete_certificate(cert_id):
    """
    Xóa 1 certificate (sau khi user xác nhận).
    """
    uid = current_user_id()
    cert = Certificate.query.filter_by(id=cert_id, user_id=uid).first()
    if not cert:
        return jsonify({"error": "Không tìm thấy chứng chỉ"}), 404

    db.session.delete(cert)
    db.session.commit()

    return jsonify({"message": "Đã xóa"})


@app.route("/api/analytics", methods=["GET"])
@login_required
def analytics():
    rows = Certificate.query.filter_by(user_id=current_user_id()).all()
    by_type = {}
    total_review = 0
    total_valid = 0
    total_fields = 0

    for row in rows:
        by_type[row.cert_type] = by_type.get(row.cert_type, 0) + 1
        quality = row._payload().get("quality", {})
        total_review += int(quality.get("review_fields", 0) or 0)
        total_valid += int(quality.get("valid_fields", 0) or 0)
        total_fields += int(quality.get("total_fields", 0) or 0)

    return jsonify(
        {
            "totalCertificates": len(rows),
            "byType": by_type,
            "reviewFields": total_review,
            "validFields": total_valid,
            "totalFields": total_fields,
            "fieldValidityRate": round(total_valid / total_fields, 4) if total_fields else 0,
        }
    )

# -------------------- FRONTEND ROUTES --------------------


@app.route("/")
def auth_page():
    return send_from_directory(app.static_folder, "auth.html")


@app.route("/app")
def app_page():
    return send_from_directory(app.static_folder, "index.html")

# -------------------- MAIN --------------------


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=8000, debug=os.getenv("FLASK_DEBUG", "0") == "1")
