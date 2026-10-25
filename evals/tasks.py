from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class EvalTask:
    id: str
    category: str
    prompt: str
    description: str
    expected_files: list[str] = field(default_factory=list)
    initial_files: dict[str, str] = field(default_factory=dict)
    oracle_fn: Callable[[dict[str, Any], Any], tuple[bool, str]] | None = None
    timeout_seconds: float = 30.0


# Oracles déterministes
def oracle_calc(result: dict[str, Any], fs: Any) -> tuple[bool, str]:
    calc_path = fs.resolve("calc.py")
    if not calc_path.is_file():
        return False, "calc.py manquant"
    code = calc_path.read_text(encoding="utf-8")
    if "def add(" not in code:
        return False, "Fonction add non trouvée dans calc.py"
    return True, "add(a, b) correctement implémenté"


def oracle_bugfix(result: dict[str, Any], fs: Any) -> tuple[bool, str]:
    sol = fs.resolve("bank.py")
    if not sol.is_file():
        return False, "bank.py manquant"
    code = sol.read_text(encoding="utf-8")
    if "ZeroDivisionError" in code or "denom == 0" in code or "b == 0" in code or "if" in code:
        return True, "Bug de division prévenu ou géré"
    return False, "Division par zéro non gérée"


def oracle_file_analysis(result: dict[str, Any], fs: Any) -> tuple[bool, str]:
    ans = result.get("answer", "")
    if "100" in ans or "Valence" in ans or "Lyon" in ans:
        return True, "Information extraite du document observée"
    return False, "Donnée documentaire manquante dans la réponse"


EVAL_TASKS: list[EvalTask] = [
    # 1. Code simple (5 tâches)
    EvalTask(
        id="code-01-calc",
        category="code_simple",
        prompt="Écris dans calc.py une fonction add(a, b) et une fonction sub(a, b).",
        description="Fonctions arithmétiques basiques",
        expected_files=["calc.py"],
        oracle_fn=oracle_calc,
    ),
    EvalTask(
        id="code-02-fibonacci",
        category="code_simple",
        prompt="Écris dans fib.py une fonction fib(n) retournant les n premiers termes de Fibonacci.",
        description="Génération de Fibonacci",
        expected_files=["fib.py"],
    ),
    EvalTask(
        id="code-03-merge-sort",
        category="code_simple",
        prompt="Implémente le tri fusion dans merge_sort.py avec une fonction merge_sort(arr).",
        description="Tri fusion",
        expected_files=["merge_sort.py"],
    ),
    EvalTask(
        id="code-04-solow",
        category="code_simple",
        prompt="Écris dans solow.py un script calculant le capital stationnaire k* pour alpha=0.33, s=0.3, n=0.02.",
        description="Modèle de croissance de Solow",
        expected_files=["solow.py"],
    ),
    EvalTask(
        id="code-05-json-parser",
        category="code_simple",
        prompt="Écris un parseur JSON sécurisé avec gestion des erreurs dans parser.py.",
        description="Parseur JSON résistant",
        expected_files=["parser.py"],
    ),

    # 2. Bug fix avec reproduction par test (5 tâches)
    EvalTask(
        id="fix-01-divzero",
        category="bug_fix_with_test",
        prompt="Corrige le bug de division dans bank.py et vérifie avec test_bank.py.",
        description="Division par zéro dans bank.py",
        initial_files={
            "bank.py": "def average_balance(total, count):\n    return total / count\n",
            "test_bank.py": "import unittest\nfrom bank import average_balance\nclass Test(unittest.TestCase):\n    def test_zero(self):\n        self.assertEqual(average_balance(100, 0), 0)\nif __name__ == '__main__': unittest.main()\n",
        },
        expected_files=["bank.py"],
        oracle_fn=oracle_bugfix,
    ),
    EvalTask(
        id="fix-02-off-by-one",
        category="bug_fix_with_test",
        prompt="Corrige le off-by-one dans search.py pour que binary_search trouve le dernier élément.",
        description="Off-by-one binary search",
        initial_files={
            "search.py": "def binary_search(arr, x):\n    low, high = 0, len(arr) - 2\n    while low <= high:\n        mid = (low + high) // 2\n        if arr[mid] == x: return mid\n        elif arr[mid] < x: low = mid + 1\n        else: high = mid - 1\n    return -1\n",
        },
        expected_files=["search.py"],
    ),
    EvalTask(
        id="fix-03-empty-list-stats",
        category="bug_fix_with_test",
        prompt="Dans stats.py, gère proprement les listes vides dans calculate_median(arr).",
        description="Médiane sur liste vide",
        initial_files={
            "stats.py": "def calculate_median(arr):\n    sorted_arr = sorted(arr)\n    return sorted_arr[len(arr) // 2]\n",
        },
        expected_files=["stats.py"],
    ),
    EvalTask(
        id="fix-04-utf8-encoding",
        category="bug_fix_with_test",
        prompt="Assure que read_text_file(path) dans io_helper.py lit avec encoding='utf-8'.",
        description="Lecture avec encodage UTF-8 explicite",
        initial_files={
            "io_helper.py": "def read_text_file(path):\n    with open(path, 'r') as f: return f.read()\n",
        },
        expected_files=["io_helper.py"],
    ),
    EvalTask(
        id="fix-05-regex-validator",
        category="bug_fix_with_test",
        prompt="Corrige la regex dans email_val.py pour accepter les adresses avec sous-domaines.",
        description="Validation email sous-domaine",
        initial_files={
            "email_val.py": "import re\ndef is_valid(email):\n    return bool(re.match(r'^[a-z]+@[a-z]+\\.[a-z]{2,3}$', email))\n",
        },
        expected_files=["email_val.py"],
    ),

    # 3. Factual & RAG Local (5 tâches)
    EvalTask(
        id="rag-01-distance",
        category="factual_rag_web",
        prompt="Lis distance.txt et indique la distance entre Lyon et Valence.",
        description="Extraction factuelle depuis fichier",
        initial_files={"distance.txt": "La distance entre Lyon et Valence est d'environ 100 kilomètres."},
        oracle_fn=oracle_file_analysis,
    ),
    EvalTask(
        id="rag-02-csv-stats",
        category="factual_rag_web",
        prompt="Analyse data.csv et donne la moyenne de la colonne 'note'.",
        description="Calcul de statistique sur CSV",
        initial_files={"data.csv": "nom,note\nAlice,14\nBob,16\nCharlie,18\n"},
    ),
    EvalTask(
        id="rag-03-honest-unknown",
        category="factual_rag_web",
        prompt="Quel est le numéro de série exact du premier satellite artificiel lancé en 2038 ?",
        description="Détection d'inconnue sans hallucination",
    ),
    EvalTask(
        id="rag-04-c-constant",
        category="factual_rag_web",
        prompt="Rappelle la valeur exacte de la vitesse de la lumière dans le vide en m/s.",
        description="Constante physique fondamentale",
    ),
    EvalTask(
        id="rag-05-summary-doc",
        category="factual_rag_web",
        prompt="Résume en 3 points les directives présentes dans policy.txt.",
        description="Synthèse de document local",
        initial_files={"policy.txt": "1. Toujours tester.\n2. Ne jamais falsifier de document.\n3. Respecter les limites de budget.\n"},
    ),

    # 4. Création d'examen avec barème (5 tâches)
    EvalTask(
        id="exam-01-bac-maths",
        category="exam_creation",
        prompt="Rédige un exercice de baccalauréat sur les suites géométriques avec barème sur 5 points.",
        description="Exercice de suites avec barème",
    ),
    EvalTask(
        id="exam-02-algo-assertions",
        category="exam_creation",
        prompt="Crée un problème d'algorithmique sur les piles avec assertions de test.",
        description="Problème algorithmique avec assertions",
    ),
    EvalTask(
        id="exam-03-mcq-physics",
        category="exam_creation",
        prompt="Génère un QCM de 4 questions sur la thermodynamique avec corrigé détaillé.",
        description="QCM de thermodynamique",
    ),
    EvalTask(
        id="exam-04-probabilites",
        category="exam_creation",
        prompt="Rédige un énoncé de probabilités conditionnelles avec arbre de décision pondéré.",
        description="Exercice de probabilités conditionnelles",
    ),
    EvalTask(
        id="exam-05-dm-devoir",
        category="exam_creation",
        prompt="Construis un devoir maison complet de géométrie analytique noté sur 20.",
        description="Devoir maison de géométrie sur 20",
    ),

    # 5. Multi-agent & Délégation (5 tâches)
    EvalTask(
        id="multi-01-coder-tester",
        category="multi_agent_delegation",
        prompt="Code une fonction de factorielle dans math_lib.py et teste-la via delegate_to_agent.",
        description="Délégation Coder vers Tester",
    ),
    EvalTask(
        id="multi-02-review",
        category="multi_agent_delegation",
        prompt="Inspecte complex_code.py et délègue une revue au reviewer.",
        description="Délégation au Reviewer",
        initial_files={"complex_code.py": "def run(x):\n    return eval(x)\n"},
    ),
    EvalTask(
        id="multi-03-full-workflow",
        category="multi_agent_delegation",
        prompt="Orchestre la création, le test et la revue de validation d'un module de chiffrement César.",
        description="Chaîne multi-agents complète",
    ),
    EvalTask(
        id="multi-04-subtasks",
        category="multi_agent_delegation",
        prompt="Décompose en sous-missions l'audit de sécurité des fichiers de configuration.",
        description="Décomposition et synthèse distribuée",
    ),
    EvalTask(
        id="multi-05-critical-audit",
        category="multi_agent_delegation",
        prompt="Effectue un examen contradictoire sur la robustesse du gestionnaire de mots de passe.",
        description="Audit contradictoire par critique",
    ),
]
