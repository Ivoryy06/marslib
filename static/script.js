(() => {
  const PREVIEW_MODE = window.location.protocol === "file:";

  const MOCK_BOOKS = [];

  const MOCK_KARYA = [];

  const CATEGORIES = [
    "Pelajaran","Novel","Komik","Biografi","Sains & Ensiklopedia",
    "Sejarah & Budaya","Sastra & Puisi","Fantasi & Fiksi Ilmiah",
    "Agama & Kerohanian","Hobi & Keterampilan"
  ];

  let activeCategory = "Semua";
  let homeSearchTerm = "";
  let selectedBook = null;
  let books = [];
  let karya = [];

  function fetchJson(url) {
    return fetch(url, { credentials: "same-origin" }).then((response) => {
      if (!response.ok) throw new Error("Gagal memuat data");
      return response.json();
    });
  }

  async function loadLibraryData() {
    if (PREVIEW_MODE) {
      books = MOCK_BOOKS;
      karya = MOCK_KARYA;
      renderCategoryChips();
      renderFeatured();
      renderBookGrid();
      renderKarya();
      populateKelas();
      updatePreview();
      return;
    }

    try {
      const [booksData, karyaData] = await Promise.all([
        fetchJson("/api/books"),
        fetchJson("/api/karya")
      ]);
      books = booksData.books;
      karya = karyaData.karya;
      renderCategoryChips();
      renderFeatured();
      renderBookGrid();
      renderKarya();
      populateKelas();
      updatePreview();
    } catch (error) {
      console.error(error);
      books = MOCK_BOOKS;
      karya = MOCK_KARYA;
      renderCategoryChips();
      renderFeatured();
      renderBookGrid();
      renderKarya();
      populateKelas();
      updatePreview();
    }
  }

  function renderCategoryChips() {
    const row = document.getElementById("cat-row");
    const all = ["Semua", ...CATEGORIES];
    row.innerHTML = all.map(category => `
      <button class="cat-chip ${category === activeCategory ? "active" : ""}" data-cat="${category}">${category}</button>
    `).join("");

    row.querySelectorAll(".cat-chip").forEach(chip => {
      chip.addEventListener("click", () => {
        activeCategory = chip.dataset.cat;
        renderCategoryChips();
        renderBookGrid();
      });
    });
  }

  function filteredBooks() {
    return books
      .filter(book => {
        const matchCat = activeCategory === "Semua" || book.category === activeCategory;
        const matchSearch = !homeSearchTerm ||
          book.title.toLowerCase().includes(homeSearchTerm) ||
          book.author.toLowerCase().includes(homeSearchTerm);
        return matchCat && matchSearch;
      })
      .sort((a, b) => {
        const categoryOrder = CATEGORIES.indexOf(a.category) - CATEGORIES.indexOf(b.category);
        if (categoryOrder !== 0) return categoryOrder;
        return a.title.localeCompare(b.title, "id");
      });
  }

  function renderBookGrid() {
    const grid = document.getElementById("book-grid");
    const empty = document.getElementById("home-empty");
    const list = filteredBooks();

    empty.style.display = list.length === 0 ? "block" : "none";
    grid.innerHTML = list.map(book => {
      const isAvailable = Boolean(book.available);
      const buttonText = isAvailable ? "Pinjam buku ini" : "Sedang dipinjam";
      return `
        <div class="book-card">
          <div class="top-row">
            <span class="call mono">${book.call_number}</span>
            <span class="badge ${isAvailable ? "ada" : "pinjam"}">${isAvailable ? "Tersedia" : "Dipinjam"}</span>
          </div>
          <h4>${book.title}</h4>
          <div class="author">${book.author}</div>
          <div class="cat-tag">${book.category}</div>
          <div class="actions">
            <button class="btn-mini" data-id="${book.id}" ${isAvailable ? "" : "disabled"}>${buttonText}</button>
          </div>
        </div>
      `;
    }).join("");

    grid.querySelectorAll(".btn-mini[data-id]").forEach(button => {
      button.addEventListener("click", () => {
        const book = books.find(item => String(item.id) === String(button.dataset.id));
        if (!book) return;
        selectBookForBorrow(book);
        switchView("pinjam");
      });
    });
  }

  function renderFeatured() {
    const featured = books.find(book => book.available) || books[0];
    if (!featured) return;
    document.getElementById("feature-call").textContent = featured.call_number;
    document.getElementById("feature-title").textContent = featured.title;
    document.getElementById("feature-author").textContent = featured.author;
    document.getElementById("feature-cat").textContent = featured.category;
  }

  function populateKelas() {
    const sel = document.getElementById("p-kelas");
    const levels = ["10","11","12"];
    const letters = "ABCDEFGHI".split("");
    let options = `<option value="">Pilih kelas</option>`;

    levels.forEach(level => {
      letters.forEach(letter => {
        options += `<option value="${level}${letter}">${level}${letter}</option>`;
      });
    });

    sel.innerHTML = options;
  }

  function selectBookForBorrow(book) {
    selectedBook = book;
    const input = document.getElementById("p-buku-search");
    const results = document.getElementById("p-buku-results");
    const selected = document.getElementById("p-buku-selected");

    input.value = "";
    results.style.display = "none";
    results.innerHTML = "";
    selected.style.display = "block";
    selected.innerHTML = `
      <div class="selected-book">
        <span><strong>${book.title}</strong> — ${book.author} <span class="mono" style="opacity:0.6;">(${book.call_number})</span></span>
        <button id="clear-selected-book" type="button">Ganti</button>
      </div>
    `;

    document.getElementById("clear-selected-book").addEventListener("click", () => {
      selectedBook = null;
      selected.style.display = "none";
      selected.innerHTML = "";
      updatePreview();
    });

    updatePreview();
  }

  function updatePreview() {
    document.getElementById("prev-nama").textContent = document.getElementById("p-nama").value || "—";
    document.getElementById("prev-kelas").textContent = document.getElementById("p-kelas").value || "—";
    document.getElementById("prev-absen").textContent = document.getElementById("p-absen").value || "—";
    document.getElementById("prev-buku").textContent = selectedBook ? selectedBook.title : "—";
    document.getElementById("prev-call").textContent = selectedBook ? selectedBook.call_number : "—";

    const lama = parseInt(document.getElementById("p-lama").value, 10);
    document.getElementById("prev-lama").textContent = lama + " hari";

    const today = new Date();
    const due = new Date(today.getTime() + lama * 24 * 60 * 60 * 1000);
    document.getElementById("prev-tanggal").textContent = due.toLocaleDateString("id-ID", {
      day: "numeric",
      month: "long",
      year: "numeric"
    });
  }

  function renderKarya() {
    const grid = document.getElementById("karya-grid");
    grid.innerHTML = karya.map(item => `
      <div class="karya-card">
        <div class="karya-type">${item.type}</div>
        <h4>${item.title}</h4>
        <div class="by">${item.author}</div>
        <p class="teaser">${item.teaser}</p>
        <button class="read-btn" data-id="${item.id}" type="button">Baca selengkapnya</button>
      </div>
    `).join("");

    grid.querySelectorAll(".read-btn").forEach(button => {
      button.addEventListener("click", () => {
        const item = karya.find(k => String(k.id) === String(button.dataset.id));
        if (!item) return;
        openModal(item);
      });
    });
  }

  function openModal(item) {
    document.getElementById("modal-type").textContent = item.type;
    document.getElementById("modal-title").textContent = item.title;
    document.getElementById("modal-by").textContent = item.author;
    document.getElementById("modal-body").textContent = item.body;
    document.getElementById("modal-bg").classList.add("active");
  }

  function switchView(name) {
    document.querySelectorAll(".tab-btn").forEach(button => {
      button.classList.toggle("active", button.dataset.view === name);
    });
    document.querySelectorAll(".view").forEach(panel => {
      panel.classList.remove("active");
    });
    const targetView = document.getElementById("view-" + name);
    if (targetView) targetView.classList.add("active");
  }

  document.querySelectorAll(".tab-btn").forEach(button => {
    button.addEventListener("click", () => switchView(button.dataset.view));
  });

  const logoutButton = document.getElementById("logout-btn");
  if (logoutButton) {
    logoutButton.addEventListener("click", async () => {
      try {
        const response = await fetch("/api/logout", { method: "POST", credentials: "same-origin" });
        const data = await response.json();
        if (data.redirect) window.location.href = data.redirect;
      } catch (error) {
        window.location.reload();
      }
    });
  }

  const homeSearchInput = document.getElementById("home-search");
  if (homeSearchInput) {
    homeSearchInput.addEventListener("input", (event) => {
      homeSearchTerm = event.target.value.trim().toLowerCase();
      renderBookGrid();
    });
  }

  const bukuSearchInput = document.getElementById("p-buku-search");
  const bukuResultsBox = document.getElementById("p-buku-results");

  if (bukuSearchInput && bukuResultsBox) {
    bukuSearchInput.addEventListener("input", () => {
      const term = bukuSearchInput.value.trim().toLowerCase();
      if (!term) {
        bukuResultsBox.style.display = "none";
        bukuResultsBox.innerHTML = "";
        return;
      }

      const matches = books.filter(book => book.available && (book.title.toLowerCase().includes(term) || book.author.toLowerCase().includes(term))).slice(0, 8);
      bukuResultsBox.style.display = "block";
      bukuResultsBox.innerHTML = matches.length
        ? matches.map(book => `<div data-id="${book.id}">${book.title} <span style="opacity:0.6;">— ${book.author}</span></div>`).join("")
        : `<div class="empty">Buku tidak ditemukan atau sedang dipinjam.</div>`;

      bukuResultsBox.querySelectorAll("div[data-id]").forEach(element => {
        element.addEventListener("click", () => {
          const book = books.find(item => String(item.id) === String(element.dataset.id));
          if (book) selectBookForBorrow(book);
        });
      });
    });
  }

  const pLamaInput = document.getElementById("p-lama");
  const pLamaVal = document.getElementById("p-lama-val");
  if (pLamaInput && pLamaVal) {
    pLamaInput.addEventListener("input", () => {
      pLamaVal.textContent = pLamaInput.value + " hari";
      updatePreview();
    });
  }

  ["p-nama", "p-kelas", "p-absen"].forEach(id => {
    const element = document.getElementById(id);
    if (!element) return;
    element.addEventListener("input", updatePreview);
    element.addEventListener("change", updatePreview);
  });

  const pSubmitButton = document.getElementById("p-submit");
  if (pSubmitButton) {
    pSubmitButton.addEventListener("click", async () => {
      const namaInput = document.getElementById("p-nama");
      const kelasInput = document.getElementById("p-kelas");
      const absenInput = document.getElementById("p-absen");
      const pLamaInput = document.getElementById("p-lama");
      const msg = document.getElementById("p-msg");

      if (!namaInput || !kelasInput || !absenInput || !pLamaInput || !msg) return;

      const nama = namaInput.value.trim();
      const kelas = kelasInput.value;
      const absen = absenInput.value;

      if (!nama || !kelas || !absen || !selectedBook) {
        msg.style.color = "var(--maroon-dark)";
        msg.textContent = "Lengkapi nama, kelas, no. absen, dan pilih buku terlebih dahulu.";
        return;
      }

      try {
        const response = await fetch("/api/borrow", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            book_id: selectedBook.id,
            borrower_name: nama,
            class_name: kelas,
            absen,
            loan_days: Number(pLamaInput.value)
          })
        });

        const result = await response.json();
        if (!response.ok) throw new Error(result.message || "Peminjaman gagal");

        msg.style.color = "var(--sage)";
        msg.textContent = result.message;
        await loadLibraryData();
      } catch (error) {
        msg.style.color = "var(--maroon-dark)";
        msg.textContent = error.message;
      }
    });
  }

  const modalCloseButton = document.getElementById("modal-close");
  const modalBg = document.getElementById("modal-bg");

  if (modalCloseButton && modalBg) {
    modalCloseButton.addEventListener("click", () => {
      modalBg.classList.remove("active");
    });

    modalBg.addEventListener("click", (event) => {
      if (event.target === modalBg) {
        modalBg.classList.remove("active");
      }
    });
  }

  loadLibraryData();
})();
