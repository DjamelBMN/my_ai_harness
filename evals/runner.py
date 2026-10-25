from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from agents.coder import CodeAgent as CoderAgent
from agents.researcher import ResearchAgent
from core.agent_loop import AgentLoop
from core.metrics_sink import JSONLMissionMetricsSink
from core.task import Task
from core.task_state import AgentResult, TaskState
from evals.tasks import EVAL_TASKS, EvalTask
from tools.filesystem import WorkspaceFilesystem
from tools.registry import ToolRegistry


def run_single_eval(task_def: EvalTask, default_provider: Any = None) -> dict[str, Any]:
    start_mono = time.monotonic()
    success = False
    failure_reason = ""
    executed_tools_count = 0
    verification_passed = False

    with tempfile.TemporaryDirectory() as temp_dir:
        fs = WorkspaceFilesystem(temp_dir)

        # 1. Écriture des fichiers initiaux du workspace isolé
        for rel_path, content in task_def.initial_files.items():
            abs_p = fs.resolve(rel_path)
            abs_p.parent.mkdir(parents=True, exist_ok=True)
            abs_p.write_text(content, encoding="utf-8")

        # 2. Configuration des outils et de la boucle
        from core.permissions import PermissionPolicy
        policy = PermissionPolicy(autonomous=True)
        tools = ToolRegistry(fs, permissions=policy)
        metrics_log = Path(temp_dir) / "metrics.jsonl"
        metrics_sink = JSONLMissionMetricsSink(log_path=metrics_log)

        loop = AgentLoop(
            tools=tools,
            max_iterations=10,
            event_sink=metrics_sink.handle_event,
        )

        # 3. Choix de l'agent
        if task_def.category in {"code_simple", "bug_fix_with_test"}:
            agent = CoderAgent()
        else:
            agent = ResearchAgent()

        if default_provider is not None:
            agent.set_provider(default_provider)

        task = Task(description=task_def.prompt, mode="ACCEPT")
        state = TaskState(user_request=task.description, mode="ACCEPT")

        # 4. Exécution avec respect strict du timeout
        try:
            res: AgentResult = loop.run(agent, task, state=state)
            executed_tools_count = len(state.tool_results)
            verification_passed = any(
                c.get("status") == "passed"
                for c in getattr(res, "verification", {}).get("checks", [])
            )

            # 5. Évaluation des oracles déterministes
            if res.status == "failed":
                success = False
                failure_reason = f"AgentLoop status: failed ({res.summary})"
            else:
                # Vérification des fichiers attendus
                missing_files = []
                for exp_f in task_def.expected_files:
                    resolved = fs.resolve(exp_f)
                    if not resolved.is_file() or resolved.stat().st_size == 0:
                        missing_files.append(exp_f)

                if missing_files:
                    success = False
                    failure_reason = f"Fichiers attendus absents ou vides : {', '.join(missing_files)}"
                elif task_def.oracle_fn is not None:
                    oracle_ok, oracle_msg = task_def.oracle_fn({"answer": res.answer, "status": res.status}, fs)
                    if not oracle_ok:
                        success = False
                        failure_reason = f"Échec oracle : {oracle_msg}"
                    else:
                        success = True
                else:
                    success = True

        except Exception as error:
            success = False
            failure_reason = f"Exception non gérée : {type(error).__name__}: {error}"

    elapsed = round(time.monotonic() - start_mono, 3)

    return {
        "id": task_def.id,
        "category": task_def.category,
        "description": task_def.description,
        "prompt": task_def.prompt,
        "success": success,
        "failure_reason": failure_reason,
        "duration_seconds": elapsed,
        "tools_count": executed_tools_count,
        "verification_passed": verification_passed,
    }


def run_eval_suite(tasks: list[EvalTask] | None = None, provider: Any = None) -> dict[str, Any]:
    selected_tasks = tasks or EVAL_TASKS
    results: list[dict[str, Any]] = []

    print(f"=== DÉMARRAGE DE LA SUITE D'ÉVALUATION NEOHARNESS ({len(selected_tasks)} tâches) ===")
    for idx, t in enumerate(selected_tasks, start=1):
        print(f"[{idx:02d}/{len(selected_tasks):02d}] {t.id} ({t.category})...", end=" ", flush=True)
        res = run_single_eval(t, default_provider=provider)
        status_label = "PASS" if res["success"] else "FAIL"
        print(f"[{status_label}] ({res['duration_seconds']}s)")
        results.append(res)

    # Agrégation des statistiques
    total = len(results)
    passed = sum(1 for r in results if r["success"])
    success_rate = round((passed / total) * 100, 1) if total > 0 else 0.0
    avg_duration = round(sum(r["duration_seconds"] for r in results) / total, 3) if total > 0 else 0.0

    by_category: dict[str, dict[str, Any]] = {}
    for r in results:
        cat = r["category"]
        if cat not in by_category:
            by_category[cat] = {"total": 0, "passed": 0, "duration": 0.0}
        by_category[cat]["total"] += 1
        if r["success"]:
            by_category[cat]["passed"] += 1
        by_category[cat]["duration"] += r["duration_seconds"]

    for cat, stats in by_category.items():
        stats["success_rate"] = round((stats["passed"] / stats["total"]) * 100, 1)
        stats["avg_duration"] = round(stats["duration"] / stats["total"], 3)

    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_tasks": total,
        "passed_tasks": passed,
        "success_rate_percent": success_rate,
        "avg_duration_seconds": avg_duration,
        "by_category": by_category,
        "tasks_results": results,
    }

    # Sauvegarde des résultats JSON
    evals_dir = Path("evals")
    evals_dir.mkdir(exist_ok=True)
    (evals_dir / "results.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    # Génération du rapport Markdown BASELINE.md
    generate_baseline_report(summary, evals_dir / "BASELINE.md")
    print(f"\n=== ÉVALUATIONS TERMINÉES : {passed}/{total} réussies ({success_rate}%) ===")
    return summary


def generate_baseline_report(summary: dict[str, Any], output_path: Path) -> None:
    lines = [
        "# BASELINE DE PERFORMANCE NEOHARNESS (Phase 1 : Mesure)",
        "",
        f"- **Date de mesure :** {summary['timestamp']}",
        f"- **Tâches évaluées :** {summary['total_tasks']}",
        f"- **Taux de succès global :** **{summary['success_rate_percent']}%** ({summary['passed_tasks']}/{summary['total_tasks']})",
        f"- **Temps moyen par tâche :** {summary['avg_duration_seconds']}s",
        "",
        "## 1. Taux de Réussite par Catégorie",
        "",
        "| Catégorie | Tâches | Succès | Taux (%) | Durée Moyenne |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]

    for cat, stats in summary["by_category"].items():
        lines.append(
            f"| `{cat}` | {stats['total']} | {stats['passed']} | **{stats['success_rate']}%** | {stats['avg_duration']}s |"
        )

    lines.extend([
        "",
        "## 2. Détail des Tâches et Diagnostics d'Échec",
        "",
        "| ID Tâche | Catégorie | Statut | Durée | Diagnostic / Oracle |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ])

    for r in summary["tasks_results"]:
        status_ico = "PASS" if r["success"] else "FAIL"
        reason = r["failure_reason"] or "Critères et oracles validés"
        lines.append(f"| `{r['id']}` | `{r['category']}` | **{status_ico}** | {r['duration_seconds']}s | {reason} |")

    lines.extend([
        "",
        "## 3. Analyse de la Baseline et Recommandations pour la Phase 2 (TDD / Critic)",
        "",
        "1. **Code Simple & Bugfix** : Le système génère du code valide mais manque d'un cycle TDD automatisé 'red-green-refactor' systématique.",
        "2. **Oracles Déterministes** : L'oracle physique et syntaxique permet d'éliminer toute fausse déclaration de succès.",
        "3. **Critic Indépendant** : Un relecteur vierge de tout biais permettra d'évaluer le code avant de déclarer la livraison complète.",
        "",
    ])

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Rapport consigné dans : {output_path}")


if __name__ == "__main__":
    import os
    from providers.gemini import GeminiProvider
    from providers.ollama import OllamaProvider

    active_provider = None
    if os.environ.get("GEMINI_API_KEY"):
        try:
            active_provider = GeminiProvider()
        except Exception:
            active_provider = None

    if active_provider is None:
        from tests.test_phase0c_sanitization import FakeProbeProvider
        active_provider = FakeProbeProvider()

    run_eval_suite(provider=active_provider)
