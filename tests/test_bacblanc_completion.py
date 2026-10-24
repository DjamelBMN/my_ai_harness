# RÔLE DE CE FICHIER : vérifie les gabarits BacBlanc, le contrôle déterministe de
# complétude et le refus de livrer un sujet partiel par l'AgentLoop.

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from contextlib import redirect_stdout
import io

from core.agent_registry import AgentRegistry
from core.agent_loop import AgentLoop
from core.context import Context
from core.modes import ModeManager
from core.orchestrator import Orchestrator
from core.permissions import PermissionPolicy
from core.router import ModelRouter
from core.task import Task
from providers.base_provider import AgentTurn, BaseProvider, ProviderToolCall
from skills.loader import SkillLoader
from skills.registry import SkillRegistry
from tools.filesystem import WorkspaceFilesystem
from tools.registry import ToolRegistry


class BacBlancProbeProvider(BaseProvider):
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.calls = 0

    def generate(self, prompt: str = "") -> str:
        return self.answer

    def execute(self, instruction: str = "") -> str:
        return "No direct execution."

    def get_name(self) -> str:
        return "BacBlancProbeProvider"

    def get_model_name(self) -> str:
        return "test-only"

    def get_status_label(self) -> str:
        return "[TEST MOCK]"

    def generate_agent_turn(self, prompt, tools, continuation=None, tool_results=None):
        self.calls += 1
        return AgentTurn(text=self.answer)


class BacBlancScriptedProvider(BaseProvider):
    def __init__(self, turns: list[AgentTurn]) -> None:
        self.turns = list(turns)
        self.calls = 0
        self.max_output_tokens = 2048
        self.output_budgets: list[int] = []

    def generate(self, prompt: str = "") -> str:
        return ""

    def execute(self, instruction: str = "") -> str:
        return "No direct execution."

    def get_name(self) -> str:
        return "BacBlancScriptedProvider"

    def get_model_name(self) -> str:
        return "test-only"

    def get_status_label(self) -> str:
        return "[TEST MOCK]"

    def generate_agent_turn(self, prompt, tools, continuation=None, tool_results=None):
        self.calls += 1
        self.output_budgets.append(self.max_output_tokens)
        if not self.turns:
            raise AssertionError("Unexpected provider turn in BacBlanc E2E test.")
        return self.turns.pop(0)


class BacBlancQuotaProvider(BacBlancScriptedProvider):
    def generate_agent_turn(self, prompt, tools, continuation=None, tool_results=None):
        if self.turns:
            return super().generate_agent_turn(prompt, tools, continuation, tool_results)
        self.calls += 1
        self.output_budgets.append(self.max_output_tokens)
        raise RuntimeError("Gemini API quota exceeded (HTTP 429).")


def make_artifacts() -> tuple[str, str]:
    subject = r"""\documentclass{article}
\usepackage[margin=1cm]{geometry}
\newcommand{\exercice}[3]{#2}
\newcommand{\partie}[1]{#1}
\newcommand{\TotalPoints}{20 points}
\begin{document}
\thispagestyle{empty}
\begin{tabularx}{\textwidth}{ll}Sujet & 20 points \\\end{tabularx}
Consigne importante aux surveillants
Consignes aux candidats
\exercice[4]{1}{Analyse}
\begin{enumerate}
\item[1.1] Calculer la dérivée de f(x)=x^2.
\end{enumerate}
\exercice[5]{2}{Probabilités}
\begin{enumerate}
\item[2.1] Calculer une probabilité sur un dé équilibré.
\end{enumerate}
\exercice[6]{3}{Suites}
\begin{enumerate}
\item[3.1] Étudier la suite définie par u_n=n+1.
\end{enumerate}
\exercice[5]{4}{Géométrie}
\begin{enumerate}
\item[4.1] Calculer un produit scalaire dans un repère orthonormé.
\end{enumerate}
\end{document}"""
    grading = r"""\documentclass{article}
\newcommand{\pts}[1]{#1}
\begin{document}
Exercice 1 & Analyse & 4 points \\
Exercice 2 & Probabilités & 5 points \\
Exercice 3 & Suites & 6 points \\
Exercice 4 & Géométrie & 5 points \\
\textbf{TOTAL} & & \textbf{20 points} \\
\begin{tabularx}{\textwidth}{ll}Barème & 20 points \\\end{tabularx}
\begin{longtable}{ll}
\textbf{\large Exercice 1}
\textbf{1.1} & Dérivée & Comme f(x)=x^2, alors f'(x)=2x. & \pts{4}
\textbf{\large Exercice 2}
\textbf{2.1} & Probabilité & Deux issues sur six sont favorables, donc P=1/3. & \pts{5}
\textbf{\large Exercice 3}
\textbf{3.1} & Suite & u_n=n+1 est une suite arithmétique de raison 1. & \pts{6}
\textbf{\large Exercice 4}
\textbf{4.1} & Produit scalaire & Le produit scalaire se calcule par la somme des produits des coordonnées. & \pts{5}
\bottomrule
\textbf{Règles générales de correction}
\end{longtable}
\end{document}"""
    return subject, grading


def make_answer(subject: str, grading: str) -> str:
    return (
        "# Sujet\n### Fichier `bacblanc_sujet.tex`\n```latex\n"
        + subject
        + "\n```\n# Barème\n### Fichier `bacblanc_bareme.tex`\n```latex\n"
        + grading
        + "\n```\n# Corrigé\nCorrigé complet inclus dans le fichier de barème.\n"
        "# Vérification mathématique\nLes calculs et la cohérence du barème ont été relus.\n"
    )


class BacBlancCompletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.project_root = Path(__file__).resolve().parents[1]

    def load_skill(self):
        registry = SkillRegistry.from_directory(self.project_root / "skills")
        return SkillLoader(self.project_root / "skills").load(registry.get("bacblanc"))

    def test_loader_reads_both_real_latex_templates(self) -> None:
        skill = self.load_skill()
        self.assertIn("sujet_bacblanc.tex", skill.template_contents)
        self.assertIn("bareme_bacblanc.tex", skill.template_contents)
        self.assertIn(r"\newcommand{\exercice}", skill.template_contents["sujet_bacblanc.tex"])
        self.assertIn(r"\newcommand{\pts}", skill.template_contents["bareme_bacblanc.tex"])
        self.assertEqual(skill.resource_errors, {})

    def test_bacblanc_slash_mission_requires_complete_deliverable_without_keywords(self) -> None:
        skill = self.load_skill()
        self.assertTrue(
            skill.agent.requires_full_deliverable(
                Task("suite fonction espace", skill=skill)
            )
        )
        self.assertFalse(
            skill.agent.requires_full_deliverable(
                Task("explique ce qu'est un bac blanc")
            )
        )

    def test_complete_artifacts_pass_only_after_full_review(self) -> None:
        skill = self.load_skill()
        subject, grading = make_artifacts()
        answer = make_answer(subject, grading)
        task_text = (
            "Relire l'intégralité du sujet, du barème et du corrigé et rechercher "
            "toute incohérence mathématique, pédagogique ou structurelle.\n"
            + subject
            + "\n"
            + grading
        )
        state = SimpleNamespace(
            delegation_results=[
                {
                    "agent": "ReviewAgent",
                    "status": "answered",
                    "task": task_text,
                    "answer": (
                        "Relecture mathématique intégrale effectuée; les calculs sont "
                        "cohérents et aucune incohérence n'a été détectée."
                    ),
                }
            ],
            tool_results=[],
        )
        report = skill.agent.validate_final_answer(
            answer,
            Task("fais un sujet complet avec correction", skill=skill),
            state=state,
        )
        self.assertTrue(report["complete"], report["missing"])

    def test_validator_rejects_missing_question_solution_and_inconsistent_points(self) -> None:
        subject, grading = make_artifacts()
        skill = self.load_skill()
        missing_question_report = skill.agent._check_template_artifact(
            subject=subject,
            grading=grading.replace(r"\textbf{2.1}", r"\textbf{2.2}"),
        )
        self.assertTrue(
            any("question 2.1 de l'exercice 2" in item for item in missing_question_report),
            missing_question_report,
        )

        inconsistent_report = skill.agent._check_template_artifact(
            subject=subject,
            grading=grading.replace(
                "Exercice 2 & Probabilités & 5 points",
                "Exercice 2 & Probabilités & 4 points",
            ),
        )
        self.assertTrue(
            any("total du barème" in item for item in inconsistent_report),
            inconsistent_report,
        )
        redistributed_points = grading.replace(
            "Exercice 1 & Analyse & 4 points",
            "Exercice 1 & Analyse & 5 points",
        ).replace(
            "Exercice 2 & Probabilités & 5 points",
            "Exercice 2 & Probabilités & 4 points",
        )
        subject_bareme_mismatch = skill.agent._check_template_artifact(
            subject=subject,
            grading=redistributed_points,
        )
        self.assertTrue(
            any("points du sujet et du barème" in item for item in subject_bareme_mismatch),
            subject_bareme_mismatch,
        )

    def test_incomplete_artifact_is_rejected_with_concrete_gaps(self) -> None:
        skill = self.load_skill()
        report = skill.agent.validate_final_answer(
            "# Sujet\nUn seul exercice et aucun corrigé.",
            Task("crée un bac blanc complet", skill=skill),
            state=SimpleNamespace(delegation_results=[], tool_results=[]),
        )
        self.assertFalse(report["complete"])
        self.assertTrue(any("sujet complet" in item for item in report["missing"]))
        self.assertTrue(any("ReviewAgent" in item for item in report["missing"]))

    def test_incomplete_result_is_returned_with_explicit_warning(self) -> None:
        skill = self.load_skill()
        provider = BacBlancProbeProvider("Voici un fragment du sujet : Exercice 4 seulement.")
        skill.agent.set_provider(provider)
        with tempfile.TemporaryDirectory(prefix="bacblanc-incomplete-") as temporary:
            filesystem = WorkspaceFilesystem(Path(temporary))
            tools = ToolRegistry(filesystem, PermissionPolicy(autonomous=True))
            loop = AgentLoop(tools, max_iterations=2, max_retries=0, emit=None)
            result = loop.run(
                skill.agent,
                Task("fais un sujet complet avec correction", skill=skill),
            )

        self.assertEqual(result.status, "incomplete")
        self.assertIn("Exercice 4 seulement", result.answer)
        self.assertIn("ÉCHEC DE LA LIVRAISON COMPLÈTE", result.answer)
        self.assertIn("peut être incomplet ou non vérifié", result.answer)
        self.assertFalse(result.verification["specialized_completeness"]["complete"])
        self.assertEqual(provider.calls, 1)

    def test_skill_limits_extend_short_cli_loop_and_token_budget_temporarily(self) -> None:
        skill = self.load_skill()
        provider = BacBlancScriptedProvider(
            [
                *[
                    AgentTurn(
                        text=f"fragment-{index} ",
                        continuation=f"turn-{index}",
                        partial=True,
                    )
                    for index in range(1, 9)
                ],
                AgentTurn(text="fragment incomplet"),
            ]
        )
        skill.agent.set_provider(provider)
        with tempfile.TemporaryDirectory(prefix="bacblanc-limits-") as temporary:
            filesystem = WorkspaceFilesystem(Path(temporary))
            loop = AgentLoop(
                ToolRegistry(filesystem, PermissionPolicy(autonomous=True)),
                max_iterations=8,
                max_retries=0,
                emit=None,
            )
            result = loop.run(
                skill.agent,
                Task("suite fonction espace", skill=skill),
            )

        self.assertEqual(result.status, "incomplete")
        self.assertEqual(provider.calls, 9)
        self.assertEqual(provider.output_budgets, [16_384] * 9)
        self.assertEqual(provider.max_output_tokens, 2048)
        self.assertIn("ÉCHEC DE LA LIVRAISON COMPLÈTE", result.answer)
        self.assertIn("fragment-1", result.answer)

    def test_provider_quota_returns_best_partial_text_and_names_the_cause(self) -> None:
        skill = self.load_skill()
        provider = BacBlancQuotaProvider(
            [
                AgentTurn(
                    text="Début de sujet déjà rédigé : exercice sur les suites.",
                    continuation="partial-1",
                    partial=True,
                )
            ]
        )
        skill.agent.set_provider(provider)
        with tempfile.TemporaryDirectory(prefix="bacblanc-quota-") as temporary:
            loop = AgentLoop(
                ToolRegistry(
                    WorkspaceFilesystem(Path(temporary)),
                    PermissionPolicy(autonomous=True),
                ),
                max_iterations=20,
                max_retries=2,
                emit=None,
            )
            result = loop.run(
                skill.agent,
                Task("suite fonction espace", skill=skill),
            )

        self.assertEqual(result.status, "incomplete")
        self.assertIn("quota exceeded (HTTP 429)", result.answer)
        self.assertIn("Début de sujet déjà rédigé", result.answer)
        self.assertIn("peut être incomplet ou non vérifié", result.answer)
        self.assertFalse(result.verification["specialized_completeness"]["complete"])
        self.assertEqual(provider.calls, 2)

    def test_iteration_exhaustion_returns_best_partial_with_warning(self) -> None:
        skill = self.load_skill()
        skill.agent.skill_config["max_iterations"] = 1
        provider = BacBlancScriptedProvider(
            [
                AgentTurn(
                    text="Exercice 1 partiellement rédigé.",
                    continuation="partial-1",
                    partial=True,
                )
            ]
        )
        skill.agent.set_provider(provider)
        with tempfile.TemporaryDirectory(prefix="bacblanc-iteration-limit-") as temporary:
            loop = AgentLoop(
                ToolRegistry(
                    WorkspaceFilesystem(Path(temporary)),
                    PermissionPolicy(autonomous=True),
                ),
                max_iterations=1,
                max_retries=0,
                emit=None,
            )
            result = loop.run(
                skill.agent,
                Task("suite fonction espace", skill=skill),
            )

        self.assertEqual(result.status, "incomplete")
        self.assertIn("limite de 1 tours agentiques", result.answer)
        self.assertIn("Exercice 1 partiellement rédigé.", result.answer)
        self.assertIn("peut être incomplet ou non vérifié", result.answer)
        self.assertTrue(result.verification["partial_delivery"])

    def test_provider_quota_includes_partial_file_already_written(self) -> None:
        skill = self.load_skill()
        partial_path = "workspace/bacblanc_sujet.tex"
        partial_file = r"\documentclass{article}\begin{document}Sujet partiel"
        provider = BacBlancQuotaProvider(
            [
                AgentTurn(
                    tool_calls=[
                        ProviderToolCall(
                            "write_file",
                            {"path": partial_path, "content": partial_file},
                            "partial-subject",
                        )
                    ]
                )
            ]
        )
        skill.agent.set_provider(provider)
        with tempfile.TemporaryDirectory(prefix="bacblanc-quota-file-") as temporary:
            filesystem = WorkspaceFilesystem(Path(temporary))
            loop = AgentLoop(
                ToolRegistry(filesystem, PermissionPolicy(autonomous=True)),
                max_iterations=20,
                max_retries=0,
                emit=None,
            )
            result = loop.run(
                skill.agent,
                Task("suite fonction espace", skill=skill),
            )

            self.assertEqual(filesystem.read_file(partial_path), partial_file)

        self.assertEqual(result.status, "incomplete")
        self.assertIn(partial_path, result.answer)
        self.assertIn(partial_file, result.answer)
        self.assertIn("complétude non vérifiée", result.answer)
        self.assertIn("quota exceeded (HTTP 429)", result.answer)

    def test_e2e_produces_files_reviews_both_and_delivers_only_after_validation(self) -> None:
        skill = self.load_skill()
        subject, grading = make_artifacts()
        subject_path = "workspace/bacblanc_sujet.tex"
        grading_path = "workspace/bacblanc_bareme.tex"
        final_answer = (
            "# Sujet complet\n"
            f"Fichier : {subject_path}\n"
            "# Barème\nTotal exact : 20 points.\n"
            f"Fichier : {grading_path}\n"
            "# Corrigé\nLes corrections détaillées des exercices 1 à 4 sont dans le fichier.\n"
            "# Vérification mathématique\nLes calculs, le total et la cohérence ont été relus."
        )
        review_task = (
            "Revue complète. Relire l'intégralité du sujet, du barème et du corrigé "
            "et rechercher toute incohérence mathématique, pédagogique ou structurelle. "
            f"Lis en entier les fichiers {subject_path} et {grading_path}."
        )
        provider = BacBlancScriptedProvider(
            [
                AgentTurn(
                    tool_calls=[
                        ProviderToolCall(
                            "write_file",
                            {"path": subject_path, "content": subject},
                            "write-subject",
                        ),
                        ProviderToolCall(
                            "write_file",
                            {"path": grading_path, "content": grading},
                            "write-grading",
                        ),
                    ]
                ),
                AgentTurn(
                    tool_calls=[
                        ProviderToolCall(
                            "delegate_to_agent",
                            {"agent": "reviewer", "task": review_task},
                            "delegate-review",
                        )
                    ]
                ),
                AgentTurn(
                    tool_calls=[
                        ProviderToolCall("read_file", {"path": subject_path}, "read-subject"),
                        ProviderToolCall("read_file", {"path": grading_path}, "read-grading"),
                    ]
                ),
                AgentTurn(
                    text=(
                        "Relecture mathématique intégrale effectuée : les calculs sont "
                        "cohérents et aucune incohérence n'a été détectée."
                    )
                ),
                AgentTurn(text=final_answer),
            ]
        )
        generic_agents = AgentRegistry.from_package()
        router = ModelRouter(
            {"session": provider},
            {agent.routing_key: "session" for agent in generic_agents.list_agents()},
            default_provider="session",
        )
        orchestrator = Orchestrator(generic_agents, router, context=Context())

        with tempfile.TemporaryDirectory(prefix="bacblanc-e2e-") as temporary:
            filesystem = WorkspaceFilesystem(Path(temporary))
            permissions = PermissionPolicy(autonomous=True)
            ModeManager(permissions, "AUTO")
            loop = AgentLoop(
                ToolRegistry(filesystem, permissions),
                max_iterations=8,
                max_retries=1,
                emit=print,
            )
            terminal = io.StringIO()
            with redirect_stdout(terminal):
                result = orchestrator.run_agentic(
                    Task("fais un sujet complet avec correction", skill=skill),
                    loop,
                )
            self.assertTrue(filesystem.resolve(subject_path).is_file())
            self.assertTrue(filesystem.resolve(grading_path).is_file())

        self.assertNotEqual(result.status, "incomplete")
        self.assertIn(
            "specialized_completeness",
            result.verification,
            f"status={result.status}; verification={result.verification}; output={terminal.getvalue()}",
        )
        self.assertTrue(result.verification["specialized_completeness"]["complete"])
        self.assertIn("[MODE] AUTO", terminal.getvalue())
        self.assertIn("[COMPLETENESS] PASS", terminal.getvalue())
        self.assertIn("[DELEGATION] BacBlancAgent -> ReviewAgent", terminal.getvalue())
        self.assertIn(subject_path, result.answer)
        self.assertIn(grading_path, result.answer)
        self.assertEqual(provider.calls, 5)
        self.assertEqual(
            provider.output_budgets,
            [16_384, 16_384, 2048, 2048, 16_384],
        )


if __name__ == "__main__":
    unittest.main()
