const loginTab = document.getElementById("login-tab");
const registerTab = document.getElementById("register-tab");

const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const otpForm = document.getElementById("otp-form");

// ---- Tab switching ----
loginTab.onclick = () => {
  loginTab.classList.add("active");
  registerTab.classList.remove("active");
  loginForm.classList.remove("hidden");
  registerForm.classList.add("hidden");
  otpForm.classList.add("hidden");
};

registerTab.onclick = () => {
  registerTab.classList.add("active");
  loginTab.classList.remove("active");
  registerForm.classList.remove("hidden");
  loginForm.classList.add("hidden");
  otpForm.classList.add("hidden");
};

// ---- Register Step 1: send OTP ----
document.getElementById("register-btn").onclick = async () => {
  const payload = {
    fullname: document.getElementById("reg-fullname").value.trim(),
    email: document.getElementById("reg-email").value.trim(),
    username: document.getElementById("reg-username").value.trim(),
    password: document.getElementById("reg-password").value,
    confirm: document.getElementById("reg-confirm").value,
  };

  const res = await fetch("/api/register-step1", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const data = await res.json();
  if (!res.ok) {
    alert(data.error || "Đăng ký thất bại");
    return;
  }

  const devOtpText = data.devOtp ? `\n\nMã OTP dev-mode: ${data.devOtp}` : "";
  alert(`Mã xác thực đã được gửi đến email. Vui lòng kiểm tra và nhập mã.${devOtpText}`);
  registerForm.classList.add("hidden");
  otpForm.classList.remove("hidden");
};

// ---- Register Step 2: verify OTP ----
document.getElementById("verify-btn").onclick = async () => {
  const code = document.getElementById("otp-code").value.trim();

  const res = await fetch("/api/register-verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
  const data = await res.json();

  if (!res.ok) {
    alert(data.error || "Xác thực thất bại");
    return;
  }

  alert("Đăng ký thành công! Vui lòng đăng nhập.");
  otpForm.classList.add("hidden");
  loginForm.classList.remove("hidden");
  loginTab.classList.add("active");
  registerTab.classList.remove("active");
};

// ---- Login ----
document.getElementById("login-btn").onclick = async () => {
  const payload = {
    username: document.getElementById("login-username").value.trim(),
    password: document.getElementById("login-password").value,
  };

  const res = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  body: JSON.stringify(payload),
  });

  const data = await res.json();
  if (!res.ok) {
    alert(data.error || "Đăng nhập thất bại");
    return;
  }

  // Đăng nhập xong chuyển sang web chính
  window.location.href = "/app";
};
