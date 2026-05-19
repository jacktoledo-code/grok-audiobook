const $ = (id) => document.getElementById(id);
const COST_PER_MILLION = 4.20;
const MAX_CHARS = 15000;

const els = {
  text: $("speak-text"),
  count: $("speak-count"),
  cost: $("speak-cost"),
  voice: $("voice-select"),
  language: $("language-select"),
  btn: $("btn-speak"),
  status: $("speak-status"),
  result: $("speak-result"),
  player: $("speak-player"),
  download: $("speak-download"),
  error: $("speak-error"),
};

let currentBlobUrl = null;

const fmtUSD = (n) => `$${Number(n ?? 0).toFixed(4)}`;
const estimate = (chars) => (chars / 1_000_000) * COST_PER_MILLION;

function updateMeter() {
  const n = els.text.value.length;
  els.count.textContent = n.toLocaleString();
  els.cost.textContent = fmtUSD(estimate(n));
  els.btn.disabled = n === 0 || n > MAX_CHARS;
}

function showError(msg) {
  els.error.textContent = msg;
  els.error.classList.remove("hidden");
}
function clearError() {
  els.error.textContent = "";
  els.error.classList.add("hidden");
}

els.text.addEventListener("input", updateMeter);
updateMeter();

els.btn.addEventListener("click", async () => {
  const text = els.text.value;
  if (!text.trim()) return;
  clearError();
  els.btn.disabled = true;
  els.status.textContent = "Synthesizing…";

  try {
    const form = new FormData();
    form.append("text", text);
    form.append("voice_id", els.voice.value);
    form.append("language", els.language.value);

    const res = await fetch("/api/speak", { method: "POST", body: form });
    if (!res.ok) {
      const j = await res.json().catch(() => ({}));
      throw new Error(j.detail || `Speak failed (${res.status})`);
    }
    const blob = await res.blob();

    if (currentBlobUrl) URL.revokeObjectURL(currentBlobUrl);
    currentBlobUrl = URL.createObjectURL(blob);

    els.player.src = currentBlobUrl;
    els.download.href = currentBlobUrl;
    els.result.classList.remove("hidden");
    els.status.textContent = `Done · ${fmtUSD(estimate(text.length))}`;
    els.player.play().catch(() => {}); // autoplay may be blocked; silently ignore
  } catch (e) {
    showError(e.message);
    els.status.textContent = "";
  } finally {
    updateMeter(); // re-enable button based on current text length
  }
});
