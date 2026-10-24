# RÔLE DE CE FICHIER :
# Établit la relation dynamique Provider -> Model -> Capabilities -> Skills -> Tools
# à partir des Skills, Agents et Tools réellement présents dans le projet.
# Ne simule aucun Skill inexistant et calcule les compatibilités réelles par modèle.

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from core.model_registry import ModelCapabilityRegistry, ModelDescriptor
from skills.loader import SkillDefinition, SkillLoadError, SkillLoader
from skills.registry import SkillRegistry
from tools.registry import ToolRegistry


# Domaines fonctionnels réels rattachés aux 18 Skills existants du projet
SKILL_CATEGORY_MAP: dict[str, dict[str, Any]] = {
    "analyze": {
        "category": "Document Analysis & Architecture",
        "domain_tags": ["Document Analysis", "PDF", "Word", "Spreadsheet", "PowerPoint", "Architecture"],
        "requires_llm": True,
        "requires_tools": True,
        "requires_web": False,
        "requires_multi_provider": False,
    },
    "auto": {
        "category": "Orchestration Automatique",
        "domain_tags": ["Coding", "Document Analysis", "Testing", "Auto-Routing"],
        "requires_llm": True,
        "requires_tools": True,
        "requires_web": False,
        "requires_multi_provider": False,
    },
    "bacblanc": {
        "category": "Mathematics & Education (LaTeX / RAG)",
        "domain_tags": ["Mathematics", "Education", "LaTeX", "PDF", "RAG", "Templates", "Review"],
        "requires_llm": True,
        "requires_tools": True,
        "requires_web": False,
        "requires_multi_provider": False,
    },
    "compare": {
        "category": "Multi-Model Evaluation",
        "domain_tags": ["Comparison", "Review", "Multi-Model"],
        "requires_llm": True,
        "requires_tools": False,
        "requires_web": False,
        "requires_multi_provider": True,
    },
    "context": {
        "category": "Context & Telemetry",
        "domain_tags": ["Context", "Session"],
        "requires_llm": False,
        "requires_tools": False,
        "requires_web": False,
        "requires_multi_provider": False,
    },
    "debug": {
        "category": "Coding & Debugging",
        "domain_tags": ["Coding", "Debugging", "Python", "Testing"],
        "requires_llm": True,
        "requires_tools": True,
        "requires_web": False,
        "requires_multi_provider": False,
    },
    "diagnostic": {
        "category": "System & Git Diagnostics",
        "domain_tags": ["Diagnostics", "Git", "Workspace"],
        "requires_llm": False,
        "requires_tools": False,
        "requires_web": False,
        "requires_multi_provider": False,
    },
    "export": {
        "category": "Document Export (PDF / DOCX / LaTeX / MD)",
        "domain_tags": ["PDF", "Word", "LaTeX", "Markdown", "Export"],
        "requires_llm": False,
        "requires_tools": False,
        "requires_web": False,
        "requires_multi_provider": False,
    },
    "memory": {
        "category": "Memory Management",
        "domain_tags": ["Memory", "Session", "Project"],
        "requires_llm": False,
        "requires_tools": False,
        "requires_web": False,
        "requires_multi_provider": False,
    },
    "mode": {
        "category": "Execution Governance",
        "domain_tags": ["Governance", "Permissions"],
        "requires_llm": False,
        "requires_tools": False,
        "requires_web": False,
        "requires_multi_provider": False,
    },
    "model": {
        "category": "Model Routing Control",
        "domain_tags": ["Routing", "Models"],
        "requires_llm": False,
        "requires_tools": False,
        "requires_web": False,
        "requires_multi_provider": False,
    },
    "plan": {
        "category": "Heuristic Planning",
        "domain_tags": ["Planning", "Intent Analysis"],
        "requires_llm": False,
        "requires_tools": False,
        "requires_web": False,
        "requires_multi_provider": False,
    },
    "refactor": {
        "category": "Coding & Refactoring",
        "domain_tags": ["Coding", "Refactoring", "Testing"],
        "requires_llm": True,
        "requires_tools": True,
        "requires_web": False,
        "requires_multi_provider": False,
    },
    "research": {
        "category": "Web & Document Research",
        "domain_tags": ["Web Research", "Document Analysis", "PDF", "RAG", "Synthesis"],
        "requires_llm": True,
        "requires_tools": True,
        "requires_web": True,
        "requires_multi_provider": False,
    },
    "review": {
        "category": "Code & Document Review",
        "domain_tags": ["Review", "Verification", "Document Analysis"],
        "requires_llm": True,
        "requires_tools": True,
        "requires_web": False,
        "requires_multi_provider": False,
    },
    "route": {
        "category": "Smart Routing & Execution",
        "domain_tags": ["Auto-Routing", "Coding", "Research"],
        "requires_llm": True,
        "requires_tools": True,
        "requires_web": False,
        "requires_multi_provider": False,
    },
    "test": {
        "category": "Testing & Verification",
        "domain_tags": ["Testing", "Python", "Verification"],
        "requires_llm": True,
        "requires_tools": True,
        "requires_web": False,
        "requires_multi_provider": False,
    },
    "workflow": {
        "category": "Multi-Agent Workflow",
        "domain_tags": ["Coding", "Testing", "Review", "Multi-Agent"],
        "requires_llm": True,
        "requires_tools": True,
        "requires_web": False,
        "requires_multi_provider": False,
    },
}


@dataclass
class SkillCompatibilityItem:
    name: str
    slash_command: str
    display_name: str
    description: str
    category: str
    domain_tags: list[str]
    agent_name: str
    execution_mode: str
    required_tools: list[str]
    available_tools: list[str]
    missing_tools: list[str]
    rag_resources: list[str]
    templates: list[str]
    compatible: bool
    compatibility_status: str
    compatibility_reason: str
    compatible_models: list[str] = field(default_factory=list)
    capabilities_used: list[str] = field(default_factory=list)
    source_path: str = ""
    aliases: list[str] = field(default_factory=list)
    requires_mission: bool = True
    canonical_index: int = 999

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SkillCompatibilityEngine:
    """Évalue la compatibilité réelle entre Modèles, Capabilities, Skills et Tools."""

    def __init__(
        self,
        skill_registry: SkillRegistry,
        skill_loader: SkillLoader,
        model_registry: ModelCapabilityRegistry,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        self.skill_registry = skill_registry
        self.skill_loader = skill_loader
        self.model_registry = model_registry
        self.tool_registry = tool_registry

    def _registered_tool_names(self) -> set[str]:
        if self.tool_registry is None:
            return {
                "list_files",
                "find_file",
                "search_files",
                "read_file",
                "read_document",
                "write_file",
                "patch_file",
                "delete_file",
                "move_file",
                "run_tests",
                "run_python",
                "git_status",
                "git_current_branch",
                "git_create_branch",
                "git_commit_staged",
                "git_merge",
                "web_search",
            }
        return {tool.name for tool in self.tool_registry.discover()}

    def _loaded_provider_count(self) -> int:
        router = self.model_registry.router
        if router is None:
            return 0
        seen: set[tuple[str, str]] = set()
        for provider in router.providers.values():
            if provider.get_status_label() == "[NON CONNECTÉ]":
                continue
            seen.add((provider.get_name(), provider.get_model_name()))
        return len(seen)

    def _evaluate_skill_for_model(
        self,
        definition: SkillDefinition,
        model: ModelDescriptor | None,
        all_models: list[ModelDescriptor],
        registered_tools: set[str],
    ) -> SkillCompatibilityItem:
        meta = SKILL_CATEGORY_MAP.get(
            definition.name,
            {
                "category": "Skill Spécialisé",
                "domain_tags": [definition.display_name],
                "requires_llm": bool(definition.agent or definition.dispatch_agent or definition.config.get("auto_route")),
                "requires_tools": bool(definition.tools),
                "requires_web": "web_search" in definition.tools,
                "requires_multi_provider": False,
            },
        )
        requires_llm = bool(meta["requires_llm"])
        requires_tools = bool(meta["requires_tools"])
        requires_web = bool(meta["requires_web"])
        requires_multi = bool(meta["requires_multi_provider"])

        if definition.agent is not None:
            agent_name = definition.agent.name
            exec_mode = "Agent spécialisé dédié"
        elif definition.dispatch_agent:
            agent_map = {
                "coder": "CodeAgent",
                "researcher": "ResearchAgent",
                "reviewer": "ReviewAgent",
                "tester": "TestAgent",
            }
            agent_name = agent_map.get(definition.dispatch_agent, definition.dispatch_agent)
            exec_mode = f"Délégation agent ({agent_name})"
        elif definition.config.get("auto_route"):
            agent_name = "Auto (AgentSelector)"
            exec_mode = "Routage automatique multi-agents"
        else:
            agent_name = "Runtime local (sans LLM)"
            exec_mode = "Commande système locale"

        effective_tools = set(registered_tools)
        if model is not None and model.capabilities.web_grounding:
            effective_tools.add("web_search")
        elif model is None:
            # En mode Auto, Gemini fournit web_search si configuré
            if any(m.capabilities.web_grounding and m.connected for m in all_models):
                effective_tools.add("web_search")

        available_tools = [t for t in definition.tools if t in effective_tools]
        missing_tools = [t for t in definition.tools if t not in effective_tools]

        # Quels modèles du catalogue sont compatibles avec ce Skill ?
        compatible_models: list[str] = []
        for candidate in all_models:
            if not requires_llm:
                compatible_models.append(candidate.display_name)
                continue
            if not candidate.connected:
                continue
            if requires_tools and not candidate.capabilities.tools:
                continue
            compatible_models.append(candidate.display_name)

        capabilities_used: list[str] = []
        compatible = True
        status = "compatible"
        reason = "Compatible avec le modèle sélectionné."

        if model is None:
            # Mode Auto
            if requires_multi and self._loaded_provider_count() < 2:
                compatible = True
                status = "conditionnel"
                reason = (
                    "Exécutable uniquement si au moins 2 providers sont chargés dans la session "
                    f"(actuellement : {self._loaded_provider_count()})."
                )
            else:
                reason = "Sélection automatique du modèle et de l'agent optimaux par le Router."
                capabilities_used = ["Auto-Routing", "Function Calling"]
        else:
            if not requires_llm:
                compatible = True
                status = "compatible_local"
                reason = "Commande locale du Harness (indépendante du LLM)."
                capabilities_used = ["Exécution locale"]
            elif not model.connected:
                compatible = False
                status = "indisponible"
                reason = f"Indisponible : {model.display_name} n'est pas connecté ({model.status_detail})"
            elif requires_tools and not model.capabilities.tools:
                compatible = False
                status = "incompatible"
                reason = f"Le modèle {model.display_name} ne prend pas en charge Function Calling / Tools."
            elif requires_multi and self._loaded_provider_count() < 2:
                compatible = False
                status = "indisponible_session"
                reason = (
                    f"/compare requiert au moins 2 providers chargés en session "
                    f"(actuellement : {self._loaded_provider_count()})."
                )
            else:
                if model.capabilities.reasoning:
                    capabilities_used.append("Raisonnement")
                if requires_tools and model.capabilities.tools:
                    capabilities_used.append("Function Calling")
                if definition.name in {"analyze", "bacblanc", "research", "review"} and model.capabilities.long_context:
                    capabilities_used.append("Long Context")
                if definition.name in {"analyze", "research"} and model.capabilities.vision:
                    capabilities_used.append("Vision / Multimodal")
                if definition.name in {"bacblanc"} and model.capabilities.structured_output:
                    capabilities_used.append("Structured Output")
                if requires_web:
                    if model.capabilities.web_grounding:
                        capabilities_used.append("Google Search Grounding")
                        reason = (
                            f"Pleinement compatible avec {model.display_name} "
                            "(recherche locale + Google Search Grounding natif + web_search)."
                        )
                    elif "web_search" in effective_tools:
                        capabilities_used.append("Web Search HTTP")
                        reason = (
                            f"Pleinement compatible avec {model.display_name} "
                            "(recherche locale + outil web_search HTTP/RSS en temps réel)."
                        )
                    else:
                        status = "compatible_partiel"
                        reason = (
                            f"Compatible en recherche documentaire locale avec {model.display_name} "
                            "(aucun outil web_search actif)."
                        )
                else:
                    reason = f"Pleinement compatible avec {model.display_name} ({', '.join(capabilities_used) or 'Standard'})."

        rag_files = [
            p.relative_to(definition.rag_path).as_posix()
            for p in definition.rag_resources
            if definition.rag_path is not None
        ]
        template_files = [
            p.name for p in definition.available_templates
        ]

        raw_aliases = definition.config.get("aliases", []) if isinstance(definition.config, dict) else []
        aliases = [str(a).strip() for a in raw_aliases if str(a).strip()]
        if f"/{definition.name}" not in aliases:
            aliases.insert(0, f"/{definition.name}")
        requires_mission = definition.name not in {"context", "diagnostic", "memory", "mode", "model"}
        c_index, _ = SkillRegistry.canonical_sort_key(definition.name)

        return SkillCompatibilityItem(
            name=str(definition.name),
            slash_command=f"/{definition.name}",
            display_name=str(definition.display_name or definition.name),
            description=str(definition.description or ""),
            category=str(meta["category"]),
            domain_tags=list(meta["domain_tags"]),
            agent_name=agent_name,
            execution_mode=exec_mode,
            required_tools=list(definition.tools),
            available_tools=available_tools,
            missing_tools=missing_tools,
            rag_resources=rag_files,
            templates=template_files,
            compatible=compatible,
            compatibility_status=status,
            compatibility_reason=reason,
            compatible_models=compatible_models,
            capabilities_used=capabilities_used,
            source_path=f"skills/{definition.name}/skill.md",
            aliases=aliases,
            requires_mission=requires_mission,
            canonical_index=c_index + 1,
        )

    def evaluate_for_model(self, model_identifier: str | None = None) -> dict[str, Any]:
        """Retourne l'arbre complet Provider -> Model -> Capabilities -> Skills -> Tools."""
        all_models = self.model_registry.list_models()
        selected_model: ModelDescriptor | None = None
        is_auto = not model_identifier or model_identifier.strip().casefold() == "auto"

        if not is_auto:
            selected_model = self.model_registry.resolve_model(model_identifier)
        else:
            summary = self.model_registry.active_selection_summary()
            eff = summary.get("effective_model")
            if eff and isinstance(eff, dict):
                selected_model = self.model_registry.resolve_model(eff.get("id"))

        registered_tools = self._registered_tool_names()
        descriptors = self.skill_registry.discover()

        skills_items: list[SkillCompatibilityItem] = []
        load_errors: dict[str, str] = dict(self.skill_registry.invalid)

        for desc in descriptors:
            try:
                definition = self.skill_loader.load(desc)
            except SkillLoadError as error:
                load_errors[desc.name] = str(error)
                continue
            item = self._evaluate_skill_for_model(
                definition,
                selected_model,
                all_models,
                registered_tools,
            )
            skills_items.append(item)

        available_skills = [item.to_dict() for item in skills_items if item.compatible]
        unavailable_skills = [item.to_dict() for item in skills_items if not item.compatible]

        # Synthèse des capacités de domaine (ex: Web Research, Document Analysis, Mathematics, PDF, Coding, RAG...)
        # strictement dérivée des Skills réellement disponibles pour ce modèle.
        domain_summary: list[dict[str, Any]] = []
        domain_Definitions = [
            ("Web Research", "research", "Recherche web (Google Search Grounding) et synthèse documentaire"),
            ("Document Analysis", "analyze", "Extraction et analyse de fichiers (PDF, DOCX, XLSX, PPTX, texte)"),
            ("Mathematics", "bacblanc", "Conception mathématique rigoureuse, sujets, barèmes et corrigés"),
            ("PDF & Bureautique", "export", "Lecture PDF/OCR (read_document) et export PDF/DOCX/LaTeX (/export)"),
            ("Coding & Debugging", "debug", "Inspection, écriture, patch et débogage de code (CodeAgent)"),
            ("RAG & Templates", "bacblanc", "Exploitation des ressources RAG et gabarits LaTeX des Skills"),
            ("Testing & Verification", "test", "Exécution bornée de la suite unittest et scripts Python"),
            ("Code & Output Review", "review", "Revue critique de code et de livrables (ReviewAgent)"),
        ]
        by_name = {item.name: item for item in skills_items}
        for label, backing_skill, desc_text in domain_Definitions:
            skill_obj = by_name.get(backing_skill)
            if skill_obj is None:
                continue
            is_domain_ok = skill_obj.compatible
            note = skill_obj.compatibility_reason
            if label == "Web Research" and selected_model is not None and not selected_model.capabilities.web_grounding and "web_search" not in registered_tools:
                is_domain_ok = False
                note = f"Recherche Web distante non disponible sur {selected_model.display_name} (aucun backend web_search connecté)."
            domain_summary.append(
                {
                    "label": label,
                    "backing_skill": f"/{backing_skill}",
                    "description": desc_text,
                    "available": is_domain_ok,
                    "reason": note,
                }
            )

        return {
            "selection_mode": "auto" if is_auto else "manual",
            "requested_model": model_identifier or "auto",
            "model": selected_model.to_dict() if selected_model else None,
            "provider_chain": {
                "provider": selected_model.provider_family if selected_model else "auto",
                "provider_class": selected_model.provider_class if selected_model else "ModelRouter",
                "model": selected_model.display_name if selected_model else "Auto (ModelRouter)",
                "capabilities": (
                    selected_model.capabilities.enabled_labels()
                    if selected_model
                    else ["Auto-Routing", "Multi-Provider"]
                ),
                "compatible_skills_count": len(available_skills),
                "incompatible_skills_count": len(unavailable_skills),
                "registered_tools_count": len(registered_tools),
            },
            "domain_capabilities": domain_summary,
            "skills": [item.to_dict() for item in skills_items],
            "available_skills": available_skills,
            "unavailable_skills": unavailable_skills,
            "invalid_skills": load_errors,
        }

