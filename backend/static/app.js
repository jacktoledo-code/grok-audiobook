const $ = (id) => document.getElementById(id);
const MAX_FILES_WARN = 10;

const els = {
  dropzone: $("dropzone"),
  fileInput: $("file-input"),
  dzHint: $("dz-hint"),
  voice: $("voice-select"),
  language: $("language-select"),
  stepBatch: $("step-batch"),
  grid: $("book-grid"),
  btnEstimateAll: $("btn-estimate-all"),
  btnStartAll: $("btn-start-all"),
  btnClear: $("btn-clear"),
  totalFiles: $("total-files"),
  totalCost: $("total-cost"),
  totalSpent: $("total-spent"),
  tpl: $("book-card-template"),
};

const state = { books: [] };

// ── helpers ────────────────────────────────────────────────────────────────
const fmtUSD = (n) => `$${Number(n ?? 0).toFixed(4)}`;
const fmtBytes = (n) =>
  n < 1024
    ? `${n} B`
    : n < 1024 * 1024
    ? `${(n / 1024).toFixed(1)} KB`
    : `${(n / 1024 / 1024).toFixed(2)} MB`;
const fmtEta = (s) => {
  if (s == null) return "—";
  if (s < 60) return `${Math.round(s)} s`;
  const m = Math.floor(s / 60);
  const r = Math.round(s % 60);
  return `${m}m ${r}s`;
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const selectedMode = () =>
  document.querySelector('input[name="mode"]:checked').value;
const uid = () =>
  (crypto.randomUUID && crypto.randomUUID()) ||
  `b${Date.now()}-${Math.random().toString(16).slice(2)}`;

// ── drag & drop / file input ───────────────────────────────────────────────
["dragenter", "dragover"].forEach((ev) =>
  els.dropzone.addEventListener(ev, (e) => {
    e.preventDefault();
    els.dropzone.classList.add("drag");
  })
);
["dragleave", "drop"].forEach((ev) =>
  els.dropzone.addEventListener(ev, (e) => {
    e.preventDefault();
    els.dropzone.classList.remove("drag");
  })
);
els.dropzone.addEventListener("drop", (e) => addFiles(e.dataTransfer.files));
els.fileInput.addEventListener("change", (e) => {
  addFiles(e.target.files);
  e.target.value = "";
});

els.btnEstimateAll.addEventListener("click", estimateAll);
els.btnStartAll.addEventListener("click", startAll);
els.btnClear.addEventListener("click", clearAll);

// ── state ops ──────────────────────────────────────────────────────────────
function addFiles(fileList) {
  const toAdd = Array.from(fileList || []).filter((f) => {
    const dup = state.books.some(
      (b) => b.file.name === f.name && b.file.size === f.size
    );
    return !dup;
  });
  if (!toAdd.length) return;
  toAdd.forEach((file) => {
    const book = {
      id: uid(),
      file,
      status: "idle",
      estimate: null,
      jobId: null,
      progress: null,
      error: null,
      cardEl: null,
    };
    state.books.push(book);
    book.cardEl = renderCard(book);
    els.grid.appendChild(book.cardEl);
  });
  if (state.books.length > MAX_FILES_WARN) {
    els.dzHint.textContent = `Heads up: ${state.books.length} files queued. Grok rate limits may kick in.`;
  } else {
    els.dzHint.textContent = "Up to 10 MB per file";
  }
  refreshUI();
}

function clearAll() {
  state.books = [];
  els.grid.innerHTML = "";
  refreshUI();
}

function removeBook(book) {
  state.books = state.books.filter((b) => b !== book);
  book.cardEl?.remove();
  refreshUI();
}

// ── card rendering ─────────────────────────────────────────────────────────
function renderCard(book) {
  const node = els.tpl.content.firstElementChild.cloneNode(true);
  node.dataset.bookId = book.id;
  node.querySelector(".bc-filename").textContent = book.file.name;
  node.querySelector(".bc-filesize").textContent = fmtBytes(book.file.size);
  node.querySelector(".bc-remove").addEventListener("click", () => {
    if (book.status !== "running") removeBook(book);
  });
  return node;
}

function updateCard(book) {
  const el = book.cardEl;
  if (!el) return;
  el.dataset.status = book.status;
  el.querySelector(".bc-pill").textContent = book.status;

  const est = book.estimate;
  el.querySelector(".bc-title").textContent = est?.title || "—";
  el.querySelector(".bc-chapters").textContent = est
    ? String(est.chapters.length)
    : "—";
  el.querySelector(".bc-chars").textContent = est
    ? est.total_chars.toLocaleString()
    : "—";
  el.querySelector(".bc-est").textContent = est
    ? fmtUSD(est.estimated_cost_usd)
    : "—";

  const p = book.progress;
  el.querySelector(".bc-bar").style.width = `${p?.progress_pct ?? 0}%`;
  el.querySelector(".bc-cur").textContent = p?.current_chapter || "—";
  el.querySelector(".bc-done").textContent = p?.chapters_done ?? 0;
  el.querySelector(".bc-total").textContent = p?.chapters_total ?? est?.chapters.length ?? 0;
  el.querySelector(".bc-cost").textContent = fmtUSD(p?.cost_so_far_usd);
  el.querySelector(".bc-eta").textContent = fmtEta(p?.eta_seconds);
  const logEl = el.querySelector(".bc-log");
  if (p?.log) {
    logEl.textContent = p.log.join("\n");
    logEl.scrollTop = logEl.scrollHeight;
  }

  const errEl = el.querySelector(".bc-error");
  if (book.error) {
    errEl.textContent = book.error;
    errEl.classList.remove("hidden");
  } else {
    errEl.classList.add("hidden");
  }

  const dlWrap = el.querySelector(".bc-downloads");
  if (book.status === "done" && book.jobId) {
    dlWrap.classList.remove("hidden");
    el.querySelector(".bc-dl-full").href = `/api/download/${book.jobId}`;
    const chaps = el.querySelector(".bc-dl-chapters");
    if (!chaps.childElementCount) {
      const total = p?.chapters_total ?? est?.chapters.length ?? 0;
      for (let i = 1; i <= total; i++) {
        const li = document.createElement("li");
        const a = document.createElement("a");
        a.href = `/api/download/${book.jobId}/chapter/${i}`;
        a.download = "";
        a.textContent = `Chapter ${i}`;
        li.appendChild(a);
        chaps.appendChild(li);
      }
    }
  } else {
    dlWrap.classList.add("hidden");
  }
}

function refreshUI() {
  const n = state.books.length;
  els.stepBatch.classList.toggle("hidden", n === 0);
  els.totalFiles.textContent = String(n);

  const totalEst = state.books.reduce(
    (s, b) => s + (b.estimate?.estimated_cost_usd ?? 0),
    0
  );
  const totalSpent = state.books.reduce(
    (s, b) => s + (b.progress?.cost_so_far_usd ?? 0),
    0
  );
  els.totalCost.textContent = fmtUSD(totalEst);
  els.totalSpent.textContent = fmtUSD(totalSpent);

  const anyIdle = state.books.some((b) => b.status === "idle");
  const anyReady = state.books.some(
    (b) => b.status === "ready" || b.status === "estimating"
  );
  const anyRunning = state.books.some((b) => b.status === "running");
  els.btnEstimateAll.disabled = !anyIdle || anyRunning;
  els.btnStartAll.disabled = !anyReady || anyRunning;
  els.btnClear.disabled = anyRunning;
}

// ── estimate / start / poll ────────────────────────────────────────────────
async function estimateOne(book) {
  if (book.status !== "idle") return;
  book.status = "estimating";
  updateCard(book);
  refreshUI();
  try {
    const form = new FormData();
    form.append("file", book.file);
    const res = await fetch("/api/estimate", { method: "POST", body: form });
    if (!res.ok) {
      const j = await res.json().catch(() => ({}));
      throw new Error(j.detail || `Estimate failed (${res.status})`);
    }
    book.estimate = await res.json();
    book.status = "ready";
  } catch (e) {
    book.status = "error";
    book.error = e.message;
  }
  updateCard(book);
  refreshUI();
}

async function estimateAll() {
  els.btnEstimateAll.disabled = true;
  await Promise.allSettled(
    state.books.filter((b) => b.status === "idle").map(estimateOne)
  );
  refreshUI();
}

async function startOne(book) {
  if (book.status !== "ready") return;
  book.status = "queued";
  updateCard(book);
  try {
    const form = new FormData();
    form.append("file", book.file);
    form.append("voice_id", els.voice.value);
    form.append("language", els.language.value);
    form.append("mode", selectedMode());
    const res = await fetch("/api/generate", { method: "POST", body: form });
    if (!res.ok) {
      const j = await res.json().catch(() => ({}));
      throw new Error(j.detail || `Start failed (${res.status})`);
    }
    const { job_id } = await res.json();
    book.jobId = job_id;
    book.status = "running";
    updateCard(book);
    await pollLoop(book);
  } catch (e) {
    book.status = "error";
    book.error = e.message;
    updateCard(book);
  }
  refreshUI();
}

async function startAll() {
  els.btnStartAll.disabled = true;
  // Auto-estimate anything still idle so the user can just click Start.
  await Promise.allSettled(
    state.books.filter((b) => b.status === "idle").map(estimateOne)
  );
  await Promise.allSettled(
    state.books.filter((b) => b.status === "ready").map(startOne)
  );
  refreshUI();
}

async function pollLoop(book) {
  while (true) {
    await sleep(1500);
    let s;
    try {
      const res = await fetch(`/api/status/${book.jobId}`);
      if (!res.ok) throw new Error(`Status ${res.status}`);
      s = await res.json();
    } catch (e) {
      book.status = "error";
      book.error = `Lost the job: ${e.message}`;
      updateCard(book);
      return;
    }
    book.progress = s;
    if (s.status === "done") {
      book.status = "done";
      updateCard(book);
      refreshUI();
      return;
    }
    if (s.status === "error") {
      book.status = "error";
      book.error = s.error || "Job failed.";
      updateCard(book);
      refreshUI();
      return;
    }
    updateCard(book);
    refreshUI();
  }
}
