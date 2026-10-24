/* RÔLE DE CE FICHIER :
 * Logique frontend minimaliste et complète de NeoHarness AI (Complexité cachée, Zéro simulation).
 * Pilote :
 * 1. Le Mode Clair premium par défaut (avec persistance localStorage et bascule Sombre/Clair)
 * 2. La palette flottante immédiate des 18 Slash Commands (/) dans l'ordre canonique
 * 3. Le panneau latéral droit unifié : Aperçu Document (PDF compilé via Tectonic & HTML sandboxé) + Inspecteur
 * 4. La dictée vocale style GPT avec onde audio temps réel (Web Audio API AnalyserNode + SpeechRecognition)
 * 5. Le streaming SSE temps réel (STREAM_DELTA, ARTIFACT_READY) avec rendu Markdown + KaTeX
 */

(function () {
  "use strict";

  const CANONICAL_SKILLS_FALLBACK = [
    { canonical_index: 1, name: "analyze", display_name: "Analyze", slash_command: "/analyze", description: "Analyse des fichiers, documents ou extraits du workspace.", compatible: true, requires_mission: true, aliases: ["/analyse"] },
    { canonical_index: 2, name: "auto", display_name: "Auto", slash_command: "/auto", description: "Exécute une mission complète en mode autonome.", compatible: true, requires_mission: true, aliases: [] },
    { canonical_index: 3, name: "bacblanc", display_name: "BacBlanc", slash_command: "/bacblanc", description: "Génère et compile un sujet de Bac Blanc LaTeX en PDF via Tectonic.", compatible: true, requires_mission: false, aliases: ["/bac"] },
    { canonical_index: 4, name: "compare", display_name: "Compare", slash_command: "/compare", description: "Compare deux fichiers, approches ou solutions techniques.", compatible: true, requires_mission: true, aliases: ["/diff"] },
    { canonical_index: 5, name: "context", display_name: "Context", slash_command: "/context", description: "Affiche l'état du contexte de session et des fichiers suivis.", compatible: true, requires_mission: false, aliases: ["/ctx"] },
    { canonical_index: 6, name: "debug", display_name: "Debug", slash_command: "/debug", description: "Diagnostique un bug, corrige le code et vérifie les tests.", compatible: true, requires_mission: true, aliases: ["/fix"] },
    { canonical_index: 7, name: "diagnostic", display_name: "Diagnostic", slash_command: "/diagnostic", description: "Vérifie l'état réel des providers, modèles, outils et compilateurs.", compatible: true, requires_mission: false, aliases: ["/diag", "/doctor"] },
    { canonical_index: 8, name: "export", display_name: "Export", slash_command: "/export", description: "Exporte le dernier résultat en Markdown ou PDF dans workspace/exports/.", compatible: true, requires_mission: false, aliases: ["/save"] },
    { canonical_index: 9, name: "memory", display_name: "Memory", slash_command: "/memory", description: "Consulte ou enregistre des notes et décisions dans la mémoire persistante.", compatible: true, requires_mission: false, aliases: ["/mem"] },
    { canonical_index: 10, name: "mode", display_name: "Mode", slash_command: "/mode", description: "Consulte ou change le mode de gouvernance (EDIT, PLAN, ACCEPT, AUTO).", compatible: true, requires_mission: false, aliases: [] },
    { canonical_index: 11, name: "model", display_name: "Model", slash_command: "/model", description: "Consulte ou change le modèle IA actif.", compatible: true, requires_mission: false, aliases: ["/models"] },
    { canonical_index: 12, name: "plan", display_name: "Plan", slash_command: "/plan", description: "Construit le plan d'exécution détaillé d'une tâche sans modifier le disque.", compatible: true, requires_mission: true, aliases: [] },
    { canonical_index: 13, name: "refactor", display_name: "Refactor", slash_command: "/refactor", description: "Refactorise du code existant proprement en préservant les tests.", compatible: true, requires_mission: true, aliases: [] },
    { canonical_index: 14, name: "research", display_name: "Research", slash_command: "/research", description: "Effectue une recherche approfondie (Web et RAG) avec sources vérifiées.", compatible: true, requires_mission: true, aliases: ["/search", "/web"] },
    { canonical_index: 15, name: "review", display_name: "Review", slash_command: "/review", description: "Réalise une revue de code et de qualité sur les fichiers du workspace.", compatible: true, requires_mission: true, aliases: [] },
    { canonical_index: 16, name: "route", display_name: "Route", slash_command: "/route", description: "Analyse l'intention et route la mission vers le meilleur agent/modèle.", compatible: true, requires_mission: true, aliases: [] },
    { canonical_index: 17, name: "test", display_name: "Test", slash_command: "/test", description: "Exécute ou génère des tests unitaires et vérifie les résultats.", compatible: true, requires_mission: true, aliases: ["/tests"] },
    { canonical_index: 18, name: "workflow", display_name: "Workflow", slash_command: "/workflow", description: "Orchestre un workflow multi-étapes complet avec vérification finale.", compatible: true, requires_mission: true, aliases: [] },
  ];

  const state = {
    appState: null,
    inspectorTab: "model",
    rightPanelMode: "inspector", // "inspector" | "document"
    activeDocument: null, // { type: 'pdf'|'html'|'tex', path, source_tex, page_count, size_bytes, viewMode: 'render'|'source', zoom: 100, auto_repaired, repair_notes, error, sourceContent }
    sidebarFilter: "",
    attachedFiles: [],
    selectedFilePreview: null,
    isExecuting: false,
    streamingBuffer: "",
    sse: null,
    slashPalette: {
      open: false,
      query: "",
      tokenStart: 0,
      tokenEnd: 0,
      selectedIndex: 0,
      filteredSkills: [],
    },
    voice: {
      active: false,
      stream: null,
      audioCtx: null,
      analyser: null,
      rafId: null,
      timerInterval: null,
      startedAt: 0,
      recognition: null,
      finalTranscript: "",
      interimTranscript: "",
      preExistingText: "",
      cancelled: false,
    },
  };

  function esc(value) {
    if (value === null || value === undefined) return "";
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  async function apiGet(url) {
    const res = await fetch(url, { headers: { Accept: "application/json" } });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `Erreur HTTP ${res.status}`);
    return data;
  }

  async function apiPost(url, payload) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload || {}),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `Erreur HTTP ${res.status}`);
    return data;
  }

  // =========================================================================
  // 0. THÈME CLAIR PAR DÉFAUT & PERSISTANCE LOCALSTORAGE
  // =========================================================================

  function initTheme() {
    let saved = null;
    try {
      saved = localStorage.getItem("neoharness_theme");
    } catch (_) {}
    const theme = saved === "dark" ? "dark" : "light";
    applyTheme(theme, false);
  }

  function applyTheme(theme, persist) {
    const normalized = theme === "dark" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", normalized);
    const iconEl = document.getElementById("theme-icon");
    if (iconEl) {
      iconEl.textContent = normalized === "light" ? "☀️" : "🌙";
    }
    if (persist) {
      try {
        localStorage.setItem("neoharness_theme", normalized);
      } catch (_) {}
    }
  }

  // =========================================================================
  // CHARGEMENT D'ÉTAT & STREAMING SSE TEMPS RÉEL
  // =========================================================================

  async function refreshFullState(modelOverride) {
    const query = modelOverride ? `?model=${encodeURIComponent(modelOverride)}` : "";
    state.appState = await apiGet(`/api/state${query}`);
    renderAll();
  }

  function connectSSE() {
    if (state.sse) {
      try {
        state.sse.close();
      } catch (_) {}
    }
    try {
      const es = new EventSource("/api/events/stream");
      es.onmessage = (evt) => {
        try {
          const parsed = JSON.parse(evt.data);
          if (!state.appState) return;

          if (parsed.event === "STREAM_DELTA") {
            const delta = (parsed.metadata && parsed.metadata.delta) || parsed.summary || "";
            if (delta && state.isExecuting) {
              state.streamingBuffer += delta;
              renderStreamingAssistantBubble();
            }
            return;
          }

          if (parsed.event === "ARTIFACT_READY" && parsed.metadata) {
            const art = parsed.metadata;
            if (art.type === "pdf" || art.type === "html") {
              openDocumentPreview(art);
            }
          }

          state.appState.events = state.appState.events || [];
          state.appState.events.push(parsed);
          if (state.appState.events.length > 250) {
            state.appState.events = state.appState.events.slice(-250);
          }
          if (parsed.event === "APPROVAL_REQUIRED") {
            refreshApprovals();
          }
          updateTopTaskStatusFromEvent(parsed);
          if (state.rightPanelMode === "inspector" && state.inspectorTab === "activity") {
            renderInspector();
          }
        } catch (_) {}
      };
      state.sse = es;
    } catch (_) {}
  }

  function renderStreamingAssistantBubble() {
    const welcomeEl = document.getElementById("welcome-screen");
    const streamEl = document.getElementById("conversation-stream");
    if (!streamEl) return;
    if (welcomeEl) welcomeEl.style.display = "none";
    streamEl.style.display = "flex";

    let bubble = document.getElementById("streaming-assistant-card");
    if (!bubble) {
      bubble = document.createElement("article");
      bubble.id = "streaming-assistant-card";
      bubble.className = "message-card assistant";
      streamEl.appendChild(bubble);
    }
    bubble.innerHTML = `
      <div class="message-header">
        <div class="message-meta-badges">
          <strong>NeoHarness AI</strong>
          <span class="meta-chip accent">Streaming temps réel…</span>
        </div>
      </div>
      <div class="message-body md-prose">${formatAssistantContent(state.streamingBuffer)}<span class="streaming-cursor"></span></div>
    `;
    const scrollEl = document.getElementById("workspace-scroll");
    if (scrollEl) {
      scrollEl.scrollTop = scrollEl.scrollHeight;
    }
  }

  async function refreshApprovals() {
    try {
      const data = await apiGet("/api/approvals");
      if (state.appState) {
        state.appState.pending_approvals = data.approvals || [];
        renderApprovalBanner();
      }
    } catch (_) {}
  }

  function updateTopTaskStatusFromEvent(evt) {
    const el = document.getElementById("top-task-status");
    const dot = document.getElementById("top-task-dot");
    if (!el || !dot) return;
    if (evt.event === "PLANNER_STARTED" || evt.event === "PLAN_CREATED") {
      el.textContent = "Planification";
      dot.className = "status-dot running";
    } else if (evt.event === "APPROVAL_REQUIRED") {
      el.textContent = "Validation requise";
      dot.className = "status-dot warning";
    } else if (evt.event === "TOOL_CALL") {
      el.textContent = evt.tool ? `Outil : ${evt.tool}` : "Exécution outil";
      dot.className = "status-dot running";
    } else if (evt.event === "VERIFIER") {
      el.textContent = "Vérification";
      dot.className = "status-dot running";
    } else if (evt.event === "TASK_COMPLETED") {
      el.textContent = evt.status === "partial" ? "Partiel" : "Terminé";
      dot.className = evt.status === "partial" ? "status-dot warning" : "status-dot";
    } else if (evt.event === "ERROR") {
      el.textContent = "Erreur";
      dot.className = "status-dot error";
    } else if (state.isExecuting) {
      el.textContent = "Exécution…";
      dot.className = "status-dot running";
    }
  }

  // =========================================================================
  // RENDU GLOBAL
  // =========================================================================

  function renderAll() {
    if (!state.appState) return;
    renderTopBar();
    renderSidebar();
    renderWorkspace();
    renderApprovalBanner();
    renderComposerControls();
    renderInspector();
    if (state.slashPalette.open) {
      updateSlashPaletteFromInput();
    }
  }

  // -------------------------------------------------------------------------
  // 1. TOP BAR MINIMALISTE
  // -------------------------------------------------------------------------
  function renderTopBar() {
    const s = state.appState;
    const sel = s.model_selection || {};
    const eff = sel.effective_model;
    const isAuto = sel.mode === "auto";

    const modelLabel = document.getElementById("top-model-label");
    const modelDot = document.getElementById("top-model-dot");
    if (modelLabel) {
      modelLabel.textContent = isAuto
        ? `Auto · ${eff ? eff.display_name.split(" (")[0] : "ModelRouter"}`
        : eff
        ? eff.display_name
        : sel.selected_id;
    }
    if (modelDot) {
      modelDot.className = eff && !eff.connected ? "status-dot warning" : "status-dot";
    }

    const taskStatusEl = document.getElementById("top-task-status");
    const taskDotEl = document.getElementById("top-task-dot");
    if (taskStatusEl && !state.isExecuting) {
      const rawStatus = s.task_status || "Prêt";
      taskStatusEl.textContent = rawStatus === "En attente" ? "Prêt" : rawStatus;
      if (taskDotEl) {
        taskDotEl.className =
          rawStatus === "Erreur"
            ? "status-dot error"
            : rawStatus === "Partiel" || rawStatus === "Attente validation"
            ? "status-dot warning"
            : "status-dot";
      }
    }
  }

  // -------------------------------------------------------------------------
  // 2. SIDEBAR DISCRÈTE
  // -------------------------------------------------------------------------
  function renderSidebar() {
    const s = state.appState;
    const filter = state.sidebarFilter.trim().toLowerCase();

    const convs = (s.conversations || []).filter((c) => {
      if (!filter) return true;
      return (c.title || "").toLowerCase().includes(filter);
    });
    const countConvsEl = document.getElementById("count-conversations");
    if (countConvsEl) countConvsEl.textContent = String(convs.length);

    const activeCid = (s.active_conversation && s.active_conversation.id) || "";
    const convContainer = document.getElementById("sec-conversations");
    if (convContainer) {
      convContainer.innerHTML = convs
        .map((c) => {
          const isCurrent = c.id === activeCid;
          const pinIcon = c.pinned ? "📌 " : "";
          const archTag = c.archived ? " · archivé" : "";
          return `
            <div class="sidebar-item ${isCurrent ? "active" : ""}" data-select-conv="${esc(c.id)}">
              <div class="sidebar-item-main">
                <span class="sidebar-item-title" title="${esc(c.title)}">${pinIcon}${esc(c.title)}${archTag}</span>
              </div>
              <div class="conv-actions">
                <button class="icon-btn-mini" data-pin-conv="${esc(c.id)}" data-pinned="${c.pinned ? "1" : "0"}" title="Épingler">📌</button>
                <button class="icon-btn-mini" data-rename-conv="${esc(c.id)}" data-title="${esc(c.title)}" title="Renommer">✎</button>
                <button class="icon-btn-mini" data-delete-conv="${esc(c.id)}" title="Supprimer">✕</button>
              </div>
            </div>
          `;
        })
        .join("");
    }

    const projects = s.projects || [];
    const countProjEl = document.getElementById("count-projects");
    if (countProjEl) countProjEl.textContent = String(projects.length);
    const projContainer = document.getElementById("sec-projects");
    if (projContainer) {
      projContainer.innerHTML = projects
        .map(
          (p) => `
          <div class="sidebar-item ${p.active ? "active" : ""}" title="${esc(p.path)}">
            <div class="sidebar-item-main">
              <span class="sidebar-item-title">${esc(p.name)}</span>
            </div>
            <span class="sidebar-item-sub">${esc(p.type === "Harness Principal" ? "Actif" : "Dossier")}</span>
          </div>
        `
        )
        .join("");
    }

    const allSkills = getCanonicalSkills();
    const countSkillsEl = document.getElementById("count-skills");
    if (countSkillsEl) countSkillsEl.textContent = String(allSkills.length);

    const tools = s.tools || [];
    const countToolsEl = document.getElementById("count-tools");
    if (countToolsEl) countToolsEl.textContent = String(tools.length);

    const models = s.models || [];
    const countModelsEl = document.getElementById("count-models");
    if (countModelsEl) countModelsEl.textContent = String(models.length);
  }

  // -------------------------------------------------------------------------
  // 3. CENTER WORKSPACE (WELCOME & CONVERSATION ÉDITORIALE + ARTEFACTS)
  // -------------------------------------------------------------------------
  function extractMessageArtifacts(m) {
    const list = [];
    const seen = new Set();

    function addArt(item) {
      if (!item || !item.path) return;
      const norm = String(item.path).replace(/\\/g, "/");
      if (seen.has(norm)) return;
      seen.add(norm);
      list.push({ ...item, path: norm });
    }

    if (Array.isArray(m.preview_artifacts)) {
      m.preview_artifacts.forEach(addArt);
    }
    if (Array.isArray(m.artifacts)) {
      m.artifacts.forEach(addArt);
    }

    const filesMod = m.files_modified || [];
    filesMod.forEach((f) => {
      const rawPath = typeof f === "object" && f !== null ? f.path : f;
      if (!rawPath) return;
      const norm = String(rawPath).replace(/\\/g, "/");
      const lower = norm.toLowerCase();
      if (lower.endsWith(".pdf")) {
        addArt({ type: "pdf", path: norm });
      } else if (lower.endsWith(".html") || lower.endsWith(".htm")) {
        addArt({ type: "html", path: norm });
      } else if (lower.endsWith(".tex")) {
        addArt({ type: "tex", path: norm });
      }
    });

    const content = String(m.content || "");
    const exportMatch = content.match(/\[EXPORT OK\]\s+([^\s|]+\.(?:pdf|md|html))/i);
    if (exportMatch) {
      const p = exportMatch[1].trim();
      if (p.toLowerCase().endsWith(".pdf")) addArt({ type: "pdf", path: p });
      else if (p.toLowerCase().endsWith(".html")) addArt({ type: "html", path: p });
    }

    return list;
  }

  function renderMessageArtifactsHtml(m) {
    const artifacts = extractMessageArtifacts(m);
    if (artifacts.length === 0) return "";

    return `
      <div class="message-artifacts-row">
        ${artifacts
          .map((art) => {
            if (art.type === "pdf") {
              const pagesTxt = art.page_count ? ` · ${art.page_count} page${art.page_count > 1 ? "s" : ""}` : "";
              return `
                <div class="artifact-card">
                  <div class="artifact-card-title">
                    <span>📄</span>
                    <span class="mono">${esc(art.path)}</span>
                    <span class="meta-chip accent">PDF${esc(pagesTxt)}</span>
                  </div>
                  <div class="artifact-card-actions">
                    <button
                      type="button"
                      class="artifact-btn primary"
                      data-open-doc-preview="pdf"
                      data-doc-path="${esc(art.path)}"
                      data-doc-source="${esc(art.source_tex || "")}"
                      data-doc-pages="${esc(art.page_count || "")}"
                    >
                      Aperçu PDF
                    </button>
                    <a class="artifact-btn" href="/api/files/raw?path=${encodeURIComponent(art.path)}&download=1" download>
                      ⬇ Télécharger
                    </a>
                  </div>
                </div>
              `;
            }
            if (art.type === "html") {
              return `
                <div class="artifact-card">
                  <div class="artifact-card-title">
                    <span>🌐</span>
                    <span class="mono">${esc(art.path)}</span>
                    <span class="meta-chip accent">HTML</span>
                  </div>
                  <div class="artifact-card-actions">
                    <button
                      type="button"
                      class="artifact-btn primary"
                      data-open-doc-preview="html"
                      data-doc-path="${esc(art.path)}"
                      data-doc-view="render"
                    >
                      Aperçu HTML
                    </button>
                    <button
                      type="button"
                      class="artifact-btn"
                      data-open-doc-preview="html"
                      data-doc-path="${esc(art.path)}"
                      data-doc-view="source"
                    >
                      Code source
                    </button>
                    <a class="artifact-btn" href="/api/files/raw?path=${encodeURIComponent(art.path)}&download=1" download>
                      ⬇
                    </a>
                  </div>
                </div>
              `;
            }
            if (art.type === "tex") {
              return `
                <div class="artifact-card">
                  <div class="artifact-card-title">
                    <span>📐</span>
                    <span class="mono">${esc(art.path)}</span>
                    <span class="meta-chip">LaTeX</span>
                  </div>
                  <div class="artifact-card-actions">
                    <button
                      type="button"
                      class="artifact-btn primary"
                      data-compile-tex-path="${esc(art.path)}"
                    >
                      ⚡ Compiler PDF (Tectonic)
                    </button>
                    <button
                      type="button"
                      class="artifact-btn"
                      data-open-doc-preview="tex"
                      data-doc-path="${esc(art.path)}"
                      data-doc-view="source"
                    >
                      Source .tex
                    </button>
                  </div>
                </div>
              `;
            }
            return "";
          })
          .join("")}
      </div>
    `;
  }

  function renderWorkspace() {
    const s = state.appState;
    const conv = s.active_conversation || { messages: [] };
    const msgs = conv.messages || [];

    const welcomeEl = document.getElementById("welcome-screen");
    const streamEl = document.getElementById("conversation-stream");

    renderWelcomeModelCard();

    if (msgs.length === 0 && !state.isExecuting) {
      welcomeEl.style.display = "flex";
      streamEl.style.display = "none";
      streamEl.innerHTML = "";
      return;
    }

    welcomeEl.style.display = "none";
    streamEl.style.display = "flex";

    streamEl.innerHTML = msgs
      .map((m, idx) => {
        if (m.role === "user") {
          const attHtml =
            m.attachments && m.attachments.length
              ? `<div class="message-meta-badges">${m.attachments
                  .map((a) => `<span class="meta-chip">📎 ${esc(a)}</span>`)
                  .join("")}</div>`
              : "";
          return `
            <article class="message-card user" data-msg-id="${esc(m.id)}">
              ${attHtml}
              <div class="message-body">${esc(m.content)}</div>
              <div class="message-actions">
                <button class="msg-action-btn" data-copy-msg="${idx}">Copier</button>
                <button class="msg-action-btn" data-edit-msg="${idx}">Modifier</button>
              </div>
            </article>
          `;
        }

        const badges = [];
        if (m.model) badges.push(`<span class="meta-chip">${esc(m.model)}</span>`);
        if (m.skill) badges.push(`<span class="meta-chip accent">/${esc(m.skill)}</span>`);
        if (m.agent && m.agent !== "Runtime Local") badges.push(`<span class="meta-chip">${esc(m.agent)}</span>`);
        if (m.status === "Erreur") {
          badges.push(`<span class="meta-chip error">Erreur</span>`);
        } else if (m.status === "Partiel") {
          badges.push(`<span class="meta-chip warning">Partiel</span>`);
        } else if (m.verification) {
          badges.push(`<span class="meta-chip success">✓ Vérifié</span>`);
        }

        const eventsList = m.events || [];
        const planSteps = m.plan_steps || [];
        const toolsUsed = m.tools_used || [];
        const sourcesUsed = m.sources || [];
        const filesMod = m.files_modified || [];

        const summaryParts = [];
        if (planSteps.length > 0) summaryParts.push(`${planSteps.length} étapes`);
        if (toolsUsed.length > 0) {
          const uniqueTools = Array.from(new Set(toolsUsed));
          summaryParts.push(`${toolsUsed.length} outil${toolsUsed.length > 1 ? "s" : ""} (${uniqueTools.join(", ")})`);
        }
        if (sourcesUsed.length > 0) summaryParts.push(`${sourcesUsed.length} source${sourcesUsed.length > 1 ? "s" : ""} Web`);
        if (m.duration_ms !== undefined) summaryParts.push(`${m.duration_ms} ms`);

        const activityHtml =
          summaryParts.length > 0 && (toolsUsed.length > 0 || planSteps.length > 0)
            ? `
            <details class="activity-flow-box">
              <summary class="activity-flow-summary">
                <span>⚡ ${esc(summaryParts.join(" · "))}</span>
                <span>▾</span>
              </summary>
              <div class="activity-steps-list">
                ${
                  planSteps.length
                    ? `<div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">
                        <strong>Plan :</strong> ${planSteps.map((st, i) => `${i + 1}. ${esc(st)}`).join(" → ")}
                       </div>`
                    : ""
                }
                ${eventsList
                  .filter((ev) => ev.event !== "CONTEXT_LOADING" && ev.event !== "SKILL_DISCOVERY")
                  .map(
                    (ev) => `
                    <div class="activity-step-row">
                      <div>
                        <span class="meta-chip">${esc(ev.event)}</span>
                        <span style="margin-left: 6px;">${esc(ev.summary)}</span>
                      </div>
                      <span class="mono" style="color: var(--text-muted); font-size: 10.5px;">
                        ${ev.tool ? `🔧 ${esc(ev.tool)} ` : ""}${ev.duration_ms ? `${ev.duration_ms}ms` : ""}
                      </span>
                    </div>
                  `
                  )
                  .join("")}
              </div>
            </details>
          `
            : "";

        const artifactsHtml = renderMessageArtifactsHtml(m);

        const sourcesHtml =
          sourcesUsed.length > 0
            ? `
            <div class="message-sources-row">
              ${sourcesUsed
                .map(
                  (src) => `
                  <a class="source-pill" href="${esc(src.url)}" target="_blank" rel="noopener noreferrer" title="${esc(src.title)} (${esc(src.published_at || src.source || src.url)})">
                    <span>🌐</span>
                    <span>${esc(src.source ? `${src.source} — ${src.title}` : src.title || src.url)}</span>
                  </a>
                `
                )
                .join("")}
            </div>
          `
            : "";

        return `
          <article class="message-card assistant" data-msg-id="${esc(m.id)}">
            <div class="message-header">
              <div class="message-meta-badges">
                <strong>NeoHarness AI</strong>
                ${badges.join("")}
              </div>
              <span class="mono" style="font-size: 11px; color: var(--text-muted);">${esc((m.timestamp || "").slice(11, 19))}</span>
            </div>
            ${activityHtml}
            <div class="message-body md-prose">${formatAssistantContent(m.content)}</div>
            ${artifactsHtml}
            ${sourcesHtml}
            <div class="message-actions">
              <button class="msg-action-btn" data-copy-msg="${idx}">Copier</button>
              <button class="msg-action-btn" data-regen-msg="${idx}">Régénérer</button>
              <button class="msg-action-btn" data-show-msg-tools="${idx}">Inspecter (${toolsUsed.length} outil${toolsUsed.length > 1 ? "s" : ""})</button>
              ${
                sourcesUsed.length + filesMod.length > 0
                  ? `<button class="msg-action-btn" data-show-msg-sources="${idx}">Sources (${sourcesUsed.length + filesMod.length})</button>`
                  : ""
              }
              <button class="msg-action-btn" data-export-last="markdown">Exporter MD</button>
              <button class="msg-action-btn" data-export-last="pdf">Exporter PDF</button>
            </div>
          </article>
        `;
      })
      .join("");
  }

  // -------------------------------------------------------------------------
  // RENDU MARKDOWN + KATEX MATH
  // -------------------------------------------------------------------------
  function renderMathExpression(expr, displayMode) {
    const cleaned = String(expr || "").trim();
    if (!cleaned) return "";
    if (window.katex && typeof window.katex.renderToString === "function") {
      try {
        return window.katex.renderToString(cleaned, {
          displayMode: Boolean(displayMode),
          throwOnError: false,
          strict: "ignore",
        });
      } catch (_) {}
    }
    return displayMode
      ? `<div class="math-block mono">${esc(cleaned)}</div>`
      : `<code class="math-inline mono">${esc(cleaned)}</code>`;
  }

  function formatInlineMarkdown(text, inlineMathTokens) {
    let out = esc(text);
    // Code inline
    out = out.replace(/`([^`\n]+)`/g, "<code>$1</code>");
    // Liens [label](https://...)
    out = out.replace(
      /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
    );
    // Gras + Italique ***...*** ou ___...___
    out = out.replace(/\*\*\*([^*]+)\*\*\*/g, "<strong><em>$1</em></strong>");
    out = out.replace(/___([^_]+)___/g, "<strong><em>$1</em></strong>");
    // Gras **...** ou __...__
    out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    out = out.replace(/__([^_]+)__/g, "<strong>$1</strong>");
    // Italique *...* ou _..._
    out = out.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, "$1<em>$2</em>");
    out = out.replace(/(^|[^_])_([^_\n]+)_(?!_)/g, "$1<em>$2</em>");

    // Supprimer tout astérisque ou puce parasite orpheline en début de texte
    out = out.replace(/^\s*[\*•]\s+/, "");
    // Supprimer les doubles astérisques non fermés
    out = out.replace(/\*\*/g, "");
    // Supprimer les astérisques orphelins non fermés en début de mot (ex: "*Astuce" sans fermeture)
    out = out.replace(/(^|\s)\*([^\s*]+)/g, "$1$2");
    // Convertir les astérisques isolés restants en séparateur discret
    out = out.replace(/(\s)\*(\s|$)/g, "$1•$2");

    if (inlineMathTokens && inlineMathTokens.length) {
      out = out.replace(/@@INLINEMATH_(\d+)@@/g, function (_, idxStr) {
        const idx = Number(idxStr);
        return inlineMathTokens[idx] || "";
      });
    }
    return out;
  }

  function formatAssistantContent(raw) {
    if (!raw) return "<em style='color:var(--text-secondary);'>Aucune sortie texte.</em>";

    const codeBlocks = [];
    const mathBlocks = [];
    const inlineMathTokens = [];

    // 1. Extraction des blocs de code ```...```
    let working = String(raw).replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, function (_, lang, code) {
      const token = `\n@@CODEBLOCK_${codeBlocks.length}@@\n`;
      codeBlocks.push(`<pre><code class="lang-${esc(lang)}">${esc(code)}</code></pre>`);
      return token;
    });

    // 2. Extraction des blocs mathématiques $$...$$ et \[...\]
    working = working.replace(/\$\$([\s\S]*?)\$\$/g, function (_, expr) {
      const token = `\n@@MATHBLOCK_${mathBlocks.length}@@\n`;
      mathBlocks.push(`<div class="math-block">${renderMathExpression(expr, true)}</div>`);
      return token;
    });
    working = working.replace(/\\\[([\s\S]*?)\\\]/g, function (_, expr) {
      const token = `\n@@MATHBLOCK_${mathBlocks.length}@@\n`;
      mathBlocks.push(`<div class="math-block">${renderMathExpression(expr, true)}</div>`);
      return token;
    });

    // 3. Extraction des formules inline \(...\) et $...$ (en évitant les prix comme 10$ ou $100 isolés)
    working = working.replace(/\\\(([^\n]+?)\\\)/g, function (_, expr) {
      const token = `@@INLINEMATH_${inlineMathTokens.length}@@`;
      inlineMathTokens.push(`<span class="math-inline">${renderMathExpression(expr, false)}</span>`);
      return token;
    });
    working = working.replace(/(^|[^\\$])\$([^\s$][^$\n]*?[^\s$]|[^\s$])\$(?!\d)/g, function (_, prefix, expr) {
      const token = `${prefix}@@INLINEMATH_${inlineMathTokens.length}@@`;
      inlineMathTokens.push(`<span class="math-inline">${renderMathExpression(expr, false)}</span>`);
      return token;
    });

    const lines = working.split("\n");
    const htmlParts = [];
    let currentListType = null; // "ul" | "ol"

    function closeList() {
      if (currentListType) {
        htmlParts.push(`</${currentListType}>`);
        currentListType = null;
      }
    }

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const trimmed = line.trim();

      if (/^@@CODEBLOCK_\d+@@$/.test(trimmed)) {
        closeList();
        const idx = Number(trimmed.replace(/\D+/g, ""));
        htmlParts.push(codeBlocks[idx] || "");
        continue;
      }

      if (/^@@MATHBLOCK_\d+@@$/.test(trimmed)) {
        closeList();
        const idx = Number(trimmed.replace(/\D+/g, ""));
        htmlParts.push(mathBlocks[idx] || "");
        continue;
      }

      // Lignes vides : maintenir la liste ouverte si l'élément suivant continue la liste
      if (!trimmed) {
        let hasNextListItem = false;
        for (let j = i + 1; j < lines.length; j++) {
          const nextTrimmed = lines[j].trim();
          if (!nextTrimmed) continue;
          if (/^([-*+•]|\d+[.)])\s+/.test(nextTrimmed)) {
            hasNextListItem = true;
          }
          break;
        }
        if (!hasNextListItem) {
          closeList();
        }
        continue;
      }

      // Séparateurs horizontaux (--- ou *** ou ___)
      if (/^(?:[-*_]\s*){3,}$/.test(trimmed)) {
        closeList();
        htmlParts.push("<hr />");
        continue;
      }

      // Titres Markdown
      if (trimmed.startsWith("#### ")) {
        closeList();
        htmlParts.push(`<h4>${formatInlineMarkdown(trimmed.slice(5), inlineMathTokens)}</h4>`);
        continue;
      }
      if (trimmed.startsWith("### ")) {
        closeList();
        htmlParts.push(`<h3>${formatInlineMarkdown(trimmed.slice(4), inlineMathTokens)}</h3>`);
        continue;
      }
      if (trimmed.startsWith("## ")) {
        closeList();
        htmlParts.push(`<h2>${formatInlineMarkdown(trimmed.slice(3), inlineMathTokens)}</h2>`);
        continue;
      }
      if (trimmed.startsWith("# ")) {
        closeList();
        htmlParts.push(`<h1>${formatInlineMarkdown(trimmed.slice(2), inlineMathTokens)}</h1>`);
        continue;
      }

      // Blockquotes
      if (trimmed.startsWith("> ")) {
        closeList();
        htmlParts.push(`<blockquote>${formatInlineMarkdown(trimmed.slice(2), inlineMathTokens)}</blockquote>`);
        continue;
      }

      // Puces non numérotées (* , - , + , •) avec gestion de l'indentation
      const ulMatch = line.match(/^(\s*)([-*+•])\s+(.*)$/);
      if (ulMatch) {
        const indent = ulMatch[1].length;
        const itemText = ulMatch[3];
        if (currentListType === "ol") {
          closeList();
        }
        if (!currentListType) {
          htmlParts.push("<ul>");
          currentListType = "ul";
        }
        const nestedStyle = indent >= 2 ? ' style="margin-left: 20px; list-style-type: circle;"' : "";
        htmlParts.push(`<li${nestedStyle}>${formatInlineMarkdown(itemText, inlineMathTokens)}</li>`);
        continue;
      }

      // Listes numérotées (1. ou 1) ou 1 - )
      const olMatch = line.match(/^(\s*)(\d+)[.)]\s+(.*)$/);
      if (olMatch) {
        const itemText = olMatch[3];
        if (currentListType === "ul") {
          closeList();
        }
        if (!currentListType) {
          htmlParts.push("<ol>");
          currentListType = "ol";
        }
        htmlParts.push(`<li>${formatInlineMarkdown(itemText, inlineMathTokens)}</li>`);
        continue;
      }

      // Paragraphes normaux
      closeList();
      htmlParts.push(`<p>${formatInlineMarkdown(line, inlineMathTokens)}</p>`);
    }

    closeList();
    return htmlParts.join("");
  }

  function renderWelcomeModelCard() {
    const el = document.getElementById("welcome-model-card");
    if (!el || !state.appState) return;
    const compat = state.appState.compatibility || {};
    const chain = compat.provider_chain || {};
    const availSkills = compat.available_skills || [];

    el.innerHTML = `
      <span class="meta-chip accent">Modèle : ${esc(chain.model || "Auto")}</span>
      <span class="meta-chip">${availSkills.length} Skills prêts</span>
      <button class="composer-chip-btn" id="btn-welcome-change-model">Changer de modèle ▾</button>
    `;

    const btn = document.getElementById("btn-welcome-change-model");
    if (btn) {
      btn.addEventListener("click", () => openModal("modal-model-picker"));
    }
  }

  // -------------------------------------------------------------------------
  // 4. HUMAN APPROVAL BANNER
  // -------------------------------------------------------------------------
  function renderApprovalBanner() {
    const container = document.getElementById("approval-banner-container");
    if (!container || !state.appState) return;
    const approvals = state.appState.pending_approvals || [];
    if (approvals.length === 0) {
      container.innerHTML = "";
      return;
    }
    const item = approvals[0];
    container.innerHTML = `
      <div class="approval-banner" role="alert">
        <div>
          <strong>⚠️ Validation humaine requise (${esc(item.risk_level)})</strong>
          <div style="font-size: 12px;">${esc(item.message)}</div>
        </div>
        <div class="approval-actions">
          <button class="btn-approve" data-approve-id="${esc(item.id)}" data-decision="allow_once">Autoriser une fois</button>
          <button class="btn-approve" data-approve-id="${esc(item.id)}" data-decision="allow_task">Pour cette tâche</button>
          <button class="btn-approve" data-approve-id="${esc(item.id)}" data-decision="allow_always">Toujours</button>
          <button class="btn-deny" data-approve-id="${esc(item.id)}" data-decision="deny">Refuser</button>
        </div>
      </div>
    `;
  }

  // -------------------------------------------------------------------------
  // 5. COMPOSER ULTRA-ÉPURÉ & PALETTE SLASH COMMANDS (/)
  // -------------------------------------------------------------------------
  function getCanonicalSkills() {
    const compat = (state.appState && state.appState.compatibility) || {};
    const rawSkills = compat.skills && compat.skills.length ? compat.skills : CANONICAL_SKILLS_FALLBACK;
    return rawSkills.slice().sort((a, b) => {
      const ia = a.canonical_index || 99;
      const ib = b.canonical_index || 99;
      if (ia !== ib) return ia - ib;
      return String(a.name).localeCompare(String(b.name));
    });
  }

  function detectSlashTrigger(text, cursorPos) {
    const beforeCursor = String(text || "").slice(0, cursorPos);
    // Ne pas déclencher dans une URL (http://, https://, file://)
    if (/(?:https?|file):\/\/[^\s]*$/i.test(beforeCursor)) {
      return null;
    }
    // Déclencher uniquement si '/' est au tout début du champ ou précédé d'un espace/saut de ligne
    const match = beforeCursor.match(/(?:^|\s)(\/[a-zA-Z0-9_-]*)$/);
    if (!match) return null;

    const fullToken = match[1]; // ex: "/pla"
    const query = fullToken.slice(1).toLowerCase(); // ex: "pla"
    const tokenStart = beforeCursor.length - fullToken.length;
    const tokenEnd = cursorPos;
    return { query, tokenStart, tokenEnd };
  }

  function updateSlashPaletteFromInput() {
    const inputEl = document.getElementById("composer-input");
    const paletteEl = document.getElementById("slash-command-palette");
    if (!inputEl || !paletteEl) return;

    const trigger = detectSlashTrigger(inputEl.value, inputEl.selectionStart || 0);
    if (!trigger) {
      closeSlashPalette();
      return;
    }

    const q = trigger.query;
    const allSkills = getCanonicalSkills();
    const filtered = allSkills.filter((sk) => {
      if (!q) return true;
      const name = String(sk.name || "").toLowerCase();
      const cmd = String(sk.slash_command || `/${name}`).toLowerCase();
      const disp = String(sk.display_name || "").toLowerCase();
      const desc = String(sk.description || "").toLowerCase();
      const aliases = Array.isArray(sk.aliases) ? sk.aliases.map((a) => String(a).toLowerCase()) : [];
      return (
        name.includes(q) ||
        cmd.includes(q) ||
        disp.includes(q) ||
        desc.includes(q) ||
        aliases.some((al) => al.includes(q))
      );
    });

    state.slashPalette.open = true;
    state.slashPalette.query = q;
    state.slashPalette.tokenStart = trigger.tokenStart;
    state.slashPalette.tokenEnd = trigger.tokenEnd;
    state.slashPalette.filteredSkills = filtered;
    if (state.slashPalette.selectedIndex >= filtered.length) {
      state.slashPalette.selectedIndex = 0;
    }

    renderSlashPalette();
  }

  function renderSlashPalette() {
    const paletteEl = document.getElementById("slash-command-palette");
    const listEl = document.getElementById("slash-palette-list");
    if (!paletteEl || !listEl) return;

    if (!state.slashPalette.open) {
      paletteEl.style.display = "none";
      return;
    }

    paletteEl.style.display = "flex";
    const items = state.slashPalette.filteredSkills;

    if (items.length === 0) {
      listEl.innerHTML = `
        <div class="slash-empty">
          Aucune commande ou skill ne correspond à <code>/${esc(state.slashPalette.query)}</code>.
        </div>
      `;
      return;
    }

    listEl.innerHTML = items
      .map((sk, idx) => {
        const isSel = idx === state.slashPalette.selectedIndex;
        const isCompat = sk.compatible !== false;
        const idxNum = sk.canonical_index || idx + 1;
        return `
          <div
            class="slash-item ${isSel ? "active" : ""} ${!isCompat ? "unavailable" : ""}"
            role="option"
            aria-selected="${isSel ? "true" : "false"}"
            data-slash-pick="${esc(sk.name)}"
            data-slash-idx="${idx}"
          >
            <div class="slash-item-left">
              <span class="slash-item-index">${idxNum}.</span>
              <span class="slash-item-cmd">/${esc(sk.name)}</span>
              <strong style="font-size: 12px;">${esc(sk.display_name)}</strong>
              <span class="slash-item-desc">${esc(sk.description)}</span>
            </div>
            <div class="slash-item-right">
              ${
                isCompat
                  ? `<span class="meta-chip success">✓ Prêt</span>`
                  : `<span class="meta-chip warning" title="${esc(sk.compatibility_reason || "Indisponible")}">○ Indisponible</span>`
              }
            </div>
          </div>
        `;
      })
      .join("");

    const activeRow = listEl.querySelector(".slash-item.active");
    if (activeRow && typeof activeRow.scrollIntoView === "function") {
      activeRow.scrollIntoView({ block: "nearest" });
    }
  }

  function closeSlashPalette() {
    state.slashPalette.open = false;
    const paletteEl = document.getElementById("slash-command-palette");
    if (paletteEl) {
      paletteEl.style.display = "none";
    }
  }

  async function selectSlashSkill(skillName) {
    const allSkills = getCanonicalSkills();
    const sk = allSkills.find((s) => s.name === skillName);
    if (!sk) {
      closeSlashPalette();
      return;
    }

    if (sk.compatible === false) {
      showStatusBanner(
        `Le skill /${sk.name} est indisponible avec le modèle actif : ${sk.compatibility_reason || "capacité requise manquante."}`,
        "warning"
      );
      closeSlashPalette();
      return;
    }

    const inputEl = document.getElementById("composer-input");
    if (inputEl) {
      const val = inputEl.value;
      const before = val.slice(0, state.slashPalette.tokenStart);
      const after = val.slice(state.slashPalette.tokenEnd).replace(/^\s+/, "");
      const replacement = `/${sk.name} `;
      inputEl.value = before + replacement + after;
      const newPos = (before + replacement).length;
      inputEl.focus();
      inputEl.setSelectionRange(newPos, newPos);
      inputEl.style.height = "auto";
      inputEl.style.height = `${Math.min(inputEl.scrollHeight, 180)}px`;
    }

    closeSlashPalette();

    try {
      await apiPost("/api/preferences", { skill_mode: "manual", active_skills: [sk.name] });
      await refreshFullState();
    } catch (_) {}
  }

  function showStatusBanner(message, level) {
    const banner = document.getElementById("voice-status-banner");
    if (!banner) return;
    if (!message) {
      banner.style.display = "none";
      banner.innerHTML = "";
      return;
    }
    banner.className = `voice-status-banner ${level === "error" ? "error" : ""}`;
    banner.style.display = "flex";
    banner.innerHTML = `
      <span>${esc(message)}</span>
      <button type="button" class="icon-btn-mini" id="btn-dismiss-status-banner">✕</button>
    `;
    const btn = document.getElementById("btn-dismiss-status-banner");
    if (btn) {
      btn.addEventListener("click", () => {
        banner.style.display = "none";
      });
    }
  }

  function renderComposerControls() {
    const s = state.appState;
    const compat = s.compatibility || {};
    const allSkills = getCanonicalSkills();
    const availSkills = compat.available_skills || allSkills.filter((k) => k.compatible !== false);
    const prefs = s.preferences || {};
    const activeSkills = prefs.active_skills || [];
    const currentSkill = activeSkills[0] || "auto";

    // Fichiers joints
    const attBar = document.getElementById("composer-attachments-bar");
    if (attBar) {
      if (state.attachedFiles.length === 0) {
        attBar.style.display = "none";
        attBar.innerHTML = "";
      } else {
        attBar.style.display = "flex";
        attBar.innerHTML = state.attachedFiles
          .map(
            (f) => `
            <span class="attachment-chip">
              📎 ${esc(f)}
              <button class="icon-btn-mini" data-remove-attachment="${esc(f)}" title="Retirer">✕</button>
            </span>
          `
          )
          .join("");
      }
    }

    // Sélecteur compact de Modèle
    const modelSel = document.getElementById("composer-model-select");
    if (modelSel) {
      const currentId = (s.model_selection && s.model_selection.selected_id) || "auto";
      const opts = [
        `<option value="auto" ${currentId === "auto" ? "selected" : ""}>Modèle : Auto</option>`,
        ...(s.models || []).map(
          (m) =>
            `<option value="${esc(m.id)}" ${currentId === m.id ? "selected" : ""}>${esc(m.display_name.split(" (")[0])} (${esc(m.status_label)})</option>`
        ),
      ];
      modelSel.innerHTML = opts.join("");
    }

    // Sélecteur compact de Skill dans l'ordre canonique
    const skillSel = document.getElementById("composer-skill-select");
    if (skillSel) {
      const skillOpts = [
        `<option value="auto" ${currentSkill === "auto" ? "selected" : ""}>Skill : Auto (${availSkills.length} prêts)</option>`,
        ...allSkills.map(
          (sk) =>
            `<option value="${esc(sk.name)}" ${currentSkill === sk.name ? "selected" : ""} ${sk.compatible === false ? "disabled" : ""}>${sk.canonical_index || ""}. /${esc(sk.name)} — ${esc(sk.display_name)}</option>`
        ),
      ];
      skillSel.innerHTML = skillOpts.join("");
    }

    // Sélecteur compact de Mode
    const modeSel = document.getElementById("composer-mode-select");
    if (modeSel && s.mode) {
      modeSel.value = s.mode.current;
    }
  }

  // =========================================================================
  // 6. DICTÉE AUDIO STYLE GPT (MICROPHONE + ONDE AUDIO RÉELLE + TRANSCRIPTION)
  // =========================================================================

  function formatDuration(ms) {
    const totalSec = Math.max(0, Math.floor(ms / 1000));
    const min = String(Math.floor(totalSec / 60)).padStart(2, "0");
    const sec = String(totalSec % 60).padStart(2, "0");
    return `${min}:${sec}`;
  }

  async function startVoiceDictation() {
    showStatusBanner("", "info");
    if (state.voice.active) {
      stopVoiceDictation(true);
      return;
    }

    if (!navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== "function") {
      showStatusBanner(
        "Votre navigateur ne donne pas accès au périphérique microphone (navigator.mediaDevices.getUserMedia indisponible).",
        "error"
      );
      return;
    }

    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;

    let stream = null;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
    } catch (err) {
      const name = (err && err.name) || "";
      if (name === "NotAllowedError" || name === "PermissionDeniedError") {
        showStatusBanner("Permission microphone refusée. Autorisez l'accès au micro dans votre navigateur.", "error");
      } else if (name === "NotFoundError" || name === "DevicesNotFoundError") {
        showStatusBanner("Aucun microphone détecté sur cet appareil.", "error");
      } else {
        showStatusBanner(`Impossible d'accéder au microphone : ${(err && err.message) || name}`, "error");
      }
      return;
    }

    const inputEl = document.getElementById("composer-input");
    state.voice.active = true;
    state.voice.cancelled = false;
    state.voice.stream = stream;
    state.voice.finalTranscript = "";
    state.voice.interimTranscript = "";
    state.voice.preExistingText = inputEl ? inputEl.value : "";
    state.voice.startedAt = Date.now();

    // Basculer le composer en mode barre vocale style GPT
    const voiceBar = document.getElementById("voice-dictation-bar");
    const micBtn = document.getElementById("btn-voice-dictate");
    const previewEl = document.getElementById("voice-live-preview");
    const timerEl = document.getElementById("voice-timer");
    if (voiceBar) voiceBar.style.display = "flex";
    if (inputEl) inputEl.style.display = "none";
    if (micBtn) micBtn.classList.add("recording");
    if (previewEl) previewEl.textContent = "Écoute en cours… Parlez maintenant.";
    if (timerEl) timerEl.textContent = "00:00";

    // Timer temps réel
    state.voice.timerInterval = setInterval(() => {
      const tEl = document.getElementById("voice-timer");
      if (tEl && state.voice.active) {
        tEl.textContent = formatDuration(Date.now() - state.voice.startedAt);
      }
    }, 250);

    // Web Audio API AnalyserNode pour onde audio 100 % réelle
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      const audioCtx = new AudioCtx();
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 128;
      analyser.smoothingTimeConstant = 0.75;
      source.connect(analyser);
      state.voice.audioCtx = audioCtx;
      state.voice.analyser = analyser;
      drawRealAudioWaveform();
    } catch (_) {}

    // Reconnaissance vocale réelle
    if (!SpeechRec) {
      if (previewEl) {
        previewEl.textContent = "Microphone actif (API SpeechRecognition absente sur ce navigateur).";
      }
      showStatusBanner(
        "Le flux audio du microphone est capté, mais ce navigateur n'expose pas Web SpeechRecognition pour la transcription locale.",
        "warning"
      );
      return;
    }

    try {
      const recognition = new SpeechRec();
      recognition.lang = "fr-FR";
      recognition.continuous = true;
      recognition.interimResults = true;

      recognition.onresult = (event) => {
        let interim = "";
        let finalChunk = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const res = event.results[i];
          if (res.isFinal) {
            finalChunk += res[0].transcript + " ";
          } else {
            interim += res[0].transcript;
          }
        }
        if (finalChunk) {
          state.voice.finalTranscript = (state.voice.finalTranscript + " " + finalChunk).trim();
        }
        state.voice.interimTranscript = interim.trim();
        const combined = [state.voice.finalTranscript, state.voice.interimTranscript].filter(Boolean).join(" ");
        if (previewEl) {
          previewEl.textContent = combined || "Écoute en cours…";
        }
      };

      recognition.onerror = (event) => {
        if (state.voice.cancelled) return;
        const errCode = event.error || "unknown";
        if (errCode === "not-allowed") {
          showStatusBanner("La reconnaissance vocale a été refusée par le navigateur.", "error");
        } else if (errCode === "network") {
          showStatusBanner("Erreur réseau du service de transcription vocale du navigateur.", "warning");
        } else if (errCode !== "aborted" && errCode !== "no-speech") {
          showStatusBanner(`Diagnostic transcription vocale : ${errCode}`, "warning");
        }
      };

      recognition.start();
      state.voice.recognition = recognition;
    } catch (err) {
      showStatusBanner(`Impossible de démarrer la transcription vocale : ${err.message}`, "error");
    }
  }

  function drawRealAudioWaveform() {
    const canvas = document.getElementById("voice-waveform-canvas");
    const analyser = state.voice.analyser;
    if (!canvas || !analyser || !state.voice.active) return;

    const ctx = canvas.getContext("2d");
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    function renderFrame() {
      if (!state.voice.active) return;
      state.voice.rafId = requestAnimationFrame(renderFrame);
      analyser.getByteFrequencyData(dataArray);

      const width = canvas.width;
      const height = canvas.height;
      ctx.clearRect(0, 0, width, height);

      const barCount = 36;
      const step = Math.max(1, Math.floor(bufferLength / barCount));
      const barWidth = 3.5;
      const gap = (width - barCount * barWidth) / (barCount - 1);
      const isDark = document.documentElement.getAttribute("data-theme") === "dark";
      ctx.fillStyle = isDark ? "#4F8CFF" : "#2563EB";

      for (let i = 0; i < barCount; i++) {
        const val = dataArray[i * step] || 0;
        const normalized = val / 255;
        const barHeight = Math.max(3, Math.round(normalized * (height - 4)));
        const x = i * (barWidth + gap);
        const y = Math.round((height - barHeight) / 2);
        ctx.beginPath();
        if (typeof ctx.roundRect === "function") {
          ctx.roundRect(x, y, barWidth, barHeight, 2);
        } else {
          ctx.rect(x, y, barWidth, barHeight);
        }
        ctx.fill();
      }
    }

    renderFrame();
  }

  function stopVoiceDictation(confirmTranscript) {
    if (!state.voice.active) return;
    state.voice.active = false;
    state.voice.cancelled = !confirmTranscript;

    if (state.voice.rafId) {
      cancelAnimationFrame(state.voice.rafId);
      state.voice.rafId = null;
    }
    if (state.voice.timerInterval) {
      clearInterval(state.voice.timerInterval);
      state.voice.timerInterval = null;
    }
    if (state.voice.recognition) {
      try {
        state.voice.recognition.stop();
      } catch (_) {}
      state.voice.recognition = null;
    }
    if (state.voice.stream) {
      try {
        state.voice.stream.getTracks().forEach((t) => t.stop());
      } catch (_) {}
      state.voice.stream = null;
    }
    if (state.voice.audioCtx) {
      try {
        state.voice.audioCtx.close();
      } catch (_) {}
      state.voice.audioCtx = null;
      state.voice.analyser = null;
    }

    const voiceBar = document.getElementById("voice-dictation-bar");
    const inputEl = document.getElementById("composer-input");
    const micBtn = document.getElementById("btn-voice-dictate");
    if (voiceBar) voiceBar.style.display = "none";
    if (micBtn) micBtn.classList.remove("recording");
    if (inputEl) {
      inputEl.style.display = "block";
      if (confirmTranscript) {
        const spoken = [state.voice.finalTranscript, state.voice.interimTranscript].filter(Boolean).join(" ").trim();
        if (spoken) {
          const prev = (state.voice.preExistingText || "").trim();
          inputEl.value = prev ? `${prev} ${spoken}` : spoken;
        } else {
          inputEl.value = state.voice.preExistingText || "";
          showStatusBanner("Aucune parole détectée pendant l'enregistrement.", "warning");
        }
      } else {
        inputEl.value = state.voice.preExistingText || "";
      }
      inputEl.style.height = "auto";
      inputEl.style.height = `${Math.min(inputEl.scrollHeight, 180)}px`;
      inputEl.focus();
    }
  }

  // =========================================================================
  // 7. PANNEAU LATÉRAL DROIT UNIFIÉ : APERÇU DOCUMENT (PDF / HTML) & INSPECTEUR
  // =========================================================================

  function switchRightPanelMode(mode) {
    state.rightPanelMode = mode === "document" ? "document" : "inspector";
    const inspectorAside = document.getElementById("right-inspector");
    const docContainer = document.getElementById("doc-preview-container");
    const techContainer = document.getElementById("inspector-tech-container");
    const btnBackToDoc = document.getElementById("btn-switch-to-doc");

    if (inspectorAside) {
      inspectorAside.classList.remove("collapsed");
      inspectorAside.classList.toggle("doc-mode", state.rightPanelMode === "document");
    }
    if (docContainer) {
      docContainer.style.display = state.rightPanelMode === "document" ? "flex" : "none";
    }
    if (techContainer) {
      techContainer.style.display = state.rightPanelMode === "inspector" ? "flex" : "none";
    }
    if (btnBackToDoc) {
      btnBackToDoc.style.display = state.activeDocument ? "inline-flex" : "none";
    }
  }

  async function openDocumentPreview(docSpec) {
    if (!docSpec || !docSpec.path) return;
    const cleanPath = String(docSpec.path).replace(/\\/g, "/");
    const lower = cleanPath.toLowerCase();
    const type =
      docSpec.type ||
      (lower.endsWith(".pdf") ? "pdf" : lower.endsWith(".html") || lower.endsWith(".htm") ? "html" : "tex");

    const docObj = {
      type,
      path: cleanPath,
      source_tex: docSpec.source_tex || (lower.endsWith(".tex") ? cleanPath : ""),
      page_count: docSpec.page_count || null,
      size_bytes: docSpec.size_bytes || null,
      viewMode: docSpec.viewMode || (type === "tex" ? "source" : "render"),
      zoom: 100,
      auto_repaired: Boolean(docSpec.auto_repaired),
      repair_notes: docSpec.repair_notes || [],
      error: docSpec.error || null,
      sourceContent: "",
    };

    state.activeDocument = docObj;
    switchRightPanelMode("document");

    if (type === "pdf") {
      try {
        const info = await apiGet(`/api/files/pdf-info?path=${encodeURIComponent(cleanPath)}`);
        docObj.page_count = info.page_count;
        docObj.size_bytes = info.size_bytes;
        if (info.source_tex) docObj.source_tex = info.source_tex;
      } catch (err) {
        docObj.error = `Impossible de charger le PDF (${cleanPath}) : ${err.message}`;
      }
    } else if (type === "html" || type === "tex") {
      try {
        const fileData = await apiGet(`/api/files/content?path=${encodeURIComponent(cleanPath)}`);
        docObj.sourceContent = fileData.content || "";
        docObj.size_bytes = fileData.size_bytes;
      } catch (err) {
        docObj.error = `Le fichier ${cleanPath} est introuvable ou illisible : ${err.message}`;
      }
    }

    renderDocumentPreviewPanel();
  }

  async function renderDocumentPreviewPanel() {
    const doc = state.activeDocument;
    if (!doc) return;

    const badgeEl = document.getElementById("doc-preview-badge");
    const nameEl = document.getElementById("doc-preview-filename");
    const metaEl = document.getElementById("doc-preview-meta");
    const noticeEl = document.getElementById("doc-preview-notice");
    const zoomControls = document.getElementById("doc-pdf-zoom-controls");
    const zoomLabel = document.getElementById("pdf-zoom-label");
    const btnRender = document.getElementById("btn-doc-view-render");
    const btnSource = document.getElementById("btn-doc-view-source");
    const btnRecompile = document.getElementById("btn-doc-recompile");
    const btnSaveSource = document.getElementById("btn-doc-save-source");
    const btnDownload = document.getElementById("btn-doc-download");
    const pdfFrame = document.getElementById("doc-pdf-frame");
    const htmlFrame = document.getElementById("doc-html-frame");
    const sourceWrap = document.getElementById("doc-source-wrap");
    const sourceEditor = document.getElementById("doc-source-editor");
    const errorBox = document.getElementById("doc-error-box");

    if (badgeEl) {
      badgeEl.textContent = doc.type === "pdf" ? "PDF · Tectonic" : doc.type === "html" ? "HTML · Sandbox" : "LaTeX · Source";
    }
    if (nameEl) {
      nameEl.textContent = doc.path;
      nameEl.title = doc.path;
    }

    const metaParts = [];
    if (doc.page_count) metaParts.push(`${doc.page_count} page${doc.page_count > 1 ? "s" : ""}`);
    if (doc.size_bytes) metaParts.push(`${doc.size_bytes} octets`);
    if (metaEl) metaEl.textContent = metaParts.join(" · ");

    if (btnDownload) {
      btnDownload.href = `/api/files/raw?path=${encodeURIComponent(doc.path)}&download=1`;
      btnDownload.setAttribute("download", doc.path.split("/").pop() || "document");
    }

    if (noticeEl) {
      if (doc.auto_repaired) {
        noticeEl.style.display = "block";
        noticeEl.textContent = `✓ Code LaTeX réparé automatiquement avant compilation Tectonic (${(doc.repair_notes || []).join(", ") || "préambule normalisé"}).`;
      } else {
        noticeEl.style.display = "none";
      }
    }

    if (btnRender && btnSource) {
      btnRender.classList.toggle("active", doc.viewMode === "render");
      btnSource.classList.toggle("active", doc.viewMode === "source");
      btnSource.textContent = doc.type === "pdf" || doc.type === "tex" ? "Source .tex" : "Code source";
      btnSource.style.display = doc.type === "pdf" && !doc.source_tex ? "none" : "inline-block";
    }

    if (zoomControls) {
      zoomControls.style.display = doc.type === "pdf" && doc.viewMode === "render" ? "inline-flex" : "none";
    }
    if (zoomLabel) {
      zoomLabel.textContent = `${doc.zoom}%`;
    }

    if (btnRecompile) {
      btnRecompile.style.display =
        (doc.type === "pdf" && doc.source_tex) || doc.type === "tex" ? "inline-flex" : "none";
    }
    if (btnSaveSource) {
      btnSaveSource.style.display = doc.type === "html" && doc.viewMode === "source" ? "inline-flex" : "none";
    }

    if (pdfFrame) pdfFrame.style.display = "none";
    if (htmlFrame) htmlFrame.style.display = "none";
    if (sourceWrap) sourceWrap.style.display = "none";
    if (errorBox) errorBox.style.display = "none";

    if (doc.error) {
      if (errorBox) {
        errorBox.style.display = "block";
        errorBox.innerHTML = `
          <strong>⚠️ Erreur d'aperçu ou de compilation</strong>
          <pre class="mono" style="margin-top: 8px; white-space: pre-wrap; font-size: 11.5px;">${esc(doc.error)}</pre>
        `;
      }
      if (doc.viewMode === "source" && sourceWrap && sourceEditor) {
        sourceWrap.style.display = "flex";
        sourceEditor.value = doc.sourceContent || "";
      }
      return;
    }

    if (doc.viewMode === "source") {
      const targetSourcePath = doc.type === "pdf" ? doc.source_tex : doc.path;
      if (targetSourcePath && !doc.sourceContent) {
        try {
          const data = await apiGet(`/api/files/content?path=${encodeURIComponent(targetSourcePath)}`);
          doc.sourceContent = data.content || "";
        } catch (err) {
          doc.sourceContent = `Erreur de lecture de ${targetSourcePath} : ${err.message}`;
        }
      }
      if (sourceWrap && sourceEditor) {
        sourceWrap.style.display = "flex";
        sourceEditor.value = doc.sourceContent || "";
      }
      return;
    }

    if (doc.type === "pdf" && pdfFrame) {
      pdfFrame.style.display = "block";
      pdfFrame.src = `/api/files/raw?path=${encodeURIComponent(doc.path)}&t=${Date.now()}#zoom=${doc.zoom}`;
    } else if (doc.type === "html" && htmlFrame) {
      htmlFrame.style.display = "block";
      htmlFrame.src = `/api/preview/workspace/${doc.path.split("/").map(encodeURIComponent).join("/")}?t=${Date.now()}`;
    }
  }

  async function compileLatexAndPreview(texPath, optionalContent) {
    const statusEl = document.getElementById("top-task-status");
    const dotEl = document.getElementById("top-task-dot");
    if (statusEl) statusEl.textContent = "Compilation Tectonic…";
    if (dotEl) dotEl.className = "status-dot running";

    try {
      const payload = { path: texPath };
      if (optionalContent !== undefined) payload.content = optionalContent;
      const res = await apiPost("/api/files/compile-latex", payload);
      await refreshFullState();
      await openDocumentPreview({
        type: "pdf",
        path: res.pdf_path,
        source_tex: res.source_tex || texPath,
        page_count: res.page_count,
        size_bytes: res.size_bytes,
        auto_repaired: res.auto_repaired,
        repair_notes: res.repair_notes,
        viewMode: "render",
      });
    } catch (err) {
      let existingSource = optionalContent || "";
      if (!existingSource) {
        try {
          const f = await apiGet(`/api/files/content?path=${encodeURIComponent(texPath)}`);
          existingSource = f.content || "";
        } catch (_) {}
      }
      state.activeDocument = {
        type: "tex",
        path: texPath,
        source_tex: texPath,
        viewMode: "source",
        zoom: 100,
        error: err.message,
        sourceContent: existingSource,
      };
      switchRightPanelMode("document");
      renderDocumentPreviewPanel();
    } finally {
      renderTopBar();
    }
  }

  // -------------------------------------------------------------------------
  // 8. RIGHT INSPECTOR TECHNIQUE
  // -------------------------------------------------------------------------
  function renderInspector() {
    const body = document.getElementById("inspector-body");
    if (!body || !state.appState) return;

    const btnBackToDoc = document.getElementById("btn-switch-to-doc");
    if (btnBackToDoc) {
      btnBackToDoc.style.display = state.activeDocument ? "inline-flex" : "none";
    }

    document.querySelectorAll(".inspector-tab").forEach((btn) => {
      btn.classList.toggle("active", btn.getAttribute("data-inspector-tab") === state.inspectorTab);
    });

    switch (state.inspectorTab) {
      case "model":
        body.innerHTML = renderInspectorModelTab();
        break;
      case "skills":
        body.innerHTML = renderInspectorSkillsTab();
        break;
      case "activity":
        body.innerHTML = renderInspectorActivityTab();
        break;
      case "context":
        body.innerHTML = renderInspectorContextTab();
        break;
      case "files":
        body.innerHTML = renderInspectorFilesTab();
        break;
      case "tools":
        body.innerHTML = renderInspectorToolsTab();
        break;
      case "memory":
        body.innerHTML = renderInspectorMemoryTab();
        break;
      case "rag":
        body.innerHTML = renderInspectorRagTab();
        break;
      default:
        body.innerHTML = renderInspectorModelTab();
    }
  }

  function renderInspectorModelTab() {
    const s = state.appState;
    const compat = s.compatibility || {};
    const model = compat.model;
    const chain = compat.provider_chain || {};
    const domains = compat.domain_capabilities || [];
    const avail = compat.available_skills || [];
    const unavail = compat.unavailable_skills || [];

    const capsObj = (model && model.capabilities) || {};
    const capRows = [
      ["Vision / Multimodal", capsObj.vision],
      ["Long Context", capsObj.long_context ? `Oui (${capsObj.context} tokens)` : false],
      ["Function Calling (Tools)", capsObj.tools],
      ["Structured Output (JSON)", capsObj.structured_output],
      ["Google Search Grounding", capsObj.web_grounding],
      ["Streaming", capsObj.streaming],
      ["Raisonnement", capsObj.reasoning],
      ["Température configurable", capsObj.temperature],
    ];

    return `
      <div class="inspector-card">
        <div class="inspector-card-title">
          <span>Modèle actif</span>
          <span class="meta-chip accent">${esc(compat.selection_mode === "auto" ? "Auto" : "Manuel")}</span>
        </div>
        <div style="display: flex; flex-wrap: wrap; gap: 5px; margin-top: 4px;">
          <button class="skill-pill ${compat.selection_mode === "auto" ? "active" : ""}" data-select-model="auto">Auto</button>
          ${(s.models || [])
            .map(
              (m) => `
              <button
                class="skill-pill ${model && model.id === m.id && compat.selection_mode !== "auto" ? "active" : ""}"
                data-select-model="${esc(m.id)}"
              >
                ${esc(m.display_name.split(" (")[0])}
              </button>
            `
            )
            .join("")}
        </div>
      </div>

      <div class="inspector-card">
        <div class="inspector-card-title"><span>Chaîne Provider → Modèle → Capabilities</span></div>
        <div class="hierarchy-tree">
          <div class="hierarchy-node">
            <div style="color:var(--text-muted); font-size:10.5px;">PROVIDER</div>
            <strong>${esc(chain.provider_class || "ModelRouter")} (${esc(chain.provider || "auto")})</strong>
          </div>
          <div class="hierarchy-arrow">↓</div>
          <div class="hierarchy-node">
            <div style="color:var(--text-muted); font-size:10.5px;">MODÈLE</div>
            <strong>${esc(model ? model.display_name : "Auto")}</strong>
            <div style="font-size:11px; color:var(--text-secondary); margin-top:2px;">
              ${esc(model ? model.status_detail : "Sélection automatique par tâche")}
            </div>
          </div>
          <div class="hierarchy-arrow">↓</div>
          <div class="hierarchy-node">
            <div style="color:var(--text-muted); font-size:10.5px; margin-bottom:4px;">CAPACITÉS RÉELLES</div>
            ${capRows
              .map(
                ([label, val]) => `
                <div class="inspector-kv">
                  <span class="k">${esc(label)}</span>
                  <span class="v" style="color:${val ? "var(--success)" : "var(--text-muted)"};">
                    ${val === true ? "✓ Oui" : val ? `✓ ${esc(val)}` : "○ Non"}
                  </span>
                </div>
              `
              )
              .join("")}
          </div>
        </div>
      </div>

      <div class="inspector-card">
        <div class="inspector-card-title">
          <span>Domaines fonctionnels (${avail.length} Skills prêts)</span>
        </div>
        ${domains
          .map(
            (d) => `
            <div class="inspector-kv" title="${esc(d.reason)}">
              <span class="k">${d.available ? "✓" : "○"} ${esc(d.label)}</span>
              <span class="v" style="color:${d.available ? "var(--success)" : "var(--warning)"};">${esc(d.backing_skill)}</span>
            </div>
          `
          )
          .join("")}
      </div>

      ${
        unavail.length > 0
          ? `
          <div class="inspector-card">
            <div class="inspector-card-title"><span>Skills indisponibles (${unavail.length})</span></div>
            ${unavail
              .map(
                (sk) => `
                <div style="padding:4px 0; font-size:11.5px;">
                  <strong>○ /${esc(sk.name)}</strong> — <span style="color:var(--warning);">${esc(sk.compatibility_reason)}</span>
                </div>
              `
              )
              .join("")}
          </div>
        `
          : ""
      }
    `;
  }

  function renderInspectorSkillsTab() {
    const s = state.appState;
    const skills = getCanonicalSkills();
    const activeSkills = (s.preferences && s.preferences.active_skills) || [];
    const isAuto = activeSkills.length === 0;

    return `
      <div class="inspector-card">
        <div class="inspector-card-title">
          <span>Sélection des Skills (${skills.length})</span>
          <button class="skill-pill ${isAuto ? "active" : ""}" data-composer-skill="auto">
            ${isAuto ? "✓ Mode Auto" : "Passer en Auto"}
          </button>
        </div>
      </div>

      ${skills
        .map((sk, idx) => {
          const isSelected = activeSkills.includes(sk.name);
          const num = sk.canonical_index || idx + 1;
          return `
            <details class="compact-row-details" style="${!sk.compatible ? "opacity:0.6;" : ""}">
              <summary>
                <span>
                  <span class="mono" style="font-size:10.5px; color:var(--text-muted);">${num}.</span>
                  <strong style="color:${sk.compatible ? "var(--success)" : "var(--warning)"};">${sk.compatible ? "✓" : "○"}</strong>
                  <strong>${esc(sk.display_name)}</strong>
                  <code class="mono" style="font-size:11px; color:var(--text-secondary);">/${esc(sk.name)}</code>
                </span>
                <button
                  class="skill-pill ${isSelected ? "active" : ""}"
                  data-composer-skill="${esc(sk.name)}"
                  ${!sk.compatible ? "disabled" : ""}
                >
                  ${isSelected ? "Actif" : sk.compatible ? "Choisir" : "Indisponible"}
                </button>
              </summary>
              <div style="margin-top:6px; padding-top:6px; border-top:1px solid var(--border-subtle); font-size:11.5px; color:var(--text-secondary);">
                <div>${esc(sk.description)}</div>
                <div class="inspector-kv"><span class="k">Agent</span><span class="v">${esc(sk.agent_name || "—")}</span></div>
                <div class="inspector-kv"><span class="k">Outils</span><span class="v">${esc((sk.required_tools || []).join(", ") || "aucun")}</span></div>
                <div style="color:${sk.compatible ? "var(--text-muted)" : "var(--warning)"}; margin-top:2px;">${esc(sk.compatibility_reason || "")}</div>
              </div>
            </details>
          `;
        })
        .join("")}
    `;
  }

  function renderInspectorActivityTab() {
    const s = state.appState;
    const events = (s.events || []).slice().reverse();
    const isDev = Boolean(s.preferences && s.preferences.developer_mode);

    return `
      <div class="inspector-card">
        <div class="inspector-card-title">
          <span>Événements temps réel (${events.length})</span>
          <button id="btn-toggle-devmode" class="skill-pill ${isDev ? "active" : ""}">
            ${isDev ? "● Mode Dev actif" : "○ Mode Dev"}
          </button>
        </div>
        <div style="font-size:11px; color:var(--text-secondary);">
          Flux réel du <code>NormalizedEventBus</code>. Aucune étape n'est simulée.
        </div>
      </div>

      ${
        isDev
          ? `
          <div class="inspector-card" style="overflow-x:auto;">
            <div class="inspector-card-title"><span>Télémétrie Developer Mode</span></div>
            <table class="telemetry-table">
              <thead>
                <tr>
                  <th>Event</th>
                  <th>Agent</th>
                  <th>Outil</th>
                  <th>Durée</th>
                </tr>
              </thead>
              <tbody>
                ${
                  events.length === 0
                    ? `<tr><td colspan="4">Aucun événement.</td></tr>`
                    : events
                        .map(
                          (e) => `
                        <tr>
                          <td><span class="meta-chip accent">${esc(e.event)}</span></td>
                          <td>${esc(e.agent || "—")}</td>
                          <td>${esc(e.tool || "—")}</td>
                          <td>${e.duration_ms ? `${e.duration_ms}ms` : "—"}</td>
                        </tr>
                      `
                        )
                        .join("")
                }
              </tbody>
            </table>
          </div>
        `
          : ""
      }

      <div style="display:flex; flex-direction:column; gap:6px;">
        ${
          events.length === 0
            ? `<div class="inspector-card">Aucune activité enregistrée.</div>`
            : events
                .map(
                  (e) => `
                  <div class="inspector-card">
                    <div class="inspector-card-title">
                      <span class="meta-chip accent">${esc(e.event)}</span>
                      <span class="mono" style="font-size:10.5px; color:var(--text-muted);">${esc((e.timestamp || "").slice(11, 19))}</span>
                    </div>
                    <div style="font-size:11.5px;">${esc(e.summary)}</div>
                  </div>
                `
                )
                .join("")
        }
      </div>
    `;
  }

  function renderInspectorContextTab() {
    const s = state.appState;
    const ctx = s.context || {};
    const mm = ctx.mission_memory;

    return `
      <div class="inspector-card">
        <div class="inspector-card-title"><span>Contexte de Session</span></div>
        <div class="inspector-kv"><span class="k">Historique</span><span class="v">${esc(ctx.history_entries)} entrées (${esc(ctx.history_characters)} car.)</span></div>
        <div class="inspector-kv"><span class="k">Dernier Skill</span><span class="v">${esc(ctx.last_skill)}</span></div>
        <div class="inspector-kv"><span class="k">Fichiers suivis</span><span class="v">${esc((ctx.tracked_files || []).length)}</span></div>
      </div>

      <div class="inspector-card">
        <div class="inspector-card-title"><span>Dernière Mission</span></div>
        ${
          !mm
            ? `<div style="font-size:11.5px; color:var(--text-secondary);">Aucune mission exécutée dans cette session.</div>`
            : `
              <div class="inspector-kv"><span class="k">Intention</span><span class="v">${esc(mm.intent)}</span></div>
              <div class="inspector-kv"><span class="k">Statut</span><span class="v">${esc(mm.status)}</span></div>
              <div class="inspector-kv"><span class="k">Agents</span><span class="v">${esc((mm.agents || []).join(", ") || "—")}</span></div>
            `
        }
      </div>
    `;
  }

  function renderInspectorFilesTab() {
    const ws = (state.appState && state.appState.workspace) || { files: [], changes: [] };
    const files = ws.files || [];
    const changes = ws.changes || [];

    return `
      <div class="inspector-card">
        <div class="inspector-card-title">
          <span>Fichiers du Workspace (${files.length})</span>
          <span class="mono" style="font-size:10px; color:var(--text-muted);">workspace/</span>
        </div>
        <div style="display:flex; flex-direction:column; gap:3px; max-height:240px; overflow-y:auto;">
          ${
            files.length === 0
              ? `<div style="font-size:11.5px; color:var(--text-secondary);">Aucun fichier dans workspace/.</div>`
              : files
                  .map((f) => {
                    const lower = String(f.path || "").toLowerCase();
                    const isPdf = lower.endsWith(".pdf");
                    const isHtml = lower.endsWith(".html") || lower.endsWith(".htm");
                    const isTex = lower.endsWith(".tex");
                    return `
                      <div class="sidebar-item" style="padding:4px 6px;">
                        <div class="sidebar-item-main" data-preview-file="${esc(f.path)}">
                          <span class="sidebar-item-title mono" style="font-size:11.5px;">${esc(f.path)}</span>
                          ${f.status ? `<span class="meta-chip accent">${esc(f.status)}</span>` : ""}
                        </div>
                        <div style="display:flex; gap:4px;">
                          ${
                            isPdf
                              ? `<button class="icon-btn-mini" data-open-doc-preview="pdf" data-doc-path="${esc(f.path)}" title="Aperçu PDF">📄 PDF</button>`
                              : isHtml
                              ? `<button class="icon-btn-mini" data-open-doc-preview="html" data-doc-path="${esc(f.path)}" title="Aperçu HTML">🌐 HTML</button>`
                              : isTex
                              ? `<button class="icon-btn-mini" data-compile-tex-path="${esc(f.path)}" title="Compiler avec Tectonic">⚡ PDF</button>`
                              : ""
                          }
                          <button class="icon-btn-mini" data-attach-ws-file="${esc(f.path)}" title="Joindre au message">+ Joindre</button>
                          <button class="icon-btn-mini" data-preview-file="${esc(f.path)}" title="Lire">Lire</button>
                        </div>
                      </div>
                    `;
                  })
                  .join("")
          }
        </div>
      </div>

      ${
        state.selectedFilePreview
          ? `
          <div class="inspector-card">
            <div class="inspector-card-title">
              <span class="mono">${esc(state.selectedFilePreview.path)}</span>
              <button class="icon-btn-mini" id="btn-close-file-preview">✕</button>
            </div>
            <pre class="diff-box">${esc(state.selectedFilePreview.content)}</pre>
          </div>
        `
          : ""
      }

      <div class="inspector-card">
        <div class="inspector-card-title"><span>Diffs enregistrés (${changes.length})</span></div>
        ${
          changes.length === 0
            ? `<div style="font-size:11.5px; color:var(--text-secondary);">Aucune modification de fichier dans cette session.</div>`
            : changes
                .map(
                  (ch) => `
                  <div style="border-top:1px solid var(--border-subtle); padding-top:6px; margin-top:4px;">
                    <div class="inspector-kv">
                      <span class="k"><strong class="mono">[${esc(ch.status)}] ${esc(ch.path)}</strong></span>
                      <span class="v"><span style="color:var(--success);">+${ch.added_lines}</span> / <span style="color:var(--error);">-${ch.removed_lines}</span></span>
                    </div>
                    <div class="diff-box">${formatUnifiedDiff(ch.diff)}</div>
                  </div>
                `
                )
                .join("")
        }
      </div>
    `;
  }

  function formatUnifiedDiff(diffText) {
    if (!diffText) return "<div class='diff-line'>Aucun diff textuel.</div>";
    return diffText
      .split("\n")
      .map((line) => {
        let cls = "";
        if (line.startsWith("+") && !line.startsWith("+++")) cls = "add";
        else if (line.startsWith("-") && !line.startsWith("---")) cls = "del";
        else if (line.startsWith("@@") || line.startsWith("---") || line.startsWith("+++")) cls = "hdr";
        return `<div class="diff-line ${cls}">${esc(line)}</div>`;
      })
      .join("");
  }

  function renderInspectorToolsTab() {
    const tools = (state.appState && state.appState.tools) || [];
    return `
      <div class="inspector-card">
        <div class="inspector-card-title">
          <span>Outils enregistrés (${tools.length})</span>
          <span class="meta-chip">ToolRegistry</span>
        </div>
        <div style="font-size:11px; color:var(--text-secondary);">
          Cliquez sur un outil pour voir ses permissions et paramètres.
        </div>
      </div>
      ${tools
        .map(
          (t) => `
          <details class="compact-row-details">
            <summary>
              <span class="mono">🔧 ${esc(t.name)}</span>
              <span class="meta-chip ${t.mutates ? "warning" : "success"}">${esc(t.risk_level)}</span>
            </summary>
            <div style="margin-top:6px; padding-top:6px; border-top:1px solid var(--border-subtle); font-size:11.5px; color:var(--text-secondary);">
              <div>${esc(t.description)}</div>
              <div class="inspector-kv"><span class="k">Modifie le disque</span><span class="v">${t.mutates ? "Oui" : "Non (Lecture seule)"}</span></div>
              <div class="inspector-kv"><span class="k">Timeout</span><span class="v">${esc(t.timeout)}s</span></div>
            </div>
          </details>
        `
        )
        .join("")}
    `;
  }

  function renderInspectorMemoryTab() {
    const mem = (state.appState && state.appState.memory) || {};
    const sessionNotes = mem.session || [];
    const projNotes = mem.project || [];
    const decisions = mem.decisions || [];
    const prefs = mem.preferences || {};

    return `
      <div class="inspector-card">
        <div class="inspector-card-title"><span>Mémoriser une note</span></div>
        <div style="display:flex; gap:6px; flex-wrap:wrap;">
          <select id="mem-scope-select" class="composer-select">
            <option value="session">Session</option>
            <option value="decision">Décision</option>
            <option value="preference">Préférence (clé=valeur)</option>
            <option value="project">Projet (.harness)</option>
          </select>
          <input id="mem-value-input" type="text" class="sidebar-search" style="flex:1;" placeholder="Note ou clé=valeur…" />
          <button id="btn-add-memory" class="send-btn">Ajouter</button>
        </div>
      </div>

      <div class="inspector-card">
        <div class="inspector-card-title">
          <span>Session (${sessionNotes.length})</span>
          <button id="btn-clear-session-mem" class="msg-action-btn" style="opacity:1;">Effacer</button>
        </div>
        ${
          sessionNotes.length === 0
            ? `<div style="font-size:11.5px; color:var(--text-secondary);">Aucune note de session.</div>`
            : sessionNotes.map((n) => `<div style="font-size:11.5px;">• ${esc(n)}</div>`).join("")
        }
      </div>

      <div class="inspector-card">
        <div class="inspector-card-title"><span>Projet (${projNotes.length}) & Décisions (${decisions.length})</span></div>
        ${projNotes.map((n) => `<div style="font-size:11.5px;">📁 ${esc(n)}</div>`).join("")}
        ${decisions.map((d) => `<div style="font-size:11.5px;">✓ ${esc(d)}</div>`).join("")}
        ${Object.entries(prefs)
          .map(([k, v]) => `<div class="inspector-kv"><span class="k">${esc(k)}</span><span class="v">${esc(v)}</span></div>`)
          .join("")}
        ${
          projNotes.length === 0 && decisions.length === 0 && Object.keys(prefs).length === 0
            ? `<div style="font-size:11.5px; color:var(--text-secondary);">Aucune entrée persistée.</div>`
            : ""
        }
      </div>
    `;
  }

  function renderInspectorRagTab() {
    const rag = (state.appState && state.appState.rag) || {};
    const collections = rag.collections || [];
    const results = rag.search_results || [];
    const emb = rag.embeddings || {};

    return `
      <div class="inspector-card">
        <div class="inspector-card-title">
          <span>RAG Documentaire & Lexical</span>
          <span class="meta-chip success">Actif</span>
        </div>
        <div class="inspector-kv">
          <span class="k">Embeddings vectoriels</span>
          <span class="v" style="color:var(--text-muted);">${esc(emb.status || "Non configuré")}</span>
        </div>
        <div style="font-size:11px; color:var(--text-secondary);">${esc(emb.detail)}</div>
      </div>

      <div class="inspector-card">
        <div class="inspector-card-title"><span>Recherche locale (RAG & Workspace)</span></div>
        <div style="display:flex; gap:6px;">
          <input
            id="rag-search-input"
            type="search"
            class="sidebar-search"
            style="flex:1;"
            value="${esc(rag.search_query || "")}"
            placeholder="Rechercher un terme…"
          />
          <button id="btn-run-rag-search" class="send-btn">Chercher</button>
        </div>
        ${
          results.length > 0
            ? `<div style="display:flex; flex-direction:column; gap:5px; margin-top:6px;">
                ${results
                  .map(
                    (r) => `
                  <div style="padding:5px; background:var(--bg-primary); border-radius:5px; font-size:11px;">
                    <div class="mono" style="color:var(--accent);">${esc(r.source)}:${esc(r.line)}</div>
                    <div>${esc(r.snippet)}</div>
                  </div>
                `
                  )
                  .join("")}
               </div>`
            : ""
        }
      </div>

      <div class="inspector-card">
        <div class="inspector-card-title"><span>Collections (${collections.length})</span></div>
        ${collections
          .map(
            (c) => `
            <div class="inspector-kv">
              <span class="k">${esc(c.name)}</span>
              <span class="v">${c.rag_count} doc · ${c.templates_count} tpl</span>
            </div>
          `
          )
          .join("")}
      </div>
    `;
  }

  // =========================================================================
  // MODALS
  // =========================================================================

  function openModal(id) {
    const el = document.getElementById(id);
    if (!el) return;
    if (id === "modal-model-picker") renderModelPickerModal();
    if (id === "modal-settings") renderSettingsModal();
    if (id === "modal-global-search") {
      runGlobalSearch("");
      setTimeout(() => {
        const inp = document.getElementById("global-search-input");
        if (inp) inp.focus();
      }, 40);
    }
    el.classList.add("open");
  }

  function closeModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove("open");
  }

  function renderModelPickerModal() {
    const body = document.getElementById("modal-model-body");
    if (!body || !state.appState) return;
    const s = state.appState;
    const currentId = (s.model_selection && s.model_selection.selected_id) || "auto";

    body.innerHTML = `
      <div class="inspector-card" style="border-color: ${currentId === "auto" ? "var(--accent)" : "var(--border-color)"};">
        <div class="inspector-card-title">
          <div>
            <strong>⚡ Auto (ModelRouter Intelligent)</strong>
            <span class="meta-chip accent" style="margin-left:6px;">Recommandé</span>
          </div>
          <button class="send-btn" data-pick-model="auto">
            ${currentId === "auto" ? "✓ Actif" : "Choisir Auto"}
          </button>
        </div>
        <div style="font-size:12px; color:var(--text-secondary);">
          Route automatiquement chaque tâche vers le modèle optimal disponible.
        </div>
      </div>

      ${(s.models || [])
        .map((m) => {
          const isSel = currentId === m.id;
          const caps = m.capability_labels || [];
          return `
            <div class="inspector-card" style="border-color: ${isSel ? "var(--accent)" : "var(--border-color)"};">
              <div class="inspector-card-title">
                <div style="display:flex; align-items:center; gap:6px;">
                  <span class="${m.connected ? "status-dot" : "status-dot warning"}"></span>
                  <strong>${esc(m.display_name)}</strong>
                  <span class="meta-chip">${esc(m.status_label)}</span>
                </div>
                <button class="send-btn" data-pick-model="${esc(m.id)}">
                  ${isSel ? "✓ Sélectionné" : "Choisir"}
                </button>
              </div>
              <div style="font-size:11.5px; color:var(--text-secondary);">${esc(m.status_detail)}</div>
              <div style="display:flex; flex-wrap:wrap; gap:4px; margin-top:2px;">
                <span class="meta-chip">Contexte : ${esc(m.capabilities.context)}</span>
                ${caps.map((c) => `<span class="meta-chip accent">${esc(c)}</span>`).join("")}
              </div>
            </div>
          `;
        })
        .join("")}
    `;
  }

  async function runGlobalSearch(query) {
    const resContainer = document.getElementById("global-search-results");
    if (!resContainer) return;
    try {
      const data = await apiGet(`/api/search?q=${encodeURIComponent(query || "")}`);
      const sections = [];

      if (data.models && data.models.length) {
        sections.push(`
          <div class="inspector-card">
            <div class="inspector-card-title"><span>Modèles (${data.models.length})</span></div>
            ${data.models
              .map(
                (m) => `
                <div class="sidebar-item" data-pick-model="${esc(m.id)}">
                  <span>🧠 ${esc(m.display_name)}</span>
                  <span class="meta-chip">${esc(m.status_label)}</span>
                </div>
              `
              )
              .join("")}
          </div>
        `);
      }

      if (data.skills && data.skills.length) {
        sections.push(`
          <div class="inspector-card">
            <div class="inspector-card-title"><span>Skills (${data.skills.length})</span></div>
            ${data.skills
              .map(
                (sk) => `
                <div class="sidebar-item" data-search-pick-skill="${esc(sk.name)}">
                  <span>${sk.compatible ? "✓" : "○"} <strong>/${esc(sk.name)}</strong> — ${esc(sk.description)}</span>
                  <span class="meta-chip">${esc(sk.agent_name)}</span>
                </div>
              `
              )
              .join("")}
          </div>
        `);
      }

      if (data.files && data.files.length) {
        sections.push(`
          <div class="inspector-card">
            <div class="inspector-card-title"><span>Fichiers Workspace (${data.files.length})</span></div>
            ${data.files
              .map(
                (f) => `
                <div class="sidebar-item" data-preview-file="${esc(f.path)}">
                  <span class="mono">📄 ${esc(f.path)}</span>
                  <span class="meta-chip">${esc(f.size_bytes)} o</span>
                </div>
              `
              )
              .join("")}
          </div>
        `);
      }

      if (data.tools && data.tools.length) {
        sections.push(`
          <div class="inspector-card">
            <div class="inspector-card-title"><span>Outils (${data.tools.length})</span></div>
            ${data.tools
              .map(
                (t) => `
                <div class="sidebar-item" data-inspect-tool="${esc(t.name)}">
                  <span class="mono">🔧 ${esc(t.name)}</span>
                  <span class="meta-chip">${esc(t.risk_level)}</span>
                </div>
              `
              )
              .join("")}
          </div>
        `);
      }

      resContainer.innerHTML = sections.join("") || `<div class="inspector-card">Aucun résultat trouvé.</div>`;
    } catch (err) {
      resContainer.innerHTML = `<div class="inspector-card">Erreur : ${esc(err.message)}</div>`;
    }
  }

  function renderSettingsModal() {
    const body = document.getElementById("modal-settings-body");
    if (!body || !state.appState) return;
    const prefs = state.appState.preferences || {};
    const creds = state.appState.credentials || {};
    const eff = state.appState.model_selection && state.appState.model_selection.effective_model;
    const supportsTemp = !eff || (eff.capabilities && eff.capabilities.temperature);

    body.innerHTML = `
      <div class="creator-hero-card">
        <div class="creator-hero-badge">
          <span class="creator-hero-avatar">DB</span>
          <div class="creator-hero-text">
            <div class="creator-hero-title">NeoHarness AI — Agent Operating Environment</div>
            <div class="creator-hero-by">Conçu & développé par <strong>Djamel BENMAKHLOUF</strong></div>
            <div class="creator-hero-details">Orchestration multi-modèles de production, 18 Skills canoniques, recherche Web temps réel, compilation LaTeX Tectonic et interface ultra-raffinée — Zéro simulation.</div>
          </div>
        </div>
      </div>

      <div class="inspector-card">
        <div class="inspector-card-title"><span>Clés API des Providers (Session & .env local)</span></div>
        <div style="font-size:11.5px; color:var(--text-secondary); margin-bottom:6px;">
          Activées immédiatement et enregistrées dans <code>.env</code> (jamais réaffichées en clair).
        </div>
        <div class="inspector-kv" style="margin-top:4px;">
          <span class="k">Google Gemini (<code>GEMINI_API_KEY</code>) — ${creds.GEMINI_API_KEY ? "<strong style='color:var(--success);'>✓ Configurée</strong>" : "<span style='color:var(--warning);'>○ Absente</span>"}</span>
          <input id="settings-key-gemini" type="password" placeholder="${creds.GEMINI_API_KEY ? "•••••••• (conserver)" : "Clé AIza..."}" class="sidebar-search" style="width:220px;" autocomplete="off" />
        </div>
        <div class="inspector-kv" style="margin-top:4px;">
          <span class="k">OpenAI (<code>OPENAI_API_KEY</code>) — ${creds.OPENAI_API_KEY ? "<strong style='color:var(--success);'>✓ Configurée</strong>" : "<span style='color:var(--warning);'>○ Absente</span>"}</span>
          <input id="settings-key-openai" type="password" placeholder="${creds.OPENAI_API_KEY ? "•••••••• (conserver)" : "Clé sk-..."}" class="sidebar-search" style="width:220px;" autocomplete="off" />
        </div>
        <div class="inspector-kv" style="margin-top:4px;">
          <span class="k">Mistral AI (<code>MISTRAL_API_KEY</code>) — ${creds.MISTRAL_API_KEY ? "<strong style='color:var(--success);'>✓ Configurée</strong>" : "<span style='color:var(--warning);'>○ Absente</span>"}</span>
          <input id="settings-key-mistral" type="password" placeholder="${creds.MISTRAL_API_KEY ? "•••••••• (conserver)" : "Clé Mistral..."}" class="sidebar-search" style="width:220px;" autocomplete="off" />
        </div>
      </div>

      <div class="inspector-card">
        <div class="inspector-card-title"><span>Paramètres de génération & Télémétrie</span></div>
        <div class="inspector-kv" style="margin-top:4px;">
          <span class="k">Température (${supportsTemp ? "Supportée" : "Non supportée par ce modèle"})</span>
          <input id="settings-temp-input" type="number" step="0.1" min="0" max="1.5" value="${esc(prefs.temperature ?? 0.4)}" class="sidebar-search" style="width:90px;" ${!supportsTemp ? "disabled" : ""} />
        </div>
        <div class="inspector-kv" style="margin-top:4px;">
          <span class="k">Max Output Tokens (optionnel)</span>
          <input id="settings-tokens-input" type="number" step="128" min="128" max="32768" value="${esc(prefs.max_output_tokens || "")}" placeholder="Défaut" class="sidebar-search" style="width:120px;" />
        </div>
        <div class="inspector-kv" style="margin-top:4px;">
          <span class="k">Mode Développeur (Télémétrie complète dans l'Inspecteur)</span>
          <input id="settings-devmode-checkbox" type="checkbox" ${prefs.developer_mode ? "checked" : ""} />
        </div>
        <div style="display:flex; justify-content:flex-end; margin-top:8px;">
          <button id="btn-save-settings" class="send-btn">Enregistrer</button>
        </div>
      </div>
    `;
  }

  // =========================================================================
  // EXÉCUTION D'UNE REQUÊTE / MISSION
  // =========================================================================

  async function submitComposerTask(overridePrompt) {
    const inputEl = document.getElementById("composer-input");
    const promptText = overridePrompt !== undefined ? overridePrompt : inputEl ? inputEl.value : "";
    if (!promptText || !promptText.trim() || state.isExecuting) return;

    closeSlashPalette();
    showStatusBanner("", "info");

    state.isExecuting = true;
    state.streamingBuffer = "";

    const sendBtn = document.getElementById("btn-send-task");
    if (sendBtn) {
      sendBtn.disabled = true;
      sendBtn.innerHTML = "<span>Exécution…</span>";
    }
    const statusEl = document.getElementById("top-task-status");
    const dotEl = document.getElementById("top-task-dot");
    if (statusEl) statusEl.textContent = "Exécution…";
    if (dotEl) dotEl.className = "status-dot running";

    try {
      if (overridePrompt === undefined && inputEl) {
        inputEl.value = "";
        inputEl.style.height = "auto";
      }
      const attachments = [...state.attachedFiles];
      state.attachedFiles = [];

      const runData = await apiPost("/api/tasks/run", {
        prompt: promptText.trim(),
        attachments: attachments,
      });
      await refreshFullState();

      // Si un artefact PDF ou HTML vient d'être produit, ouvrir l'aperçu automatiquement
      const assistantMsg = (runData && (runData.assistant_message || runData.result)) || {};
      const artifacts =
        (runData && runData.preview_artifacts) ||
        assistantMsg.preview_artifacts ||
        assistantMsg.artifacts ||
        [];
      const previewArt = artifacts.find((a) => a.type === "pdf" || a.type === "html");
      if (previewArt) {
        await openDocumentPreview(previewArt);
      } else if (assistantMsg.content) {
        const exportMatch = String(assistantMsg.content).match(/\[EXPORT OK\]\s+([^\s|]+\.pdf)/i);
        if (exportMatch) {
          await openDocumentPreview({ type: "pdf", path: exportMatch[1].trim() });
        }
      }

      const scrollEl = document.getElementById("workspace-scroll");
      if (scrollEl) {
        scrollEl.scrollTop = scrollEl.scrollHeight;
      }
    } catch (err) {
      showStatusBanner(`Erreur lors de l'exécution : ${err.message}`, "error");
    } finally {
      state.isExecuting = false;
      state.streamingBuffer = "";
      const tempBubble = document.getElementById("streaming-assistant-card");
      if (tempBubble) tempBubble.remove();
      if (sendBtn) {
        sendBtn.disabled = false;
        sendBtn.innerHTML = "<span>Envoyer</span><span>↑</span>";
      }
      renderTopBar();
    }
  }

  // =========================================================================
  // ÉVÉNEMENTS DOM & INTERACTIONS
  // =========================================================================

  function setupEventListeners() {
    document.getElementById("btn-toggle-sidebar").addEventListener("click", () => {
      document.getElementById("left-sidebar").classList.toggle("collapsed");
    });
    document.getElementById("btn-toggle-inspector").addEventListener("click", () => {
      const rightEl = document.getElementById("right-inspector");
      if (rightEl.classList.contains("collapsed")) {
        switchRightPanelMode("inspector");
        renderInspector();
      } else {
        rightEl.classList.add("collapsed");
      }
    });
    const closeInspBtn = document.getElementById("btn-close-inspector");
    if (closeInspBtn) {
      closeInspBtn.addEventListener("click", () => {
        const rightEl = document.getElementById("right-inspector");
        rightEl.classList.add("collapsed");
        rightEl.classList.remove("doc-fullscreen");
      });
    }

    // Boutons de la barre d'aperçu de document (PDF / HTML)
    const btnCloseDoc = document.getElementById("btn-close-doc-preview");
    if (btnCloseDoc) {
      btnCloseDoc.addEventListener("click", () => {
        const rightEl = document.getElementById("right-inspector");
        rightEl.classList.add("collapsed");
        rightEl.classList.remove("doc-fullscreen");
      });
    }
    const btnSwitchToInsp = document.getElementById("btn-switch-to-inspector");
    if (btnSwitchToInsp) {
      btnSwitchToInsp.addEventListener("click", () => {
        switchRightPanelMode("inspector");
        renderInspector();
      });
    }
    const btnSwitchToDoc = document.getElementById("btn-switch-to-doc");
    if (btnSwitchToDoc) {
      btnSwitchToDoc.addEventListener("click", () => {
        if (state.activeDocument) {
          switchRightPanelMode("document");
          renderDocumentPreviewPanel();
        }
      });
    }
    const btnViewRender = document.getElementById("btn-doc-view-render");
    if (btnViewRender) {
      btnViewRender.addEventListener("click", () => {
        if (state.activeDocument) {
          state.activeDocument.viewMode = "render";
          renderDocumentPreviewPanel();
        }
      });
    }
    const btnViewSource = document.getElementById("btn-doc-view-source");
    if (btnViewSource) {
      btnViewSource.addEventListener("click", () => {
        if (state.activeDocument) {
          state.activeDocument.viewMode = "source";
          renderDocumentPreviewPanel();
        }
      });
    }
    const btnZoomOut = document.getElementById("btn-pdf-zoom-out");
    if (btnZoomOut) {
      btnZoomOut.addEventListener("click", () => {
        if (state.activeDocument && state.activeDocument.type === "pdf") {
          state.activeDocument.zoom = Math.max(50, (state.activeDocument.zoom || 100) - 25);
          renderDocumentPreviewPanel();
        }
      });
    }
    const btnZoomIn = document.getElementById("btn-pdf-zoom-in");
    if (btnZoomIn) {
      btnZoomIn.addEventListener("click", () => {
        if (state.activeDocument && state.activeDocument.type === "pdf") {
          state.activeDocument.zoom = Math.min(250, (state.activeDocument.zoom || 100) + 25);
          renderDocumentPreviewPanel();
        }
      });
    }
    const btnDocRefresh = document.getElementById("btn-doc-refresh");
    if (btnDocRefresh) {
      btnDocRefresh.addEventListener("click", () => {
        if (state.activeDocument) {
          openDocumentPreview({
            type: state.activeDocument.type,
            path: state.activeDocument.path,
            source_tex: state.activeDocument.source_tex,
            viewMode: state.activeDocument.viewMode,
          });
        }
      });
    }
    const btnDocFullscreen = document.getElementById("btn-doc-fullscreen");
    if (btnDocFullscreen) {
      btnDocFullscreen.addEventListener("click", () => {
        document.getElementById("right-inspector").classList.toggle("doc-fullscreen");
      });
    }
    const btnDocRecompile = document.getElementById("btn-doc-recompile");
    if (btnDocRecompile) {
      btnDocRecompile.addEventListener("click", async () => {
        const doc = state.activeDocument;
        if (!doc) return;
        const texPath = doc.source_tex || (doc.path.endsWith(".tex") ? doc.path : "");
        if (!texPath) return;
        const editor = document.getElementById("doc-source-editor");
        const newContent = doc.viewMode === "source" && editor ? editor.value : undefined;
        await compileLatexAndPreview(texPath, newContent);
      });
    }
    const btnDocSaveSource = document.getElementById("btn-doc-save-source");
    if (btnDocSaveSource) {
      btnDocSaveSource.addEventListener("click", async () => {
        const doc = state.activeDocument;
        const editor = document.getElementById("doc-source-editor");
        if (!doc || !editor) return;
        try {
          await apiPost("/api/files/write", { path: doc.path, content: editor.value });
          doc.sourceContent = editor.value;
          doc.viewMode = "render";
          await refreshFullState();
          renderDocumentPreviewPanel();
        } catch (err) {
          showStatusBanner(`Erreur d'enregistrement : ${err.message}`, "error");
        }
      });
    }

    // Dictée vocale style GPT
    const btnVoiceDictate = document.getElementById("btn-voice-dictate");
    if (btnVoiceDictate) {
      btnVoiceDictate.addEventListener("click", () => {
        startVoiceDictation();
      });
    }
    const btnVoiceCancel = document.getElementById("btn-voice-cancel");
    if (btnVoiceCancel) {
      btnVoiceCancel.addEventListener("click", () => {
        stopVoiceDictation(false);
      });
    }
    const btnVoiceConfirm = document.getElementById("btn-voice-confirm");
    if (btnVoiceConfirm) {
      btnVoiceConfirm.addEventListener("click", () => {
        stopVoiceDictation(true);
      });
    }

    document.getElementById("btn-new-task").addEventListener("click", async () => {
      await apiPost("/api/conversations/create", { title: "Nouvelle tâche" });
      await refreshFullState();
      document.getElementById("composer-input").focus();
    });
    document.getElementById("btn-brand-home").addEventListener("click", async () => {
      await apiPost("/api/conversations/create", { title: "Nouvelle tâche" });
      await refreshFullState();
    });

    document.getElementById("sidebar-filter-input").addEventListener("input", (e) => {
      state.sidebarFilter = e.target.value || "";
      renderSidebar();
    });

    document.getElementById("btn-open-model-picker").addEventListener("click", () => {
      openModal("modal-model-picker");
    });
    document.getElementById("btn-open-search").addEventListener("click", () => {
      openModal("modal-global-search");
    });
    document.getElementById("btn-toggle-theme").addEventListener("click", () => {
      const html = document.documentElement;
      const next = html.getAttribute("data-theme") === "light" ? "dark" : "light";
      applyTheme(next, true);
    });
    document.getElementById("btn-open-settings").addEventListener("click", () => {
      openModal("modal-settings");
    });

    // Composer : auto-resize, détection de `/` pour Slash Commands & envoi
    const composerInput = document.getElementById("composer-input");
    composerInput.addEventListener("input", () => {
      composerInput.style.height = "auto";
      composerInput.style.height = `${Math.min(composerInput.scrollHeight, 180)}px`;
      updateSlashPaletteFromInput();
    });
    composerInput.addEventListener("click", () => {
      updateSlashPaletteFromInput();
    });
    composerInput.addEventListener("keydown", (e) => {
      if (state.slashPalette.open) {
        const items = state.slashPalette.filteredSkills || [];
        if (e.key === "ArrowDown") {
          e.preventDefault();
          if (items.length > 0) {
            state.slashPalette.selectedIndex = (state.slashPalette.selectedIndex + 1) % items.length;
            renderSlashPalette();
          }
          return;
        }
        if (e.key === "ArrowUp") {
          e.preventDefault();
          if (items.length > 0) {
            state.slashPalette.selectedIndex =
              (state.slashPalette.selectedIndex - 1 + items.length) % items.length;
            renderSlashPalette();
          }
          return;
        }
        if ((e.key === "Enter" && !e.shiftKey) || e.key === "Tab") {
          if (items.length > 0) {
            e.preventDefault();
            const chosen = items[state.slashPalette.selectedIndex] || items[0];
            if (chosen) {
              selectSlashSkill(chosen.name);
            }
            return;
          }
        }
        if (e.key === "Escape") {
          e.preventDefault();
          closeSlashPalette();
          return;
        }
      }

      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        submitComposerTask();
      }
    });

    document.getElementById("btn-send-task").addEventListener("click", () => {
      submitComposerTask();
    });

    document.getElementById("composer-model-select").addEventListener("change", async (e) => {
      await apiPost("/api/models/select", { model: e.target.value });
      await refreshFullState();
    });
    document.getElementById("composer-skill-select").addEventListener("change", async (e) => {
      const val = e.target.value;
      if (val === "auto") {
        await apiPost("/api/preferences", { skill_mode: "auto", active_skills: [] });
      } else {
        await apiPost("/api/preferences", { skill_mode: "manual", active_skills: [val] });
      }
      await refreshFullState();
    });
    document.getElementById("composer-mode-select").addEventListener("change", async (e) => {
      await apiPost("/api/mode", { mode: e.target.value });
      await refreshFullState();
    });
    document.getElementById("btn-attach-file").addEventListener("click", () => {
      state.inspectorTab = "files";
      switchRightPanelMode("inspector");
      renderInspector();
    });

    document.getElementById("global-search-input").addEventListener("input", (e) => {
      runGlobalSearch(e.target.value || "");
    });

    // Fermeture de la palette `/` au clic extérieur
    document.addEventListener("mousedown", (e) => {
      if (state.slashPalette.open) {
        const box = document.getElementById("composer-box");
        if (box && !box.contains(e.target)) {
          closeSlashPalette();
        }
      }
    });

    document.body.addEventListener("click", async (e) => {
      const target = e.target.closest(
        "[data-slash-pick], [data-open-doc-preview], [data-compile-tex-path], [data-close-modal], [data-toggle-section], [data-inspector-tab], [data-open-inspector-tab], [data-select-model], [data-pick-model], [data-composer-skill], [data-search-pick-skill], [data-quick-prompt], [data-select-conv], [data-pin-conv], [data-rename-conv], [data-delete-conv], [data-approve-id], [data-preview-file], [data-attach-ws-file], [data-remove-attachment], [data-copy-msg], [data-edit-msg], [data-regen-msg], [data-show-msg-tools], [data-show-msg-sources], [data-export-last], [data-inspect-tool], #btn-close-file-preview, #btn-add-memory, #btn-clear-session-mem, #btn-run-rag-search, #btn-save-settings, #btn-toggle-devmode"
      );
      if (!target) return;

      if (target.hasAttribute("data-slash-pick")) {
        const skName = target.getAttribute("data-slash-pick");
        await selectSlashSkill(skName);
        return;
      }

      if (target.hasAttribute("data-open-doc-preview")) {
        const type = target.getAttribute("data-open-doc-preview");
        const path = target.getAttribute("data-doc-path");
        const sourceTex = target.getAttribute("data-doc-source") || "";
        const viewMode = target.getAttribute("data-doc-view") || (type === "tex" ? "source" : "render");
        await openDocumentPreview({
          type,
          path,
          source_tex: sourceTex,
          viewMode,
        });
        return;
      }

      if (target.hasAttribute("data-compile-tex-path")) {
        const texPath = target.getAttribute("data-compile-tex-path");
        await compileLatexAndPreview(texPath);
        return;
      }

      if (target.hasAttribute("data-close-modal")) {
        closeModal(target.getAttribute("data-close-modal"));
        return;
      }

      if (target.hasAttribute("data-toggle-section")) {
        const secId = target.getAttribute("data-toggle-section");
        const secEl = document.getElementById(secId);
        if (secEl) secEl.style.display = secEl.style.display === "none" ? "block" : "none";
        return;
      }

      if (target.hasAttribute("data-inspector-tab")) {
        state.inspectorTab = target.getAttribute("data-inspector-tab");
        switchRightPanelMode("inspector");
        renderInspector();
        return;
      }

      if (target.hasAttribute("data-open-inspector-tab")) {
        state.inspectorTab = target.getAttribute("data-open-inspector-tab");
        switchRightPanelMode("inspector");
        renderInspector();
        return;
      }

      if (target.hasAttribute("data-inspect-tool")) {
        closeModal("modal-global-search");
        state.inspectorTab = "tools";
        switchRightPanelMode("inspector");
        renderInspector();
        return;
      }

      if (target.id === "btn-toggle-devmode") {
        const curr = Boolean(state.appState && state.appState.preferences && state.appState.preferences.developer_mode);
        await apiPost("/api/preferences", { developer_mode: !curr });
        await refreshFullState();
        return;
      }

      if (target.hasAttribute("data-select-model") || target.hasAttribute("data-pick-model")) {
        const modelId = target.getAttribute("data-select-model") || target.getAttribute("data-pick-model");
        await apiPost("/api/models/select", { model: modelId });
        closeModal("modal-model-picker");
        closeModal("modal-global-search");
        await refreshFullState();
        return;
      }

      if (target.hasAttribute("data-composer-skill") || target.hasAttribute("data-search-pick-skill")) {
        const skName = target.getAttribute("data-composer-skill") || target.getAttribute("data-search-pick-skill");
        closeModal("modal-global-search");
        if (skName === "auto") {
          await apiPost("/api/preferences", { skill_mode: "auto", active_skills: [] });
        } else {
          const curr = (state.appState && state.appState.preferences && state.appState.preferences.active_skills) || [];
          const next = curr.includes(skName) ? [] : [skName];
          await apiPost("/api/preferences", {
            skill_mode: next.length ? "manual" : "auto",
            active_skills: next,
          });
        }
        await refreshFullState();
        return;
      }

      if (target.hasAttribute("data-quick-prompt")) {
        const qp = target.getAttribute("data-quick-prompt");
        submitComposerTask(qp);
        return;
      }

      if (target.hasAttribute("data-select-conv")) {
        await apiPost("/api/conversations/select", { id: target.getAttribute("data-select-conv") });
        await refreshFullState();
        return;
      }
      if (target.hasAttribute("data-pin-conv")) {
        e.stopPropagation();
        const cid = target.getAttribute("data-pin-conv");
        const pinned = target.getAttribute("data-pinned") !== "1";
        await apiPost("/api/conversations/update", { id: cid, pinned });
        await refreshFullState();
        return;
      }
      if (target.hasAttribute("data-rename-conv")) {
        e.stopPropagation();
        const cid = target.getAttribute("data-rename-conv");
        const oldTitle = target.getAttribute("data-title") || "";
        const newTitle = prompt("Nouveau titre :", oldTitle);
        if (newTitle && newTitle.trim()) {
          await apiPost("/api/conversations/update", { id: cid, title: newTitle.trim() });
          await refreshFullState();
        }
        return;
      }
      if (target.hasAttribute("data-delete-conv")) {
        e.stopPropagation();
        const cid = target.getAttribute("data-delete-conv");
        await apiPost("/api/conversations/delete", { id: cid });
        await refreshFullState();
        return;
      }

      if (target.hasAttribute("data-approve-id")) {
        const aid = target.getAttribute("data-approve-id");
        const dec = target.getAttribute("data-decision");
        await apiPost("/api/approvals/resolve", { id: aid, decision: dec });
        await refreshApprovals();
        return;
      }

      if (target.hasAttribute("data-preview-file")) {
        const fpath = target.getAttribute("data-preview-file");
        closeModal("modal-global-search");
        const lower = String(fpath || "").toLowerCase();
        if (lower.endsWith(".pdf")) {
          await openDocumentPreview({ type: "pdf", path: fpath });
          return;
        }
        if (lower.endsWith(".html") || lower.endsWith(".htm")) {
          await openDocumentPreview({ type: "html", path: fpath });
          return;
        }
        try {
          state.selectedFilePreview = await apiGet(`/api/files/content?path=${encodeURIComponent(fpath)}`);
          state.inspectorTab = "files";
          switchRightPanelMode("inspector");
          renderInspector();
        } catch (err) {
          showStatusBanner(`Impossible de lire ${fpath} : ${err.message}`, "error");
        }
        return;
      }
      if (target.id === "btn-close-file-preview") {
        state.selectedFilePreview = null;
        renderInspector();
        return;
      }

      if (target.hasAttribute("data-attach-ws-file")) {
        const fpath = target.getAttribute("data-attach-ws-file");
        if (!state.attachedFiles.includes(fpath)) {
          state.attachedFiles.push(fpath);
          renderComposerControls();
        }
        return;
      }
      if (target.hasAttribute("data-remove-attachment")) {
        const fpath = target.getAttribute("data-remove-attachment");
        state.attachedFiles = state.attachedFiles.filter((x) => x !== fpath);
        renderComposerControls();
        return;
      }

      const msgs = (state.appState && state.appState.active_conversation && state.appState.active_conversation.messages) || [];
      if (target.hasAttribute("data-copy-msg")) {
        const m = msgs[Number(target.getAttribute("data-copy-msg"))];
        if (m && navigator.clipboard) {
          navigator.clipboard.writeText(m.content || "");
        }
        return;
      }
      if (target.hasAttribute("data-edit-msg")) {
        const m = msgs[Number(target.getAttribute("data-edit-msg"))];
        if (m) {
          const inp = document.getElementById("composer-input");
          inp.value = m.content || "";
          inp.focus();
        }
        return;
      }
      if (target.hasAttribute("data-regen-msg")) {
        const idx = Number(target.getAttribute("data-regen-msg"));
        for (let i = idx - 1; i >= 0; i--) {
          if (msgs[i] && msgs[i].role === "user") {
            submitComposerTask(msgs[i].content);
            break;
          }
        }
        return;
      }
      if (target.hasAttribute("data-show-msg-tools")) {
        state.inspectorTab = "activity";
        switchRightPanelMode("inspector");
        renderInspector();
        return;
      }
      if (target.hasAttribute("data-show-msg-sources")) {
        state.inspectorTab = "rag";
        switchRightPanelMode("inspector");
        renderInspector();
        return;
      }
      if (target.hasAttribute("data-export-last")) {
        const fmt = target.getAttribute("data-export-last");
        submitComposerTask(`/export ${fmt}`);
        return;
      }

      if (target.id === "btn-add-memory") {
        const scope = document.getElementById("mem-scope-select").value;
        const val = document.getElementById("mem-value-input").value;
        if (!val || !val.trim()) return;
        try {
          await apiPost("/api/memory", { action: "remember", scope, value: val.trim() });
          await refreshFullState();
        } catch (err) {
          showStatusBanner(err.message, "error");
        }
        return;
      }
      if (target.id === "btn-clear-session-mem") {
        await apiPost("/api/memory", { action: "clear_session" });
        await refreshFullState();
        return;
      }

      if (target.id === "btn-run-rag-search") {
        const q = document.getElementById("rag-search-input").value || "";
        const ragData = await apiGet(`/api/rag?q=${encodeURIComponent(q)}`);
        state.appState.rag = ragData;
        renderInspector();
        return;
      }

      if (target.id === "btn-save-settings") {
        const keyGemini = document.getElementById("settings-key-gemini");
        const keyOpenai = document.getElementById("settings-key-openai");
        const keyMistral = document.getElementById("settings-key-mistral");
        const credPayload = {};
        if (keyGemini && keyGemini.value.trim()) credPayload.GEMINI_API_KEY = keyGemini.value.trim();
        if (keyOpenai && keyOpenai.value.trim()) credPayload.OPENAI_API_KEY = keyOpenai.value.trim();
        if (keyMistral && keyMistral.value.trim()) credPayload.MISTRAL_API_KEY = keyMistral.value.trim();
        if (Object.keys(credPayload).length > 0) {
          await apiPost("/api/credentials", credPayload);
        }

        const tempEl = document.getElementById("settings-temp-input");
        const tokEl = document.getElementById("settings-tokens-input");
        const devEl = document.getElementById("settings-devmode-checkbox");
        const payload = {};
        if (tempEl && !tempEl.disabled) payload.temperature = parseFloat(tempEl.value);
        if (tokEl) payload.max_output_tokens = tokEl.value ? parseInt(tokEl.value, 10) : null;
        if (devEl) payload.developer_mode = Boolean(devEl.checked);
        await apiPost("/api/preferences", payload);
        closeModal("modal-settings");
        await refreshFullState();
      }
    });

    // Raccourcis clavier globaux
    window.addEventListener("keydown", async (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        openModal("modal-global-search");
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "n") {
        e.preventDefault();
        await apiPost("/api/conversations/create", { title: "Nouvelle tâche" });
        await refreshFullState();
        document.getElementById("composer-input").focus();
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b") {
        e.preventDefault();
        document.getElementById("left-sidebar").classList.toggle("collapsed");
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "i") {
        e.preventDefault();
        document.getElementById("right-inspector").classList.toggle("collapsed");
      } else if (e.shiftKey && e.key === "Tab") {
        e.preventDefault();
        const order = ["EDIT", "PLAN", "ACCEPT", "AUTO"];
        const curr = (state.appState && state.appState.mode && state.appState.mode.current) || "AUTO";
        const next = order[(order.indexOf(curr) + 1) % order.length];
        await apiPost("/api/mode", { mode: next });
        await refreshFullState();
      } else if (e.key === "Escape") {
        if (state.voice.active) {
          stopVoiceDictation(false);
          return;
        }
        if (state.slashPalette.open) {
          closeSlashPalette();
          return;
        }
        closeModal("modal-model-picker");
        closeModal("modal-global-search");
        closeModal("modal-settings");
      }
    });

    setupPanelResizers();
  }

  function setupPanelResizers() {
    const leftResizer = document.getElementById("resizer-left");
    const rightResizer = document.getElementById("resizer-right");
    const sidebar = document.getElementById("left-sidebar");
    const inspector = document.getElementById("right-inspector");

    let activeSide = null;

    if (leftResizer) {
      leftResizer.addEventListener("mousedown", () => {
        activeSide = "left";
        leftResizer.classList.add("active");
      });
    }
    if (rightResizer) {
      rightResizer.addEventListener("mousedown", () => {
        activeSide = "right";
        rightResizer.classList.add("active");
      });
    }

    window.addEventListener("mousemove", (e) => {
      if (!activeSide) return;
      if (activeSide === "left") {
        const w = Math.max(200, Math.min(360, e.clientX));
        sidebar.classList.remove("collapsed");
        sidebar.style.width = `${w}px`;
      } else if (activeSide === "right") {
        const w = Math.max(300, Math.min(Math.floor(window.innerWidth * 0.65), window.innerWidth - e.clientX));
        inspector.classList.remove("collapsed");
        inspector.style.width = `${w}px`;
      }
    });

    window.addEventListener("mouseup", () => {
      if (activeSide) {
        activeSide = null;
        if (leftResizer) leftResizer.classList.remove("active");
        if (rightResizer) rightResizer.classList.remove("active");
      }
    });
  }

  window.addEventListener("DOMContentLoaded", async () => {
    initTheme();
    setupEventListeners();
    await refreshFullState();
    connectSSE();
  });
})();
