import { api } from "../../../scripts/api.js";

const STORE_KEY = "vrgdg.minimaxStudio.v1";
const OUTPUT_NODE = "142";
const MODES = {
  text_to_video: {
    label: "Text to video",
    hint: "Describe the whole shot: who, where, the camera move, what is said and heard.",
  },
  image_to_video: {
    label: "Image to video",
    hint: "The video starts on your image. Describe what happens next: motion, camera, dialogue, sound.",
  },
  reference_to_video: {
    label: "Reference to video",
    hint: "Call your images <Picture 1>, <Picture 2>, ... in the prompt. Click a picture's tag to insert it.",
  },
};
const SHAPES = { landscape: "Landscape 16:9", portrait: "Portrait 9:16", square: "Square 1:1" };
// Output sizes; square keeps the landscape pixel count. maxLength and the pass 2 window (seconds per VRAM tier) are
// starting points still being tested, which is what the Custom VRAM option is for.
const SIZES = {
  "2k": { label: "2K · 1920×1080", landscape: [1920, 1088], portrait: [1088, 1920], square: [1440, 1440],
    maxLength: 30, windows: { 32: 8, 16: 6, 12: 5, 8: 3 } },
  "1440p": { label: "1440p · 2560×1440", landscape: [2560, 1440], portrait: [1440, 2560], square: [1920, 1920],
    maxLength: 15, windows: { 32: 5, 16: 4, 12: 2, 8: 1 } },
  "4k": { label: "4K · 3840×2160", landscape: [3840, 2160], portrait: [2160, 3840], square: [2880, 2880],
    maxLength: 8, windows: { 32: 5, 16: 4, 12: 2, 8: 1 } },
};
const VRAM_TIERS = [32, 16, 12, 8];
const CUSTOM_MAX_LENGTH = 30;
const MODEL_LABELS = {
  diffusion_model: ["Video model", "diffusion_models"],
  text_encoder: ["Text encoder", "text_encoders"],
  video_vae: ["Video VAE", "vae"],
  audio_vae: ["Audio VAE", "vae"],
  pass1_lora: ["Pass 1 LoRA", "loras"],
  refiner_lora: ["Pass 2 refiner LoRA", "loras"],
  upscaler: ["Latent upscaler", "latent_upscale_models"],
};
const STAGES = {
  "128": "Loading the text encoder",
  "136": "Reading the prompt",
  "141": "Loading the video model",
  "125": "Pass 1",
  "9502": "Pass 2: refining",
  "300": "Freeing memory",
  "122": "Decoding the video",
  "304": "Preparing the sound",
  "142": "Saving",
};

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function inputImageUrl(name) {
  const slash = name.lastIndexOf("/");
  const subfolder = slash >= 0 ? name.slice(0, slash) : "";
  const filename = slash >= 0 ? name.slice(slash + 1) : name;
  return api.apiURL(`/view?filename=${encodeURIComponent(filename)}&subfolder=${encodeURIComponent(subfolder)}&type=input`);
}

async function uploadImage(file) {
  const body = new FormData();
  body.append("image", file);
  body.append("type", "input");
  const response = await api.fetchApi("/upload/image", { method: "POST", body });
  if (!response.ok) throw new Error(`Upload failed: HTTP ${response.status}`);
  const data = await response.json();
  return data.subfolder ? `${data.subfolder}/${data.name}` : data.name;
}

async function postJson(url, payload) {
  const response = await api.fetchApi(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok || data.error) {
    const error = data.error;
    const details = Object.values(data.node_errors || {})
      .flatMap((node) => (node.errors || []).map((item) => item.details || item.message))
      .filter(Boolean);
    throw new Error([error?.message || error || `HTTP ${response.status}`, ...details].join(" "));
  }
  return data;
}

function addStyles() {
  if (document.getElementById("vmx-styles")) return;
  const style = document.createElement("style");
  style.id = "vmx-styles";
  style.textContent = `
    .vmx-overlay { position: fixed; inset: 0; z-index: 9000; display: flex; align-items: center; justify-content: center;
      background: rgba(8, 9, 12, 0.72); backdrop-filter: blur(6px); font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
    .vmx-card { width: min(980px, 94vw); max-height: 92vh; display: flex; flex-direction: column; overflow: hidden;
      background: #15171c; color: #e8eaf0; border: 1px solid #262a33; border-radius: 16px; box-shadow: 0 24px 80px rgba(0,0,0,.55); }
    .vmx-head { display: flex; align-items: center; gap: 12px; padding: 16px 20px; border-bottom: 1px solid #22262e; }
    .vmx-logo { width: 28px; height: 28px; border-radius: 8px; background: linear-gradient(135deg, #8b5cf6, #38bdf8); }
    .vmx-title { font-size: 16px; font-weight: 650; letter-spacing: .2px; }
    .vmx-sub { font-size: 12px; color: #8a90a0; }
    .vmx-close { margin-left: auto; width: 32px; height: 32px; border: 0; border-radius: 8px; background: transparent; color: #8a90a0; font-size: 20px; cursor: pointer; }
    .vmx-close:hover { background: #22262e; color: #fff; }
    .vmx-body { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 20px; padding: 20px; overflow: auto; }
    @media (max-width: 820px) { .vmx-body { grid-template-columns: 1fr; } }
    .vmx-col { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
    .vmx-label { display: block; font-size: 12px; font-weight: 600; color: #a7adbb; margin-bottom: 6px; text-transform: uppercase; letter-spacing: .6px; }
    .vmx-select, .vmx-input, .vmx-text { width: 100%; box-sizing: border-box; background: #0f1115; color: #e8eaf0; border: 1px solid #2a2f39;
      border-radius: 10px; padding: 10px 12px; font: inherit; font-size: 14px; outline: none; }
    .vmx-select:focus, .vmx-input:focus, .vmx-text:focus { border-color: #7c6cf6; box-shadow: 0 0 0 3px rgba(124,108,246,.18); }
    .vmx-text { min-height: 180px; resize: vertical; line-height: 1.45; }
    .vmx-hint { font-size: 12px; color: #8a90a0; margin-top: 6px; }
    .vmx-row { display: grid; grid-template-columns: 1.3fr 1fr 1fr; gap: 12px; }
    .vmx-row[hidden] { display: none; }
    .vmx-vram { display: grid; grid-template-columns: 1fr 1.6fr; gap: 12px; align-items: end; }
    .vmx-vram .vmx-hint { margin: 0 0 11px; }
    .vmx-length { display: flex; align-items: center; gap: 10px; }
    .vmx-length input { flex: 1; accent-color: #8b5cf6; }
    .vmx-length span { min-width: 34px; text-align: right; font-variant-numeric: tabular-nums; color: #cfd3dc; }
    .vmx-seed { display: flex; gap: 6px; }
    .vmx-dice { flex: none; width: 40px; border: 1px solid #2a2f39; border-radius: 10px; background: #0f1115; color: #8a90a0; cursor: pointer; font-size: 16px; }
    .vmx-dice.on { color: #fff; border-color: #7c6cf6; background: rgba(124,108,246,.18); }
    .vmx-images { display: grid; grid-template-columns: repeat(auto-fill, minmax(104px, 1fr)); gap: 10px; }
    .vmx-images.single { grid-template-columns: 1fr; }
    .vmx-tile { position: relative; aspect-ratio: 1; border-radius: 12px; overflow: hidden; background: #0f1115; border: 1px solid #2a2f39; }
    .vmx-images.single .vmx-tile { aspect-ratio: 16 / 9; }
    .vmx-tile img { width: 100%; height: 100%; object-fit: cover; display: block; }
    .vmx-images.single .vmx-tile img { object-fit: contain; }
    .vmx-tag { position: absolute; left: 6px; bottom: 6px; padding: 3px 7px; border: 0; border-radius: 6px; background: rgba(0,0,0,.7); color: #fff; font-size: 11px; cursor: pointer; }
    .vmx-tag:hover { background: #7c6cf6; }
    .vmx-remove { position: absolute; top: 6px; right: 6px; width: 22px; height: 22px; border: 0; border-radius: 50%; background: rgba(0,0,0,.7); color: #fff; cursor: pointer; line-height: 22px; padding: 0; }
    .vmx-add { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; aspect-ratio: 1; border-radius: 12px;
      border: 1.5px dashed #343a46; color: #8a90a0; font-size: 12px; cursor: pointer; text-align: center; padding: 8px; }
    .vmx-images.single .vmx-add { aspect-ratio: 16 / 9; }
    .vmx-add:hover, .vmx-add.drag { border-color: #7c6cf6; color: #e8eaf0; background: rgba(124,108,246,.08); }
    .vmx-add b { font-size: 22px; font-weight: 400; }
    .vmx-card.wide { width: min(1360px, 97vw); }
    .vmx-body.adv { grid-template-columns: minmax(0, 1fr) 340px 360px; }
    @media (max-width: 1180px) { .vmx-body.adv { grid-template-columns: 1fr 1fr; } }
    @media (max-width: 820px) { .vmx-body.adv { grid-template-columns: 1fr; } }
    .vmx-adv-toggle { margin-left: auto; border: 1px solid #2a2f39; border-radius: 9px; background: transparent; color: #a7adbb; font: inherit; font-size: 13px; padding: 7px 12px; cursor: pointer; }
    .vmx-adv-toggle:hover, .vmx-adv-toggle.on { color: #fff; border-color: #7c6cf6; background: rgba(124,108,246,.14); }
    .vmx-adv-toggle + .vmx-close { margin-left: 0; }
    .vmx-adv { background: #0f1115; border: 1px solid #22262e; border-radius: 14px; padding: 14px; gap: 10px; align-self: start; }
    .vmx-adv[hidden] { display: none; }
    .vmx-adv-summary { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: #a7adbb; background: #15171c; border: 1px solid #262a33; border-radius: 10px; padding: 10px 12px; }
    .vmx-adv-summary b { color: #e8eaf0; font-weight: 600; margin-right: 4px; }
    .vmx-adv-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .vmx-adv-grid .vmx-label { text-transform: none; letter-spacing: 0; font-weight: 500; font-size: 12px; }
    .vmx-adv-grid .vmx-select, .vmx-adv-grid .vmx-input { padding: 7px 9px; font-size: 13px; }
    .vmx-adv-grid .changed .vmx-label { color: #c4b5fd; }
    .vmx-adv-grid .changed .vmx-label::after { content: " •"; }
    .vmx-tagline { color: #6f7686; font-size: 11px; }
    .vmx-switch { display: flex; align-items: center; gap: 8px; height: 34px; font-size: 13px; color: #cfd3dc; cursor: pointer; }
    .vmx-switch input { accent-color: #8b5cf6; width: 16px; height: 16px; }
    .vmx-reset { margin: 6px 0 0; align-self: flex-start; }
    .vmx-go { border: 0; border-radius: 12px; padding: 14px; font: inherit; font-size: 15px; font-weight: 650; color: #fff; cursor: pointer;
      background: linear-gradient(135deg, #7c5cf6, #3aa8f0); }
    .vmx-go:disabled { opacity: .45; cursor: default; }
    .vmx-stop { border: 1px solid #3a2a2f; border-radius: 12px; padding: 10px; font: inherit; color: #f3a5ad; background: transparent; cursor: pointer; }
    .vmx-preview { display: flex; flex-direction: column; gap: 12px; background: #0f1115; border: 1px solid #22262e; border-radius: 14px; padding: 14px; min-height: 260px; }
    .vmx-screen { flex: 1; display: flex; align-items: center; justify-content: center; border-radius: 10px; background: #0a0b0e; min-height: 200px; overflow: hidden;
      color: #5f6574; font-size: 13px; text-align: center; padding: 12px; }
    .vmx-screen video { width: 100%; max-height: 60vh; border-radius: 8px; background: #000; }
    .vmx-bar { height: 6px; border-radius: 3px; background: #22262e; overflow: hidden; }
    .vmx-bar i { display: block; height: 100%; width: 0; background: linear-gradient(90deg, #7c5cf6, #38bdf8); transition: width .3s; }
    .vmx-status { font-size: 13px; color: #a7adbb; min-height: 18px; }
    .vmx-status.error { color: #f3a5ad; white-space: pre-wrap; }
    .vmx-file { font-size: 12px; color: #8a90a0; word-break: break-all; }
    .vmx-file a { color: #9ec9ff; }
    .vmx-setup { background: #0f1115; border: 1px solid #22262e; border-radius: 14px; padding: 14px; display: flex; flex-direction: column; gap: 10px; }
    .vmx-setup-head { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 650; }
    .vmx-chip { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 999px; background: #1d2a22; color: #7ddc9b; }
    .vmx-chip.bad { background: #2e1d21; color: #f3a5ad; }
    .vmx-recheck { margin-left: auto; border: 1px solid #2a2f39; border-radius: 8px; background: transparent; color: #a7adbb; font: inherit; font-size: 12px; padding: 4px 9px; cursor: pointer; }
    .vmx-recheck:hover { color: #fff; border-color: #7c6cf6; }
    .vmx-group { font-size: 11px; text-transform: uppercase; letter-spacing: .6px; color: #6f7686; margin-top: 4px; }
    .vmx-req { display: grid; grid-template-columns: 10px minmax(0, 1fr) auto; gap: 8px; align-items: start; font-size: 12.5px; }
    .vmx-dot { width: 8px; height: 8px; border-radius: 50%; margin-top: 5px; background: #4ade80; }
    .vmx-req.missing .vmx-dot { background: #f87171; }
    .vmx-req-name { color: #e8eaf0; }
    .vmx-req-sub { color: #7d8494; font-size: 11.5px; word-break: break-all; }
    .vmx-req-note { color: #f3c58a; font-size: 11.5px; }
    .vmx-req a, .vmx-opt a { color: #9ec9ff; text-decoration: none; white-space: nowrap; font-size: 12px; }
    .vmx-req a:hover, .vmx-opt a:hover { text-decoration: underline; }
    .vmx-opts { margin: 4px 0 2px; display: flex; flex-direction: column; gap: 3px; }
    .vmx-opts summary { cursor: pointer; color: #7d8494; font-size: 11.5px; }
    .vmx-opt { display: flex; gap: 6px; align-items: baseline; font-size: 11.5px; color: #a7adbb; }
    .vmx-opt span { flex: 1; }
    .vmx-opt.have span::after { content: " ✓"; color: #4ade80; }
  `;
  document.head.appendChild(style);
}

function loadState() {
  const saved = (() => {
    try { return JSON.parse(localStorage.getItem(STORE_KEY) || "{}"); } catch { return {}; }
  })();
  return {
    mode: MODES[saved.mode] ? saved.mode : "image_to_video",
    prompt: saved.prompt || "",
    images: { image_to_video: [], reference_to_video: [], ...(saved.images || {}) },
    duration: saved.duration || 10,
    size: SIZES[saved.size] ? saved.size : "2k",
    shape: SHAPES[saved.shape] ? saved.shape : "landscape",
    vram: VRAM_TIERS.includes(saved.vram) || saved.vram === "custom" ? saved.vram : null,
    advanced: saved.advanced || {},
    advancedOpen: false,
    seed: saved.seed ?? 1,
    randomSeed: saved.randomSeed ?? true,
    models: saved.models || {},
  };
}

class MiniMaxStudio {
  constructor() {
    this.state = loadState();
    this.options = null;
    this.promptId = null;
    this.overlay = null;
    this.onKey = (event) => { if (event.key === "Escape") this.close(); };
    api.addEventListener("progress", ({ detail }) => this.onProgress(detail));
    api.addEventListener("executing", ({ detail }) => this.onExecuting(detail));
    api.addEventListener("execution_error", ({ detail }) => this.onError(detail));
    api.addEventListener("executed", ({ detail }) => this.onExecuted(detail));
    api.addEventListener("execution_success", ({ detail }) => { if (detail?.prompt_id === this.promptId) this.setRunning(false); });
    api.addEventListener("execution_interrupted", ({ detail }) => {
      if (detail?.prompt_id !== this.promptId) return;
      this.setRunning(false);
      this.setStatus("Stopped.");
    });
  }

  save() {
    localStorage.setItem(STORE_KEY, JSON.stringify(this.state));
  }

  async open() {
    addStyles();
    if (!this.overlay) this.build();
    document.body.appendChild(this.overlay);
    document.addEventListener("keydown", this.onKey);
    this.detectVram();
    if (!this.options) await this.loadOptions();
  }

  async loadOptions() {
    try {
      const response = await api.fetchApi("/vrgdg/minimax_studio/options");
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      this.options = await response.json();
      this.renderModels();
      this.renderTiming();
    } catch (error) {
      this.$("[data-setup]").innerHTML = `<div class="vmx-status error">Could not check the setup: ${esc(error.message || error)}</div>`;
    }
  }

  close() {
    this.overlay?.remove();
    document.removeEventListener("keydown", this.onKey);
  }

  $(selector) {
    return this.overlay.querySelector(selector);
  }

  build() {
    const s = this.state;
    this.overlay = document.createElement("div");
    this.overlay.className = "vmx-overlay";
    this.overlay.innerHTML = `
      <div class="vmx-card" role="dialog" aria-label="VRGDG MiniMax">
        <div class="vmx-head">
          <div class="vmx-logo"></div>
          <div><div class="vmx-title">VRGDG MiniMax</div><div class="vmx-sub">MiniMax H3 · two-pass · one video</div></div>
          <button class="vmx-adv-toggle" data-action="advanced">⚙ Advanced settings</button>
          <button class="vmx-close" data-action="close" title="Close (Esc)">×</button>
        </div>
        <div class="vmx-body">
          <div class="vmx-col">
            <div>
              <label class="vmx-label">Mode</label>
              <select class="vmx-select" data-bind="mode">
                ${Object.entries(MODES).map(([key, mode]) => `<option value="${key}" ${key === s.mode ? "selected" : ""}>${mode.label}</option>`).join("")}
              </select>
            </div>
            <div data-section="images">
              <label class="vmx-label" data-images-label></label>
              <div class="vmx-images" data-images></div>
              <input type="file" accept="image/*" data-file hidden>
            </div>
            <div>
              <label class="vmx-label">Prompt</label>
              <textarea class="vmx-text" data-bind="prompt" placeholder="Describe your video...">${esc(s.prompt)}</textarea>
              <div class="vmx-hint" data-hint></div>
            </div>
            <div class="vmx-row">
              <div>
                <label class="vmx-label">Size</label>
                <select class="vmx-select" data-bind="size">
                  ${Object.entries(SIZES).map(([key, size]) => `<option value="${key}" ${key === s.size ? "selected" : ""}>${size.label}</option>`).join("")}
                </select>
              </div>
              <div>
                <label class="vmx-label">Shape</label>
                <select class="vmx-select" data-bind="shape">
                  ${Object.entries(SHAPES).map(([key, label]) => `<option value="${key}" ${key === s.shape ? "selected" : ""}>${label}</option>`).join("")}
                </select>
              </div>
              <div>
                <label class="vmx-label">Seed</label>
                <div class="vmx-seed">
                  <input class="vmx-input" type="number" min="0" step="1" data-bind="seed" value="${s.seed}">
                  <button class="vmx-dice ${s.randomSeed ? "on" : ""}" data-action="random" title="New random seed for every video">🎲</button>
                </div>
              </div>
            </div>
            <div>
              <label class="vmx-label">Length</label>
              <div class="vmx-length"><input type="range" min="5" step="1" data-bind="duration"><span data-duration></span></div>
            </div>
            <div class="vmx-vram">
              <div>
                <label class="vmx-label">GPU memory</label>
                <select class="vmx-select" data-bind="vram">
                  ${VRAM_TIERS.map((gb) => `<option value="${gb}">${gb} GB</option>`).join("")}
                  <option value="custom">Custom (advanced)</option>
                </select>
              </div>
              <div class="vmx-hint" data-window></div>
            </div>
          </div>
          <div class="vmx-col">
            <div class="vmx-preview">
              <div class="vmx-screen" data-screen>Your video shows up here.</div>
              <div class="vmx-bar"><i data-bar></i></div>
              <div class="vmx-status" data-status>Ready.</div>
              <div class="vmx-file" data-file-link></div>
            </div>
            <button class="vmx-go" data-action="generate">Generate video</button>
            <button class="vmx-stop" data-action="stop" hidden>Stop</button>
            <div class="vmx-setup">
              <div class="vmx-setup-head">
                <span>Setup check</span><span class="vmx-chip" data-setup-summary></span>
                <button class="vmx-recheck" data-action="recheck" title="Look for new custom nodes and model files">Check again</button>
              </div>
              <div data-setup><div class="vmx-hint">Checking...</div></div>
            </div>
          </div>
          <div class="vmx-col vmx-adv" data-adv hidden>
            <div class="vmx-adv-summary" data-adv-summary></div>
            <div class="vmx-group">Models</div>
            <div class="vmx-adv-grid" data-models><div class="vmx-hint">Reading model folders...</div></div>
            <div data-adv-groups></div>
            <button class="vmx-recheck vmx-reset" data-action="reset">Reset advanced settings to defaults</button>
          </div>
        </div>
      </div>`;

    this.overlay.addEventListener("mousedown", (event) => { if (event.target === this.overlay) this.close(); });
    this.$('[data-action="close"]').addEventListener("click", () => this.close());
    this.$('[data-action="generate"]').addEventListener("click", () => this.generate());
    this.$('[data-action="stop"]').addEventListener("click", () => api.interrupt());
    this.$('[data-action="recheck"]').addEventListener("click", () => {
      this.$("[data-setup]").innerHTML = `<div class="vmx-hint">Checking...</div>`;
      this.loadOptions();
    });
    this.$('[data-action="random"]').addEventListener("click", (event) => {
      s.randomSeed = !s.randomSeed;
      event.currentTarget.classList.toggle("on", s.randomSeed);
      this.save();
      if (this.options) this.renderSummary();
    });
    this.$('[data-bind="mode"]').addEventListener("change", (event) => {
      s.mode = event.target.value;
      this.save();
      this.renderMode();
      this.renderModels();
      this.renderAdvanced();
    });
    this.$('[data-bind="prompt"]').addEventListener("input", (event) => { s.prompt = event.target.value; this.save(); });
    this.$('[data-bind="duration"]').addEventListener("input", (event) => {
      s.duration = Number(event.target.value);
      this.$("[data-duration]").textContent = `${s.duration} s`;
      this.save();
      if (this.options) this.renderSummary();
    });
    this.$('[data-bind="size"]').addEventListener("change", (event) => { s.size = event.target.value; this.save(); this.renderTiming(); });
    this.$('[data-bind="shape"]').addEventListener("change", (event) => { s.shape = event.target.value; this.save(); if (this.options) this.renderSummary(); });
    this.$('[data-bind="vram"]').addEventListener("change", (event) => {
      s.vram = event.target.value === "custom" ? "custom" : Number(event.target.value);
      if (s.vram === "custom") this.toggleAdvanced(true);
      this.renderTiming();
    });
    this.$('[data-action="advanced"]').addEventListener("click", () => this.toggleAdvanced(!s.advancedOpen));
    this.$('[data-action="reset"]').addEventListener("click", () => {
      s.advanced = {};
      s.models[s.mode] = {};
      if (s.vram === "custom") s.vram = null;
      this.renderModels();
      this.renderTiming();
      this.detectVram();
    });
    this.$('[data-bind="seed"]').addEventListener("change", (event) => {
      s.seed = Math.max(0, Math.floor(Number(event.target.value) || 0));
      this.save();
      if (this.options) this.renderSummary();
    });
    this.$("[data-file]").addEventListener("change", (event) => {
      this.addFiles([...event.target.files]);
      event.target.value = "";
    });
    this.renderMode();
    this.renderTiming();
  }

  toggleAdvanced(open) {
    this.state.advancedOpen = open;
    this.$("[data-adv]").hidden = !open;
    this.$(".vmx-card").classList.toggle("wide", open);
    this.$(".vmx-body").classList.toggle("adv", open);
    this.$('[data-action="advanced"]').classList.toggle("on", open);
  }

  fields() {
    return (this.options?.advanced || []).flatMap((group) => group.fields);
  }

  // The value a setting will run with: the VRAM preset's window, else the user's change, else the workflow's value.
  effective(key) {
    const s = this.state;
    if (key === "chunk_seconds" && s.vram !== "custom") return SIZES[s.size].windows[s.vram || 8];
    if (key in s.advanced) return s.advanced[key];
    const field = this.fields().find((item) => item.key === key);
    return field?.defaults[s.mode] ?? null;
  }

  renderTiming() {
    const s = this.state;
    const custom = s.vram === "custom";
    const max = custom ? CUSTOM_MAX_LENGTH : SIZES[s.size].maxLength;
    s.duration = Math.min(Math.max(5, s.duration), max);
    const slider = this.$('[data-bind="duration"]');
    slider.max = max;
    slider.value = s.duration;
    this.$("[data-duration]").textContent = `${s.duration} s`;
    this.$('[data-bind="vram"]').value = String(s.vram || 8);
    const seconds = this.effective("chunk_seconds");
    this.$("[data-window]").textContent = custom
      ? `Custom: ${seconds ?? "?"} s pass 2 windows (Advanced settings), length up to ${max} s.`
      : `Pass 2 refines in ${seconds} s windows. Up to ${max} s at ${SIZES[s.size].label.split(" ·")[0]}.`;
    this.save();
    this.renderAdvanced();
  }

  renderAdvanced() {
    if (!this.options?.advanced) return;
    const s = this.state;
    const groups = this.options.advanced.map((group) => {
      const rows = group.fields.filter((field) => field.defaults[s.mode] !== null).map((field) => {
        const value = this.effective(field.key);
        const changed = field.key in s.advanced || (field.key === "chunk_seconds" && s.vram === "custom");
        const preset = field.key === "chunk_seconds" && s.vram !== "custom" ? `<span class="vmx-tagline">from ${s.vram || 8} GB preset</span>` : "";
        let input;
        if (field.kind === "combo") {
          input = `<select class="vmx-select" data-adv-key="${field.key}">${field.options.map((option) =>
            `<option value="${esc(option)}" ${option === value ? "selected" : ""}>${esc(option)}</option>`).join("")}</select>`;
        } else if (field.kind === "BOOLEAN") {
          input = `<label class="vmx-switch"><input type="checkbox" data-adv-key="${field.key}" ${value ? "checked" : ""}><span>${value ? "On" : "Off"}</span></label>`;
        } else if (field.kind === "STRING") {
          input = `<input class="vmx-input" type="text" data-adv-key="${field.key}" value="${esc(value)}">`;
        } else {
          const limits = ["min", "max"].filter((name) => Math.abs(field[name] ?? Infinity) < 1e12).map((name) => `${name}="${field[name]}"`).join(" ");
          input = `<input class="vmx-input" type="number" ${limits} step="${field.kind === "INT" ? 1 : "any"}" data-adv-key="${field.key}" value="${esc(value)}">`;
        }
        return `<div class="${changed ? "changed" : ""}"><label class="vmx-label">${esc(field.label)} ${preset}</label>${input}</div>`;
      }).join("");
      return rows ? `<div class="vmx-group">${esc(group.title)}</div><div class="vmx-adv-grid">${rows}</div>` : "";
    }).join("");
    const box = this.$("[data-adv-groups]");
    box.innerHTML = groups;
    box.querySelectorAll("[data-adv-key]").forEach((input) => input.addEventListener("change", () => {
      const field = this.fields().find((item) => item.key === input.dataset.advKey);
      const value = field.kind === "BOOLEAN" ? input.checked : ["combo", "STRING"].includes(field.kind) ? input.value : Number(input.value);
      s.advanced[field.key] = value;
      if (field.key === "chunk_seconds") s.vram = "custom";
      this.renderTiming();
    }));
    this.renderSummary();
  }

  // What both passes will actually run, worked out the way the workflow does it.
  renderSummary() {
    const s = this.state;
    const [width, height] = SIZES[s.size][s.shape];
    const scale = Number(this.effective("upscale_scale")) || 2;
    const align = (value) => Math.max(32, Math.ceil(value / scale / 32) * 32);
    const pass1 = [align(width), align(height)];
    const pass2 = pass1.map((side) => Math.round((side / 16) * scale) * 16);
    const raw = Math.max(5, Math.round(s.duration * 24));
    const frames = raw + ((5 - (raw % 17)) % 17 + 17) % 17;
    const v = (key) => this.effective(key);
    this.$("[data-adv-summary]").innerHTML = `
      <div><b>Pass 1</b> ${pass1[0]}×${pass1[1]} · ${v("pass1_steps")} steps · ${esc(v("pass1_sampler"))} / ${esc(v("pass1_scheduler"))} · denoise ${v("pass1_denoise")}</div>
      <div><b>Pass 2</b> ×${scale} → ${pass2[0]}×${pass2[1]} · ${v("pass2_steps")} steps · ${esc(v("pass2_sampler"))} / ${esc(v("pass2_scheduler"))} · denoise ${v("pass2_denoise")}</div>
      <div><b>Windows</b> ${v("chunk_seconds")} s, ${v("overlap_seconds")} s overlap (${esc(v("overlap_mode"))}), ${v("tail_trim_seconds")} s tail trim</div>
      <div><b>Length</b> ${frames} frames at 24 fps (${(frames / 24).toFixed(2)} s) · seed ${s.randomSeed ? "random" : s.seed}</div>`;
  }

  async detectVram() {
    if (this.state.vram) return;
    try {
      const response = await api.fetchApi("/system_stats");
      const stats = await response.json();
      const gb = (stats.devices?.[0]?.vram_total || 0) / 2 ** 30;
      this.state.vram = VRAM_TIERS.find((tier) => gb >= tier - 2) || 8;
    } catch {
      this.state.vram = 8;
    }
    this.renderTiming();
  }

  renderMode() {
    const mode = this.state.mode;
    this.$("[data-hint]").textContent = MODES[mode].hint;
    this.$('[data-section="images"]').hidden = mode === "text_to_video";
    this.$("[data-images-label]").textContent = mode === "image_to_video" ? "Start image" : "Reference images";
    this.$("[data-file]").multiple = mode === "reference_to_video";
    this.renderImages();
  }

  maxImages() {
    return this.state.mode === "image_to_video" ? 1 : (this.options?.max_reference_images || 9);
  }

  renderImages() {
    const mode = this.state.mode;
    if (mode === "text_to_video") return;
    const images = this.state.images[mode];
    const grid = this.$("[data-images]");
    grid.classList.toggle("single", mode === "image_to_video");
    grid.innerHTML = images.map((name, index) => `
      <div class="vmx-tile" title="${esc(name)}">
        <img src="${esc(inputImageUrl(name))}" alt="">
        ${mode === "reference_to_video" ? `<button class="vmx-tag" data-tag="${index + 1}" title="Insert into the prompt">&lt;Picture ${index + 1}&gt;</button>` : ""}
        <button class="vmx-remove" data-remove="${index}" title="Remove">×</button>
      </div>`).join("");
    if (images.length < this.maxImages()) {
      const add = document.createElement("div");
      add.className = "vmx-add";
      add.innerHTML = `<b>+</b>${mode === "image_to_video" ? "Drop or click to load the start image" : `Add image (${images.length}/${this.maxImages()})`}`;
      add.addEventListener("click", () => this.$("[data-file]").click());
      add.addEventListener("dragover", (event) => { event.preventDefault(); add.classList.add("drag"); });
      add.addEventListener("dragleave", () => add.classList.remove("drag"));
      add.addEventListener("drop", (event) => {
        event.preventDefault();
        add.classList.remove("drag");
        this.addFiles([...event.dataTransfer.files].filter((file) => file.type.startsWith("image/")));
      });
      grid.appendChild(add);
    }
    grid.querySelectorAll("[data-remove]").forEach((button) => button.addEventListener("click", () => {
      images.splice(Number(button.dataset.remove), 1);
      this.save();
      this.renderImages();
    }));
    grid.querySelectorAll("[data-tag]").forEach((button) => button.addEventListener("click", () => this.insertTag(`<Picture ${button.dataset.tag}>`)));
  }

  insertTag(tag) {
    const box = this.$('[data-bind="prompt"]');
    const start = box.selectionStart ?? box.value.length;
    box.setRangeText(tag, start, box.selectionEnd ?? start, "end");
    box.focus();
    this.state.prompt = box.value;
    this.save();
  }

  async addFiles(files) {
    const images = this.state.images[this.state.mode];
    const room = this.maxImages() - images.length;
    if (!files.length || room <= 0) return;
    this.setStatus("Uploading...");
    try {
      for (const file of files.slice(0, room)) images.push(await uploadImage(file));
      this.setStatus(files.length > room ? `Only ${this.maxImages()} images fit; the rest were skipped.` : "Ready.");
    } catch (error) {
      this.setStatus(error.message || String(error), true);
    }
    this.save();
    this.renderImages();
  }

  // The user's pick, else the template's file when it is installed, else the first recommended download that is.
  modelValue(key) {
    const { defaults, choices, models } = this.options;
    const mode = this.state.mode;
    const chosen = this.state.models[mode]?.[key];
    if (chosen) return chosen;
    const folder = MODEL_LABELS[key][1];
    const fallback = defaults[mode][key];
    if ((choices[folder] || []).includes(fallback)) return fallback;
    const row = models[mode].find((item) => item.key === key);
    return row?.options.find((option) => option.installed_as)?.installed_as || fallback;
  }

  renderModels() {
    if (!this.options) return;
    const { choices } = this.options;
    const chosen = (this.state.models[this.state.mode] ||= {});
    const box = this.$("[data-models]");
    box.innerHTML = Object.entries(MODEL_LABELS).map(([key, [label, folder]]) => {
      const value = this.modelValue(key);
      const list = choices[folder] || [];
      const names = list.includes(value) ? list : [value, ...list];
      return `<div><label class="vmx-label">${label}</label><select class="vmx-select" data-model="${key}">
        ${names.map((name) => `<option value="${esc(name)}" ${name === value ? "selected" : ""}>${esc(name)}${list.includes(name) ? "" : " (missing)"}</option>`).join("")}
      </select></div>`;
    }).join("");
    box.querySelectorAll("[data-model]").forEach((select) => select.addEventListener("change", () => {
      chosen[select.dataset.model] = select.value;
      this.save();
      this.renderSetup();
    }));
    this.renderSetup();
  }

  renderSetup() {
    if (!this.options?.custom_nodes) return;
    const { choices, custom_nodes: packs, models } = this.options;
    const mode = this.state.mode;
    let missing = 0;
    const packRows = packs.map((pack) => {
      if (!pack.installed) missing += 1;
      return `<div class="vmx-req ${pack.installed ? "" : "missing"}"><i class="vmx-dot"></i>
        <div><div class="vmx-req-name">${esc(pack.name)}</div>
          ${pack.installed ? "" : `<div class="vmx-req-sub">${pack.note ? "" : "Not installed. Restart ComfyUI after installing."}</div>`}
          ${pack.note ? `<div class="vmx-req-note">${esc(pack.note)}</div>` : ""}</div>
        <a href="${esc(pack.url)}" target="_blank" rel="noopener">GitHub ↗</a></div>`;
    }).join("");
    const modelRows = models[mode].map((row) => {
      const value = this.modelValue(row.key);
      const have = (choices[row.folder] || []).includes(value);
      if (!have) missing += 1;
      const options = row.options.map((option) => `<div class="vmx-opt ${option.installed_as ? "have" : ""}">
        <span>${esc(option.label)} · ${esc(option.size)}</span>
        <a href="${esc(option.url)}" target="_blank" rel="noopener" title="${esc(option.file)}">Download ↗</a></div>`).join("");
      return `<div class="vmx-req ${have ? "" : "missing"}"><i class="vmx-dot"></i>
        <div><div class="vmx-req-name">${esc(row.label)}</div>
          <div class="vmx-req-sub">${have ? esc(value) : `Missing. Put it in models/${esc(row.folder)}`}</div>
          ${have ? `<details class="vmx-opts"><summary>Downloads</summary>${options}</details>` : `<div class="vmx-opts">${options}</div>`}</div>
        <span></span></div>`;
    }).join("");
    const chip = this.$("[data-setup-summary]");
    chip.textContent = missing ? `${missing} missing` : "All set";
    chip.classList.toggle("bad", missing > 0);
    this.$("[data-setup]").innerHTML = `
      <div class="vmx-group">Custom nodes</div>${packRows}
      <div class="vmx-group">Models · ${esc(MODES[mode].label)}</div>${modelRows}
      <div class="vmx-hint">New model files show up after Check again. New custom nodes need a ComfyUI restart.</div>`;
  }

  setStatus(text, error = false) {
    const status = this.$("[data-status]");
    status.textContent = text;
    status.classList.toggle("error", error);
  }

  setRunning(running) {
    this.$('[data-action="generate"]').disabled = running;
    this.$('[data-action="stop"]').hidden = !running;
    if (!running) this.promptId = null;
  }

  async generate() {
    const s = this.state;
    if (s.randomSeed) {
      s.seed = Math.floor(Math.random() * 2 ** 32);
      this.$('[data-bind="seed"]').value = s.seed;
    }
    this.save();
    const [width, height] = SIZES[s.size][s.shape];
    const images = s.mode === "text_to_video" ? [] : s.images[s.mode];
    this.$("[data-bar]").style.width = "0";
    this.$("[data-file-link]").textContent = "";
    this.setRunning(true);
    this.setStatus("Queueing...");
    try {
      const built = await postJson("/vrgdg/minimax_studio/build", {
        mode: s.mode, prompt: s.prompt, images, duration: s.duration,
        width, height, seed: s.seed,
        models: this.options ? Object.fromEntries(Object.keys(MODEL_LABELS).map((key) => [key, this.modelValue(key)])) : {},
        advanced: Object.fromEntries(this.fields().filter((field) => field.defaults[s.mode] !== null)
          .map((field) => [field.key, this.effective(field.key)])),
      });
      const queued = await postJson("/prompt", { prompt: built.prompt, client_id: api.clientId });
      this.promptId = queued.prompt_id;
      this.setStatus("Waiting in the queue...");
    } catch (error) {
      this.setRunning(false);
      this.setStatus(error.message || String(error), true);
    }
  }

  onProgress(detail) {
    if (!this.promptId || detail?.prompt_id !== this.promptId) return;
    const stage = STAGES[detail.node] || "Working";
    this.$("[data-bar]").style.width = `${Math.round((detail.value / Math.max(1, detail.max)) * 100)}%`;
    this.setStatus(`${stage}: ${detail.value}/${detail.max}`);
  }

  onExecuting(detail) {
    if (!this.promptId || detail?.prompt_id !== this.promptId) return;
    if (detail.node === null) {
      this.setRunning(false);
      return;
    }
    this.$("[data-bar]").style.width = "0";
    this.setStatus(`${STAGES[detail.node] || "Working"}...`);
  }

  onError(detail) {
    if (!this.promptId || detail?.prompt_id !== this.promptId) return;
    this.setRunning(false);
    this.setStatus(`${detail.node_type || "Node"} failed: ${detail.exception_message || "unknown error"}`, true);
  }

  onExecuted(detail) {
    if (!this.promptId || detail?.prompt_id !== this.promptId || String(detail.node) !== OUTPUT_NODE) return;
    const video = detail.output?.gifs?.[0];
    if (!video) return;
    const url = api.apiURL(`/view?filename=${encodeURIComponent(video.filename)}&subfolder=${encodeURIComponent(video.subfolder || "")}&type=${video.type || "output"}`);
    this.$("[data-screen]").innerHTML = `<video src="${esc(url)}" controls autoplay loop></video>`;
    this.$("[data-bar]").style.width = "100%";
    this.$("[data-file-link]").innerHTML = `<a href="${esc(url)}" target="_blank">${esc(`${video.subfolder ? `${video.subfolder}/` : ""}${video.filename}`)}</a>`;
    this.setStatus("Done.");
  }
}

let studio = null;

export function openMiniMaxStudio() {
  studio ||= new MiniMaxStudio();
  return studio.open();
}
