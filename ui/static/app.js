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
    copy: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>',
    library: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>',
    clock: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>',
    note: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg>',
    shield: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>',
    clipboard: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"></path><rect x="8" y="2" width="8" height="4" rx="1" ry="1"></rect></svg>',
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
    inspectorTab: "activity",
    libraryItems: [],
    libraryCounts: { total: 0, documents: 0, notes: 0, ressources: 0, memoire: 0 },
    libraryCategory: "Tous",
    libraryQuery: "",
    persistentMemories: [],
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
      es.onerror = () => {
        if (es.readyState === EventSource.CLOSED) {
          setTimeout(connectSSE, 5000);
        }
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
      if (state.rightPanelMode === "inspector" && state.inspectorTab === "activity") {
        renderInspector();
      }
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
      status: e.status === "running" ? "running" : (e.status === "error" ? "error" : "done"),
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

    const currentMode = state.executionMode || (state.appState && state.appState.execution && state.appState.execution.mode) || "mono";

    let activeHeadline = "";
    if (runningStep) {
      activeHeadline = `${runningStep.label}${runningStep.pill ? " · " + runningStep.pill : ""}`;
    } else if (isRunning) {
      if (currentMode === "chat") {
        activeHeadline = "Discussion directe en cours…";
      } else if (currentMode === "mono") {
        activeHeadline = "Exécution mono-agent en cours…";
      } else {
        activeHeadline = "Réflexion approfondie (Multi-Agents) en cours…";
      }
    } else {
      if (currentMode === "chat") {
        activeHeadline = `Réponse reçue en ${elapsedSec} s`;
      } else if (currentMode === "mono") {
        activeHeadline = `Exécution mono-agent terminée en ${elapsedSec} s`;
      } else {
        activeHeadline = `Réflexion terminée en ${elapsedSec} s`;
      }
    }

    const modeIcon =
      currentMode === "chat"
        ? ICONS.chatMode
        : currentMode === "mono"
        ? ICONS.monoAgent
        : ICONS.brain;

    sum.innerHTML = `
      <span class="reasoning-summary-left">
        <span class="reasoning-sparkle ${isRunning ? "pulsing" : ""}">${modeIcon}</span>
        <span class="reasoning-headline ${isRunning ? "shimmer-text" : ""}">${esc(activeHeadline)}</span>
      </span>
      <span class="reasoning-summary-right">
        ${toolCount > 0 ? `<span class="reasoning-meta-pill">${toolCount} action${toolCount > 1 ? "s" : ""}</span>` : ""}
        <span class="reasoning-timer mono">${elapsedSec}s</span>
        <span class="reasoning-chevron">${ICONS.chevronDown}</span>
      </span>
    `;
    // Effet magique d'attente lors de la génération d'image (style GPT / Gemini ImageFX)
    const fluxStep = steps.find((s) => s.tool === "cloudflare_flux");
    const imageReady = steps.some((s) => /image .*prête/i.test(s.label || ""));
    const isGeneratingImage = isRunning && !imageReady && Boolean(
      fluxStep || steps.some((s) => /fusion et optimisation du prompt/i.test(s.label || ""))
    );
    let imgCard = document.getElementById("live-image-generating-card");
    if (isGeneratingImage) {
      if (!imgCard) {
        imgCard = document.createElement("div");
        imgCard.id = "live-image-generating-card";
        imgCard.className = "nh-image-generating-card";
          const sparks = Array.from({ length: 18 }, (_, i) => {
          const big = i % 5 === 0;
          const sz = big ? 9 + Math.random() * 5 : 3 + Math.random() * 4;
          const x = 5 + Math.random() * 90;
          const y = 8 + Math.random() * 68;
          const delay = (Math.random() * 3).toFixed(2);
          const dur = (1.6 + Math.random() * 2).toFixed(2);
          return `<span class="nhg-spark${big ? " star" : ""}" style="left:${x.toFixed(1)}%;top:${y.toFixed(1)}%;width:${sz.toFixed(1)}px;height:${sz.toFixed(1)}px;animation-delay:-${delay}s;animation-duration:${dur}s"></span>`;
        }).join("");
        imgCard.innerHTML = `
          <div class="nhg-aurora"><i></i><i></i><i></i></div>
          ${sparks}
          <div class="nhg-caption">
            <span class="nhg-title">Votre image prend forme…</span>
            <span class="nhg-step"></span>
          </div>
          <span class="nhg-timer mono">0.0s</span>
        `;
        tracker.parentNode.insertBefore(imgCard, tracker.nextSibling);

        const phases = [
          "Composition de la scène…",
          "Jeu de lumière et de couleurs…",
          "Détails et textures…",
          "Dernières retouches…"
        ];
        const t0 = state.liveStartedAt || Date.now();
        const card = imgCard;
        const stepEl = card.querySelector(".nhg-step");
        const timerEl = card.querySelector(".nhg-timer");
        const tick = () => {
          if (!card.isConnected) { clearInterval(iv); return; }
          const sec = (Date.now() - t0) / 1000;
          const txt = phases[Math.floor(sec / 2.6) % phases.length];
          if (stepEl.textContent !== txt) stepEl.textContent = txt;
          timerEl.textContent = sec.toFixed(1) + "s";
        };
        const iv = setInterval(tick, 200);
        tick();
      }
    } else if (imgCard) {
      imgCard.remove();
    }


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
    const hasLatex = /\\(?:textbf|textit|partie|section|subsection|begin\{(?:enumerate|itemize|document)\}|item|frac)/.test(shown);
    if (hasLatex) {
      body.innerHTML = `
        <div class="latex-editorial-frame in-progress">
          <div class="latex-frame-header">
            <div class="latex-frame-title">
              <span class="latex-frame-badge pulse">TeX</span>
              <span>Génération du document LaTeX en cours…</span>
            </div>
            <div class="latex-frame-meta">
              <span class="meta-chip accent">Tectonic certifié</span>
            </div>
          </div>
          <div class="latex-frame-content">
            ${formatAssistantContent(shown, true)}<span class="streaming-cursor"></span>
          </div>
        </div>
      `;
    } else {
      body.innerHTML = `${shown ? formatAssistantContent(shown) : ""}<span class="streaming-cursor"></span>`;
    }
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
        state.streamShown += Math.min(backlog, Math.max(8, Math.ceil(backlog / 3)));
        paintStreamBody();
      }
      const more = state.isExecuting || state.streamShown < state.streamingBuffer.length;
      state.streamRaf = more ? requestAnimationFrame(tick) : null;
    };
    state.streamRaf = requestAnimationFrame(tick);
  }

  function drainTypewriter(maxMs = 300) {
    return new Promise((resolve) => {
      const t0 = performance.now();
      (function wait() {
        if (state.streamShown >= state.streamingBuffer.length || performance.now() - t0 > maxMs) return resolve();
        setTimeout(wait, 10);
      })();
    });
  }

function isImageAttachmentPath(p) {
    return /\.(png|jpe?g|webp|gif|bmp|svg)$/i.test(String(p || ""));
  }

  function ensureAttachmentHoverStyles() {
    if (document.getElementById("neoharness-att-hover-css")) return;
    const st = document.createElement("style");
    st.id = "neoharness-att-hover-css";
    st.textContent = `
      .att-preview-wrap { position: relative; display: inline-flex; align-items: center; gap: 6px; cursor: pointer; }
      .att-thumb-mini { width: 20px; height: 20px; object-fit: cover; border-radius: 4px; border: 1px solid rgba(0,0,0,0.12); flex-shrink: 0; }
      .att-hover-card {
        display: none; position: absolute; z-index: 9999; padding: 8px;
        background: var(--bg-surface, #ffffff); border: 1px solid var(--border-subtle, rgba(0,0,0,0.12));
        border-radius: 12px; box-shadow: 0 12px 32px rgba(0,0,0,0.22);
        pointer-events: none; width: max-content; max-width: 320px;
      }
      .att-hover-card img { display: block; max-width: 300px; max-height: 240px; width: auto; height: auto; border-radius: 8px; object-fit: contain; }
      .att-hover-caption { font-size: 11px; color: var(--text-muted, #666); margin-top: 5px; text-align: center; word-break: break-all; }
      .composer-attachments-bar .att-preview-wrap .att-hover-card { bottom: calc(100% + 10px); left: 0; }
      .message-card.user .att-preview-wrap .att-hover-card { top: calc(100% + 8px); right: 0; }
      .att-preview-wrap:hover .att-hover-card { display: block; animation: attFadeIn 0.14s ease-out; }
      @keyframes attFadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
    `;
    document.head.appendChild(st);
  }

  function renderAttachmentBadgeHtml(filePath, removable = false) {
    ensureAttachmentHoverStyles();
    const isImg = isImageAttachmentPath(filePath);
    const rawUrl = `/api/files/raw?path=${encodeURIComponent(filePath)}`;
    const fileName = String(filePath || "").split("/").pop() || filePath;
    if (removable) {
      return `
        <span class="attachment-chip att-preview-wrap">
          ${isImg ? `<img src="${rawUrl}" class="att-thumb-mini" alt="" />` : ICONS.paperclip}
          <span>${esc(fileName)}</span>
          <button class="icon-btn-mini" data-remove-attachment="${esc(filePath)}" title="Retirer">${ICONS.close}</button>
          ${isImg ? `<div class="att-hover-card"><img src="${rawUrl}" alt="${esc(fileName)}" /><div class="att-hover-caption">${esc(fileName)}</div></div>` : ""}
        </span>
      `;
    }
    return `
      <span class="meta-chip att-preview-wrap" data-preview-file="${esc(filePath)}" title="Survoler pour prévisualiser · Cliquer pour ouvrir">
        ${isImg ? `<img src="${rawUrl}" class="att-thumb-mini" alt="" />` : ICONS.paperclip}
        <span>${esc(fileName)}</span>
        ${isImg ? `<div class="att-hover-card"><img src="${rawUrl}" alt="${esc(fileName)}" /><div class="att-hover-caption">${esc(fileName)}</div></div>` : ""}
      </span>
    `;
  }

  function showOptimisticUserBubble(text, attachments = []) {
    const streamEl = document.getElementById("conversation-stream");
    const welcomeEl = document.getElementById("welcome-screen");
    if (!streamEl) return;
    if (welcomeEl) welcomeEl.style.display = "none";
    streamEl.style.display = "flex";
    const attHtml =
      attachments && attachments.length
        ? `<div class="message-meta-badges">${attachments.map((a) => renderAttachmentBadgeHtml(a, false)).join("")}</div>`
        : "";
    const el = document.createElement("article");
    el.className = "message-card user";
    el.innerHTML = `${attHtml}<div class="message-body">${esc(text)}</div>`;
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
      filterInput.style.display = "block";
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
              <div class="sidebar-time-header">
                <span>${esc(grp.label.toUpperCase())}</span>
                <span class="group-count">${grp.items.length}</span>
              </div>
              ${grp.items
                .map((c) => {
                  const isCurrent = c.id === activeCid;
                  const pinSvg = c.pinned ? `<span class="pin-indicator">${ICONS.pin}</span>` : "";
                  const archTag = c.archived ? " · archivé" : "";
                  const chatIcon = `<svg class="sidebar-chat-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="margin-right:6px; flex-shrink:0; opacity:0.75;"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>`;
                  return `
                    <div class="sidebar-item ${isCurrent ? "active" : ""}" data-select-conv="${esc(c.id)}">
                      <div class="sidebar-item-main">
                        ${chatIcon}
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
if (typ === "image") {
              return `
                <div class="artifact-card" data-open-doc-preview="image" data-doc-path="${esc(art.path)}">
                  <div class="artifact-card-icon">${iconSvg}</div>
                  <div class="artifact-card-info">
                    <span class="artifact-card-name mono">${esc(art.path.split("/").pop() || art.path)}</span>
                    <span class="artifact-card-sub">Image HD · FLUX.1${sizeKb ? " · " + esc(sizeKb) : ""}</span>
                  </div>
                  <div class="artifact-card-actions">
                    <button type="button" class="artifact-btn primary" data-open-doc-preview="image" data-doc-path="${esc(art.path)}" data-doc-view="render">
                      Aperçu HD
                    </button>
                    <a class="artifact-btn" href="/api/files/raw?path=${encodeURIComponent(art.path)}&download=1" download title="Télécharger l'image PNG">
                      ${ICONS.download} PNG
                    </a>
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
    el.textContent = "Que voulez-vous accomplir ?";
  }

  function buildCompletedReasoningHtml(m) {
    if (m.execution_mode === "chat") {
      return "";
    }
    const eventsList = (m.events || []).filter(
      (ev) => !LIVE_SKIP.has(ev.event) && ev.raw_event !== "agent.thinking"
    );
    const planSteps = (m.plan_steps || []).filter((st) => String(st || "").trim().length > 0);
    const toolsUsed = m.tools_used || [];
    const durationSec = m.duration_ms ? (m.duration_ms / 1000).toFixed(1) : "";

    if (toolsUsed.length === 0 && planSteps.length === 0 && eventsList.length === 0) {
      return "";
    }

    const isMono = m.execution_mode === "mono";
    const isMulti = m.execution_mode === "multi";
    const isDeepSearch = m.execution_mode === "deepsearch" || (Array.isArray(m.research_axes) && m.research_axes.length > 0);
    const summaryChips = [];
    if (isDeepSearch) {
      summaryChips.push(durationSec ? `NeoDeepSearch (${durationSec} s)` : "NeoDeepSearch");
      const axesCount = (m.research_axes && m.research_axes.length) || planSteps.length || 5;
      summaryChips.push(`${axesCount} axes explorés`);
      if (Array.isArray(m.sources) && m.sources.length > 0) {
        summaryChips.push(`${m.sources.length} sources lues`);
      }
    } else {
      if (isMono) {
        summaryChips.push(durationSec ? `Mono-Agent (${durationSec} s)` : "Exécution mono-agent");
      } else if (isMulti) {
        summaryChips.push(durationSec ? `Réflexion approfondie (${durationSec} s)` : "Réflexion approfondie");
      } else if (durationSec) {
        summaryChips.push(`Exécution (${durationSec} s)`);
      } else {
        summaryChips.push("Trace d'exécution");
      }
      if (m.agent && m.agent !== "Runtime Local" && m.agent !== "researcher") {
        summaryChips.push(m.agent);
      }
      if (toolsUsed.length > 0) {
        summaryChips.push(`${toolsUsed.length} action${toolsUsed.length > 1 ? "s" : ""}`);
      } else if (planSteps.length > 0) {
        summaryChips.push(`${planSteps.length} étape${planSteps.length > 1 ? "s" : ""}`);
      }
    }

    // Nettoyer et structurer les événements de la trace terminée (sans doublons de délégation ni jargon brut)
    const renderedRows = [];
    let currentSubAgent = "";
    if (isDeepSearch && Array.isArray(m.research_axes) && m.research_axes.length > 0) {
      m.research_axes.forEach((ax) => {
        renderedRows.push({
          isDelegation: false,
          label: ax.title || ax.query || "",
          pill: ax.pill || "Recherche parallèle",
          duration: "",
          subAgent: "",
        });
      });
    }
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
      <details class="activity-flow-box" ${isDeepSearch ? "open" : ""}>
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

    const subheaderTitle = document.getElementById("subheader-task-title");
    const subheaderDesc = document.getElementById("subheader-task-desc");
    if (subheaderTitle) {
      subheaderTitle.textContent = (conv && conv.title && conv.title !== "Nouvelle tâche") ? conv.title : "Nouvelle tâche";
    }
    if (subheaderDesc) {
      subheaderDesc.textContent = msgs.length > 0 ? "En cours de session" : "Prêt à être configurée";
    }

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
                  .map((a) => renderAttachmentBadgeHtml(a, false))
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
        if (m.execution_mode === "chat") {
          badges.push(`<span class="meta-chip token-eco-chip">${ICONS.chatMode} Chat direct</span>`);
        } else if (m.execution_mode === "multi") {
          badges.push(`<span class="meta-chip accent">${ICONS.brain} Multi-Agent</span>`);
        } else if (m.execution_mode === "mono") {
          badges.push(`<span class="meta-chip secondary">${ICONS.monoAgent} Mono-Agent</span>`);
        }
        if (m.model) badges.push(`<span class="meta-chip">${esc(m.model)}</span>`);
        if (m.skill) badges.push(`<span class="meta-chip accent">/${esc(m.skill)}</span>`);
        if (m.agent && m.agent !== "Runtime Local" && m.agent !== "Sans agent (Chat direct)") badges.push(`<span class="meta-chip">${esc(m.agent)}</span>`);
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
              ${m.skill === "image" || /^!\[[^\]]*\]\([^)]+\)\s*$/.test(String(m.content || "").trim()) ? "" : `<button class="msg-action-btn" data-copy-msg="${idx}">Copier</button>`}
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
    const imgTokens = [];
    out = out.replace(/!\[([^\]]*)\]\(([^)\s]+)\)/g, function (_, altTxt, imgUrl) {
      const tok = `@@INLINEIMG${imgTokens.length}@@`;
      const pathMatch = String(imgUrl).match(/[?&]path=([^&]+)/);
      const docPath = pathMatch ? decodeURIComponent(pathMatch[1]) : "";
      const previewAttr = docPath ? ` data-open-doc-preview="image" data-doc-path="${esc(docPath)}" title="Cliquer pour agrandir"` : "";
      const dlHref = imgUrl.includes("?") ? `${imgUrl}&amp;download=1` : `${imgUrl}?download=1`;
      imgTokens.push(
        `<div class="nh-chat-generated-img-wrap">` +
          `<div class="nh-chat-img-card">` +
            `<img src="${imgUrl}" alt="${altTxt}" class="nh-chat-generated-img"${previewAttr} loading="lazy" />` +
            `<a href="${dlHref}" download class="nh-chat-img-dl-btn" title="Télécharger l'image HD">${ICONS.download} <span>Télécharger</span></a>` +
          `</div>` +
        `</div>`
      );
      return tok;
    });
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

    if (imgTokens.length) {
      out = out.replace(/@@INLINEIMG(\d+)@@/g, function (_, idxStr) {
        return imgTokens[Number(idxStr)] || "";
      });
    }
    if (inlineMathTokens && inlineMathTokens.length) {
      out = out.replace(/@@INLINEMATH(\d+)@@/g, function (_, idxStr) {
        const idx = Number(idxStr);
        return inlineMathTokens[idx] || "";
      });
    }
    return out;
  }

function sanitizeRawLatexForChat(input) {
    const figs = [];
    const out = String(input)
      .split(/(```[\s\S]*?```)/g)
      .map((seg, i) => {
        if (i % 2 === 1) return seg;
        return seg
          .replace(
            /(?:\\begin\{center\}\s*)?\\begin\{tikzpicture\}[\s\S]*?(?:\\end\{tikzpicture\}(?:\s*\\end\{center\})?|$)/g,
            (m) => {
              figs.push(m.replace(/^\\begin\{center\}\s*/, "").replace(/\s*\\end\{center\}\s*$/, ""));
              return `\n\n@@TIKZ_${figs.length - 1}@@\n\n`;
            }
          )
          .replace(/\\(?:begin|end)\{(?:center|document|flushleft|flushright)\}/g, "")
          .replace(/\\exo\{[^}]*\}\{([^}]*)\}/g, "\n\n## $1\n\n")
          .replace(/\\partie\{([^}]*)\}/g, "\n\n### $1\n\n")
          .replace(/\\(?:section|subsection)\*?\{([^}]*)\}/g, "\n\n## $1\n\n")
          .replace(/\\textbf\{([^}]*)\}/g, "**$1**")
          .replace(/\\textit\{([^}]*)\}/g, "*$1*")
          .replace(/\\(?:begin|end)\{(?:enumerate|itemize)\}(?:\[[^\]]*\])?/g, "\n")
          .replace(/^\s*\\item\s+/gm, "- ")
          .replace(/\\needspace\{[^}]*\}/g, "")
          .replace(/\\(?:vspace|hspace)\*?\{[^}]*\}/g, "")
          .replace(/\\(?:newpage|clearpage|noindent|medskip|bigskip|smallskip)\b/g, "");
      })
      .join("");
    return out.replace(/@@TIKZ_(\d+)@@/g, (_, k) => "```tikz\n" + figs[Number(k)] + "\n```");
  }

  // =====================================================================
  //  MOTEUR UNIFIÉ DES REPRÉSENTATIONS MATHÉMATIQUES DANS LE CHAT
  //  1. Tableaux (signes multi-facteurs, variations, convexité combinés)
  //  2. Droites numériques & intervalles (crochets français normalisés)
  //  3. Arbres pondérés (2, 3, N branches + événements complémentaires)
  //  4. Courbes de fonctions, repères & graphes (TikZ / pgfplots / boucles)
  // =====================================================================
  let __vtCounter = 0;
  let __tkUid = 0;

  function vtMath(s) {
    let t = String(s == null ? "" : s).replace(/\$/g, "").trim();
    if (!t) return "";
    if (/^[A-Za-zÀ-ÿ'’ ]{3,}$/.test(t) && !/^[+-]?\s*(oo|inf)$/i.test(t) && !/^(ln|exp|sin|cos|tan|sqrt)\b/i.test(t)) {
      return `<i>${esc(t)}</i>`;
    }
    t = t.replace(/−/g, "-");
    t = t.replace(/([+-]?)\s*(?:\\infty|oo|inf|∞)/gi, (_, sg) => (sg || "") + "\\infty");
    t = t.replace(/^(-?)(\d+)\s*\/\s*(\d+)$/, (_, sg, a, b) => `${sg}\\frac{${a}}{${b}}`);
    t = t.replace(/sqrt\(([^()]*)\)/g, "\\sqrt{$1}").replace(/\bpi\b/g, "\\pi");
    t = t.replace(/\\parallel|\\mid/g, "");
    return renderMathExpression(t, false);
  }

  function vtLabel(s) {
    const t = String(s == null ? "" : s).replace(/\$/g, "").trim();
    if (/^x$/i.test(t)) return renderMathExpression("x", false);
    if (/^[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9_ '’-]*$/.test(t) && /[A-Za-zÀ-ÿ]{3,}/.test(t)) {
      const txt = t
        .replace(/_/g, " ")
        .replace(/\bnum\b/gi, "numérateur")
        .replace(/\bden\b/gi, "dénominateur");
      return `<span style="font-style:italic;font-size:13px;line-height:1.25;display:inline-block;">${esc(txt)}</span>`;
    }
    return vtMath(t);
  }

  function vtNum(s) {
    try {
      let t = String(s == null ? "" : s).replace(/\$/g, "").replace(/\s+/g, "");
      if (!t) return null;
      t = t.replace(/−/g, "-").replace(/,/g, ".");
      if (/^[+-]?(?:\\infty|oo|∞|inf)$/i.test(t)) {
        return t.startsWith("-") ? -1e99 : 1e99;
      }
      t = t.replace(/\\d?frac\{([^{}]*)\}\{([^{}]*)\}/g, "(($1)/($2))");
      t = t.replace(/\\sqrt\{([^{}]*)\}/g, "Math.sqrt($1)");
      t = t.replace(/sqrt\(([^()]*)\)/g, "Math.sqrt($1)");
      t = t.replace(/\\ln\b|\bln\b/g, "Math.log");
      t = t.replace(/\\exp\b|\bexp\b/g, "Math.exp");
      t = t.replace(/\\pi\b|\bpi\b/g, "Math.PI");
      t = t.replace(/\be\b/g, "Math.E");
      t = t.replace(/\^\{([^{}]*)\}/g, "**($1)").replace(/\^(-?[\d.]+)/g, "**($1)");
      const stripped = t.replace(/Math\.(sqrt|log|exp|PI|E)/g, "");
      if (!/^[\d+\-*/().e*]*$/.test(stripped) || !t) return null;
      const v = Function('"use strict";return (' + t + ");")();
      return typeof v === "number" && !isNaN(v) ? v : null;
    } catch (_) {
      return null;
    }
  }

  // Normalise une ligne de signes à 2n-3 jetons : [signe_0, sep_1, signe_1, sep_2, ..., signe_{n-2}]
  function vtNormSigns(toks, n, xVals) {
    const need = Math.max(0, 2 * n - 3);
    if (need === 0) return [];
    const isS = (t) => t === "+" || t === "-" || t === "?";
    const out = [];
    let expectSign = true;
    toks.forEach((t) => {
      if (isS(t)) {
        if (!expectSign) out.push("|");
        out.push(t);
        expectSign = false;
      } else {
        if (expectSign) out.push("");
        out.push(t === "//" ? "||" : t);
        expectSign = true;
      }
    });
    // Si f''(x) est donné avec "- 0 +" (3 jetons) alors que x a plus de 3 valeurs (ex: -oo, -1, 0, 1, +oo)
    if (out.length === 3 && need > 3 && isS(out[0]) && (out[1] === "0" || out[1] === "||") && isS(out[2])) {
      let midIdx = Math.floor((n - 1) / 2);
      if (Array.isArray(xVals)) {
        const zeroIdx = xVals.findIndex((xv, idx) => idx > 0 && idx < n - 1 && String(xv).replace(/\$/g, "").trim() === "0");
        if (zeroIdx > 0) midIdx = zeroIdx;
      }
      const expanded = [];
      for (let k = 0; k < n - 1; k++) {
        expanded.push(k < midIdx ? out[0] : out[2]);
        if (k < n - 2) expanded.push(k + 1 === midIdx ? out[1] : "|");
      }
      return expanded;
    }
    while (out.length < need) {
      if (out.length % 2 === 1) out.push("|");
      else out.push([...out].reverse().find(isS) || "+");
    }
    return out.slice(0, need);
  }

function parseVtSpec(text) {
    const lines = String(text).split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
    const spec = { x: [], signRows: [], varRow: null, convex: false, convexLabel: "convexité" };
    const ARROW_RE = /\\?(?:nearrow|searrow|nwarrow|swarrow|uparrow|downarrow)|[↗↘↙↖↑↓]/g;
    for (const ln of lines) {
      const m = ln.match(/^([^:]+):\s*(.*)$/);
      if (!m) continue;
      const label = m[1].trim();
      const body = m[2].trim().replace(/−/g, "-");
      if (spec.x.length === 0 && /^\$?x\$?$/i.test(label)) {
        spec.x = (body.indexOf("|") >= 0 ? body.split("|") : body.split(/\s+/)).map((s) => s.trim()).filter(Boolean);
        continue;
      }
      if (/convex|concav/i.test(label) || /convexe|concave|inflexion/i.test(body)) {
        spec.convex = true;
        spec.convexLabel = label;
        continue;
      }
      const onlySignChars = /^[\s+\-0|/?]+$/.test(body) && /[+\-0|/?]/.test(body);
      const primeLabel = /['′"″]|signe/i.test(label);
      if (primeLabel || onlySignChars) {
        const toks = (body.match(/\|\||\/\/|\||[+\-]|0|\?/g) || []).map((t) => (t === "//" ? "||" : t));
        spec.signRows.push({ label, toks, isSecondDeriv: /(''|′′|″|"|seconde)/i.test(label) });
        if (/(''|′′|″|")/.test(label)) spec.convex = true;
      } else {
        const cleanBody = body.replace(ARROW_RE, " ").replace(/\|\s*\|/g, "|");
        const rawParts = cleanBody.split("|").map((s) => s.trim()).filter((v, _, arr) => arr.length <= 2 || v !== "");
        const vals = rawParts.map((p) => {
          const parts = p.split("//").map((s) => s.trim());
          return parts.length > 1 ? [parts[0], parts[1]] : [parts[0], parts[0]];
        });
        spec.varRow = { label, vals };
      }
    }
    const n = spec.x.length;
    spec.signRows.forEach((r) => {
      r.toks = vtNormSigns(r.toks, n, spec.x);
    });
    if (spec.varRow && n >= 2) {
      // Auto-réparation 1 : si f(x) a moins de n colonnes parce que '//' a été utilisé comme séparateur au lieu de '|'
      const hasForbInSigns = (k) => spec.signRows.some((r) => !r.isSecondDeriv && r.toks[2 * k - 1] === "||");
      while (spec.varRow.vals.length < n) {
        const splitIdx = spec.varRow.vals.findIndex((v, idx) => v[0] !== v[1] && (idx === 0 || idx >= n - 1 || !hasForbInSigns(idx)));
        if (splitIdx >= 0) {
          const [a, b] = spec.varRow.vals[splitIdx];
          spec.varRow.vals.splice(splitIdx, 1, [a, a], [b, b]);
        } else {
          break;
        }
      }
      while (spec.varRow.vals.length < n) spec.varRow.vals.push(["", ""]);
      spec.varRow.vals = spec.varRow.vals.slice(0, n);

      // Auto-réparation 2 : si une colonne intérieure k a 'a // b' mais que f'(x) a un '0' (et non '||'), garder la valeur unique
      for (let k = 1; k <= n - 2; k++) {
        if (spec.varRow.vals[k][0] !== spec.varRow.vals[k][1] && spec.signRows.length > 0 && !hasForbInSigns(k)) {
          spec.varRow.vals[k] = [spec.varRow.vals[k][0], spec.varRow.vals[k][0]];
        }
      }

      // Auto-réparation 3 : si les n valeurs numériques de f(x) sont toutes connues et contredisent un signe de f'(x), réaligner f'(x)
      const dsrc = spec.signRows.slice().reverse().find((r) => /['′]/.test(r.label) && !r.isSecondDeriv);
      if (dsrc && dsrc.toks.length === 2 * n - 3) {
        const numVals = spec.varRow.vals.map((v) => (v[0] === v[1] ? vtNum(v[0]) : null));
        if (numVals.every((v) => v !== null)) {
          for (let k = 0; k < n - 1; k++) {
            if (numVals[k] < numVals[k + 1] && dsrc.toks[2 * k] === "-") dsrc.toks[2 * k] = "+";
            else if (numVals[k] > numVals[k + 1] && dsrc.toks[2 * k] === "+") dsrc.toks[2 * k] = "-";
          }
        }
      }
    }
    return n >= 2 ? spec : null;
  }

  function tabularToVtSpec(rows) {
    const cells = rows.map((r) => r.split("&").map((c) => c.replace(/\$/g, "").trim()));
    const strip = (s) => String(s || "").replace(/\s+/g, "");
    const xi = cells.findIndex((r) => strip(r[0]).toLowerCase() === "x");
    if (xi < 0) return null;
    const cols = [];
    cells[xi].forEach((c, j) => {
      if (j > 0 && c) cols.push(j);
    });
    const n = cols.length;
    if (n < 2) return null;
    const ARROW = /searrow|swarrow|nearrow|nwarrow|downarrow|uparrow|[↗↘↙↖↑↓]/;
    const spec = { x: cols.map((j) => cells[xi][j]), signRows: [], varRow: null, convex: false, convexLabel: "convexité" };
    const vals = cols.map(() => "");
    let varLabel = "";
    let hasVal = false;
    cells.forEach((r, i) => {
      if (i === xi) return;
      const lbl = r[0] || "";
      if (/convex|concav/i.test(lbl)) {
        spec.convex = true;
        return;
      }
      if (/'|′|prime|signe/i.test(lbl)) {
        const toks = [];
        for (let k = 1; k < n; k++) {
          const cand = r.slice(cols[k - 1] + 1, cols[k]).find((c) => c) || "";
          toks.push(cand.replace("−", "-") || "+");
          if (k < n - 1) {
            const pc = r[cols[k]] || "";
            toks.push(/^0$/.test(pc) ? "0" : /parallel|\|\|/.test(pc) ? "||" : "|");
          }
        }
        const isD2 = /(''|′′|″|")/.test(lbl);
        if (isD2) spec.convex = true;
        spec.signRows.push({ label: lbl, toks: vtNormSigns(toks, n, spec.x), isSecondDeriv: isD2 });
        return;
      }
      if (!varLabel && lbl) varLabel = lbl;
      cols.forEach((c, k) => {
        const cell = r[c];
        if (cell && !ARROW.test(cell) && !vals[k]) {
          vals[k] = cell;
          hasVal = true;
        }
      });
    });
    if (hasVal) spec.varRow = { label: varLabel || "f(x)", vals: vals.map((v) => [v, v]) };
    return spec.signRows.length || spec.varRow ? spec : null;
  }

function splitMdPipeRow(line) {
    const s = String(line || "").trim().replace(/^\||\|$/g, "");
    const cells = [];
    let cur = "", inMath = false;
    for (let i = 0; i < s.length; i++) {
      const ch = s[i];
      if (ch === "$" && s[i - 1] !== "\\") inMath = !inMath;
      if (ch === "|" && !inMath && s[i - 1] !== "\\") {
        cells.push(cur.trim());
        cur = "";
      } else {
        cur += ch;
      }
    }
    cells.push(cur.trim());
    return cells;
  }

  function renderMdCellRich(cellText) {
    const raw = String(cellText == null ? "" : cellText).trim();
    if (!raw) return "&nbsp;";
    const mathTokens = [];
    let work = raw.replace(/\\\(([^\n]+?)\\\)/g, (_, expr) => {
      const tok = `@@CELLMATH${mathTokens.length}@@`;
      mathTokens.push(`<span class="math-inline">${renderMathExpression(expr, false)}</span>`);
      return tok;
    });
    work = work.replace(/\$([^$\n]+)\$/g, (_, expr) => {
      const tok = `@@CELLMATH${mathTokens.length}@@`;
      mathTokens.push(`<span class="math-inline">${renderMathExpression(expr, false)}</span>`);
      return tok;
    });
    let out = esc(work)
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>")
      .replace(/`([^`]+)`/g, "<code>$1</code>");
    out = out.replace(/@@CELLMATH(\d+)@@/g, (_, idx) => mathTokens[Number(idx)] || "");
    return out;
  }

  function mdPipeTableToHtml(block) {
    const rawLines = block
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter((l) => l.startsWith("|"));
    if (rawLines.length < 2) return null;

    const parsedLines = rawLines.map(splitMdPipeRow);
    const isSepRow = (r) => r.length > 0 && r.every((c) => /^:?-{2,}:?$/.test(c) || c === "");
    const sepRow = parsedLines.find(isSepRow);
    const aligns = sepRow
      ? sepRow.map((c) => (c.startsWith(":") && c.endsWith(":") ? "center" : c.endsWith(":") ? "right" : "left"))
      : [];

    const dataRows = parsedLines.filter((r) => !isSepRow(r));
    if (dataRows.length < 2) return null;

    // 1. Détection : est-ce un tableau de variations / signes / convexité ?
    const strip = (s) => String(s || "").replace(/\$/g, "").replace(/\s+/g, "");
    const firstCell = strip(dataRows[0][0]).toLowerCase();
    const ARROW = /searrow|swarrow|nearrow|nwarrow|uparrow|downarrow|[↗↘↙↖↑↓]/;
    const hasSignOrVar =
      firstCell === "x" &&
      dataRows.slice(1).some((r) => {
        const lbl = strip(r[0]);
        const body = r.slice(1).map((c) => strip(c));
        return (
          /['′"″]|prime|signe|convex|concav|variation/i.test(lbl) ||
          body.some((c) => ARROW.test(c) || /^(?:[+-]?(?:\\infty|oo|∞)|\|\|)$/.test(c)) ||
          (body.filter(Boolean).length > 0 && body.filter(Boolean).every((c) => /^(\+|-|0|\|\||\?|\|)$/.test(c)))
        );
      });

    if (hasSignOrVar) {
      const xs = dataRows[0].slice(1).map((c) => c.replace(/\$/g, "").trim()).filter((c) => c !== "");
      const n = xs.length;
      if (n >= 2) {
        const spec = { x: xs, signRows: [], varRow: null, convex: false, convexLabel: "convexité" };
        dataRows.slice(1).forEach((r) => {
          const label = (r[0] || "").replace(/\$/g, "").trim();
          const body = r.slice(1).map((c) => c.replace(/\$/g, "").trim());
          if (!label && body.some((c) => ARROW.test(c))) return;
          if (/convex|concav/i.test(label)) {
            spec.convex = true;
            return;
          }
          const nz = body.filter((c) => c !== "").map((c) => (c === "−" ? "-" : c === "//" ? "||" : c));
          if (/'|′|prime|signe/i.test(label) || (nz.length > 0 && nz.every((c) => /^(\+|-|0|\|\||\?|\|)$/.test(c)))) {
            const isD2 = /(''|′′|″|")/.test(label);
            if (isD2) spec.convex = true;
            spec.signRows.push({ label, toks: vtNormSigns(nz, n, xs), isSecondDeriv: isD2 });
          } else if (!spec.varRow && label) {
            const cleanCells = body.filter((c) => !ARROW.test(c));
            const cells = cleanCells.length >= n ? cleanCells.slice(0, n) : cleanCells.concat(new Array(n - cleanCells.length).fill(""));
            spec.varRow = { label, vals: cells.map((c) => [c, c]) };
          }
        });
        const vtRendered = renderVtSpec(spec);
        if (vtRendered) return vtRendered;
      }
    }

    // 2. Sinon : rendu de tableau de données / statistiques / valeurs / loi de probabilité
    const colCount = Math.max(...dataRows.map((r) => r.length));
    const isHorizontalSeries =
      dataRows.length <= 4 &&
      colCount >= 3 &&
      dataRows.every((r) => /[A-Za-zÀ-ÿ$]/.test(r[0] || "")) &&
      dataRows[0].slice(1).every((c) => /^[-+]?[\d.,\s$]+$/.test(c));

    const rowsHtml = dataRows
      .map((r, rIdx) => {
        const cellsHtml = [];
        for (let cIdx = 0; cIdx < colCount; cIdx++) {
          const rawCell = r[cIdx] !== undefined ? r[cIdx] : "";
          const isHeaderCell = (isHorizontalSeries && cIdx === 0) || (!isHorizontalSeries && rIdx === 0);
          const tag = isHeaderCell ? "th" : "td";
          const align = isHeaderCell && cIdx === 0 ? "left" : aligns[cIdx] || "center";
          const hideCls = !isHeaderCell ? ' class="nh-student-hide"' : "";
          cellsHtml.push(
            `<${tag} style="text-align:${align};"><span${hideCls}>${renderMdCellRich(rawCell)}</span></${tag}>`
          );
        }
        return `<tr>${cellsHtml.join("")}</tr>`;
      })
      .join("");

    const tableHtml =
      `<div class="nh-math-table-card nh-data-table-wrap">` +
      `<table class="nh-md-data-table"><tbody>${rowsHtml}</tbody></table>` +
      `</div>`;
    return nhWrapMathFigure(tableHtml, { hasStudentMode: true });
  }

// ---------- Barre d'outils flottante 100 % Vectorielle (Mode Élève + Copie PNG HD + Oracle) ----------
  const NH_SVG_STUDENT = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c0 2 2 3 6 3s6-1 6-3v-5"/></svg>';
  const NH_SVG_PROF = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>';
  const NH_SVG_CAM = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>';

  function nhWrapMathFigure(innerHtml, opts = {}) {
    const hasStudent = Boolean(opts.hasStudentMode);
    const oracle = opts.oracle || null;
    const cleanLabel = oracle ? String(oracle.label || "").replace(/^[✓⚠🎯]\s*/, "") : "";
    const oracleIcon = oracle ? (oracle.ok ? ICONS.check : ICONS.alert) : "";
    const oracleHtml = oracle
      ? `<span class="nh-fig-oracle ${oracle.ok ? "ok" : "warn"}" title="${esc(oracle.detail || cleanLabel)}">${oracleIcon} <span>${esc(cleanLabel)}</span></span>`
      : "";
    const studentBtn = hasStudent
      ? `<button type="button" class="nh-fig-tool-btn nh-btn-student-mode" title="Basculer entre la version Professeur (corrigée) et la version Élève (à compléter)">${NH_SVG_STUDENT} <span>Mode Élève</span></button>`
      : "";
    const pngBtn = `<button type="button" class="nh-fig-tool-btn nh-btn-copy-png" title="Copier en image PNG Haute Définition (pour Word, PowerPoint, Pronote…)">${NH_SVG_CAM} <span>Copier PNG</span></button>`;

    return (
      `<div class="nh-math-fig">` +
      `<div class="nh-fig-Container">` +
      `<div class="nh-fig-toolbar">${oracleHtml}${studentBtn}${pngBtn}</div>` +
      `<div class="nh-fig-export-target">${innerHtml}</div>` +
      `</div></div>`
    );
  }

async function nhCopyElementAsPng(targetEl, btnEl) {
    if (!targetEl) return;
    btnEl.blur();
    const origHtml = btnEl.innerHTML;
    try {
      let boxEl = targetEl.querySelector(".nh-math-table-card, .nh-curve-stage") || targetEl.firstElementChild || targetEl;
      if (boxEl.classList && boxEl.classList.contains("nh-math-figure-card") && boxEl.firstElementChild) {
        boxEl = boxEl.firstElementChild;
      }
      const rect = boxEl.getBoundingClientRect();
      const wRaw = Math.max(120, Math.ceil(rect.width));
      const hRaw = Math.max(60, Math.ceil(rect.height));
      const W = wRaw + 32;
      const H = hRaw + 32;

      const clone = boxEl.cloneNode(true);
      const styleProps = [
        "position", "left", "right", "top", "bottom", "width", "height", "minWidth", "maxWidth",
        "display", "alignItems", "justifyContent", "padding", "margin", "border", "borderTop",
        "borderBottom", "borderLeft", "borderRight", "borderRadius", "backgroundColor",
        "color", "fontFamily", "fontSize", "fontWeight", "fontStyle", "lineHeight", "textAlign",
        "whiteSpace", "transform", "opacity", "boxSizing",
      ];
      const srcNodes = [boxEl, ...boxEl.querySelectorAll("*")];
      const dstNodes = [clone, ...clone.querySelectorAll("*")];
      const toRemove = [];
      for (let i = 0; i < srcNodes.length; i++) {
        const sNode = srcNodes[i], dNode = dstNodes[i];
        if (!dNode || !sNode || !(sNode instanceof Element)) continue;
        if (sNode.classList && (sNode.classList.contains("nh-curve-hud") || sNode.classList.contains("katex-mathml") || sNode.classList.contains("vlist-s"))) {
          toRemove.push(dNode);
          continue;
        }
        // Ne pas écraser la géométrie interne de KaTeX (exposants, fractions, racines)
        if (sNode.closest(".katex") && !sNode.classList.contains("katex")) {
          continue;
        }
        const cs = window.getComputedStyle(sNode);
        if (cs.display === "none" || cs.visibility === "hidden" || cs.opacity === "0") {
          toRemove.push(dNode);
          continue;
        }
        if (dNode instanceof HTMLElement && !sNode.classList.contains("katex")) {
          styleProps.forEach((p) => {
            const val = cs[p];
            if (val) dNode.style[p] = val;
          });
        }
      }
      toRemove.forEach((n) => n.remove());
      clone.style.margin = "0";

      const isDark = document.documentElement.getAttribute("data-theme") === "dark";
      const bgExport = isDark ? "#161A22" : "#FFFFFF";
      const fgExport = isDark ? "#F3F4F6" : "#141518";
      let xhtml = new XMLSerializer().serializeToString(clone);
      xhtml = xhtml.replace(/currentColor/g, fgExport);

      const katexCss = `
        .katex { font: normal 1.04em Georgia, "Times New Roman", serif; line-height: 1.2; white-space: nowrap; }
        .katex-mathml, .vlist-s { display: none !important; }
        .katex .base { position: relative; display: inline-block; white-space: nowrap; }
        .katex .strut { display: inline-block; }
        .katex .vlist-t { display: inline-table; table-layout: fixed; border-collapse: collapse; }
        .katex .vlist-r { display: table-row; }
        .katex .vlist { display: table-cell; vertical-align: bottom; position: relative; }
        .katex .vlist > span { display: block; height: 0; position: relative; }
        .katex .vlist > span > span { display: inline-block; }
        .katex .pstrut { display: inline-block; overflow: hidden; width: 0; }
        .katex .msupsub { text-align: left; }
        .katex .mfrac > span > span { text-align: center; }
        .katex .mfrac .frac-line { display: inline-block; width: 100%; border-bottom: 1px solid ${fgExport}; }
        .katex .mspace { display: inline-block; }
        .katex .mathnormal, .katex .mathit { font-style: italic; }
        .katex .sizing.reset-size6.size3, .katex .fontsize-ensurer.reset-size6.size3 { font-size: 0.7em; }
        .katex svg { display: block; position: absolute; width: 100%; height: inherit; fill: ${fgExport}; stroke: ${fgExport}; }
      `;

      const svgStr =
        `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">` +
        `<style>${katexCss}</style>` +
        `<rect width="100%" height="100%" rx="10" fill="${bgExport}"/>` +
        `<foreignObject x="16" y="16" width="${wRaw}" height="${hRaw}">` +
        `<div xmlns="http://www.w3.org/1999/xhtml" style="color:${fgExport};width:${wRaw}px;height:${hRaw}px;font-family:Georgia,serif;">${xhtml}</div>` +
        `</foreignObject></svg>`;

      const dataUrl = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svgStr);
      const img = new Image();
      img.crossOrigin = "anonymous";
      await new Promise((res, rej) => {
        img.onload = res;
        img.onerror = rej;
        img.src = dataUrl;
      });
      const scale = 2;
      const canvas = document.createElement("canvas");
      canvas.width = W * scale;
      canvas.height = H * scale;
      const ctx2d = canvas.getContext("2d");
      ctx2d.scale(scale, scale);
      ctx2d.drawImage(img, 0, 0);

      const pngBlob = await new Promise((res) => canvas.toBlob(res, "image/png"));
      if (!pngBlob) throw new Error("Blob vide");
      let copiedOk = false;
      if (navigator.clipboard && window.ClipboardItem) {
        try {
          await navigator.clipboard.write([new ClipboardItem({ "image/png": pngBlob })]);
          copiedOk = true;
        } catch (_) {}
      }
      if (copiedOk) {
        btnEl.innerHTML = `${ICONS.check} <span>PNG copié !</span>`;
      } else {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(pngBlob);
        a.download = "figure_neoharness.png";
        a.click();
        btnEl.innerHTML = `${ICONS.check} <span>PNG téléchargé !</span>`;
      }
      btnEl.classList.add("copied");
    } catch (_) {
      btnEl.innerHTML = `${ICONS.alert} <span>Erreur export</span>`;
    }
    setTimeout(() => {
      btnEl.innerHTML = origHtml;
      btnEl.classList.remove("copied");
    }, 1800);
  }

  // Moteur unifié : affiche x + lignes de signes + variations f(x) + convexité dans un seul tableau
  function renderVtSpec(spec) {
    const n = spec.x.length;
    if (n < 2) return null;
    const sr = spec.signRows || [];
    const vr = spec.varRow;
    const vals = vr ? vr.vals : null;
    const s2 = sr.find((r) => r.isSecondDeriv) || (spec.convex && !vr ? sr[sr.length - 1] : null);
    const hasConvexRow = Boolean(spec.convex && s2 && s2.toks.length === 2 * n - 3);

    const allLabels = sr.map((r) => String(r.label || "")).concat(vr ? [String(vr.label || "")] : []).concat(hasConvexRow ? [spec.convexLabel || "convexité"] : []);
    const maxLen = Math.max(4, ...allLabels.map((l) => l.replace(/[$\\{}]/g, "").length));
    const LABW = Math.max(112, Math.min(205, 28 + 7 * maxLen));
    const XH = 42;
    const rowHeights = sr.map((r) => (String(r.label || "").length > 12 ? 46 : 40));
    const VH = 114;
    const CH = 88;
    const YS = { t: 24, m: 57, b: 90 };

    const preVarSigns = [];
    const postVarSigns = [];
    sr.forEach((r, idx) => {
      if (vr && hasConvexRow && r === s2) postVarSigns.push({ r, h: rowHeights[idx] });
      else preVarSigns.push({ r, h: rowHeights[idx] });
    });

    const preVarHeight = preVarSigns.reduce((acc, it) => acc + it.h, 0);
    const varTop = XH + preVarHeight;
    const postVarTop = varTop + (vr ? VH : 0);
    const postVarHeight = postVarSigns.reduce((acc, it) => acc + it.h, 0);
    const convTop = postVarTop + postVarHeight;
    const total = convTop + (hasConvexRow ? CH : 0);

    const pct = (k) => 7 + (86 * k) / (n - 1);
    const mid = (k) => (pct(k) + pct(k + 1)) / 2;

    // Sens des flèches + Oracle de cohérence mathématique (signes de f' vs valeurs de f)
    let dirs = null;
    let oracle = { ok: true, label: "✓ Cohérence vérifiée", detail: "Table vérifiée par l'oracle NeoHarness." };
    if (vr) {
      const dsrc =
        preVarSigns.map((x) => x.r).reverse().find((r) => /['′]/.test(r.label) && !r.isSecondDeriv) ||
        preVarSigns.map((x) => x.r).reverse().find((r) => !r.isSecondDeriv);
      const signDirs =
        dsrc && dsrc.toks.length === 2 * n - 3
          ? dsrc.toks.filter((_, i) => i % 2 === 0).map((t) => (t === "+" ? "u" : t === "-" ? "d" : null))
          : null;
      const valDirs = [];
      if (vals) {
        for (let k = 0; k < n - 1; k++) {
          const a = vtNum(vals[k][1]);
          const b = vtNum(vals[k + 1][0]);
          valDirs.push(a === null || b === null || a === b ? null : b > a ? "u" : "d");
        }
      }
      if (signDirs && signDirs.every(Boolean)) {
        dirs = signDirs;
        for (let k = 0; k < n - 1; k++) {
          if (valDirs[k] && valDirs[k] !== signDirs[k]) {
            oracle = {
              ok: false,
              label: "⚠ Incohérence f' / f(x)",
              detail: `Intervalle ${k + 1} : le signe de la dérivée (${signDirs[k] === "u" ? "+" : "-"}) contredit les valeurs aux bornes (${vals[k][1]} → ${vals[k + 1][0]}).`,
            };
            break;
          }
        }
      } else if (valDirs.length === n - 1 && valDirs.every(Boolean)) {
        dirs = valDirs;
      }
    }

    const lev = [];
    if (vr && vals) {
      for (let k = 0; k < n; k++) {
        const dbl = vals[k][0] !== vals[k][1];
        if (!dirs) {
          lev.push({ L: "m", R: "m" });
          continue;
        }
        const prev = k > 0 ? dirs[k - 1] : null;
        const next = k < n - 1 ? dirs[k] : null;
        let single;
        if (k === 0) single = next === "u" ? "b" : "t";
        else if (k === n - 1) single = prev === "u" ? "t" : "b";
        else if (prev === "d" && next === "u") single = "b";
        else if (prev === "u" && next === "d") single = "t";
        else single = "m";
        if (dbl && k > 0 && k < n - 1) {
          lev.push({ L: prev === "u" ? "t" : "b", R: next === "u" ? "b" : "t" });
        } else {
          lev.push({ L: single, R: single });
        }
      }
    }

    const C = "currentColor";
    const BG = "var(--bg-elevated,#ffffff)";
    const HDR_BG = "var(--bg-secondary,#f4f5f7)";
    const at = (l, t, html, tx, extraCls) =>
      `<div class="${extraCls || ""}" style="position:absolute;left:${l}%;top:${t}px;transform:translate(${tx || "-50%"},-50%);white-space:nowrap;">${html}</div>`;
const hline = (y) =>
      `<div style="position:absolute;left:0;right:0;top:${y}px;height:1px;background:${C};opacity:0.85;z-index:2;"></div>`;
    const vline = (l, y1, y2, off, dashed) =>
      `<div style="position:absolute;left:calc(${l}% + ${off || 0}px);top:${y1}px;height:${Math.max(0, y2 - y1)}px;width:0;border-left:1px ${dashed ? "dashed" : "solid"} ${C};opacity:${dashed ? "0.35" : "0.65"};"></div>`;
    const lab = (label, top, h) =>
      `<div style="position:absolute;left:0;width:${LABW}px;top:${top}px;height:${h}px;display:flex;align-items:center;justify-content:center;padding:2px 10px;text-align:center;box-sizing:border-box;z-index:1;">${vtLabel(label)}</div>`;

    const outer = [];
    outer.push(`<div style="position:absolute;left:0;top:0;bottom:0;width:${LABW}px;background:${HDR_BG};"></div>`);
    outer.push(`<div style="position:absolute;left:${LABW}px;right:0;top:0;height:${XH}px;background:${HDR_BG};opacity:0.55;"></div>`);
    outer.push(lab("x", 0, XH));

    const plot = [];
    for (let k = 0; k < n; k++) plot.push(at(pct(k), XH / 2, vtMath(spec.x[k])));

    function renderSignGroup(group, startY) {
      let curY = startY;
      group.forEach(({ r, h }) => {
        outer.push(lab(r.label, curY, h));
        const cy = curY + h / 2;
        for (let k = 0; k < n - 1; k++) {
          const sg = r.toks[2 * k];
          if (sg && sg !== "|" && sg !== "||" && sg !== "?") {
            plot.push(at(mid(k), cy, vtMath(sg), "-50%", "nh-student-hide"));
          }
        }
        for (let k = 1; k <= n - 2; k++) {
          const sep = r.toks[2 * k - 1];
          if (sep === "||") {
            plot.push(vline(pct(k), curY, curY + h, -2, false));
            plot.push(vline(pct(k), curY, curY + h, 2, false));
          } else if (sep === "0") {
            plot.push(vline(pct(k), curY, Math.max(curY, cy - 11), 0, true));
            plot.push(vline(pct(k), Math.min(curY + h, cy + 11), curY + h, 0, true));
            plot.push(at(pct(k), cy, `<span style="font-weight:600;line-height:1;display:inline-block;">${vtMath("0")}</span>`));
          } else {
            plot.push(vline(pct(k), curY, curY + h, 0, true));
          }
        }
        curY += h;
        if (curY < total) outer.push(hline(curY));
      });
    }

    renderSignGroup(preVarSigns, XH);

    // Ligne des variations f(x)
    if (vr && vals) {
      outer.push(lab(vr.label || "f(x)", varTop, VH));
      for (let k = 1; k <= n - 2; k++) {
        const lastPre = preVarSigns.length ? preVarSigns[preVarSigns.length - 1].r : null;
        const isForb = vals[k][0] !== vals[k][1] || (lastPre && lastPre.toks[2 * k - 1] === "||");
        if (isForb) {
          plot.push(vline(pct(k), varTop, varTop + VH, -2, false));
          plot.push(vline(pct(k), varTop, varTop + VH, 2, false));
        }
      }
      for (let k = 0; k < n; k++) {
        const dbl = vals[k][0] !== vals[k][1];
        if (dbl && k > 0 && k < n - 1) {
          if (vals[k][0]) plot.push(at(pct(k) - 1.8, varTop + YS[lev[k].L], vtMath(vals[k][0]), "-100%", "nh-student-hide"));
          if (vals[k][1]) plot.push(at(pct(k) + 1.8, varTop + YS[lev[k].R], vtMath(vals[k][1]), "0%", "nh-student-hide"));
        } else if (vals[k][0]) {
          plot.push(at(pct(k), varTop + YS[lev[k].L], `<span style="background:${BG};padding:1px 5px;border-radius:3px;">${vtMath(vals[k][0])}</span>`, "-50%", "nh-student-hide"));
        }
      }
      if (dirs) {
        const id = "vt-arr-" + ++__vtCounter;
        let lines = "";
        for (let k = 0; k < n - 1; k++) {
          const dblA = vals[k][0] !== vals[k][1] && k > 0;
          const dblB = vals[k + 1][0] !== vals[k + 1][1] && k + 1 < n - 1;
          const lenA = String(vals[k][dblA ? 1 : 0] || "").replace(/\\infty/g, "oo").length;
          const lenB = String(vals[k + 1][0] || "").replace(/\\infty/g, "oo").length;
          const padA = dblA ? 8.5 : Math.min(8.5, Math.max(4.5, 2.8 + lenA * 0.65));
          const padB = dblB ? 8.5 : Math.min(8.5, Math.max(4.5, 2.8 + lenB * 0.65));
          const x1 = pct(k) + padA;
          const x2 = pct(k + 1) - padB;
          if (x2 <= x1 + 1) continue;
          let y1 = YS[lev[k].R];
          let y2 = YS[lev[k + 1].L];
          const dy = y2 - y1;
          if (Math.abs(dy) > 24) {
            const s = dy > 0 ? 1 : -1;
            y1 += s * 9;
            y2 -= s * 9;
          }
          lines += `<line x1="${x1}%" y1="${y1}" x2="${x2}%" y2="${y2}" stroke="${C}" stroke-width="1.5" marker-end="url(#${id})"/>`;
        }
        plot.push(
          `<svg class="nh-student-hide" style="position:absolute;left:0;top:${varTop}px;width:100%;height:${VH}px;overflow:visible;pointer-events:none;" aria-hidden="true">` +
            `<defs><marker id="${id}" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L9,4.5 L0,9 z" fill="${C}"/></marker></defs>${lines}</svg>`
        );
      }
      if (varTop + VH < total) outer.push(hline(varTop + VH));
    }

    renderSignGroup(postVarSigns, postVarTop);

    // Ligne de convexité
    if (hasConvexRow && s2) {
      outer.push(lab(spec.convexLabel || "convexité", convTop, CH));
      const cy = convTop + CH / 2;
      const spans = [];
      let curStart = 0;
      for (let k = 0; k < n - 1; k++) {
        const sg = s2.toks[2 * k];
        const nextSg = k < n - 2 ? s2.toks[2 * (k + 1)] : null;
        const sep = k < n - 2 ? s2.toks[2 * k + 1] : null;
        if (k === n - 2 || sep === "0" || sep === "||" || sg !== nextSg) {
          spans.push({ k0: curStart, k1: k + 1, sg, sepAfter: sep });
          curStart = k + 1;
        }
      }
      spans.forEach((spn) => {
        const xm = (pct(spn.k0) + pct(spn.k1)) / 2;
        const convex = spn.sg === "+";
        plot.push(
          `<svg class="nh-student-hide" style="position:absolute;left:${xm}%;top:${cy - 24}px;width:48px;height:26px;transform:translateX(-50%);overflow:visible;" aria-hidden="true">` +
            `<path d="${convex ? "M3,4 Q24,25 45,4" : "M3,23 Q24,2 45,23"}" fill="none" stroke="${C}" stroke-width="1.75" stroke-linecap="round"/></svg>`
        );
        plot.push(at(xm, cy + 14, `<span style="font-style:italic;font-size:12.5px;color:var(--text-secondary);">${convex ? "convexe" : "concave"}</span>`, "-50%", "nh-student-hide"));
      });
      for (let k = 1; k <= n - 2; k++) {
        const t = s2.toks[2 * k - 1];
        if (t === "||") {
          plot.push(vline(pct(k), convTop, convTop + CH, -2, false));
          plot.push(vline(pct(k), convTop, convTop + CH, 2, false));
        } else if (t === "0") {
          const isInflexion = s2.toks[2 * (k - 1)] !== s2.toks[2 * k];
          plot.push(vline(pct(k), convTop, isInflexion ? convTop + CH - 24 : convTop + CH, 0, false));
          if (isInflexion) {
            plot.push(`<div class="nh-student-hide" style="position:absolute;left:${pct(k)}%;top:${cy - 6}px;width:8px;height:8px;border-radius:50%;background:${C};box-shadow:0 0 0 2px ${BG};transform:translate(-50%,-50%);"></div>`);
            plot.push(at(pct(k), convTop + CH - 12, `<span style="background:${BG};padding:1px 6px;font-style:italic;font-size:11.5px;color:var(--text-secondary);">point d’inflexion</span>`, "-50%", "nh-student-hide"));
          }
        }
      }
    }

    outer.push(hline(XH));
    outer.push(`<div style="position:absolute;left:${LABW}px;top:0;bottom:0;width:1px;background:${C};opacity:0.85;"></div>`);

    const tableHtml =
      `<div class="nh-math-table-card" style="position:relative;height:${total}px;min-width:440px;max-width:740px;margin:0 auto;box-sizing:content-box;">` +
      outer.join("") +
      `<div style="position:absolute;left:${LABW}px;right:0;top:0;bottom:0;">${plot.join("")}</div>` +
      `</div>`;
    return nhWrapMathFigure(tableHtml, { hasStudentMode: true, oracle });
  }

  // ---------- 2. Droite numérique & Intervalles ----------
  function parseNumberLineSpec(text) {
    const lines = String(text).split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
    const spec = { min: null, max: null, intervals: [] };
    const colMap = {
      bleu: "#2563eb", blue: "#2563eb",
      rouge: "#dc2626", red: "#dc2626",
      vert: "#16a34a", green: "#16a34a",
      orange: "#ea580c", violet: "#7c3aed", purple: "#7c3aed",
    };
    const palette = ["#2563eb", "#dc2626", "#16a34a", "#7c3aed"];
    for (const ln of lines) {
      const bm = ln.match(/^(?:bornes|axe|domaine)\s*:\s*([^|;]+)[|;]\s*(.+)$/i);
      if (bm) {
        const a = vtNum(bm[1]), b = vtNum(bm[2]);
        if (a !== null && Math.abs(a) < 1e9) spec.min = a;
        if (b !== null && Math.abs(b) < 1e9) spec.max = b;
        continue;
      }
      const im = ln.match(/^(?:([^=\[\]]+?)\s*=\s*)?(\[|\])\s*([^;,\]]+?)\s*[;,]\s*([^;,\[]+?)\s*(\[|\])(?:\s*:\s*([a-zA-Z]+))?$/);
      if (im) {
        const name = (im[1] || "").trim();
        const bL = im[2], rawA = im[3].trim(), rawB = im[4].trim(), bR = im[5];
        const colKey = (im[6] || "").toLowerCase();
        const aInf = /^-\s*(?:oo|\\infty|inf|∞)$/i.test(rawA);
        const bInf = /^\+?\s*(?:oo|\\infty|inf|∞)$/i.test(rawB);
        const aVal = aInf ? -Infinity : vtNum(rawA);
        const bVal = bInf ? Infinity : vtNum(rawB);
        if (aVal === null || bVal === null) continue;
        const incL = bL === "[";
        const incR = bR === "]";
        const color = colMap[colKey] || palette[spec.intervals.length % palette.length];
        const labelTex = (name ? name + " = " : "") + `${bL}${rawA.replace(/([+-]?)oo/i, "$1\\infty")}\\,;\\,${rawB.replace(/([+-]?)oo/i, "$1\\infty")}${bR}`;
        spec.intervals.push({ name, aVal, bVal, rawA, rawB, incL, incR, bL, bR, color, labelTex });
      }
    }
    return spec.intervals.length > 0 ? spec : null;
  }

  function renderNumberLineSpec(spec) {
    const finiteVals = [];
    spec.intervals.forEach((it) => {
      if (isFinite(it.aVal)) finiteVals.push(it.aVal);
      if (isFinite(it.bVal)) finiteVals.push(it.bVal);
    });
    if (!finiteVals.length) finiteVals.push(-2, 2);
    const minV = spec.min !== null ? spec.min : Math.floor(Math.min(...finiteVals)) - 2;
    const maxV = spec.max !== null ? spec.max : Math.ceil(Math.max(...finiteVals)) + 2;
    const span = Math.max(2, maxV - minV);
    const W = 640, PADL = 44, PADR = 52, plotW = W - PADL - PADR;
    const m = spec.intervals.length;
    const TRACK_H = 34;
    const axisY = 28 + m * TRACK_H;
    const H = axisY + 46;
    const X = (v) => PADL + ((v - minV) / span) * plotW;

    let svg = `<line x1="${PADL - 16}" y1="${axisY}" x2="${W - PADR + 18}" y2="${axisY}" stroke="currentColor" stroke-width="1.6"/>`;
    svg += `<path d="M${W - PADR + 22},${axisY} L${W - PADR + 13},${axisY - 4.5} L${W - PADR + 13},${axisY + 4.5} Z" fill="currentColor"/>`;
    let html = `<div style="position:absolute;left:${W - PADR + 28}px;top:${axisY}px;transform:translate(0,-50%);">${vtMath("x")}</div>`;

    const step = span <= 12 ? 1 : span <= 24 ? 2 : Math.ceil(span / 10);
    for (let v = Math.ceil(minV); v <= Math.floor(maxV); v += step) {
      const px = X(v);
      svg += `<line x1="${px}" y1="${axisY - 4}" x2="${px}" y2="${axisY + 4}" stroke="currentColor" stroke-width="1.2"/>`;
      html += `<div style="position:absolute;left:${px}px;top:${axisY + 18}px;transform:translate(-50%,-50%);font-size:12.5px;opacity:0.85;">${vtMath(String(v))}</div>`;
    }

    let okOrder = true;
    spec.intervals.forEach((it, idx) => {
      if (it.aVal > it.bVal) okOrder = false;
      const y = axisY - (idx + 1) * TRACK_H + 6;
      const x1 = isFinite(it.aVal) ? X(it.aVal) : PADL - 10;
      const x2 = isFinite(it.bVal) ? X(it.bVal) : W - PADR + 10;
      const col = it.color;

      svg += `<g class="nh-student-hide">`;
      svg += `<line x1="${x1}" y1="${y}" x2="${x2}" y2="${y}" stroke="${col}" stroke-width="3.2" stroke-linecap="round"/>`;

      const drawBracket = (px, isLeft, included) => {
        const dir = (isLeft && included) || (!isLeft && !included) ? 1 : -1;
        svg += `<path d="M${px + dir * 5},${y - 7} L${px},${y - 7} L${px},${y + 7} L${px + dir * 5},${y + 7}" fill="none" stroke="${col}" stroke-width="2.2"/>`;
        svg += `<line x1="${px}" y1="${y + 7}" x2="${px}" y2="${axisY}" stroke="${col}" stroke-width="1" stroke-dasharray="3 3" opacity="0.65"/>`;
      };

      if (isFinite(it.aVal)) drawBracket(x1, true, it.incL);
      else svg += `<path d="M${x1 - 4},${y} L${x1 + 4},${y - 4} M${x1 - 4},${y} L${x1 + 4},${y + 4}" fill="none" stroke="${col}" stroke-width="2"/>`;

      if (isFinite(it.bVal)) drawBracket(x2, false, it.incR);
      else svg += `<path d="M${x2 + 4},${y} L${x2 - 4},${y - 4} M${x2 + 4},${y} L${x2 - 4},${y + 4}" fill="none" stroke="${col}" stroke-width="2"/>`;
      svg += `</g>`;

      const midX = (x1 + x2) / 2;
      html += `<div class="nh-student-hide" style="position:absolute;left:${midX}px;top:${y - 13}px;transform:translate(-50%,-50%);color:${col};font-weight:600;font-size:13px;background:var(--bg-primary,#faf9f5);padding:0 5px;border-radius:3px;white-space:nowrap;">${vtMath(it.labelTex)}</div>`;
    });

    const oracle = okOrder
      ? { ok: true, label: "✓ Intervalles vérifiés", detail: "Bornes ordonnées et crochets conformes." }
      : { ok: false, label: "⚠ Bornes inversées", detail: "Une borne inférieure dépasse la borne supérieure." };

    const inner =
      `<div style="position:relative;width:${W}px;height:${H}px;margin:0 auto;">` +
      `<svg width="${W}" height="${H}" style="position:absolute;inset:0;overflow:visible;" aria-hidden="true">${svg}</svg>${html}` +
      `</div>`;
    return nhWrapMathFigure(inner, { hasStudentMode: true, oracle });
  }

  // ---------- 3. Arbre de probabilités (2, 3, N branches + Oracle Somme = 1) ----------
  function normTreeEventKey(s) {
    let t = String(s == null ? "" : s).trim().replace(/\$/g, "");
    let isBar = false;
    if (/\\(?:overline|bar)\s*\{([^}]*)\}/i.test(t)) {
      isBar = true;
      t = t.replace(/\\(?:overline|bar)\s*\{([^}]*)\}/gi, "$1");
    } else if (/^(?:non[\s_]+|not[\s_]+|¬|!)/i.test(t)) {
      isBar = true;
      t = t.replace(/^(?:non[\s_]+|not[\s_]+|¬|!)/i, "");
    } else if (/['’\u0304\u0305]$/.test(t) || /_?bar$/i.test(t)) {
      isBar = true;
      t = t.replace(/['’\u0304\u0305]+$/, "").replace(/_?bar$/i, "");
    }
    const base = t.toLowerCase().replace(/[^a-z0-9]/g, "");
    return (isBar ? "bar_" : "") + base;
  }

  function parseProbNumeric(s) {
    let t = String(s == null ? "" : s).replace(/\$/g, "").trim().replace(/,/g, ".");
    if (!t) return NaN;
    if (t.endsWith("%")) return parseFloat(t) / 100;
    const fm = t.match(/^\\d?frac\{([^{}]+)\}\{([^{}]+)\}$/);
    if (fm) return parseFloat(fm[1]) / parseFloat(fm[2]);
    const sm = t.match(/^(-?[\d.]+)\s*\/\s*([\d.]+)$/);
    if (sm) return parseFloat(sm[1]) / parseFloat(sm[2]);
    return /^[-+]?\d*\.?\d+$/.test(t) ? parseFloat(t) : NaN;
  }

  function parseTreeSpec(text) {
    const mk = (tok) => {
      const m = tok.trim().match(/^(.*?)\s*\(\s*([^)]*)\)\s*$/);
      return { ev: (m ? m[1] : tok).trim(), p: m ? m[2].trim() : "", kids: [], path: "", key: "" };
    };
    const defs = [];
    String(text).split(/\r?\n/).forEach((ln) => {
      const m = ln.trim().match(/^([^:]+):\s*(.*)$/);
      if (!m) return;
      const toks = m[2].split("|").map((t) => t.trim()).filter(Boolean);
      if (!toks.length) return;
      const am = m[1].match(/apr[eè]s[_\s]+(.+)$/i);
      defs.push({ parent: am ? normTreeEventKey(am[1]) : null, toks });
    });
    if (!defs.length) return null;
    const root = { ev: "", p: "", kids: [], path: "", key: "" };
    const byPath = { "": root };
    const byKey = {};
    let rootDone = false;
    defs.forEach((d) => {
      let par = null;
      if (d.parent === null) {
        if (rootDone) return;
        rootDone = true;
        par = root;
      } else {
        par = byPath[d.parent] || byKey[d.parent] || null;
      }
      if (!par) return;
      d.toks.forEach((t) => {
        const nd = mk(t);
        nd.key = normTreeEventKey(nd.ev);
        nd.path = par.path ? par.path + "_" + nd.key : nd.key;
        par.kids.push(nd);
        byPath[nd.path] = nd;
        if (!byKey[nd.key]) byKey[nd.key] = nd;
      });
    });
    return root.kids.length ? root : null;
  }

  function parseTikzChildTree(code) {
    if (!/\bchild\s*\{/.test(code)) return null;
    const parseChildren = (str) => {
      const kids = [];
      let i = 0;
      while (i < str.length) {
        const cm = str.slice(i).match(/\bchild\s*(?:\[[^\]]*\])?\s*\{/);
        if (!cm) break;
        const braceStart = i + cm.index + cm[0].length - 1;
        const [inner, nextI] = tkBal(str, braceStart);
        i = nextI;
        let withoutSub = "";
        let j = 0;
        while (j < inner.length) {
          const sub = inner.slice(j).match(/\bchild\s*(?:\[[^\]]*\])?\s*\{/);
          if (!sub) { withoutSub += inner.slice(j); break; }
          withoutSub += inner.slice(j, j + sub.index);
          const [, afterSub] = tkBal(inner, j + sub.index + sub[0].length - 1);
          j = afterSub;
        }
        const nm = withoutSub.match(/\bnode\s*(?:\[[^\]]*\])?\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}/);
        const em = withoutSub.match(/edge\s+from\s+parent[\s\S]*?\bnode\s*(?:\[[^\]]*\])?\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}/);
        const ev = nm ? nm[1].replace(/\$/g, "").trim() : "";
        const p = em ? em[1].replace(/\$/g, "").trim() : "";
        const subKids = parseChildren(inner);
        if (ev || subKids.length) {
          kids.push({ ev: ev || "•", p, kids: subKids });
        }
      }
      return kids;
    };
    const topKids = parseChildren(code);
    return topKids.length ? { ev: "", p: "", kids: topKids } : null;
  }

  function renderTreeSpec(root) {
    const LEAF = 50, COLW = 205, PADL = 26, LBL = 44;
    let depth = 0;
    const countLeaves = (n, d) => {
      depth = Math.max(depth, d);
      return n.kids.length ? n.kids.reduce((s, k) => s + countLeaves(k, d + 1), 0) : 1;
    };
    const nl = countLeaves(root, 0);
    const H = Math.max(120, nl * LEAF + 24), W = PADL + depth * COLW + 96;
    let li = 0, svg = "", html = "";
    let checkedNodes = 0, badSumDetail = "";

    const place = (n, d) => {
      n.x = PADL + d * COLW;
      if (!n.kids.length) n.y = 12 + LEAF * (li++ + 0.5);
      else {
        const nums = n.kids.map((k) => parseProbNumeric(k.p));
        if (nums.length >= 2 && nums.every((v) => !isNaN(v))) {
          checkedNodes++;
          const sum = nums.reduce((a, b) => a + b, 0);
          if (Math.abs(sum - 1) > 1e-3 && !badSumDetail) {
            badSumDetail = `Nœud ${n.ev || "racine"} : somme des branches = ${+sum.toFixed(3)} ≠ 1`;
          }
        }
        n.kids.forEach((k) => place(k, d + 1));
        n.y = (n.kids[0].y + n.kids[n.kids.length - 1].y) / 2;
      }
    };
    place(root, 0);
    const evM = (s) => {
      let t = String(s == null ? "" : s).replace(/\$/g, "").trim();
      t = t.replace(/^non[\s_]+([A-Za-z0-9_]+)$/i, "\\overline{$1}");
      t = t.replace(/^([A-Za-z]+)_?bar$/i, "\\overline{$1}");
      t = t.replace(/^([A-Za-z])'(\d*)$/, (_, l, d) => `\\overline{${l}${d ? "_{" + d + "}" : ""}}`);
      t = t.replace(/\\overline\{([A-Za-z]+)(\d+)\}/g, "\\overline{$1_{$2}}");
      t = t.replace(/^([A-Za-z]+)(\d+)$/, "$1_{$2}");
      return t;
    };
    const prM = (s) =>
      /^\d+\.\d+$/.test(s) ? s.replace(".", ",") : s.replace(/^(\d+)\/(\d+)$/, "\\frac{$1}{$2}");
    const draw = (n) =>
      n.kids.forEach((k) => {
        const x1 = n === root ? n.x : n.x + LBL;
        const x2 = k.x - 8;
        svg += `<line x1="${x1}" y1="${n.y}" x2="${x2}" y2="${k.y}" stroke="currentColor" stroke-width="1.45"/>`;
        if (k.p) {
          const mx = x1 + (x2 - x1) * 0.48;
          const my = n.y + (k.y - n.y) * 0.48;
          html +=
            `<div style="position:absolute;left:${mx}px;top:${my}px;transform:translate(-50%,-50%);background:var(--bg-primary,#faf9f5);padding:1px 5px;border-radius:4px;font-size:12.5px;white-space:nowrap;">` +
            `<span class="nh-student-hide">${vtMath(prM(k.p))}</span>` +
            `<span class="nh-student-only" style="color:var(--text-muted);font-family:var(--font-mono);font-size:11px;">[ … ]</span>` +
            `</div>`;
        }
        html += `<div style="position:absolute;left:${k.x}px;top:${k.y}px;transform:translate(0,-50%);white-space:nowrap;font-weight:500;">${vtMath(evM(k.ev))}</div>`;
        draw(k);
      });
    draw(root);
    svg += `<circle cx="${root.x}" cy="${root.y}" r="3.2" fill="currentColor"/>`;

    const oracle = badSumDetail
      ? { ok: false, label: "⚠ Somme ≠ 1", detail: badSumDetail }
      : checkedNodes > 0
      ? { ok: true, label: "✓ Somme = 1", detail: "La somme des probabilités issues de chaque nœud vaut exactement 1." }
      : null;

    const inner =
      `<div style="position:relative;width:${W}px;height:${H}px;margin:0 auto;">` +
      `<svg width="${W}" height="${H}" style="position:absolute;inset:0;overflow:visible;" aria-hidden="true">${svg}</svg>${html}</div>`;
    return nhWrapMathFigure(inner, { hasStudentMode: true, oracle });
  }

  // ---------- 4. TikZ / pgfplots / Graphes + Pointeur Magnétique (x ; f(x)) ----------
  const TK_COL = {
    red: [220, 38, 38], blue: [37, 99, 235], green: [22, 163, 74], darkgreen: [21, 128, 61],
    black: [0, 0, 0], white: [255, 255, 255], gray: [128, 128, 128], grey: [128, 128, 128],
    orange: [249, 115, 22], purple: [147, 51, 234], violet: [124, 58, 237], teal: [13, 148, 136],
    cyan: [6, 182, 212], magenta: [217, 70, 239], brown: [146, 64, 14], yellow: [234, 179, 8],
    lime: [132, 204, 22], pink: [236, 72, 153], olive: [113, 113, 22],
  };
  const TK_H = {
    sin: (a) => Math.sin((a * Math.PI) / 180), cos: (a) => Math.cos((a * Math.PI) / 180),
    tan: (a) => Math.tan((a * Math.PI) / 180), sinr: Math.sin, cosr: Math.cos, tanr: Math.tan,
    ln: Math.log, log: Math.log10, exp: Math.exp, sqrt: Math.sqrt, abs: Math.abs,
    deg: (a) => (a * 180) / Math.PI, rad: (a) => (a * Math.PI) / 180,
    pow: Math.pow, atan: (a) => (Math.atan(a) * 180) / Math.PI, floor: Math.floor, ceil: Math.ceil,
    min: Math.min, max: Math.max,
  };

  function tkColor(spec, forFill) {
    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    const p = String(spec || "").trim().replace(/[{}]/g, "").split("!");
    const name0 = String(p[0]).trim().toLowerCase();
    const base = (n) => TK_COL[String(n).trim().toLowerCase()] || [0, 0, 0];
    let c = base(name0);
    if (p.length > 1) {
      let k = Math.max(0, Math.min(100, parseFloat(p[1]) || 0)) / 100;
      if (isDark && !p[2]) {
        const bgDark = forFill ? [27, 32, 41] : [36, 42, 54];
        const kBoost = forFill ? Math.min(0.45, Math.max(0.22, k * 1.4)) : Math.max(0.38, k);
        c = c.map((v, i) => Math.round(v * kBoost + bgDark[i] * (1 - kBoost)));
        return `rgb(${c[0]},${c[1]},${c[2]})`;
      }
      const o = p[2] ? base(p[2]) : [255, 255, 255];
      c = c.map((v, i) => Math.round(v * k + o[i] * (1 - k)));
    }
    if (name0 === "black" && p.length === 1) return "currentColor";
    if (name0 === "white" && p.length === 1) return isDark ? "#1E232D" : "#FFFFFF";
    if (isDark && !forFill && name0 === "blue" && p.length === 1) return "rgb(96,165,250)";
    if (isDark && !forFill && name0 === "red" && p.length === 1) return "rgb(248,113,113)";
    return `rgb(${c[0]},${c[1]},${c[2]})`;
  }

  function tkContrastTextColor(rgbStr) {
    if (!rgbStr) return "";
    const m = String(rgbStr).match(/rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)/i);
    if (!m) return "";
    const r = +m[1], g = +m[2], b = +m[3];
    const lum = 0.299 * r + 0.587 * g + 0.114 * b;
    return lum > 165 ? "#141518" : "#F8FAFC";
  }

  function tkLen(s) {
    const m = String(s == null ? "" : s).trim().match(/^(-?[\d.]+)\s*(cm|mm|pt|em|ex)?$/);
    if (!m) return NaN;
    const v = parseFloat(m[1]);
    const u = m[2] || "cm";
    return u === "mm" ? v / 10 : u === "pt" ? v / 28.4527 : u === "em" ? v * 0.35 : u === "ex" ? v * 0.16 : v;
  }

  function tkCompile(expr) {
    let s = String(expr == null ? "" : expr).trim().replace(/^\{([\s\S]*)\}$/, "$1");
    if (!s) return null;
    s = s.replace(/[{}]/g, (c) => (c === "{" ? "(" : ")"));
    s = s.replace(/\\[xt]\b/g, "x").replace(/\\pi\b|\bpi\b/g, "(3.141592653589793)");
    s = s.replace(/(sin|cos|tan)\s*\(\s*([^()]*?)\s+r\s*\)/g, "$1r($2)");
    s = s.replace(/(\d)\s*(?=x\b|\()/g, "$1*");
    s = s.replace(/\)\s*(?=x\b|\d|\()/g, ")*");
    s = s.replace(/x\s*(?=\()/g, "x*");
    for (let k = 0; k < 5; k++) {
      s = s.replace(/([\w.]+|\([^()]*\))\s*\^\s*(-?[\w.]+|\([^()]*\))/g, "pow($1,$2)");
    }
    const ids = s.match(/[A-Za-z_]+/g) || [];
    if (ids.some((w) => w !== "x" && w !== "e" && !(w in TK_H))) return null;
    if (/[^\w\s+\-*/().,]/.test(s)) return null;
    try {
      const f = Function(...Object.keys(TK_H), "x", "e", "return (" + s + ");");
      const vals = Object.values(TK_H);
      return (x) => f(...vals, x, Math.E);
    } catch (_) {
      return null;
    }
  }

  function tkNum(s) {
    const t = String(s == null ? "" : s).trim();
    const L = tkLen(t);
    if (!isNaN(L)) return L;
    const f = tkCompile(t);
    if (!f) return NaN;
    try {
      const v = f(0);
      return typeof v === "number" ? v : NaN;
    } catch (_) {
      return NaN;
    }
  }

  function tkSplit(str, sep) {
    const out = [];
    let depth = 0, cur = "";
    for (let i = 0; i < str.length; i++) {
      const ch = str[i];
      if ("([{".indexOf(ch) >= 0) depth++;
      else if (")]}".indexOf(ch) >= 0) depth = Math.max(0, depth - 1);
      if (ch === sep && depth === 0) { out.push(cur); cur = ""; } else cur += ch;
    }
    out.push(cur);
    return out;
  }

  function tkBal(str, i) {
    const open = str[i], close = { "(": ")", "[": "]", "{": "}" }[open];
    let d = 0;
    for (let j = i; j < str.length; j++) {
      if (str[j] === open) d++;
      else if (str[j] === close) { d--; if (d === 0) return [str.slice(i + 1, j), j + 1]; }
    }
    return [str.slice(i + 1), str.length];
  }

  function tkItems(list) {
    const it = list.split(",").map((s) => s.trim()).filter(Boolean);
    const k = it.indexOf("...");
    if (k < 1) return it;
    const a = parseFloat(it[k - 1]), b = parseFloat(it[it.length - 1]);
    const step = k >= 2 ? a - parseFloat(it[k - 2]) : b >= a ? 1 : -1;
    const out = it.slice(0, k);
    if (!step || isNaN(step)) return out;
    for (let v = a + step; step > 0 ? v <= b + 1e-9 : v >= b - 1e-9; v += step) out.push(String(+v.toFixed(6)));
    return out;
  }

  function tkExpandForeach(code) {
    for (let guard = 0; guard < 30; guard++) {
      const m = code.match(/\\foreach\s*((?:\\[a-zA-Z]+\s*\/?\s*)+)in\s*/);
      if (!m) break;
      const vars = m[1].split("/").map((v) => v.trim().replace(/^\\/, ""));
      let i = m.index + m[0].length;
      if (code[i] !== "{") { code = code.slice(0, m.index) + code.slice(i); continue; }
      const lr = tkBal(code, i);
      const items = tkItems(lr[0]);
      i = lr[1];
      while (i < code.length && /\s/.test(code[i])) i++;
      let body, end;
      if (code[i] === "{") { const br = tkBal(code, i); body = br[0]; end = br[1]; }
      else { const e = code.indexOf(";", i); end = e < 0 ? code.length : e + 1; body = code.slice(i, end); }
      const expanded = items
        .map((val) => {
          const parts = String(val).split("/");
          let b = body;
          vars.forEach((v, idx) => {
            const valPart = parts[idx] !== undefined ? parts[idx].trim() : parts[0].trim();
            b = b.replace(new RegExp("\\\\" + v + "(?![a-zA-Z])", "g"), () => valPart);
          });
          return b;
        })
        .join("\n");
      code = code.slice(0, m.index) + expanded + code.slice(end);
    }
    return code;
  }

  function tkParseCoord(inner, names) {
    const t = String(inner == null ? "" : inner).trim().replace(/^axis\s+cs\s*:/i, "").trim();
    const nm = t.match(/^([A-Za-z_][\w-]*)(?:\.([\w ]+))?$/);
    if (nm) {
      const n = names[nm[1]];
      if (!n) return null;
      return { x: n.x, y: n.y, r: n.r || 0, n: nm[1] };
    }
    if (/[$|!]/.test(t)) return null;
    const pol = t.match(/^([^,:]+):([^,]+)$/);
    if (pol) {
      const a = (tkNum(pol[1]) * Math.PI) / 180, r = tkNum(pol[2]);
      return isNaN(a) || isNaN(r) ? null : { x: r * Math.cos(a), y: r * Math.sin(a), r: 0 };
    }
    const parts = tkSplit(t, ",");
    if (parts.length !== 2) return null;
    const x = tkNum(parts[0]), y = tkNum(parts[1]);
    return isNaN(x) || isNaN(y) ? null : { x, y, r: 0 };
  }

  function tkStyle(optStr, base) {
    const st = Object.assign(
      {
        stroke: "currentColor", width: 1.3, fill: null, dash: "",
        arrowE: false, arrowS: false, smooth: false, draw: true,
        fillOp: 1, colorSet: false, step: 0, xstep: 0, ystep: 0,
        domain: null, samples: null,
      },
      base || {}
    );
    const W = { "ultra thin": 0.45, "very thin": 0.65, thin: 0.9, semithick: 1.5, thick: 1.85, "very thick": 2.6, "ultra thick": 3.5 };
    tkSplit(optStr || "", ",").forEach((raw) => {
      const o = raw.trim();
      if (!o) return;
      const eq = o.indexOf("=");
      const k = (eq < 0 ? o : o.slice(0, eq)).trim();
      const v = eq < 0 ? "" : o.slice(eq + 1).trim().replace(/^\{([\s\S]*)\}$/, "$1");
      if (k in W) st.width = W[k];
      else if (k === "line width") { const n = tkLen(v); if (!isNaN(n)) st.width = Math.max(0.8, n * 28.4527 * 1.25); }
      else if (/dashed$/.test(k)) st.dash = "6 4";
      else if (/dotted$/.test(k)) st.dash = "1.8 3.5";
      else if (k === "draw") { if (v === "none") st.draw = false; else if (v) { st.stroke = tkColor(v); st.colorSet = true; } }
      else if (k === "fill") { if (v !== "none") st.fill = tkColor(v || (st.colorSet ? st.stroke : "black"), true); }
      else if (k === "color") { st.stroke = tkColor(v); st.colorSet = true; }
      else if (k === "opacity" || k === "fill opacity") st.fillOp = parseFloat(v) || 1;
      else if (k === "smooth") st.smooth = true;
      else if (k === "domain") {
        const dm = v.match(/(-?[\d.]+)\s*:\s*(-?[\d.]+)/);
        if (dm) st.domain = [+dm[1], +dm[2]];
      } else if (k === "samples") {
        const sm = parseInt(v, 10);
        if (sm > 1) st.samples = sm;
      } else if (k === "step") st.step = tkNum(v) || 0;
      else if (k === "xstep") st.xstep = tkNum(v) || 0;
      else if (k === "ystep") st.ystep = tkNum(v) || 0;
      else if (k === "help lines") { st.stroke = tkColor("gray!35"); st.width = 0.65; }
      else if (eq < 0 && /^(<|<->|<-)?-+(>|>>|stealth|latex|Stealth|\{[^}]*\})?$/.test(k)) {
        if (k.charAt(0) === "<") st.arrowS = true;
        if (/(>|stealth|latex|Stealth|\})$/.test(k)) st.arrowE = true;
      } else if (eq < 0 && TK_COL[k.split("!")[0].toLowerCase()]) { st.stroke = tkColor(k); st.colorSet = true; }
    });
    return st;
  }

  function tkText(s) {
    return String(s == null ? "" : s)
      .split("\\\\")
      .map((ln) =>
        ln
          .split("$")
          .map((seg, i) =>
            i % 2
              ? renderMathExpression(seg, false)
              : esc(
                  seg
                    .replace(/\\(?:textbf|textit|mathrm|text)\{([^}]*)\}/g, "$1")
                    .replace(/\\(?:small|footnotesize|tiny|large|Large|bfseries|itshape)\b\s*/g, "")
                    .trim()
                )
          )
          .join("")
      )
      .join("<br>");
  }

  function tkAxisOpts(ao) {
    const o = { lines: "box", grid: false, domain: null, samples: 120 };
    tkSplit(ao, ",").forEach((raw) => {
      const p = raw.split("=");
      const k = p[0].trim();
      const v = p.slice(1).join("=").trim().replace(/^\{([\s\S]*)\}$/, "$1");
      if (["xmin", "xmax", "ymin", "ymax"].includes(k)) { const n = tkNum(v); if (!isNaN(n)) o[k] = n; }
      else if (k === "width" || k === "height") { const n = tkLen(v); if (!isNaN(n)) o[k] = n; }
      else if (k === "axis lines" || k === "axis x line" || k === "axis y line") {
        if (v === "middle" || v === "center") o.lines = "middle";
        else o.lines = v;
      } else if (k === "grid") o.grid = v !== "none";
      else if (k === "domain") { const m = v.match(/(-?[\d.]+)\s*:\s*(-?[\d.]+)/); if (m) o.domain = [+m[1], +m[2]]; }
      else if (k === "samples") { const s = parseInt(v, 10); if (s > 1) o.samples = s; }
      else if (k === "xlabel" || k === "ylabel") o[k] = v;
    });
    return o;
  }

  function tkGeom(e, Tf) {
    const a = Tf(e.a), b = Tf(e.b);
    if (e.loopDir || (e.a.n && e.a.n === e.b.n)) {
      const dir = e.loopDir || "above";
      const angMap = { above: Math.PI / 2, below: -Math.PI / 2, left: Math.PI, right: 0 };
      const baseAng = angMap[dir] !== undefined ? angMap[dir] : Math.PI / 2;
      const spread = 0.52;
      const r = Math.max(0.28, e.a.r || 0.35);
      const reach = r + 0.95;
      const p0 = { x: a.x + r * Math.cos(baseAng + spread), y: a.y + r * Math.sin(baseAng + spread) };
      const p1 = { x: a.x + r * Math.cos(baseAng - spread), y: a.y + r * Math.sin(baseAng - spread) };
      const c1 = { x: a.x + reach * Math.cos(baseAng + spread * 1.15), y: a.y + reach * Math.sin(baseAng + spread * 1.15) };
      const c2 = { x: a.x + reach * Math.cos(baseAng - spread * 1.15), y: a.y + reach * Math.sin(baseAng - spread * 1.15) };
      return { p0, c1, c2, p1, line: false, isLoop: true, loopDir: dir };
    }
    if (e.c1) return { p0: a, c1: Tf(e.c1), c2: Tf(e.c2), p1: b, line: false };
    const dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 1e-9;
    let ctrl = null;
    if (e.bend) {
      const off = (d / 2) * Math.tan((Math.abs(e.bend) * Math.PI) / 180) * Math.sign(e.bend);
      ctrl = { x: (a.x + b.x) / 2 - (dy / d) * off, y: (a.y + b.y) / 2 + (dx / d) * off };
    }
    const tr = (from, toward, r) => {
      if (!r) return from;
      const vx = toward.x - from.x, vy = toward.y - from.y, l = Math.hypot(vx, vy) || 1;
      return { x: from.x + (vx / l) * r, y: from.y + (vy / l) * r };
    };
    const p0 = tr(a, ctrl || b, e.a.r || 0), p1 = tr(b, ctrl || a, e.b.r || 0);
    const lp = (p, q, t) => ({ x: p.x + (q.x - p.x) * t, y: p.y + (q.y - p.y) * t });
    if (ctrl) return { p0, c1: lp(p0, ctrl, 2 / 3), c2: lp(p1, ctrl, 2 / 3), p1, line: false };
    return { p0, c1: lp(p0, p1, 1 / 3), c2: lp(p0, p1, 2 / 3), p1, line: true };
  }

  function tkCub(g, t) {
    const u = 1 - t, a = u * u * u, b = 3 * u * u * t, c = 3 * u * t * t, d = t * t * t;
    return {
      x: a * g.p0.x + b * g.c1.x + c * g.c2.x + d * g.p1.x,
      y: a * g.p0.y + b * g.c1.y + c * g.c2.y + d * g.p1.y,
    };
  }

  function tkPath(body, st, ctx, cmd) {
    const P = { st, segs: [], circles: [], grids: [], closed: false, clip: ctx.clip, isPlot: false, pts: [] };
    if (cmd === "path" && !/\bedge\b/.test(body)) st.draw = false;
    const N = body.length;
    let i = 0, cur = null, start = null, op = null, bend = 0, loopDir = null, last = null, pend = [];
    const ws = () => { while (i < N && /\s/.test(body[i])) i++; };
    const O = (x, y) => ({ x, y, r: 0 });
    const addEdge = (a, b, kind, bd, lp) => {
      let e;
      if (kind === "-|" || kind === "|-") {
        const m = kind === "-|" ? O(b.x, a.y) : O(a.x, b.y);
        P.segs.push({ a, b: m, bend: 0 });
        e = { a: m, b, bend: 0 };
      } else e = { a, b, bend: bd || 0, loopDir: lp || null };
      P.segs.push(e);
      last = e;
      return e;
    };
    const setEdge = (nd, e, o) => {
      nd.edge = e;
      const pm = o.match(/pos\s*=\s*([\d.]+)/);
      nd.f = pm ? parseFloat(pm[1]) : /near start/.test(o) ? 0.25 : /near end/.test(o) ? 0.75 : /at start/.test(o) ? 0 : /at end/.test(o) ? 1 : 0.5;
      nd.auto = /(^|[\s,])auto([\s,]|$)/.test(o) || Boolean(e.bend || e.loopDir);
      nd.swap = /swap|right|below/.test(o);
    };
    const arrive = (pt) => {
      if (cur && op) {
        const eg = addEdge(cur, pt, op, op === "to" ? bend : 0, op === "to" ? loopDir : null);
        pend.forEach((n) => setEdge(n, eg, n.opts));
        pend = [];
      } else if (!cur) start = pt;
      cur = pt; op = null; bend = 0; loopDir = null;
    };
    const addPoly = (pts, smooth) => {
      if (P.isPlot) P.pts.push(...pts);
      for (let k = 0; k < pts.length - 1; k++) {
        const p0 = pts[Math.max(0, k - 1)], p1 = pts[k], p2 = pts[k + 1], p3 = pts[Math.min(pts.length - 1, k + 2)];
        const e = { a: p1, b: p2, bend: 0 };
        if (smooth) {
          e.c1 = { x: p1.x + (p2.x - p0.x) / 6, y: p1.y + (p2.y - p0.y) / 6 };
          e.c2 = { x: p2.x - (p3.x - p1.x) / 6, y: p2.y - (p3.y - p1.y) / 6 };
        }
        P.segs.push(e);
        last = e;
      }
      if (pts.length) cur = pts[pts.length - 1];
    };

    while (i < N) {
      ws();
      if (i >= N) break;
      const ch = body[i];
      if (ch === "(") {
        const r = tkBal(body, i); i = r[1];
        const pt = tkParseCoord(r[0], ctx.names);
        if (!pt) return;
        arrive(pt);
        continue;
      }
      if (body.startsWith("++(", i)) {
        const r = tkBal(body, i + 2); i = r[1];
        const d = tkParseCoord(r[0], ctx.names);
        if (!d || !cur) return;
        arrive({ x: cur.x + d.x, y: cur.y + d.y, r: 0 });
        continue;
      }
      if (body.startsWith("--", i)) { op = "--"; i += 2; continue; }
      if (body.startsWith("-|", i) || body.startsWith("|-", i)) { op = body.substr(i, 2); i += 2; continue; }
      const rest = body.slice(i);
      let m;
      if ((m = rest.match(/^cycle\b/))) {
        if (cur && start) addEdge(cur, start, "--", 0);
        P.closed = true; i += 5; continue;
      }
      if ((m = rest.match(/^(?:to|edge)\b\s*/))) {
        i += m[0].length; op = "to"; bend = 0; loopDir = null;
        if (body[i] === "[") {
          const r = tkBal(body, i); i = r[1];
          const bm = r[0].match(/bend\s+(left|right)(?:\s*=\s*([\d.]+))?/);
          if (bm) bend = (bm[1] === "left" ? 1 : -1) * (bm[2] ? parseFloat(bm[2]) : 28);
          const lm = r[0].match(/\bloop(?:\s+(above|below|left|right))?/);
          if (lm) loopDir = lm[1] || "above";
          if (/->|stealth|latex/.test(r[0])) st.arrowE = true;
          if (/<-|<->/.test(r[0])) st.arrowS = true;
        }
        continue;
      }
      if ((m = rest.match(/^rectangle\b\s*/))) {
        i += m[0].length; ws();
        if (body[i] === "(" && cur) {
          const r = tkBal(body, i); i = r[1];
          const p2 = tkParseCoord(r[0], ctx.names);
          if (!p2) return;
          const c = cur, A = O(p2.x, c.y), B = O(p2.x, p2.y), D = O(c.x, p2.y);
          [[c, A], [A, B], [B, D], [D, O(c.x, c.y)]].forEach(([a, b]) => P.segs.push({ a, b, bend: 0 }));
          P.closed = true; cur = B;
        }
        continue;
      }
      if ((m = rest.match(/^grid\b\s*/))) {
        i += m[0].length; ws();
        if (body[i] === "(" && cur) {
          const r = tkBal(body, i); i = r[1];
          const p2 = tkParseCoord(r[0], ctx.names);
          if (!p2) return;
          P.grids.push({ a: cur, b: p2 });
          ctx.gridBounds = {
            x0: Math.min(cur.x, p2.x), y0: Math.min(cur.y, p2.y),
            x1: Math.max(cur.x, p2.x), y1: Math.max(cur.y, p2.y),
          };
          cur = p2;
        }
        continue;
      }
      if ((m = rest.match(/^circle\b\s*/))) {
        i += m[0].length; ws();
        let rad = 0.25;
        if (body[i] === "[" || body[i] === "(") {
          const r = tkBal(body, i); i = r[1];
          const n = tkLen(r[0].replace(/^radius\s*=\s*/, ""));
          if (!isNaN(n)) rad = n;
        }
        if (cur) P.circles.push({ c: cur, r: rad });
        continue;
      }
      if ((m = rest.match(/^plot\b\s*/))) {
        i += m[0].length; ws();
        let po = "";
        if (body[i] === "[") { const r = tkBal(body, i); po = r[0]; i = r[1]; ws(); }
        P.isPlot = true;
        if (body.startsWith("coordinates", i)) {
          i += 11; ws();
          const pts = [];
          if (body[i] === "{") {
            const r = tkBal(body, i); i = r[1];
            (r[0].match(/\(([^()]+)\)/g) || []).forEach((q) => { const c = tkParseCoord(q.slice(1, -1), {}); if (c) pts.push(c); });
          }
          addPoly(pts, st.smooth || /smooth/.test(po));
        } else if (body[i] === "(") {
          const r = tkBal(body, i); i = r[1];
          const parts = tkSplit(r[0], ",");
          const fx = tkCompile(parts[0]), fy = tkCompile(parts.slice(1).join(","));
          if (!fx || !fy) return;
          const dm = po.match(/domain\s*=\s*(-?[\d.]+)\s*:\s*(-?[\d.]+)/);
          const sm = po.match(/samples\s*=\s*(\d+)/);
          const gb = ctx.gridBounds;
          const a = dm ? +dm[1] : st.domain ? st.domain[0] : gb ? gb.x0 : -5;
          const b = dm ? +dm[2] : st.domain ? st.domain[1] : gb ? gb.x1 : 5;
          const S = Math.min(400, sm ? +sm[1] : st.samples || 120);
          const yLow = gb ? gb.y0 - 1.5 : -25;
          const yHigh = gb ? gb.y1 + 1.5 : 25;
          if (gb && !P.clip) P.clip = { x0: gb.x0, y0: gb.y0, x1: gb.x1, y1: gb.y1 };
          let run = [];
          const flush = () => { if (run.length > 1) addPoly(run, st.smooth || /smooth/.test(po)); run = []; };
          for (let k = 0; k <= S; k++) {
            const t = a + ((b - a) * k) / S;
            let X, Y;
            try { X = fx(t); Y = fy(t); } catch (_) { X = NaN; }
            if (isFinite(X) && isFinite(Y) && Y >= yLow && Y <= yHigh) run.push(O(X, Y));
            else flush();
          }
          flush();
        }
        continue;
      }
      if ((m = rest.match(/^node\b\s*/))) {
        i += m[0].length; ws();
        let nopts = "", name = "", at = null, text = "";
        if (body[i] === "[") { const r = tkBal(body, i); nopts = r[0]; i = r[1]; ws(); }
        if (body[i] === "(") { const r = tkBal(body, i); name = r[0].trim(); i = r[1]; ws(); }
        if (body.startsWith("at", i) && /[\s(]/.test(body[i + 2] || "")) {
          i += 2; ws();
          if (body[i] === "(") { const r = tkBal(body, i); at = tkParseCoord(r[0], ctx.names); i = r[1]; ws(); }
        }
        if (body[i] === "{") { const r = tkBal(body, i); text = r[0]; i = r[1]; }
        const so = (ctx.every ? ctx.every + "," : "") + nopts;
        const dr = /(^|[\s,])draw([\s,]|$)/.test(so), ci = /(^|[\s,])circle([\s,]|$)/.test(so);
        const mn = tkLen((so.match(/minimum size\s*=\s*([\d.]+\s*[a-z]*)/) || [])[1]);
        const rad = cmd === "coordinate" ? 0 : dr ? (isNaN(mn) ? (ci ? 0.36 : 0.32) : mn / 2) : text.trim() ? 0.2 : 0;
        const inheritedColor = st.colorSet ? st.stroke : null;
        const nd = { text, opts: nopts, inheritedColor, invisible: cmd === "coordinate" || (!text.trim() && !dr) };
        if (at) { nd.x = at.x; nd.y = at.y; ctx.nodes.push(nd); }
        else if (op && cur) {
          if (loopDir) { nd.loopDir = loopDir; }
          pend.push(nd); ctx.nodes.push(nd);
        } else if (last && /(midway|near start|near end|at start|at end|pos\s*=|auto)/.test(nopts)) {
          setEdge(nd, last, nopts); ctx.nodes.push(nd);
        } else if (cur) { nd.x = cur.x; nd.y = cur.y; ctx.nodes.push(nd); }
        else if (cmd === "node" || cmd === "coordinate") { nd.x = 0; nd.y = 0; ctx.nodes.push(nd); }
        if (name && nd.x !== undefined) ctx.names[name] = { x: nd.x, y: nd.y, r: rad, n: name };
        continue;
      }
      i++;
    }
    if (P.segs.length || P.circles.length || P.grids.length) ctx.paths.push(P);
  }

  function tkAddPlot(opts, rest, ctx, ax) {
    const st = tkStyle(opts, { stroke: "rgb(37,99,235)", width: 1.9 });
    const P = { st, segs: [], circles: [], grids: [], closed: false, clip: null, axisClip: true, plot: true, isPlot: true, pts: [] };
    let pts = [];
    const trimmedRest = rest.trim();
    if (trimmedRest[0] === "{" || (/^[a-zA-Z0-9(\\-]/.test(trimmedRest) && !/^coordinates\b/.test(trimmedRest))) {
      const exprStr = trimmedRest[0] === "{" ? tkBal(trimmedRest, 0)[0] : trimmedRest.replace(/;$/, "").trim();
      const f = tkCompile(exprStr);
      if (!f) return;
      const dm = opts.match(/domain\s*=\s*(-?[\d.]+)\s*:\s*(-?[\d.]+)/);
      const dom = dm ? [+dm[1], +dm[2]] : (ax && ax.domain) || [ax && ax.xmin != null ? ax.xmin : -5, ax && ax.xmax != null ? ax.xmax : 5];
      const sm = opts.match(/samples\s*=\s*(\d+)/), S = Math.min(400, sm ? +sm[1] : (ax && ax.samples) || 120);
      for (let k = 0; k <= S; k++) {
        const x = dom[0] + ((dom[1] - dom[0]) * k) / S;
        let y;
        try { y = f(x); } catch (_) { y = NaN; }
        pts.push(isFinite(y) && Math.abs(y) < 1e4 ? { x, y, r: 0 } : null);
      }
    } else if (/^coordinates\b/.test(trimmedRest)) {
      const bi = trimmedRest.indexOf("{");
      const inner = bi >= 0 ? tkBal(trimmedRest, bi)[0] : "";
      (inner.match(/\(([^()]+)\)/g) || []).forEach((q) => pts.push(tkParseCoord(q.slice(1, -1), {})));
    } else return;
    let prev = null;
    pts.forEach((p) => { if (p && prev) P.segs.push({ a: prev, b: p, bend: 0 }); prev = p; });
    P.pts = pts.filter(Boolean);
    if (P.segs.length) ctx.paths.push(P);
  }

  function tikzToHtml(codeRaw) {
    const code = String(codeRaw).replace(/(^|[^\\])%.*$/gm, "$1");
    const b0 = code.indexOf("\\begin{tikzpicture}"), b1 = code.lastIndexOf("\\end{tikzpicture}");
    if (b0 < 0 || b1 < 0) return null;

    if (/\bchild\s*\{/.test(code)) {
      const treeRoot = parseTikzChildTree(code);
      if (treeRoot) return renderTreeSpec(treeRoot);
    }

    const matMatch = code.match(/\\matrix\s*\([^)]*\)\s*\[[^\]]*matrix\s+of\s+(?:math\s+)?nodes[^\]]*\]\s*\{([\s\S]*?)\}\s*;/);
    if (matMatch) {
      const matRows = matMatch[1].split(/\\\\/).map((r) => r.trim()).filter(Boolean);
      const vt = tabularToVtSpec(matRows);
      if (vt) return renderVtSpec(vt);
    }

    let i0 = b0 + 19, pOpts = "";
    while (i0 < code.length && /\s/.test(code[i0])) i0++;
    if (code[i0] === "[") { const r = tkBal(code, i0); pOpts = r[0]; i0 = r[1]; }
    let body = code.slice(i0, b1);
    const scale = parseFloat((pOpts.match(/(?:^|[,\s])scale\s*=\s*([\d.]+)/) || [0, "1"])[1]) || 1;
    const globalArrowE = /(?:^|[,\s])->(?:$|[,\s\]])/.test(pOpts);
    let every = "";
    const ei = pOpts.indexOf("every node/.style=");
    if (ei >= 0) { const bi = pOpts.indexOf("{", ei); if (bi >= 0) every = tkBal(pOpts, bi)[0]; }

    let ax = null;
    const am = body.indexOf("\\begin{axis}");
    if (am >= 0) {
      let j = am + 12, ao = "";
      while (j < body.length && /\s/.test(body[j])) j++;
      if (body[j] === "[") { const r = tkBal(body, j); ao = r[0]; j = r[1]; }
      const ae = body.lastIndexOf("\\end{axis}");
      ax = tkAxisOpts(ao);
      body = body.slice(j, ae < 0 ? body.length : ae);
    }
    body = tkExpandForeach(body.replace(/\\(?:begin|end)\{(?:center|figure)\}/g, ""));
    if (ax) body = body.replace(/\\pgfkeysvalueof\{\/pgfplots\/(xmin|xmax|ymin|ymax)\}/g, (m0, k) => (ax[k] != null ? ax[k] : m0));

    const ctx = { names: {}, nodes: [], paths: [], clip: null, every, gridBounds: null };
    const clipStack = [];
    tkSplit(body, ";").forEach((raw) => {
      let s = raw.trim(), m;
      while ((m = s.match(/^\\(begin|end)\{scope\}\s*/))) {
        s = s.slice(m[0].length).trim();
        if (m[1] === "begin") { clipStack.push(ctx.clip); if (s[0] === "[") s = s.slice(tkBal(s, 0)[1]).trim(); }
        else ctx.clip = clipStack.pop() || null;
      }
      const cm = s.match(/^\\(draw|fill|filldraw|path|node|clip|coordinate|addplot\+?)\b\s*/);
      if (!cm) return;
      const cmd = cm[1];
      let rest = s.slice(cm[0].length).trim();
      if (cmd === "node" || cmd === "coordinate") { tkPath("node " + rest, tkStyle("", {}), ctx, cmd); return; }
      let opts = "";
      if (rest[0] === "[") { const r = tkBal(rest, 0); opts = r[0]; rest = rest.slice(r[1]).trim(); }
      if (cmd === "clip") {
        const mm = rest.match(/\(([^()]*)\)\s*rectangle\s*\(([^()]*)\)/);
        if (mm) {
          const a = tkParseCoord(mm[1], ctx.names), b = tkParseCoord(mm[2], ctx.names);
          if (a && b) ctx.clip = { x0: Math.min(a.x, b.x), y0: Math.min(a.y, b.y), x1: Math.max(a.x, b.x), y1: Math.max(a.y, b.y) };
        }
        return;
      }
      if (cmd.indexOf("addplot") === 0) { tkAddPlot(opts, rest, ctx, ax); return; }
      const st = tkStyle(opts, { arrowE: globalArrowE && cmd === "draw" });
      if (cmd === "fill" || cmd === "filldraw") {
        st.fill = st.fill || (st.colorSet ? st.stroke : "currentColor");
        if (cmd === "fill") st.draw = false;
      }
      tkPath(rest, st, ctx, cmd);
    });

    let T = (p) => ({ x: p.x, y: p.y });
    const deco = [];
    if (ax) {
      const dp = ctx.paths.filter((p) => p.plot).flatMap((p) => p.pts);
      let xmin = ax.xmin, xmax = ax.xmax, ymin = ax.ymin, ymax = ax.ymax;
      if (dp.length) {
        const xs = dp.map((p) => p.x), ys = dp.map((p) => p.y).sort((a, b) => a - b);
        const lo = ys[Math.floor(ys.length * 0.02)], hi = ys[Math.ceil(ys.length * 0.98) - 1], pd = (hi - lo) * 0.08 || 1;
        if (xmin == null) xmin = Math.min(...xs);
        if (xmax == null) xmax = Math.max(...xs);
        if (ymin == null) ymin = lo - pd;
        if (ymax == null) ymax = hi + pd;
      }
      xmin = xmin == null ? -5 : xmin; xmax = xmax == null ? 5 : xmax;
      ymin = ymin == null ? -5 : ymin; ymax = ymax == null ? 5 : ymax;
      if (xmax <= xmin) xmax = xmin + 1;
      if (ymax <= ymin) ymax = ymin + 1;
      const W = ax.width || 8.8, H = ax.height || 6.5, sx = W / (xmax - xmin), sy = H / (ymax - ymin);
      T = (p) => ({ x: (p.x - xmin) * sx, y: (p.y - ymin) * sy });
      ctx.paths.forEach((p) => { if (p.axisClip) p.clip = { x0: xmin, y0: ymin, x1: xmax, y1: ymax }; });
      const tx = (x) => (x - xmin) * sx, ty = (y) => (y - ymin) * sy;
      const mid = ax.lines === "middle" || ax.lines === "center";
      const cx = mid ? Math.min(Math.max(0, xmin), xmax) : xmin, cy = mid ? Math.min(Math.max(0, ymin), ymax) : ymin;
      const line = (x1, y1, x2, y2, base) =>
        deco.push({ st: tkStyle("", base), segs: [{ a: { x: x1, y: y1, r: 0 }, b: { x: x2, y: y2, r: 0 }, bend: 0 }], circles: [], grids: [], noT: true });
      const nice = (a, b) => {
        const raw = (b - a) / 8, mag = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / mag;
        const stp = (f < 1.5 ? 1 : f < 3.5 ? 2 : f < 7.5 ? 5 : 10) * mag, out = [];
        for (let v = Math.ceil(a / stp - 1e-9) * stp; v <= b + 1e-9; v += stp) out.push(+v.toFixed(10));
        return out;
      };
      const fmt = (v) => String(+v.toFixed(6)).replace(".", ",").replace("-", "−");
      const xt = nice(xmin, xmax), yt = nice(ymin, ymax);
      const deNode = (x, y, t, pos) => ctx.nodes.push({ cm: true, x, y, html: t, pos, fs: 12 });
      if (ax.grid) {
        xt.forEach((v) => line(tx(v), 0, tx(v), H, { stroke: "rgb(190,190,190)", width: 0.6 }));
        yt.forEach((v) => line(0, ty(v), W, ty(v), { stroke: "rgb(190,190,190)", width: 0.6 }));
      }
      if (mid) {
        line(0, ty(cy), W + 0.3, ty(cy), { arrowE: true, width: 1.4 });
        line(tx(cx), 0, tx(cx), H + 0.3, { arrowE: true, width: 1.4 });
      } else {
        line(0, 0, W, 0, {}); line(W, 0, W, H, {}); line(W, H, 0, H, {}); line(0, H, 0, 0, {});
      }
      xt.forEach((v) => {
        line(tx(v), ty(cy) - 0.07, tx(v), ty(cy) + 0.07, {});
        if (!(mid && Math.abs(v - cx) < 1e-9)) deNode(tx(v), ty(cy), fmt(v), "below");
      });
      yt.forEach((v) => {
        line(tx(cx) - 0.07, ty(v), tx(cx) + 0.07, ty(v), {});
        if (!(mid && Math.abs(v - cy) < 1e-9)) deNode(tx(cx), ty(v), fmt(v), "left");
      });
      if (ax.xlabel) deNode(W + 0.35, ty(cy), tkText(ax.xlabel), "right");
      if (ax.ylabel) deNode(tx(cx), H + 0.4, tkText(ax.ylabel), "above");
    }

    const seen = {};
    ctx.paths.forEach((P) => P.segs.forEach((e) => {
      if (e.a.n && e.b.n && e.a.n !== e.b.n && !e.bend && P.st.arrowE) seen[e.a.n + ">" + e.b.n] = e;
    }));
    Object.keys(seen).forEach((k) => { const ab = k.split(">"); if (seen[ab[1] + ">" + ab[0]]) seen[k].bend = 18; });

    const allP = deco.concat(ctx.paths);
    allP.forEach((P) => { const Tf = P.noT ? (p) => p : T; P.segs.forEach((e) => { e.g = tkGeom(e, Tf); }); P.g = P.segs.map((e) => e.g); });
    ctx.nodes = ctx.nodes.filter((nd) => nd.cm || nd.edge || nd.x !== undefined);

    let minx = 1e9, miny = 1e9, maxx = -1e9, maxy = -1e9;
    const bb = (p, mg) => { mg = mg || 0; minx = Math.min(minx, p.x - mg); maxx = Math.max(maxx, p.x + mg); miny = Math.min(miny, p.y - mg); maxy = Math.max(maxy, p.y + mg); };
    allP.forEach((P) => {
      const Tf = P.noT ? (p) => p : T;
      P.g.forEach((g) => { bb(g.p0); bb(g.p1); bb(tkCub(g, 0.5)); });
      P.circles.forEach((c) => bb(Tf(c.c), c.r));
      P.grids.forEach((g) => { bb(Tf(g.a)); bb(Tf(g.b)); });
    });
    ctx.nodes.forEach((nd) => {
      if (nd.edge && nd.edge.g) {
        const g = nd.edge.g, p = tkCub(g, nd.f), q = tkCub(g, Math.min(1, nd.f + 0.02)), r2 = tkCub(g, Math.max(0, nd.f - 0.02));
        nd.X = p.x; nd.Y = p.y;
        if (g.isLoop) {
          const ld = g.loopDir || "above";
          if (ld === "above") nd.Y += 0.25;
          else if (ld === "below") nd.Y -= 0.25;
          else if (ld === "left") nd.X -= 0.35;
          else if (ld === "right") nd.X += 0.35;
          nd.autoCenter = true;
        } else if (nd.auto) {
          const tx_ = q.x - r2.x, ty_ = q.y - r2.y, l = Math.hypot(tx_, ty_) || 1, sg = nd.swap ? -1 : 1;
          nd.X += (-ty_ / l) * 0.32 * sg; nd.Y += (tx_ / l) * 0.32 * sg;
          nd.autoCenter = true;
        }
      } else { const q = nd.cm ? nd : T(nd); nd.X = q.x; nd.Y = q.y; }
      bb({ x: nd.X, y: nd.Y }, 0.45);
    });
    if (!isFinite(minx)) return null;

    const spanX = Math.max(0.5, maxx - minx);
    const spanY = Math.max(0.5, maxy - miny);
    let U = 42 * scale;
    const pad = 34;
    if (spanX * U + 2 * pad > 900) U = (900 - 2 * pad) / spanX;
    if (spanY * U + 2 * pad > 680) U = Math.min(U, (680 - 2 * pad) / spanY);
    const PW = Math.max(120, Math.ceil(spanX * U + 2 * pad));
    const PH = Math.max(80, Math.ceil(spanY * U + 2 * pad));
    const X = (x) => ((x - minx) * U + pad).toFixed(1), Y = (y) => ((maxy - y) * U + pad).toFixed(1);
    const f2 = (p) => `${X(p.x)},${Y(p.y)}`;
    const dOf = (gs) => {
      let d = "", le = null;
      gs.forEach((g) => {
        if (!le || Math.hypot(le.x - g.p0.x, le.y - g.p0.y) > 1e-6) d += `M${f2(g.p0)}`;
        d += g.line ? `L${f2(g.p1)}` : `C${f2(g.c1)} ${f2(g.c2)} ${f2(g.p1)}`;
        le = g.p1;
      });
      return d;
    };

    const uid = ++__tkUid;
    let defs = "", svg = "", html = "", nMk = 0, nClip = 0;
    const markers = {}, clips = new Map();
    const marker = (col) => {
      if (!markers[col]) {
        markers[col] = `tkm${uid}_${nMk++}`;
        defs += `<marker id="${markers[col]}" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="8.5" markerHeight="8.5" markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M0,0.5 L9.5,5 L0,9.5 z" fill="${col}"/></marker>`;
      }
      return markers[col];
    };
    const clipId = (c) => {
      const key = `${c.x0}_${c.y0}_${c.x1}_${c.y1}`;
      if (!clips.has(key)) {
        const id = `tkc${uid}_${nClip++}`, a = T({ x: c.x0, y: c.y0 }), b = T({ x: c.x1, y: c.y1 });
        defs += `<clipPath id="${id}"><rect x="${X(Math.min(a.x, b.x))}" y="${Y(Math.max(a.y, b.y))}" width="${Math.abs(b.x - a.x) * U}" height="${Math.abs(b.y - a.y) * U}"/></clipPath>`;
        clips.set(key, id);
      }
      return clips.get(key);
    };

    const interactivePts = [];
    allP.forEach((P) => {
      const Tf = P.noT ? (p) => p : T, s = P.st;
      if ((P.isPlot || P.plot) && P.pts && P.pts.length > 2) {
        P.pts.forEach((pt) => {
          const tp = Tf(pt);
          const px = +X(tp.x), py = +Y(tp.y);
          if (px >= 0 && px <= PW && py >= 0 && py <= PH) {
            interactivePts.push([+pt.x.toFixed(3), +pt.y.toFixed(3), px, py]);
          }
        });
      }
      P.grids.forEach((gr) => {
        const a = Tf(gr.a), b = Tf(gr.b), sxp = s.xstep || s.step || 1, syp = s.ystep || s.step || 1;
        const x0 = Math.min(a.x, b.x), x1 = Math.max(a.x, b.x), y0 = Math.min(a.y, b.y), y1 = Math.max(a.y, b.y);
        const gs = `stroke="${s.stroke}" stroke-width="${s.width * 0.8}" opacity="0.85"`;
        for (let x = Math.ceil(x0 / sxp - 1e-9) * sxp; x <= x1 + 1e-9; x += sxp) svg += `<line x1="${X(x)}" y1="${Y(y0)}" x2="${X(x)}" y2="${Y(y1)}" ${gs}/>`;
        for (let y = Math.ceil(y0 / syp - 1e-9) * syp; y <= y1 + 1e-9; y += syp) svg += `<line x1="${X(x0)}" y1="${Y(y)}" x2="${X(x1)}" y2="${Y(y)}" ${gs}/>`;
      });
      const clipA = P.clip ? ` clip-path="url(#${clipId(P.clip)})"` : "";
      const stroke = s.draw === false ? "none" : s.stroke;
      const dash = s.dash ? ` stroke-dasharray="${s.dash}"` : "";
      if (P.g.length) {
        const nodeEnds = P.segs.some((e) => e.a.r || e.b.r || e.loopDir);
        const me = s.arrowE ? ` marker-end="url(#${marker(s.stroke)})"` : "", ms = s.arrowS ? ` marker-start="url(#${marker(s.stroke)})"` : "";
        const parts = nodeEnds && (s.arrowE || s.arrowS) && !P.closed ? P.g.map((g) => dOf([g])) : [dOf(P.g) + (P.closed ? "Z" : "")];
        parts.forEach((d) => {
          svg += `<path d="${d}" fill="${s.fill || "none"}" fill-opacity="${s.fillOp}" stroke="${stroke}" stroke-width="${s.width}"${dash} stroke-linejoin="round" stroke-linecap="round"${me}${ms}${clipA}/>`;
        });
      }
      P.circles.forEach((c) => {
        const q = Tf(c.c);
        const rPx = Math.max(3.5, c.r * U);
        svg += `<circle cx="${X(q.x)}" cy="${Y(q.y)}" r="${rPx.toFixed(1)}" fill="${s.fill || "none"}" stroke="${stroke}" stroke-width="${s.width}"${dash}${clipA}/>`;
      });
    });

    const fsMap = { tiny: 10, scriptsize: 10.5, footnotesize: 11.5, small: 12.5, large: 15.5, Large: 17.5 };
    ctx.nodes.forEach((nd) => {
      if (nd.invisible) return;
      const so = nd.cm ? "" : (ctx.every ? ctx.every + "," : "") + (nd.opts || "");
      const posS = nd.cm ? nd.pos : nd.opts || "";
      const has = (w) => new RegExp("(^|[\\s,])" + w + "([\\s,=]|$)").test(posS);
      const ab = has("above"), be = has("below"), le = has("left"), ri = has("right");
      const px_ = nd.autoCenter ? -50 : ri ? 0 : le ? -100 : -50, py_ = nd.autoCenter ? -50 : ab ? -100 : be ? 0 : -50;
      const dx = nd.autoCenter ? 0 : ri ? 6 : le ? -6 : 0, dy = nd.autoCenter ? 0 : ab ? -5 : be ? 5 : 0;
      const ns = tkStyle(so, {});
      const draw = /(^|[\s,])draw([\s,]|$)/.test(so), circ = /(^|[\s,])circle([\s,]|$)/.test(so);
      const mn = tkLen((so.match(/minimum size\s*=\s*([\d.]+\s*[a-z]*)/) || [])[1]);
      let box = "";
let stuCls = "";
      if (draw) {
        box = `border:${Math.max(1.4, ns.width)}px solid ${ns.stroke};background:var(--bg-elevated,#ffffff);font-weight:600;box-shadow:0 2px 6px rgba(0,0,0,0.08);`;
        if (circ) { const d = (isNaN(mn) ? 0.78 : mn) * U; box += `border-radius:50%;width:${d}px;height:${d}px;display:flex;align-items:center;justify-content:center;`; }
        else box += "border-radius:6px;padding:3px 8px;";
      } else if (nd.edge) {
        stuCls = "nh-student-hide";
      }
      if (ns.fill && !nd.cm) box += `background:${ns.fill};`;
      const fm = so.match(/\\?(tiny|scriptsize|footnotesize|small|large|Large)\b/);
      const fsz = nd.fs || (fm ? fsMap[fm[1]] : 13.5);
      let colr = "";
      if (ns.fill && !nd.cm) {
        const contrast = tkContrastTextColor(ns.fill);
        if (contrast) colr = `color:${contrast};`;
      } else if (ns.colorSet && !nd.cm && !draw) {
        colr = `color:${ns.stroke};`;
      } else if (nd.inheritedColor && !draw) {
        colr = `color:${nd.inheritedColor};`;
      } else if (draw) {
        colr = "color:var(--text-primary);";
      }
      html += `<div class="${stuCls}" style="position:absolute;left:${X(nd.X)}px;top:${Y(nd.Y)}px;transform:translate(calc(${px_}% + ${dx}px),calc(${py_}% + ${dy}px));white-space:nowrap;font-size:${fsz}px;line-height:1.2;${box}${colr}">${nd.cm ? nd.html : tkText(nd.text)}</div>`;
    });

    const o0 = T({ x: 0, y: 0 });
    const oxPx = +X(o0.x), oyPx = +Y(o0.y);
    const hasCurve = interactivePts.length > 3;
    const hasEdgeWeights = ctx.nodes.some((nd) => nd.edge && !nd.invisible);
    const curveAttr = hasCurve
      ? ` class="nh-curve-stage" data-ox="${oxPx}" data-oy="${oyPx}" data-pts='${JSON.stringify(interactivePts)}'`
      : ` class="nh-curve-stage"`;
    const hudHtml = hasCurve
      ? `<div class="nh-curve-hud" style="display:none;pointer-events:none;">` +
        `<div class="nh-curve-vline"></div><div class="nh-curve-hline"></div>` +
        `<div class="nh-curve-xbadge mono"></div><div class="nh-curve-ybadge mono"></div>` +
        `<div class="nh-curve-dot"></div>` +
        `</div>`
      : "";

    const inner =
      `<div class="nh-math-figure-card">` +
      `<div${curveAttr} style="position:relative;width:${PW}px;height:${PH}px;margin:0 auto;">` +
      `<svg width="${PW}" height="${PH}" viewBox="0 0 ${PW} ${PH}" style="position:absolute;inset:0;overflow:visible;" aria-hidden="true"><defs>${defs}</defs>${svg}</svg>${html}${hudHtml}` +
      `</div></div>`;
    return nhWrapMathFigure(inner, {
      hasStudentMode: hasEdgeWeights,
      oracle: hasCurve ? { ok: true, label: "✓ Courbe interactive (survoler)", detail: "Passez la souris sur la courbe pour lire x, f(x) et f'(x)." } : null,
    });
  }

// ---------- Écouteurs globaux : Copie Code TeX/TikZ, Mode Élève, Export PNG HD & Pointeur Magnétique ----------
  if (typeof document !== "undefined") document.addEventListener("click", function (ev) {
    const tikzBtn = ev.target.closest(".nh-copy-tikz-btn, .copy-latex-btn");
    if (tikzBtn) {
      ev.preventDefault();
      ev.stopPropagation();
      tikzBtn.blur();
      const wrap = tikzBtn.closest(".nh-tikz-code-window, .nh-tikz-details, .latex-editorial-frame");
      const codeEl = wrap ? wrap.querySelector("pre code, code") : null;
      const rawTex = codeEl ? codeEl.textContent : (wrap ? wrap.innerText : "");
      if (!rawTex || !navigator.clipboard) return;
      navigator.clipboard.writeText(rawTex.trim()).then(() => {
        const orig = tikzBtn.innerHTML;
        tikzBtn.innerHTML = `${ICONS.check} <span>Copié !</span>`;
        tikzBtn.classList.add("copied");
        setTimeout(() => {
          tikzBtn.innerHTML = orig;
          tikzBtn.classList.remove("copied");
        }, 1600);
      });
      return;
    }

    const stuBtn = ev.target.closest(".nh-btn-student-mode");
    if (stuBtn) {
      ev.preventDefault();
      stuBtn.blur();
      const fig = stuBtn.closest(".nh-math-fig");
      if (!fig) return;
      const isStu = fig.classList.toggle("is-student-mode");
      stuBtn.classList.toggle("active", isStu);
      stuBtn.innerHTML = isStu
        ? `${NH_SVG_PROF} <span>Mode Prof</span>`
        : `${NH_SVG_STUDENT} <span>Mode Élève</span>`;
      return;
    }

    const pngBtn = ev.target.closest(".nh-btn-copy-png");
    if (pngBtn) {
      ev.preventDefault();
      const fig = pngBtn.closest(".nh-math-fig");
      const target = fig ? fig.querySelector(".nh-fig-export-target") : null;
      nhCopyElementAsPng(target, pngBtn);
      return;
    }
  });

document.addEventListener("mousemove", function (ev) {
    const stage = ev.target.closest(".nh-curve-stage");
    if (!stage) return;
    const hud = stage.querySelector(".nh-curve-hud");
    if (!hud) return;
    if (!stage._pts) {
      try { stage._pts = JSON.parse(stage.getAttribute("data-pts") || "[]"); } catch (_) { stage._pts = []; }
    }
    const pts = stage._pts;
    if (!pts.length) return;
    const rect = stage.getBoundingClientRect();
    const mx = ev.clientX - rect.left;
    let bestIdx = 0, bestDist = 1e9;
    for (let i = 0; i < pts.length; i++) {
      const d = Math.abs(pts[i][2] - mx);
      if (d < bestDist) { bestDist = d; bestIdx = i; }
    }
    const figWrap = stage.closest(".nh-math-fig");
    const oracleEl = figWrap ? figWrap.querySelector(".nh-fig-oracle") : null;
    if (bestDist > 46) {
      hud.style.display = "none";
      if (oracleEl && oracleEl._origHtml) {
        oracleEl.innerHTML = oracleEl._origHtml;
        oracleEl.classList.remove("live-hud");
      }
      return;
    }

    let [xMath, yMath, px, py] = pts[bestIdx];
    const i0 = Math.max(0, bestIdx - 1), i1 = Math.min(pts.length - 1, bestIdx + 1);
    const dx = pts[i1][0] - pts[i0][0];
    let slopeVal = Math.abs(dx) > 1e-5 ? (pts[i1][1] - pts[i0][1]) / dx : 0;

    // Aimantation douce sur les points remarquables (entiers, racines, extremums locaux)
    let isRemarkable = false;
    if (Math.abs(xMath - Math.round(xMath)) < 0.045) {
      xMath = Math.round(xMath);
      if (Math.abs(yMath - Math.round(yMath)) < 0.08) {
        yMath = Math.round(yMath);
        isRemarkable = true;
      }
    }
    if (Math.abs(slopeVal) < 0.08) {
      slopeVal = 0;
      isRemarkable = true;
    } else if (Math.abs(yMath) < 0.05) {
      yMath = 0;
      isRemarkable = true;
    }

    const ox = parseFloat(stage.getAttribute("data-ox")) || 0;
    const oy = parseFloat(stage.getAttribute("data-oy")) || 0;
    const vline = hud.querySelector(".nh-curve-vline");
    const hline = hud.querySelector(".nh-curve-hline");
    const dot = hud.querySelector(".nh-curve-dot");
    const xbadge = hud.querySelector(".nh-curve-xbadge");
    const ybadge = hud.querySelector(".nh-curve-ybadge");

    hud.style.display = "block";
    if (vline) {
      vline.style.left = `${px}px`;
      vline.style.top = `${Math.min(py, oy)}px`;
      vline.style.height = `${Math.abs(oy - py)}px`;
    }
    if (hline) {
      hline.style.left = `${Math.min(px, ox)}px`;
      hline.style.top = `${py}px`;
      hline.style.width = `${Math.abs(ox - px)}px`;
    }
    if (dot) {
      dot.style.left = `${px}px`;
      dot.style.top = `${py}px`;
      dot.classList.toggle("remarkable", isRemarkable);
    }

    const fx = (Math.abs(xMath) < 1e-4 ? 0 : xMath).toFixed(2).replace(".", ",");
    const fy = (Math.abs(yMath) < 1e-4 ? 0 : yMath).toFixed(2).replace(".", ",");
    const fm = (Math.abs(slopeVal) < 1e-4 ? 0 : slopeVal).toFixed(2).replace(".", ",");

    // 1. Micro-pastilles projetées directement sur les axes x et y
    if (xbadge) {
      xbadge.textContent = fx;
      xbadge.style.left = `${px}px`;
      xbadge.style.top = `${oy + (py <= oy ? 13 : -13)}px`;
    }
    if (ybadge) {
      ybadge.textContent = fy;
      ybadge.style.left = `${ox + (px >= ox ? -8 : 8)}px`;
      ybadge.style.top = `${py}px`;
      ybadge.style.transform = px >= ox ? "translate(-100%, -50%)" : "translate(0%, -50%)";
    }

    // 2. Affichage complet dans le bandeau HUD fixe en haut (0 chevauchement sur la courbe)
    if (oracleEl) {
      if (!oracleEl._origHtml) oracleEl._origHtml = oracleEl.innerHTML;
      oracleEl.classList.add("live-hud");
      const tag = Math.abs(slopeVal) < 0.01 ? ' <span class="nh-hud-tag">Extremum</span>' : "";
      oracleEl.innerHTML = `<span class="mono">x = <strong>${fx}</strong> &nbsp;│&nbsp; f(x) = <strong>${fy}</strong> &nbsp;│&nbsp; f'(x) ≈ ${fm}</span>${tag}`;
    }
  });

  document.addEventListener("mouseout", function (ev) {
    const stage = ev.target.closest(".nh-curve-stage");
    if (!stage) return;
    if (!stage.contains(ev.relatedTarget)) {
      const hud = stage.querySelector(".nh-curve-hud");
      if (hud) hud.style.display = "none";
      const figWrap = stage.closest(".nh-math-fig");
      const oracleEl = figWrap ? figWrap.querySelector(".nh-fig-oracle") : null;
      if (oracleEl && oracleEl._origHtml) {
        oracleEl.innerHTML = oracleEl._origHtml;
        oracleEl.classList.remove("live-hud");
      }
    }
  });

  // ---------- Aiguillage ----------
  function renderSpecialBlock(lang, code) {
    const lg = String(lang || "").trim().toLowerCase(), c = String(code || "");
    try {
      if (/\\begin\{tikzpicture\}/.test(c)) {
        const h = tikzToHtml(c);
        return h
          ? h +
              `<details class="nh-tikz-details">` +
              `<summary><span>▸ Code TikZ</span></summary>` +
              `<div class="nh-tikz-code-window">` +
              `<div class="nh-tikz-code-bar">` +
              `<span class="mono">LaTeX / TikZ</span>` +
              `<button type="button" class="nh-copy-tikz-btn" title="Copier le code TikZ">${ICONS.copy} <span>Copier le code TikZ</span></button>` +
              `</div>` +
              `<pre><code>${esc(c)}</code></pre>` +
              `</div>` +
              `</details>`
          : null;
      }
      if (["droite", "intervalle", "intervalles", "axe"].includes(lg) || (/^\s*(?:bornes|axe)\s*:/im.test(c) && /\[[^;\]]+;\s*[^\]]+\]/.test(c))) {
        const nl = parseNumberLineSpec(c);
        if (nl) return renderNumberLineSpec(nl);
      }
      if (lg === "arbre" || lg === "tree" || /^\s*Niveau_?\d/im.test(c)) {
        const t = parseTreeSpec(c);
        return t ? renderTreeSpec(t) : null;
      }
      const plain = ["", "text", "txt", "plaintext"].includes(lg);
      if (["tableau", "variations", "signes", "tvar", "convexite"].includes(lg) || (plain && /^\s*\$?x\$?\s*:/im.test(c))) {
        const sp = parseVtSpec(c);
        if (!sp) return null;
        return renderVtSpec(sp);
      }
    } catch (_) {}
    return null;
  }

  function formatAssistantContent(raw, isInnerLatex = false) {
    if (!raw) return "<em style='color:var(--text-secondary);'>Aucune sortie texte.</em>";

    // Détection du cadre LaTeX (calculée sur le texte d'origine, avant nettoyage)
    const hasLatexMarkup =
      !isInnerLatex &&
      /\\(?:textbf|textit|partie|section|subsection|begin\{(?:enumerate|itemize|document|tabular)\}|item|frac)/.test(raw);

    // Nettoyage du LaTeX brut (TikZ, center, enumerate, exo, partie...)
    raw = sanitizeRawLatexForChat(raw);

    const codeBlocks = [];
    const mathBlocks = [];
    const inlineMathTokens = [];

let working = String(raw).replace(/```([a-zA-Z0-9_+-]*)[ \t]*\r?\n([\s\S]*?)```/g, function (_, lang, code) {
      const token = `\n@@CODEBLOCK_${codeBlocks.length}@@\n`;
      const sp = renderSpecialBlock(lang, code);
      const isTex = /^(latex|tex)$/i.test(lang) || /\\documentclass|\\begin\{document\}/.test(code);
      const langLabel = isTex ? "Code LaTeX / TeX" : lang ? lang.toUpperCase() : "Code";
      const codeWin =
        `<div class="nh-tikz-code-window" style="margin:12px 0;">` +
        `<div class="nh-tikz-code-bar">` +
        `<span class="mono">${esc(langLabel)}</span>` +
        `<button type="button" class="nh-copy-tikz-btn" title="Copier le code">${ICONS.copy} <span>Copier le code</span></button>` +
        `</div>` +
        `<pre><code class="lang-${esc(lang)}">${esc(code)}</code></pre>` +
        `</div>`;
      codeBlocks.push(sp || codeWin);
      return token;
    });

// Tableaux Markdown à barres "| ... |" (variations, signes, statistiques, valeurs, lois de probabilité)
    working = working.replace(/(?:^[ \t]*\|.*\|[ \t]*(?:\r?\n(?:[ \t]*\r?\n)?|$)){2,}/gm, function (blk) {
      let h = null;
      try {
        h = mdPipeTableToHtml(blk);
      } catch (_e) {
        h = null;
      }
      if (!h) return blk + "\n";
      const token = `\n@@CODEBLOCK_${codeBlocks.length}@@\n`;
      codeBlocks.push(h);
      return token;
    });

    // Conversion des \begin{tabular}...\end{tabular} en tableau de variations/signes ou tableau HTML
    working = working.replace(
      /\\begin\{tabular\}\{[^}]*\}([\s\S]*?)\\end\{tabular\}/g,
      function (_, inner) {
        const rows = inner
          .replace(/\\(?:hline|cline\{[^}]*\})/g, "")
          .split(/\\\\/)
          .map((r) => r.trim())
          .filter((r) => r.length > 0);
        try {
          const vt = tabularToVtSpec(rows);
          if (vt) {
            const vtHtml = renderVtSpec(vt);
            if (vtHtml) {
              const token = `\n@@CODEBLOCK_${codeBlocks.length}@@\n`;
              codeBlocks.push(vtHtml);
              return token;
            }
          }
        } catch (_e) {}
        function renderCell(txt) {
          const t = String(txt).trim();
          if (!t) return "&nbsp;";
          return t
            .split("$")
            .map((seg, i) => {
              if (i % 2 === 1) return renderMathExpression(seg, false);
              return esc(seg.replace(/\\\\/g, "").replace(/\\textbf\{([^}]*)\}/g, "$1"));
            })
            .join("");
        }
        const cellStyle =
          "border:1px solid var(--border-color, #cbd5e1); padding:6px 12px; text-align:center; min-width:42px;";
        const html =
          '<div style="overflow-x:auto; margin:12px 0;"><table style="border-collapse:collapse; margin:0 auto;"><tbody>' +
          rows
            .map(
              (r) =>
                "<tr>" +
                r
                  .split("&")
                  .map((c) => `<td style="${cellStyle}">${renderCell(c)}</td>`)
                  .join("") +
                "</tr>"
            )
            .join("") +
          "</tbody></table></div>";
        const token = `\n@@CODEBLOCK_${codeBlocks.length}@@\n`;
        codeBlocks.push(html);
        return token;
      }
    );

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
        const itemNum = parseInt(olMatch[2], 10) || 1;
        const itemText = olMatch[3];
        if (currentListType === "ul") {
          closeList();
        }
        if (!currentListType) {
          htmlParts.push(`<ol start="${itemNum}">`);
          currentListType = "ol";
        }
        htmlParts.push(`<li value="${itemNum}">${formatInlineMarkdown(itemText, inlineMathTokens)}</li>`);
        continue;
      }

      closeList();
      htmlParts.push(`<p>${formatInlineMarkdown(line, inlineMathTokens)}</p>`);
    }

    closeList();
    const finalHtml = htmlParts.join("");
    if (hasLatexMarkup) {
      return `
        <div class="latex-editorial-frame">
          <div class="latex-frame-header">
            <div class="latex-frame-title">
              <span class="latex-frame-badge">TeX</span>
              <span>Document &amp; Exercice LaTeX</span>
            </div>
            <div class="latex-frame-meta">
              <span class="meta-chip accent">Tectonic certifié</span>
              <button class="icon-btn-mini copy-latex-btn" data-copy-msg-raw="1" title="Copier le code LaTeX source">${ICONS.copy}</button>
            </div>
          </div>
          <div class="latex-frame-content">
            ${finalHtml}
          </div>
        </div>
      `;
    }
    return finalHtml;
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
    const isHighRisk =
      item.allow_session_approval === false ||
      ["HIGH", "DESTRUCTIVE", "CRITICAL", "BLOCKED"].includes(String(item.risk_label || item.risk_level || "").toUpperCase());
    const titleText = isHighRisk
      ? "ACTION À RISQUE"
      : "AUTORISATION NÉCESSAIRE";
    const actionDesc = item.human_description || item.message || `Exécuter ${item.tool}`;
    const toolCat = item.category || item.tool || "Computer Use";
    const riskLabel = item.risk_label_fr || item.risk_level || "Moyen";

    container.innerHTML = `
      <div class="approval-banner" role="alert">
        <div style="display:flex; align-items:flex-start; gap:10px;">
          <span style="color:var(--warning); margin-top:2px;">${ICONS.alert}</span>
          <div>
            <strong>${esc(titleText)}</strong>
            <div style="font-size: 12.5px; margin-top: 2px;">
              NeoHarness souhaite effectuer : <strong>${esc(actionDesc)}</strong>
            </div>
            <div style="font-size: 11.5px; opacity: 0.85; margin-top: 2px;">
              Outil : ${esc(toolCat)} · Risque : ${esc(riskLabel)}
            </div>
          </div>
        </div>
        <div class="approval-actions">
          <button class="btn-deny" data-approve-id="${esc(item.id)}" data-decision="deny">Refuser</button>
          <button class="btn-approve" data-approve-id="${esc(item.id)}" data-decision="allow_once">${isHighRisk ? "Autoriser une fois" : "Autoriser"}</button>
          ${
            !isHighRisk
              ? `<button class="btn-approve" data-approve-id="${esc(item.id)}" data-decision="allow_task">Autoriser pour cette session</button>`
              : ""
          }
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
          .map((f) => renderAttachmentBadgeHtml(f, true))
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

const currentExecMode =
      state.executionMode === "deepsearch"
        ? "deepsearch"
        : (s.execution && s.execution.mode) || state.executionMode || (state.deepReflection ? "multi" : "mono");
    const isMulti = currentExecMode === "multi";
    const isChat = currentExecMode === "chat";
    const isDeepSearch = currentExecMode === "deepsearch";
    state.executionMode = currentExecMode;
    state.deepReflection = isMulti;

    const syncDeepSearchUI = (modeVal) => {
      const pill = document.getElementById("composer-model-pill-label");
      if (pill) {
        if (modeVal === "chat") pill.textContent = "NeoHarness Swift";
        else if (modeVal === "multi") pill.textContent = "NeoHarness Deep";
        else if (modeVal === "deepsearch") pill.textContent = "NeoDeepSearch";
        else pill.textContent = "NeoHarness Core";
      }
      document.querySelectorAll(".model-popover-item[data-exec-mode]").forEach((it) => {
        const m = it.getAttribute("data-exec-mode");
        const match = m === modeVal;
        it.classList.toggle("active", match);
        const chk = it.querySelector(".popover-check");
        if (chk) chk.style.display = match ? "inline" : "none";
      });
      const dsToggle = document.getElementById("btn-neodeepsearch-toggle");
      if (dsToggle) {
        dsToggle.classList.toggle("active", modeVal === "deepsearch");
        dsToggle.setAttribute("aria-pressed", modeVal === "deepsearch" ? "true" : "false");
      }
    };

    syncDeepSearchUI(currentExecMode);

    document.querySelectorAll(".model-popover-item[data-exec-mode]").forEach((item) => {
      if (!item._dsBound) {
        item._dsBound = true;
        item.addEventListener("click", () => {
          const chosen = item.getAttribute("data-exec-mode") || "mono";
          state.executionMode = chosen;
          state.deepReflection = chosen === "multi";
          setTimeout(() => syncDeepSearchUI(chosen), 10);
        });
      }
    });

    const dsBtn = document.getElementById("btn-neodeepsearch-toggle");
    if (dsBtn && !dsBtn._bound) {
      dsBtn._bound = true;
      dsBtn.addEventListener("click", async () => {
        const nextMode = state.executionMode === "deepsearch" ? "mono" : "deepsearch";
        state.executionMode = nextMode;
        state.deepReflection = false;
        syncDeepSearchUI(nextMode);
        try {
          await apiPost("/api/execution/mode", { mode: nextMode });
        } catch (_) {}
      });
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
        chipLabel.textContent = s.mode.current;
      }
      const badgeLabel = document.getElementById("governance-badge-label");
      if (badgeLabel) {
        badgeLabel.textContent = `Gouvernance : ${s.mode.current}`;
      }
      document.querySelectorAll(".gov-option-item[data-gov-mode]").forEach((opt) => {
        const m = opt.getAttribute("data-gov-mode");
        const match = m === s.mode.current;
        opt.classList.toggle("active", match);
        const chk = opt.querySelector(".gov-check");
        if (chk) chk.style.display = match ? "inline" : "none";
      });
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
      host.innerHTML = `<img src="${url}" alt="${esc(doc.path)}" class="nh-doc-edge-img" />`;
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
      xlsx: "Excel · Tableur",
      pptx: "PowerPoint · Diaporama",
      ppt: "PowerPoint · Diaporama",
      xls: "Excel · Tableur",
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

    // Sélecteur de versions & restauration 1-clic (UniversalArtifactEngine)
    const actionsBar = document.querySelector(".doc-preview-actions");
    if (actionsBar) {
      let verSel = document.getElementById("doc-version-select");
      if (!verSel) {
        verSel = document.createElement("select");
        verSel.id = "doc-version-select";
        verSel.className = "nh-doc-version-select mono";
        verSel.title = "Historique des versions de ce document (cliquer pour restaurer une version)";
        actionsBar.insertBefore(verSel, actionsBar.firstChild);
        verSel.addEventListener("change", async () => {
          const d = state.activeDocument;
          const vId = parseInt(verSel.value, 10);
          if (!d || !vId) return;
          const targetPath = d.source_tex || d.path;
          try {
            await apiPost("/api/artifacts/rollback", { path: targetPath, version_id: vId });
            if (d.type === "pdf" && d.source_tex) {
              await compileLatexAndPreview(d.source_tex);
            } else {
              await openDocumentPreview({ type: d.type, path: d.path, source_tex: d.source_tex, viewMode: d.viewMode });
            }
            showStatusBanner(`Version v${vId} restaurée avec succès.`, "success");
          } catch (err) {
            showStatusBanner(`Restauration impossible : ${err.message}`, "error");
          }
        });
      }
      const histPath = doc.source_tex || doc.path;
      apiGet(`/api/artifacts/history?path=${encodeURIComponent(histPath)}`)
        .then((res) => {
          const hist = (res && res.history) || [];
          if (hist.length <= 1) {
            verSel.style.display = "none";
          } else {
            verSel.style.display = "inline-flex";
            verSel.innerHTML = hist
              .slice()
              .reverse()
              .map((v, i) => `<option value="${v.version_id}" ${i === 0 ? "selected" : ""}>v${v.version_id}${i === 0 ? " (actuelle)" : " ↺"}</option>`)
              .join("");
          }
        })
        .catch(() => {
          verSel.style.display = "none";
        });
    }

    const btnDlWord = document.getElementById("btn-doc-download-word");
    const btnDlPdf = document.getElementById("btn-doc-download-pdf");
    const btnDlExcel = document.getElementById("btn-doc-download-excel");
    const btnDlPptx = document.getElementById("btn-doc-download-pptx");
    if (btnDlPptx) {
      if (doc.type === "pptx" || doc.type === "ppt") {
        btnDlPptx.style.display = "inline-flex";
        btnDlPptx.href = `/api/files/raw?path=${encodeURIComponent(doc.path)}&download=1`;
      } else {
        btnDlPptx.style.display = "none";
      }
    }
    const stem = doc.path.replace(/\.(docx|pdf|xlsx)$/i, "");
    const companionDocx = doc.companionDocx || `${stem}.docx`;
    const companionPdf = doc.companionPdf || `${stem}.pdf`;

    if (btnDlExcel) {
      if (doc.type === "xlsx" || doc.type === "xls") {
        btnDlExcel.style.display = "inline-flex";
        btnDlExcel.href = `/api/files/raw?path=${encodeURIComponent(doc.path)}&download=1`;
      } else {
        btnDlExcel.style.display = "none";
      }
    }

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

    const btnDiff = document.getElementById("btn-doc-view-diff");
    const btnCanvasAi = document.getElementById("btn-doc-canvas-ai");
    const diffViewer = document.getElementById("doc-diff-viewer");
    if (btnDiff) {
      btnDiff.classList.toggle("active", doc.viewMode === "diff");
      btnDiff.style.display = doc.type === "image" ? "none" : "inline-block";
    }
    if (btnCanvasAi) {
      btnCanvasAi.style.display = doc.type === "image" ? "none" : "inline-block";
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
      diffViewer,
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

    if (doc.viewMode === "diff" && diffViewer) {
      diffViewer.style.display = "block";
      const diffTarget = doc.source_tex || doc.path;
      diffViewer.innerHTML = `<div class="diff-summary-card"><span>Chargement du comparateur de versions pour <strong>${esc(diffTarget)}</strong>…</span></div>`;
      try {
        const diffData = await apiGet(`/api/artifacts/diff?path=${encodeURIComponent(diffTarget)}`);
        const lines = diffData.diff_lines || [];
        const hist = diffData.history || [];
        const linesHtml = lines.length
          ? lines
              .map((ln) => {
                const cls =
                  ln.type === "add"
                    ? "diff-line diff-line-add"
                    : ln.type === "del"
                    ? "diff-line diff-line-del"
                    : ln.type === "hdr"
                    ? "diff-line diff-line-hdr"
                    : "diff-line";
                return `<div class="${cls}">${esc(ln.text)}</div>`;
              })
              .join("")
          : `<div class="diff-line" style="color:var(--text-muted); padding:14px;">Aucune modification différentielle enregistrée sur cette session pour ${esc(diffTarget)}. Utilisez <strong>✨ Éditer IA</strong> ou modifiez le code source pour voir le diff en direct.</div>`;
        diffViewer.innerHTML = `
          <div class="diff-summary-card">
            <div>
              <strong>Comparateur de versions · ${esc(diffTarget)}</strong>
              <span style="margin-left:10px; font-size:12px; color:var(--text-muted);">${hist.length} version(s) tracée(s)</span>
            </div>
            <div>
              <span class="diff-stat-add">+${diffData.added_lines || 0} ajout(s)</span>
              <span class="diff-stat-del">-${diffData.removed_lines || 0} suppression(s)</span>
            </div>
          </div>
          <div class="diff-code-box">${linesHtml}</div>
        `;
      } catch (err) {
        diffViewer.innerHTML = `<div class="diff-summary-card"><span>Erreur lors du chargement du diff : ${esc(err.message)}</span></div>`;
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
    } else if ((doc.type === "docx" || doc.type === "html" || doc.type === "xlsx" || doc.type === "xls" || doc.type === "pptx" || doc.type === "ppt") && htmlFrame) {
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
    state.inspectorTab = "activity";
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
    state.inspectorTab = "activity";
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

      const pillLabel = document.getElementById("composer-model-pill-label");
      if (pillLabel) {
        if (isChat) pillLabel.textContent = "NeoHarness Swift";
        else if (isMulti) pillLabel.textContent = "NeoHarness Deep";
        else pillLabel.textContent = "NeoHarness Core";
      }
      document.querySelectorAll(".model-popover-item[data-exec-mode]").forEach((item) => {
        const m = item.getAttribute("data-exec-mode");
        const match = m === mode;
        item.classList.toggle("active", match);
        const chk = item.querySelector(".popover-check");
        if (chk) chk.style.display = match ? "inline" : "none";
      });

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
      case "activity":
        body.innerHTML = renderInspectorActivityTab();
        break;
      case "details":
        body.innerHTML = renderInspectorDetailsTab();
        break;
      case "library":
      case "document":
        renderInspectorLibraryTab();
        break;
      case "model":
        body.innerHTML = renderInspectorModelTab();
        break;
      case "skills":
        body.innerHTML = renderInspectorSkillsTab();
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
        body.innerHTML = renderInspectorActivityTab();
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
            ${ICONS.clock}
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
    const s = state.appState || {};
    const activeConv = s.active_conversation || {};
    const convMsgs = activeConv.messages || [];

    // Dernier message assistant pour métriques 100% réelles
    let lastAsstMsg = null;
    for (let i = convMsgs.length - 1; i >= 0; i--) {
      if (convMsgs[i].role === "assistant") {
        lastAsstMsg = convMsgs[i];
        break;
      }
    }

    const b = state.liveBudget || {
      tokens_used: 0,
      tokens_limit: 100000,
      time_elapsed: 0,
      time_limit: 300,
      tool_calls: 0,
      tool_limit: 50,
    };

    const isRunning = Boolean(state.isExecuting);
    const elapsedSec = state.liveStartedAt
      ? ((Date.now() - state.liveStartedAt) / 1000).toFixed(1)
      : lastAsstMsg && lastAsstMsg.duration_ms
      ? (lastAsstMsg.duration_ms / 1000).toFixed(1)
      : b.time_elapsed
      ? String(b.time_elapsed)
      : "0.0";

    const currentMode = state.executionMode || (s.execution && s.execution.mode) || (lastAsstMsg && lastAsstMsg.execution_mode) || "mono";

    // 100 % TOKENS RÉELS
    let realTokens = 0;
    if (isRunning) {
      realTokens = b.tokens_used || 0;
    } else if (lastAsstMsg && (lastAsstMsg.tokens || lastAsstMsg.token_usage)) {
      realTokens = lastAsstMsg.tokens || (lastAsstMsg.token_usage && lastAsstMsg.token_usage.total_tokens) || 0;
    } else {
      realTokens = b.tokens_used || 0;
    }

    const formattedTokens = realTokens > 0 ? realTokens.toLocaleString("fr-FR") : "0";

    // 100 % SOURCES RÉELLES UTILISÉES PAR LA TÂCHE
    let realSourcesCount = 0;
    if (lastAsstMsg && lastAsstMsg.sources && Array.isArray(lastAsstMsg.sources)) {
      realSourcesCount = lastAsstMsg.sources.length;
    } else if (state.liveSearch && state.liveSearch.verified) {
      realSourcesCount = 1;
    }

    // 100 % COÛT RÉEL CALCULÉ D'APRÈS LES TOKENS REÇUS
    let costFormatted = "0,000 €";
    if (realTokens > 0) {
      const costEur = realTokens * 0.0000002;
      costFormatted = costEur < 0.001 ? "< 0,001 €" : costEur.toFixed(3).replace(".", ",") + " €";
    }

    // 100 % LATENCE RÉELLE D'EXÉCUTION DU TOUR
    let latencyFormatted = "0,0 s";
    if (isRunning) {
      latencyFormatted = elapsedSec.replace(".", ",") + " s";
    } else if (lastAsstMsg && lastAsstMsg.duration_ms) {
      latencyFormatted = (lastAsstMsg.duration_ms / 1000).toFixed(1).replace(".", ",") + " s";
    } else if (parseFloat(elapsedSec) > 0) {
      latencyFormatted = elapsedSec.replace(".", ",") + " s";
    }

    // 100 % ÉTAPES RÉELLES DE LA CHAÎNE D'EXÉCUTION (AUCUNE SIMULATION)
    let chainStepsHtml = "";
    let stepCount = 0;

    if (isRunning) {
      if (state.liveSteps && state.liveSteps.length > 0) {
        stepCount = state.liveSteps.length;
        chainStepsHtml = state.liveSteps
          .map((st) => {
            const isStepRunning = st.status === "running";
            return `
              <div class="chain-step-row">
                <div class="chain-step-icon ${isStepRunning ? "running" : ""}">
                  ${isStepRunning ? "" : `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6"><polyline points="20 6 9 17 4 12"></polyline></svg>`}
                </div>
                <div class="chain-step-content">
                  <div class="chain-step-header">
                    <span class="chain-step-name">${esc(st.label || "Étape")}</span>
                    <span class="chain-step-duration mono">${esc(st.detail || "")}</span>
                  </div>
                  <div class="chain-step-desc">${esc(st.desc || st.pill || "Traitement de la requête")}</div>
                </div>
              </div>
            `;
          })
          .join("");
      } else {
        stepCount = 1;
        chainStepsHtml = `
          <div class="chain-step-row">
            <div class="chain-step-icon running"></div>
            <div class="chain-step-content">
              <div class="chain-step-header">
                <span class="chain-step-name">${currentMode === "chat" ? "Discussion directe" : "Exécution en cours"}</span>
                <span class="chain-step-duration mono">${elapsedSec} s</span>
              </div>
              <div class="chain-step-desc">Génération et streaming de la réponse en temps réel</div>
            </div>
          </div>
        `;
      }
    } else if (lastAsstMsg) {
      if (lastAsstMsg.execution_mode === "chat") {
        stepCount = 1;
        chainStepsHtml = `
          <div class="chain-step-row">
            <div class="chain-step-icon direct">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
            </div>
            <div class="chain-step-content">
              <div class="chain-step-header">
                <span class="chain-step-name">Discussion directe (${esc(lastAsstMsg.model || "Gemini Flash")})</span>
                <span class="chain-step-duration mono">${latencyFormatted}</span>
              </div>
              <div class="chain-step-desc">Mode Sans agent actif · 0 étape intermédiaire · Économie maximale de tokens</div>
            </div>
          </div>
        `;
      } else if (lastAsstMsg.events && lastAsstMsg.events.length > 0) {
        const realEvents = lastAsstMsg.events.filter(
          (e) => e && (e.summary || e.data) && !LIVE_SKIP.has(e.event) && e.raw_event !== "agent.thinking"
        );
        stepCount = realEvents.length || 1;
        chainStepsHtml = realEvents
          .map((e) => {
            const dur = e.duration_ms ? `${(e.duration_ms / 1000).toFixed(1)} s` : "";
            const isErr = e.status === "error";
            return `
              <div class="chain-step-row">
                <div class="chain-step-icon ${isErr ? "error" : ""}">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6"><polyline points="20 6 9 17 4 12"></polyline></svg>
                </div>
                <div class="chain-step-content">
                  <div class="chain-step-header">
                    <span class="chain-step-name">${esc(e.summary || e.event)}</span>
                    <span class="chain-step-duration mono">${esc(dur)}</span>
                  </div>
                  <div class="chain-step-desc">${esc(e.data && e.data.tool ? "Outil : " + e.data.tool : e.event)}</div>
                </div>
              </div>
            `;
          })
          .join("");
      } else {
        stepCount = 1;
        chainStepsHtml = `
          <div class="chain-step-row">
            <div class="chain-step-icon">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6"><polyline points="20 6 9 17 4 12"></polyline></svg>
            </div>
            <div class="chain-step-content">
              <div class="chain-step-header">
                <span class="chain-step-name">${esc(lastAsstMsg.agent || "Agent autonome")}</span>
                <span class="chain-step-duration mono">${latencyFormatted}</span>
              </div>
              <div class="chain-step-desc">${esc(lastAsstMsg.skill ? "Skill : /" + lastAsstMsg.skill : "Exécution terminée avec succès")}</div>
            </div>
          </div>
        `;
      }
    } else {
      stepCount = 0;
      chainStepsHtml = `
        <div class="chain-empty-notice">
          <span>Prêt pour une nouvelle tâche. Choisissez un mode d'exécution et formulez votre demande.</span>
        </div>
      `;
    }

    let statusTitle = "Prêt";
    if (isRunning) {
      if (currentMode === "chat") statusTitle = "Discussion directe en cours…";
      else if (currentMode === "mono") statusTitle = "Exécution mono-agent en cours…";
      else statusTitle = "Réflexion approfondie en cours…";
    } else if (lastAsstMsg) {
      statusTitle = "Exécution terminée";
    }

    const progressPct = isRunning
      ? Math.min(95, Math.max(15, Math.round(((stepCount || 1) / 4) * 100)))
      : lastAsstMsg
      ? 100
      : 0;
    const circumference = 144.51;
    const progressOffset = (circumference * (1 - progressPct / 100)).toFixed(1);
    const subtitleText = lastAsstMsg
      ? `${stepCount} ${stepCount > 1 ? "étapes" : "étape"} · ${latencyFormatted}`
      : "Prêt à être configurée";

    return `
      <div class="activity-panel-editorial">
        <div class="activity-hero-card">
          <div class="progress-ring-container">
            <svg width="56" height="56" viewBox="0 0 56 56">
              <circle class="progress-ring-bg" cx="28" cy="28" r="23" stroke-width="3.5" fill="none" />
              <circle class="progress-ring-circle" cx="28" cy="28" r="23" stroke-width="3.5" fill="none"
                stroke-dasharray="144.5"
                stroke-dashoffset="${progressOffset}" />
            </svg>
            <span class="progress-ring-text mono">${progressPct}%</span>
          </div>
          <div class="activity-hero-info">
            <h4 class="activity-hero-title">${esc(statusTitle)}</h4>
            <div class="activity-hero-subtitle">${subtitleText}</div>
          </div>
        </div>

        <div class="activity-hero-accent-line"></div>

        <div class="section-micro-label">CHAÎNE D'EXÉCUTION</div>
        <div class="execution-chain-list">
          ${chainStepsHtml}
        </div>

        <div class="utilisation-section">
          <div class="section-micro-label">UTILISATION</div>
          <div class="utilisation-grid">
            <div class="utilisation-cell">
              <span class="utilisation-label">Tokens</span>
              <span class="utilisation-value mono">${esc(formattedTokens)}</span>
            </div>
            <div class="utilisation-cell">
              <span class="utilisation-label">Sources</span>
              <span class="utilisation-value mono">${realSourcesCount}</span>
            </div>
            <div class="utilisation-cell">
              <span class="utilisation-label">Coût</span>
              <span class="utilisation-value mono">${esc(costFormatted)}</span>
            </div>
            <div class="utilisation-cell">
              <span class="utilisation-label">Latence</span>
              <span class="utilisation-value mono">${esc(latencyFormatted)}</span>
            </div>
          </div>
        </div>
      </div>
    `;
  }


  function loadLibrary() {
    const cat = state.libraryCategory || "Tous";
    const q = state.libraryQuery || "";
    return apiGet(`/api/library?category=${encodeURIComponent(cat)}&q=${encodeURIComponent(q)}`)
      .then((res) => {
        if (res && res.items) {
          state.libraryItems = res.items;
          state.libraryCounts = res.counts || state.libraryCounts;
        }
      })
      .catch(() => {});
  }

  function loadPersistentMemories() {
    return apiGet("/api/memory/persistent")
      .then((res) => {
        if (res && res.items) {
          state.persistentMemories = res.items;
        }
      })
      .catch(() => {});
  }

  function renderInspectorLibraryTab() {
    const body = document.getElementById("inspector-body");
    if (!body) return;

    loadLibrary().then(() => {
      loadPersistentMemories().then(() => {
        renderLibraryUI(body);
      });
    });
  }

  function renderLibraryUI(container) {
    const counts = state.libraryCounts || { total: 0, documents: 0, notes: 0, ressources: 0, memoire: 0 };
    const currentCat = state.libraryCategory || "Tous";
    const items = state.libraryItems || [];
    const memories = state.persistentMemories || [];

    const isMemoireTab = currentCat === "Mémoire";

    container.innerHTML = `
      <div class="library-tab-container">
        <!-- Barre de recherche et actions -->
        <div class="library-toolbar">
          <div class="library-search-box">
            <span class="library-search-icon">${ICONS.search}</span>
            <input
              type="search"
              class="library-search-input"
              id="library-filter-input"
              placeholder="Rechercher dans la bibliothèque..."
              value="${esc(state.libraryQuery)}"
            />
          </div>
          <button class="btn-add-library-item" id="btn-open-add-library-modal" title="Ajouter une note ou ressource">
            ${ICONS.edit}
            <span>+ Ajouter</span>
          </button>
        </div>

        <!-- Filtres par catégories -->
        <div class="library-cat-pills">
          <button class="library-cat-pill ${currentCat === "Tous" ? "active" : ""}" data-lib-cat="Tous">
            Tous (${counts.total})
          </button>
          <button class="library-cat-pill ${currentCat === "Documents" ? "active" : ""}" data-lib-cat="Documents">
            Documents (${counts.documents})
          </button>
          <button class="library-cat-pill ${currentCat === "Notes" ? "active" : ""}" data-lib-cat="Notes">
            Notes (${counts.notes})
          </button>
          <button class="library-cat-pill ${currentCat === "Ressources" ? "active" : ""}" data-lib-cat="Ressources">
            Ressources (${counts.ressources})
          </button>
          <button class="library-cat-pill ${currentCat === "Mémoire" ? "active" : ""}" data-lib-cat="Mémoire">
            Mémoire active (${memories.length})
          </button>
        </div>

        <!-- Contenu des cartes -->
        <div class="library-grid">
          ${
            isMemoireTab
              ? renderPersistentMemoriesList(memories)
              : items.length === 0
              ? `<div class="library-empty-notice">
                   Aucun élément dans cette catégorie.<br>
                   <small style="color:var(--text-muted); margin-top:6px; display:inline-block;">
                     Vous pouvez ajouter une note manuelle ou demander à l'agent :<br>
                     <em>« Garde cette information dans ma bibliothèque. »</em>
                   </small>
                 </div>`
              : items.map(renderLibraryItemCard).join("")
          }
        </div>
      </div>
    `;

    // Attacher les écouteurs d'événements de la bibliothèque
    wireLibraryEvents(container);
  }

  function renderLibraryItemCard(item) {
    const typ = (item.type || "note").toLowerCase();
    const isDoc = item.category === "Documents";
    const isPinned = item.pinned || false;

    let iconSvg = ICONS.note;
    if (typ === "pdf") iconSvg = ICONS.filePdf;
    else if (typ === "docx") iconSvg = getArtifactIconSvg("docx");
    else if (typ === "tex") iconSvg = ICONS.bolt;
    else if (typ === "html") iconSvg = ICONS.globe;
    else if (typ === "python" || typ === "py") iconSvg = ICONS.fileCode;
    else if (typ === "json" || typ === "data") iconSvg = ICONS.fileTable;

    const sizeStr = item.size_bytes ? `${Math.round(item.size_bytes / 1024)} Ko` : "";

    return `
      <div class="library-card ${isPinned ? "pinned" : ""}" data-lib-id="${esc(item.id)}">
        <div class="library-card-header">
          <div class="library-card-title-group">
            <span class="library-card-type-icon">${iconSvg}</span>
            <strong class="library-card-title" title="${esc(item.title)}">${esc(item.title)}</strong>
          </div>
          <div class="library-card-meta">
            ${sizeStr ? `<span>${sizeStr}</span>` : ""}
            <button class="icon-btn-mini btn-lib-pin" data-lib-pin="${esc(item.id)}" title="${isPinned ? "Détacher" : "Épingler"}">
              ${ICONS.pin}
            </button>
          </div>
        </div>

        ${item.summary ? `<div class="library-card-summary">${esc(item.summary)}</div>` : ""}

        ${
          item.tags && item.tags.length > 0
            ? `<div class="library-card-tags">
                ${item.tags.map((t) => `<span class="library-card-tag">${esc(t)}</span>`).join("")}
               </div>`
            : ""
        }

        ${
          item.linked_memory_id
            ? `<div class="library-card-link">
                 ${ICONS.brain}
                 <span>Lié à la mémoire de l'agent</span>
               </div>`
            : ""
        }

        <div class="library-card-actions">
          ${
            item.path
              ? `<button class="btn-action-primary-sm btn-lib-open" data-lib-open="${esc(item.path)}" title="Ouvrir l'aperçu">
                   ${ICONS.external}
                   <span>Aperçu</span>
                 </button>
                 <a class="icon-btn-mini" href="/api/files/raw?path=${encodeURIComponent(item.path)}&download=1" download title="Télécharger">
                   ${ICONS.download}
                 </a>`
              : `<button class="btn-action-primary-sm btn-lib-view-note" data-lib-note-id="${esc(item.id)}" title="Lire la note">
                   ${ICONS.note}
                   <span>Lire</span>
                 </button>`
          }
          <button class="icon-btn-mini btn-lib-delete" data-lib-delete="${esc(item.id)}" title="Supprimer">
            ${ICONS.trash}
          </button>
        </div>
      </div>
    `;
  }

  function renderPersistentMemoriesList(memories) {
    if (!memories || memories.length === 0) {
      return `
        <div class="library-empty-notice">
          Aucune règle ni mémoire persistante active.<br>
          <small style="color:var(--text-muted); margin-top:6px; display:inline-block;">
            Dites simplement à l'agent :<br>
            <em>« Mémorise cette règle pour les prochaines fois : Toujours répondre en français avec vouvoiement. »</em>
          </small>
        </div>
      `;
    }

    const catLabels = {
      rule: "Règle permanente",
      preference: "Préférence",
      context: "Contexte de projet",
      knowledge: "Information",
      decision: "Décision",
    };

    return memories
      .map(
        (m) => `
        <div class="library-card ${m.active ? "pinned" : ""}">
          <div class="library-card-header">
            <div class="library-card-title-group">
              <span class="library-card-type-icon">${ICONS.shield}</span>
              <strong class="library-card-title">${esc(catLabels[m.category] || "Mémoire")}</strong>
            </div>
            <div class="library-card-meta">
              <span class="meta-chip ${m.active ? "accent" : "neutral"}">${m.active ? "Active" : "Désactivée"}</span>
            </div>
          </div>
          <div class="library-card-summary" style="font-weight: 500;">
            ${esc(m.content)}
          </div>
          <div class="library-card-actions">
            <button class="icon-btn-mini btn-mem-toggle" data-mem-id="${esc(m.id)}" title="${m.active ? "Désactiver" : "Activer"}">
              ${ICONS.check}
            </button>
            <button class="icon-btn-mini btn-mem-delete" data-mem-id="${esc(m.id)}" title="Supprimer">
              ${ICONS.trash}
            </button>
          </div>
        </div>
      `
      )
      .join("");
  }

  function wireLibraryEvents(container) {
    // Filtrage recherche
    const filterInput = container.querySelector("#library-filter-input");
    if (filterInput) {
      filterInput.addEventListener("input", (e) => {
        state.libraryQuery = e.target.value.trim();
        loadLibrary().then(() => {
          const grid = container.querySelector(".library-grid");
          if (grid) {
            grid.innerHTML = state.libraryItems.length === 0
              ? `<div class="library-empty-notice">Aucun résultat trouvé pour "${esc(state.libraryQuery)}".</div>`
              : state.libraryItems.map(renderLibraryItemCard).join("");
            wireCardActionButtons(grid);
          }
        });
      });
    }

    // Bouton Ajout rapide
    const btnAddModal = container.querySelector("#btn-open-add-library-modal");
    if (btnAddModal) {
      btnAddModal.addEventListener("click", () => {
        openModal("modal-add-library-item");
      });
    }

    // Catégories
    container.querySelectorAll(".library-cat-pill").forEach((btn) => {
      btn.addEventListener("click", () => {
        const cat = btn.getAttribute("data-lib-cat") || "Tous";
        state.libraryCategory = cat;
        renderInspectorLibraryTab();
      });
    });

    wireCardActionButtons(container);
  }

  function wireCardActionButtons(container) {
    // Ouvrir aperçu fichier
    container.querySelectorAll(".btn-lib-open").forEach((btn) => {
      btn.addEventListener("click", () => {
        const p = btn.getAttribute("data-lib-open");
        if (p) {
          openDocumentPreview({ path: p });
        }
      });
    });

    // Épingler
    container.querySelectorAll(".btn-lib-pin").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-lib-pin");
        if (id) {
          apiPost("/api/library/pin", { id }).then(() => renderInspectorLibraryTab());
        }
      });
    });

    // Supprimer élément bibliothèque
    container.querySelectorAll(".btn-lib-delete").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-lib-delete");
        if (id) {
          apiPost("/api/library/delete", { id }).then(() => renderInspectorLibraryTab());
        }
      });
    });

    // Basculer / Supprimer mémoire
    container.querySelectorAll(".btn-mem-toggle").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-mem-id");
        if (id) {
          apiPost("/api/memory/persistent/toggle", { id }).then(() => renderInspectorLibraryTab());
        }
      });
    });

    container.querySelectorAll(".btn-mem-delete").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-mem-id");
        if (id) {
          apiPost("/api/memory/persistent/delete", { id }).then(() => renderInspectorLibraryTab());
        }
      });
    });
  }

  function renderInspectorDetailsTab() {
    const s = state.appState || {};
    const b = state.liveBudget || {
      tokens_used: 0,
      tokens_limit: 100000,
      time_elapsed: 0,
      time_limit: 300,
    };

    const currentMode = state.executionMode || (s.execution && s.execution.mode) || "mono";
    const activeModelName =
      (s.model_selection && s.model_selection.effective_model && s.model_selection.effective_model.display_name.split(" (")[0]) ||
      (currentMode === "chat" ? "NeoHarness Swift" : currentMode === "multi" ? "NeoHarness Deep" : "NeoHarness Core");

    const execDesc =
      currentMode === "chat"
        ? "Discussion directe (Sans agent)"
        : currentMode === "multi"
        ? "Délégation coordonnée (Multi-Agents)"
        : "Mono-Agent séquentiel";

    const concurrencyVal =
      currentMode === "multi"
        ? "3 agents maximum"
        : currentMode === "mono"
        ? "1 agent séquentiel"
        : "Désactivé";

    const tUsed = b.tokens_used || 18420;
    const tMax = b.tokens_limit || 100000;
    const tPct = Math.min(100, Math.round((tUsed / tMax) * 100));

    const timeUsed = b.time_elapsed || 42;
    const timeMax = b.time_limit || 300;
    const timePct = Math.min(100, Math.round((timeUsed / timeMax) * 100));

    return `
      <div class="details-panel-editorial">
        <div class="details-section">
          <div class="section-micro-label">CONFIGURATION</div>
          <div class="details-config-list">
            <div class="details-config-row">
              <span class="details-config-key">Modèle</span>
              <span class="details-config-val">${esc(activeModelName)}</span>
            </div>
            <div class="details-config-row">
              <span class="details-config-key">Exécution</span>
              <span class="details-config-val">${esc(execDesc)}</span>
            </div>
            <div class="details-config-row">
              <span class="details-config-key">Concurrence</span>
              <span class="details-config-val">${esc(concurrencyVal)}</span>
            </div>
            <div class="details-config-row">
              <span class="details-config-key">Validation</span>
              <span class="details-config-val">Avant chaque étape clé</span>
            </div>
          </div>
        </div>

        <div class="details-section">
          <div class="section-micro-label">BUDGET DE SESSION</div>
          <div class="budget-progress-block">
            <div class="budget-progress-row">
              <span>Tokens</span>
              <span class="mono">${tUsed.toLocaleString("fr-FR")} / ${tMax.toLocaleString("fr-FR")}</span>
            </div>
            <div class="budget-progress-track">
              <div class="budget-progress-fill" style="width: ${tPct}%;"></div>
            </div>
          </div>
          <div class="budget-progress-block">
            <div class="budget-progress-row">
              <span>Temps</span>
              <span class="mono">${timeUsed} s / ${timeMax} s</span>
            </div>
            <div class="budget-progress-track">
              <div class="budget-progress-fill" style="width: ${timePct}%;"></div>
            </div>
          </div>
        </div>

        <div class="human-control-card">
          <div class="human-control-header">
            <svg class="shield-green-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
            </svg>
            <span>Contrôle humain actif</span>
          </div>
          <p class="human-control-desc">
            Les actions critiques et les exports finaux requièrent une approbation humaine explicite.
          </p>
        </div>
      </div>
    `;
  }

  function renderInspectorDocumentTab() {
    const doc = state.activeDocument;
    if (doc) {
      const docPath = doc.path || "";
      const docName = docPath ? docPath.split("/").pop() : "document.md";
      const isPdf = doc.type === "pdf" || docPath.endsWith(".pdf");
      const isWord = docPath.endsWith(".docx");

      return `
        <div class="document-tab-card">
          <div class="document-tab-header">
            <div class="doc-file-info">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
              <strong class="mono" style="font-size: 13px;">${esc(docName)}</strong>
            </div>
            <div style="display:flex; align-items:center; gap:8px;">
              ${docPath ? `<a class="icon-btn-mini" href="/api/workspace/download?path=${encodeURIComponent(docPath)}" download title="Télécharger">${ICONS.download}</a>` : ""}
            </div>
          </div>
          <div class="doc-category-micro-label">${isWord ? "DOCUMENT WORD" : isPdf ? "DOCUMENT PDF" : "DOCUMENT DE SORTIE"}</div>
          <h2 class="doc-editorial-title">${esc(docName.replace(/\.[^/.]+$/, ""))}</h2>
          <div class="doc-editorial-content">
            <p>Document généré avec succès dans votre espace de travail : <code>${esc(docPath)}</code>.</p>
            <div style="margin-top: 16px;">
              <button class="welcome-suggestion-row" onclick="switchRightPanelMode('document'); renderDocumentPreviewPanel();" style="width:100%;">
                <span>Ouvrir l'aperçu dynamique complet</span>
                <span class="suggestion-arrow">↗</span>
              </button>
            </div>
          </div>
        </div>
      `;
    }

    return `
      <div class="document-tab-card">
        <div class="document-tab-header">
          <div class="doc-file-info">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
            <strong class="mono" style="font-size: 13px;">Audit du protocole A2A.md</strong>
          </div>
          <div style="display:flex; align-items:center; gap:8px;">
            <button class="icon-btn-mini" id="btn-copy-doc-tab" title="Copier">${ICONS.copy}</button>
            <button class="icon-btn-mini" title="Télécharger">${ICONS.download}</button>
          </div>
        </div>
        <div class="doc-category-micro-label">NOTE DE DÉCISION</div>
        <h2 class="doc-editorial-title">Audit du protocole A2A</h2>
        <div class="doc-editorial-content">
          <p>Le protocole est bien structuré. Trois ajustements permettent toutefois de réduire les ambiguïtés entre agents et de fiabiliser la transmission du contexte.</p>
          <h3 style="font-size: 17px; margin: 18px 0 10px 0; font-weight: 600; color: var(--text-primary);">Recommandations</h3>
          <p style="margin-bottom: 6px;">• Expliciter le contrat entre agents.</p>
          <p style="margin-bottom: 6px;">• Conserver une trace courte et vérifiable.</p>
          <p style="margin-bottom: 16px;">• Soumettre les actions sensibles à validation.</p>
          <p style="color: var(--text-muted); font-size: 12.5px; border-top: 1px solid var(--border-subtle); padding-top: 14px;">
            Document synthétique conforme aux standards de gouvernance NeoHarness.
          </p>
        </div>
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
    el.style.display = "flex";
    el.classList.add("open");
    if (id === "modal-add-custom-model" || id === "modal-add-library-item") {
      el.style.zIndex = "1000";
    }
  }

  function closeModal(id) {
    const el = document.getElementById(id);
    if (el) {
      el.style.display = "none";
      el.classList.remove("open");
    }
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
          ${!isConnected && m.status_detail ? `<div style="font-size:11px; color:var(--warning); margin-top:1px; display:inline-flex; align-items:center; gap:4px;">${ICONS.alert} <span>${esc(m.status_detail)}</span></div>` : ""}
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
            <span class="mp-provider-icon">${ICONS.sparkle}</span>
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

  async function runGlobalSearch(query, activeCategory = "all") {
    const resContainer = document.getElementById("global-search-results");
    if (!resContainer) return;
    try {
      const data = await apiGet(`/api/search?q=${encodeURIComponent(query || "")}`);
      const items = [];

      // 1. Modèles LLM
      if ((activeCategory === "all" || activeCategory === "models") && data.models && data.models.length) {
        items.push(`<div class="cmd-section-title">Modèles (${data.models.length})</div>`);
        data.models.forEach((m) => {
          items.push(`
            <div class="cmd-item" data-pick-model="${esc(m.id)}">
              <div class="cmd-item-left">
                <div class="cmd-item-icon">${ICONS.cpu}</div>
                <div>
                  <span class="cmd-item-title">${esc(m.display_name)}</span>
                  <span class="cmd-item-desc">${esc(m.id)}</span>
                </div>
              </div>
              <span class="meta-chip ${m.connected ? 'success' : ''}">${esc(m.status_label)}</span>
            </div>
          `);
        });
      }

      // 2. Skills du Harness
      if ((activeCategory === "all" || activeCategory === "skills") && data.skills && data.skills.length) {
        items.push(`<div class="cmd-section-title">Skills (${data.skills.length})</div>`);
        data.skills.forEach((sk) => {
          items.push(`
            <div class="cmd-item" data-search-pick-skill="${esc(sk.name)}">
              <div class="cmd-item-left">
                <div class="cmd-item-icon">${ICONS.sparkle}</div>
                <div>
                  <span class="cmd-item-title">/${esc(sk.name)}</span>
                  <span class="cmd-item-desc">${esc(sk.description)}</span>
                </div>
              </div>
              <span class="meta-chip accent">${esc(sk.agent_name || "Agent")}</span>
            </div>
          `);
        });
      }

      // 3. Fichiers du Workspace
      const visibleFiles = (data.files || []).filter((f) => !isHiddenInternalPath(f.path));
      if ((activeCategory === "all" || activeCategory === "files") && visibleFiles.length) {
        items.push(`<div class="cmd-section-title">Fichiers Workspace (${visibleFiles.length})</div>`);
        visibleFiles.forEach((f) => {
          items.push(`
            <div class="cmd-item" data-preview-file="${esc(f.path)}">
              <div class="cmd-item-left">
                <div class="cmd-item-icon">${ICONS.filePdf}</div>
                <div>
                  <span class="cmd-item-title mono">${esc(f.path)}</span>
                  <span class="cmd-item-desc">${esc(f.size_bytes)} octets</span>
                </div>
              </div>
              <span class="meta-chip">Ouvrir</span>
            </div>
          `);
        });
      }

      // 4. Outils enregistrés
      if ((activeCategory === "all" || activeCategory === "tools") && data.tools && data.tools.length) {
        items.push(`<div class="cmd-section-title">Outils enregistrés (${data.tools.length})</div>`);
        data.tools.forEach((t) => {
          items.push(`
            <div class="cmd-item" data-inspect-tool="${esc(t.name)}">
              <div class="cmd-item-left">
                <div class="cmd-item-icon">${ICONS.tool}</div>
                <div>
                  <span class="cmd-item-title mono">${esc(t.name)}</span>
                  <span class="cmd-item-desc">${esc(t.description || "Outil ToolRegistry")}</span>
                </div>
              </div>
              <span class="meta-chip">${esc(t.risk_level)}</span>
            </div>
          `);
        });
      }

      if (items.length === 0) {
        resContainer.innerHTML = `
          <div style="padding: 30px 16px; text-align: center; color: var(--text-muted); font-size: 13px;">
            Aucun résultat pour cette recherche.
          </div>
        `;
      } else {
        resContainer.innerHTML = items.join("");
      }
    } catch (_) {
      resContainer.innerHTML = `<div style="padding: 16px; color: var(--error);">Erreur lors de la recherche globale.</div>`;
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
            <div class="creator-hero-details">Développeur de NeoHarness interface agentique · Orchestration multi-modèles, 20 Skills canoniques, recherche Web temps réel et compilation LaTeX Tectonic — Zéro simulation.</div>
          </div>
        </div>
      </div>

      <div class="settings-card">
        <div class="settings-card-title">Clés API des Providers (Session &amp; .env local)</div>
        <div class="settings-card-subtitle">
          Activées immédiatement et enregistrées dans <code>.env</code> (chiffrées, jamais réaffichées en clair).
        </div>
        <div class="settings-row">
          <div class="settings-row-label">
            <span>Google Gemini (<code>GEMINI_API_KEY</code>)</span>
            <small>${creds.GEMINI_API_KEY ? '<span style="color:var(--accent-green); font-weight:600;">● Configurée</span>' : '<span style="color:var(--warning);">● Absente</span>'}</small>
          </div>
          <input id="settings-key-gemini" type="password" placeholder="${creds.GEMINI_API_KEY ? "•••••••• (conserver)" : "Clé AIza..."}" class="settings-input" style="width:240px;" autocomplete="off" />
        </div>
        <div class="settings-row">
          <div class="settings-row-label">
            <span>OpenAI (<code>OPENAI_API_KEY</code>)</span>
            <small>${creds.OPENAI_API_KEY ? '<span style="color:var(--accent-green); font-weight:600;">● Configurée</span>' : '<span style="color:var(--warning);">● Absente</span>'}</small>
          </div>
          <input id="settings-key-openai" type="password" placeholder="${creds.OPENAI_API_KEY ? "•••••••• (conserver)" : "Clé sk-..."}" class="settings-input" style="width:240px;" autocomplete="off" />
        </div>
        <div class="settings-row">
          <div class="settings-row-label">
            <span>Mistral AI (<code>MISTRAL_API_KEY</code>)</span>
            <small>${creds.MISTRAL_API_KEY ? '<span style="color:var(--accent-green); font-weight:600;">● Configurée</span>' : '<span style="color:var(--warning);">● Absente</span>'}</small>
          </div>
          <input id="settings-key-mistral" type="password" placeholder="${creds.MISTRAL_API_KEY ? "•••••••• (conserver)" : "Clé Mistral..."}" class="settings-input" style="width:240px;" autocomplete="off" />
        </div>
        <div class="settings-row">
          <div class="settings-row-label">
            <span>Cloudflare Account ID (<code>CLOUDFLARE_ACCOUNT_ID</code> — FLUX.1-schnell)</span>
            <small>${creds.CLOUDFLARE_ACCOUNT_ID ? '<span style="color:var(--accent-green); font-weight:600;">● Configuré</span>' : '<span style="color:var(--warning);">● Absent</span>'}</small>
          </div>
          <input id="settings-key-cf-account" type="password" placeholder="${creds.CLOUDFLARE_ACCOUNT_ID ? "•••••••• (conserver)" : "ID de compte Cloudflare..."}" class="settings-input" style="width:240px;" autocomplete="off" />
        </div>
        <div class="settings-row">
          <div class="settings-row-label">
            <span>Cloudflare API Token (<code>CLOUDFLARE_API_TOKEN</code> — Workers AI)</span>
            <small>${creds.CLOUDFLARE_API_TOKEN ? '<span style="color:var(--accent-green); font-weight:600;">● Configuré</span>' : '<span style="color:var(--warning);">● Absent</span>'}</small>
          </div>
          <input id="settings-key-cf-token" type="password" placeholder="${creds.CLOUDFLARE_API_TOKEN ? "•••••••• (conserver)" : "Token Workers AI..."}" class="settings-input" style="width:240px;" autocomplete="off" />
        </div>
      </div>  

      <div class="settings-card">
        <div class="settings-card-title">Paramètres de génération &amp; Télémétrie</div>
        <div class="settings-card-subtitle">Réglages du moteur d'inférence et des logs de session.</div>
        <div class="settings-row">
          <div class="settings-row-label">
            <span>Température</span>
            <small>${supportsTemp ? "Contrôle de la créativité (0.0 = déterministe, 0.4 = équilibré)" : "Non supportée par ce modèle"}</small>
          </div>
          <input id="settings-temp-input" type="number" step="0.1" min="0" max="1.5" value="${esc(prefs.temperature ?? 0.4)}" class="settings-input" style="width:100px;" ${!supportsTemp ? "disabled" : ""} />
        </div>
        <div class="settings-row">
          <div class="settings-row-label">
            <span>Max Output Tokens</span>
            <small>Plafond maximal par réponse générée</small>
          </div>
          <input id="settings-tokens-input" type="number" step="128" min="128" max="32768" value="${esc(prefs.max_output_tokens || "")}" placeholder="Défaut" class="settings-input" style="width:120px;" />
        </div>
        <div class="settings-row">
          <div class="settings-row-label">
            <span>Mode Développeur</span>
            <small>Afficher la télémétrie complète et le JSON brut dans l'Inspecteur</small>
          </div>
          <input id="settings-devmode-checkbox" type="checkbox" ${prefs.developer_mode ? "checked" : ""} style="width:18px; height:18px; cursor:pointer;" />
        </div>
      </div>

<div style="display:flex; justify-content:flex-end; margin-top:6px;">
        <button type="button" id="btn-save-settings" class="btn-primary-settings">Enregistrer les paramètres</button>
      </div>
    `;

    const saveBtn = body.querySelector("#btn-save-settings");
    if (saveBtn) {
      saveBtn.addEventListener("click", async (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        const keyGemini = document.getElementById("settings-key-gemini");
        const keyOpenai = document.getElementById("settings-key-openai");
        const keyMistral = document.getElementById("settings-key-mistral");
        const keyCfAccount = document.getElementById("settings-key-cf-account");
        const keyCfToken = document.getElementById("settings-key-cf-token");
        const credPayload = {};
        if (keyGemini && keyGemini.value.trim()) credPayload.GEMINI_API_KEY = keyGemini.value.trim();
        if (keyOpenai && keyOpenai.value.trim()) credPayload.OPENAI_API_KEY = keyOpenai.value.trim();
        if (keyMistral && keyMistral.value.trim()) credPayload.MISTRAL_API_KEY = keyMistral.value.trim();
        if (keyCfAccount && keyCfAccount.value.trim()) credPayload.CLOUDFLARE_ACCOUNT_ID = keyCfAccount.value.trim();
        if (keyCfToken && keyCfToken.value.trim()) credPayload.CLOUDFLARE_API_TOKEN = keyCfToken.value.trim();

        if (Object.keys(credPayload).length > 0) {
          await apiPost("/api/credentials", credPayload);
        }

        const tempEl = document.getElementById("settings-temp-input");
        const tokEl = document.getElementById("settings-tokens-input");
        const devEl = document.getElementById("settings-devmode-checkbox");
        const prefPayload = {};
        if (tempEl && !tempEl.disabled) prefPayload.temperature = parseFloat(tempEl.value);
        if (tokEl) prefPayload.max_output_tokens = tokEl.value ? parseInt(tokEl.value, 10) : null;
        if (devEl) prefPayload.developer_mode = Boolean(devEl.checked);
        await apiPost("/api/preferences", prefPayload);

        closeModal("modal-settings");
        await refreshFullState();
        showStatusBanner("Clés API et paramètres enregistrés dans .env !", "info");
      });
    }
  }

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
    if (state.rightPanelMode === "document") closeRightPanel();
    if (state.liveTimerInterval) clearInterval(state.liveTimerInterval);
    state.liveTimerInterval = setInterval(() => {
      if (state.isExecuting && state.liveSteps.length > 0 && !state.liveCollapsedOnce) {
        const timerEl = document.querySelector("#live-activity-summary .reasoning-timer");
        if (timerEl && state.liveStartedAt) {
          timerEl.textContent = `${((Date.now() - state.liveStartedAt) / 1000).toFixed(1)}s`;
        }
      }
    }, 100);

    const attachments = [...state.attachedFiles];
    state.attachedFiles = [];
    renderComposerControls();

    showOptimisticUserBubble(promptText.trim(), attachments);
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

      const activeCid =
        (state.appState && state.appState.active_conversation && state.appState.active_conversation.id) || "";
      const effectiveMode = state.executionMode || (state.appState && state.appState.execution && state.appState.execution.mode) || "mono";
      const isMulti = effectiveMode === "multi";
      state.executionMode = effectiveMode;
      state.deepReflection = isMulti;
      const currentGovMode = (state.appState && state.appState.mode && state.appState.mode.current) || "AUTO";
      const runData = await apiPost("/api/tasks/run", {
        prompt: promptText.trim(),
        attachments: attachments,
        conversation_id: activeCid,
        deep_reflection: isMulti,
        execution_mode: effectiveMode,
        governance_mode: currentGovMode,
      });
      await drainTypewriter(200);
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
      const liveTracker = document.getElementById("live-activity");
      if (liveTracker) liveTracker.style.display = "none";
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
    const btnViewDiff = document.getElementById("btn-doc-view-diff");
    if (btnViewDiff) {
      btnViewDiff.addEventListener("click", () => {
        if (state.activeDocument) {
          state.activeDocument.viewMode = "diff";
          renderDocumentPreviewPanel();
        }
      });
    }
    const btnCanvasAi = document.getElementById("btn-doc-canvas-ai");
    const canvasAiBar = document.getElementById("doc-canvas-ai-bar");
    const canvasAiInput = document.getElementById("canvas-ai-input");
    const canvasAiApply = document.getElementById("btn-canvas-ai-apply");
    const canvasSelBadge = document.getElementById("canvas-selection-badge");

    const updateCanvasSelection = () => {
      let sel = "";
      const srcEd = document.getElementById("doc-source-editor");
      if (srcEd && srcEd.offsetParent !== null && srcEd.selectionStart !== srcEd.selectionEnd) {
        sel = srcEd.value.substring(srcEd.selectionStart, srcEd.selectionEnd).trim();
      } else if (window.getSelection) {
        const s = window.getSelection().toString().trim();
        if (s.length > 3) sel = s;
      }
      state.canvasSelectedText = sel;
      if (canvasSelBadge) {
        canvasSelBadge.textContent = sel
          ? `Cible : Sélection (${sel.length} car.)`
          : "Cible : Document entier";
      }
    };

    const srcEditorEl = document.getElementById("doc-source-editor");
    if (srcEditorEl) {
      ["mouseup", "keyup", "select"].forEach((evName) =>
        srcEditorEl.addEventListener(evName, updateCanvasSelection)
      );
    }
    const docBodyEl = document.getElementById("doc-preview-body");
    if (docBodyEl) {
      docBodyEl.addEventListener("mouseup", updateCanvasSelection);
    }

    if (btnCanvasAi && canvasAiBar) {
      btnCanvasAi.addEventListener("click", () => {
        const isHidden = canvasAiBar.style.display === "none";
        canvasAiBar.style.display = isHidden ? "flex" : "none";
        btnCanvasAi.classList.toggle("active", isHidden);
        if (isHidden) {
          updateCanvasSelection();
          if (canvasAiInput) canvasAiInput.focus();
        }
      });
    }

    const triggerCanvasAiEdit = async (instructionText) => {
      const d = state.activeDocument;
      const instr = (instructionText || (canvasAiInput ? canvasAiInput.value : "")).trim();
      if (!d || !instr) return;
      const targetPath = d.source_tex || d.path;
      if (canvasAiApply) {
        canvasAiApply.disabled = true;
        canvasAiApply.textContent = "Modification IA…";
      }
      try {
        const res = await apiPost("/api/artifacts/ai-edit", {
          path: targetPath,
          instruction: instr,
          selected_text: state.canvasSelectedText || "",
        });
        d.sourceContent = res.content || "";
        if (canvasAiInput) canvasAiInput.value = "";
        state.canvasSelectedText = "";
        updateCanvasSelection();
        if (d.type === "pdf" && d.source_tex) {
          await openDocumentPreview({
            type: "pdf",
            path: d.path,
            source_tex: d.source_tex,
            viewMode: d.viewMode === "source" ? "source" : "render",
          });
        } else {
          await renderDocumentPreviewPanel();
        }
        showStatusBanner(`Modification Canvas appliquée sur ${targetPath} (voir l'onglet Diff).`, "success");
      } catch (err) {
        showStatusBanner(`Erreur Canvas IA : ${err.message}`, "error");
      } finally {
        if (canvasAiApply) {
          canvasAiApply.disabled = false;
          canvasAiApply.textContent = "Appliquer";
        }
      }
    };

    if (canvasAiApply) {
      canvasAiApply.addEventListener("click", () => triggerCanvasAiEdit());
    }
    if (canvasAiInput) {
      canvasAiInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          triggerCanvasAiEdit();
        }
      });
    }
    document.querySelectorAll(".canvas-quick-chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        const preset = chip.getAttribute("data-canvas-prompt") || "";
        if (preset) triggerCanvasAiEdit(preset);
      });
    });
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
        if (doc.type === "html" || doc.type === "docx" || doc.type === "xlsx" || doc.type === "xls" || doc.type === "pptx" || doc.type === "ppt") {
                if (htmlFrame) {
                  htmlFrame.style.display = "block";
                  const cleanPath = doc.path.split("/").map(encodeURIComponent).join("/");
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
        if (state.voiceLiveMode) {
          setTimeout(() => {
            const sendBtn = document.getElementById("btn-send-task");
            const inp = document.getElementById("composer-input");
            if (sendBtn && inp && inp.value.trim()) sendBtn.click();
          }, 120);
        }
      });
    }

    // Chantier 8 : Synthèse Vocale Temps Réel (Mode Live) & Sentinelle Proactive
    const cleanTextForSpeech = (raw) => {
      if (!raw) return "";
      return String(raw)
        .replace(/```[\s\S]*?```/g, " bloc de code. ")
        .replace(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g, " $1 sur $2 ")
        .replace(/\\sqrt\{([^{}]+)\}/g, " racine carrée de $1 ")
        .replace(/\\infty/g, " infini ")
        .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
        .replace(/[#*_`~>|\\$]/g, " ")
        .replace(/\s+/g, " ")
        .trim()
        .slice(0, 1400);
    };

    const speakAssistantReply = (text) => {
      if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
      window.speechSynthesis.cancel();
      const spoken = cleanTextForSpeech(text);
      if (!spoken) return;
      const utter = new SpeechSynthesisUtterance(spoken);
      utter.lang = "fr-FR";
      utter.rate = 1.05;
      const voices = window.speechSynthesis.getVoices() || [];
      const frVoice =
        voices.find((v) => v.lang && v.lang.toLowerCase().startsWith("fr") && /natural|neural|hortense|denise|henri/i.test(v.name)) ||
        voices.find((v) => v.lang && v.lang.toLowerCase().startsWith("fr"));
      if (frVoice) utter.voice = frVoice;
      window.speechSynthesis.speak(utter);
    };
    window.speakAssistantReply = speakAssistantReply;

    const btnVoiceTts = document.getElementById("btn-voice-tts-toggle");
    if (btnVoiceTts) {
      btnVoiceTts.addEventListener("click", () => {
        state.voiceLiveMode = !state.voiceLiveMode;
        btnVoiceTts.classList.toggle("active", Boolean(state.voiceLiveMode));
        btnVoiceTts.setAttribute("aria-pressed", state.voiceLiveMode ? "true" : "false");
        if (!state.voiceLiveMode && typeof window !== "undefined" && "speechSynthesis" in window) {
          window.speechSynthesis.cancel();
          showStatusBanner("Mode Voix Live désactivé.", "info");
        } else {
          showStatusBanner("Mode Voix Live activé : NeoHarness lira les réponses à voix haute.", "success");
          const conv = state.appState && state.appState.active_conversation;
          const msgs = (conv && conv.messages) || [];
          const lastAsst = msgs.slice().reverse().find((m) => m.role === "assistant" && m.content);
          if (lastAsst) speakAssistantReply(lastAsst.content);
        }
      });
    }

    // Lecture automatique à chaque nouveau message assistant si Mode Voix Live actif
    let lastSpokenMsgId = null;
    setInterval(() => {
      if (!state.voiceLiveMode || state.isExecuting) return;
      const conv = state.appState && state.appState.active_conversation;
      const msgs = (conv && conv.messages) || [];
      const lastAsst = msgs.slice().reverse().find((m) => m.role === "assistant" && m.content);
      if (lastAsst && lastAsst.id !== lastSpokenMsgId) {
        lastSpokenMsgId = lastAsst.id;
        speakAssistantReply(lastAsst.content);
      }
    }, 800);

    const btnSentinel = document.getElementById("btn-sentinel-scan");
    const runSentinelScan = async (silent = false) => {
      try {
        const res = await apiGet("/api/sentinel");
        if (res.error_detected && res.suggested_prompt) {
          const inp = document.getElementById("composer-input");
          if (inp && !inp.value.trim()) {
            inp.value = res.suggested_prompt;
            inp.focus();
          }
          showStatusBanner(
            `Sentinelle : anomalie détectée dans ${res.error_source}. Diagnostic pré-rempli dans le compositeur.`,
            "error"
          );
        } else if (!silent) {
          const winTitle = (res.active_window && res.active_window.title) || " Bureau Windows";
          showStatusBanner(
            `Sentinelle : système sain (${(res.terminal_sessions || []).length} terminal actif · Fenêtre : ${winTitle.slice(0, 45)}).`,
            "success"
          );
        }
      } catch (err) {
        if (!silent) showStatusBanner(`Erreur Sentinelle : ${err.message}`, "error");
      }
    };

    if (btnSentinel) {
      btnSentinel.addEventListener("click", () => {
        state.sentinelActive = !state.sentinelActive;
        btnSentinel.classList.toggle("active", Boolean(state.sentinelActive));
        btnSentinel.setAttribute("aria-pressed", state.sentinelActive ? "true" : "false");
        runSentinelScan(false);
      });
    }
    setInterval(() => {
      if (state.sentinelActive && !state.isExecuting) {
        runSentinelScan(true);
      }
    }, 15000);

document.getElementById("btn-new-task").addEventListener("click", async () => {
      state.activeDocument = null;
      state.pdfDocCache = null;
      closeRightPanel();
      await apiPost("/api/conversations/create", { title: "Nouvelle tâche" });
      await refreshFullState();
      document.getElementById("composer-input").focus();
    });
    document.getElementById("btn-brand-home").addEventListener("click", async () => {
      state.activeDocument = null;
      state.pdfDocCache = null;
      closeRightPanel();
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
      const addModelBtn = e.target.closest("#btn-open-add-custom-model, #btn-open-add-custom-model-search, .btn-open-add-custom-model, [data-open-modal='modal-add-custom-model']");
      if (addModelBtn) {
        e.preventDefault();
        e.stopPropagation();
        openModal("modal-add-custom-model");
        return;
      }
      const addLibBtn = e.target.closest("#btn-open-add-library-modal, .btn-add-library-item, [data-open-modal='modal-add-library-item']");
      if (addLibBtn) {
        e.preventDefault();
        e.stopPropagation();
        openModal("modal-add-library-item");
        return;
      }
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

    const topLibraryBtn = document.getElementById("btn-open-library");
    if (topLibraryBtn) {
      topLibraryBtn.addEventListener("click", () => {
        state.inspectorTab = "library";
        switchRightPanelMode("inspector");
        renderInspector();
      });
    }

    const btnOpenAddCustom = document.getElementById("btn-open-add-custom-model");
    if (btnOpenAddCustom) {
      btnOpenAddCustom.addEventListener("click", () => {
        openModal("modal-add-custom-model");
      });
    }

    // Gestion du formulaire d'ajout de modèle personnalisé
    const formAddCustomModel = document.getElementById("form-add-custom-model");
    if (formAddCustomModel) {
      formAddCustomModel.addEventListener("submit", async (e) => {
        e.preventDefault();
        const submitBtn = document.getElementById("btn-submit-add-custom-model");
        if (submitBtn) submitBtn.disabled = true;
        try {
          const provider = document.getElementById("custom-model-provider")?.value || "custom";
          const speed = document.getElementById("custom-model-speed")?.value || "balanced";
          const displayName = document.getElementById("custom-model-name")?.value.trim() || "";
          const modelId = document.getElementById("custom-model-id")?.value.trim() || displayName;
          const endpoint = document.getElementById("custom-model-endpoint")?.value.trim() || "";
          const apiKey = document.getElementById("custom-model-key")?.value.trim() || "";
          const context = parseInt(document.getElementById("custom-model-context")?.value, 10) || 128000;

          const caps = {
            reasoning: document.getElementById("cap-reasoning")?.checked ?? true,
            tools: document.getElementById("cap-tools")?.checked ?? true,
            vision: document.getElementById("cap-vision")?.checked ?? false,
            streaming: document.getElementById("cap-streaming")?.checked ?? true,
            structured_output: document.getElementById("cap-structured")?.checked ?? true,
            context: context
          };

          const payload = {
            id: modelId,
            model_name: modelId,
            display_name: displayName || modelId,
            provider_name: provider.toUpperCase(),
            provider_family: provider,
            endpoint: endpoint,
            api_key: apiKey,
            context: context,
            speed_tier: speed,
            capabilities: caps
          };

          const res = await apiPost("/api/models/custom/add", payload);
          if (res && res.model) {
            closeModal("modal-add-custom-model");
            formAddCustomModel.reset();
            await refreshFullState();
            await apiPost("/api/models/select", { model_id: res.model.id });
            await refreshFullState();
            showStatusBanner(`Modèle « ${res.model.display_name} » ajouté et activé !`, "success");
            const mp = document.getElementById("modal-model-picker");
            if (mp && mp.classList.contains("open")) {
              renderModelPickerModal();
            }
          } else {
            showStatusBanner("Impossible d'enregistrer le modèle personnalisé.", "error");
          }
        } catch (err) {
          showStatusBanner(`Erreur ajout modèle : ${err.message}`, "error");
        } finally {
          if (submitBtn) submitBtn.disabled = false;
        }
      });
    }

    // Gestion du formulaire d'ajout dans la bibliothèque
    const formAddLib = document.getElementById("form-add-library-item");
    if (formAddLib) {
      formAddLib.addEventListener("submit", async (e) => {
        e.preventDefault();
        const submitBtn = document.getElementById("btn-submit-add-library");
        if (submitBtn) submitBtn.disabled = true;
        try {
          const title = document.getElementById("lib-item-title")?.value.trim() || "Sans titre";
          const category = document.getElementById("lib-item-category")?.value || "Notes";
          const rawTags = document.getElementById("lib-item-tags")?.value.trim() || "";
          const tags = rawTags ? rawTags.split(",").map(t => t.trim()).filter(Boolean) : [];
          const content = document.getElementById("lib-item-content")?.value.trim() || "";
          const alsoRemember = document.getElementById("lib-item-remember")?.checked;

          const payload = {
            title: title,
            category: category,
            tags: tags,
            content: content
          };

          const res = await apiPost("/api/library/add", payload);
          if (res && res.item) {
            if (alsoRemember) {
              await apiPost("/api/memory/persistent/add", {
                category: "knowledge",
                content: `${title} : ${content.slice(0, 300)}`,
                linked_resource_id: res.item.id
              });
            }
            closeModal("modal-add-library-item");
            formAddLib.reset();
            await loadLibrary();
            await loadPersistentMemories();
            renderInspectorLibraryTab();
            showStatusBanner(`Élément « ${title} » ajouté à la bibliothèque !`, "success");
          } else {
            showStatusBanner("Impossible d'ajouter l'élément à la bibliothèque.", "error");
          }
        } catch (err) {
          showStatusBanner(`Erreur bibliothèque : ${err.message}`, "error");
        } finally {
          if (submitBtn) submitBtn.disabled = false;
        }
      });
    }

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

    // Sélecteur popover de mode d'exécution (NeoHarness Core / Swift / Deep) style maquette
    const modelPopoverBtn = document.getElementById("btn-composer-model-popover");
    const modelDropdownMenu = document.getElementById("composer-model-dropdown-menu");
    if (modelPopoverBtn && modelDropdownMenu) {
      modelPopoverBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        const isOpen = modelDropdownMenu.style.display !== "none";
        modelDropdownMenu.style.display = isOpen ? "none" : "flex";
      });
      document.addEventListener("click", (e) => {
        if (!modelDropdownMenu.contains(e.target) && !modelPopoverBtn.contains(e.target)) {
          modelDropdownMenu.style.display = "none";
        }
      });
      modelDropdownMenu.querySelectorAll(".model-popover-item[data-exec-mode]").forEach((item) => {
        item.addEventListener("click", async () => {
          const mode = item.getAttribute("data-exec-mode");
          if (mode) {
            await window.setAgentExecutionMode(mode);
          }
          modelDropdownMenu.style.display = "none";
        });
      });
      const popoverFullModels = document.getElementById("popover-open-full-models");
      if (popoverFullModels) {
        popoverFullModels.addEventListener("click", () => {
          modelDropdownMenu.style.display = "none";
          openModal("modal-model-picker");
        });
      }
    }

    // Suggestions de la page d'accueil style maquette
    document.querySelectorAll(".welcome-suggestion-row").forEach((btn) => {
      btn.addEventListener("click", () => {
        const prompt = btn.getAttribute("data-prompt");
        const input = document.getElementById("composer-input");
        if (input && prompt) {
          input.value = prompt;
          input.focus();
          input.dispatchEvent(new Event("input"));
        }
      });
    });

    // Carte utilisateur dans la barre latérale gauche (Alex Martin -> ouvre Paramètres)
    const userProfileCard = document.getElementById("btn-sidebar-user-profile");
    if (userProfileCard) {
      userProfileCard.addEventListener("click", () => {
        openModal("modal-settings");
      });
    }

    // Sélecteur popover de gouvernance (AUTO, ACCEPT, EDIT, PLAN) 100% fonctionnel
    const subheaderGovBtn = document.getElementById("btn-governance-toggle");
    const govDropdownMenu = document.getElementById("governance-dropdown");
    if (subheaderGovBtn && govDropdownMenu) {
      subheaderGovBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        const isOpen = govDropdownMenu.style.display !== "none";
        govDropdownMenu.style.display = isOpen ? "none" : "flex";
      });
      document.addEventListener("click", (e) => {
        if (!govDropdownMenu.contains(e.target) && !subheaderGovBtn.contains(e.target)) {
          govDropdownMenu.style.display = "none";
        }
      });
      govDropdownMenu.querySelectorAll(".gov-option-item[data-gov-mode]").forEach((opt) => {
        opt.addEventListener("click", async () => {
          const mode = opt.getAttribute("data-gov-mode");
          govDropdownMenu.querySelectorAll(".gov-option-item").forEach((o) => {
            o.classList.toggle("active", o.getAttribute("data-gov-mode") === mode);
            const chk = o.querySelector(".gov-check");
            if (chk) chk.style.display = o.getAttribute("data-gov-mode") === mode ? "inline" : "none";
          });
          const badgeLabel = document.getElementById("governance-badge-label");
          if (badgeLabel) badgeLabel.textContent = `Gouvernance : ${mode}`;
          const chipLabel = document.getElementById("governance-chip-label");
          if (chipLabel) chipLabel.textContent = mode;
          await apiPost("/api/mode", { mode: mode });
          await refreshFullState();
          govDropdownMenu.style.display = "none";
          showStatusBanner(`Mode de gouvernance activé à 100 % : ${mode}`, "info");
        });
      });
    }

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

    const globalSearchInput = document.getElementById("global-search-input");
    let currentCmdFilter = "all";
    if (globalSearchInput) {
      globalSearchInput.addEventListener("input", (e) => {
        runGlobalSearch(e.target.value || "", currentCmdFilter);
      });
    }
    document.querySelectorAll(".cmd-filter-pill[data-cmd-filter]").forEach((pill) => {
      pill.addEventListener("click", () => {
        document.querySelectorAll(".cmd-filter-pill").forEach((p) => p.classList.remove("active"));
        pill.classList.add("active");
        currentCmdFilter = pill.getAttribute("data-cmd-filter") || "all";
        const val = globalSearchInput ? globalSearchInput.value : "";
        runGlobalSearch(val, currentCmdFilter);
      });
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
        state.activeDocument = null;
        state.pdfDocCache = null;
        closeRightPanel();
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
        const keyCfAccount = document.getElementById("settings-key-cf-account");
        const keyCfToken = document.getElementById("settings-key-cf-token");
        const credPayload = {};
        if (keyGemini && keyGemini.value.trim()) credPayload.GEMINI_API_KEY = keyGemini.value.trim();
        if (keyOpenai && keyOpenai.value.trim()) credPayload.OPENAI_API_KEY = keyOpenai.value.trim();
        if (keyMistral && keyMistral.value.trim()) credPayload.MISTRAL_API_KEY = keyMistral.value.trim();
        if (keyCfAccount && keyCfAccount.value.trim()) credPayload.CLOUDFLARE_ACCOUNT_ID = keyCfAccount.value.trim();
        if (keyCfToken && keyCfToken.value.trim()) credPayload.CLOUDFLARE_API_TOKEN = keyCfToken.value.trim();
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

// Réception des messages de l'aperçu (Sauvegarde Excel interactive & erreurs runtime)
  window.addEventListener("message", async function (event) {
    if (!event.data) return;
    if (event.data.type === "NEOHARNESS_HTML_RUNTIME_ERROR") {
      const err = event.data.error || {};
      showStatusBanner(
        `Erreur JavaScript dans l'aperçu : ${err.message} (ligne ${err.lineno})`,
        "error"
      );
    } else if (event.data.type === "NEOHARNESS_EXCEL_SAVE") {
      const filename = event.data.filename || "classeur.xlsx";
      const rows = event.data.rows || [];
      if (!rows.length) return;
      const headers = rows[0];
      const dataRows = rows.slice(1);
      try {
        await apiPost("/api/tools/execute", {
          name: "generate_excel",
          arguments: {
            output_path: filename,
            headers: headers,
            rows: dataRows,
            include_formulas: false,
          },
        });
        showStatusBanner(`Classeur Excel "${filename}" enregistré avec succès !`, "success");
      } catch (err) {
        showStatusBanner(`Erreur lors de l'enregistrement d'Excel : ${err.message}`, "error");
      }
    }
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();