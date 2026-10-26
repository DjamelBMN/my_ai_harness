/* RÔLE DE CE FICHIER :
 * Logique frontend minimaliste et complète de NeoHarness AI (Complexité cachée, Zéro simulation).
 * Pilote :
 * 1. Le Mode Clair premium par défaut (avec persistance localStorage et bascule Sombre/Clair vectorielle)
 * 2. La palette flottante immédiate des 20 Slash Commands (/) dans l'ordre canonique
 * 3. Le panneau latéral droit unifié : Aperçu Document (PDF compilé via Tectonic & HTML sandboxé) + Inspecteur
 * 4. La dictée vocale style GPT avec onde audio temps réel (Web Audio API AnalyserNode + SpeechRecognition)
 * 5. Le streaming SSE temps réel (STREAM_DELTA, ARTIFACT_READY) avec mise en scène de la réflexion multi-agents
 */

(function () {
  "use strict";

  const ICONS = {
    brain: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-2.04"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-2.04"/></svg>',
    chatMode: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>',
    monoAgent: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="11" width="18" height="10" rx="3"></rect><circle cx="12" cy="5" r="2"></circle><path d="M12 7v4"></path><line x1="8" y1="16" x2="8.01" y2="16" stroke-width="2.5"></line><line x1="16" y1="16" x2="16.01" y2="16" stroke-width="2.5"></line></svg>',
    multiAgent: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-2.04"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-2.04"/></svg>',
    sun: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>',
    moon: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>',
    check: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>',
    close: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>',
    chevronDown: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="6 9 12 15 18 9"></polyline></svg>',
    chevronRight: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="9 18 15 12 9 6"></polyline></svg>',
    arrowDown: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"></line><polyline points="19 12 12 19 5 12"></polyline></svg>',
    pin: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="17" x2="12" y2="22"></line><path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1v4.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24Z"></path></svg>',
    edit: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>',
    trash: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path><path d="M10 11v6M14 11v6"></path><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"></path></svg>',
    paperclip: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path></svg>',
    download: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>',
    bolt: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>',
    globe: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>',
    search: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>',
    tool: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path></svg>',
    alert: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
    folder: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>',
    cpu: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="2"></rect><rect x="9" y="9" width="6" height="6"></rect><line x1="9" y1="1" x2="9" y2="4"></line><line x1="15" y1="1" x2="15" y2="4"></line><line x1="9" y1="20" x2="9" y2="23"></line><line x1="15" y1="20" x2="15" y2="23"></line><line x1="20" y1="9" x2="23" y2="9"></line><line x1="20" y1="14" x2="23" y2="14"></line><line x1="1" y1="9" x2="4" y2="9"></line><line x1="1" y1="14" x2="4" y2="14"></line></svg>',
    sparkle: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3l1.912 5.813a2 2 0 0 0 1.275 1.275L21 12l-5.813 1.912a2 2 0 0 0-1.275 1.275L12 21l-1.912-5.813a2 2 0 0 0-1.275-1.275L3 12l5.813-1.912a2 2 0 0 0 1.275-1.275L12 3Z"></path></svg>',
    agent: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>',
    filePdf: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg>',
    fileCode: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><polyline points="10 13 8 15 10 17"></polyline><polyline points="14 13 16 15 14 17"></polyline></svg>',
    fileImage: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>',
    fileTable: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line><line x1="3" y1="15" x2="21" y2="15"></line><line x1="9" y1="3" x2="9" y2="21"></line></svg>',
    fileChart: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="1.5"></rect><rect x="14" y="14" width="7" height="7" rx="1.5"></rect><path d="M10 6.5h4a3 3 0 0 1 3 3V14"></path></svg>',
    external: '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>',
    dotHollow: '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" aria-hidden="true"><circle cx="12" cy="12" r="8"></circle></svg>',
    dotFilled: '<svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><circle cx="12" cy="12" r="7"></circle></svg>',
  };

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
    activeDocument: null,
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
    liveStartedAt: 0,
    liveTimerInterval: null,
    activeSubAgent: "",
    liveCollapsedOnce: false,
    toastTimer: null,
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

  function isHiddenInternalPath(p) {
    const norm = String(p || "").replace(/\\/g, "/").replace(/^\/+/, "");
    return (
      norm.startsWith(".harness/") ||
      norm.startsWith(".neoharness/") ||
      norm === ".harness" ||
      norm === ".neoharness"
    );
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
  // 0. THÈME CLAIR PAR DÉFAUT & PERSISTANCE LOCALSTORAGE (ICÔNES VECTORIELLES)
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
      iconEl.innerHTML = normalized === "light" ? ICONS.sun : ICONS.moon;
    }
    const labelEl = document.getElementById("theme-label-text");
    if (labelEl) {
      labelEl.textContent = normalized === "light" ? "Passer au thème sombre" : "Passer au thème clair";
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
              finishThinkingSteps(true);
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
    "STREAM_DELTA",
    "TASK_STARTED",
    "TASK_COMPLETED",
    "CONTEXT_LOADING",
    "MEMORY_RETRIEVAL",
    "SKILL_DISCOVERY",
    "MODEL_SELECTED",
    "MODE_CHANGED",
    "TASK_CONTEXT_UPDATED",
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

  // Traduction sémantique d'un appel d'outil en intention humaine claire
  function humanizeToolStep(toolName, rawTarget, rawDetails) {
    const t = String(toolName || "").trim();
    let cleanedTarget = String(rawTarget || "").trim();
    cleanedTarget = cleanedTarget.replace(/^\[path=([^\]]+)\]$/i, "$1").replace(/^path=/i, "");

    const map = {
      list_files: {
        label: "Exploration de l'arborescence du workspace",
        pill: cleanedTarget && cleanedTarget !== "." ? cleanedTarget : "",
      },
      read_file: {
        label: "Analyse du fichier",
        pill: cleanedTarget || (rawDetails && rawDetails.path) || "",
      },
      read_document: {
        label: "Extraction documentaire",
        pill: cleanedTarget || (rawDetails && rawDetails.path) || "",
      },
      find_file: {
        label: "Recherche de fichiers correspondants",
        pill: cleanedTarget || "",
      },
      search_files: {
        label: "Recherche lexicale dans le code",
        pill: cleanedTarget || (rawDetails && rawDetails.query) || "",
      },
      write_file: {
        label: "Rédaction et écriture du fichier",
        pill: cleanedTarget || (rawDetails && rawDetails.path) || "",
      },
      patch_file: {
        label: "Modification ciblée du fichier",
        pill: cleanedTarget || (rawDetails && rawDetails.path) || "",
      },
      delete_file: {
        label: "Suppression du fichier",
        pill: cleanedTarget || "",
      },
      web_search: {
        label: "Investigation Web en direct",
        pill: cleanedTarget || (rawDetails && rawDetails.query) || "",
      },
      fetch_url: {
        label: "Lecture de source Web",
        pill: cleanedTarget || "",
      },
      download_file: {
        label: "Téléchargement et vérification de ressource",
        pill: cleanedTarget || "",
      },
      tectonic: {
        label: "Compilation LaTeX certifiée via Tectonic",
        pill: cleanedTarget || (rawDetails && rawDetails.path) || "",
      },
      html_compiler: {
        label: "Validation et compilation HTML5 / JS",
        pill: cleanedTarget || (rawDetails && rawDetails.path) || "",
      },
      run_python: {
        label: "Exécution du script Python",
        pill: cleanedTarget || "",
      },
      run_tests: {
        label: "Exécution de la suite de tests",
        pill: cleanedTarget || "",
      },
      delegate_to_agent: {
        label: "Délégation à un agent spécialisé",
        pill: cleanedTarget || "",
      },
    };

    if (map[t]) {
      return map[t];
    }
    return {
      label: `Action : ${t.replace(/_/g, " ")}`,
      pill: cleanedTarget.slice(0, 70),
    };
  }

  function humanizeEventBadge(eventCode) {
    const code = String(eventCode || "").toUpperCase();
    const map = {
      TASK_STARTED: "Démarrage",
      PLANNER_STARTED: "Planification",
      PLAN_CREATED: "Plan établi",
      PLAN_STEP: "Étape du plan",
      CONTEXT_LOADING: "Contexte",
      MEMORY_RETRIEVAL: "Mémoire",
      SKILL_DISCOVERY: "Skills",
      RAG_SEARCH: "Recherche RAG",
      TOOL_CALL: "Action outil",
      TOOL_RESULT: "Résultat outil",
      AGENT_STEP: "Progression",
      COMPILATION: "Compilation",
      SEARCH: "Recherche Web",
      DOWNLOAD: "Téléchargement",
      VERIFIER: "Vérification",
      ARTIFACT_READY: "Livrable prêt",
      APPROVAL_REQUIRED: "Validation requise",
      MODEL_SELECTED: "Modèle",
      MODE_CHANGED: "Gouvernance",
      TASK_COMPLETED: "Terminé",
      TASK_STOPPED: "Interrompu",
      TASK_CONTEXT_UPDATED: "Contexte mis à jour",
      ERROR: "Erreur",
    };
    return map[code] || code;
  }

  function finishThinkingSteps(collapseIfStreaming) {
    let changed = false;
    // Supprimer les étapes "Réflexion…" génériques terminées pour ne garder que les vraies actions intellectuelles
    for (let i = state.liveSteps.length - 1; i >= 0; i--) {
      if (state.liveSteps[i].kind === "think") {
        state.liveSteps.splice(i, 1);
        changed = true;
      } else if (collapseIfStreaming && state.liveSteps[i].status === "running") {
        state.liveSteps[i].status = "done";
        changed = true;
      }
    }
    if (collapseIfStreaming && !state.liveCollapsedOnce && state.liveSteps.length > 0) {
      state.liveCollapsedOnce = true;
      const tracker = document.getElementById("live-activity");
      if (tracker) {
        tracker.removeAttribute("open");
      }
    }
    if (changed) renderLiveSteps();
  }

  function handleLiveEvent(e) {
    if (!e) return;
    const raw = e.raw_event || e.type || e.event || "";
    const data = e.data || e.details || {};

    if (raw === "plan.created" || e.event === "PLAN_CREATED") {
      const rawSteps = data.plan_steps || data.steps || [];
      state.livePlan = rawSteps
        .map((s, idx) => {
          const desc = typeof s === "string" ? s : s.description || s.title || "";
          return {
            id: (typeof s === "object" && s && s.id) || idx + 1,
            description: String(desc).trim(),
            status: (typeof s === "object" && s && s.status) || "pending",
          };
        })
        .filter((s) => s.description.length > 0);
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
    const summaryText = String(e.summary || e.event || "").trim();

    if (e.event === "TOOL_RESULT") {
      for (let i = steps.length - 1; i >= 0; i--) {
        if (steps[i].tool === e.tool && steps[i].status === "running") {
          steps[i].status = e.status === "error" || e.status === "denied" ? "error" : "done";
          if (e.duration_ms) steps[i].detail = `${e.duration_ms} ms`;
          if (e.tool === "delegate_to_agent") {
            state.activeSubAgent = "";
          }
          break;
        }
      }
      renderLiveSteps();
      return;
    }

    if (e.event === "TOOL_CALL") {
      finishThinkingSteps(false);
      // Si l'outil est delegate_to_agent et qu'un noeud de délégation vient déjà d'être créé, les fusionner sans doublon
      if (e.tool === "delegate_to_agent") {
        const lastStep = steps[steps.length - 1];
        if (lastStep && lastStep.kind === "delegation") {
          lastStep.tool = "delegate_to_agent";
          renderLiveSteps();
          return;
        }
        const targetAgent = String((data && (data.agent || data.target)) || "Agent spécialisé").replace(/^\[|\]$/g, "");
        state.activeSubAgent = targetAgent;
        steps.push({
          kind: "delegation",
          tool: "delegate_to_agent",
          label: "Délégation de mission à",
          pill: targetAgent,
          detail: "",
          status: "running",
          subAgent: "",
        });
        renderLiveSteps();
        return;
      }

      // Si une délégation parente était restée en "running", la marquer comme active/validée
      steps.forEach((s) => {
        if (s.kind === "delegation" && s.status === "running") {
          s.status = "done";
        }
      });

      const humanized = humanizeToolStep(e.tool, (data && data.target) || "", data);
      steps.push({
        kind: "tool",
        tool: e.tool,
        label: humanized.label,
        pill: humanized.pill,
        detail: "",
        status: "running",
        subAgent: state.activeSubAgent || "",
      });
      renderLiveSteps();
      return;
    }

    if (raw === "agent.thinking") {
      // Ne jamais empiler plusieurs lignes "Réflexion…" : mettre à jour ou placer une seule étape active en fin de liste
      finishThinkingSteps(false);
      const lastReal = steps[steps.length - 1];
      let thinkLabel = "Réflexion et analyse en cours…";
      if (lastReal && lastReal.pill) {
        thinkLabel = `Analyse de ${lastReal.pill}…`;
      } else if (state.activeSubAgent) {
        thinkLabel = `Raisonnement de ${state.activeSubAgent}…`;
      }
      steps.push({
        kind: "think",
        label: thinkLabel,
        pill: "",
        detail: "",
        status: "running",
        subAgent: state.activeSubAgent || "",
      });
      renderLiveSteps();
      return;
    }

    // Détection et fusion des lignes de délégation redondantes ("Délégation à reviewer...", "L'agent ReviewAgent commence la mission.")
    const delegMatch =
      summaryText.match(/Délégation\s+à\s+([a-zA-Z0-9_-]+)/i) ||
      summaryText.match(/L'agent\s+([a-zA-Z0-9_-]+)\s+commence\s+la\s+mission/i);
    if (delegMatch) {
      finishThinkingSteps(false);
      const agentLabel = delegMatch[1];
      state.activeSubAgent = agentLabel;
      const existingDeleg = steps.find(
        (s) => s.kind === "delegation" && (s.status === "running" || s.pill.toLowerCase() === agentLabel.toLowerCase())
      );
      if (existingDeleg) {
        if (agentLabel.length > existingDeleg.pill.length) {
          existingDeleg.pill = agentLabel;
        }
        existingDeleg.status = "done";
        renderLiveSteps();
        return;
      }
      steps.push({
        kind: "delegation",
        tool: "delegate_to_agent",
        label: "Délégation de mission à",
        pill: agentLabel,
        detail: "",
        status: "done",
        subAgent: "",
      });
      renderLiveSteps();
      return;
    }

    finishThinkingSteps(false);
    steps.push({
      kind: "info",
      label: summaryText.slice(0, 100),
      pill: "",
      detail: e.duration_ms ? `${e.duration_ms} ms` : "",
      status: e.status === "error" ? "error" : "done",
      subAgent: state.activeSubAgent || "",
    });
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

    const runningStep = steps.slice().reverse().find((s) => s.status === "running");
    const isRunning = Boolean(runningStep) || (state.isExecuting && !state.streamingBuffer);
    const toolCount = steps.filter((s) => s.kind === "tool").length;
    const elapsedSec = state.liveStartedAt ? ((Date.now() - state.liveStartedAt) / 1000).toFixed(1) : "0.0";

    const activeHeadline = runningStep
      ? `${runningStep.label}${runningStep.pill ? " · " + runningStep.pill : ""}`
      : isRunning
      ? "Réflexion approfondie en cours…"
      : `Réflexion terminée en ${elapsedSec} s`;

    sum.innerHTML = `
      <span class="reasoning-summary-left">
        <span class="reasoning-sparkle ${isRunning ? "pulsing" : ""}">${ICONS.sparkle}</span>
        <span class="reasoning-headline ${isRunning ? "shimmer-text" : ""}">${esc(activeHeadline)}</span>
      </span>
      <span class="reasoning-summary-right">
        ${toolCount > 0 ? `<span class="reasoning-meta-pill">${toolCount} action${toolCount > 1 ? "s" : ""}</span>` : ""}
        <span class="reasoning-timer mono">${elapsedSec}s</span>
        <span class="reasoning-chevron">${ICONS.chevronDown}</span>
      </span>
    `;

    box.innerHTML = steps
      .map((s) => {
        const iconHtml =
          s.status === "error"
            ? ICONS.close
            : s.status === "running"
            ? ICONS.dotFilled
            : s.kind === "delegation"
            ? ICONS.agent
            : ICONS.check;
        const indentClass = s.subAgent && s.kind !== "delegation" ? "is-subagent-step" : "";
        const kindClass = s.kind === "think" ? "is-thinking-step" : s.kind === "delegation" ? "is-delegation-step" : "";
        return `
          <div class="activity-step-item ${indentClass} ${kindClass}">
            <div class="activity-step-left">
              <span class="step-marker ${s.status}">${iconHtml}</span>
              <span class="activity-step-label ${s.status === "running" ? "shimmer-text" : ""}">${esc(s.label)}</span>
              ${s.pill ? `<code class="step-target-pill mono">${esc(s.pill)}</code>` : ""}
            </div>
            ${s.detail ? `<span class="activity-step-detail mono">${esc(s.detail)}</span>` : ""}
          </div>
        `;
      })
      .join("");
    box.scrollTop = box.scrollHeight;
  }

  function paintStreamBody() {
    ensureStreamingCard();
    const body = document.getElementById("streaming-body");
    if (!body) return;
    const shown = state.streamingBuffer.slice(0, state.streamShown);
    body.innerHTML = `${shown ? formatAssistantContent(shown) : ""}<span class="streaming-cursor"></span>`;
    if (shown && !state.streamAnchored) {
      state.streamAnchored = true;
      const card = document.getElementById("streaming-assistant-card");
      if (card) card.scrollIntoView({ block: "start", behavior: "smooth" });
    }
  }

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
      el.style.display = "inline";
      dot.className = "status-dot running";
    } else if (evt.event === "APPROVAL_REQUIRED") {
      el.textContent = "Validation requise";
      el.style.display = "inline";
      dot.className = "status-dot warning";
    } else if (evt.event === "TOOL_CALL") {
      const h = humanizeToolStep(evt.tool, "", {});
      el.textContent = h.label;
      el.style.display = "inline";
      dot.className = "status-dot running";
    } else if (evt.event === "VERIFIER") {
      el.textContent = "Vérification";
      el.style.display = "inline";
      dot.className = "status-dot running";
    } else if (evt.event === "TASK_COMPLETED") {
      el.textContent = evt.status === "partial" ? "Partiel" : "Prêt";
      el.style.display = evt.status === "partial" ? "inline" : "none";
      dot.className = evt.status === "partial" ? "status-dot warning" : "status-dot";
    } else if (evt.event === "ERROR") {
      el.textContent = "Erreur";
      el.style.display = "inline";
      dot.className = "status-dot error";
    } else if (state.isExecuting) {
      el.textContent = "Exécution…";
      el.style.display = "inline";
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
    const taskPillEl = document.getElementById("top-task-pill");
    if (taskStatusEl && !state.isExecuting) {
      const rawStatus = s.task_status || "Prêt";
      const isIdle = rawStatus === "En attente" || rawStatus === "Prêt" || rawStatus === "Terminé";
      taskStatusEl.textContent = isIdle ? "Prêt" : rawStatus;
      taskStatusEl.style.display = isIdle ? "none" : "inline";
      if (taskPillEl) {
        taskPillEl.style.display = isIdle ? "none" : "inline-flex";
      }
      if (taskDotEl) {
        taskDotEl.className =
          rawStatus === "Erreur"
            ? "status-dot error"
            : rawStatus === "Partiel" || rawStatus === "Attente validation"
            ? "status-dot warning"
            : "status-dot";
      }
    } else if (taskPillEl && state.isExecuting) {
      taskPillEl.style.display = "inline-flex";
    }
  }

  // -------------------------------------------------------------------------
  // 2. SIDEBAR DISCRÈTE (GROUPEMENT PAR DATE & ICÔNES VECTORIELLES)
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
                  const pinSvg = c.pinned ? `<span class="pin-indicator">${ICONS.pin}</span>` : "";
                  const archTag = c.archived ? " · archivé" : "";
                  return `
                    <div class="sidebar-item ${isCurrent ? "active" : ""}" data-select-conv="${esc(c.id)}">
                      <div class="sidebar-item-main">
                        ${pinSvg}
                        <span class="sidebar-item-title" title="${esc(c.title)}">${esc(c.title)}${archTag}</span>
                      </div>
                      <div class="conv-actions">
                        <button class="icon-btn-mini" data-pin-conv="${esc(c.id)}" data-pinned="${c.pinned ? "1" : "0"}" title="Épingler">${ICONS.pin}</button>
                        <button class="icon-btn-mini" data-rename-conv="${esc(c.id)}" data-title="${esc(c.title)}" title="Renommer">${ICONS.edit}</button>
                        <button class="icon-btn-mini" data-delete-conv="${esc(c.id)}" title="Supprimer">${ICONS.close}</button>
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

    const technicalFolders = ["exports", "generated", "temp", "tmp", "uploads", "downloads"];
    const realProjects = (s.projects || []).filter((p) => {
      const name = (p.name || "").toLowerCase();
      if (technicalFolders.includes(name) || name.startsWith("harness-test-") || name.startsWith(".")) {
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
  // 3. CENTER WORKSPACE (WELCOME & CONVERSATION ÉDITORIALE + ARTEFACTS VECTORIELS)
  // -------------------------------------------------------------------------
  function detectArtifactType(path, explicitType) {
    if (explicitType) {
      const et = String(explicitType).toLowerCase();
      if (et === "latex") return "tex";
      if (et === "word") return "docx";
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

  function getArtifactIconSvg(type) {
    switch (type) {
      case "pdf":
        return ICONS.filePdf;
      case "docx":
        return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>`;
      case "html":
        return ICONS.globe;
      case "tex":
      case "python":
      case "json":
        return ICONS.fileCode;
      case "svg":
      case "image":
        return ICONS.fileImage;
      case "mermaid":
        return ICONS.fileChart;
      case "csv":
        return ICONS.fileTable;
      default:
        return ICONS.filePdf;
    }
  }

  function extractMessageArtifacts(m) {
    const list = [];
    const seen = new Set();

    function addArt(item) {
      if (!item || !item.path) return;
      const norm = String(item.path).replace(/\\/g, "/");
      if (isHiddenInternalPath(norm)) return;
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
            const iconSvg = getArtifactIconSvg(typ);
            const pagesCount = art.page_count || art.pages;
            const bytesCount = art.size_bytes || art.bytes;
            const sizeKb = bytesCount ? `${Math.max(1, Math.round(bytesCount / 1024))} Ko` : "";

            if (typ === "pdf") {
              const stem = art.path.replace(/\.pdf$/i, "");
              const companionDocx = `${stem}.docx`;
              const metaParts = ["Document PDF"];
              if (pagesCount) metaParts.push(`${pagesCount} page${pagesCount > 1 ? "s" : ""}`);
              if (sizeKb) metaParts.push(sizeKb);
              return `
                <div class="artifact-card" data-open-doc-preview="pdf" data-doc-path="${esc(art.path)}" data-doc-source="${esc(art.source_tex || "")}" data-doc-pages="${esc(pagesCount || "")}">
                  <div class="artifact-card-icon pdf">${iconSvg}</div>
                  <div class="artifact-card-info">
                    <span class="artifact-card-name mono">${esc(art.path)}</span>
                    <span class="artifact-card-sub">${esc(metaParts.join(" · "))}</span>
                  </div>
                  <div class="artifact-card-actions">
                    <button type="button" class="artifact-btn primary pdf" data-open-doc-preview="pdf" data-doc-path="${esc(art.path)}" data-doc-source="${esc(art.source_tex || "")}" data-doc-pages="${esc(pagesCount || "")}">
                      Aperçu PDF
                    </button>
                    <a class="artifact-btn pdf" href="/api/files/raw?path=${encodeURIComponent(art.path)}&download=1" download title="Télécharger le PDF (.pdf)">
                      ${ICONS.download} PDF
                    </a>
                    <a class="artifact-btn word" href="/api/files/raw?path=${encodeURIComponent(companionDocx)}&download=1" download title="Télécharger en Word (.docx)">
                      ${ICONS.download} Word
                    </a>
                  </div>
                </div>
              `;
            }
            if (typ === "docx") {
              const stem = art.path.replace(/\.docx$/i, "");
              const companionPdf = `${stem}.pdf`;
              return `
                <div class="artifact-card" data-open-doc-preview="docx" data-doc-path="${esc(art.path)}">
                  <div class="artifact-card-icon docx">${iconSvg}</div>
                  <div class="artifact-card-info">
                    <span class="artifact-card-name mono">${esc(art.path)}</span>
                    <span class="artifact-card-sub">Document Word (.docx)${sizeKb ? " · " + esc(sizeKb) : ""}</span>
                  </div>
                  <div class="artifact-card-actions">
                    <button type="button" class="artifact-btn primary word" data-open-doc-preview="docx" data-doc-path="${esc(art.path)}">
                      Aperçu Word
                    </button>
                    <a class="artifact-btn word" href="/api/files/raw?path=${encodeURIComponent(art.path)}&download=1" download title="Télécharger le fichier Word (.docx)">
                      ${ICONS.download} Word
                    </a>
                    <a class="artifact-btn pdf" href="/api/files/raw?path=${encodeURIComponent(companionPdf)}&download=1" download title="Télécharger en PDF (.pdf)">
                      ${ICONS.download} PDF
                    </a>
                  </div>
                </div>
              `;
            }
            if (typ === "html") {
              return `
                <div class="artifact-card">
                  <div class="artifact-card-icon html">${iconSvg}</div>
                  <div class="artifact-card-info">
                    <span class="artifact-card-name mono">${esc(art.path)}</span>
                    <span class="artifact-card-sub">Application Web interactive${sizeKb ? " · " + esc(sizeKb) : ""}</span>
                  </div>
                  <div class="artifact-card-actions">
                    <button type="button" class="artifact-btn primary" data-open-doc-preview="html" data-doc-path="${esc(art.path)}" data-doc-view="render">
                      Aperçu HTML
                    </button>
                    <button type="button" class="artifact-btn" data-open-doc-preview="html" data-doc-path="${esc(art.path)}" data-doc-view="source">
                      Code
                    </button>
                    <a class="artifact-btn icon-only" href="/api/files/raw?path=${encodeURIComponent(art.path)}&download=1" download title="Télécharger">${ICONS.download}</a>
                  </div>
                </div>
              `;
            }
            if (typ === "tex") {
              return `
                <div class="artifact-card">
                  <div class="artifact-card-icon tex">${iconSvg}</div>
                  <div class="artifact-card-info">
                    <span class="artifact-card-name mono">${esc(art.path)}</span>
                    <span class="artifact-card-sub">Source LaTeX</span>
                  </div>
                  <div class="artifact-card-actions">
                    <button type="button" class="artifact-btn primary" data-compile-tex-path="${esc(art.path)}">
                      ${ICONS.bolt} Compiler PDF
                    </button>
                    <button type="button" class="artifact-btn" data-open-doc-preview="tex" data-doc-path="${esc(art.path)}" data-doc-view="source">
                      Source .tex
                    </button>
                  </div>
                </div>
              `;
            }
            if (typ === "python") {
              return `
                <div class="artifact-card">
                  <div class="artifact-card-icon py">${iconSvg}</div>
                  <div class="artifact-card-info">
                    <span class="artifact-card-name mono">${esc(art.path)}</span>
                    <span class="artifact-card-sub">Script Python exécutable</span>
                  </div>
                  <div class="artifact-card-actions">
                    <button type="button" class="artifact-btn primary" data-open-doc-preview="python" data-doc-path="${esc(art.path)}" data-doc-view="render">
                      ${ICONS.bolt} Aperçu & Exécution
                    </button>
                    <button type="button" class="artifact-btn" data-open-doc-preview="python" data-doc-path="${esc(art.path)}" data-doc-view="source">
                      Code
                    </button>
                  </div>
                </div>
              `;
            }
            return `
              <div class="artifact-card">
                <div class="artifact-card-icon">${iconSvg}</div>
                <div class="artifact-card-info">
                  <span class="artifact-card-name mono">${esc(art.path)}</span>
                  <span class="artifact-card-sub">${esc((typ || "Fichier").toUpperCase())}${sizeKb ? " · " + esc(sizeKb) : ""}</span>
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

  function buildCompletedReasoningHtml(m) {
    const eventsList = (m.events || []).filter(
      (ev) => !LIVE_SKIP.has(ev.event) && ev.raw_event !== "agent.thinking"
    );
    const planSteps = (m.plan_steps || []).filter((st) => String(st || "").trim().length > 0);
    const toolsUsed = m.tools_used || [];
    const durationSec = m.duration_ms ? (m.duration_ms / 1000).toFixed(1) : "";

    if (toolsUsed.length === 0 && planSteps.length === 0 && eventsList.length === 0) {
      return "";
    }

    const summaryChips = [];
    if (durationSec) summaryChips.push(`Réflexion (${durationSec} s)`);
    else summaryChips.push("Trace de raisonnement");
    if (m.agent && m.agent !== "Runtime Local" && m.agent !== "researcher") {
      summaryChips.push(m.agent);
    }
    if (toolsUsed.length > 0) {
      summaryChips.push(`${toolsUsed.length} action${toolsUsed.length > 1 ? "s" : ""}`);
    } else if (planSteps.length > 0) {
      summaryChips.push(`${planSteps.length} étape${planSteps.length > 1 ? "s" : ""}`);
    }

    // Nettoyer et structurer les événements de la trace terminée (sans doublons de délégation ni jargon brut)
    const renderedRows = [];
    let currentSubAgent = "";
    eventsList.forEach((ev) => {
      if (ev.event === "TOOL_RESULT") return;
      const sumText = String(ev.summary || "").trim();
      const delegMatch =
        sumText.match(/Délégation\s+à\s+([a-zA-Z0-9_-]+)/i) ||
        sumText.match(/L'agent\s+([a-zA-Z0-9_-]+)\s+commence\s+la\s+mission/i);
      if (delegMatch || ev.tool === "delegate_to_agent") {
        const ag = delegMatch ? delegMatch[1] : (ev.details && ev.details.agent) || "Agent spécialisé";
        if (currentSubAgent.toLowerCase() === ag.toLowerCase()) return;
        currentSubAgent = ag;
        renderedRows.push({
          isDelegation: true,
          label: "Délégation de mission à",
          pill: ag,
          duration: ev.duration_ms ? `${ev.duration_ms} ms` : "",
          subAgent: "",
        });
        return;
      }
      if (ev.event === "TOOL_CALL" && ev.tool) {
        const det = ev.details || ev.data || {};
        const h = humanizeToolStep(ev.tool, det.target || det.path || det.query || "", det);
        renderedRows.push({
          isDelegation: false,
          label: h.label,
          pill: h.pill,
          duration: ev.duration_ms ? `${ev.duration_ms} ms` : "",
          subAgent: currentSubAgent,
        });
        return;
      }
      if (sumText) {
        renderedRows.push({
          isDelegation: false,
          label: sumText,
          pill: "",
          duration: ev.duration_ms ? `${ev.duration_ms} ms` : "",
          subAgent: currentSubAgent,
        });
      }
    });

    return `
      <details class="activity-flow-box">
        <summary class="activity-flow-summary">
          <span class="reasoning-summary-left">
            <span class="reasoning-sparkle">${ICONS.sparkle}</span>
            <span>${esc(summaryChips.join(" · "))}</span>
          </span>
          <span class="reasoning-chevron">${ICONS.chevronDown}</span>
        </summary>
        <div class="activity-steps-list">
          ${
            planSteps.length
              ? `<div class="reasoning-plan-brief">
                  <strong>Plan :</strong> ${planSteps.map((st, i) => `${i + 1}. ${esc(st)}`).join(" → ")}
                 </div>`
              : ""
          }
          ${renderedRows
            .map(
              (r) => `
              <div class="activity-step-item ${r.subAgent ? "is-subagent-step" : ""} ${r.isDelegation ? "is-delegation-step" : ""}">
                <div class="activity-step-left">
                  <span class="step-marker done">${r.isDelegation ? ICONS.agent : ICONS.check}</span>
                  <span class="activity-step-label">${esc(r.label)}</span>
                  ${r.pill ? `<code class="step-target-pill mono">${esc(r.pill)}</code>` : ""}
                </div>
                ${r.duration ? `<span class="activity-step-detail mono">${esc(r.duration)}</span>` : ""}
              </div>
            `
            )
            .join("")}
        </div>
      </details>
    `;
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
                  .map((a) => `<span class="meta-chip">${ICONS.paperclip} ${esc(a)}</span>`)
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
          badges.push(`<span class="meta-chip success">${ICONS.check} Vérifié</span>`);
        }

        const toolsUsed = m.tools_used || [];
        const sourcesUsed = m.sources || [];
        const filesMod = m.files_modified || [];

        const activityHtml = buildCompletedReasoningHtml(m);
        const artifactsHtml = renderMessageArtifactsHtml(m);

        const sourcesHtml =
          sourcesUsed.length > 0
            ? `
            <div class="message-sources-row">
              ${sourcesUsed
                .map(
                  (src) => `
                  <a class="source-pill" href="${esc(src.url)}" target="_blank" rel="noopener noreferrer" title="${esc(src.title)} (${esc(src.published_at || src.source || src.url)})">
                    ${ICONS.globe}
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
    out = out.replace(/`([^`\n]+)`/g, "<code>$1</code>");
    out = out.replace(
      /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
    );
    out = out.replace(/\*\*\*([^*]+)\*\*\*/g, "<strong><em>$1</em></strong>");
    out = out.replace(/___([^_]+)___/g, "<strong><em>$1</em></strong>");
    out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    out = out.replace(/__([^_]+)__/g, "<strong>$1</strong>");
    out = out.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, "$1<em>$2</em>");
    out = out.replace(/(^|[^_])_([^_\n]+)_(?!_)/g, "$1<em>$2</em>");

    out = out.replace(/^\s*[\*•]\s+/, "");
    out = out.replace(/\*\*/g, "");
    out = out.replace(/(^|\s)\*([^\s*]+)/g, "$1$2");
    out = out.replace(/(\s)\*(\s|$)/g, "$1·$2");

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

    let working = String(raw).replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, function (_, lang, code) {
      const token = `\n@@CODEBLOCK_${codeBlocks.length}@@\n`;
      codeBlocks.push(`<pre><code class="lang-${esc(lang)}">${esc(code)}</code></pre>`);
      return token;
    });

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
    let currentListType = null;

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

      if (/^(?:[-*_]\s*){3,}$/.test(trimmed)) {
        closeList();
        htmlParts.push("<hr />");
        continue;
      }

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

      if (trimmed.startsWith("> ")) {
        closeList();
        htmlParts.push(`<blockquote>${formatInlineMarkdown(trimmed.slice(2), inlineMathTokens)}</blockquote>`);
        continue;
      }

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

      closeList();
      htmlParts.push(`<p>${formatInlineMarkdown(line, inlineMathTokens)}</p>`);
    }

    closeList();
    return htmlParts.join("");
  }

  function renderMarkdownToHtml(md) {
    return formatAssistantContent(md);
  }

  function renderKaTeXInElement(_el) {
    // Le rendu mathématique est déjà intégré dans formatAssistantContent
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
      <button class="composer-chip-btn" id="btn-welcome-change-model">Changer de modèle ${ICONS.chevronDown}</button>
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
        <div style="display:flex; align-items:flex-start; gap:10px;">
          <span style="color:var(--warning); margin-top:2px;">${ICONS.alert}</span>
          <div>
            <strong>Validation humaine requise (${esc(item.risk_level)})</strong>
            <div style="font-size: 12px;">${esc(item.message)}</div>
          </div>
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
    if (/(?:https?|file):\/\/[^\s]*$/i.test(beforeCursor)) {
      return null;
    }
    const match = beforeCursor.match(/(?:^|\s)(\/[a-zA-Z0-9_-]*)$/);
    if (!match) return null;

    const fullToken = match[1];
    const query = fullToken.slice(1).toLowerCase();
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
                  ? `<span class="meta-chip success">${ICONS.check} Prêt</span>`
                  : `<span class="meta-chip warning" title="${esc(sk.compatibility_reason || "Indisponible")}">Indisponible</span>`
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
    if (state.toastTimer) {
      clearTimeout(state.toastTimer);
      state.toastTimer = null;
    }
    if (!message) {
      banner.style.display = "none";
      banner.innerHTML = "";
      return;
    }
    const tone = level === "error" ? "error" : level === "warning" ? "warning" : "info";
    banner.className = `voice-status-banner ${tone}`;
    banner.style.display = "flex";
    banner.innerHTML = `
      <span class="toast-banner-text">${esc(message)}</span>
      <button type="button" class="icon-btn-mini" id="btn-dismiss-status-banner" aria-label="Fermer">${ICONS.close}</button>
    `;
    const btn = document.getElementById("btn-dismiss-status-banner");
    if (btn) {
      btn.addEventListener("click", () => {
        banner.style.display = "none";
      });
    }
    if (tone === "info" || level === "success") {
      state.toastTimer = setTimeout(() => {
        banner.style.display = "none";
      }, 3600);
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
              ${ICONS.paperclip}
              <span>${esc(f)}</span>
              <button class="icon-btn-mini" data-remove-attachment="${esc(f)}" title="Retirer">${ICONS.close}</button>
            </span>
          `
          )
          .join("");
      }
    }

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

    const currentExecMode = (s.execution && s.execution.mode) || state.executionMode || (state.deepReflection ? "multi" : "mono");
    const isMulti = currentExecMode === "multi";
    const isChat = currentExecMode === "chat";
    state.executionMode = currentExecMode;
    state.deepReflection = isMulti;

    const chatBtn = document.getElementById("btn-direct-chat");
    if (chatBtn) {
      chatBtn.classList.toggle("active", isChat);
      chatBtn.setAttribute("aria-pressed", isChat ? "true" : "false");
      chatBtn.removeAttribute("title");
      chatBtn.setAttribute(
        "data-tooltip",
        isChat
          ? "Chat direct actif (Sans agent · 0 surcoût tokens)"
          : "Activer le chat direct (Sans agent · Économie de tokens)"
      );
    }

    const deepBtn = document.getElementById("btn-deep-reflection");
    if (deepBtn) {
      deepBtn.classList.toggle("active", isMulti);
      deepBtn.setAttribute("aria-pressed", isMulti ? "true" : "false");
      deepBtn.removeAttribute("title");
      deepBtn.setAttribute(
        "data-tooltip",
        isMulti
          ? "Réflexion approfondie activée (Multi-Agents)"
          : "Activer la réflexion approfondie (Multi-Agents)"
      );
      const iconSpan = deepBtn.querySelector(".deep-reflection-icon");
      if (iconSpan && !iconSpan.querySelector("svg")) {
        iconSpan.innerHTML = ICONS.brain;
      }
    }

    const modeSel = document.getElementById("composer-mode-select");
    if (modeSel && s.mode) {
      modeSel.value = s.mode.current;
      const chipLabel = document.getElementById("governance-chip-label");
      if (chipLabel) {
        chipLabel.textContent =
          s.mode.current === "AUTO" ? "Auto" : s.mode.current;
      }
    }
  }

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

    const voiceBar = document.getElementById("voice-dictation-bar");
    const micBtn = document.getElementById("btn-voice-dictate");
    const previewEl = document.getElementById("voice-live-preview");
    const timerEl = document.getElementById("voice-timer");
    if (voiceBar) voiceBar.style.display = "flex";
    if (inputEl) inputEl.style.display = "none";
    if (micBtn) micBtn.classList.add("recording");
    if (previewEl) previewEl.textContent = "Écoute en cours… Parlez maintenant.";
    if (timerEl) timerEl.textContent = "00:00";

    state.voice.timerInterval = setInterval(() => {
      const tEl = document.getElementById("voice-timer");
      if (tEl && state.voice.active) {
        tEl.textContent = formatDuration(Date.now() - state.voice.startedAt);
      }
    }, 250);

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
      page_count: docSpec.page_count || docSpec.pages || null,
      size_bytes: docSpec.size_bytes || docSpec.bytes || null,
      viewMode: docSpec.viewMode || (type === "tex" ? "source" : "render"),
      zoom: docSpec.zoom || 100,
      auto_repaired: Boolean(docSpec.auto_repaired || docSpec.repaired),
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
      const stem = cleanPath.replace(/\.pdf$/i, "");
      docObj.companionPdf = cleanPath;
      docObj.companionDocx = `${stem}.docx`;
      docObj.viewMode = docSpec.viewMode || "pdf";
      try {
        const info = await apiGet(`/api/files/pdf-info?path=${encodeURIComponent(cleanPath)}`);
        docObj.page_count = info.page_count;
        docObj.size_bytes = info.size_bytes;
        if (info.source_tex) docObj.source_tex = info.source_tex;
      } catch (err) {
        docObj.error = `Impossible de charger le PDF (${cleanPath}) : ${err.message}`;
      }
    } else if (type === "docx") {
      const stem = cleanPath.replace(/\.docx$/i, "");
      docObj.companionPdf = `${stem}.pdf`;
      docObj.companionDocx = cleanPath;
      docObj.viewMode = docSpec.viewMode || "word";
      try {
        const fileData = await apiGet(`/api/files/content?path=${encodeURIComponent(cleanPath)}`);
        docObj.size_bytes = fileData.size_bytes;
      } catch (_) {}
    } else if (type === "image") {
      try {
        const fileData = await apiGet(`/api/files/content?path=${encodeURIComponent(cleanPath)}`);
        docObj.size_bytes = fileData.size_bytes;
      } catch (_) {}
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
          if (
            docObj.metadata &&
            (docObj.metadata.visual_output || (docObj.metadata.figures && docObj.metadata.figures.length > 0))
          ) {
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
          <strong>${ICONS.alert} Erreur de syntaxe Mermaid</strong>
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

  function renderFiguresGalleryInViewer(figures, _doc) {
    const host = document.getElementById("doc-image-viewer");
    if (!host) return;
    host.innerHTML = `
      <div style="display:flex; flex-direction:column; align-items:center; gap:20px; max-width:100%; padding:16px;">
        <div style="font-size:12.5px; font-weight:600; color:var(--text-secondary); display:flex; align-items:center; gap:6px;">
          ${ICONS.fileChart}
          <span>${figures.length} figure${figures.length > 1 ? "s" : ""} Matplotlib capturée${figures.length > 1 ? "s" : ""} :</span>
        </div>
        ${figures
          .map((figPath, idx) => {
            const url = `/api/files/raw?path=${encodeURIComponent(figPath)}&t=${Date.now()}`;
            return `
            <div style="display:flex; flex-direction:column; align-items:center; gap:8px; width:100%; max-width:720px; background:var(--bg-primary); border:1px solid var(--border-subtle); border-radius:10px; padding:12px; box-shadow:var(--shadow-sm);">
              <img src="${url}" alt="${esc(figPath)}" style="max-width:100%; max-height:65vh; object-fit:contain; border-radius:6px;" />
              <div style="display:flex; justify-content:space-between; width:100%; font-size:11.5px; color:var(--text-muted); padding:0 4px;">
                <span><strong>Figure ${idx + 1}</strong> : ${esc(figPath.split("/").pop())}</span>
                <a href="${url}" target="_blank" class="link-subtle" style="font-size:11px; display:inline-flex; align-items:center; gap:4px;">Ouvrir ${ICONS.external}</a>
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
      <div style="overflow-x:auto; border:1px solid var(--border-color); border-radius:8px;">
        <table class="doc-data-table" id="csv-table-element">
          <thead>
            <tr>${headers.map((h, idx) => `<th data-col-idx="${idx}" style="cursor:pointer;" title="Colonne ${idx + 1}">${esc(h)}</th>`).join("")}</tr>
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
          <strong>${ICONS.alert} Erreur de syntaxe JSON :</strong>
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
              <span class="json-toggle" style="user-select:none; display:inline-flex;">${ICONS.chevronDown}</span>
              ${keyPrefix}
              <span class="json-bracket">${openChar}</span>
              <span class="json-badge" style="font-size:11px; opacity:0.75;">${count} élément${count > 1 ? "s" : ""}</span>
            </div>
            <div class="json-children" style="margin-left: 14px; border-left: 1px dashed var(--border-color); padding-left: 8px;">
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
            if (toggle) toggle.innerHTML = isHidden ? ICONS.chevronDown : ICONS.chevronRight;
          }
        }
      });
    });

    const btnExp = host.querySelector("#btn-json-expand-all");
    const btnCol = host.querySelector("#btn-json-collapse-all");
    if (btnExp) {
      btnExp.addEventListener("click", () => {
        host.querySelectorAll(".json-children").forEach((c) => (c.style.display = "block"));
        host.querySelectorAll(".json-toggle").forEach((t) => (t.innerHTML = ICONS.chevronDown));
      });
    }
    if (btnCol) {
      btnCol.addEventListener("click", () => {
        host.querySelectorAll(".json-children").forEach((c) => (c.style.display = "none"));
        host.querySelectorAll(".json-toggle").forEach((t) => (t.innerHTML = ICONS.chevronRight));
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
      <div class="rendered-markdown-content md-prose" style="padding: 16px; line-height: 1.65;">
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
    if (doc.path && !isHiddenInternalPath(doc.path)) allFiles.add(doc.path);
    if (doc.source_tex && !isHiddenInternalPath(doc.source_tex)) allFiles.add(doc.source_tex);
    if (Array.isArray(doc.output_paths)) {
      doc.output_paths.filter((p) => !isHiddenInternalPath(p)).forEach((p) => allFiles.add(p));
    }
    if (Array.isArray(doc.source_paths)) {
      doc.source_paths.filter((p) => !isHiddenInternalPath(p)).forEach((p) => allFiles.add(p));
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
            <div class="inspector-card" style="display:flex; flex-direction:row; justify-content:space-between; align-items:center; margin:0; padding:10px 14px;">
              <div style="display:flex; align-items:center; gap:8px; min-width:0;">
                <span style="color:var(--text-secondary); display:inline-flex;">${getArtifactIconSvg(typ)}</span>
                <span class="mono" style="font-size:12px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${esc(fpath)}</span>
                ${isPrimary ? `<span class="meta-chip accent">Principal</span>` : `<span class="meta-chip">Généré</span>`}
              </div>
              <div style="display:flex; gap:6px; flex-shrink:0;">
                <button type="button" class="icon-btn-mini" data-open-doc-preview="${esc(typ)}" data-doc-path="${esc(fpath)}">Ouvrir</button>
                <a class="icon-btn-mini" href="/api/files/raw?path=${encodeURIComponent(fpath)}&download=1" download title="Télécharger">${ICONS.download}</a>
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
          ${doc.type === "python" ? `<br/><button type="button" id="btn-run-python-now" class="composer-chip-btn" style="margin-top:8px;">${ICONS.bolt} Exécuter maintenant</button>` : ""}
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
            ${isSuccess ? `${ICONS.check} Succès (Code 0)` : `${ICONS.alert} Code ` + (exec.exit_code !== undefined ? exec.exit_code : "1")}
          </span>
          <span class="mono" style="font-size:11.5px; opacity:0.85; color:#94A3B8;">${durTxt}</span>
        </div>
        ${doc.type === "python" ? `<button type="button" id="btn-re-execute-console" class="icon-btn-mini">${ICONS.bolt} Relancer l'exécution</button>` : ""}
      </div>
      ${exec.command ? `<div style="font-size:11px; color:#94A3B8; margin-bottom:8px;"><span class="mono">Commande : ${esc(exec.command)}</span></div>` : ""}
      ${
        exec.stdout
          ? `
        <div style="margin-bottom:14px;">
          <div style="font-size:11px; font-weight:600; color:#CBD5E1; margin-bottom:6px; letter-spacing:0.4px;">STDOUT :</div>
          <pre class="doc-console-pre mono">${esc(exec.stdout)}</pre>
        </div>
      `
          : ""
      }
      ${
        exec.stderr
          ? `
        <div>
          <div style="font-size:11px; font-weight:600; color:#F87171; margin-bottom:6px; letter-spacing:0.4px;">STDERR :</div>
          <pre class="doc-console-pre mono" style="background:rgba(239, 68, 68, 0.1) !important; border:1px solid rgba(239, 68, 68, 0.4) !important; color:#FCA5A5 !important;">${esc(exec.stderr)}</pre>
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

    const lines = stdout ? stdout.split("\n") : [];
    const metrics = [];
    const metricRegex = /^(?:[-*•]\s*)?([^:=\n]+?)\s*[:=]\s*(.+)$/;

    for (const line of lines) {
      const trimmed = line.trim();
      const match = trimmed.match(metricRegex);
      if (match && match[1].length < 50 && match[2].length < 60) {
        metrics.push({
          label: match[1].trim().replace(/^[-*•]\s*/, ""),
          value: match[2].trim().replace(/\.$/, ""),
        });
      }
    }

    let metricsHtml = "";
    if (metrics.length > 0) {
      metricsHtml = `
        <div style="margin-bottom:16px;">
          <div style="font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.6px; color:var(--text-secondary); margin-bottom:8px;">Résultats & Métriques calculés</div>
          <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:10px;">
            ${metrics
              .map(
                (m) => `
              <div style="background:var(--bg-secondary); border:1px solid var(--border-color); border-left:3px solid var(--accent); border-radius:6px; padding:10px 14px;">
                <div style="font-size:11px; color:var(--text-secondary); margin-bottom:4px; font-weight:500;">${esc(m.label)}</div>
                <div style="font-size:16px; font-weight:700; color:var(--text-primary); font-family:var(--font-mono, monospace);">${esc(m.value)}</div>
              </div>
            `
              )
              .join("")}
          </div>
        </div>
      `;
    }

    host.innerHTML = `
      <div style="padding:16px; max-width:850px; margin:0 auto; width:100%;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; padding-bottom:12px; border-bottom:1px solid var(--border-color);">
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
                  ${isSuccess ? `${ICONS.check} Exécution réussie` : `${ICONS.alert} Erreur (Code ` + exec.exit_code + ")"}
                </span>
                <span>·</span>
                <span class="mono">${durTxt}</span>
              </div>
            </div>
          </div>
          <div style="display:flex; gap:6px;">
            <button type="button" id="btn-result-switch-console" class="icon-btn-mini" title="Basculer vers la console brute">Console brute</button>
            <button type="button" id="btn-result-reexecute" class="icon-btn-mini" title="Ré-exécuter le script">${ICONS.bolt} Relancer</button>
          </div>
        </div>

        ${metricsHtml}

        ${
          stdout
            ? `
          <div style="margin-bottom:16px;">
            <div style="font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.6px; color:var(--text-secondary); margin-bottom:8px;">Sortie du calcul</div>
            <div style="background:#0F172A; border:1px solid #334155; border-radius:8px; padding:14px; color:#F8FAFC; font-family:var(--font-mono, monospace); font-size:12.5px; line-height:1.6; white-space:pre-wrap; overflow-x:auto;">${esc(stdout)}</div>
          </div>
        `
            : ""
        }

        ${
          stderr
            ? `
          <div style="margin-bottom:16px;">
            <div style="font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.6px; color:#EF4444; margin-bottom:8px;">Avertissements / Erreurs</div>
            <div style="background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.3); border-radius:8px; padding:12px; color:#FCA5A5; font-family:var(--font-mono, monospace); font-size:12px; line-height:1.5; white-space:pre-wrap;">${esc(stderr)}</div>
          </div>
        `
            : ""
        }

        ${
          !stdout && !stderr
            ? `
          <div class="inspector-card" style="text-align:center; padding:24px; color:var(--text-secondary);">
            Le script s'est exécuté avec succès (Code 0) mais n'a produit aucun affichage dans la console.
          </div>
        `
            : ""
        }
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
      docx: "Word · DOCX",
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

    const btnDlWord = document.getElementById("btn-doc-download-word");
    const btnDlPdf = document.getElementById("btn-doc-download-pdf");
    const stem = doc.path.replace(/\.(docx|pdf)$/i, "");
    const companionDocx = doc.companionDocx || `${stem}.docx`;
    const companionPdf = doc.companionPdf || `${stem}.pdf`;

    if (btnDlWord) {
      if (doc.type === "docx" || doc.type === "pdf") {
        btnDlWord.style.display = "inline-flex";
        btnDlWord.href = `/api/files/raw?path=${encodeURIComponent(companionDocx)}&download=1`;
      } else {
        btnDlWord.style.display = "none";
      }
    }
    if (btnDlPdf) {
      if (doc.type === "docx" || doc.type === "pdf") {
        btnDlPdf.style.display = "inline-flex";
        btnDlPdf.href = `/api/files/raw?path=${encodeURIComponent(companionPdf)}&download=1`;
      } else {
        btnDlPdf.style.display = "none";
      }
    }

    if (btnDownload) {
      btnDownload.href = `/api/files/raw?path=${encodeURIComponent(doc.path)}&download=1`;
      btnDownload.setAttribute("download", doc.path.split("/").pop() || "document");
    }

    if (noticeEl) {
      if (doc.auto_repaired) {
        noticeEl.style.display = "flex";
        noticeEl.innerHTML = `${ICONS.check} <span>Artefact réparé automatiquement (${esc((doc.repair_notes || []).join(", ") || "syntaxe normalisée")}).</span>`;
      } else {
        noticeEl.style.display = "none";
      }
    }

    const btnWord = document.getElementById("btn-doc-view-word");
    const btnPdf = document.getElementById("btn-doc-view-pdf");
    const isDocx = doc.type === "docx";
    const isPdf = doc.type === "pdf";
    const isDualDoc = isDocx || isPdf;
    const isWordView = doc.viewMode === "word" || (isDocx && doc.viewMode === "render");
    const isPdfView = doc.viewMode === "pdf" || (isPdf && doc.viewMode === "render");

    if (isDualDoc) {
      if (btnRender) btnRender.style.display = "none";
      if (btnWord) {
        btnWord.style.display = "inline-flex";
        btnWord.classList.toggle("active", isWordView);
      }
      if (btnPdf) {
        btnPdf.style.display = "inline-flex";
        btnPdf.classList.toggle("active", isPdfView);
      }
    } else {
      if (btnWord) btnWord.style.display = "none";
      if (btnPdf) btnPdf.style.display = "none";
      if (btnRender) {
        btnRender.style.display = "inline-flex";
        btnRender.classList.toggle("active", doc.viewMode === "render");
      }
    }

    if (btnSource) {
      btnSource.classList.toggle("active", doc.viewMode === "source");
      btnSource.textContent =
        doc.type === "pdf" || doc.type === "tex"
          ? "Source .tex"
          : doc.type === "docx"
          ? "Texte source"
          : doc.type === "svg"
          ? "Code XML"
          : doc.type === "csv"
          ? "Données brutes"
          : "Code source";
      btnSource.style.display = doc.type === "image" ? "none" : "inline-block";
    }

    if (btnFiles) {
      btnFiles.classList.toggle("active", doc.viewMode === "files");
      const hasFiles =
        (doc.output_paths && doc.output_paths.length > 0) || (doc.source_paths && doc.source_paths.length > 0);
      btnFiles.style.display = hasFiles ? "inline-block" : "none";
    }

    if (btnConsole) {
      btnConsole.classList.toggle("active", doc.viewMode === "console");
      btnConsole.style.display = doc.execution || doc.type === "python" ? "inline-block" : "none";
    }

    if (zoomControls) {
      zoomControls.style.display = isPdfView ? "inline-flex" : "none";
    }
    if (zoomLabel) {
      zoomLabel.textContent = `${Math.round(doc.zoom || 100)}%`;
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

    [
      pdfViewer,
      htmlFrame,
      svgViewer,
      mermaidViewer,
      imageViewer,
      tableViewer,
      jsonViewer,
      markdownViewer,
      resultViewer,
      filesViewer,
      consoleViewer,
      sourceWrap,
      errorBox,
    ].forEach((el) => {
      if (el) el.style.display = "none";
    });

    if (doc.error) {
      if (errorBox) {
        errorBox.style.display = "block";
        errorBox.innerHTML = `
          <strong style="display:inline-flex; align-items:center; gap:6px;">${ICONS.alert} Erreur d'aperçu ou de validation</strong>
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

    if (isWordView && htmlFrame) {
      htmlFrame.style.display = "block";
      const targetDocx = doc.companionDocx || doc.path;
      const targetSrc = `/api/preview/workspace/${targetDocx.split("/").map(encodeURIComponent).join("/")}?t=${Date.now()}`;
      if (htmlFrame.getAttribute("data-doc-path") !== targetDocx) {
        htmlFrame.setAttribute("data-doc-path", targetDocx);
        htmlFrame.src = targetSrc;
      }
    } else if (isPdfView && pdfViewer) {
      pdfViewer.style.display = "flex";
      const targetPdf = doc.companionPdf || doc.path;
      renderPdfInViewer({ path: targetPdf, zoom: doc.zoom || 100 }).catch((err) => {
        if (errorBox) {
          errorBox.style.display = "block";
          errorBox.innerHTML = `<strong style="display:inline-flex; align-items:center; gap:6px;">${ICONS.alert} Aperçu PDF impossible</strong><pre class="mono" style="margin-top:8px;white-space:pre-wrap;font-size:11.5px;">${esc(err.message)}</pre>`;
        }
      });
    } else if ((doc.type === "docx" || doc.type === "html") && htmlFrame) {
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

    const rect = host.getBoundingClientRect();
    const ax = clientX == null ? host.clientWidth / 2 : clientX - rect.left;
    const ay = clientY == null ? host.clientHeight / 2 : clientY - rect.top;
    const px = host.scrollLeft + ax;
    const py = host.scrollTop + ay;
    const ratio = z / oldZoom;

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

    clearTimeout(setPdfZoom._t);
    setPdfZoom._t = setTimeout(() => renderPdfInViewer(d).catch(() => {}), 220);
  }

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

  const zoomLabelEl = document.getElementById("pdf-zoom-label");
  if (zoomLabelEl) zoomLabelEl.addEventListener("click", () => setPdfZoom(100));

  window.addEventListener("keydown", (e) => {
    const d = state.activeDocument;
    if (!(e.ctrlKey || e.metaKey) || !d || d.type !== "pdf" || state.rightPanelMode !== "document") return;
    if (e.key === "+" || e.key === "=") {
      e.preventDefault();
      setPdfZoom((d.zoom || 100) + 25);
    } else if (e.key === "-") {
      e.preventDefault();
      setPdfZoom((d.zoom || 100) - 25);
    } else if (e.key === "0") {
      e.preventDefault();
      setPdfZoom(100);
    }
  });

  async function compileLatexAndPreview(texPath, optionalContent) {
    const statusEl = document.getElementById("top-task-status");
    const dotEl = document.getElementById("top-task-dot");
    if (statusEl) {
      statusEl.textContent = "Compilation Tectonic…";
      statusEl.style.display = "inline";
    }
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
  // 8. RIGHT INSPECTOR TECHNIQUE (100 % ICÔNES VECTORIELLES & LIGNES ÉPURÉES)
  // -------------------------------------------------------------------------
  window.toggleDirectChat = async function () {
    const currentMode = (state.appState && state.appState.execution && state.appState.execution.mode) || state.executionMode || "mono";
    const newMode = currentMode === "chat" ? "mono" : "chat";
    state.executionMode = newMode;
    state.deepReflection = (newMode === "multi");

    // Ouvre et sélectionne immédiatement l'onglet Modèle dans la barre latérale droite
    state.inspectorTab = "model";
    switchRightPanelMode("inspector");

    await window.setAgentExecutionMode(newMode);
    showStatusBanner(
      newMode === "chat"
        ? "Mode Chat direct activé (Sans agent — Économie maximale de tokens)."
        : "Mode Mono-Agent (standard séquentiel) activé.",
      "info"
    );
  };

  window.toggleDeepReflection = async function () {
    const currentMode = (state.appState && state.appState.execution && state.appState.execution.mode) || state.executionMode || "mono";
    const newMode = currentMode === "multi" ? "mono" : "multi";
    state.executionMode = newMode;
    state.deepReflection = (newMode === "multi");

    // Ouvre et sélectionne immédiatement l'onglet Modèle dans la barre latérale droite
    state.inspectorTab = "model";
    switchRightPanelMode("inspector");

    await window.setAgentExecutionMode(newMode);
    showStatusBanner(
      newMode === "multi"
        ? "Mode Réflexion Approfondie (Multi-Agents) activé dans la barre latérale."
        : "Mode Mono-Agent (prudent) activé.",
      "info"
    );
  };

  window.setAgentExecutionMode = async function (mode) {
    try {
      const isMulti = mode === "multi";
      const isChat = mode === "chat";
      state.executionMode = mode;
      state.deepReflection = isMulti;

      // Synchronisation directe des boutons dans le compositeur
      const deepBtn = document.getElementById("btn-deep-reflection");
      if (deepBtn) {
        deepBtn.classList.toggle("active", isMulti);
        deepBtn.setAttribute("aria-pressed", isMulti ? "true" : "false");
        deepBtn.removeAttribute("title");
        deepBtn.setAttribute(
          "data-tooltip",
          isMulti
            ? "Réflexion approfondie activée (Multi-Agents)"
            : "Activer la réflexion approfondie (Multi-Agents)"
        );
      }

      const chatBtn = document.getElementById("btn-direct-chat");
      if (chatBtn) {
        chatBtn.classList.toggle("active", isChat);
        chatBtn.setAttribute("aria-pressed", isChat ? "true" : "false");
        chatBtn.removeAttribute("title");
        chatBtn.setAttribute(
          "data-tooltip",
          isChat
            ? "Chat direct actif (Sans agent · 0 surcoût tokens)"
            : "Activer le chat direct (Sans agent · Économie de tokens)"
        );
      }

      const currParallel = (state.appState && state.appState.execution && state.appState.execution.max_parallel_agents) || 2;
      const targetParallel = isMulti ? (currParallel > 1 ? currParallel : 2) : 1;
      const res = await apiPost("/api/execution/mode", {
        mode: mode,
        max_parallel_agents: targetParallel,
      });
      if (res && res.execution && state.appState) {
        state.appState.execution = res.execution;
        renderComposerControls();
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
          <span class="meta-chip ${execMode === "chat" ? "neutral" : (execMode === "mono" ? "secondary" : "accent")}">${execMode === "chat" ? "CHAT DIRECT" : (execMode === "mono" ? "MONO-AGENT" : "MULTI-AGENT")}</span>
        </div>

        <div style="font-size:11px; font-weight:700; text-transform:uppercase; color:var(--text-muted); letter-spacing:0.04em;">MODE D'EXÉCUTION</div>
        <div class="execution-mode-selector">
          <label class="execution-mode-option ${execMode === "chat" ? "selected" : ""}" data-set-execution-mode="chat">
            <input type="radio" name="cockpit_mode_radio" value="chat" ${execMode === "chat" ? "checked" : ""} data-set-execution-mode="chat">
            <div class="exec-mode-label">
              <div class="exec-mode-title-row">
                <div class="exec-mode-title-wrap">
                  <span class="exec-mode-icon chat-icon-badge">${ICONS.chatMode}</span>
                  <span class="exec-mode-title">Chat direct (Sans agent)</span>
                </div>
                <span class="exec-mode-badge token-eco">Économie tokens</span>
              </div>
              <span class="exec-mode-desc">Discussion directe avec Gemini · 0 outil · 0 surcoût</span>
            </div>
          </label>
          <label class="execution-mode-option ${execMode === "mono" ? "selected" : ""}" data-set-execution-mode="mono">
            <input type="radio" name="cockpit_mode_radio" value="mono" ${execMode === "mono" ? "checked" : ""} data-set-execution-mode="mono">
            <div class="exec-mode-label">
              <div class="exec-mode-title-row">
                <div class="exec-mode-title-wrap">
                  <span class="exec-mode-icon mono-icon-badge">${ICONS.monoAgent}</span>
                  <span class="exec-mode-title">Mono-Agent</span>
                </div>
                <span class="exec-mode-badge default-pill">Par défaut</span>
              </div>
              <span class="exec-mode-desc">1 agent séquentiel complet (Free Tier recommandé)</span>
            </div>
          </label>
          <label class="execution-mode-option ${execMode === "multi" ? "selected" : ""}" data-set-execution-mode="multi">
            <input type="radio" name="cockpit_mode_radio" value="multi" ${execMode === "multi" ? "checked" : ""} data-set-execution-mode="multi">
            <div class="exec-mode-label">
              <div class="exec-mode-title-row">
                <div class="exec-mode-title-wrap">
                  <span class="exec-mode-icon multi-icon-badge">${ICONS.multiAgent}</span>
                  <span class="exec-mode-title">Multi-Agent</span>
                </div>
                <span class="exec-mode-badge multi-pill">DAG</span>
              </div>
              <span class="exec-mode-desc">DAG asynchrone borné (${maxParallel} agents max)</span>
            </div>
          </label>
        </div>

        <div class="execution-concurrency-row">
          <div class="concurrency-label-wrap">
            <span class="concurrency-title">Agents simultanés</span>
            <span class="concurrency-hint">${execMode === "chat" ? "Désactivé en Chat direct (aucun agent)" : (execMode === "mono" ? "1 = très prudent (verrouillé en Mono)" : "Limite stricte de concurrence")}</span>
          </div>
          <select class="concurrency-select" data-set-execution-concurrency ${execMode !== "multi" ? "disabled" : ""}>
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
            <span class="tel-val ${activeCalls > 0 ? "highlight-active" : ""}">${execMode === "chat" ? "0 / 0 (Chat direct)" : `${activeCalls} / ${execMode === "mono" ? 1 : maxParallel}`}</span>
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
      </div>

      <button type="button" class="model-line" data-open-model-modal>
        <span>Modèle actif</span>
        <span class="model-line-value">${esc(compat.selection_mode === "auto" ? "Auto" : model ? model.display_name.split(" (")[0] : "—")} ${ICONS.chevronRight}</span>
      </button>

      <div class="inspector-card">
        <div class="inspector-card-title">
          <span>Architecture & Capacités Réelles</span>
          <span class="meta-chip accent">${esc(chain.provider || "auto")}</span>
        </div>
        <div class="model-identity-box">
          <div class="model-identity-name">${esc(model ? model.display_name : "Routage Automatique (ModelRouter)")}</div>
          <div class="model-identity-sub">${esc(model ? model.status_detail : "Sélection dynamique selon la complexité de la tâche")}</div>
        </div>
        <div class="capabilities-grid-2">
          ${capRows
            .map(
              ([label, val]) => `
              <div class="cap-cell ${val ? "active" : "inactive"}">
                <span class="cap-icon">${val ? ICONS.check : ICONS.dotHollow}</span>
                <div class="cap-info">
                  <span class="cap-label">${esc(label)}</span>
                  <span class="cap-val mono">${val === true ? "Actif" : val ? esc(val) : "Non"}</span>
                </div>
              </div>
            `
            )
            .join("")}
        </div>
      </div>

      <div class="inspector-card">
        <div class="inspector-card-title">
          <span>Domaines fonctionnels</span>
          <span class="meta-chip">${avail.length} Skills prêts</span>
        </div>
        ${domains
          .map(
            (d) => `
            <div class="inspector-kv" title="${esc(d.reason)}">
              <span class="k" style="display:inline-flex; align-items:center; gap:6px;">
                <span style="color:${d.available ? "var(--success)" : "var(--warning)"}; display:inline-flex;">${d.available ? ICONS.check : ICONS.dotHollow}</span>
                <span>${esc(d.label)}</span>
              </span>
              <span class="v" style="color:${d.available ? "var(--text-primary)" : "var(--warning)"};">${esc(d.backing_skill)}</span>
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
                <div style="padding:4px 0; font-size:11.5px; display:flex; align-items:center; gap:6px;">
                  <span style="color:var(--warning); display:inline-flex;">${ICONS.dotHollow}</span>
                  <strong>/${esc(sk.name)}</strong> — <span style="color:var(--warning);">${esc(sk.compatibility_reason)}</span>
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
          <span>Catalogue des Skills (${skills.length})</span>
          <button class="skill-pill ${isAuto ? "active" : ""}" data-composer-skill="auto">
            ${isAuto ? `${ICONS.check} Mode Auto` : "Passer en Auto"}
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
                <span style="display:inline-flex; align-items:center; gap:6px; min-width:0;">
                  <span class="mono" style="font-size:10.5px; color:var(--text-muted); min-width:18px;">${num}.</span>
                  <span style="color:${sk.compatible ? "var(--success)" : "var(--warning)"}; display:inline-flex;">${sk.compatible ? ICONS.check : ICONS.dotHollow}</span>
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
      return ICONS.search;
    }
    if (raw.startsWith("compile") || ev === "compilation") {
      return ICONS.bolt;
    }
    if (raw.startsWith("verify") || ev === "verifier") {
      return ICONS.check;
    }
    if (raw.startsWith("tool") || ev.startsWith("tool")) {
      return ICONS.tool;
    }
    if (raw.startsWith("plan") || ev.startsWith("plan")) {
      return ICONS.sparkle;
    }
    return ICONS.agent;
  }

  function renderInspectorActivityTab() {
    const s = state.appState;
    const events = (s.events || []).slice();
    const isDev = Boolean(s.preferences && s.preferences.developer_mode);
    const b = state.liveBudget || {
      tokens_used: 0,
      tokens_limit: 100000,
      time_elapsed: 0,
      time_limit: 300,
      tool_calls: 0,
      tool_limit: 50,
    };

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

    // Ne conserver que les étapes de plan qui ont un vrai texte descriptif (élimine 1. 2. 3. 4. 5. vides)
    const validPlanSteps = (state.livePlan || []).filter(
      (st) => st && String(st.description || "").trim().length > 0
    );

    return `
      <div class="activity-panel-wrap">
        <div class="activity-panel-header">
          <div class="activity-panel-title">
            <span>Journal d'activité (${events.length})</span>
            ${state.isExecuting ? '<span class="step-badge in_progress"><span class="pulse-dot"></span>En direct</span>' : ""}
          </div>
          <div style="display:flex; align-items:center; gap:6px;">
            ${
              state.isExecuting
                ? `
              <button id="btn-activity-stop" class="activity-stop-btn" title="Interrompre immédiatement la tâche en cours">
                <span>Arrêter</span>
              </button>
            `
                : ""
            }
            <button id="btn-toggle-devmode" class="skill-pill ${isDev ? "active" : ""}">
              ${isDev ? `${ICONS.dotFilled} Mode Dev` : `${ICONS.dotHollow} Mode Dev`}
            </button>
          </div>
        </div>

        <!-- 1. JAUGES DE BUDGET TEMPS RÉEL COMPACTES -->
        <div class="budget-gauge-grid">
          <div class="budget-gauge-card">
            <div class="gauge-label-row"><span>Tokens</span><span class="mono">${tPct}%</span></div>
            <div class="gauge-value-row mono">${tUsed} / ${tMax}</div>
            <div class="gauge-bar"><div class="gauge-fill ${tColor}" style="width:${tPct}%;"></div></div>
          </div>
          <div class="budget-gauge-card">
            <div class="gauge-label-row"><span>Temps</span><span class="mono">${timePct}%</span></div>
            <div class="gauge-value-row mono">${timeUsed}s / ${timeMax}s</div>
            <div class="gauge-bar"><div class="gauge-fill ${timeColor}" style="width:${timePct}%;"></div></div>
          </div>
          <div class="budget-gauge-card">
            <div class="gauge-label-row"><span>Outils</span><span class="mono">${callsPct}%</span></div>
            <div class="gauge-value-row mono">${callsUsed} / ${callsMax}</div>
            <div class="gauge-bar"><div class="gauge-fill ${callsColor}" style="width:${callsPct}%;"></div></div>
          </div>
        </div>

        <!-- 2. SUIVI DU PLAN EN DIRECT (UNIQUEMENT SI NON VIDE) -->
        ${
          validPlanSteps.length > 0
            ? `
          <div class="live-plan-card">
            <div class="inspector-card-title"><span>Plan d'exécution</span></div>
            ${validPlanSteps
              .map(
                (st, idx) => `
              <div class="plan-step-row">
                <span class="step-badge ${esc(st.status || "pending")}">
                  ${
                    st.status === "in_progress"
                      ? '<span class="pulse-dot"></span>En cours'
                      : st.status === "completed"
                      ? `${ICONS.check} Fait`
                      : st.status === "error"
                      ? `${ICONS.close} Échec`
                      : "À faire"
                  }
                </span>
                <span><strong>${idx + 1}.</strong> ${esc(st.description)}</span>
              </div>
            `
              )
              .join("")}
          </div>
        `
            : ""
        }

        <!-- 3. COMPILATION EN DIRECT -->
        ${
          state.liveCompile
            ? `
          <div class="live-banner-box compile">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <strong>Compilation ${esc(state.liveCompile.attempt)}/${esc(state.liveCompile.max_attempts)}</strong>
              <span class="step-badge ${esc(state.liveCompile.status)}">${esc(state.liveCompile.status)}</span>
            </div>
            ${state.liveCompile.message ? `<div style="color:var(--error);">Erreur ligne ${esc(state.liveCompile.line || "?")} : ${esc(state.liveCompile.message)}</div>` : ""}
            ${state.liveCompile.note ? `<div style="color:var(--text-secondary);">Action : ${esc(state.liveCompile.note)}</div>` : ""}
          </div>
        `
            : ""
        }

        <!-- 4. RECHERCHE WEB EN DIRECT -->
        ${
          state.liveSearch
            ? `
          <div class="live-banner-box search">
            <strong>Recherche & Téléchargement Web</strong>
            ${state.liveSearch.query ? `<div>Requête : <code>${esc(state.liveSearch.query)}</code></div>` : ""}
            ${
              state.liveSearch.rejected && state.liveSearch.rejected.length
                ? `
              <div style="font-size:10.5px; color:var(--text-muted);">
                Candidats rejetés (${state.liveSearch.rejected.length}) :
                ${state.liveSearch.rejected.map((r) => `<div>- ${esc(r.url)} : ${esc(r.reason)}</div>`).join("")}
              </div>
            `
                : ""
            }
            ${
              state.liveSearch.verified
                ? `
              <div style="color:#2b8a3e; font-weight:500; display:inline-flex; align-items:center; gap:4px;">
                ${ICONS.check} Validé : <code>${esc(state.liveSearch.verified.destination)}</code> (${state.liveSearch.verified.size_bytes} octets)
              </div>
            `
                : ""
            }
          </div>
        `
            : ""
        }

        <!-- 5. TIMELINE DES ÉVÉNEMENTS TEMPS RÉEL -->
        <div id="activity-scroll-body" style="overflow-y:auto; max-height:480px; display:flex; flex-direction:column; gap:6px;">
          ${
            events.length === 0
              ? `<div class="inspector-card">Aucune activité enregistrée.</div>`
              : events
                  .map((e) => {
                    const rawStatus = (e.status || "info").toLowerCase();
                    const badgeClass =
                      rawStatus === "running"
                        ? "in_progress"
                        : rawStatus === "completed" || rawStatus === "success" || rawStatus === "ok"
                        ? "completed"
                        : rawStatus === "error" || rawStatus === "denied"
                        ? "error"
                        : "pending";
                    const dur = e.duration_ms
                      ? e.duration_ms >= 1000
                        ? (e.duration_ms / 1000).toFixed(1) + "s"
                        : e.duration_ms + "ms"
                      : "";
                    const detailsObj = e.data || e.details || {};
                    const hasDetails = Object.keys(detailsObj).length > 0;
                    const badgeLabel = isDev ? e.event : humanizeEventBadge(e.event);
                    return `
              <div class="timeline-item">
                <div class="timeline-head">
                  <div class="timeline-title-wrap">
                    <span class="timeline-icon-box">${getEventIconSvg(e.event, e.raw_event)}</span>
                    <span class="step-badge ${badgeClass}" title="${esc(e.event)}">${rawStatus === "running" ? '<span class="pulse-dot"></span>' : ""}${esc(badgeLabel)}</span>
                  </div>
                  <div style="display:flex; align-items:center; gap:6px;">
                    ${dur ? `<span class="timeline-duration mono">${esc(dur)}</span>` : ""}
                    <span class="mono" style="font-size:10px; color:var(--text-muted);">${esc((e.timestamp || "").slice(11, 19))}</span>
                  </div>
                </div>
                <div class="timeline-summary">${esc(e.summary)}</div>
                ${
                  hasDetails
                    ? `
                  <details class="timeline-collapsible">
                    <summary>Détails techniques</summary>
                    <pre>${esc(JSON.stringify(detailsObj, null, 2))}</pre>
                  </details>
                `
                    : ""
                }
              </div>
            `;
                  })
                  .join("")
          }
        </div>
        <button id="btn-resume-scroll" class="scroll-resume-btn" style="display:none;">${ICONS.arrowDown} Reprendre le défilement</button>
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
    // Filtrer strictement .harness/ et .neoharness/ (shadow.git)
    const files = (ws.files || []).filter((f) => !isHiddenInternalPath(f.path));
    const changes = (ws.changes || []).filter((ch) => !isHiddenInternalPath(ch.path));

    return `
      <div class="inspector-card">
        <div class="inspector-card-title">
          <span>Fichiers du Workspace (${files.length})</span>
          <button type="button" class="sidebar-danger-btn" data-clear-workspace-files ${files.length === 0 ? "disabled" : ""} title="Supprimer tous les fichiers du workspace">
            ${ICONS.trash}
            <span>Tout supprimer</span>
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
                    const isDocx = lower.endsWith(".docx");
                    const isHtml = lower.endsWith(".html") || lower.endsWith(".htm");
                    const isTex = lower.endsWith(".tex");
                    const typ = detectArtifactType(f.path);
                    return `
                      <div class="sidebar-item" style="padding:5px 8px;">
                        <div class="sidebar-item-main" data-preview-file="${esc(f.path)}">
                          <span style="color:var(--text-muted); display:inline-flex;">${getArtifactIconSvg(typ)}</span>
                          <span class="sidebar-item-title mono" style="font-size:11.5px;">${esc(f.path)}</span>
                          ${f.status ? `<span class="meta-chip accent">${esc(f.status)}</span>` : ""}
                        </div>
                        <div style="display:flex; gap:4px; flex-shrink:0;">
                          ${
                            isPdf
                              ? `<button class="icon-btn-mini" data-open-doc-preview="pdf" data-doc-path="${esc(f.path)}" title="Aperçu PDF">${ICONS.filePdf} PDF</button>`
                              : isDocx
                              ? `<button class="icon-btn-mini" data-open-doc-preview="docx" data-doc-path="${esc(f.path)}" title="Aperçu Word">${getArtifactIconSvg("docx")} Word</button>`
                              : isHtml
                              ? `<button class="icon-btn-mini" data-open-doc-preview="html" data-doc-path="${esc(f.path)}" title="Aperçu HTML">${ICONS.globe} HTML</button>`
                              : isTex
                              ? `<button class="icon-btn-mini" data-compile-tex-path="${esc(f.path)}" title="Compiler avec Tectonic">${ICONS.bolt} PDF</button>`
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
              <button class="icon-btn-mini" id="btn-close-file-preview">${ICONS.close}</button>
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
                  <div style="border-top:1px solid var(--border-subtle); padding-top:8px; margin-top:6px;">
                    <div class="inspector-kv">
                      <span class="k"><strong class="mono">[${esc(ch.status)}] ${esc(ch.path)}</strong></span>
                      <span class="v mono"><span style="color:#16a34a;">+${ch.added_lines}</span> / <span style="color:var(--error);">-${ch.removed_lines}</span></span>
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
          Cliquez sur un outil pour inspecter ses permissions et paramètres.
        </div>
      </div>
      ${tools
        .map(
          (t) => `
          <details class="compact-row-details">
            <summary>
              <span class="mono" style="display:inline-flex; align-items:center; gap:6px;">${ICONS.tool} ${esc(t.name)}</span>
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
            : sessionNotes.map((n) => `<div style="font-size:11.5px;">· ${esc(n)}</div>`).join("")
        }
      </div>

      <div class="inspector-card">
        <div class="inspector-card-title"><span>Projet (${projNotes.length}) & Décisions (${decisions.length})</span></div>
        ${projNotes.map((n) => `<div style="font-size:11.5px; display:flex; align-items:center; gap:6px;">${ICONS.folder} <span>${esc(n)}</span></div>`).join("")}
        ${decisions.map((d) => `<div style="font-size:11.5px; display:flex; align-items:center; gap:6px;">${ICONS.check} <span>${esc(d)}</span></div>`).join("")}
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

  function confirmModal({ title = "Confirmer", message = "", confirmLabel = "Supprimer", danger = true } = {}) {
    return new Promise((resolve) => {
      const modal = document.getElementById("modal-confirm");
      const okBtn = document.getElementById("confirm-ok");
      const cancelBtn = document.getElementById("confirm-cancel");
      if (!modal || !okBtn || !cancelBtn) {
        resolve(window.confirm(message));
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
      const onBackdrop = (e) => {
        if (e.target === modal) finish(false);
      };
      const onKey = (e) => {
        if (e.key === "Escape") {
          e.preventDefault();
          e.stopPropagation();
          finish(false);
        } else if (e.key === "Enter") {
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
      setTimeout(() => cancelBtn.focus(), 30);
    });
  }

  async function renderLibraryModal() {
    const body = document.getElementById("modal-library-body");
    if (!body) return;
    body.innerHTML =
      '<div style="text-align: center; padding: 24px; color: var(--text-muted);">Chargement de la bibliothèque du workspace…</div>';

    try {
      const res = await apiGet("/api/files");
      const rawFiles =
        (res && res.files) ||
        (state.appState && state.appState.workspace && state.appState.workspace.files) ||
        [];
      const files = rawFiles.filter((f) => !isHiddenInternalPath(f.path));

      body.innerHTML = `
        <div class="library-search-box">
          <input type="text" id="library-search-input" class="library-search-input" placeholder="Filtrer les fichiers, templates, scripts (.tex, .py, .html, .csv)..." />
          <button type="button" class="send-btn" id="library-btn-upload-file" style="height:34px;">+ Importer</button>
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
        const filtered = files.filter(
          (f) =>
            !q ||
            (f.path || f.name).toLowerCase().includes(q) ||
            (f.extension || "").toLowerCase().includes(q)
        );
        if (filtered.length === 0) {
          listEl.innerHTML = `<div style="padding: 24px; text-align: center; color: var(--text-muted); font-size: 13px;">Aucun fichier trouvé pour "${esc(filter)}".</div>`;
          return;
        }
        listEl.innerHTML = filtered
          .map((f) => {
            const isAttached = state.attachedFiles.includes(f.path);
            const sizeKb = Math.max(1, Math.round((f.size_bytes || 0) / 1024));
            const ext = (f.extension || "").replace(".", "").toUpperCase() || "FILE";
            return `
            <div class="library-file-item">
              <div class="library-file-info">
                <div class="library-file-name">
                  <span class="library-badge">${esc(ext)}</span>
                  <span>${esc(f.name || f.path)}</span>
                </div>
                <div class="library-file-meta">${esc(f.path)} · ${sizeKb} Ko</div>
              </div>
              <button type="button" class="icon-btn-mini" data-attach-lib-file="${esc(f.path)}" style="${isAttached ? "color: var(--success); font-weight: 600;" : ""}">
                ${isAttached ? `${ICONS.check} Joint` : "+ Joindre"}
              </button>
            </div>
          `;
          })
          .join("");
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
          btn.innerHTML = `${ICONS.check} Joint`;
          btn.style.color = "var(--success)";
          btn.style.fontWeight = "600";
          renderComposer();
        } else {
          state.attachedFiles = state.attachedFiles.filter((p) => p !== fpath);
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
      if (n >= 1000000) return `${Math.round(n / 100000) / 10}M tokens`;
      if (n >= 1000) return `${Math.round(n / 1000)}k tokens`;
      return n > 0 ? `${n} tokens` : "";
    };

    const getProviderFamily = (m) => {
      const fam = (m.provider_family || "").toLowerCase();
      const txt = `${m.id} ${m.display_name} ${m.provider_class || ""}`.toLowerCase();
      if (fam === "gemini" || /gemini|google/.test(txt)) return "Google DeepMind";
      if (fam === "openai" || /gpt|openai/.test(txt)) return "OpenAI";
      if (fam === "mistral" || /mistral/.test(txt)) return "Mistral AI";
      if (fam === "ollama" || /ollama|qwen|local/.test(txt)) return "Modèles Locaux (Ollama)";
      if (fam === "claude" || /claude|anthropic/.test(txt)) return "Anthropic";
      return "Autres Modèles";
    };

    const getProviderIcon = (group) => {
      if (group === "Google DeepMind") {
        return `<svg class="cap-svg" style="color:#4285F4;" viewBox="0 0 24 24"><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm1 14.93V17a1 1 0 0 1-2 0v-.07A7.003 7.003 0 0 1 5.07 11H7a1 1 0 0 1 0-2H5.07A7.003 7.003 0 0 1 11 5.07V7a1 1 0 0 1 2 0V5.07A7.003 7.003 0 0 1 18.93 11H17a1 1 0 0 1 0 2h1.93A7.003 7.003 0 0 1 13 16.93z"/></svg>`;
      }
      if (group === "OpenAI") {
        return `<svg class="cap-svg" style="color:#10A37F;" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M8 12h8M12 8v8"/></svg>`;
      }
      if (group === "Mistral AI") {
        return `<svg class="cap-svg" style="color:#F36B28;" viewBox="0 0 24 24"><path d="M3 3h4v18H3zm7 5h4v13h-4zm7-3h4v16h-4z"/></svg>`;
      }
      if (group === "Modèles Locaux (Ollama)") {
        return `<svg class="cap-svg" style="color:#8B5CF6;" viewBox="0 0 24 24"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>`;
      }
      return `<svg class="cap-svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/></svg>`;
    };

    const renderCard = (m) => {
      const isSelected = currentId === m.id;
      const isConnected = m.connected !== false;
      const caps = m.capabilities || {};
      const ctxText = fmtCtx(caps.context);
      const cleanName = (m.display_name || m.id).split(" (")[0];
      const modelId = m.model_name || m.id;
      const groupName = getProviderFamily(m);
      const searchTerms = `${cleanName} ${modelId} ${groupName} ${ctxText} ${caps.vision ? "vision" : ""} ${caps.tools ? "outils tools" : ""} ${caps.web_grounding ? "web" : ""} ${caps.reasoning ? "raisonnement" : ""}`.toLowerCase();

      return `
        <div class="mp-model-card ${isSelected ? "is-selected" : ""} ${!isConnected ? "is-disconnected" : ""}" data-pick-model="${esc(m.id)}" data-q="${esc(searchTerms)}">
          <div class="mp-card-header">
            <div class="mp-card-title-wrap">
              <span class="mp-provider-icon">${getProviderIcon(groupName)}</span>
              <span class="mp-model-display-name">${esc(cleanName)}</span>
              <span class="mp-model-id mono">${esc(modelId)}</span>
            </div>
            <div class="mp-card-badges">
              ${
                isConnected
                  ? `<span class="mp-status-pill online"><span class="dot"></span> ${esc(m.status_label || "Disponible")}</span>`
                  : `<span class="mp-status-pill offline"><span class="dot"></span> ${esc(m.status_label || "Non configuré")}</span>`
              }
              ${isSelected ? `<span class="mp-selected-badge">${ICONS.check} Actif</span>` : ""}
            </div>
          </div>

          <div class="mp-caps-strip">
            ${ctxText ? `<span class="mp-cap-tag mono highlight" title="Fenêtre de contexte maximale">${esc(ctxText)}</span>` : ""}
            ${caps.reasoning ? `<span class="mp-cap-tag active" title="Raisonnement structuré"><svg class="cap-svg" viewBox="0 0 24 24"><path d="M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.2 1 2.3h6c0-1.1.4-1.8 1-2.3A7 7 0 0 0 12 2z"/></svg> Raisonnement</span>` : ""}
            ${caps.vision ? `<span class="mp-cap-tag active" title="Vision & analyse d'images multimodale"><svg class="cap-svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/></svg> Vision</span>` : ""}
            ${caps.tools ? `<span class="mp-cap-tag active" title="Appel d'outils / Function Calling"><svg class="cap-svg" viewBox="0 0 24 24"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg> Outils</span>` : ""}
            ${caps.web_grounding ? `<span class="mp-cap-tag active" title="Recherche Web Google en temps réel"><svg class="cap-svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg> Web direct</span>` : ""}
            ${caps.structured_output ? `<span class="mp-cap-tag passive" title="JSON structuré garanti"><svg class="cap-svg" viewBox="0 0 24 24"><rect width="18" height="18" rx="2"/><path d="M8 7h8M8 12h8M8 17h5"/></svg> JSON</span>` : ""}
            ${caps.streaming ? `<span class="mp-cap-tag passive" title="Streaming token par token"><svg class="cap-svg" viewBox="0 0 24 24"><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/></svg> Streaming</span>` : ""}
          </div>
          ${!isConnected && m.status_detail ? `<div style="font-size:11px; color:var(--warning); margin-top:1px;">⚠️ ${esc(m.status_detail)}</div>` : ""}
        </div>
      `;
    };

    const groups = {};
    const groupOrder = ["Google DeepMind", "OpenAI", "Mistral AI", "Modèles Locaux (Ollama)", "Anthropic", "Autres Modèles"];

    (s.models || []).forEach((m) => {
      const g = getProviderFamily(m);
      groups[g] = groups[g] || [];
      groups[g].push(renderCard(m));
    });

    const isAutoSelected = currentId === "auto";
    const autoCardHtml = `
      <div class="mp-model-card ${isAutoSelected ? "is-selected" : ""}" data-pick-model="auto" data-q="auto automatique routage selection dynamique">
        <div class="mp-card-header">
          <div class="mp-card-title-wrap">
            <span class="mp-provider-icon">✨</span>
            <span class="mp-model-display-name">Routage Automatique (ModelRouter)</span>
            <span class="mp-model-id mono">Dynamique</span>
          </div>
          <div class="mp-card-badges">
            <span class="mp-status-pill online"><span class="dot"></span> Recommandé</span>
            ${isAutoSelected ? `<span class="mp-selected-badge">${ICONS.check} Actif</span>` : ""}
          </div>
        </div>
        <div class="mp-caps-strip">
          <span class="mp-cap-tag highlight">Multi-Fournisseurs</span>
          <span class="mp-cap-tag active">Sélectionne le meilleur modèle selon la complexité et les quotas</span>
        </div>
      </div>
    `;

    body.innerHTML = `
      <div class="mp-modal-container">
        <div class="mp-search-wrap">
          <svg class="mp-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
          <input id="model-picker-search" type="search" class="mp-search-input" placeholder="Rechercher par modèle, fournisseur ou capacité (ex: vision, web, 1M)..." autocomplete="off" />
        </div>

        ${autoCardHtml}

        ${groupOrder
          .filter((g) => groups[g] && groups[g].length > 0)
          .map((g) => `
            <div class="mp-group-title">${esc(g)} (${groups[g].length})</div>
            ${groups[g].join("")}
          `)
          .join("")}
      </div>
    `;

    const searchInput = body.querySelector("#model-picker-search");
    if (searchInput) {
      searchInput.addEventListener("input", () => {
        const query = searchInput.value.trim().toLowerCase();
        const cards = body.querySelectorAll(".mp-model-card");
        cards.forEach((card) => {
          const qData = card.getAttribute("data-q") || "";
          card.style.display = !query || qData.includes(query) ? "" : "none";
        });

        // Hide empty group headers
        const groupTitles = body.querySelectorAll(".mp-group-title");
        groupTitles.forEach((header) => {
          let next = header.nextElementSibling;
          let hasVisible = false;
          while (next && !next.classList.contains("mp-group-title")) {
            if (next.classList.contains("mp-model-card") && next.style.display !== "none") {
              hasVisible = true;
              break;
            }
            next = next.nextElementSibling;
          }
          header.style.display = hasVisible ? "" : "none";
        });
      });
    }
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
                  <span style="display:inline-flex; align-items:center; gap:6px;">${ICONS.cpu} ${esc(m.display_name)}</span>
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
                  <span style="display:inline-flex; align-items:center; gap:6px;">${sk.compatible ? ICONS.check : ICONS.dotHollow} <strong>/${esc(sk.name)}</strong> — ${esc(sk.description)}</span>
                  <span class="meta-chip">${esc(sk.agent_name)}</span>
                </div>
              `
              )
              .join("")}
          </div>
        `);
      }

      const visibleFiles = (data.files || []).filter((f) => !isHiddenInternalPath(f.path));
      if (visibleFiles.length) {
        sections.push(`
          <div class="inspector-card">
            <div class="inspector-card-title"><span>Fichiers Workspace (${visibleFiles.length})</span></div>
            ${visibleFiles
              .map(
                (f) => `
                <div class="sidebar-item" data-preview-file="${esc(f.path)}">
                  <span class="mono" style="display:inline-flex; align-items:center; gap:6px;">${ICONS.filePdf} ${esc(f.path)}</span>
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
                  <span class="mono" style="display:inline-flex; align-items:center; gap:6px;">${ICONS.tool} ${esc(t.name)}</span>
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
            <div class="creator-hero-details">Orchestration multi-modèles de production, 20 Skills canoniques, recherche Web temps réel, compilation LaTeX Tectonic et interface ultra-raffinée — Zéro simulation.</div>
          </div>
        </div>
      </div>

      <div class="inspector-card">
        <div class="inspector-card-title"><span>Clés API des Providers (Session & .env local)</span></div>
        <div style="font-size:11.5px; color:var(--text-secondary); margin-bottom:6px;">
          Activées immédiatement et enregistrées dans <code>.env</code> (jamais réaffichées en clair).
        </div>
        <div class="inspector-kv" style="margin-top:4px;">
          <span class="k">Google Gemini (<code>GEMINI_API_KEY</code>) — ${creds.GEMINI_API_KEY ? `<strong style="color:var(--success); display:inline-flex; align-items:center; gap:4px;">${ICONS.check} Configurée</strong>` : '<span style="color:var(--warning);">Absente</span>'}</span>
          <input id="settings-key-gemini" type="password" placeholder="${creds.GEMINI_API_KEY ? "•••••••• (conserver)" : "Clé AIza..."}" class="sidebar-search" style="width:220px;" autocomplete="off" />
        </div>
        <div class="inspector-kv" style="margin-top:4px;">
          <span class="k">OpenAI (<code>OPENAI_API_KEY</code>) — ${creds.OPENAI_API_KEY ? `<strong style="color:var(--success); display:inline-flex; align-items:center; gap:4px;">${ICONS.check} Configurée</strong>` : '<span style="color:var(--warning);">Absente</span>'}</span>
          <input id="settings-key-openai" type="password" placeholder="${creds.OPENAI_API_KEY ? "•••••••• (conserver)" : "Clé sk-..."}" class="sidebar-search" style="width:220px;" autocomplete="off" />
        </div>
        <div class="inspector-kv" style="margin-top:4px;">
          <span class="k">Mistral AI (<code>MISTRAL_API_KEY</code>) — ${creds.MISTRAL_API_KEY ? `<strong style="color:var(--success); display:inline-flex; align-items:center; gap:4px;">${ICONS.check} Configurée</strong>` : '<span style="color:var(--warning);">Absente</span>'}</span>
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
    state.liveStartedAt = Date.now();
    state.activeSubAgent = "";
    state.liveCollapsedOnce = false;
    state.activeDocument = null;
    state.pdfDocCache = null;
    switchRightPanelMode("inspector");
    if (state.liveTimerInterval) clearInterval(state.liveTimerInterval);
    state.liveTimerInterval = setInterval(() => {
      if (state.isExecuting && state.liveSteps.length > 0 && !state.liveCollapsedOnce) {
        const timerEl = document.querySelector("#live-activity-summary .reasoning-timer");
        if (timerEl && state.liveStartedAt) {
          timerEl.textContent = `${((Date.now() - state.liveStartedAt) / 1000).toFixed(1)}s`;
        }
      }
    }, 100);

    showOptimisticUserBubble(promptText.trim());
    paintStreamBody();
    kickTypewriter();
    const sc0 = document.getElementById("workspace-scroll");
    if (sc0) sc0.scrollTop = sc0.scrollHeight;

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
    const taskPillEl = document.getElementById("top-task-pill");
    if (taskPillEl) taskPillEl.style.display = "inline-flex";
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

      const activeCid =
        (state.appState && state.appState.active_conversation && state.appState.active_conversation.id) || "";
      const currentExecMode = (state.appState && state.appState.execution && state.appState.execution.mode) || state.executionMode || (state.deepReflection ? "multi" : "mono");
      const effectiveMode = currentExecMode === "chat" ? "chat" : (currentExecMode === "multi" || state.deepReflection ? "multi" : "mono");
      const runData = await apiPost("/api/tasks/run", {
        prompt: promptText.trim(),
        attachments: attachments,
        conversation_id: activeCid,
        deep_reflection: effectiveMode === "multi",
        execution_mode: effectiveMode,
      });
      await drainTypewriter(1500);
      const scKeep = document.getElementById("workspace-scroll");
      const keepTop = scKeep ? scKeep.scrollTop : 0;
      await refreshFullState();
      if (scKeep) scKeep.scrollTop = keepTop;

      const assistantMsg = (runData && (runData.assistant_message || runData.result)) || {};
      const artifacts =
        (runData && runData.preview_artifacts) ||
        assistantMsg.preview_artifacts ||
        assistantMsg.artifacts ||
        [];
      const previewArt = [...artifacts].reverse().find((a) => a && a.path);
      if (previewArt) {
        await openDocumentPreview(previewArt);
      } else if (assistantMsg.content) {
        const exportMatch = String(assistantMsg.content).match(
          /\[EXPORT OK\]\s+([^\s|]+\.(?:pdf|docx|html|py|svg|mmd|mermaid|json|csv|md|png|jpg))/i
        );
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
      state.activeSubAgent = "";
      if (state.liveTimerInterval) {
        clearInterval(state.liveTimerInterval);
        state.liveTimerInterval = null;
      }
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
      renderComposerControls();
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
    const btnViewWord = document.getElementById("btn-doc-view-word");
    if (btnViewWord) {
      btnViewWord.addEventListener("click", () => {
        if (state.activeDocument) {
          state.activeDocument.viewMode = "word";
          renderDocumentPreviewPanel();
        }
      });
    }
    const btnViewPdf = document.getElementById("btn-doc-view-pdf");
    if (btnViewPdf) {
      btnViewPdf.addEventListener("click", () => {
        if (state.activeDocument) {
          state.activeDocument.viewMode = "pdf";
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
              showStatusBanner("Script Python exécuté avec succès.", "success");
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
            showStatusBanner(
              `Page HTML validée et actualisée (${comp.size_bytes || editor.value.length} octets).`,
              "success"
            );
          } else if (doc.type === "tex") {
            doc.sourceContent = editor.value;
            await apiPost("/api/files/write", { path: doc.path, content: editor.value });
            await compileLatexAndPreview(doc.path, editor.value);
            showStatusBanner("Source LaTeX enregistrée et compilée.", "success");
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
            showStatusBanner("Artefact mis à jour et validé.", "success");
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
          <div style="flex: 1; min-width: 0; display:flex; align-items:center; gap:6px;">
            ${ICONS.alert}
            <span><strong>Erreur d'exécution JS :</strong> ${esc(err.message)}</span>
            ${err.lineno ? `<span class="mono" style="opacity: 0.85; margin-left: 4px;">(ligne ${err.lineno})</span>` : ""}
          </div>
          <button type="button" id="btn-fix-runtime-error" class="composer-chip-btn" style="margin-left: 8px; flex-shrink: 0;">
            ${ICONS.edit}
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
      state.activeDocument = null;
      state.pdfDocCache = null;
      switchRightPanelMode("inspector");
      await apiPost("/api/conversations/create", { title: "Nouvelle tâche" });
      await refreshFullState();
      document.getElementById("composer-input").focus();
    });
    document.getElementById("btn-brand-home").addEventListener("click", async () => {
      state.activeDocument = null;
      state.pdfDocCache = null;
      switchRightPanelMode("inspector");
      await apiPost("/api/conversations/create", { title: "Nouvelle tâche" });
      await refreshFullState();
    });

    // Supprimer TOUTES les discussions
    const btnDelAllConvs = document.getElementById("btn-delete-all-convs");
    if (btnDelAllConvs) {
      btnDelAllConvs.addEventListener("click", async () => {
        const convs = (state.appState && state.appState.conversations) || [];
        if (convs.length === 0) {
          showStatusBanner("Aucune discussion à supprimer.", "info");
          return;
        }
        if (
          !(await confirmModal({
            title: "Supprimer toutes les discussions ?",
            message: `${convs.length} discussion(s) seront supprimées définitivement. Cette action est irréversible.`,
            confirmLabel: "Tout supprimer",
          }))
        )
          return;
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

    // Supprimer TOUS les fichiers du workspace (onglet Fichiers)
    
    document.body.addEventListener("change", (e) => {
      const target = e.target;
      if (target && target.hasAttribute("data-set-execution-concurrency")) {
        window.setAgentConcurrency(target.value);
      }
    });

    document.body.addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-clear-workspace-files]");
      if (!btn || btn.disabled) return;
      const rawFiles =
        (state.appState && state.appState.workspace && state.appState.workspace.files) || [];
      const count = rawFiles.filter((f) => !isHiddenInternalPath(f.path)).length;
      if (
        !(await confirmModal({
          title: "Supprimer tous les fichiers ?",
          message: `${count} fichier(s) du workspace (PDF, exports, uploads…) seront supprimés définitivement.`,
          confirmLabel: "Tout supprimer",
        }))
      )
        return;
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

    const composerInput = document.getElementById("composer-input");
    composerInput.addEventListener("input", () => {
      composerInput.style.height = "auto";
      const newH = Math.min(Math.max(composerInput.scrollHeight, 40), 200);
      composerInput.style.height = `${newH}px`;
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

    document.getElementById("btn-send-task").addEventListener("click", () => {
      if (state.isExecuting) {
        stopTaskExecution();
        return;
      }
      submitComposerTask();
    });

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
          if (chipLabel) chipLabel.textContent = mode === "AUTO" ? "Auto" : mode;
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
          showStatusBanner("Mode Réflexion approfondie (PLAN) activé.", "info");
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

    const deepReflectionBtnEl = document.getElementById("btn-deep-reflection");
    if (deepReflectionBtnEl) {
      deepReflectionBtnEl.addEventListener("click", async (e) => {
        e.preventDefault();
        e.stopPropagation();
        await window.toggleDeepReflection();
      });
    }

    const directChatBtnEl = document.getElementById("btn-direct-chat");
    if (directChatBtnEl) {
      directChatBtnEl.addEventListener("click", async (e) => {
        e.preventDefault();
        e.stopPropagation();
        await window.toggleDirectChat();
      });
    }

    document.getElementById("global-search-input").addEventListener("input", (e) => {
      runGlobalSearch(e.target.value || "");
    });

    document.addEventListener("mousedown", (e) => {
      if (state.slashPalette.open) {
        const box = document.getElementById("composer-box");
        if (box && !box.contains(e.target)) {
          closeSlashPalette();
        }
      }
    });

    document.body.addEventListener("click", async (e) => {
      const deepBtnClick = e.target.closest("#btn-deep-reflection, .deep-reflection-btn");
      if (deepBtnClick) {
        e.preventDefault();
        e.stopPropagation();
        await window.toggleDeepReflection();
        return;
      }

      const chatBtnClick = e.target.closest("#btn-direct-chat, .direct-chat-btn");
      if (chatBtnClick) {
        e.preventDefault();
        e.stopPropagation();
        await window.toggleDirectChat();
        return;
      }

      const target = e.target.closest(
        "[data-set-execution-mode], #btn-deep-reflection, #btn-direct-chat, .deep-reflection-btn, .direct-chat-btn, [data-slash-pick], [data-open-doc-preview], [data-compile-tex-path], [data-close-modal], [data-toggle-section], [data-inspector-tab], [data-open-inspector-tab], [data-select-model], [data-pick-model], [data-composer-skill], [data-search-pick-skill], [data-quick-prompt], [data-select-conv], [data-pin-conv], [data-rename-conv], [data-delete-conv], [data-approve-id], [data-preview-file], [data-attach-ws-file], [data-remove-attachment], [data-copy-msg], [data-edit-msg], [data-regen-msg], [data-show-msg-tools], [data-show-msg-sources], [data-export-last], [data-inspect-tool], #btn-close-file-preview, #btn-add-memory, #btn-clear-session-mem, #btn-run-rag-search, #btn-save-settings, #btn-toggle-devmode"
      );
      if (!target) return;

      if (target.id === "btn-deep-reflection" || target.closest("#btn-deep-reflection")) {
        await window.toggleDeepReflection();
        return;
      }

      if (target.id === "btn-direct-chat" || target.closest("#btn-direct-chat")) {
        await window.toggleDirectChat();
        return;
      }

      if (target.hasAttribute("data-set-execution-mode")) {
        const mode = target.getAttribute("data-set-execution-mode");
        if (mode) {
          window.setAgentExecutionMode(mode);
          return;
        }
      }

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
          const curr =
            (state.appState && state.appState.preferences && state.appState.preferences.active_skills) || [];
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
        const activeConv = state.appState && state.appState.active_conversation;
        const convMsgs = (activeConv && activeConv.messages) || [];
        let convArt = null;
        for (let i = convMsgs.length - 1; i >= 0; i--) {
          const m = convMsgs[i];
          const arts = m.preview_artifacts || m.artifacts || [];
          convArt = [...arts].reverse().find((a) => a && a.path);
          if (convArt) break;
        }
        if (convArt) {
          await openDocumentPreview(convArt);
        } else {
          state.activeDocument = null;
          state.pdfDocCache = null;
          switchRightPanelMode("inspector");
        }
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
        if (
          !(await confirmModal({
            title: "Supprimer cette discussion ?",
            message: `« ${(convToDelete && convToDelete.title) || "Discussion"} » sera supprimée définitivement.`,
            confirmLabel: "Supprimer",
          }))
        )
          return;
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

      const msgs =
        (state.appState && state.appState.active_conversation && state.appState.active_conversation.messages) || [];
      if (target.hasAttribute("data-copy-msg")) {
        const m = msgs[Number(target.getAttribute("data-copy-msg"))];
        if (m && navigator.clipboard) {
          navigator.clipboard.writeText(m.content || "");
          showStatusBanner("Message copié dans le presse-papiers.", "info");
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
        showStatusBanner("Paramètres enregistrés.", "info");
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
        closeModal("modal-library");
      }
    });

    const pdfHost = document.getElementById("doc-pdf-viewer");
    if (pdfHost && window.ResizeObserver) {
      let t = null;
      new ResizeObserver(() => {
        clearTimeout(t);
        t = setTimeout(() => {
          const d = state.activeDocument;
          if (
            d &&
            d.type === "pdf" &&
            d.viewMode === "render" &&
            !d.error &&
            pdfHost.clientWidth > 0 &&
            Math.abs(pdfHost.clientWidth - state.pdfWidth) > 24
          ) {
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
        if (runState.plan && runState.plan.length) {
          state.livePlan = runState.plan.filter((s) => s && String(s.description || "").trim().length > 0);
        }
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
})();;
