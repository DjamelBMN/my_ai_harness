"""Unit tests covering the 10 mandatory requirements for Mono/Multi Agent Modes
and the Centralized RateLimitManager in NeoHarness AI.
"""

from __future__ import annotations

import threading
import time
import unittest
from typing import Any

from core.dag_engine import AsyncDAGEngine, DAGNode, TaskDAG
from core.rate_limit_manager import (
    CircuitBreakerOpenError,
    CircuitState,
    ExecutionMode,
    RateLimitExhaustedError,
    RateLimitManager,
    attach_rate_limit_to_provider,
)


class TestRateLimitAndAgentModes(unittest.TestCase):
    """Suite de tests couvrant strictement les 10 exigences du système agentique."""

    # -------------------------------------------------------------------------
    # 1. test_mono_mode_allows_one_agent
    # -------------------------------------------------------------------------
    def test_mono_mode_allows_one_agent(self):
        """Vérifie qu'en mode Mono, 1 seul agent peut s'exécuter à la fois."""
        rlm = RateLimitManager(mode="mono", max_parallel_agents=1)
        self.assertEqual(rlm.mode, ExecutionMode.MONO)
        self.assertEqual(rlm.max_parallel_agents, 1)

        active_count = 0
        max_active_observed = 0
        lock = threading.Lock()

        def worker_job():
            nonlocal active_count, max_active_observed
            with rlm.acquire_slot(agent_name="agent-mono", provider_name="gemini"):
                with lock:
                    active_count += 1
                    if active_count > max_active_observed:
                        max_active_observed = active_count
                time.sleep(0.04)
                with lock:
                    active_count -= 1

        threads = [threading.Thread(target=worker_job) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(max_active_observed, 1, "En mode Mono, la concurrence maximale doit être de 1.")

    # -------------------------------------------------------------------------
    # 2. test_multi_mode_respects_max_parallel_agents
    # -------------------------------------------------------------------------
    def test_multi_mode_respects_max_parallel_agents(self):
        """Vérifie qu'en mode Multi avec N=2 agents max, jamais plus de 2 agents ne tournent simultanément."""
        rlm = RateLimitManager(mode="multi", max_parallel_agents=2)
        self.assertEqual(rlm.mode, ExecutionMode.MULTI)
        self.assertEqual(rlm.max_parallel_agents, 2)

        active_count = 0
        max_active_observed = 0
        lock = threading.Lock()

        def worker_job():
            nonlocal active_count, max_active_observed
            with rlm.acquire_slot(agent_name="agent-multi", provider_name="gemini"):
                with lock:
                    active_count += 1
                    if active_count > max_active_observed:
                        max_active_observed = active_count
                time.sleep(0.05)
                with lock:
                    active_count -= 1

        threads = [threading.Thread(target=worker_job) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertLessEqual(
            max_active_observed, 2,
            f"En mode Multi (max=2), la concurrence maximale observée ({max_active_observed}) ne doit jamais dépasser 2."
        )

    # -------------------------------------------------------------------------
    # 3. test_rate_limit_queue
    # -------------------------------------------------------------------------
    def test_rate_limit_queue(self):
        """Vérifie la mise en attente (FIFO) des requêtes excédentaires."""
        rlm = RateLimitManager(mode="mono", max_parallel_agents=1)
        execution_order = []
        lock = threading.Lock()
        hold_slot = threading.Event()
        first_entered = threading.Event()

        def first_worker():
            with rlm.acquire_slot(agent_name="first", provider_name="gemini"):
                first_entered.set()
                hold_slot.wait(timeout=2.0)
                with lock:
                    execution_order.append(1)

        def subsequent_worker(idx: int):
            with rlm.acquire_slot(agent_name=f"worker-{idx}", provider_name="gemini"):
                with lock:
                    execution_order.append(idx)

        t1 = threading.Thread(target=first_worker)
        t1.start()
        self.assertTrue(first_entered.wait(timeout=1.0))

        # Vérifier que le slot est occupé
        state_during = rlm.get_state()
        self.assertEqual(state_during["active_calls"], 1)

        # Lancer t2 qui doit être mis en file d'attente
        t2 = threading.Thread(target=subsequent_worker, args=(2,))
        t2.start()
        time.sleep(0.04)

        # La requête est bien en attente dans la queue
        self.assertGreaterEqual(rlm.get_state()["queued_calls"], 1)

        # Libérer t1
        hold_slot.set()
        t1.join()
        t2.join()

        self.assertEqual(execution_order, [1, 2])
        self.assertEqual(rlm.get_state()["queued_calls"], 0)
        self.assertEqual(rlm.get_state()["active_calls"], 0)

    # -------------------------------------------------------------------------
    # 4. test_429_backoff
    # -------------------------------------------------------------------------
    def test_429_backoff(self):
        """Vérifie l'augmentation exponentielle des délais (1s, 2s, 4s...) en cas de 429."""
        rlm = RateLimitManager(mode="mono")
        base = 1.0

        # Sans jitter (facteur jitter = 0)
        d1 = rlm.calculate_backoff_delay(attempt=1, base_delay=base, jitter=False)
        d2 = rlm.calculate_backoff_delay(attempt=2, base_delay=base, jitter=False)
        d3 = rlm.calculate_backoff_delay(attempt=3, base_delay=base, jitter=False)
        d4 = rlm.calculate_backoff_delay(attempt=4, base_delay=base, jitter=False)

        self.assertEqual(d1, 1.0)
        self.assertEqual(d2, 2.0)
        self.assertEqual(d3, 4.0)
        self.assertEqual(d4, 8.0)

        # Avec jitter : chaque tentative reste strictement inférieure à la suivante
        j1 = rlm.calculate_backoff_delay(attempt=1, base_delay=base, jitter=True)
        j2 = rlm.calculate_backoff_delay(attempt=2, base_delay=base, jitter=True)
        j3 = rlm.calculate_backoff_delay(attempt=3, base_delay=base, jitter=True)

        self.assertLess(j1, j2)
        self.assertLess(j2, j3)

    # -------------------------------------------------------------------------
    # 5. test_429_jitter
    # -------------------------------------------------------------------------
    def test_429_jitter(self):
        """Vérifie la présence d'un jitter aléatoire pour désynchroniser les agents."""
        rlm = RateLimitManager(mode="multi", max_parallel_agents=2)
        attempt = 2  # base delay = 2.0s
        delays = [rlm.calculate_backoff_delay(attempt=attempt, base_delay=1.0, jitter=True) for _ in range(15)]

        # Toutes les valeurs ne doivent pas être identiques
        unique_delays = set(round(d, 4) for d in delays)
        self.assertGreater(len(unique_delays), 1, "Le jitter doit produire des délais diversifiés.")

        # Chaque valeur doit rester bornée entre 75% et 125% du délai nominal (2.0s +/- 25%)
        for d in delays:
            self.assertGreaterEqual(d, 1.5 - 0.05)
            self.assertLessEqual(d, 2.5 + 0.05)

    # -------------------------------------------------------------------------
    # 6. test_circuit_breaker
    # -------------------------------------------------------------------------
    def test_circuit_breaker(self):
        """Vérifie le basculement en état OPEN après plusieurs 429 consécutifs."""
        rlm = RateLimitManager(
            mode="mono",
            max_consecutive_429=3,
            cooldown_after_429=60.0,
            fallback_enabled=False,
        )
        provider = "gemini"

        # Au départ, circuit fermé
        status = rlm.get_provider_status(provider)
        self.assertEqual(status.circuit_state, CircuitState.CLOSED)
        self.assertTrue(rlm.is_provider_available(provider))

        # Enregistrer 2 erreurs 429
        rlm.record_429(provider)
        rlm.record_429(provider)
        self.assertEqual(status.circuit_state, CircuitState.CLOSED)
        self.assertTrue(rlm.is_provider_available(provider))

        # 3e erreur consécutive -> Déclenchement du Circuit Breaker -> OPEN
        rlm.record_429(provider)
        self.assertEqual(status.circuit_state, CircuitState.OPEN)
        self.assertFalse(rlm.is_provider_available(provider))
        self.assertTrue(status.is_cooling_down)

    # -------------------------------------------------------------------------
    # 7. test_provider_cooldown
    # -------------------------------------------------------------------------
    def test_provider_cooldown(self):
        """Vérifie le respect de la durée de cooldown avant de réautoriser un provider."""
        cooldown_sec = 0.15
        rlm = RateLimitManager(
            mode="mono",
            max_consecutive_429=2,
            cooldown_after_429=cooldown_sec,
            fallback_enabled=False,
        )
        provider = "gemini_free"

        # Faire disjoncter le circuit
        rlm.record_429(provider)
        rlm.record_429(provider)

        status = rlm.get_provider_status(provider)
        self.assertEqual(status.circuit_state, CircuitState.OPEN)
        self.assertFalse(rlm.is_provider_available(provider))

        # Attendre l'expiration du cooldown
        time.sleep(cooldown_sec + 0.05)

        # Dès expiration du cooldown, le provider redevient disponible (transition test)
        self.assertTrue(
            rlm.is_provider_available(provider),
            "Le provider doit redevenir disponible une fois la durée de cooldown écoulée."
        )

    # -------------------------------------------------------------------------
    # 8. test_no_uncontrolled_parallel_calls
    # -------------------------------------------------------------------------
    def test_no_uncontrolled_parallel_calls(self):
        """Vérifie l'absence d'explosion d'appels même en cas de rafale soudaine."""
        max_parallel = 2
        rlm = RateLimitManager(mode="multi", max_parallel_agents=max_parallel)

        max_concurrent_seen = 0
        current_concurrent = 0
        lock = threading.Lock()
        completed_tasks = 0

        def burst_task():
            nonlocal max_concurrent_seen, current_concurrent, completed_tasks
            with rlm.acquire_slot(agent_name="burst-agent", provider_name="gemini"):
                with lock:
                    current_concurrent += 1
                    if current_concurrent > max_concurrent_seen:
                        max_concurrent_seen = current_concurrent
                time.sleep(0.03)
                with lock:
                    current_concurrent -= 1
                    completed_tasks += 1

        # Rafale de 16 threads lancés en même temps
        threads = [threading.Thread(target=burst_task) for _ in range(16)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(completed_tasks, 16)
        self.assertLessEqual(
            max_concurrent_seen, max_parallel,
            f"La concurrence ({max_concurrent_seen}) ne doit jamais dépasser max_parallel ({max_parallel})."
        )

    # -------------------------------------------------------------------------
    # 9. test_dag_mono_execution
    # -------------------------------------------------------------------------
    def test_dag_mono_execution(self):
        """Vérifie qu'un graphe DAG s'exécute séquentiellement en mode Mono sans perdre ses dépendances."""
        rlm = RateLimitManager(mode="mono", max_parallel_agents=1)
        dag_engine = AsyncDAGEngine(
            execution_mode="mono",
            max_parallel_agents=1,
            rate_limit_manager=rlm,
        )

        execution_log = []
        lock = threading.Lock()

        def worker_fn(ctx: dict[str, Any]) -> dict[str, Any]:
            node_id = ctx["id"]
            time.sleep(0.03)
            with lock:
                execution_log.append(node_id)
            return {"status": "success", "summary": f"Finished {node_id}"}

        dag = TaskDAG(mission_id="mono_mission")
        dag.add_node(DAGNode(id="node_a", agent="worker", title="Tâche A"))
        dag.add_node(DAGNode(id="node_b", agent="worker", title="Tâche B"))
        dag.add_node(DAGNode(id="node_c", agent="worker", title="Tâche C Synthèse", dependencies=["node_a", "node_b"]))

        result = dag_engine.execute_dag(dag, worker_executors={"worker": worker_fn})
        self.assertTrue(result["success"])
        self.assertEqual(len(result["completed_nodes"]), 3)

        # En mode Mono, C doit impérativement s'exécuter après A et B
        self.assertEqual(execution_log[-1], "node_c")
        self.assertIn("node_a", execution_log[:2])
        self.assertIn("node_b", execution_log[:2])

    # -------------------------------------------------------------------------
    # 10. test_dag_multi_execution
    # -------------------------------------------------------------------------
    def test_dag_multi_execution(self):
        """Vérifie qu'un graphe DAG exécute les branches indépendantes en parallèle borné par max_parallel_agents."""
        rlm = RateLimitManager(mode="multi", max_parallel_agents=3)
        dag_engine = AsyncDAGEngine(
            execution_mode="multi",
            max_parallel_agents=3,
            rate_limit_manager=rlm,
        )

        active_parallel = 0
        max_parallel_reached = 0
        lock = threading.Lock()

        def parallel_worker_fn(ctx: dict[str, Any]) -> dict[str, Any]:
            nonlocal active_parallel, max_parallel_reached
            with lock:
                active_parallel += 1
                if active_parallel > max_parallel_reached:
                    max_parallel_reached = active_parallel
            time.sleep(0.06)
            with lock:
                active_parallel -= 1
            return {"status": "success", "summary": f"Done {ctx['id']}"}

        dag = TaskDAG(mission_id="multi_mission")
        dag.add_node(DAGNode(id="task_1", agent="worker", title="Branche 1"))
        dag.add_node(DAGNode(id="task_2", agent="worker", title="Branche 2"))
        dag.add_node(DAGNode(id="task_3", agent="worker", title="Branche 3"))
        dag.add_node(DAGNode(id="task_final", agent="worker", title="Validation Finale", dependencies=["task_1", "task_2", "task_3"]))

        t_start = time.monotonic()
        result = dag_engine.execute_dag(dag, worker_executors={"worker": parallel_worker_fn})
        t_duration = time.monotonic() - t_start

        self.assertTrue(result["success"])
        self.assertEqual(len(result["completed_nodes"]), 4)

        # La concurrence doit avoir atteint plus de 1 (les branches indépendantes ont tourné en parallèle)
        self.assertGreater(
            max_parallel_reached, 1,
            f"Les branches indépendantes doivent s'exécuter en parallèle (max atteint: {max_parallel_reached})."
        )
        self.assertLessEqual(
            max_parallel_reached, 3,
            f"La concurrence ne doit pas excéder max_parallel_agents (max atteint: {max_parallel_reached})."
        )



    # -------------------------------------------------------------------------
    # 11. test_gemini_provider_429_temporary_exponential_backoff
    # -------------------------------------------------------------------------
    def test_gemini_provider_429_temporary_exponential_backoff(self):
        """Vérifie le backoff exponentiel avec jitter et les logs [GeminiProvider] 429 détecté."""
        import io
        from contextlib import redirect_stdout
        from providers.gemini import GeminiProvider, GeminiProviderError

        prov = GeminiProvider(model="gemini-3.8-flash")
        prov._verified = True
        prov.base_backoff_seconds = 0.05
        prov.max_retries = 2

        call_count = 0
        def fake_generate_content(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                # 429 temporaire
                err = RuntimeError("429 RESOURCE_EXHAUSTED: Rate limit reached. Please retry in 0.1s.")
                setattr(err, "code", 429)
                raise err
            from types import SimpleNamespace
            return SimpleNamespace(text="Réponse après retry")

        prov._client = type("MockClient", (), {"models": type("MockModels", (), {"generate_content": fake_generate_content})()})()

        f = io.StringIO()
        with redirect_stdout(f):
            resp = prov.generate("Calcul 1+1")
        output = f.getvalue()

        self.assertEqual(resp, "Réponse après retry")
        self.assertIn("[GeminiProvider] 429 détecté", output)
        self.assertIn("[GeminiProvider] Retry dans", output)
        self.assertEqual(call_count, 2)

    # -------------------------------------------------------------------------
    # 12. test_gemini_provider_respects_retry_after
    # -------------------------------------------------------------------------
    def test_gemini_provider_respects_retry_after(self):
        """Vérifie l'extraction précise et le respect du délai Retry-After fourni par l'API."""
        from providers.gemini import extract_gemini_retry_after
        from core.rate_limit_manager import extract_retry_after

        # Header HTTP
        err1 = RuntimeError("Too Many Requests")
        setattr(err1, "headers", {"Retry-After": "4.5"})
        self.assertEqual(extract_gemini_retry_after(err1), 4.5)
        self.assertEqual(extract_retry_after(err1), 4.5)

        # Message string
        err2 = RuntimeError("429 RESOURCE_EXHAUSTED: Please retry in 12.3s.")
        self.assertEqual(extract_gemini_retry_after(err2), 12.3)
        self.assertEqual(extract_retry_after(err2), 12.3)

    # -------------------------------------------------------------------------
    # 13. test_gemini_provider_quota_exhausted_stops_immediately
    # -------------------------------------------------------------------------
    def test_gemini_provider_quota_exhausted_stops_immediately(self):
        """Vérifie qu'un quota réellement épuisé (journalier) arrête immédiatement les retries."""
        import io
        from contextlib import redirect_stdout
        from providers.gemini import GeminiProvider, GeminiProviderError

        prov = GeminiProvider(model="gemini-3.8-flash")
        prov._verified = True
        prov.max_retries = 3

        call_count = 0
        def fake_generate_exhausted(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            err = RuntimeError("429 RESOURCE_EXHAUSTED: Quota exceeded for quota metric 'GenerateContent requests per day'. Daily quota exceeded.")
            setattr(err, "code", 429)
            raise err

        prov._client = type("MockClient", (), {"models": type("MockModels", (), {"generate_content": fake_generate_exhausted})()})()

        f = io.StringIO()
        with redirect_stdout(f):
            with self.assertRaises(GeminiProviderError) as ctx:
                prov.generate("Bonjour")
        output = f.getvalue()

        self.assertIn("[GeminiProvider] Quota épuisé", output)
        self.assertEqual(ctx.exception.category, "quota_exhausted")
        self.assertTrue(ctx.exception.is_quota_exhausted)
        # Arrêt immédiat : un seul appel effectué, pas 3 retries inutiles !
        self.assertEqual(call_count, 1)

    # -------------------------------------------------------------------------
    # 14. test_multi_agent_gemini_concurrency_semaphore
    # -------------------------------------------------------------------------
    def test_multi_agent_gemini_concurrency_semaphore(self):
        """Vérifie la limitation stricte de concurrence Gemini en Multi-Agent avec log [Orchestrator] Concurrence Gemini."""
        import io
        from contextlib import redirect_stdout

        rlm = RateLimitManager(mode="multi", max_parallel_agents=4, max_parallel_gemini=2)
        active_gemini = 0
        max_gemini_observed = 0
        lock = threading.Lock()

        def fake_gemini_call():
            nonlocal active_gemini, max_gemini_observed
            with lock:
                active_gemini += 1
                if active_gemini > max_gemini_observed:
                    max_gemini_observed = active_gemini
            time.sleep(0.04)
            with lock:
                active_gemini -= 1
            return "ok"

        f = io.StringIO()
        with redirect_stdout(f):
            threads = [
                threading.Thread(
                    target=lambda: rlm.execute_call(fake_gemini_call, provider_name="gemini", agent_name="worker")
                )
                for _ in range(6)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        output = f.getvalue()

        self.assertLessEqual(max_gemini_observed, 2, f"Concurrence Gemini max dépassée: {max_gemini_observed} > 2")
        self.assertIn("[Orchestrator] Concurrence Gemini :", output)

    # -------------------------------------------------------------------------
    # 15. test_fallback_provider_on_failure
    # -------------------------------------------------------------------------
    def test_fallback_provider_on_failure(self):
        """Vérifie le repli propre vers un provider de secours et le log [Orchestrator] Fallback provider utilisé."""
        import io
        from contextlib import redirect_stdout
        from providers.base_provider import BaseProvider

        class PrimaryGemini(BaseProvider):
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

        class SecondaryMistral(BaseProvider):
            def generate(self, prompt: str = "") -> str:
                return "Réponse de secours Mistral"
            def execute(self, instruction: str = "") -> str:
                return self.generate(instruction)
            def get_name(self) -> str:
                return "mistral"
            def get_model_name(self) -> str:
                return "mistral-small-latest"

        primary = PrimaryGemini()
        secondary = SecondaryMistral()

        rlm = RateLimitManager(
            mode="multi",
            fallback_enabled=True,
            fallback_provider_resolver=lambda: ("mistral", secondary),
        )

        wrapped = rlm.wrap_provider(primary, agent_name="test-agent")

        f = io.StringIO()
        with redirect_stdout(f):
            result = wrapped.generate("Test prompt")
        output = f.getvalue()

        self.assertEqual(result, "Réponse de secours Mistral")
        self.assertIn("[Orchestrator] Fallback provider utilisé", output)

    # -------------------------------------------------------------------------
    # 16. test_chat_mode_configuration_and_token_efficiency
    # -------------------------------------------------------------------------
    def test_chat_mode_configuration_and_token_efficiency(self):
        """Vérifie la configuration du Mode Chat direct (Sans agent) et le retour d'état."""
        rlm = RateLimitManager(mode="chat")
        self.assertEqual(rlm.mode, ExecutionMode.CHAT)
        self.assertEqual(rlm.max_parallel_agents, 1)
        self.assertEqual(rlm.active_profile, "chat")

        state = rlm.get_state()
        self.assertEqual(state["mode"], "chat")
        self.assertEqual(state["max_parallel_agents"], 1)

        # Reconfiguration en mono
        rlm.configure(mode="mono")
        self.assertEqual(rlm.mode, ExecutionMode.MONO)
        self.assertEqual(rlm.get_state()["mode"], "mono")

        # Reconfiguration en multi
        rlm.configure(mode="multi", max_parallel_agents=3)
        self.assertEqual(rlm.mode, ExecutionMode.MULTI)
        self.assertEqual(rlm.max_parallel_agents, 3)

        # Reconfiguration en chat
        rlm.configure(mode="chat")
        self.assertEqual(rlm.mode, ExecutionMode.CHAT)
        self.assertEqual(rlm.max_parallel_agents, 1)

    # -------------------------------------------------------------------------
    # 17. test_chat_mode_direct_provider_call
    # -------------------------------------------------------------------------
    def test_chat_mode_direct_provider_call(self):
        """Vérifie qu'un appel direct en mode chat bénéficie de la protection du RateLimitManager."""
        from providers.base_provider import BaseProvider

        class MockChatProvider(BaseProvider):
            def generate(self, prompt: str = "") -> str:
                return f"Echo direct: {prompt}"
            def execute(self, instruction: str = "") -> str:
                return self.generate(instruction)
            def get_name(self) -> str:
                return "gemini"
            def get_model_name(self) -> str:
                return "gemini-3.8-flash"

        rlm = RateLimitManager(mode="chat")
        wrapped = rlm.wrap_provider(MockChatProvider(), agent_name="chat_direct")
        res = wrapped.generate("Bonjour Gemini !")
        self.assertEqual(res, "Echo direct: Bonjour Gemini !")
        self.assertEqual(rlm.active_calls, 0)


if __name__ == "__main__":
    unittest.main()
