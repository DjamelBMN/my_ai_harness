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
    { canonical_index: 8, name: "dm", display_name: "DM", slash_command: "/dm", description: "Génère un devoir maison de mathématiques structuré en LaTeX Libertinus.", compatible: true, requires_mission: false, aliases: ["/devoir", "/devoir-maison"] },
    { canonical_index: 9, name: "exercice", display_name: "Exercice", slash_command: "/exercice", description: "Génère un exercice de mathématiques progressif avec corrigé détaillé.", compatible: true, requires_mission: false, aliases: ["/exo"] },
    { canonical_index: 10, name: "export", display_name: "Export", slash_command: "/export", description: "Exporte le dernier résultat en Markdown ou PDF dans workspace/exports/.", compatible: true, requires_mission: false, aliases: ["/save"] },
    { canonical_index: 11, name: "memory", display_name: "Memory", slash_command: "/memory", description: "Consulte ou enregistre des notes et décisions dans la mémoire persistante.", compatible: true, requires_mission: false, aliases: ["/mem"] },
    { canonical_index: 12, name: "mode", display_name: "Mode", slash_command: "/mode", description: "Consulte ou change le mode de gouvernance (EDIT, PLAN, ACCEPT, AUTO).", compatible: true, requires_mission: false, aliases: [] },
    { canonical_index: 13, name: "model", display_name: "Model", slash_command: "/model", description: "Consulte ou change le modèle IA actif.", compatible: true, requires_mission: false, aliases: ["/models"] },
    { canonical_index: 14, name: "plan", display_name: "Plan", slash_command: "/plan", description: "Construit le plan d'exécution détaillé d'une tâche sans modifier le disque.", compatible: true, requires_mission: true, aliases: [] },
    { canonical_index: 15, name: "refactor", display_name: "Refactor", slash_command: "/refactor", description: "Refactorise du code existant proprement en préservant les tests.", compatible: true, requires_mission: true, aliases: [] },
    { canonical_index: 16, name: "research", display_name: "Research", slash_command: "/research", description: "Effectue une recherche approfondie (Web et RAG) avec sources vérifiées.", compatible: true, requires_mission: true, aliases: ["/search", "/web"] },
    { canonical_index: 17, name: "review", display_name: "Review", slash_command: "/review", description: "Réalise une revue de code et de qualité sur les fichiers du workspace.", compatible: true, requires_mission: true, aliases: [] },
    { canonical_index: 18, name: "route", display_name: "Route", slash_command: "/route", description: "Analyse l'intention et route la mission vers le meilleur agent/modèle.", compatible: true, requires_mission: true, aliases: [] },
    { canonical_index: 19, name: "test", display_name: "Test", slash_command: "/test", description: "Exécute ou génère des tests unitaires et vérifie les résultats.", compatible: true, requires_mission: true, aliases: ["/tests"] },
    { canonical_index: 20, name: "workflow", display_name: "Workflow", slash_command: "/workflow", description: "Orchestre un workflow multi-étapes complet avec vérification finale.", compatible: true, requires_mission: true, aliases: [] },
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
    streamShown: 0,
    streamAnchored: false,
    streamRaf: null,
    sidebarAutoCollapsed: false,
    docWidth: 0,
    pdfDocCache: null,
    pdfRenderToken: 0,
    pdfWidth: 0,
    liveSteps: [],
    livePlan: [],
    liveBudget: {
      tokens_used: 0,
      tokens_limit: 100000,
      time_elapsed: 0,
      time_limit: 300,
      tool_calls: 0,
      tool_limit: 50,
    },
    liveCompile: null,
    liveSearch: null,
    lastEventSeq: 0,
    activityAutoScroll: true,
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
      const lastSeq = state.lastEventSeq || 0;
      const sseUrl = lastSeq > 0 ? `/api/events/stream?last_event_id=${lastSeq}` : "/api/events/stream";
      const es = new EventSource(sseUrl);
      es.onmessage = (evt) => {
        try {
          const parsed = JSON.parse(evt.data);
          if (evt.lastEventId) {
            state.lastEventSeq = parseInt(evt.lastEventId, 10) || state.lastEventSeq;
          } else if (parsed.seq) {
            state.lastEventSeq = Math.max(state.lastEventSeq || 0, parsed.seq);
          }
          if (!state.appState) return;

          if (parsed.event === "STREAM_DELTA") {
            const d = parsed.details || parsed.data || {};
            const delta = d.delta || "";
            if (delta && state.isExecuting) {
              finishThinkingSteps();
              // Nouveau tour du modèle (après un outil) : séparer les paragraphes
              if (state.streamingBuffer && d.accumulated === delta) state.streamingBuffer += "\n\n";
              state.streamingBuffer += delta;
              renderStreamingAssistantBubble();
            }
            return;
          }

          if (parsed.event === "ARTIFACT_READY" && (parsed.details || parsed.data)) {
            const art = parsed.details || parsed.data;
            if (art && art.path) {
              openDocumentPreview(art);
            }
          }

          handleLiveEvent(parsed);

          state.appState.events = state.appState.events || [];
          state.appState.events.push(parsed);
          if (state.appState.events.length > 500) {
            state.appState.events = state.appState.events.slice(-500);
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

  const LIVE_SKIP = new Set([
    "STREAM_DELTA", "TASK_STARTED", "TASK_COMPLETED", "CONTEXT_LOADING",
    "MEMORY_RETRIEVAL", "SKILL_DISCOVERY", "MODEL_SELECTED", "MODE_CHANGED",
  ]);

  function ensureStreamingCard() {
    const welcomeEl = document.getElementById("welcome-screen");
    const streamEl = document.getElementById("conversation-stream");
    if (!streamEl) return null;
    if (welcomeEl) welcomeEl.style.display = "none";
    streamEl.style.display = "flex";
    let card = document.getElementById("streaming-assistant-card");
    if (!card) {
      card = document.createElement("article");
      card.id = "streaming-assistant-card";
      card.className = "message-card assistant";
      card.innerHTML = `
        <div class="message-header">
          <div class="message-meta-badges">
            <strong>NeoHarness AI</strong>
            <span class="meta-chip accent">En direct</span>
          </div>
        </div>
        <details class="live-activity-tracker" id="live-activity" open style="display:none;">
          <summary id="live-activity-summary"></summary>
          <div class="live-activity-steps" id="live-activity-steps"></div>
        </details>
        <div class="message-body md-prose" id="streaming-body"></div>
      `;
      streamEl.appendChild(card);
    }
    return card;
  }

  function finishThinkingSteps() {
    let changed = false;
    state.liveSteps.forEach((s) => {
      if (s.kind === "think" && s.status === "running") {
        s.status = "done";
        changed = true;
      }
    });
    if (changed) renderLiveSteps();
  }

  function handleLiveEvent(e) {
    if (!e) return;
    const raw = e.raw_event || e.type || e.event || "";
    const data = e.data || e.details || {};

    if (raw === "plan.created" || e.event === "PLAN_CREATED") {
      state.livePlan = (data.plan_steps || data.steps || []).map((s, idx) => ({
        id: s.id || idx + 1,
        description: s.description || "",
        status: s.status || "pending",
      }));
    } else if (raw === "plan.step_started" || e.event === "PLAN_STEP") {
      const idx = data.step_index;
      if (idx && state.livePlan) {
        state.livePlan.forEach((s) => {
          if (s.id === idx) s.status = "in_progress";
        });
      }
    } else if (raw === "plan.step_completed") {
      const idx = data.step_index;
      if (idx && state.livePlan) {
        state.livePlan.forEach((s) => {
          if (s.id === idx) s.status = data.status || "completed";
        });
      }
    } else if (raw === "budget.update" || e.event === "BUDGET") {
      state.liveBudget = Object.assign({}, state.liveBudget, data);
    } else if (raw.startsWith("compile.") || e.event === "COMPILATION") {
      state.liveCompile = {
        event: raw,
        attempt: data.attempt || data.attempts || 1,
        max_attempts: data.max_attempts || 25,
        file: data.file || "",
        line: data.line,
        message: data.message || "",
        note: data.note || data.action || "",
        status: raw === "compile.error" ? "error" : raw === "compile.completed" ? "completed" : "running",
      };
    } else if (raw.startsWith("search.") || e.event === "SEARCH" || raw === "download.verified" || e.event === "DOWNLOAD") {
      state.liveSearch = state.liveSearch || { query: "", rejected: [], verified: null };
      if (raw === "search.query") {
        state.liveSearch.query = data.query || "";
      } else if (raw === "search.candidate_rejected") {
        state.liveSearch.rejected = state.liveSearch.rejected || [];
        state.liveSearch.rejected.push({
          url: data.url || "",
          reason: data.reason || "",
        });
      } else if (raw === "download.verified" || e.event === "DOWNLOAD") {
        state.liveSearch.verified = {
          destination: data.destination || "",
          size_bytes: data.size_bytes || 0,
          sha256: data.sha256 || "",
        };
      }
    }

    if (LIVE_SKIP.has(e.event)) return;
    const steps = state.liveSteps;
    if (e.event === "TOOL_RESULT") {
      for (let i = steps.length - 1; i >= 0; i--) {
        if (steps[i].tool === e.tool && steps[i].status === "running") {
          steps[i].status = e.status === "error" || e.status === "denied" ? "error" : "done";
          if (e.duration_ms) steps[i].detail = `${e.duration_ms} ms`;
          break;
        }
      }
    } else if (e.event === "TOOL_CALL") {
      finishThinkingSteps();
      steps.push({
        kind: "tool",
        tool: e.tool,
        label: `Outil : ${e.tool}`,
        detail: String((data && data.target) || "").slice(0, 90),
        status: "running",
      });
    } else if (e.raw_event === "agent.thinking") {
      finishThinkingSteps();
      steps.push({ kind: "think", label: "Réflexion…", detail: "", status: "running" });
    } else {
      finishThinkingSteps();
      steps.push({
        kind: "info",
        label: String(e.summary || e.event).slice(0, 90),
        detail: "",
        status: e.status === "error" ? "error" : "done",
      });
    }
    renderLiveSteps();
  }

  function renderLiveSteps() {
    ensureStreamingCard();
    const tracker = document.getElementById("live-activity");
    const box = document.getElementById("live-activity-steps");
    const sum = document.getElementById("live-activity-summary");
    if (!tracker || !box || !sum) return;
    const steps = state.liveSteps;
    tracker.style.display = steps.length ? "" : "none";
    const running = steps.some((s) => s.status === "running");
    const tools = steps.filter((s) => s.kind === "tool").length;
    sum.innerHTML = `<span>${running ? "En cours" : "Exécuté"} · ${tools} commande${tools > 1 ? "s" : ""} · ${steps.length} étape${steps.length > 1 ? "s" : ""}</span><span>▾</span>`;
    const marker = { done: "✓", running: "●", error: "✕" };
    box.innerHTML = steps
      .map(
        (s) => `
        <div class="activity-step-item">
          <div class="activity-step-left">
            <span class="step-marker ${s.status}">${marker[s.status] || "•"}</span>
            <span class="activity-step-label">${esc(s.label)}</span>
          </div>
          <span class="activity-step-detail">${esc(s.detail)}</span>
        </div>`
      )
      .join("");
    box.scrollTop = box.scrollHeight;
  }

  function paintStreamBody() {
    ensureStreamingCard();
    const body = document.getElementById("streaming-body");
    if (!body) return;
    const shown = state.streamingBuffer.slice(0, state.streamShown);
    body.innerHTML = `${shown ? formatAssistantContent(shown) : ""}<span class="streaming-cursor"></span>`;
    // Ancrage unique au premier mot : le lecteur lit depuis le début, sans être entraîné.
    if (shown && !state.streamAnchored) {
      state.streamAnchored = true;
      const card = document.getElementById("streaming-assistant-card");
      if (card) card.scrollIntoView({ block: "start", behavior: "smooth" });
    }
  }

  // Machine à écrire : la vitesse s'adapte au retard accumulé (fluide, jamais à la traîne)
  function kickTypewriter() {
    if (state.streamRaf) return;
    const tick = () => {
      const backlog = state.streamingBuffer.length - state.streamShown;
      if (backlog > 0) {
        state.streamShown += Math.min(backlog, Math.max(2, Math.ceil(backlog / 10)));
        paintStreamBody();
      }
      const more = state.isExecuting || state.streamShown < state.streamingBuffer.length;
      state.streamRaf = more ? requestAnimationFrame(tick) : null;
    };
    state.streamRaf = requestAnimationFrame(tick);
  }

  function drainTypewriter(maxMs) {
    return new Promise((resolve) => {
      const t0 = performance.now();
      (function wait() {
        if (state.streamShown >= state.streamingBuffer.length || performance.now() - t0 > maxMs) return resolve();
        setTimeout(wait, 30);
      })();
    });
  }

  function showOptimisticUserBubble(text) {
    const streamEl = document.getElementById("conversation-stream");
    const welcomeEl = document.getElementById("welcome-screen");
    if (!streamEl) return;
    if (welcomeEl) welcomeEl.style.display = "none";
    streamEl.style.display = "flex";
    const el = document.createElement("article");
    el.className = "message-card user";
    el.innerHTML = `<div class="message-body">${esc(text)}</div>`;
    streamEl.appendChild(el);
  }

  function renderStreamingAssistantBubble() {
    kickTypewriter();
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
        ? "Auto"
        : eff
        ? eff.display_name.split(" (")[0]
        : sel.selected_id;
      modelLabel.title = eff ? eff.display_name : "";
    }
    if (modelDot) {
      modelDot.className = eff && !eff.connected ? "status-dot warning" : "status-dot";
    }

    const taskStatusEl = document.getElementById("top-task-status");
    const taskDotEl = document.getElementById("top-task-dot");
    if (taskStatusEl && !state.isExecuting) {
      const rawStatus = s.task_status || "Prêt";
      const displayStatus = rawStatus === "En attente" ? "Prêt" : rawStatus;
      taskStatusEl.textContent = displayStatus;
      taskStatusEl.style.display = displayStatus === "Prêt" ? "none" : "inline";
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
  // 2. SIDEBAR DISCRÈTE (GROUPEMENT PAR DATE & DOSSIERS TECHNIQUES MASQUÉS)
  // -------------------------------------------------------------------------
  function groupConversationsByDate(convs) {
    const now = new Date();
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const startOfYesterday = startOfToday - 86400000;
    const startOfWeek = startOfToday - 6 * 86400000;

    const groups = {
      today: { label: "Aujourd'hui", items: [] },
      yesterday: { label: "Hier", items: [] },
      thisWeek: { label: "Cette semaine", items: [] },
      older: { label: "Plus ancien", items: [] },
    };

    convs.forEach((c) => {
      const dateStr = c.updated_at || c.created_at;
      const ts = dateStr ? new Date(dateStr).getTime() : startOfToday;
      if (ts >= startOfToday) {
        groups.today.items.push(c);
      } else if (ts >= startOfYesterday) {
        groups.yesterday.items.push(c);
      } else if (ts >= startOfWeek) {
        groups.thisWeek.items.push(c);
      } else {
        groups.older.items.push(c);
      }
    });

    return [groups.today, groups.yesterday, groups.thisWeek, groups.older].filter((g) => g.items.length > 0);
  }

  function renderSidebar() {
    const s = state.appState || {};
    const filter = state.sidebarFilter.trim().toLowerCase();

    const allConvs = s.conversations || [];
    const activeCid = (s.active_conversation && s.active_conversation.id) || "";

    // Filtrer les conversations vides (0 message et titre par défaut), sauf si c'est la conversation active
    const validConvs = allConvs.filter((c) => {
      const msgCount = (c.messages && c.messages.length) || 0;
      if (msgCount > 0 || c.id === activeCid || c.pinned || (c.title && c.title !== "Nouvelle tâche")) {
        return true;
      }
      return false;
    });

    const convs = validConvs.filter((c) => {
      if (!filter) return true;
      return (c.title || "").toLowerCase().includes(filter);
    });

    const countConvsEl = document.getElementById("count-conversations");
    if (countConvsEl) countConvsEl.textContent = String(convs.length);

    // Champ filtrer contextuel : affiché uniquement si >= 8 conversations
    const filterInput = document.getElementById("sidebar-filter-input");
    if (filterInput) {
      filterInput.style.display = allConvs.length >= 8 ? "block" : "none";
    }

    const convContainer = document.getElementById("sec-conversations");
    if (convContainer) {
      if (convs.length === 0) {
        convContainer.innerHTML = `
          <div style="padding: 12px 10px; font-size: 12px; color: var(--text-muted);">
            Aucune conversation
          </div>
        `;
      } else {
        const grouped = groupConversationsByDate(convs);
        convContainer.innerHTML = grouped
          .map(
            (grp) => `
            <div class="sidebar-time-group">
              <div class="sidebar-time-header">${esc(grp.label)}</div>
              ${grp.items
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
                .join("")}
            </div>
          `
          )
          .join("");
      }
    }

    // Filtrer les dossiers techniques de la liste des projets visibles dans la sidebar
    const technicalFolders = ["exports", "generated", "temp", "tmp"];
    const realProjects = (s.projects || []).filter((p) => {
      const name = (p.name || "").toLowerCase();
      if (technicalFolders.includes(name) || name.startsWith("harness-test-")) {
        return false;
      }
      return true;
    });

    const countProjEl = document.getElementById("count-projects");
    if (countProjEl) countProjEl.textContent = String(realProjects.length);
    const projContainer = document.getElementById("sec-projects");
    if (projContainer) {
      projContainer.innerHTML = realProjects
        .map(
          (p) => `
          <div class="sidebar-item ${p.active ? "active" : ""}" title="${esc(p.path)}">
            <div class="sidebar-item-main">
              <span class="sidebar-item-title">${esc(p.name)}</span>
            </div>
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
  function detectArtifactType(path, explicitType) {
    if (explicitType) {
      const et = String(explicitType).toLowerCase();
      if (et === "latex") return "tex";
      return et;
    }
    const lower = String(path || "").toLowerCase();
    if (lower.endsWith(".docx") || lower.endsWith(".doc")) return "docx";
    if (lower.endsWith(".pdf")) return "pdf";
    if (lower.endsWith(".html") || lower.endsWith(".htm")) return "html";
    if (lower.endsWith(".tex")) return "tex";
    if (lower.endsWith(".py")) return "python";
    if (lower.endsWith(".svg")) return "svg";
    if (lower.endsWith(".mmd") || lower.endsWith(".mermaid")) return "mermaid";
    if (lower.endsWith(".json")) return "json";
    if (lower.endsWith(".csv") || lower.endsWith(".tsv")) return "csv";
    if (lower.endsWith(".md") || lower.endsWith(".markdown")) return "markdown";
    if (/\.(png|jpe?g|webp|gif|bmp)$/i.test(lower)) return "image";
    return "unknown";
  }

  function extractMessageArtifacts(m) {
    const list = [];
    const seen = new Set();

    function addArt(item) {
      if (!item || !item.path) return;
      const norm = String(item.path).replace(/\\/g, "/");
      if (seen.has(norm)) return;
      seen.add(norm);
      const typ = detectArtifactType(norm, item.type);
      list.push({ ...item, path: norm, type: typ });
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
      const typ = detectArtifactType(norm);
      if (typ !== "unknown") {
        addArt({ type: typ, path: norm });
      }
    });

    const content = String(m.content || "");
    const exportMatch = content.match(/\[EXPORT OK\]\s+([^\s|]+\.(?:pdf|md|html|py|svg|mmd|mermaid|json|csv|png|jpg))/i);
    if (exportMatch) {
      const p = exportMatch[1].trim();
      addArt({ path: p });
    }

    if (list.some((a) => a.type === "docx")) return list.filter((a) => a.type !== "tex" && a.type !== "pdf");
    if (list.some((a) => a.type === "pdf")) return list.filter((a) => a.type !== "tex");
    return list;
  }

  function renderMessageArtifactsHtml(m) {
    const artifacts = extractMessageArtifacts(m);
    if (artifacts.length === 0) return "";

    return `
      <div class="message-artifacts-row">
        ${artifacts
          .map((art) => {
            const typ = art.type || detectArtifactType(art.path);
            if (typ === "pdf") {
              const pagesTxt = art.page_count ? ` · ${art.page_count} page${art.page_count > 1 ? "s" : ""}` : "";
              return `
                <div class="artifact-card">
                  <div class="artifact-card-title">
                    <span>📄</span>
                    <span class="mono">${esc(art.path)}</span>
                    <span class="meta-chip accent">PDF${esc(pagesTxt)}</span>
                  </div>
                  <div class="artifact-card-actions">
                    <button type="button" class="artifact-btn primary" data-open-doc-preview="pdf" data-doc-path="${esc(art.path)}" data-doc-source="${esc(art.source_tex || "")}" data-doc-pages="${esc(art.page_count || "")}">
                      Aperçu PDF
                    </button>
                    <a class="artifact-btn" href="/api/files/raw?path=${encodeURIComponent(art.path)}&download=1" download>
                      ⬇ Télécharger
                    </a>
                  </div>
                </div>
              `;
            }
            if (typ === "html") {
              return `
                <div class="artifact-card">
                  <div class="artifact-card-title">
                    <span>🌐</span>
                    <span class="mono">${esc(art.path)}</span>
                    <span class="meta-chip accent">HTML</span>
                  </div>
                  <div class="artifact-card-actions">
                    <button type="button" class="artifact-btn primary" data-open-doc-preview="html" data-doc-path="${esc(art.path)}" data-doc-view="render">
                      Aperçu HTML
                    </button>
                    <button type="button" class="artifact-btn" data-open-doc-preview="html" data-doc-path="${esc(art.path)}" data-doc-view="source">
                      Code source
                    </button>
                    <a class="artifact-btn" href="/api/files/raw?path=${encodeURIComponent(art.path)}&download=1" download>⬇</a>
                  </div>
                </div>
              `;
            }
            if (typ === "tex") {
              return `
                <div class="artifact-card">
                  <div class="artifact-card-title">
                    <span>📐</span>
                    <span class="mono">${esc(art.path)}</span>
                    <span class="meta-chip">LaTeX</span>
                  </div>
                  <div class="artifact-card-actions">
                    <button type="button" class="artifact-btn primary" data-compile-tex-path="${esc(art.path)}">
                      ⚡ Compiler PDF (Tectonic)
                    </button>
                    <button type="button" class="artifact-btn" data-open-doc-preview="tex" data-doc-path="${esc(art.path)}" data-doc-view="source">
                      Source .tex
                    </button>
                  </div>
                </div>
              `;
            }
            if (typ === "docx" || typ === "word") {
              const sizeTxt = art.size_bytes ? ` · ${Math.max(1, Math.round(art.size_bytes / 1024))} Ko` : "";
              return `
                <div class="artifact-card">
                  <div class="artifact-card-title">
                    <span>📘</span>
                    <span class="mono">${esc(art.path)}</span>
                    <span class="meta-chip accent">Word (DOCX)${esc(sizeTxt)}</span>
                  </div>
                  <div class="artifact-card-actions">
                    <button type="button" class="artifact-btn primary" data-open-doc-preview="docx" data-doc-path="${esc(art.path)}">
                      Aperçu Word
                    </button>
                    <a class="artifact-btn" href="/api/files/raw?path=${encodeURIComponent(art.path)}&download=1" download title="Télécharger le document Word (.docx)">
                      ⬇ Télécharger
                    </a>
                  </div>
                </div>
              `;
            }
            if (typ === "python") {
              return `
                <div class="artifact-card">
                  <div class="artifact-card-title">
                    <span>🐍</span>
                    <span class="mono">${esc(art.path)}</span>
                    <span class="meta-chip accent">Python</span>
                  </div>
                  <div class="artifact-card-actions">
                    <button type="button" class="artifact-btn primary" data-open-doc-preview="python" data-doc-path="${esc(art.path)}" data-doc-view="render">
                      ⚡ Aperçu & Exécution
                    </button>
                    <button type="button" class="artifact-btn" data-open-doc-preview="python" data-doc-path="${esc(art.path)}" data-doc-view="source">
                      Code source
                    </button>
                    <a class="artifact-btn" href="/api/files/raw?path=${encodeURIComponent(art.path)}&download=1" download title="Télécharger le fichier">
                      ⬇ Télécharger
                    </a>
                  </div>
                </div>
              `;
            }
            if (typ === "svg") {
              return `
                <div class="artifact-card">
                  <div class="artifact-card-title">
                    <span>🎨</span>
                    <span class="mono">${esc(art.path)}</span>
                    <span class="meta-chip accent">SVG</span>
                  </div>
                  <div class="artifact-card-actions">
                    <button type="button" class="artifact-btn primary" data-open-doc-preview="svg" data-doc-path="${esc(art.path)}" data-doc-view="render">
                      Aperçu SVG
                    </button>
                    <button type="button" class="artifact-btn" data-open-doc-preview="svg" data-doc-path="${esc(art.path)}" data-doc-view="source">
                      Code XML
                    </button>
                    <a class="artifact-btn" href="/api/files/raw?path=${encodeURIComponent(art.path)}&download=1" download>⬇</a>
                  </div>
                </div>
              `;
            }
            if (typ === "mermaid") {
              return `
                <div class="artifact-card">
                  <div class="artifact-card-title">
                    <span>📊</span>
                    <span class="mono">${esc(art.path)}</span>
                    <span class="meta-chip accent">Mermaid</span>
                  </div>
                  <div class="artifact-card-actions">
                    <button type="button" class="artifact-btn primary" data-open-doc-preview="mermaid" data-doc-path="${esc(art.path)}" data-doc-view="render">
                      Aperçu Diagramme
                    </button>
                    <button type="button" class="artifact-btn" data-open-doc-preview="mermaid" data-doc-path="${esc(art.path)}" data-doc-view="source">
                      Source Mermaid
                    </button>
                  </div>
                </div>
              `;
            }
            if (typ === "json") {
              return `
                <div class="artifact-card">
                  <div class="artifact-card-title">
                    <span>🌳</span>
                    <span class="mono">${esc(art.path)}</span>
                    <span class="meta-chip accent">JSON</span>
                  </div>
                  <div class="artifact-card-actions">
                    <button type="button" class="artifact-btn primary" data-open-doc-preview="json" data-doc-path="${esc(art.path)}" data-doc-view="render">
                      Arborescence JSON
                    </button>
                    <button type="button" class="artifact-btn" data-open-doc-preview="json" data-doc-path="${esc(art.path)}" data-doc-view="source">
                      Code source
                    </button>
                  </div>
                </div>
              `;
            }
            if (typ === "csv") {
              return `
                <div class="artifact-card">
                  <div class="artifact-card-title">
                    <span>📈</span>
                    <span class="mono">${esc(art.path)}</span>
                    <span class="meta-chip accent">Tableur CSV</span>
                  </div>
                  <div class="artifact-card-actions">
                    <button type="button" class="artifact-btn primary" data-open-doc-preview="csv" data-doc-path="${esc(art.path)}" data-doc-view="render">
                      Tableau Interactif
                    </button>
                    <button type="button" class="artifact-btn" data-open-doc-preview="csv" data-doc-path="${esc(art.path)}" data-doc-view="source">
                      Données brutes
                    </button>
                    <a class="artifact-btn" href="/api/files/raw?path=${encodeURIComponent(art.path)}&download=1" download>⬇</a>
                  </div>
                </div>
              `;
            }
            if (typ === "markdown") {
              return `
                <div class="artifact-card">
                  <div class="artifact-card-title">
                    <span>📝</span>
                    <span class="mono">${esc(art.path)}</span>
                    <span class="meta-chip accent">Markdown</span>
                  </div>
                  <div class="artifact-card-actions">
                    <button type="button" class="artifact-btn primary" data-open-doc-preview="markdown" data-doc-path="${esc(art.path)}" data-doc-view="render">
                      Aperçu Document
                    </button>
                    <button type="button" class="artifact-btn" data-open-doc-preview="markdown" data-doc-path="${esc(art.path)}" data-doc-view="source">
                      Source .md
                    </button>
                  </div>
                </div>
              `;
            }
            if (typ === "image") {
              return `
                <div class="artifact-card">
                  <div class="artifact-card-title">
                    <span>🖼️</span>
                    <span class="mono">${esc(art.path)}</span>
                    <span class="meta-chip accent">Image HD</span>
                  </div>
                  <div class="artifact-card-actions">
                    <button type="button" class="artifact-btn primary" data-open-doc-preview="image" data-doc-path="${esc(art.path)}" data-doc-view="render">
                      Aperçu Image
                    </button>
                    <a class="artifact-btn" href="/api/files/raw?path=${encodeURIComponent(art.path)}&download=1" download>⬇ Télécharger</a>
                  </div>
                </div>
              `;
            }
            return `
              <div class="artifact-card">
                <div class="artifact-card-title">
                  <span>📦</span>
                  <span class="mono">${esc(art.path)}</span>
                  <span class="meta-chip">${esc((typ || "Fichier").toUpperCase())}</span>
                </div>
                <div class="artifact-card-actions">
                  <button type="button" class="artifact-btn primary" data-open-doc-preview="${esc(typ)}" data-doc-path="${esc(art.path)}" data-doc-view="render">
                    Aperçu
                  </button>
                  <button type="button" class="artifact-btn" data-open-doc-preview="${esc(typ)}" data-doc-path="${esc(art.path)}" data-doc-view="source">
                    Source
                  </button>
                </div>
              </div>
            `;
          })
          .join("")}
      </div>
    `;
  }

  function setWelcomeGreeting() {
    const el = document.getElementById("welcome-title");
    if (!el) return;
    const h = new Date().getHours();
    const hello = h < 5 ? "Bonsoir" : h < 12 ? "Bonjour" : h < 18 ? "Bon après-midi" : "Bonsoir";
    el.textContent = `${hello}. Que faisons-nous ?`;
  }

  function renderWorkspace() {
    const s = state.appState;
    const conv = s.active_conversation || { messages: [] };
    const msgs = conv.messages || [];

    const welcomeEl = document.getElementById("welcome-screen");
    const streamEl = document.getElementById("conversation-stream");

    renderWelcomeModelCard();
    setWelcomeGreeting();

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
          summaryParts.push(`${toolsUsed.length} action${toolsUsed.length > 1 ? "s" : ""}`);
        }
        if (sourcesUsed.length > 0) summaryParts.push(`${sourcesUsed.length} source${sourcesUsed.length > 1 ? "s" : ""}`);

        const activityHtml =
          summaryParts.length > 0 && (toolsUsed.length > 0 || planSteps.length > 0)
            ? `
            <details class="activity-flow-box">
              <summary class="activity-flow-summary">
              <span>${esc(summaryParts.join(" · "))}</span>
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
      out = out.replace(/@@INLINEMATH(\d+)@@/g, function (_, idxStr) {
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
      const token = `@@INLINEMATH${inlineMathTokens.length}@@`;
      inlineMathTokens.push(`<span class="math-inline">${renderMathExpression(expr, false)}</span>`);
      return token;
    });
    working = working.replace(/(^|[^\\$])\$([^\s$][^$\n]*?[^\s$]|[^\s$])\$(?!\d)/g, function (_, prefix, expr) {
      const token = `${prefix}@@INLINEMATH${inlineMathTokens.length}@@`;
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

    // Alias : corrige les appels existants à renderComposer()
  function renderComposer() {
    renderComposerControls();
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

  function closeRightPanel() {
    const rightEl = document.getElementById("right-inspector");
    if (rightEl) {
      rightEl.classList.add("collapsed");
      rightEl.style.width = "0px";
      rightEl.style.display = "none";
      rightEl.classList.remove("doc-fullscreen");
    }
    state.rightPanelMode = "inspector";
    restoreSidebarIfAutoCollapsed();
  }

  // Ferme le document ouvert (croix de l'aperçu) et l'oublie complètement
  function closeDocumentPreview() {
    state.activeDocument = null;
    state.pdfDocCache = null;
    state.pdfRenderToken++;
    closeRightPanel();
  }

  function restoreSidebarIfAutoCollapsed() {
    if (!state.sidebarAutoCollapsed) return;
    const sb = document.getElementById("left-sidebar");
    if (sb) sb.classList.remove("collapsed");
    state.sidebarAutoCollapsed = false;
  }

  function toggleRightPanel() {
    const rightEl = document.getElementById("right-inspector");
    if (!rightEl) return;
    const isClosed =
      rightEl.classList.contains("collapsed") ||
      rightEl.style.display === "none" ||
      rightEl.offsetWidth === 0;
    if (isClosed) {
      switchRightPanelMode("inspector");
      renderInspector();
    } else if (state.rightPanelMode === "document") {
      rightEl.classList.remove("doc-fullscreen");
      switchRightPanelMode("inspector");
      renderInspector();
    } else {
      closeRightPanel();
    }
  }

  function switchRightPanelMode(mode) {
    state.rightPanelMode = mode === "document" ? "document" : "inspector";
    const inspectorAside = document.getElementById("right-inspector");
    const docContainer = document.getElementById("doc-preview-container");
    const techContainer = document.getElementById("inspector-tech-container");
    const btnBackToDoc = document.getElementById("btn-switch-to-doc");

    if (inspectorAside) {
      inspectorAside.classList.remove("collapsed");
      inspectorAside.style.display = "flex";
      inspectorAside.classList.toggle("doc-mode", state.rightPanelMode === "document");
            const areaW = (document.querySelector(".main-area") || document.body).clientWidth;
      inspectorAside.style.width =
        state.rightPanelMode === "document" ? `${state.docWidth || Math.floor(areaW / 2)}px` : "400px";
    }
    const sbEl = document.getElementById("left-sidebar");
    if (state.rightPanelMode === "document") {
      if (sbEl && !sbEl.classList.contains("collapsed")) {
        sbEl.classList.add("collapsed");
        state.sidebarAutoCollapsed = true;
      }
    } else {
      restoreSidebarIfAutoCollapsed();
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
    const type = detectArtifactType(cleanPath, docSpec.type);

    const docObj = {
      id: docSpec.id || null,
      type,
      path: cleanPath,
      source_tex: docSpec.source_tex || (type === "tex" ? cleanPath : ""),
      page_count: docSpec.page_count || null,
      size_bytes: docSpec.size_bytes || null,
      viewMode: docSpec.viewMode || (type === "tex" ? "source" : "render"),
      zoom: docSpec.zoom || 100,
      auto_repaired: Boolean(docSpec.auto_repaired),
      repair_notes: docSpec.repair_notes || [],
      error: docSpec.error || null,
      sourceContent: docSpec.sourceContent || "",
      execution: docSpec.execution || null,
      output_paths: docSpec.output_paths ? [...docSpec.output_paths] : [],
      source_paths: docSpec.source_paths ? [...docSpec.source_paths] : [],
      metadata: docSpec.metadata || {},
    };

    state.activeDocument = docObj;
    state.pdfDocCache = null;
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
    } else if (type === "image") {
      try {
        const fileData = await apiGet(`/api/files/content?path=${encodeURIComponent(cleanPath)}`);
        docObj.size_bytes = fileData.size_bytes;
      } catch (_) {}
    } else if (type === "docx") {
      docObj.viewMode = "render";
    } else {
      try {
        const fileData = await apiGet(`/api/files/content?path=${encodeURIComponent(cleanPath)}`);
        docObj.sourceContent = fileData.content || "";
        docObj.size_bytes = fileData.size_bytes;
      } catch (err) {
        docObj.error = `Le fichier ${cleanPath} est introuvable ou illisible : ${err.message}`;
      }
    }

    if (type === "python" && !docObj.execution && !docObj.error) {
      try {
        const execRes = await apiPost("/api/artifacts/execute", { path: cleanPath });
        if (execRes.artifact) {
          docObj.execution = execRes.artifact.execution;
          docObj.output_paths = execRes.artifact.output_paths || [];
          docObj.error = execRes.artifact.error || null;
          docObj.metadata = execRes.artifact.metadata || docObj.metadata;
          if (docObj.metadata && (docObj.metadata.visual_output || (docObj.metadata.figures && docObj.metadata.figures.length > 0))) {
            docObj.viewMode = "render";
          }
        }
      } catch (err) {
        docObj.error = err.message;
      }
    }

    renderDocumentPreviewPanel();
  }

  const PDFJS_WORKER = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";

  async function renderPdfInViewer(doc) {
    const host = document.getElementById("doc-pdf-viewer");
    if (!host) return;
    if (!window.pdfjsLib) throw new Error("PDF.js n'est pas chargé (réseau ou cdnjs bloqué).");
    window.pdfjsLib.GlobalWorkerOptions.workerSrc = PDFJS_WORKER;
    const token = ++state.pdfRenderToken;

    let pdf = state.pdfDocCache && state.pdfDocCache.key === doc.path ? state.pdfDocCache.pdf : null;
    if (!pdf) {
      const res = await fetch(`/api/files/raw?path=${encodeURIComponent(doc.path)}&t=${Date.now()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      pdf = await window.pdfjsLib.getDocument({ data: await res.arrayBuffer() }).promise;
      state.pdfDocCache = { key: doc.path, pdf };
    }
    if (token !== state.pdfRenderToken) return;

    const avail = Math.max(200, host.clientWidth - 32);
    state.pdfWidth = host.clientWidth;
    const dpr = window.devicePixelRatio || 1;
    const zoomUsed = doc.zoom || 100;
    const frag = document.createDocumentFragment();
    for (let n = 1; n <= pdf.numPages; n++) {
      const page = await pdf.getPage(n);
      if (token !== state.pdfRenderToken) return;
      const base = page.getViewport({ scale: 1 });
      const vp = page.getViewport({ scale: (avail / base.width) * (zoomUsed / 100) });
      const canvas = document.createElement("canvas");
      canvas.className = "pdf-page";
      canvas.width = Math.floor(vp.width * dpr);
      canvas.height = Math.floor(vp.height * dpr);
      canvas.style.width = `${Math.floor(vp.width)}px`;
      canvas.style.height = `${Math.floor(vp.height)}px`;
      canvas.dataset.w = String(Math.floor(vp.width));
      canvas.dataset.h = String(Math.floor(vp.height));
      await page.render({
        canvasContext: canvas.getContext("2d"),
        viewport: vp,
        transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : null,
      }).promise;
      frag.appendChild(canvas);
    }
    if (token !== state.pdfRenderToken) return;
    const keepTop = host.scrollTop;
    const keepLeft = host.scrollLeft;
    host.innerHTML = "";
    host.appendChild(frag);
    host.dataset.renderedZoom = String(zoomUsed);
    host.scrollTop = keepTop;
    host.scrollLeft = keepLeft;
  }

  function renderSvgInViewer(doc) {
    const host = document.getElementById("doc-svg-viewer");
    if (!host) return;
    host.innerHTML = "";
    if (!doc.sourceContent) {
      host.innerHTML = `<div class="inspector-card">Aucun contenu SVG à afficher.</div>`;
      return;
    }
    try {
      const parser = new DOMParser();
      const docParsed = parser.parseFromString(doc.sourceContent, "image/svg+xml");
      const svgEl = docParsed.querySelector("svg");
      if (svgEl) {
        svgEl.style.maxWidth = "100%";
        svgEl.style.maxHeight = "100%";
        svgEl.style.display = "block";
        svgEl.style.margin = "auto";
        svgEl.style.filter = "drop-shadow(0 4px 12px rgba(0,0,0,0.08))";
        host.appendChild(document.importNode(svgEl, true));
      } else {
        host.innerHTML = `<div class="doc-error-box" style="display:block;"><strong>Erreur SVG</strong> : Balise &lt;svg&gt; manquante ou XML invalide.</div>`;
      }
    } catch (err) {
      host.innerHTML = `<div class="doc-error-box" style="display:block;"><strong>Erreur de rendu SVG</strong> : ${esc(err.message)}</div>`;
    }
  }

  async function renderMermaidInViewer(doc) {
    const host = document.getElementById("doc-mermaid-viewer");
    if (!host) return;
    host.innerHTML = "";
    if (!doc.sourceContent) {
      host.innerHTML = `<div class="inspector-card">Aucun code Mermaid à afficher.</div>`;
      return;
    }
    if (!window.mermaid) {
      host.innerHTML = `
        <div class="inspector-card">
          <strong>Mermaid.js</strong> est en cours de chargement ou indisponible hors-ligne.
          <pre class="mono" style="margin-top:8px;">${esc(doc.sourceContent)}</pre>
        </div>
      `;
      return;
    }
    try {
      const isDark = document.documentElement.getAttribute("data-theme") === "dark";
      window.mermaid.initialize({
        startOnLoad: false,
        theme: isDark ? "dark" : "default",
        securityLevel: "loose",
      });
      const id = "mermaid-svg-" + Math.random().toString(36).slice(2, 8);
      const renderResult = await window.mermaid.render(id, doc.sourceContent);
      host.innerHTML = renderResult.svg || "";
    } catch (err) {
      host.innerHTML = `
        <div class="doc-error-box" style="display:block;">
          <strong>⚠️ Erreur de syntaxe Mermaid</strong>
          <pre class="mono" style="margin-top:8px; white-space:pre-wrap;">${esc(err.message)}</pre>
        </div>
      `;
    }
  }

  function renderImageInViewer(doc) {
    const host = document.getElementById("doc-image-viewer");
    if (!host) return;
    const url = `/api/files/raw?path=${encodeURIComponent(doc.path)}&t=${Date.now()}`;
    host.innerHTML = `
      <div style="display:flex; flex-direction:column; align-items:center; gap:12px; max-width:100%; padding:16px;">
        <img src="${url}" alt="${esc(doc.path)}" style="max-width:100%; max-height:75vh; object-fit:contain; border-radius:8px; box-shadow:0 6px 20px rgba(0,0,0,0.12);" />
        <div style="font-size:12px; color:var(--text-secondary); display:flex; gap:8px;">
          <span>${esc(doc.path.split("/").pop())}</span>
          ${doc.size_bytes ? `<span>· ${doc.size_bytes} octets</span>` : ""}
        </div>
      </div>
    `;
  }

  function renderFiguresGalleryInViewer(figures, doc) {
    const host = document.getElementById("doc-image-viewer");
    if (!host) return;
    host.innerHTML = `
      <div style="display:flex; flex-direction:column; align-items:center; gap:20px; max-width:100%; padding:16px;">
        <div style="font-size:12.5px; font-weight:600; color:var(--text-secondary); display:flex; align-items:center; gap:6px;">
          <span>📊</span>
          <span>${figures.length} figures Matplotlib capturées :</span>
        </div>
        ${figures
          .map((figPath, idx) => {
            const url = `/api/files/raw?path=${encodeURIComponent(figPath)}&t=${Date.now()}`;
            return `
            <div style="display:flex; flex-direction:column; align-items:center; gap:8px; width:100%; max-width:720px; background:var(--bg-primary); border:1px solid var(--border-subtle); border-radius:10px; padding:12px; box-shadow:var(--shadow-sm);">
              <img src="${url}" alt="${esc(figPath)}" style="max-width:100%; max-height:65vh; object-fit:contain; border-radius:6px;" />
              <div style="display:flex; justify-content:space-between; width:100%; font-size:11.5px; color:var(--text-muted); padding:0 4px;">
                <span><strong>Figure ${idx + 1}</strong> : ${esc(figPath.split("/").pop())}</span>
                <a href="${url}" target="_blank" class="link-subtle" style="font-size:11px;">Ouvrir ↗</a>
              </div>
            </div>
          `;
          })
          .join("")}
      </div>
    `;
  }

  function renderCsvInViewer(doc) {
    const host = document.getElementById("doc-table-viewer");
    if (!host) return;
    host.innerHTML = "";
    if (!doc.sourceContent) {
      host.innerHTML = `<div class="inspector-card">Aucune donnée CSV à afficher.</div>`;
      return;
    }

    const firstLine = doc.sourceContent.split("\n")[0] || "";
    const commaCount = (firstLine.match(/,/g) || []).length;
    const semiCount = (firstLine.match(/;/g) || []).length;
    const tabCount = (firstLine.match(/\t/g) || []).length;
    let delim = ",";
    if (semiCount > commaCount && semiCount >= tabCount) delim = ";";
    else if (tabCount > commaCount && tabCount > semiCount) delim = "\t";

    function parseCSVLine(line, delimiter) {
      const result = [];
      let current = "";
      let inQuotes = false;
      for (let i = 0; i < line.length; i++) {
        const c = line[i];
        if (c === '"') {
          if (inQuotes && line[i + 1] === '"') {
            current += '"';
            i++;
          } else {
            inQuotes = !inQuotes;
          }
        } else if (c === delimiter && !inQuotes) {
          result.push(current.trim());
          current = "";
        } else {
          current += c;
        }
      }
      result.push(current.trim());
      return result;
    }

    const lines = doc.sourceContent.split(/\r?\n/).filter((l) => l.trim().length > 0);
    if (lines.length === 0) {
      host.innerHTML = `<div class="inspector-card">Fichier CSV vide.</div>`;
      return;
    }

    const headers = parseCSVLine(lines[0], delim);
    const rows = lines.slice(1).map((l) => parseCSVLine(l, delim));

    host.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; gap:8px;">
        <input type="text" id="csv-search-input" class="sidebar-search" placeholder="Filtrer dans les données (${rows.length} lignes)..." style="max-width:320px;" />
        <div style="font-size:12px; color:var(--text-secondary);">${rows.length} lignes · ${headers.length} colonnes</div>
      </div>
      <div style="overflow-x:auto; border:1px solid var(--border); border-radius:8px;">
        <table class="doc-data-table" id="csv-table-element">
          <thead>
            <tr>${headers.map((h, idx) => `<th data-col-idx="${idx}" style="cursor:pointer;" title="Colonne ${idx + 1}">${esc(h)} ▾</th>`).join("")}</tr>
          </thead>
          <tbody>
            ${rows
              .map(
                (row) => `
              <tr>${headers.map((_, i) => `<td>${esc(row[i] !== undefined ? row[i] : "")}</td>`).join("")}</tr>
            `
              )
              .join("")}
          </tbody>
        </table>
      </div>
    `;

    const searchInput = document.getElementById("csv-search-input");
    const tbody = host.querySelector("tbody");
    if (searchInput && tbody) {
      searchInput.addEventListener("input", (e) => {
        const q = String(e.target.value || "").toLowerCase();
        const trs = tbody.querySelectorAll("tr");
        trs.forEach((tr) => {
          const txt = tr.textContent.toLowerCase();
          tr.style.display = txt.includes(q) ? "" : "none";
        });
      });
    }
  }

  function renderJsonInViewer(doc) {
    const host = document.getElementById("doc-json-viewer");
    if (!host) return;
    host.innerHTML = "";
    if (!doc.sourceContent) {
      host.innerHTML = `<div class="inspector-card">Aucun contenu JSON à afficher.</div>`;
      return;
    }
    let parsed = null;
    try {
      parsed = JSON.parse(doc.sourceContent);
    } catch (err) {
      host.innerHTML = `
        <div class="doc-error-box" style="display:block;">
          <strong>⚠️ Erreur de syntaxe JSON :</strong>
          <pre class="mono" style="margin-top:8px;">${esc(err.message)}</pre>
        </div>
      `;
      return;
    }

    function buildJsonTree(val, keyName = null) {
      const type = Array.isArray(val) ? "array" : val === null ? "null" : typeof val;
      const keyPrefix = keyName !== null ? `<span class="json-key">"${esc(keyName)}"</span>: ` : "";

      if (type === "object" || type === "array") {
        const isArr = type === "array";
        const keys = Object.keys(val);
        const count = keys.length;
        const openChar = isArr ? "[" : "{";
        const closeChar = isArr ? "]" : "}";
        if (count === 0) {
          return `<div class="json-line">${keyPrefix}<span class="json-bracket">${openChar}${closeChar}</span></div>`;
        }
        return `
          <div class="json-node collapsed" style="margin-left: 12px;">
            <div class="json-header" style="cursor:pointer; display:flex; align-items:center; gap:6px;">
              <span class="json-toggle" style="user-select:none; font-family:monospace; font-size:10px;">▼</span>
              ${keyPrefix}
              <span class="json-bracket">${openChar}</span>
              <span class="json-badge" style="font-size:11px; opacity:0.75;">${count} élément${count > 1 ? "s" : ""}</span>
            </div>
            <div class="json-children" style="margin-left: 14px; border-left: 1px dashed var(--border); padding-left: 8px;">
              ${keys.map((k) => buildJsonTree(val[k], isArr ? null : k)).join("")}
            </div>
            <div class="json-bracket" style="margin-left: 16px;">${closeChar}</div>
          </div>
        `;
      }
      if (type === "string") {
        return `<div class="json-line" style="margin-left:12px;">${keyPrefix}<span class="json-str" style="color:var(--accent);">"${esc(val)}"</span></div>`;
      }
      if (type === "number") {
        return `<div class="json-line" style="margin-left:12px;">${keyPrefix}<span class="json-num" style="color:#d97706;">${esc(String(val))}</span></div>`;
      }
      if (type === "boolean") {
        return `<div class="json-line" style="margin-left:12px;">${keyPrefix}<span class="json-bool" style="color:#2563eb; font-weight:600;">${val}</span></div>`;
      }
      return `<div class="json-line" style="margin-left:12px;">${keyPrefix}<span class="json-null" style="opacity:0.6;">null</span></div>`;
    }

    host.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
        <span class="meta-chip">JSON Valide</span>
        <div style="display:flex; gap:6px;">
          <button type="button" class="icon-btn-mini" id="btn-json-expand-all">Tout déplier</button>
          <button type="button" class="icon-btn-mini" id="btn-json-collapse-all">Tout replier</button>
        </div>
      </div>
      <div class="json-tree-container mono" style="font-size:12px; line-height:1.5;">
        ${buildJsonTree(parsed)}
      </div>
    `;

    host.querySelectorAll(".json-header").forEach((hdr) => {
      hdr.addEventListener("click", () => {
        const node = hdr.closest(".json-node");
        if (node) {
          const children = node.querySelector(".json-children");
          const toggle = node.querySelector(".json-toggle");
          if (children) {
            const isHidden = children.style.display === "none";
            children.style.display = isHidden ? "block" : "none";
            if (toggle) toggle.textContent = isHidden ? "▼" : "▶";
          }
        }
      });
    });

    const btnExp = host.querySelector("#btn-json-expand-all");
    const btnCol = host.querySelector("#btn-json-collapse-all");
    if (btnExp) {
      btnExp.addEventListener("click", () => {
        host.querySelectorAll(".json-children").forEach((c) => (c.style.display = "block"));
        host.querySelectorAll(".json-toggle").forEach((t) => (t.textContent = "▼"));
      });
    }
    if (btnCol) {
      btnCol.addEventListener("click", () => {
        host.querySelectorAll(".json-children").forEach((c) => (c.style.display = "none"));
        host.querySelectorAll(".json-toggle").forEach((t) => (t.textContent = "▶"));
      });
    }
  }

  function renderMarkdownInViewer(doc) {
    const host = document.getElementById("doc-markdown-viewer");
    if (!host) return;
    host.innerHTML = "";
    if (!doc.sourceContent) {
      host.innerHTML = `<div class="inspector-card">Aucun contenu Markdown à afficher.</div>`;
      return;
    }
    host.innerHTML = `
      <div class="rendered-markdown-content" style="padding: 16px; line-height: 1.65;">
        ${renderMarkdownToHtml(doc.sourceContent)}
      </div>
    `;
    renderKaTeXInElement(host);
  }

  function renderFilesListInViewer(doc) {
    const host = document.getElementById("doc-files-viewer");
    if (!host) return;
    host.innerHTML = "";

    const allFiles = new Set();
    if (doc.path) allFiles.add(doc.path);
    if (doc.source_tex) allFiles.add(doc.source_tex);
    if (Array.isArray(doc.output_paths)) {
      doc.output_paths.forEach((p) => allFiles.add(p));
    }
    if (Array.isArray(doc.source_paths)) {
      doc.source_paths.forEach((p) => allFiles.add(p));
    }

    const list = Array.from(allFiles);
    if (list.length === 0) {
      host.innerHTML = `<div class="inspector-card">Aucun fichier associé à cet artefact.</div>`;
      return;
    }

    host.innerHTML = `
      <div style="font-size:12px; color:var(--text-secondary); margin-bottom:12px;">
        ${list.length} fichier${list.length > 1 ? "s" : ""} généré${list.length > 1 ? "s" : ""} ou lié${list.length > 1 ? "s" : ""} :
      </div>
      <div style="display:flex; flex-direction:column; gap:8px;">
        ${list
          .map((fpath) => {
            const isPrimary = fpath === doc.path;
            const typ = detectArtifactType(fpath);
            return `
            <div class="inspector-card" style="display:flex; justify-content:space-between; align-items:center; margin:0; padding:10px 14px;">
              <div style="display:flex; align-items:center; gap:8px; min-width:0;">
                <span style="font-size:16px;">${typ === "image" ? "🖼️" : typ === "pdf" ? "📄" : typ === "python" ? "🐍" : "📄"}</span>
                <span class="mono" style="font-size:12px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${esc(fpath)}</span>
                ${isPrimary ? `<span class="meta-chip accent">Principal</span>` : `<span class="meta-chip">Généré</span>`}
              </div>
              <div style="display:flex; gap:6px; flex-shrink:0;">
                <button type="button" class="icon-btn-mini" data-open-doc-preview="${esc(typ)}" data-doc-path="${esc(fpath)}">Ouvrir</button>
                <a class="icon-btn-mini" href="/api/files/raw?path=${encodeURIComponent(fpath)}&download=1" download title="Télécharger">⬇</a>
              </div>
            </div>
          `;
          })
          .join("")}
      </div>
    `;
  }

  function renderConsoleInViewer(doc) {
    const host = document.getElementById("doc-console-viewer");
    if (!host) return;
    host.innerHTML = "";

    const exec = doc.execution;
    if (!exec) {
      host.innerHTML = `
        <div class="inspector-card">
          <span>Aucune exécution enregistrée pour ce fichier.</span>
          ${doc.type === "python" ? `<br/><button type="button" id="btn-run-python-now" class="composer-chip-btn" style="margin-top:8px;">⚡ Exécuter maintenant</button>` : ""}
        </div>
      `;
      const btnRun = host.querySelector("#btn-run-python-now");
      if (btnRun) {
        btnRun.addEventListener("click", async () => {
          try {
            const res = await apiPost("/api/artifacts/execute", { path: doc.path });
            if (res.artifact) {
              doc.execution = res.artifact.execution;
              doc.output_paths = res.artifact.output_paths || [];
              doc.error = res.artifact.error || null;
              renderDocumentPreviewPanel();
            }
          } catch (err) {
            showStatusBanner(`Erreur d'exécution : ${err.message}`, "error");
          }
        });
      }
      return;
    }

    const isSuccess = Number(exec.exit_code) === 0;
    const durTxt = exec.duration_ms ? `${Math.round(exec.duration_ms)} ms` : "0 ms";

    host.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; gap:8px;">
        <div style="display:flex; align-items:center; gap:8px;">
          <span class="meta-chip" style="${isSuccess ? "background:rgba(16,185,129,0.18); color:#10B981; border:1px solid rgba(16,185,129,0.35); font-weight:600;" : "background:rgba(239,68,68,0.18); color:#EF4444; border:1px solid rgba(239,68,68,0.35); font-weight:600;"}">
            ${isSuccess ? "✓ Succès (Code 0)" : "⚠️ Code " + (exec.exit_code !== undefined ? exec.exit_code : "1")}
          </span>
          <span class="mono" style="font-size:11.5px; opacity:0.85; color:#94A3B8;">${durTxt}</span>
        </div>
        ${doc.type === "python" ? `<button type="button" id="btn-re-execute-console" class="icon-btn-mini">⚡ Relancer l'exécution</button>` : ""}
      </div>
      ${exec.command ? `<div style="font-size:11px; color:#94A3B8; margin-bottom:8px;"><span class="mono">Commande : ${esc(exec.command)}</span></div>` : ""}
      ${
        exec.stdout
          ? `
        <div style="margin-bottom:14px;">
          <div style="font-size:11px; font-weight:600; color:#CBD5E1; margin-bottom:6px; letter-spacing:0.4px;">STDOUT :</div>
          <pre class="doc-console-pre mono" style="background:#0F172A !important; color:#F8FAFC !important; border:1px solid #334155 !important; border-radius:6px; padding:12px; font-size:12px; line-height:1.6; max-height:360px; overflow:auto; white-space:pre-wrap;">${esc(exec.stdout)}</pre>
        </div>
      `
          : ""
      }
      ${
        exec.stderr
          ? `
        <div>
          <div style="font-size:11px; font-weight:600; color:#F87171; margin-bottom:6px; letter-spacing:0.4px;">STDERR :</div>
          <pre class="doc-console-pre mono" style="background:rgba(239, 68, 68, 0.1); border:1px solid rgba(239, 68, 68, 0.4); color:#FCA5A5; border-radius:6px; padding:12px; font-size:12px; line-height:1.6; max-height:360px; overflow:auto; white-space:pre-wrap;">${esc(exec.stderr)}</pre>
        </div>
      `
          : ""
      }
      ${!exec.stdout && !exec.stderr ? `<div class="inspector-card" style="color:#94A3B8;">Exécution terminée sans sortie console.</div>` : ""}
    `;

    const btnReExec = host.querySelector("#btn-re-execute-console");
    if (btnReExec) {
      btnReExec.addEventListener("click", async () => {
        try {
          const res = await apiPost("/api/artifacts/execute", { path: doc.path });
          if (res.artifact) {
            doc.execution = res.artifact.execution;
            doc.output_paths = res.artifact.output_paths || [];
            doc.error = res.artifact.error || null;
            renderDocumentPreviewPanel();
          }
        } catch (err) {
          showStatusBanner(`Erreur d'exécution : ${err.message}`, "error");
        }
      });
    }
  }

  function renderPythonResultInViewer(doc) {
    const host = document.getElementById("doc-result-viewer");
    if (!host) return;
    host.innerHTML = "";

    const exec = doc.execution || {};
    const isSuccess = Number(exec.exit_code) === 0;
    const durTxt = exec.duration_ms ? `${Math.round(exec.duration_ms)} ms` : "0 ms";
    const stdout = (exec.stdout || "").trim();
    const stderr = (exec.stderr || "").trim();

    // Extraire les métriques clés de stdout (e.g. "Le seuil est atteint au bout de : 9 ans.")
    const lines = stdout ? stdout.split("\n") : [];
    const metrics = [];
    const metricRegex = /^(?:[-*•]\s*)?([^:=\n]+?)\s*[:=]\s*(.+)$/;

    for (const line of lines) {
      const trimmed = line.trim();
      const match = trimmed.match(metricRegex);
      if (match && match[1].length < 50 && match[2].length < 60) {
        metrics.push({
          label: match[1].trim().replace(/^[-*•]\s*/, ""),
          value: match[2].trim().replace(/\.$/, "")
        });
      }
    }

    let metricsHtml = "";
    if (metrics.length > 0) {
      metricsHtml = `
        <div style="margin-bottom:16px;">
          <div style="font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.6px; color:var(--text-secondary); margin-bottom:8px;">Résultats & Métriques calculés</div>
          <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:10px;">
            ${metrics.map(m => `
              <div style="background:var(--bg-secondary); border:1px solid var(--border); border-left:3px solid var(--accent); border-radius:6px; padding:10px 14px;">
                <div style="font-size:11px; color:var(--text-secondary); margin-bottom:4px; font-weight:500;">${esc(m.label)}</div>
                <div style="font-size:16px; font-weight:700; color:var(--text-primary); font-family:var(--font-mono, monospace);">${esc(m.value)}</div>
              </div>
            `).join("")}
          </div>
        </div>
      `;
    }

    host.innerHTML = `
      <div style="padding:16px; max-width:850px; margin:0 auto; width:100%;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; padding-bottom:12px; border-bottom:1px solid var(--border);">
          <div style="display:flex; align-items:center; gap:10px;">
            <div style="width:36px; height:36px; border-radius:8px; background:rgba(59,130,246,0.12); display:flex; align-items:center; justify-content:center; color:#3B82F6;">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="4 17 10 11 4 5"></polyline>
                <line x1="12" y1="19" x2="20" y2="19"></line>
              </svg>
            </div>
            <div>
              <div style="font-weight:600; font-size:14px; color:var(--text-primary);">${esc(doc.path.split("/").pop())}</div>
              <div style="font-size:11.5px; color:var(--text-secondary); display:flex; align-items:center; gap:8px;">
                <span style="display:inline-flex; align-items:center; gap:4px; color:${isSuccess ? "#10B981" : "#EF4444"}; font-weight:600;">
                  ${isSuccess ? "✓ Exécution réussie" : "⚠️ Erreur (Code " + exec.exit_code + ")"}
                </span>
                <span>·</span>
                <span class="mono">${durTxt}</span>
              </div>
            </div>
          </div>
          <div style="display:flex; gap:6px;">
            <button type="button" id="btn-result-switch-console" class="icon-btn-mini" title="Basculer vers la console brute">Console brute</button>
            <button type="button" id="btn-result-reexecute" class="icon-btn-mini" title="Ré-exécuter le script">⚡ Relancer</button>
          </div>
        </div>

        ${metricsHtml}

        ${stdout ? `
          <div style="margin-bottom:16px;">
            <div style="font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.6px; color:var(--text-secondary); margin-bottom:8px;">Sortie du calcul</div>
            <div style="background:#0F172A; border:1px solid #334155; border-radius:8px; padding:14px; color:#F8FAFC; font-family:var(--font-mono, monospace); font-size:12.5px; line-height:1.6; white-space:pre-wrap; overflow-x:auto;">${esc(stdout)}</div>
          </div>
        ` : ""}

        ${stderr ? `
          <div style="margin-bottom:16px;">
            <div style="font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.6px; color:#EF4444; margin-bottom:8px;">Avertissements / Erreurs</div>
            <div style="background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.3); border-radius:8px; padding:12px; color:#FCA5A5; font-family:var(--font-mono, monospace); font-size:12px; line-height:1.5; white-space:pre-wrap;">${esc(stderr)}</div>
          </div>
        ` : ""}

        ${!stdout && !stderr ? `
          <div class="inspector-card" style="text-align:center; padding:24px; color:var(--text-secondary);">
            Le script s'est exécuté avec succès (Code 0) mais n'a produit aucun affichage dans la console.
          </div>
        ` : ""}
      </div>
    `;

    const btnSwitchConsole = host.querySelector("#btn-result-switch-console");
    if (btnSwitchConsole) {
      btnSwitchConsole.addEventListener("click", () => {
        doc.viewMode = "console";
        renderDocumentPreviewPanel();
      });
    }

    const btnReExec = host.querySelector("#btn-result-reexecute");
    if (btnReExec) {
      btnReExec.addEventListener("click", async () => {
        try {
          const res = await apiPost("/api/artifacts/execute", { path: doc.path });
          if (res.artifact) {
            doc.execution = res.artifact.execution;
            doc.output_paths = res.artifact.output_paths || [];
            doc.error = res.artifact.error || null;
            renderDocumentPreviewPanel();
          }
        } catch (err) {
          showStatusBanner(`Erreur d'exécution : ${err.message}`, "error");
        }
      });
    }
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
    const btnFiles = document.getElementById("btn-doc-view-files");
    const btnConsole = document.getElementById("btn-doc-view-console");
    const btnRecompile = document.getElementById("btn-doc-recompile");
    const btnSaveSource = document.getElementById("btn-doc-save-source");
    const btnDownload = document.getElementById("btn-doc-download");

    const pdfViewer = document.getElementById("doc-pdf-viewer");
    const htmlFrame = document.getElementById("doc-html-frame");
    const svgViewer = document.getElementById("doc-svg-viewer");
    const mermaidViewer = document.getElementById("doc-mermaid-viewer");
    const imageViewer = document.getElementById("doc-image-viewer");
    const tableViewer = document.getElementById("doc-table-viewer");
    const jsonViewer = document.getElementById("doc-json-viewer");
    const markdownViewer = document.getElementById("doc-markdown-viewer");
    const resultViewer = document.getElementById("doc-result-viewer");
    const filesViewer = document.getElementById("doc-files-viewer");
    const consoleViewer = document.getElementById("doc-console-viewer");
    const sourceWrap = document.getElementById("doc-source-wrap");
    const sourceEditor = document.getElementById("doc-source-editor");
    const errorBox = document.getElementById("doc-error-box");

    const badgeMap = {
      pdf: "PDF · Tectonic",
      docx: "Word · Pandoc",
      html: "HTML · Sandbox",
      tex: "LaTeX · Source",
      python: "Python · Exécution",
      svg: "SVG · Vectoriel",
      mermaid: "Mermaid · Diagramme",
      json: "JSON · Arborescence",
      csv: "CSV · Tableur",
      markdown: "Markdown · Document",
      image: "Image · HD",
    };
    if (badgeEl) {
      badgeEl.textContent = badgeMap[doc.type] || `${(doc.type || "Fichier").toUpperCase()}`;
    }
    if (nameEl) {
      nameEl.textContent = doc.path;
      nameEl.title = doc.path;
    }

    const metaParts = [];
    if (doc.page_count) metaParts.push(`${doc.page_count} page${doc.page_count > 1 ? "s" : ""}`);
    if (doc.size_bytes) metaParts.push(`${doc.size_bytes} octets`);
    if (doc.execution && doc.execution.duration_ms) metaParts.push(`${Math.round(doc.execution.duration_ms)} ms`);
    if (metaEl) metaEl.textContent = metaParts.join(" · ");

    if (btnDownload) {
      btnDownload.href = `/api/files/raw?path=${encodeURIComponent(doc.path)}&download=1`;
      btnDownload.setAttribute("download", doc.path.split("/").pop() || "document");
    }

    if (noticeEl) {
      if (doc.auto_repaired) {
        noticeEl.style.display = "block";
        noticeEl.textContent = `✓ Artefact réparé automatiquement (${(doc.repair_notes || []).join(", ") || "syntaxe normalisée"}).`;
      } else {
        noticeEl.style.display = "none";
      }
    }

    if (btnRender && btnSource) {
      btnRender.classList.toggle("active", doc.viewMode === "render");
      btnSource.classList.toggle("active", doc.viewMode === "source");
      btnSource.textContent =
        doc.type === "pdf" || doc.type === "tex"
          ? "Source .tex"
          : doc.type === "svg"
          ? "Code XML"
          : doc.type === "csv"
          ? "Données brutes"
          : "Code source";
      btnSource.style.display = doc.type === "image" ? "none" : "inline-block";
    }

    if (btnFiles) {
      btnFiles.classList.toggle("active", doc.viewMode === "files");
      const hasFiles = (doc.output_paths && doc.output_paths.length > 0) || (doc.source_paths && doc.source_paths.length > 0);
      btnFiles.style.display = hasFiles ? "inline-block" : "none";
    }

    if (btnConsole) {
      btnConsole.classList.toggle("active", doc.viewMode === "console");
      btnConsole.style.display = doc.execution || doc.type === "python" ? "inline-block" : "none";
    }

    if (zoomControls) {
      zoomControls.style.display = doc.type === "pdf" && doc.viewMode === "render" ? "inline-flex" : "none";
    }
    if (zoomLabel) {
      zoomLabel.textContent = `${doc.zoom}%`;
    }

    if (btnRecompile) {
      if ((doc.type === "pdf" && doc.source_tex) || doc.type === "tex") {
        btnRecompile.style.display = "inline-flex";
        const txt = btnRecompile.querySelector("span");
        if (txt) txt.textContent = "Compiler";
      } else if (doc.type === "python") {
        btnRecompile.style.display = "inline-flex";
        const txt = btnRecompile.querySelector("span");
        if (txt) txt.textContent = "Exécuter";
      } else {
        btnRecompile.style.display = "none";
      }
    }

    if (btnSaveSource) {
      btnSaveSource.style.display = doc.viewMode === "source" ? "inline-flex" : "none";
    }

    [pdfViewer, htmlFrame, svgViewer, mermaidViewer, imageViewer, tableViewer, jsonViewer, markdownViewer, resultViewer, filesViewer, consoleViewer, sourceWrap, errorBox].forEach((el) => {
      if (el) el.style.display = "none";
    });

    if (doc.error) {
      if (errorBox) {
        errorBox.style.display = "block";
        errorBox.innerHTML = `
          <strong>⚠️ Erreur d'aperçu ou de validation</strong>
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

    if (doc.viewMode === "files") {
      if (filesViewer) {
        filesViewer.style.display = "block";
        renderFilesListInViewer(doc);
      }
      return;
    }

    if (doc.viewMode === "console") {
      if (consoleViewer) {
        consoleViewer.style.display = "block";
        renderConsoleInViewer(doc);
      }
      return;
    }

    // doc.viewMode === "render"
    if (doc.type === "pdf" && pdfViewer) {
      pdfViewer.style.display = "flex";
      renderPdfInViewer(doc).catch((err) => {
        if (errorBox) {
          errorBox.style.display = "block";
          errorBox.innerHTML = `<strong>⚠️ Aperçu PDF impossible</strong><pre class="mono" style="margin-top:8px;white-space:pre-wrap;font-size:11.5px;">${esc(err.message)}</pre>`;
        }
      });
    } else if ((doc.type === "html" || doc.type === "docx") && htmlFrame) {
      htmlFrame.style.display = "block";
      htmlFrame.src = `/api/preview/workspace/${doc.path.split("/").map(encodeURIComponent).join("/")}?t=${Date.now()}`;
    } else if (doc.type === "svg" && svgViewer) {
      svgViewer.style.display = "flex";
      renderSvgInViewer(doc);
    } else if (doc.type === "mermaid" && mermaidViewer) {
      mermaidViewer.style.display = "flex";
      renderMermaidInViewer(doc);
    } else if (doc.type === "image" && imageViewer) {
      imageViewer.style.display = "flex";
      renderImageInViewer(doc);
    } else if (doc.type === "csv" && tableViewer) {
      tableViewer.style.display = "block";
      renderCsvInViewer(doc);
    } else if (doc.type === "json" && jsonViewer) {
      jsonViewer.style.display = "block";
      renderJsonInViewer(doc);
    } else if (doc.type === "markdown" && markdownViewer) {
      markdownViewer.style.display = "block";
      renderMarkdownInViewer(doc);
    } else if (doc.type === "python") {
      const figures = (doc.metadata && doc.metadata.figures) || [];
      const visualOut =
        (doc.metadata && doc.metadata.visual_output) ||
        figures[0] ||
        (doc.output_paths || []).find((p) => /\.(png|jpe?g|webp|svg)$/i.test(p));
      const csvOut = (doc.output_paths || []).find((p) => /\.csv$/i.test(p));
      const jsonOut = (doc.output_paths || []).find((p) => /\.json$/i.test(p));

      if (visualOut && imageViewer) {
        imageViewer.style.display = "flex";
        if (figures.length > 1) {
          renderFiguresGalleryInViewer(figures, doc);
        } else {
          renderImageInViewer({ path: visualOut, size_bytes: null });
        }
      } else if (csvOut && tableViewer) {
        tableViewer.style.display = "block";
        renderCsvInViewer({ path: csvOut });
      } else if (jsonOut && jsonViewer) {
        jsonViewer.style.display = "block";
        renderJsonInViewer({ path: jsonOut });
      } else if (resultViewer) {
        resultViewer.style.display = "block";
        renderPythonResultInViewer(doc);
      } else if (consoleViewer) {
        consoleViewer.style.display = "block";
        renderConsoleInViewer(doc);
      }
    }
  }

    function setPdfZoom(next, clientX, clientY) {
      const d = state.activeDocument;
      const host = document.getElementById("doc-pdf-viewer");
      if (!d || !host || d.type !== "pdf" || d.viewMode !== "render") return;
      const oldZoom = d.zoom || 100;
      const z = Math.max(50, Math.min(400, next));
      if (Math.abs(z - oldZoom) < 0.05) return;

      // Point fixe : sous le curseur (ou centre du panneau si clavier / boutons)
      const rect = host.getBoundingClientRect();
      const ax = clientX == null ? host.clientWidth / 2 : clientX - rect.left;
      const ay = clientY == null ? host.clientHeight / 2 : clientY - rect.top;
      const px = host.scrollLeft + ax;
      const py = host.scrollTop + ay;
      const ratio = z / oldZoom;

      // Aperçu immédiat : on redimensionne les canvas existants (proportions conservées)
      const rendered = Number(host.dataset.renderedZoom) || oldZoom;
      const k = z / rendered;
      host.querySelectorAll("canvas.pdf-page").forEach((c) => {
        const w = Number(c.dataset.w) || c.clientWidth;
        const h = Number(c.dataset.h) || c.clientHeight;
        c.style.width = `${w * k}px`;
        c.style.height = `${h * k}px`;
      });
      host.scrollLeft = px * ratio - ax;
      host.scrollTop = py * ratio - ay;

      d.zoom = z;
      const lbl = document.getElementById("pdf-zoom-label");
      if (lbl) lbl.textContent = `${Math.round(z)}%`;

      // Re-rendu net une fois le geste terminé
      clearTimeout(setPdfZoom._t);
      setPdfZoom._t = setTimeout(() => renderPdfInViewer(d).catch(() => {}), 220);
    }

    // Ctrl + molette (ou pincement du pavé tactile) sur le document
    const pdfZoomHost = document.getElementById("doc-pdf-viewer");
    if (pdfZoomHost) {
      pdfZoomHost.addEventListener(
        "wheel",
        (e) => {
          if (!e.ctrlKey && !e.metaKey) return;
          e.preventDefault();
          const d = state.activeDocument;
            if (d) {
            const delta = Math.max(-40, Math.min(40, e.deltaY));
            setPdfZoom((d.zoom || 100) * Math.exp(-delta * 0.004), e.clientX, e.clientY);
          }
        },
        { passive: false }
      );
    }

    // Clic sur le pourcentage : retour à 100 %
    const zoomLabelEl = document.getElementById("pdf-zoom-label");
    if (zoomLabelEl) zoomLabelEl.addEventListener("click", () => setPdfZoom(100));

    // Ctrl + / Ctrl - / Ctrl 0 quand un document est ouvert
    window.addEventListener("keydown", (e) => {
      const d = state.activeDocument;
      if (!(e.ctrlKey || e.metaKey) || !d || d.type !== "pdf" || state.rightPanelMode !== "document") return;
      if (e.key === "+" || e.key === "=") { e.preventDefault(); setPdfZoom((d.zoom || 100) + 25); }
      else if (e.key === "-") { e.preventDefault(); setPdfZoom((d.zoom || 100) - 25); }
      else if (e.key === "0") { e.preventDefault(); setPdfZoom(100); }
    });

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

    if (state.inspectorTab === "activity") {
      const stopBtn = document.getElementById("btn-activity-stop");
      if (stopBtn) {
        stopBtn.addEventListener("click", () => {
          stopTaskExecution();
        });
      }
      const scrollBody = document.getElementById("activity-scroll-body");
      const resumeBtn = document.getElementById("btn-resume-scroll");
      if (scrollBody && resumeBtn) {
        scrollBody.addEventListener("scroll", () => {
          const atBottom = scrollBody.scrollHeight - scrollBody.scrollTop - scrollBody.clientHeight < 30;
          state.activityAutoScroll = atBottom;
          resumeBtn.style.display = atBottom ? "none" : "flex";
        });
        resumeBtn.addEventListener("click", () => {
          scrollBody.scrollTop = scrollBody.scrollHeight;
          state.activityAutoScroll = true;
          resumeBtn.style.display = "none";
        });
        if (state.activityAutoScroll) {
          scrollBody.scrollTop = scrollBody.scrollHeight;
        }
      }
      const devBtn = document.getElementById("btn-toggle-devmode");
      if (devBtn) {
        devBtn.addEventListener("click", async () => {
          const current = Boolean(state.appState.preferences && state.appState.preferences.developer_mode);
          await apiPost("/api/preferences", { developer_mode: !current });
          await refreshFullState();
        });
      }
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
      <button type="button" class="model-line" data-open-model-modal>
        <span>Modèle</span>
        <span class="model-line-value">${esc(compat.selection_mode === "auto" ? "Auto" : model ? model.display_name.split(" (")[0] : "—")} ›</span>
      </button>

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

  function getEventIconSvg(eventType, rawEvent) {
    const raw = (rawEvent || "").toLowerCase();
    const ev = (eventType || "").toLowerCase();
    if (raw.startsWith("search") || ev === "search") {
      return `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>`;
    }
    if (raw.startsWith("compile") || ev === "compilation") {
      return `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path></svg>`;
    }
    if (raw.startsWith("verify") || ev === "verifier") {
      return `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>`;
    }
    if (raw.startsWith("tool") || ev.startsWith("tool")) {
      return `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>`;
    }
    if (raw.startsWith("plan") || ev.startsWith("plan")) {
      return `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3" y1="6" x2="3.01" y2="6"></line><line x1="3" y1="12" x2="3.01" y2="12"></line><line x1="3" y1="18" x2="3.01" y2="18"></line></svg>`;
    }
    if (raw.includes("rollback") || raw.includes("failover") || ev === "rollback" || ev === "failover") {
      return `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="1 4 1 10 7 10"></polyline><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"></path></svg>`;
    }
    if (raw.startsWith("critic") || ev === "critic") {
      return `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v18M3 9l9-6 9 6M3 9v6l9 6 9-6V9"></path></svg>`;
    }
    return `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>`;
  }

  function renderInspectorActivityTab() {
    const s = state.appState;
    const events = (s.events || []).slice();
    const isDev = Boolean(s.preferences && s.preferences.developer_mode);
    const b = state.liveBudget || { tokens_used: 0, tokens_limit: 100000, time_elapsed: 0, time_limit: 300, tool_calls: 0, tool_limit: 50 };

    const tUsed = b.tokens_used || 0;
    const tMax = b.tokens_limit || 100000;
    const tPct = Math.min(100, Math.round((tUsed / (tMax || 1)) * 100));
    const tColor = tPct < 50 ? "green" : tPct <= 80 ? "orange" : "red";

    const timeUsed = b.time_elapsed || 0;
    const timeMax = b.time_limit || 300;
    const timePct = Math.min(100, Math.round((timeUsed / (timeMax || 1)) * 100));
    const timeColor = timePct < 50 ? "green" : timePct <= 80 ? "orange" : "red";

    const callsUsed = b.tool_calls || 0;
    const callsMax = b.tool_limit || 50;
    const callsPct = Math.min(100, Math.round((callsUsed / (callsMax || 1)) * 100));
    const callsColor = callsPct < 50 ? "green" : callsPct <= 80 ? "orange" : "red";

    return `
      <div class="activity-panel-wrap">
        <div class="activity-panel-header">
          <div class="activity-panel-title">
            <span>Panneau d'activité (${events.length})</span>
            ${state.isExecuting ? '<span class="step-badge in_progress"><span class="pulse-dot"></span>En direct</span>' : ''}
          </div>
          <div style="display:flex; align-items:center; gap:6px;">
            ${state.isExecuting ? `
              <button id="btn-activity-stop" class="activity-stop-btn" title="Interrompre immédiatement la tâche en cours">
                <span>Arrêter</span>
              </button>
            ` : ''}
            <button id="btn-toggle-devmode" class="skill-pill ${isDev ? "active" : ""}">
              ${isDev ? "● Mode Dev" : "○ Mode Dev"}
            </button>
          </div>
        </div>

        <!-- 1. JAUGES DE BUDGET TEMPS RÉEL -->
        <div class="budget-gauge-grid">
          <div class="budget-gauge-card">
            <div class="gauge-label-row"><span>Tokens</span><span>${tPct}%</span></div>
            <div class="gauge-value-row">${tUsed} / ${tMax}</div>
            <div class="gauge-bar"><div class="gauge-fill ${tColor}" style="width:${tPct}%;"></div></div>
          </div>
          <div class="budget-gauge-card">
            <div class="gauge-label-row"><span>Temps</span><span>${timePct}%</span></div>
            <div class="gauge-value-row">${timeUsed}s / ${timeMax}s</div>
            <div class="gauge-bar"><div class="gauge-fill ${timeColor}" style="width:${timePct}%;"></div></div>
          </div>
          <div class="budget-gauge-card">
            <div class="gauge-label-row"><span>Outils</span><span>${callsPct}%</span></div>
            <div class="gauge-value-row">${callsUsed} / ${callsMax}</div>
            <div class="gauge-bar"><div class="gauge-fill ${callsColor}" style="width:${callsPct}%;"></div></div>
          </div>
        </div>

        <!-- 2. SUIVI DU PLAN EN DIRECT -->
        ${state.livePlan && state.livePlan.length ? `
          <div class="live-plan-card">
            <div class="inspector-card-title"><span>Plan d'exécution en direct</span></div>
            ${state.livePlan.map((s, idx) => `
              <div class="plan-step-row">
                <span class="step-badge ${esc(s.status || 'pending')}">
                  ${s.status === 'in_progress' ? '<span class="pulse-dot"></span>En cours' : s.status === 'completed' ? '✓ Terminé' : s.status === 'error' ? '✕ Échoué' : 'À faire'}
                </span>
                <span><strong>${idx + 1}.</strong> ${esc(s.description)}</span>
              </div>
            `).join("")}
          </div>
        ` : ''}

        <!-- 3. COMPILATION EN DIRECT -->
        ${state.liveCompile ? `
          <div class="live-banner-box compile">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <strong>Compilation ${esc(state.liveCompile.attempt)}/${esc(state.liveCompile.max_attempts)}</strong>
              <span class="step-badge ${esc(state.liveCompile.status)}">${esc(state.liveCompile.status)}</span>
            </div>
            ${state.liveCompile.message ? `<div style="color:var(--error);">Erreur ligne ${esc(state.liveCompile.line || '?')} : ${esc(state.liveCompile.message)}</div>` : ''}
            ${state.liveCompile.note ? `<div style="color:var(--text-secondary);">Action : ${esc(state.liveCompile.note)}</div>` : ''}
          </div>
        ` : ''}

        <!-- 4. RECHERCHE WEB EN DIRECT -->
        ${state.liveSearch ? `
          <div class="live-banner-box search">
            <strong>Recherche & Téléchargement Web</strong>
            ${state.liveSearch.query ? `<div>Requête : <code>${esc(state.liveSearch.query)}</code></div>` : ''}
            ${state.liveSearch.rejected && state.liveSearch.rejected.length ? `
              <div style="font-size:10.5px; color:var(--text-muted);">
                Candidats rejetés (${state.liveSearch.rejected.length}) :
                ${state.liveSearch.rejected.map(r => `<div>- ${esc(r.url)} : ${esc(r.reason)}</div>`).join('')}
              </div>
            ` : ''}
            ${state.liveSearch.verified ? `
              <div style="color:#2b8a3e; font-weight:500;">
                ✓ Validé : <code>${esc(state.liveSearch.verified.destination)}</code> (${state.liveSearch.verified.size_bytes} octets)
              </div>
            ` : ''}
          </div>
        ` : ''}

        <!-- 5. TIMELINE DES ÉVÉNEMENTS TEMPS RÉEL -->
        <div id="activity-scroll-body" style="overflow-y:auto; max-height:480px; display:flex; flex-direction:column; gap:6px;">
          ${events.length === 0 ? `<div class="inspector-card">Aucune activité enregistrée.</div>` : events.map(e => {
            const rawStatus = (e.status || "info").toLowerCase();
            const badgeClass = rawStatus === "running" ? "in_progress" : rawStatus === "completed" || rawStatus === "success" || rawStatus === "ok" ? "completed" : rawStatus === "error" || rawStatus === "denied" ? "error" : "pending";
            const dur = e.duration_ms ? (e.duration_ms >= 1000 ? (e.duration_ms / 1000).toFixed(1) + "s" : e.duration_ms + "ms") : "";
            const detailsObj = e.data || e.details || {};
            const hasDetails = Object.keys(detailsObj).length > 0;
            return `
              <div class="timeline-item">
                <div class="timeline-head">
                  <div class="timeline-title-wrap">
                    <span class="timeline-icon-box">${getEventIconSvg(e.event, e.raw_event)}</span>
                    <span class="step-badge ${badgeClass}">${rawStatus === 'running' ? '<span class="pulse-dot"></span>' : ''}${esc(e.event)}</span>
                  </div>
                  <div style="display:flex; align-items:center; gap:6px;">
                    ${dur ? `<span class="timeline-duration">${esc(dur)}</span>` : ''}
                    <span class="mono" style="font-size:10px; color:var(--text-muted);">${esc((e.timestamp || "").slice(11, 19))}</span>
                  </div>
                </div>
                <div class="timeline-summary">${esc(e.summary)}</div>
                ${hasDetails ? `
                  <details class="timeline-collapsible">
                    <summary>Détails</summary>
                    <pre>${esc(JSON.stringify(detailsObj, null, 2))}</pre>
                  </details>
                ` : ''}
              </div>
            `;
          }).join("")}
        </div>
        <button id="btn-resume-scroll" class="scroll-resume-btn" style="display:none;">↓ Reprendre le défilement</button>
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
          <button type="button" class="sidebar-danger-btn" data-clear-workspace-files ${files.length === 0 ? "disabled" : ""} title="Supprimer tous les fichiers du workspace">
            <span>🗑 Tout supprimer</span>
          </button>
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
    if (id === "modal-library") renderLibraryModal();
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

    // Fenêtre modale de confirmation (remplace confirm()). Retourne true / false.
  function confirmModal({ title = "Confirmer", message = "", confirmLabel = "Supprimer", danger = true } = {}) {
    return new Promise((resolve) => {
      const modal = document.getElementById("modal-confirm");
      const okBtn = document.getElementById("confirm-ok");
      const cancelBtn = document.getElementById("confirm-cancel");
      if (!modal || !okBtn || !cancelBtn) {
        resolve(window.confirm(message)); // repli de sécurité
        return;
      }
      document.getElementById("confirm-title").textContent = title;
      document.getElementById("confirm-message").textContent = message;
      okBtn.textContent = confirmLabel;
      okBtn.classList.toggle("danger", danger);

      const finish = (value) => {
        modal.classList.remove("open");
        okBtn.removeEventListener("click", onOk);
        cancelBtn.removeEventListener("click", onCancel);
        modal.removeEventListener("mousedown", onBackdrop);
        document.removeEventListener("keydown", onKey, true);
        resolve(value);
      };
      const onOk = () => finish(true);
      const onCancel = () => finish(false);
      const onBackdrop = (e) => { if (e.target === modal) finish(false); };
      const onKey = (e) => {
        if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); finish(false); }
        else if (e.key === "Enter") {
          // Entrée active le bouton qui a le focus (Annuler par défaut), jamais la suppression à l'aveugle
          e.preventDefault();
          e.stopPropagation();
          finish(document.activeElement === okBtn);
        }
      };

      okBtn.addEventListener("click", onOk);
      cancelBtn.addEventListener("click", onCancel);
      modal.addEventListener("mousedown", onBackdrop);
      document.addEventListener("keydown", onKey, true);
      modal.classList.add("open");
      setTimeout(() => cancelBtn.focus(), 30); // focus sur Annuler par sécurité
    });
  }

  async function renderLibraryModal() {
    const body = document.getElementById("modal-library-body");
    if (!body) return;
    body.innerHTML = '<div style="text-align: center; padding: 24px; color: var(--text-muted);">Chargement de la bibliothèque du workspace…</div>';

    try {
      const res = await apiGet("/api/files");
      const files = (res && res.files) || (state.appState && state.appState.workspace && state.appState.workspace.files) || [];
      
      body.innerHTML = `
        <div class="library-search-box">
          <input type="text" id="library-search-input" class="library-search-input" placeholder="Filtrer les fichiers, templates, scripts (.tex, .py, .html, .csv)..." />
          <button type="button" class="btn-primary-mini" id="library-btn-upload-file">+ Importer</button>
        </div>
        <div class="library-file-list" id="library-file-list"></div>
      `;

      const listEl = document.getElementById("library-file-list");
      const searchInput = document.getElementById("library-search-input");
      const uploadBtn = document.getElementById("library-btn-upload-file");

      if (uploadBtn) {
        uploadBtn.addEventListener("click", () => {
          closeModal("modal-library");
          const fi = document.getElementById("composer-file-input");
          if (fi) {
            fi.accept = "";
            fi.click();
          }
        });
      }

      const renderList = (filter = "") => {
        const q = filter.trim().toLowerCase();
        const filtered = files.filter(f => !q || (f.path || f.name).toLowerCase().includes(q) || (f.extension || "").toLowerCase().includes(q));
        if (filtered.length === 0) {
          listEl.innerHTML = `<div style="padding: 24px; text-align: center; color: var(--text-muted); font-size: 13px;">Aucun fichier trouvé pour "${esc(filter)}".</div>`;
          return;
        }
        listEl.innerHTML = filtered.map(f => {
          const isAttached = state.attachedFiles.includes(f.path);
          const sizeKb = Math.round((f.size_bytes || 0) / 1024);
          const ext = (f.extension || "").replace(".", "").toUpperCase() || "FILE";
          return `
            <div class="library-file-item">
              <div class="library-file-info">
                <div class="library-file-name">
                  <span class="library-badge">${esc(ext)}</span>
                  <span>${esc(f.name || f.path)}</span>
                </div>
                <div class="library-file-meta">${esc(f.path)} • ${sizeKb} Ko</div>
              </div>
              <button type="button" class="btn-ghost-mini" data-attach-lib-file="${esc(f.path)}" style="${isAttached ? "color: var(--success); font-weight: 600;" : ""}">
                ${isAttached ? "✓ Attaché" : "+ Joindre"}
              </button>
            </div>
          `;
        }).join("");
      };

      if (searchInput) {
        searchInput.addEventListener("input", (e) => {
          renderList(e.target.value);
        });
      }

      listEl.addEventListener("click", (e) => {
        const btn = e.target.closest("[data-attach-lib-file]");
        if (!btn) return;
        const fpath = btn.getAttribute("data-attach-lib-file");
        if (!fpath) return;
        if (!state.attachedFiles.includes(fpath)) {
          state.attachedFiles.push(fpath);
          btn.innerHTML = "✓ Attaché";
          btn.style.color = "var(--success)";
          btn.style.fontWeight = "600";
          renderComposer();
        } else {
          state.attachedFiles = state.attachedFiles.filter(p => p !== fpath);
          btn.innerHTML = "+ Joindre";
          btn.style.color = "";
          btn.style.fontWeight = "";
          renderComposer();
        }
      });

      renderList("");
    } catch (err) {
      body.innerHTML = `<div style="color: var(--error); padding: 16px;">Erreur chargement bibliothèque : ${esc(String(err))}</div>`;
    }
  }


  function renderModelPickerModal() {
    const body = document.getElementById("modal-model-body");
    if (!body || !state.appState) return;
    const s = state.appState;
    const currentId = (s.model_selection && s.model_selection.selected_id) || "auto";

    const fmtCtx = (n) => {
      n = Number(n) || 0;
      return n >= 1e6 ? `${Math.round(n / 1e5) / 10}M` : n >= 1e3 ? `${Math.round(n / 1e3)}k` : "";
    };
    const family = (m) => {
      const t = `${m.id} ${m.display_name}`.toLowerCase();
      if (/gpt|openai/.test(t)) return "OpenAI";
      if (/mistral/.test(t)) return "Mistral";
      if (/ollama|qwen/.test(t)) return "Local";
      if (/claude/.test(t)) return "Anthropic";
      return "Google";
    };
    const KEEP = { Vision: "Vision", "Function Calling": "Outils", "Google Search Grounding": "Web", Raisonnement: "Raisonnement" };

    const row = (id, name, sub, selected, warn, tip) => `
      <div class="mp-row ${selected ? "selected" : ""}" data-pick-model="${esc(id)}" data-q="${esc((name + " " + id).toLowerCase())}" title="${esc(tip || "")}">
        <span class="mp-main">
          <span class="mp-name">${esc(name)}</span>
          ${sub ? `<span class="mp-sub ${warn ? "warn" : ""}">${esc(sub)}</span>` : ""}
        </span>
        <span class="mp-check">${selected ? "✓" : ""}</span>
      </div>`;

    const groups = {};
    (s.models || []).forEach((m) => {
      const caps = (m.capability_labels || []).map((c) => KEEP[c]).filter(Boolean);
      const ctx = fmtCtx(m.capabilities && m.capabilities.context);
      const parts = [ctx ? `${ctx} tokens` : "", ...caps].filter(Boolean);
      const sub = m.connected === false ? m.status_label || "Indisponible" : parts.join(" · ");
      (groups[family(m)] = groups[family(m)] || []).push(
        row(m.id, m.display_name.split(" (")[0], sub, currentId === m.id, m.connected === false, m.status_detail)
      );
    });

    body.innerHTML = `
      <input id="model-picker-search" type="search" class="mp-search" placeholder="Rechercher un modèle" autocomplete="off" />
      ${row("auto", "Auto", "Choisit le meilleur modèle pour chaque tâche", currentId === "auto", false, "")}
      ${["Google", "OpenAI", "Mistral", "Local", "Anthropic"]
        .filter((g) => groups[g])
        .map((g) => `<div class="mp-group">${g}</div>${groups[g].join("")}`)
        .join("")}
    `;

    const search = body.querySelector("#model-picker-search");
    search.addEventListener("input", () => {
      const q = search.value.trim().toLowerCase();
      let header = null;
      let seen = false;
      Array.from(body.children).forEach((el) => {
        if (el.classList.contains("mp-group")) {
          if (header) header.style.display = seen ? "" : "none";
          header = el;
          seen = false;
        } else if (el.classList.contains("mp-row")) {
          const ok = !q || el.dataset.q.includes(q);
          el.style.display = ok ? "" : "none";
          if (ok) seen = true;
        }
      });
      if (header) header.style.display = seen ? "" : "none";
    });
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
    state.streamShown = 0;
    state.streamAnchored = false;
    state.liveSteps = [];
    showOptimisticUserBubble(promptText.trim());
    paintStreamBody();
    kickTypewriter();
    const sc0 = document.getElementById("workspace-scroll");
    if (sc0) sc0.scrollTop = sc0.scrollHeight; // une seule fois : voir son message

    const sendBtn = document.getElementById("btn-send-task");
    if (sendBtn) {
      sendBtn.disabled = false;
      sendBtn.className = "send-btn stop-btn";
      sendBtn.title = "Arrêter l'exécution de la tâche en cours";
      sendBtn.innerHTML = `
        <span id="btn-send-task-text">Arrêter</span>
        <span id="btn-send-task-icon">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
            <rect x="4" y="4" width="16" height="16" rx="2"></rect>
          </svg>
        </span>
      `;
    }
    const statusEl = document.getElementById("top-task-status");
    const dotEl = document.getElementById("top-task-dot");
    if (statusEl) {
      statusEl.textContent = "Exécution…";
      statusEl.style.display = "inline";
    }
    if (dotEl) dotEl.className = "status-dot running";

    try {
      if (overridePrompt === undefined && inputEl) {
        inputEl.value = "";
        inputEl.style.height = "auto";
      }
      const attachments = [...state.attachedFiles];
      state.attachedFiles = [];

      const activeCid = (state.appState && state.appState.active_conversation && state.appState.active_conversation.id) || "";
      const runData = await apiPost("/api/tasks/run", {
        prompt: promptText.trim(),
        attachments: attachments,
        conversation_id: activeCid,
      });
      await drainTypewriter(1500);
      const scKeep = document.getElementById("workspace-scroll");
      const keepTop = scKeep ? scKeep.scrollTop : 0;
      await refreshFullState();
      if (scKeep) scKeep.scrollTop = keepTop;

      // Si un artefact PDF ou HTML vient d'être produit, ouvrir l'aperçu automatiquement
      const assistantMsg = (runData && (runData.assistant_message || runData.result)) || {};
      const artifacts =
        (runData && runData.preview_artifacts) ||
        assistantMsg.preview_artifacts ||
        assistantMsg.artifacts ||
        [];
      const previewArt = artifacts.find((a) => a && a.path);
      if (previewArt) {
        await openDocumentPreview(previewArt);
      } else if (assistantMsg.content) {
        const exportMatch = String(assistantMsg.content).match(/\[EXPORT OK\]\s+([^\s|]+\.(?:pdf|html|py|svg|mmd|mermaid|json|csv|md|png|jpg))/i);
        if (exportMatch) {
          await openDocumentPreview({ path: exportMatch[1].trim() });
        }
      }

      
    } catch (err) {
      showStatusBanner(`Erreur lors de l'exécution : ${err.message}`, "error");
    } finally {
      state.isExecuting = false;
      state.streamingBuffer = "";
      state.streamShown = 0;
      state.liveSteps = [];
      if (state.streamRaf) {
        cancelAnimationFrame(state.streamRaf);
        state.streamRaf = null;
      }
      const tempBubble = document.getElementById("streaming-assistant-card");
      if (tempBubble) tempBubble.remove();
      if (sendBtn) {
        sendBtn.disabled = false;
        sendBtn.className = "send-btn";
        sendBtn.title = "Envoyer (Entrée)";
        sendBtn.innerHTML = `
          <span id="btn-send-task-text">Envoyer</span>
          <span id="btn-send-task-icon">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <line x1="12" y1="19" x2="12" y2="5"></line>
              <polyline points="5 12 12 5 19 12"></polyline>
            </svg>
          </span>
        `;
      }
      renderTopBar();
    }
  }

  async function stopTaskExecution() {
    try {
      const sendBtn = document.getElementById("btn-send-task");
      if (sendBtn) {
        sendBtn.innerHTML = "<span>Arrêt…</span>";
      }
      await apiPost("/api/tasks/stop", {});
      const statusEl = document.getElementById("top-task-status");
      const dotEl = document.getElementById("top-task-dot");
      if (statusEl) {
        statusEl.textContent = "Arrêté";
        statusEl.style.display = "inline";
      }
      if (dotEl) dotEl.className = "status-dot warning";
      showStatusBanner("Arrêt demandé par l'utilisateur.", "info");
      await refreshFullState();
    } catch (e) {
      console.warn("Erreur stop task:", e);
    }
  }

  async function handleFilesUpload(fileList) {
    if (!fileList || fileList.length === 0) return;
    const files = Array.from(fileList);
    let okCount = 0;

    for (const file of files) {
      showStatusBanner(`Téléversement de ${file.name}…`, "info");
      const isText =
        (file.type || "").startsWith("text/") ||
        /\.(txt|md|py|js|ts|json|yaml|yml|csv|tex|html|css)$/i.test(file.name);

      try {
        const payload = { filename: file.name };
        if (isText) {
          payload.content_text = await file.text();
        } else {
          const dataUrl = await new Promise((resolve, reject) => {
            const r = new FileReader();
            r.onload = () => resolve(String(r.result));
            r.onerror = () => reject(new Error("Lecture du fichier impossible"));
            r.readAsDataURL(file);
          });
          payload.content_base64 = dataUrl.split(",")[1] || "";
        }
        const res = await apiPost("/api/files/upload", payload);
        const p = (res && res.path) || `uploads/${file.name}`;
        if (!state.attachedFiles.includes(p)) state.attachedFiles.push(p);
        okCount++;
      } catch (err) {
        showStatusBanner(`Échec du téléversement de ${file.name} : ${err.message}`, "error");
        console.warn("Upload error:", err);
      }
      renderComposerControls(); // la pastille apparaît fichier par fichier
    }

    if (okCount === files.length) showStatusBanner("", "info");
  }

  // =========================================================================
  // ÉVÉNEMENTS DOM & INTERACTIONS
  // =========================================================================

  function setupEventListeners() {
    document.getElementById("btn-toggle-sidebar").addEventListener("click", () => {
      document.getElementById("left-sidebar").classList.toggle("collapsed");
    });
    const toggleInspBtn = document.getElementById("btn-toggle-inspector");
    if (toggleInspBtn) {
      toggleInspBtn.addEventListener("click", () => {
        toggleRightPanel();
      });
    }
    const closeInspBtn = document.getElementById("btn-close-inspector");
    if (closeInspBtn) {
      closeInspBtn.addEventListener("click", closeRightPanel);
    }

    // Boutons de la barre d'aperçu de document (PDF / HTML)
    const btnCloseDoc = document.getElementById("btn-close-doc-preview");
    if (btnCloseDoc) {
      btnCloseDoc.addEventListener("click", closeDocumentPreview);
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
    const btnViewFiles = document.getElementById("btn-doc-view-files");
    if (btnViewFiles) {
      btnViewFiles.addEventListener("click", () => {
        if (state.activeDocument) {
          state.activeDocument.viewMode = "files";
          renderDocumentPreviewPanel();
        }
      });
    }
    const btnViewConsole = document.getElementById("btn-doc-view-console");
    if (btnViewConsole) {
      btnViewConsole.addEventListener("click", () => {
        if (state.activeDocument) {
          state.activeDocument.viewMode = "console";
          renderDocumentPreviewPanel();
        }
      });
    }
    const btnZoomOut = document.getElementById("btn-pdf-zoom-out");
    if (btnZoomOut) {
      btnZoomOut.addEventListener("click", () => {
        if (state.activeDocument && state.activeDocument.type === "pdf") {
          setPdfZoom((state.activeDocument.zoom || 100) - 25);
        }
      });
    }
    const btnZoomIn = document.getElementById("btn-pdf-zoom-in");
    if (btnZoomIn) {
      btnZoomIn.addEventListener("click", () => {
        if (state.activeDocument && state.activeDocument.type === "pdf") {
          setPdfZoom((state.activeDocument.zoom || 100) + 25);
        }
      });
    }
    const btnDocRefresh = document.getElementById("btn-doc-refresh");
    if (btnDocRefresh) {
      btnDocRefresh.addEventListener("click", () => {
        if (state.activeDocument) {
          if (state.activeDocument.type === "html") {
            const htmlFrame = document.getElementById("doc-html-frame");
            if (htmlFrame && state.activeDocument.viewMode === "render") {
              const cleanPath = state.activeDocument.path.split("/").map(encodeURIComponent).join("/");
              htmlFrame.src = `/api/preview/workspace/${cleanPath}?t=${Date.now()}`;
            }
          }
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
        if (doc.type === "python") {
          try {
            const res = await apiPost("/api/artifacts/execute", { path: doc.path });
            if (res.artifact) {
              doc.execution = res.artifact.execution;
              doc.output_paths = res.artifact.output_paths || [];
              doc.error = res.artifact.error || null;
              doc.metadata = res.artifact.metadata || doc.metadata;
              await refreshFullState();
              renderDocumentPreviewPanel();
              showStatusBanner("✓ Script Python exécuté", "success");
            }
          } catch (err) {
            showStatusBanner(`Erreur d'exécution : ${err.message}`, "error");
          }
          return;
        }
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
          if (doc.type === "html") {
            const comp = await apiPost("/api/files/compile-html", { path: doc.path, content: editor.value });
            doc.sourceContent = editor.value;
            doc.viewMode = "render";
            doc.error = null;
            await refreshFullState();
            renderDocumentPreviewPanel();
            showStatusBanner(`✓ Page HTML validée et actualisée (${comp.size_bytes || editor.value.length} octets)`, "success");
          } else if (doc.type === "tex") {
            doc.sourceContent = editor.value;
            await apiPost("/api/files/write", { path: doc.path, content: editor.value });
            await compileLatexAndPreview(doc.path, editor.value);
            showStatusBanner("✓ Source LaTeX enregistrée et compilée", "success");
          } else {
            const res = await apiPost("/api/artifacts/process", { path: doc.path, content: editor.value });
            doc.sourceContent = editor.value;
            if (res.artifact) {
              doc.execution = res.artifact.execution;
              doc.output_paths = res.artifact.output_paths || [];
              doc.error = res.artifact.error || null;
            }
            doc.viewMode = "render";
            await refreshFullState();
            renderDocumentPreviewPanel();
            showStatusBanner("✓ Artefact mis à jour et validé", "success");
          }
        } catch (err) {
          showStatusBanner(`Erreur de validation/enregistrement : ${err.message}`, "error");
          doc.error = err.message;
          renderDocumentPreviewPanel();
        }
      });
    }

    // Capture des erreurs d'exécution JavaScript depuis l'iframe de prévisualisation HTML
    window.addEventListener("message", (event) => {
      if (!event.data || event.data.type !== "NEOHARNESS_HTML_RUNTIME_ERROR") return;
      const err = event.data.error || {};
      const noticeEl = document.getElementById("doc-preview-notice");
      if (noticeEl) {
        noticeEl.style.display = "flex";
        noticeEl.className = "doc-preview-notice doc-runtime-error-banner";
        noticeEl.innerHTML = `
          <div style="flex: 1; min-width: 0;">
            <strong>⚠️ Erreur d'exécution JS :</strong> ${esc(err.message)}
            ${err.lineno ? `<span class="mono" style="opacity: 0.85; margin-left: 4px;">(ligne ${err.lineno})</span>` : ""}
          </div>
          <button type="button" id="btn-fix-runtime-error" class="composer-chip-btn" style="margin-left: 8px; flex-shrink: 0;">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M12 20h9"></path>
              <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
            </svg>
            <span>Corriger avec l'IA</span>
          </button>
        `;
        const btnFix = document.getElementById("btn-fix-runtime-error");
        if (btnFix) {
          btnFix.addEventListener("click", () => {
            const doc = state.activeDocument;
            const promptText = `Corrige l'erreur JavaScript d'exécution suivante sur ${doc ? doc.path : "la page HTML"} :\nMessage: ${err.message}\n${err.lineno ? `Ligne: ${err.lineno}\n` : ""}${err.stack ? `Stack: ${err.stack}\n` : ""}`;
            const inputEl = document.getElementById("composer-input");
            if (inputEl) {
              inputEl.value = promptText;
              submitComposerTask();
            }
          });
        }
      }
    });

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
        // --- Supprimer TOUTES les discussions ---
    const btnDelAllConvs = document.getElementById("btn-delete-all-convs");
    if (btnDelAllConvs) {
      btnDelAllConvs.addEventListener("click", async () => {
        const convs = (state.appState && state.appState.conversations) || [];
        if (convs.length === 0) {
          showStatusBanner("Aucune discussion à supprimer.", "info");
          return;
        }
        if (!(await confirmModal({
          title: "Supprimer toutes les discussions ?",
          message: `${convs.length} discussion(s) seront supprimées définitivement. Cette action est irréversible.`,
          confirmLabel: "Tout supprimer",
        }))) return;
        btnDelAllConvs.disabled = true;
        try {
          await apiPost("/api/conversations/clear", {});
          await refreshFullState();
          showStatusBanner("Toutes les discussions ont été supprimées.", "info");
        } catch (err) {
          showStatusBanner(`Suppression impossible : ${err.message}`, "error");
        } finally {
          btnDelAllConvs.disabled = false;
        }
      });
    }

    // --- Supprimer TOUS les fichiers du workspace (onglet Fichiers) ---
    document.body.addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-clear-workspace-files]");
      if (!btn || btn.disabled) return;
      const count = ((state.appState && state.appState.workspace && state.appState.workspace.files) || []).length;
      if (!(await confirmModal({
        title: "Supprimer tous les fichiers ?",
        message: `${count} fichier(s) du workspace (PDF, exports, uploads…) seront supprimés définitivement.`,
        confirmLabel: "Tout supprimer",
      }))) return;
      btn.disabled = true;
      try {
        const res = await apiPost("/api/files/clear", {});
        state.selectedFilePreview = null;
        state.attachedFiles = [];
        if (state.activeDocument) {
          state.activeDocument = null;
          state.pdfDocCache = null;
          closeRightPanel();
        }
        await refreshFullState();
        showStatusBanner(`${(res && res.deleted) || count} fichier(s) supprimé(s).`, "info");
      } catch (err) {
        btn.disabled = false;
        showStatusBanner(`Suppression impossible : ${err.message}`, "error");
      }
    });

    document.getElementById("sidebar-filter-input").addEventListener("input", (e) => {
      state.sidebarFilter = e.target.value || "";
      renderSidebar();
    });

    document.getElementById("btn-open-model-picker").addEventListener("click", () => {
      openModal("modal-model-picker");
    });
    const taskPill = document.getElementById("top-task-pill");
    if (taskPill) {
      taskPill.addEventListener("click", () => {
        state.inspectorTab = "activity";
        switchRightPanelMode("inspector");
        renderInspector();
      });
    }
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
        if (state.isExecuting) {
          stopTaskExecution();
        } else {
          submitComposerTask();
        }
      }
    });

    // Auto-grow textarea up to 200px
    composerInput.addEventListener("input", () => {
      composerInput.style.height = "auto";
      const newH = Math.min(Math.max(composerInput.scrollHeight, 40), 200);
      composerInput.style.height = `${newH}px`;
    });

    document.getElementById("btn-send-task").addEventListener("click", () => {
      if (state.isExecuting) {
        stopTaskExecution();
        return;
      }
      submitComposerTask();
    });

    // Menu déroulant Topbar (Thème, Réglages, À propos)
    const topMenuBtn = document.getElementById("btn-topbar-menu");
    const topMenuDropdown = document.getElementById("topbar-menu-dropdown");
    if (topMenuBtn && topMenuDropdown) {
      topMenuBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        const isOpen = topMenuDropdown.style.display !== "none";
        topMenuDropdown.style.display = isOpen ? "none" : "flex";
      });
      document.addEventListener("click", (e) => {
        if (!topMenuDropdown.contains(e.target) && !topMenuBtn.contains(e.target)) {
          topMenuDropdown.style.display = "none";
        }
      });
    }

    // Popover de gouvernance compact (Auto, Edit, Plan, Accept)
    const govBtn = document.getElementById("btn-composer-governance");
    const govDropdown = document.getElementById("governance-dropdown");
    if (govBtn && govDropdown) {
      govBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        const isOpen = govDropdown.style.display !== "none";
        govDropdown.style.display = isOpen ? "none" : "flex";
      });
      document.addEventListener("click", (e) => {
        if (!govDropdown.contains(e.target) && !govBtn.contains(e.target)) {
          govDropdown.style.display = "none";
        }
      });
      govDropdown.querySelectorAll(".governance-option").forEach((opt) => {
        opt.addEventListener("click", async () => {
          const mode = opt.getAttribute("data-mode");
          govDropdown.querySelectorAll(".governance-option").forEach((o) => o.classList.remove("active"));
          opt.classList.add("active");
          const chipLabel = document.getElementById("governance-chip-label");
          if (chipLabel) chipLabel.textContent = mode;
          const modeSel = document.getElementById("composer-mode-select");
          if (modeSel) {
            modeSel.value = mode;
            modeSel.dispatchEvent(new Event("change"));
          }
          await apiPost("/api/mode", { mode: mode });
          govDropdown.style.display = "none";
        });
      });
    }

    // Drag and Drop & Collage (Ctrl+V) d'images et fichiers
    const composerBox = document.getElementById("composer-box");
    if (composerBox && composerInput) {
      composerBox.addEventListener("dragover", (e) => {
        e.preventDefault();
        composerBox.classList.add("dragover");
      });
      composerBox.addEventListener("dragleave", (e) => {
        e.preventDefault();
        composerBox.classList.remove("dragover");
      });
      composerBox.addEventListener("drop", async (e) => {
        e.preventDefault();
        composerBox.classList.remove("dragover");
        if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
          await handleFilesUpload(e.dataTransfer.files);
        }
      });
      composerInput.addEventListener("paste", async (e) => {
        const items = (e.clipboardData || window.clipboardData)?.items;
        if (!items) return;
        const filesToUpload = [];
        for (let i = 0; i < items.length; i++) {
          if (items[i].kind === "file") {
            const f = items[i].getAsFile();
            if (f) filesToUpload.push(f);
          }
        }
        if (filesToUpload.length > 0) {
          e.preventDefault();
          await handleFilesUpload(filesToUpload);
        }
      });
    }

    // Menu + & Téléversement de pièces jointes
    const attachBtn = document.getElementById("btn-attach-file");
    const plusMenu = document.getElementById("composer-plus-menu");
    const fileInput = document.getElementById("composer-file-input");
    if (attachBtn && fileInput) {
      if (plusMenu) {
        attachBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          const isVis = plusMenu.style.display === "flex";
          plusMenu.style.display = isVis ? "none" : "flex";
        });
        document.addEventListener("click", (e) => {
          if (plusMenu.style.display !== "none" && !plusMenu.contains(e.target) && !attachBtn.contains(e.target)) {
            plusMenu.style.display = "none";
          }
        });
      } else {
        attachBtn.addEventListener("click", () => {
          fileInput.click();
        });
      }
      fileInput.addEventListener("change", async (e) => {
        if (e.target.files && e.target.files.length > 0) {
          await handleFilesUpload(e.target.files);
          e.target.value = "";
          fileInput.accept = "";
        }
      });

      const plusActions = {
        "plus-action-upload": () => {
          fileInput.accept = "";
          fileInput.click();
        },
        "plus-action-library": () => {
          openModal("modal-library");
        },
        "plus-action-image": () => {
          fileInput.accept = "image/*";
          fileInput.click();
        },
        "plus-action-web": () => {
          const inp = document.getElementById("composer-input");
          if (inp) {
            inp.value = "Recherche sur le web : " + inp.value;
            inp.focus();
          }
        },
        "plus-action-deep-search": () => {
          const inp = document.getElementById("composer-input");
          if (inp) {
            inp.value = "/analyze " + inp.value;
            inp.focus();
          }
        },
        "plus-action-thinking": async () => {
          const sel = document.getElementById("composer-mode-select");
          if (sel) sel.value = "PLAN";
          await apiPost("/api/mode", { mode: "PLAN" });
          await refreshFullState();
          showStatusBanner("Mode Réflexion approfondie (PLAN) activé", "info");
        },
        "plus-action-pdf": () => {
          const inp = document.getElementById("composer-input");
          if (inp) {
            inp.value = "/bacblanc " + inp.value;
            inp.focus();
          }
        },
        "plus-action-diagram": () => {
          const inp = document.getElementById("composer-input");
          if (inp) {
            inp.value = "Génère un diagramme Mermaid détaillé pour : " + inp.value;
            inp.focus();
          }
        },
        "plus-action-docs": () => {
          const inp = document.getElementById("composer-input");
          if (inp) {
            inp.value = "Rédige un document structuré et complet sur : " + inp.value;
            inp.focus();
          }
        },
        "plus-action-sheets": () => {
          const inp = document.getElementById("composer-input");
          if (inp) {
            inp.value = "Génère un jeu de données CSV complet et analyse : " + inp.value;
            inp.focus();
          }
        },
        "plus-action-slides": () => {
          const inp = document.getElementById("composer-input");
          if (inp) {
            inp.value = "Crée une présentation Web interactive en HTML/CSS/JS sur : " + inp.value;
            inp.focus();
          }
        },
        "plus-action-templates": () => {
          openModal("modal-library");
          setTimeout(() => {
            const q = document.getElementById("library-search-input");
            if (q) {
              q.value = "template";
              q.dispatchEvent(new Event("input"));
            }
          }, 50);
        },
      };

      Object.entries(plusActions).forEach(([aid, ahandler]) => {
        const el = document.getElementById(aid);
        if (el) {
          el.addEventListener("click", async (e) => {
            e.stopPropagation();
            if (plusMenu) plusMenu.style.display = "none";
            await ahandler();
          });
        }
      });
    }

    // Badge créateur sidebar -> ouvre Réglages / À propos
    const aboutBtn = document.getElementById("btn-sidebar-about");
    if (aboutBtn) {
      aboutBtn.addEventListener("click", () => {
        openModal("modal-settings");
      });
    }

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
        try {
          await apiPost("/api/conversations/select", { id: target.getAttribute("data-select-conv") });
        } catch (_) {}
        await refreshFullState();
        return;
      }
      if (target.hasAttribute("data-pin-conv")) {
        e.stopPropagation();
        const cid = target.getAttribute("data-pin-conv");
        const pinned = target.getAttribute("data-pinned") !== "1";
        try {
          await apiPost("/api/conversations/update", { id: cid, pinned });
        } catch (_) {}
        await refreshFullState();
        return;
      }
      if (target.hasAttribute("data-rename-conv")) {
        e.stopPropagation();
        const cid = target.getAttribute("data-rename-conv");
        const oldTitle = target.getAttribute("data-title") || "";
        const newTitle = prompt("Nouveau titre :", oldTitle);
        if (newTitle && newTitle.trim()) {
          try {
            await apiPost("/api/conversations/update", { id: cid, title: newTitle.trim() });
          } catch (_) {}
          await refreshFullState();
        }
        return;
      }
      if (target.hasAttribute("data-delete-conv")) {
        e.stopPropagation();
        const cid = target.getAttribute("data-delete-conv");
        const convToDelete = ((state.appState && state.appState.conversations) || []).find((c) => c.id === cid);
        if (!(await confirmModal({
          title: "Supprimer cette discussion ?",
          message: `« ${(convToDelete && convToDelete.title) || "Discussion"} » sera supprimée définitivement.`,
          confirmLabel: "Supprimer",
        }))) return;
        try {
          await apiPost("/api/conversations/delete", { id: cid });
        } catch (_) {}
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
        const typ = detectArtifactType(fpath);
        if (typ !== "unknown") {
          await openDocumentPreview({ type: typ, path: fpath });
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
        toggleRightPanel();
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

        const pdfHost = document.getElementById("doc-pdf-viewer");
    if (pdfHost && window.ResizeObserver) {
      let t = null;
      new ResizeObserver(() => {
        clearTimeout(t);
        t = setTimeout(() => {
          const d = state.activeDocument;
          if (d && d.type === "pdf" && d.viewMode === "render" && !d.error && pdfHost.clientWidth > 0 && Math.abs(pdfHost.clientWidth - state.pdfWidth) > 24) {
            renderPdfInViewer(d).catch(() => {});
          }
        }, 200);
      }).observe(pdfHost);
    }

    document.body.addEventListener("click", (e) => {
      if (e.target.closest("[data-open-model-modal]")) openModal("modal-model-picker");
    });

    setupPanelResizers();
  }

  function setupPanelResizers() {
    const area = document.querySelector(".main-area");
    const sidebar = document.getElementById("left-sidebar");
    const inspector = document.getElementById("right-inspector");
    const MIN = 320;

    function bind(handle, side) {
      if (!handle) return;
      handle.addEventListener("pointerdown", (e) => {
        e.preventDefault();
        handle.setPointerCapture(e.pointerId);
        handle.classList.add("active");
        document.body.classList.add("is-resizing");
      });
      handle.addEventListener("pointermove", (e) => {
        if (!handle.hasPointerCapture(e.pointerId)) return;
        const rect = area.getBoundingClientRect();
        if (side === "left") {
          sidebar.style.width = `${Math.max(200, Math.min(360, e.clientX - rect.left))}px`;
        } else {
          const sbW = sidebar.classList.contains("collapsed") ? 0 : sidebar.offsetWidth;
          const max = Math.max(MIN, rect.width - sbW - MIN);
          const w = Math.max(MIN, Math.min(max, rect.right - e.clientX));
          inspector.style.width = `${w}px`;
          if (state.rightPanelMode === "document") state.docWidth = w;
        }
      });
      const end = () => {
        handle.classList.remove("active");
        document.body.classList.remove("is-resizing");
      };
      handle.addEventListener("pointerup", end);
      handle.addEventListener("pointercancel", end);
      handle.addEventListener("lostpointercapture", end);
    }

    bind(document.getElementById("resizer-left"), "left");
    bind(document.getElementById("resizer-right"), "right");
  }

  // Exposer les fonctions critiques globalement pour une invocation immédiate sans délai
  window.toggleRightPanel = toggleRightPanel;
  window.closeRightPanel = closeRightPanel;
  window.switchRightPanelMode = switchRightPanelMode;

  async function boot() {
    initTheme();
    setupEventListeners();
    await refreshFullState();
    try {
      const runState = await apiGet("/api/runs/current");
      if (runState && runState.ok) {
        if (runState.plan && runState.plan.length) state.livePlan = runState.plan;
        if (runState.budget) state.liveBudget = Object.assign({}, state.liveBudget, runState.budget);
        if (runState.compilation && Object.keys(runState.compilation).length) state.liveCompile = runState.compilation;
        if (runState.search && Object.keys(runState.search).length) state.liveSearch = runState.search;
        if (runState.last_seq) state.lastEventSeq = runState.last_seq;
        if (runState.status === "Exécution…" || runState.status === "running") {
          state.isExecuting = true;
        }
      }
    } catch (_) {}
    connectSSE();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
