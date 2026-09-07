(() => {
  const queueBox = document.getElementById("approval-queue");
  const financeForm = document.getElementById("finance-form");
  const financeMessage = document.getElementById("finance-message");
  const financeIdInput = document.getElementById("finance-id");
  const financeSubmitBtn = document.getElementById("finance-submit-btn");
  const financeCancelBtn = document.getElementById("finance-cancel-btn");
  const selectAllFinanceCheckbox = document.getElementById("select-all-finance");
  const bulkDeleteFinanceBtn = document.getElementById("bulk-delete-finance");
  const logDateFilter = document.getElementById("log-date-filter");
  const logTypeFilter = document.getElementById("log-type-filter");
  const logFinanceFilter = document.getElementById("log-finance-filter");
  const logSortFilter = document.getElementById("log-sort-filter");
  const logClearFiltersBtn = document.getElementById("log-clear-filters");

  function getSelectedFinanceIds() {
    return Array.from(document.querySelectorAll(".finance-select:checked")).map((checkbox) => Number(checkbox.value));
  }

  function sortLogItems() {
    const container = document.getElementById("full-log-list");
    if (!container || !logSortFilter) return;

    const sortValue = logSortFilter.value || "newest";
    const items = Array.from(container.querySelectorAll(".log-item"));

    items.sort((a, b) => {
      const aValue = Date.parse(a.dataset.logTs || a.dataset.logDate || "1970-01-01") || 0;
      const bValue = Date.parse(b.dataset.logTs || b.dataset.logDate || "1970-01-01") || 0;
      return sortValue === "oldest" ? aValue - bValue : bValue - aValue;
    });

    items.forEach((item) => container.appendChild(item));
  }

  function applyLogFilters() {
    const dateValue = logDateFilter ? logDateFilter.value : "";
    const kindValue = logTypeFilter ? logTypeFilter.value : "all";
    const financeValue = logFinanceFilter ? logFinanceFilter.value : "all";
    const items = document.querySelectorAll(".log-item");

    items.forEach((item) => {
      const itemDate = item.dataset.logDate || "";
      const itemKind = item.dataset.logKind || "activity";
      const itemType = item.dataset.logType || "";

      const matchesDate = !dateValue || itemDate === dateValue;
      const matchesKind = kindValue === "all" || itemKind === kindValue;
      const matchesFinance = financeValue === "all" || itemKind !== "finance" || itemType === financeValue;

      item.style.display = matchesDate && matchesKind && matchesFinance ? "flex" : "none";
    });

    sortLogItems();
  }

  function resetFinanceForm() {
    if (!financeForm) return;
    financeForm.reset();
    if (financeIdInput) financeIdInput.value = "";
    if (financeSubmitBtn) financeSubmitBtn.textContent = "Simpan data keuangan";
    if (financeCancelBtn) financeCancelBtn.style.display = "none";
  }

  async function loadQueue() {
    if (!queueBox) return;
    try {
      const response = await fetch("/api/approval-queue", { credentials: "same-origin" });
      const data = await response.json();
      const users = data.users || [];

      if (!users.length) {
        queueBox.innerHTML = '<div class="approval-empty">Tidak ada akun yang menunggu persetujuan.</div>';
        return;
      }

      queueBox.innerHTML = users.map((user) => `
        <div class="approval-item">
          <div>
            <strong>${user.name}</strong><br>
            <span>${user.email}</span><br>
            <small>${user.id_proof_name ? "Identitas terlampir: " + user.id_proof_name : "Permintaan persetujuan via Gmail"}</small>
          </div>
          <div class="approval-actions">
            <button class="approve-btn" data-action="approve" data-user-id="${user.id}">Setujui</button>
            <button class="reject-btn" data-action="reject" data-user-id="${user.id}">Tolak</button>
          </div>
        </div>
      `).join("");

      queueBox.querySelectorAll("button[data-user-id]").forEach((button) => {
        button.addEventListener("click", async () => {
          const userId = button.dataset.userId;
          const action = button.dataset.action;
          const response = await fetch(`/api/approval/${userId}/${action}`, {
            method: "POST",
            credentials: "same-origin"
          });
          const result = await response.json();
          if (response.ok) {
            loadQueue();
          }
        });
      });
    } catch (error) {
      queueBox.innerHTML = '<div class="approval-empty">Gagal memuat daftar persetujuan.</div>';
    }
  }

  [logDateFilter, logTypeFilter, logFinanceFilter, logSortFilter].forEach((filter) => {
    if (filter) {
      filter.addEventListener("change", applyLogFilters);
    }
  });

  if (logClearFiltersBtn) {
    logClearFiltersBtn.addEventListener("click", () => {
      if (logDateFilter) logDateFilter.value = "";
      if (logTypeFilter) logTypeFilter.value = "all";
      if (logFinanceFilter) logFinanceFilter.value = "all";
      if (logSortFilter) logSortFilter.value = "newest";
      applyLogFilters();
    });
  }

  if (financeForm) {
    financeForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const formData = new FormData(financeForm);
      const financeId = financeIdInput ? financeIdInput.value : "";
      const isEdit = Boolean(financeId);
      financeMessage.textContent = "Menyimpan...";

      try {
        const response = await fetch(isEdit ? `/api/admin/finance/${financeId}` : "/api/admin/finance", {
          method: isEdit ? "PUT" : "POST",
          credentials: "same-origin",
          body: formData
        });
        const payload = await response.json();
        financeMessage.textContent = payload.message || "Terjadi kesalahan.";
        if (response.ok) {
          resetFinanceForm();
          setTimeout(() => window.location.reload(), 300);
        }
      } catch (error) {
        financeMessage.textContent = isEdit ? "Gagal mengubah data keuangan." : "Gagal menambahkan data keuangan.";
      }
    });
  }

  document.querySelectorAll(".edit-finance-btn").forEach((button) => {
    button.addEventListener("click", () => {
      const selectedIds = getSelectedFinanceIds();
      if (selectedIds.length > 1) {
        if (financeMessage) financeMessage.textContent = "Pilih satu data saja untuk edit.";
        return;
      }

      const form = document.getElementById("finance-form");
      if (!form) return;
      const id = button.dataset.financeId;
      const type = button.dataset.financeType;
      const label = button.dataset.financeLabel || "";
      const amount = button.dataset.financeAmount || "";
      const notes = button.dataset.financeNotes || "";

      const entryTypeField = document.getElementById("finance-entry-type");
      const labelField = document.getElementById("finance-label");
      const amountField = document.getElementById("finance-amount");
      const notesField = document.getElementById("finance-notes");
      const hiddenId = document.getElementById("finance-id");

      if (entryTypeField) entryTypeField.value = type;
      if (labelField) labelField.value = label;
      if (amountField) amountField.value = amount;
      if (notesField) notesField.value = notes;
      if (hiddenId) hiddenId.value = id;
      if (financeSubmitBtn) financeSubmitBtn.textContent = "Simpan perubahan";
      if (financeCancelBtn) financeCancelBtn.style.display = "inline-block";
      if (financeMessage) financeMessage.textContent = "Mode edit aktif.";
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  });

  if (selectAllFinanceCheckbox) {
    selectAllFinanceCheckbox.addEventListener("change", () => {
      document.querySelectorAll(".finance-select").forEach((checkbox) => {
        checkbox.checked = selectAllFinanceCheckbox.checked;
      });
    });
  }

  document.querySelectorAll(".finance-select").forEach((checkbox) => {
    checkbox.addEventListener("change", () => {
      if (!checkbox.checked && selectAllFinanceCheckbox) {
        selectAllFinanceCheckbox.checked = false;
      }
      if (document.querySelectorAll(".finance-select").length === document.querySelectorAll(".finance-select:checked").length && selectAllFinanceCheckbox) {
        selectAllFinanceCheckbox.checked = true;
      }
    });
  });

  if (bulkDeleteFinanceBtn) {
    bulkDeleteFinanceBtn.addEventListener("click", async () => {
      const ids = getSelectedFinanceIds();
      if (!ids.length) {
        if (financeMessage) financeMessage.textContent = "Pilih minimal satu data keuangan terlebih dahulu.";
        return;
      }

      if (!confirm(`Hapus ${ids.length} data keuangan yang dipilih?`)) return;

      try {
        const response = await fetch("/api/admin/finance/bulk-delete", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ids })
        });
        const payload = await response.json();
        if (response.ok) {
          window.location.reload();
        } else {
          if (financeMessage) financeMessage.textContent = payload.message || "Gagal menghapus data keuangan.";
        }
      } catch (error) {
        if (financeMessage) financeMessage.textContent = "Gagal menghapus data keuangan.";
      }
    });
  }

  if (financeCancelBtn) {
    financeCancelBtn.addEventListener("click", resetFinanceForm);
  }

  document.querySelectorAll(".delete-finance-btn").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.financeId;
      if (!id || !confirm("Hapus data keuangan ini?")) return;

      try {
        const response = await fetch(`/api/admin/finance/${id}`, {
          method: "DELETE",
          credentials: "same-origin"
        });
        const payload = await response.json();
        if (response.ok) {
          window.location.reload();
        } else {
          financeMessage.textContent = payload.message || "Gagal menghapus data keuangan.";
        }
      } catch (error) {
        financeMessage.textContent = "Gagal menghapus data keuangan.";
      }
    });
  });

  document.querySelectorAll(".tab-btn").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((item) => item.classList.toggle("active", item === button));
      document.querySelectorAll(".view").forEach((panel) => {
        panel.classList.toggle("active", panel.id === `view-${button.dataset.view}`);
      });
    });
  });

  const logoutButton = document.getElementById("logout-btn");
  if (logoutButton) {
    logoutButton.addEventListener("click", async () => {
      await fetch("/api/logout", { method: "POST", credentials: "same-origin" });
      window.location.href = "/auth";
    });
  }

  loadQueue();
})();
