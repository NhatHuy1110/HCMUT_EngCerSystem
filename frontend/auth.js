const loginTab = document.getElementById("login-tab");
const registerTab = document.getElementById("register-tab");

const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const otpForm = document.getElementById("otp-form");

function showLogin() {
  loginTab.classList.add("active");
  registerTab.classList.remove("active");
  loginForm.classList.remove("hidden");
  registerForm.classList.add("hidden");
  otpForm.classList.add("hidden");
}

function showRegister() {
  registerTab.classList.add("active");
  loginTab.classList.remove("active");
  registerForm.classList.remove("hidden");
  loginForm.classList.add("hidden");
  otpForm.classList.add("hidden");
}

async function readJsonResponse(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data;
}

loginTab.onclick = showLogin;
registerTab.onclick = showRegister;

document.getElementById("register-btn").onclick = async () => {
  const payload = {
    fullname: document.getElementById("reg-fullname").value.trim(),
    email: document.getElementById("reg-email").value.trim(),
    username: document.getElementById("reg-username").value.trim(),
    password: document.getElementById("reg-password").value,
    confirm: document.getElementById("reg-confirm").value,
  };

  try {
    const response = await fetch("/api/register-step1", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await readJsonResponse(response);
    const devOtpText = data.devOtp ? `\n\nDev-mode OTP: ${data.devOtp}` : "";
    alert(`A verification code has been sent to your email.${devOtpText}`);
    registerForm.classList.add("hidden");
    otpForm.classList.remove("hidden");
  } catch (error) {
    alert(error.message || "Registration failed");
  }
};

document.getElementById("verify-btn").onclick = async () => {
  const code = document.getElementById("otp-code").value.trim();

  try {
    const response = await fetch("/api/register-verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });
    await readJsonResponse(response);
    alert("Registration completed. Please sign in.");
    showLogin();
  } catch (error) {
    alert(error.message || "Verification failed");
  }
};

document.getElementById("login-btn").onclick = async () => {
  const payload = {
    username: document.getElementById("login-username").value.trim(),
    password: document.getElementById("login-password").value,
  };

  try {
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    await readJsonResponse(response);
    window.location.href = "/app";
  } catch (error) {
    alert(error.message || "Sign in failed");
  }
};
