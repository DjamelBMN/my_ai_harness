# scripts/update_ui.py
import re
from pathlib import Path

app_js_path = Path("ui/static/app.js")
text = app_js_path.read_text(encoding="utf-8")

# 1. Deduplicate docx in openDocumentPreview
pattern1 = (
    r'(} else if \(type === "docx"\) \{\s*'
    r'const stem = cleanPath\.replace\(/\\\.docx\$/i, ""\);\s*'
    r'docObj\.companionPdf = `\${stem}\.pdf`;\s*'
    r'docObj\.companionDocx = cleanPath;\s*'
    r'docObj\.viewMode = docSpec\.viewMode \|\| "word";\s*'
    r'try \{\s*'
    r'const fileData = await apiGet\(`/api/files/content\?path=\${encodeURIComponent\(cleanPath\)}`\);\s*'
    r'docObj\.size_bytes = fileData\.size_bytes;\s*'
    r'\} catch \(_\) \{\}\s*'
    r'\}\s*)else if \(type === "docx"\) \{\s*'
    r'const stem = cleanPath\.replace\(/\\\.docx\$/i, ""\);\s*'
    r'docObj\.companionPdf = `\${stem}\.pdf`;\s*'
    r'docObj\.companionDocx = cleanPath;\s*'
    r'try \{\s*'
    r'const fileData = await apiGet\(`/api/files/content\?path=\${encodeURIComponent\(cleanPath\)}`\);\s*'
    r'docObj\.size_bytes = fileData\.size_bytes;\s*'
    r'\} catch \(_\) \{\}'
)
if re.search(pattern1, text):
    text = re.sub(pattern1, r"\1", text)
    print("Deduplicated docx block in openDocumentPreview")
else:
    print("Pattern1 not matched")

# 2. Update renderDocumentPreviewPanel Word frame loading
pattern2 = (
    r'if \(isWordView && htmlFrame\) \{\s*'
    r'htmlFrame\.style\.display = "block";\s*'
    r'const targetDocx = doc\.companionDocx \|\| doc\.path;\s*'
    r'htmlFrame\.src = `/api/preview/workspace/\${targetDocx\.split\("/"\)\.map\(encodeURIComponent\)\.join\("/"\)}\?t=\${Date\.now\(\)}`;'
)
replacement2 = """if (isWordView && htmlFrame) {
      htmlFrame.style.display = "block";
      const targetDocx = doc.companionDocx || doc.path;
      const targetSrc = `/api/preview/workspace/${targetDocx.split("/").map(encodeURIComponent).join("/")}?t=${Date.now()}`;
      if (htmlFrame.getAttribute("data-doc-path") !== targetDocx) {
        htmlFrame.setAttribute("data-doc-path", targetDocx);
        htmlFrame.src = targetSrc;
      }
    }"""
if re.search(pattern2, text):
    text = re.sub(pattern2, replacement2, text)
    print("Updated renderDocumentPreviewPanel Word frame loading")
else:
    print("Pattern2 not matched")

# 3. Add SSE handling for Rate Limit & Execution Mode events
pattern3 = r'(if \(parsed\.event === "APPROVAL_REQUIRED"\) \{\s*refreshApprovals\(\);\s*\})'
replacement3 = r"""\1
          if ([
            "AGENT_MODE_CHANGED", "LLM_REQUEST_QUEUED", "LLM_REQUEST_STARTED",
            "LLM_REQUEST_COMPLETED", "LLM_RATE_LIMITED", "LLM_RETRY_SCHEDULED",
            "LLM_CIRCUIT_OPEN", "LLM_CIRCUIT_CLOSED"
          ].includes(parsed.event)) {
            apiGet("/api/execution/config").then((cfg) => {
              if (state.appState && cfg && cfg.mode) {
                state.appState.execution = cfg;
                if (state.rightPanelMode === "inspector" && state.inspectorTab === "model") {
                  renderInspector();
                }
              }
            }).catch(() => {});
          }"""
if re.search(pattern3, text) and "AGENT_MODE_CHANGED" not in text:
    text = re.sub(pattern3, replacement3, text)
    print("Added SSE event handling for execution events")
else:
    print("Pattern3 not matched or already present")

# 4. Enhance renderInspectorModelTab
old_model_tab_start = "function renderInspectorModelTab() {"
new_model_tab = """function renderInspectorModelTab() {
    const s = state.appState;
    const compat = s.compatibility || {};
    const model = compat.model;
    const chain = compat.provider_chain || {};
    const domains = compat.domain_capabilities || [];
    const avail = compat.available_skills || [];
    const unavail = compat.unavailable_skills || [];

    const exec = s.execution || {};
    const execMode = exec.mode || "mono";
    const maxParallel = Number(exec.max_parallel_agents || 1);
    const activeCalls = Number(exec.active_calls || 0);
    const queuedCalls = Number(exec.queued_calls || 0);
    const total429 = Number(exec.total_recent_429 || 0);
    const providerName = (chain.provider || (model ? model.provider : "") || "Gemini").toUpperCase();
    const modelDisplayName = model ? model.display_name.split(" (")[0] : "Gemini Flash Lite";

    const circuits = exec.provider_circuits || {};
    let isCoolingDown = false;
    let cooldownRemaining = 0;
    let coolingProvider = "";
    for (const [pname, pinfo] of Object.entries(circuits)) {
      if (pinfo && pinfo.is_cooling_down) {
        isCoolingDown = true;
        cooldownRemaining = Math.max(cooldownRemaining, Math.round(pinfo.cooldown_remaining_seconds || 0));
        coolingProvider = pname.toUpperCase();
      }
    }
    const cooldownDisplay = isCoolingDown ? `${cooldownRemaining}s` : "aucun";
    const showWaitingBanner = queuedCalls > 0 || isCoolingDown;
    const bannerAgentName = coolingProvider || providerName || "LLM";
    const bannerSeconds = cooldownRemaining > 0 ? cooldownRemaining : 2;

    const capsObj = (model && model.capabilities) || {};
    const fmtCtx = capsObj.context
      ? capsObj.context >= 1000000
        ? `${Math.round(capsObj.context / 100000) / 10}M tokens`
        : `${Math.round(capsObj.context / 1000)}k tokens`
      : "Oui";

    const capRows = [
      ["Vision / Multimodal", capsObj.vision],
      ["Long Context", capsObj.long_context ? fmtCtx : false],
      ["Function Calling", capsObj.tools],
      ["Structured JSON", capsObj.structured_output],
      ["Web Grounding", capsObj.web_grounding],
      ["Streaming", capsObj.streaming],
      ["Raisonnement", capsObj.reasoning],
      ["Température", capsObj.temperature],
    ];

    return `
      <button type="button" class="model-line" data-open-model-modal>
        <span>Modèle actif</span>
        <span class="model-line-value">${esc(compat.selection_mode === "auto" ? "Auto" : model ? model.display_name.split(" (")[0] : "—")} ${ICONS.chevronRight}</span>
      </button>

      <div class="inspector-card execution-cockpit-card">
        <div class="inspector-card-title">
          <span>Mode d'exécution & Rate Limiter</span>
          <span class="meta-chip ${execMode === "mono" ? "secondary" : "accent"}">${execMode === "mono" ? "MONO-AGENT" : "MULTI-AGENT"}</span>
        </div>

        <div style="font-size:11px; font-weight:700; text-transform:uppercase; color:var(--text-muted); letter-spacing:0.04em;">MODE AGENT</div>
        <div class="execution-mode-selector">
          <label class="execution-mode-option ${execMode === "mono" ? "selected" : ""}" data-set-execution-mode="mono">
            <input type="radio" name="cockpit_mode_radio" value="mono" ${execMode === "mono" ? "checked" : ""} data-set-execution-mode="mono">
            <div class="exec-mode-label">
              <span class="exec-mode-title">Mono-Agent</span>
              <span class="exec-mode-desc">1 agent séquentiel (Free Tier recommandé)</span>
            </div>
          </label>
          <label class="execution-mode-option ${execMode === "multi" ? "selected" : ""}" data-set-execution-mode="multi">
            <input type="radio" name="cockpit_mode_radio" value="multi" ${execMode === "multi" ? "checked" : ""} data-set-execution-mode="multi">
            <div class="exec-mode-label">
              <span class="exec-mode-title">Multi-Agent</span>
              <span class="exec-mode-desc">DAG asynchrone borné (${maxParallel} agents)</span>
            </div>
          </label>
        </div>

        <div class="execution-concurrency-row">
          <div class="concurrency-label-wrap">
            <span class="concurrency-title">Agents simultanés</span>
            <span class="concurrency-hint">${execMode === "mono" ? "1 = très prudent (verrouillé en Mono)" : "Limite stricte de concurrence"}</span>
          </div>
          <select class="concurrency-select" data-set-execution-concurrency ${execMode === "mono" ? "disabled" : ""}>
            <option value="1" ${maxParallel === 1 ? "selected" : ""}>1 (très prudent)</option>
            <option value="2" ${maxParallel === 2 ? "selected" : ""}>2 (Free Tier recommandé)</option>
            <option value="3" ${maxParallel === 3 ? "selected" : ""}>3 (équilibré)</option>
            <option value="4" ${maxParallel >= 4 ? "selected" : ""}>4+ (quotas suffisants)</option>
          </select>
        </div>

        <div class="cockpit-telemetry-grid">
          <div class="telemetry-item">
            <span class="tel-label">Provider</span>
            <span class="tel-val" title="${esc(providerName)}">${esc(providerName)}</span>
          </div>
          <div class="telemetry-item">
            <span class="tel-label">Modèle</span>
            <span class="tel-val" title="${esc(modelDisplayName)}">${esc(modelDisplayName)}</span>
          </div>
          <div class="telemetry-item">
            <span class="tel-label">Agents actifs</span>
            <span class="tel-val ${activeCalls > 0 ? "highlight-active" : ""}">${activeCalls} / ${execMode === "mono" ? 1 : maxParallel}</span>
          </div>
          <div class="telemetry-item">
            <span class="tel-label">Appels en attente</span>
            <span class="tel-val ${queuedCalls > 0 ? "highlight-queued" : ""}">${queuedCalls}</span>
          </div>
          <div class="telemetry-item">
            <span class="tel-label">429 récents</span>
            <span class="tel-val ${total429 > 0 ? "highlight-warning" : ""}">${total429}</span>
          </div>
          <div class="telemetry-item">
            <span class="tel-label">Cooldown</span>
            <span class="tel-val ${isCoolingDown ? "highlight-cooldown" : ""}">${esc(cooldownDisplay)}</span>
          </div>
        </div>

        ${
          showWaitingBanner
            ? `
          <div class="telemetry-waiting-banner">
            <span style="font-size:14px;">⏳</span>
            <span><strong>[${esc(bannerAgentName)}]</strong> en attente — Rate limit [${esc(providerName)}] — retry dans ${bannerSeconds} s</span>
          </div>
        `
            : ""
        }
      </div>"""

# Replace the beginning of renderInspectorModelTab up to return `\n      <button
model_tab_regex = (
    r'function renderInspectorModelTab\(\) \{\s*'
    r'const s = state\.appState;\s*'
    r'const compat = s\.compatibility \|\| \{\};\s*'
    r'const model = compat\.model;\s*'
    r'const chain = compat\.provider_chain \|\| \{\};\s*'
    r'const domains = compat\.domain_capabilities \|\| \[\];\s*'
    r'const avail = compat\.available_skills \|\| \[\];\s*'
    r'const unavail = compat\.unavailable_skills \|\| \[\];\s*'
    r'[\s\S]*?'
    r'return `\s*<button type="button" class="model-line" data-open-model-modal>'
)

if re.search(model_tab_regex, text):
    text = re.sub(model_tab_regex, new_model_tab + "\n\n      <button type=\"button\" class=\"model-line\" data-open-model-modal>", text)
    print("Enhanced renderInspectorModelTab with Cockpit Execution Card")
else:
    print("model_tab_regex not matched")

# 5. Add window functions setAgentExecutionMode & setAgentConcurrency if not present
if "window.setAgentExecutionMode" not in text:
    funcs = """
  window.setAgentExecutionMode = async function (mode) {
    try {
      const currParallel = (state.appState && state.appState.execution && state.appState.execution.max_parallel_agents) || 2;
      const targetParallel = mode === "mono" ? 1 : (currParallel > 1 ? currParallel : 2);
      const res = await apiPost("/api/execution/mode", {
        mode: mode,
        max_parallel_agents: targetParallel,
      });
      if (res && res.execution && state.appState) {
        state.appState.execution = res.execution;
        renderInspector();
      } else {
        await refreshFullState();
      }
    } catch (err) {
      showStatusBanner(`Erreur changement de mode : ${err.message}`, "error");
    }
  };

  window.setAgentConcurrency = async function (count) {
    try {
      const num = parseInt(count, 10);
      if (isNaN(num) || num < 1) return;
      const res = await apiPost("/api/execution/config", {
        max_parallel_agents: num,
      });
      if (res && res.execution && state.appState) {
        state.appState.execution = res.execution;
        renderInspector();
      } else {
        await refreshFullState();
      }
    } catch (err) {
      showStatusBanner(`Erreur réglage agents simultanés : ${err.message}`, "error");
    }
  };
"""
    # Insert right before document.addEventListener("click"
    click_listener = 'document.addEventListener("click", async (e) => {'
    if click_listener in text:
        text = text.replace(click_listener, funcs + "\n  " + click_listener)
        print("Exposed setAgentExecutionMode and setAgentConcurrency on window")

# 6. Add event listeners inside click and change handlers
click_pattern = r'(if \(target\.hasAttribute\("data-inspector-tab"\)\) \{)'
click_hook = """if (target.hasAttribute("data-set-execution-mode") || target.closest("[data-set-execution-mode]")) {
        const el = target.hasAttribute("data-set-execution-mode") ? target : target.closest("[data-set-execution-mode]");
        const mode = el.getAttribute("data-set-execution-mode");
        if (mode) {
          window.setAgentExecutionMode(mode);
          return;
        }
      }

      \\1"""
if "data-set-execution-mode" not in text:
    text = re.sub(click_pattern, click_hook, text)
    print("Added click handler for data-set-execution-mode")

# Add change event listener for concurrency select
if "data-set-execution-concurrency" not in text:
    change_listener = """
    document.addEventListener("change", (e) => {
      const target = e.target;
      if (target && target.hasAttribute("data-set-execution-concurrency")) {
        window.setAgentConcurrency(target.value);
      }
    });
"""
    end_of_app = text.rfind("})();")
    if end_of_app != -1:
        text = text[:end_of_app] + change_listener + "\n" + text[end_of_app:]
        print("Added change listener for data-set-execution-concurrency")

app_js_path.write_text(text, encoding="utf-8")
print("Successfully written ui/static/app.js!")

