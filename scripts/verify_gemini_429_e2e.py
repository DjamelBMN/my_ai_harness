"""
Script de validation complète du comportement 429 et Multi-Agent:
- Mono-Agent avec Gemini
- Multi-Agent
- Plusieurs requêtes concurrentes (queue / sémaphore)
- Simulation d'un 429 avec exponential backoff + jitter
- Simulation d'un 429 avec Retry-After
- Comportement après quota épuisé (arrêt immédiat sans retries inutiles)
- Fallback vers provider de secours
- Vérification de l'ensemble des 5 logs obligatoires
"""
import io
import sys
import time
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
from contextlib import redirect_stdout
from types import SimpleNamespace

from providers.base_provider import BaseProvider
from providers.gemini import GeminiProvider, GeminiProviderError
from core.rate_limit_manager import (
    RateLimitManager,
    RateLimitExhaustedError,
    CircuitBreakerOpenError,
    ExecutionMode,
)

captured_logs = io.StringIO()

print("======================================================================")
print("TEST 1: MONO-AGENT AVEC GEMINI & LOG CONCURRENCE")
print("======================================================================")
prov_mono = GeminiProvider(model="gemini-3.8-flash")
prov_mono._verified = True
prov_mono._client = type("MockClient", (), {
    "models": type("MockModels", (), {
        "generate_content": lambda *a, **k: SimpleNamespace(text="Succès Mono Gemini")
    })()
})()

rlm_mono = RateLimitManager(mode="mono", max_parallel_agents=1, max_parallel_gemini=1)
wrapped_mono = rlm_mono.wrap_provider(prov_mono, agent_name="agent-mono")

with redirect_stdout(captured_logs):
    res_mono = wrapped_mono.generate("Test mono")

print(f"Résultat Mono: {res_mono}")
assert res_mono == "Succès Mono Gemini"
assert "[Orchestrator] Concurrence Gemini : 1/1" in captured_logs.getvalue()
print("-> TEST 1 VALIDE : Mono-Agent s'exécute avec concurrence bornée à 1/1.\n")


print("======================================================================")
print("TEST 2: MULTI-AGENT & CONCURRENCE BORNEE PAR SEMAPHORE")
print("======================================================================")
rlm_multi = RateLimitManager(mode="multi", max_parallel_agents=4, max_parallel_gemini=2)
max_simultaneous = 0
current_simultaneous = 0
lock = threading.Lock()

def simulated_gemini_worker():
    global current_simultaneous, max_simultaneous
    with lock:
        current_simultaneous += 1
        if current_simultaneous > max_simultaneous:
            max_simultaneous = current_simultaneous
    time.sleep(0.05)
    with lock:
        current_simultaneous -= 1
    return "ok multi"

with redirect_stdout(captured_logs):
    threads = [
        threading.Thread(
            target=lambda: rlm_multi.execute_call(simulated_gemini_worker, provider_name="gemini", agent_name="worker")
        )
        for _ in range(8)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

print(f"Concurrence Gemini max observée (sur 8 threads): {max_simultaneous} (limite configurée: 2)")
assert max_simultaneous <= 2
assert "[Orchestrator] Concurrence Gemini : 1/2" in captured_logs.getvalue() or "[Orchestrator] Concurrence Gemini : 2/2" in captured_logs.getvalue()
print("-> TEST 2 VALIDE : Concurrence Multi-Agent strictement contenue à max 2.\n")


print("======================================================================")
print("TEST 3: 429 TEMPORAIRE AVEC BACKOFF + JITTER & RETRY-AFTER")
print("======================================================================")
prov_retry = GeminiProvider(model="gemini-3.8-flash")
prov_retry._verified = True
prov_retry.max_retries = 2
prov_retry.base_backoff_seconds = 0.05

attempts_429 = 0
def fake_call_temporary_429(*a, **k):
    global attempts_429
    attempts_429 += 1
    if attempts_429 < 2:
        err = RuntimeError("429 RESOURCE_EXHAUSTED: Rate limit exceeded. Please retry in 0.15s.")
        setattr(err, "code", 429)
        raise err
    return SimpleNamespace(text="Succès après backoff temporaire")

prov_retry._client = type("MockClient", (), {
    "models": type("MockModels", (), {
        "generate_content": fake_call_temporary_429
    })()
})()

with redirect_stdout(captured_logs):
    res_retry = prov_retry.generate("Calcul exponentiel")

print(f"Tentatives effectuées: {attempts_429}")
print(f"Résultat final: {res_retry}")
assert attempts_429 == 2
assert res_retry == "Succès après backoff temporaire"
assert "[GeminiProvider] 429 détecté" in captured_logs.getvalue()
assert "[GeminiProvider] Retry dans" in captured_logs.getvalue()
print("-> TEST 3 VALIDE : 429 temporaire absorbé avec backoff et retry réussi.\n")


print("======================================================================")
print("TEST 4: QUOTA REELLEMENT EPUISE -> ARRET IMMEDIAT SANS RETRIES INUTILES")
print("======================================================================")
prov_exhausted = GeminiProvider(model="gemini-3.8-flash")
prov_exhausted._verified = True
prov_exhausted.max_retries = 3

attempts_exhausted = 0
def fake_call_exhausted(*a, **k):
    global attempts_exhausted
    attempts_exhausted += 1
    err = RuntimeError("429 RESOURCE_EXHAUSTED: Quota exceeded for quota metric 'GenerateContent requests per day'. Daily limit exceeded.")
    setattr(err, "code", 429)
    raise err

prov_exhausted._client = type("MockClient", (), {
    "models": type("MockModels", (), {
        "generate_content": fake_call_exhausted
    })()
})()

caught_error = None
with redirect_stdout(captured_logs):
    try:
        prov_exhausted.generate("Mission impossible")
    except GeminiProviderError as e:
        caught_error = e

print(f"Tentatives lors d'un quota épuisé: {attempts_exhausted} (doit être 1, pas 3!)")
print(f"Catégorie d'erreur: {getattr(caught_error, 'category', None)}")
assert attempts_exhausted == 1, "Un quota épuisé ne doit PAS boucler 3 retries inutiles !"
assert getattr(caught_error, "category", None) == "quota_exhausted"
assert "[GeminiProvider] Quota épuisé" in captured_logs.getvalue()
print("-> TEST 4 VALIDE : Arrêt immédiat et erreur propre dès détection de quota journalier épuisé.\n")


print("======================================================================")
print("TEST 5: FAILOVER AUTOMATIQUE VERS PROVIDER DE SECOURS")
print("======================================================================")
class MockFailingGemini(BaseProvider):
    def generate(self, prompt: str = "") -> str:
        err = RuntimeError("429 RESOURCE_EXHAUSTED: Daily quota exceeded")
        setattr(err, "code", 429)
        raise err
    def execute(self, instruction: str = "") -> str:
        return self.generate(instruction)
    def get_name(self) -> str:
        return "gemini"
    def get_model_name(self) -> str:
        return "gemini-3.8-flash"

class MockBackupMistral(BaseProvider):
    def generate(self, prompt: str = "") -> str:
        return "Réponse générée avec succès par Mistral (Secours)"
    def execute(self, instruction: str = "") -> str:
        return self.generate(instruction)
    def get_name(self) -> str:
        return "mistral"
    def get_model_name(self) -> str:
        return "mistral-small-latest"

rlm_failover = RateLimitManager(
    mode="multi",
    fallback_enabled=True,
    fallback_provider_resolver=lambda: ("mistral", MockBackupMistral()),
)
wrapped_failing = rlm_failover.wrap_provider(MockFailingGemini(), agent_name="worker")

with redirect_stdout(captured_logs):
    res_failover = wrapped_failing.generate("Fais mon analyse")

print(f"Résultat après bascule: {res_failover}")
assert res_failover == "Réponse générée avec succès par Mistral (Secours)"
assert "[Orchestrator] Fallback provider utilisé" in captured_logs.getvalue()
print("-> TEST 5 VALIDE : Bascule propre vers le provider de secours réussie.\n")


print("======================================================================")
print("TEST 6: VERIFICATION DES 5 FORMATS DE LOGS OBLIGATOIRES")
print("======================================================================")
all_logs = captured_logs.getvalue()
expected_logs = [
    "[GeminiProvider] 429 détecté",
    "[GeminiProvider] Retry dans",
    "[Orchestrator] Concurrence Gemini :",
    "[GeminiProvider] Quota épuisé",
    "[Orchestrator] Fallback provider utilisé",
]
for expected in expected_logs:
    assert expected in all_logs, f"Log manquant : '{expected}'"
    print(f" - Log présent et vérifié : '{expected}'")

print("\nTOUTES LES VALIDATIONS BOUT-EN-BOUT SONT 100% CONFORMES ET RÉUSSIES !")
