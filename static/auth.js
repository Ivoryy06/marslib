(() => {
  const API_BASE = "";

  function showAuthMessage(message, type = "info") {
    const box = document.getElementById("auth-message");
    if (!box) return;
    box.textContent = message;
    box.className = `auth-message ${type}`;
  }

  function toggleAuthTabs(target) {
    document.querySelectorAll(".auth-tab").forEach(button => {
      button.classList.toggle("active", button.dataset.authTab === target);
    });
    document.querySelectorAll(".auth-form").forEach(form => {
      form.classList.toggle("active", form.id === (target === "login" ? "loginForm" : "registerForm"));
    });
  }

  function toggleGmailExtras() {
    const emailInput = document.getElementById("reg-email");
    const gmailExtra = document.getElementById("gmail-extra");
    if (!emailInput || !gmailExtra) return;
    gmailExtra.style.display = emailInput.value.trim().toLowerCase().endsWith("@gmail.com") ? "block" : "none";
  }

  function makeRequest(url, options = {}) {
    return fetch(url, {
      credentials: "same-origin",
      ...options,
      headers: {
        ...(options.headers || {})
      }
    }).then(async (response) => {
      const contentType = response.headers.get("content-type") || "";
      const payload = contentType.includes("application/json") ? await response.json() : null;
      if (!response.ok) {
        throw new Error(payload?.message || "Terjadi kesalahan");
      }
      return payload;
    });
  }

  document.querySelectorAll(".auth-tab").forEach(button => {
    button.addEventListener("click", () => toggleAuthTabs(button.dataset.authTab));
  });

  document.getElementById("reg-email").addEventListener("input", toggleGmailExtras);

  document.getElementById("registerForm").addEventListener("submit", async (event) => {
    event.preventDefault();

    const form = event.currentTarget;
    const formData = new FormData(form);
    const approvalRequested = document.getElementById("reg-approval-request").checked;
    const file = document.getElementById("reg-id-proof").files[0];

    if (file) formData.append("id_proof", file);
    formData.set("approval_requested", String(approvalRequested));

    try {
      const result = await makeRequest(`${API_BASE}/api/register`, {
        method: "POST",
        body: formData
      });
      showAuthMessage(result.message, "success");
      form.reset();
      document.getElementById("gmail-extra").style.display = "none";
    } catch (error) {
      showAuthMessage(error.message, "error");
    }
  });

  document.getElementById("loginForm").addEventListener("submit", async (event) => {
    event.preventDefault();

    const email = document.getElementById("login-email").value;
    const password = document.getElementById("login-password").value;
    const role = document.getElementById("login-role").value;

    try {
      const result = await makeRequest(`${API_BASE}/api/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"
        },
        body: new URLSearchParams({ email, password, role }).toString()
      });
      showAuthMessage(result.message, "success");
      window.location.href = result.redirect;
    } catch (error) {
      showAuthMessage(error.message, "error");
    }
  });
})();
