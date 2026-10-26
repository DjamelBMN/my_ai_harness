# RÔLE DE CE FICHIER :
# Gestionnaire centralisé de concurrence LLM, limitation de débit (RateLimitManager),
# absorption intelligente des erreurs 429 avec exponential backoff + jitter,
# et Circuit Breaker par provider pour protéger les quotas Free Tier et API payantes.

from __future__ import annotations

import contextlib
from dataclasses import asdict, dataclass, field
from enum import Enum
import random
import re
import threading
import time
from typing import Any, Callable

from providers.base_provider import AgentTurn, BaseProvider


class ExecutionMode(str, Enum):
    CHAT = "chat"
    MONO = "mono"
    MULTI = "multi"


class CircuitState(str, Enum):
    CLOSED = "closed"        # Fonctionnement normal
    OPEN = "open"            # Cooldown actif, requêtes bloquées ou repliées
    HALF_OPEN = "half_open"  # Test d'une requête pour valider la guérison


class RateLimitExhaustedError(RuntimeError):
    """Exception levée lorsque toutes les tentatives de retry sur 429 ont échoué."""


class CircuitBreakerOpenError(RuntimeError):
    """Exception levée lorsque le Circuit Breaker est ouvert et qu'aucun fallback n'est disponible."""


@dataclass
class ProfileConfig:
    name: str
    mode: ExecutionMode
    max_parallel_agents: int
    max_retries: int = 3
    backoff: bool = True
    circuit_breaker: bool = True
    fallback_enabled: bool = False
    cooldown_after_429: float = 60.0


PROFILES: dict[str, ProfileConfig] = {
    "chat": ProfileConfig(
        name="chat",
        mode=ExecutionMode.CHAT,
        max_parallel_agents=1,
        max_retries=3,
        backoff=True,
        circuit_breaker=True,
        fallback_enabled=False,
        cooldown_after_429=60.0,
    ),
    "free": ProfileConfig(
        name="free",
        mode=ExecutionMode.MONO,
        max_parallel_agents=1,
        max_retries=3,
        backoff=True,
        circuit_breaker=True,
        fallback_enabled=False,
        cooldown_after_429=60.0,
    ),
    "balanced": ProfileConfig(
        name="balanced",
        mode=ExecutionMode.MULTI,
        max_parallel_agents=2,
        max_retries=3,
        backoff=True,
        circuit_breaker=True,
        fallback_enabled=True,
        cooldown_after_429=45.0,
    ),
    "powerful": ProfileConfig(
        name="powerful",
        mode=ExecutionMode.MULTI,
        max_parallel_agents=4,
        max_retries=4,
        backoff=True,
        circuit_breaker=True,
        fallback_enabled=True,
        cooldown_after_429=30.0,
    ),
}


@dataclass
class ProviderCircuitStatus:
    provider_name: str
    state: CircuitState = CircuitState.CLOSED
    consecutive_429s: int = 0
    last_429_time: float = 0.0
    cooldown_until: float = 0.0
    total_calls: int = 0
    successful_calls: int = 0
    rate_limited_calls: int = 0
    recent_429_timestamps: list[float] = field(default_factory=list)

    @property
    def circuit_state(self) -> CircuitState:
        return self.state

    def record_429(self, now: float, threshold: int, cooldown_seconds: float) -> None:
        self.rate_limited_calls += 1
        self.consecutive_429s += 1
        self.last_429_time = now
        self.recent_429_timestamps.append(now)
        if self.consecutive_429s >= threshold:
            self.state = CircuitState.OPEN
            self.cooldown_until = now + cooldown_seconds

    def is_cooling_down(self, now: float | None = None) -> bool:
        t = now if now is not None else time.monotonic()
        if self.state == CircuitState.OPEN:
            if t < self.cooldown_until:
                return True
            # Transition automatique en HALF_OPEN dès expiration du cooldown
            self.state = CircuitState.HALF_OPEN
            return False
        return False

    def remaining_cooldown(self, now: float | None = None) -> float:
        t = now if now is not None else time.monotonic()
        if self.state == CircuitState.OPEN and t < self.cooldown_until:
            return round(self.cooldown_until - t, 1)
        return 0.0

    def prune_recent(self, window_seconds: float = 300.0, now: float | None = None) -> None:
        t = now if now is not None else time.monotonic()
        cutoff = t - window_seconds
        self.recent_429_timestamps = [ts for ts in self.recent_429_timestamps if ts >= cutoff]

    def to_dict(self) -> dict[str, Any]:
        now = time.monotonic()
        self.prune_recent(now=now)
        return {
            "provider_name": self.provider_name,
            "state": self.state.value,
            "consecutive_429s": self.consecutive_429s,
            "is_cooling_down": self.is_cooling_down(now),
            "remaining_cooldown_seconds": self.remaining_cooldown(now),
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "rate_limited_calls": self.rate_limited_calls,
            "recent_429_count": len(self.recent_429_timestamps),
        }


def extract_retry_after(error: Exception) -> float | None:
    """Extrait le délai Retry-After (en secondes) depuis l'exception, headers ou message."""
    if error is None:
        return None
    if hasattr(error, "retry_after") and isinstance(error.retry_after, (int, float)):
        return float(error.retry_after)

    # 1. Headers HTTP
    for holder in (getattr(error, "response", None), error):
        headers = getattr(holder, "headers", None)
        if isinstance(headers, dict):
            for k, v in headers.items():
                if str(k).lower() in ("retry-after", "retry_after"):
                    try:
                        return float(v)
                    except (ValueError, TypeError):
                        pass

    # 2. Détails structurés Google RPC
    details = getattr(error, "details", None) or []
    if isinstance(details, (list, tuple)):
        for item in details:
            if isinstance(item, dict):
                retry_delay = item.get("retryDelay") or item.get("retry_delay")
                if retry_delay:
                    m = re.search(r"([0-9]+(?:\.[0-9]+)?)", str(retry_delay))
                    if m:
                        try:
                            return float(m.group(1))
                        except ValueError:
                            pass

    # 3. Regex dans le message
    msg = str(error)
    patterns = [
        r"please retry in\s+([0-9]+(?:\.[0-9]+)?)\s*s",
        r"retry[-_]after\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*s?",
        r"retry in\s+([0-9]+(?:\.[0-9]+)?)\s*s",
        r"retry_delay\s*\{\s*seconds:\s*([0-9]+)",
        r"wait\s+([0-9]+(?:\.[0-9]+)?)\s*s",
        r"retry within\s+([0-9]+(?:\.[0-9]+)?)\s*s",
    ]
    for pat in patterns:
        m = re.search(pat, msg, re.IGNORECASE)
        if m:
            try:
                val = float(m.group(1))
                if val > 0:
                    return val
            except ValueError:
                pass
    return None


def is_permanent_quota_exhausted(error: Exception) -> bool:
    """Distingue un quota réellement épuisé (journalier/compte) d'un 429 temporaire (RPM/TPM)."""
    if error is None:
        return False
    if getattr(error, "is_quota_exhausted", False) or getattr(error, "category", "") == "quota_exhausted":
        return True

    msg = str(error).lower()
    exhausted_markers = (
        "perday",
        "per day",
        "requests per day",
        "daily quota",
        "daily limit",
        "for the day",
        "billing not enabled",
        "free_tier_requests_per_day",
        "current plan",
        "plan and billing",
        "credit balance",
        "insufficient_quota",
        "quotas épuisés",
        "quota réellement épuisé",
    )
    return any(marker in msg for marker in exhausted_markers)


def is_rate_limit_error(error: Exception) -> bool:
    """Détecte de manière fiable si une exception correspond à une erreur 429 ou Rate Limit."""
    if error is None:
        return False
    if str(getattr(error, "category", "")).casefold() in {"quota", "rate_limit", "quota_exhausted", "429"}:
        return True
    status = getattr(error, "status_code", None) or getattr(error, "code", None)
    if status == 429:
        return True
    msg = str(error).casefold().replace("_", " ")
    return any(
        marker in msg
        for marker in (
            "429",
            "rate limit",
            "ratelimit",
            "quota",
            "too many requests",
            "resource exhausted",
            "exceeded your current quota",
            "tokens per minute",
            "requests per minute",
        )
    )


class RateLimitManager:
    """Gestionnaire centralisé pour la limitation de débit, le backoff et le Circuit Breaker."""

    def __init__(
        self,
        *,
        mode: str | ExecutionMode = ExecutionMode.MONO,
        max_parallel_agents: int = 1,
        max_parallel_gemini: int | None = None,
        max_retries: int = 3,
        base_backoff_seconds: float = 1.0,
        max_backoff_seconds: float = 32.0,
        jitter_range: tuple[float, float] = (0.1, 0.5),
        circuit_breaker_threshold: int = 3,
        max_consecutive_429: int | None = None,
        cooldown_after_429: float = 60.0,
        fallback_enabled: bool = False,
        fallback_provider_resolver: Callable[[], tuple[str, BaseProvider] | None] | None = None,
        event_sink: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self.event_sink = event_sink
        self.fallback_provider_resolver = fallback_provider_resolver

        # Configuration de mode
        mode_str = str(mode).strip().lower()
        if mode_str == "chat":
            self._mode = ExecutionMode.CHAT
            self.active_profile = "chat"
        elif mode_str == "multi":
            self._mode = ExecutionMode.MULTI
            self.active_profile = "balanced"
        else:
            self._mode = ExecutionMode.MONO
            self.active_profile = "free"

        if self._mode in (ExecutionMode.MONO, ExecutionMode.CHAT):
            self._max_parallel = 1
            self.max_parallel_gemini = 1
        else:
            self._max_parallel = max(1, int(max_parallel_agents))
            if max_parallel_gemini is not None:
                self.max_parallel_gemini = max(1, int(max_parallel_gemini))
            else:
                self.max_parallel_gemini = min(2, self._max_parallel)

        self.max_retries = max(0, int(max_retries))
        self.base_backoff_seconds = max(0.1, float(base_backoff_seconds))
        self.max_backoff_seconds = max(self.base_backoff_seconds, float(max_backoff_seconds))
        self.jitter_range = jitter_range
        eff_threshold = max_consecutive_429 if max_consecutive_429 is not None else circuit_breaker_threshold
        self.circuit_breaker_threshold = max(1, int(eff_threshold))
        self.cooldown_after_429 = max(0.01, float(cooldown_after_429))
        self.fallback_enabled = bool(fallback_enabled)

        # Concurrence globale et spécifique Gemini
        self._semaphore = threading.Semaphore(self._max_parallel)
        self._gemini_semaphore = threading.Semaphore(self.max_parallel_gemini)
        self._active_gemini_calls = 0
        self._thread_local = threading.local()
        self._active_calls = 0
        self._queued_calls = 0
        self._provider_circuits: dict[str, ProviderCircuitStatus] = {}

    # ------------------------------------------------------------------
    # PROPRIÉTÉS & ÉTAT
    # ------------------------------------------------------------------

    @property
    def mode(self) -> ExecutionMode:
        with self._lock:
            return self._mode

    @property
    def max_parallel_agents(self) -> int:
        with self._lock:
            return self._max_parallel

    @property
    def active_calls(self) -> int:
        with self._lock:
            return self._active_calls

    @property
    def queued_calls(self) -> int:
        with self._lock:
            return self._queued_calls

    def get_circuit_status(self, provider_name: str) -> ProviderCircuitStatus:
        with self._lock:
            p_norm = (provider_name or "default").lower().strip()
            if p_norm not in self._provider_circuits:
                self._provider_circuits[p_norm] = ProviderCircuitStatus(provider_name=p_norm)
            return self._provider_circuits[p_norm]

    def get_provider_status(self, provider_name: str) -> ProviderCircuitStatus:
        """Alias pratique de get_circuit_status."""
        return self.get_circuit_status(provider_name)

    def record_429(self, provider_name: str) -> None:
        """Enregistre une erreur 429 sur le provider et déclenche le Circuit Breaker si seuil atteint."""
        p_norm = (provider_name or "default").lower().strip()
        circuit = self.get_circuit_status(p_norm)
        with self._lock:
            now = time.monotonic()
            circuit.record_429(now, self.circuit_breaker_threshold, self.cooldown_after_429)
            if circuit.state == CircuitState.OPEN:
                self._emit(
                    "llm.circuit_open",
                    {
                        "provider": p_norm,
                        "cooldown_seconds": self.cooldown_after_429,
                        "consecutive_429s": circuit.consecutive_429s,
                    },
                )

    def is_provider_available(self, provider_name: str) -> bool:
        """Vérifie si un provider est immédiatement disponible (non bloqué par le Circuit Breaker)."""
        p_norm = (provider_name or "default").lower().strip()
        circuit = self.get_circuit_status(p_norm)
        with self._lock:
            now = time.monotonic()
            if circuit.is_cooling_down(now):
                return False
            if circuit.state == CircuitState.OPEN:
                return False
            return True

    @contextlib.contextmanager
    def acquire_slot(self, provider_name: str = "default", agent_name: str = "agent"):
        """Context manager pour réserver un slot d'exécution LLM respectant strictement max_parallel_agents."""
        p_name = (provider_name or "default").lower().strip()
        circuit = self.get_circuit_status(p_name)
        with self._lock:
            now = time.monotonic()
            if circuit.is_cooling_down(now):
                rem = circuit.remaining_cooldown(now)
                raise CircuitBreakerOpenError(
                    f"Le provider '{p_name}' est en cooldown (Circuit Breaker ouvert pour encore {rem}s)."
                )
            self._queued_calls += 1
            circuit.total_calls += 1

        self._emit(
            "llm.request_queued",
            {
                "provider": p_name,
                "agent": agent_name,
                "queued_calls": self._queued_calls,
                "active_calls": self._active_calls,
                "mode": self._mode.value,
            },
        )

        acquired = False
        try:
            self._semaphore.acquire(blocking=True)
            acquired = True
            self._thread_local.in_call = True
            with self._lock:
                self._queued_calls = max(0, self._queued_calls - 1)
                self._active_calls += 1

            self._emit(
                "llm.request_started",
                {
                    "provider": p_name,
                    "agent": agent_name,
                    "active_calls": self._active_calls,
                    "max_parallel": self._max_parallel,
                },
            )
            yield self
        finally:
            if acquired:
                self._thread_local.in_call = False
                with self._lock:
                    self._active_calls = max(0, self._active_calls - 1)
                self._semaphore.release()
                self._emit(
                    "llm.request_completed",
                    {
                        "provider": p_name,
                        "agent": agent_name,
                        "status": "completed",
                    },
                )

    def calculate_backoff_delay(self, attempt: int, base_delay: float = 1.0, jitter: bool = True) -> float:
        """Calcule un délai exponentiel avec ou sans jitter aléatoire."""
        step = max(0, attempt - 1)
        delay = float(base_delay) * (2 ** step)
        clamped = min(delay, self.max_backoff_seconds)
        if jitter:
            jitter_factor = random.uniform(0.75, 1.25)
            return round(clamped * jitter_factor, 3)
        return round(clamped, 3)

    def _emit(self, event_name: str, payload: dict[str, Any]) -> None:
        if self.event_sink is not None:
            try:
                self.event_sink(event_name, payload)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # CONFIGURATION DYNAMIQUE
    # ------------------------------------------------------------------

    def configure(
        self,
        *,
        mode: str | ExecutionMode | None = None,
        max_parallel_agents: int | None = None,
        max_parallel_gemini: int | None = None,
        profile: str | None = None,
        fallback_enabled: bool | None = None,
        cooldown_after_429: float | None = None,
        max_retries: int | None = None,
    ) -> dict[str, Any]:
        """Met à jour dynamiquement le mode, le profil ou les limites."""
        with self._lock:
            prev_mode = self._mode
            prev_parallel = self._max_parallel
            prev_gemini = self.max_parallel_gemini

            # 1. Application de profil prédéfini si demandé
            if profile and profile.lower() in PROFILES:
                p = PROFILES[profile.lower()]
                self.active_profile = p.name
                self._mode = p.mode
                self._max_parallel = p.max_parallel_agents
                self.max_parallel_gemini = 1 if p.mode == ExecutionMode.MONO else min(2, p.max_parallel_agents)
                self.max_retries = p.max_retries
                self.fallback_enabled = p.fallback_enabled
                self.cooldown_after_429 = p.cooldown_after_429
            else:
                if profile:
                    self.active_profile = "custom"

            # 2. Surcharges explicites
            if mode is not None:
                mode_str = str(mode).strip().lower()
                if mode_str == "chat":
                    parsed_mode = ExecutionMode.CHAT
                    self.active_profile = "chat"
                elif mode_str == "multi":
                    parsed_mode = ExecutionMode.MULTI
                    self.active_profile = "balanced"
                else:
                    parsed_mode = ExecutionMode.MONO
                    self.active_profile = "free"
                self._mode = parsed_mode
                if self._mode in (ExecutionMode.MONO, ExecutionMode.CHAT):
                    self._max_parallel = 1
                    self.max_parallel_gemini = 1
                elif max_parallel_agents is not None:
                    self._max_parallel = max(1, int(max_parallel_agents))
                elif self._max_parallel < 2:
                    self._max_parallel = 2

            if max_parallel_agents is not None and self._mode == ExecutionMode.MULTI:
                self._max_parallel = max(1, int(max_parallel_agents))

            if max_parallel_gemini is not None:
                self.max_parallel_gemini = 1 if self._mode in (ExecutionMode.MONO, ExecutionMode.CHAT) else max(1, int(max_parallel_gemini))
            elif self._mode in (ExecutionMode.MONO, ExecutionMode.CHAT):
                self.max_parallel_gemini = 1

            if fallback_enabled is not None:
                self.fallback_enabled = bool(fallback_enabled)
            if cooldown_after_429 is not None:
                self.cooldown_after_429 = max(1.0, float(cooldown_after_429))
            if max_retries is not None:
                self.max_retries = max(0, int(max_retries))

            # Ajustement du sémaphore global pour refléter la nouvelle capacité
            diff = self._max_parallel - prev_parallel
            if diff > 0:
                for _ in range(diff):
                    self._semaphore.release()
            elif diff < 0:
                for _ in range(abs(diff)):
                    self._semaphore.acquire(blocking=False)

            # Ajustement du sémaphore Gemini
            diff_g = self.max_parallel_gemini - prev_gemini
            if diff_g > 0:
                for _ in range(diff_g):
                    self._gemini_semaphore.release()
            elif diff_g < 0:
                for _ in range(abs(diff_g)):
                    self._gemini_semaphore.acquire(blocking=False)

            if prev_mode != self._mode or prev_parallel != self._max_parallel or prev_gemini != self.max_parallel_gemini:
                self._emit(
                    "agent_mode.changed",
                    {
                        "previous_mode": prev_mode.value,
                        "mode": self._mode.value,
                        "previous_max_parallel": prev_parallel,
                        "max_parallel_agents": self._max_parallel,
                        "max_parallel_gemini": self.max_parallel_gemini,
                        "profile": self.active_profile,
                    },
                )

            return self.get_state()

    def get_state(self) -> dict[str, Any]:
        """Retourne un snapshot complet de l'état du gestionnaire pour l'UI et les tests."""
        with self._lock:
            now = time.monotonic()
            circuits_dict = {}
            total_recent_429 = 0
            for name, c in self._provider_circuits.items():
                cd = c.to_dict()
                circuits_dict[name] = cd
                total_recent_429 += cd["recent_429_count"]

            return {
                "mode": self._mode.value,
                "max_parallel_agents": self._max_parallel,
                "max_parallel_gemini": self.max_parallel_gemini,
                "active_gemini_calls": self._active_gemini_calls,
                "profile": self.active_profile,
                "active_calls": self._active_calls,
                "queued_calls": self._queued_calls,
                "total_recent_429": total_recent_429,
                "fallback_enabled": self.fallback_enabled,
                "cooldown_after_429": self.cooldown_after_429,
                "max_retries": self.max_retries,
                "circuits": circuits_dict,
            }

    # ------------------------------------------------------------------
    # EXÉCUTION D'APPEL AVEC CONTRÔLE, QUEUE, BACKOFF & CIRCUIT BREAKER
    # ------------------------------------------------------------------

    def calculate_backoff(self, attempt: int) -> float:
        """Calcule le délai d'attente avec progression exponentielle et jitter aléatoire."""
        exp_delay = self.base_backoff_seconds * (2 ** attempt)
        clamped = min(exp_delay, self.max_backoff_seconds)
        jitter = random.uniform(*self.jitter_range)
        return round(clamped + jitter, 3)

    def execute_call(
        self,
        func: Callable[..., Any],
        *args: Any,
        provider_name: str = "default",
        agent_name: str = "agent",
        fallback_fn: Callable[..., Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Point de passage unique et obligatoire pour exécuter une requête vers un LLM.

        Gère :
        - La détection des appels réentrants pour éviter tout auto-blocage (deadlock).
        - La mise en attente (queue) si la concurrence max est atteinte.
        - La régulation stricte de la concurrence Gemini (semaphore dédié).
        - L'inspection du Circuit Breaker et la gestion du cooldown.
        - La distinction entre 429 temporaire et quota réellement épuisé.
        - Le respect de Retry-After et l'exponential backoff + jitter.
        - Le repli (failover) sur fallback_fn si activé.
        """
        # Éviter l'auto-blocage si un provider appelle self.generate depuis generate_agent_turn
        if getattr(self._thread_local, "in_call", False):
            return func(*args, **kwargs)

        p_name = (provider_name or "default").lower().strip()
        is_gemini = "gemini" in p_name or p_name in {"gemini", "gemini_flash_lite", "gemini_pro", "geminiprovider"}
        circuit = self.get_circuit_status(p_name)

        # Résolveur effectif de repli si fallback_fn non passé explicitement
        effective_fallback = fallback_fn
        if effective_fallback is None and self.fallback_provider_resolver is not None:
            def _auto_fallback(*fb_args, **fb_kwargs):
                fb = self.fallback_provider_resolver()
                if fb is None:
                    raise RuntimeError("Aucun provider de secours disponible.")
                next_name, next_prov = fb
                target_method = getattr(next_prov, func.__name__, None)
                if target_method is None:
                    target_method = getattr(next_prov, "generate", None)
                if target_method is None:
                    raise RuntimeError(f"Le provider de repli {next_name} ne supporte pas {func.__name__}.")
                return target_method(*fb_args, **fb_kwargs)
            effective_fallback = _auto_fallback

        # 1. Vérification du Circuit Breaker
        with self._lock:
            now = time.monotonic()
            if circuit.is_cooling_down(now):
                rem = circuit.remaining_cooldown(now)
                if self.fallback_enabled and effective_fallback is not None:
                    print("[Orchestrator] Fallback provider utilisé", flush=True)
                    self._emit(
                        "llm.fallback",
                        {
                            "provider": p_name,
                            "reason": f"Circuit ouvert (cooldown restant: {rem}s)",
                            "agent": agent_name,
                        },
                    )
                    return effective_fallback(*args, **kwargs)
                raise CircuitBreakerOpenError(
                    f"Le provider '{p_name}' est en cooldown (Circuit Breaker ouvert pour encore {rem}s). "
                    "Nouvelle tentative ultérieure requise pour préserver vos quotas."
                )

        # 2. Mise en file d'attente globale
        with self._lock:
            self._queued_calls += 1
            circuit.total_calls += 1

        self._emit(
            "llm.request_queued",
            {
                "provider": p_name,
                "agent": agent_name,
                "queued_calls": self._queued_calls,
                "active_calls": self._active_calls,
                "mode": self._mode.value,
            },
        )

        global_acquired = False
        gemini_acquired = False
        try:
            self._semaphore.acquire(blocking=True)
            global_acquired = True

            # Concurrence spécifique Gemini pour le Free Tier et le Multi-Agent
            if is_gemini:
                self._gemini_semaphore.acquire(blocking=True)
                gemini_acquired = True
                with self._lock:
                    self._active_gemini_calls += 1
                    cur_g = self._active_gemini_calls
                    max_g = self.max_parallel_gemini
                print(f"[Orchestrator] Concurrence Gemini : {cur_g}/{max_g}", flush=True)

            self._thread_local.in_call = True
            with self._lock:
                self._queued_calls = max(0, self._queued_calls - 1)
                self._active_calls += 1

            self._emit(
                "llm.request_started",
                {
                    "provider": p_name,
                    "agent": agent_name,
                    "active_calls": self._active_calls,
                    "max_parallel": self._max_parallel,
                    "active_gemini_calls": self._active_gemini_calls if is_gemini else None,
                },
            )

            # 3. Boucle d'exécution avec backoff, jitter, respect de Retry-After et failover
            attempt = 0
            while True:
                try:
                    result = func(*args, **kwargs)
                    with self._lock:
                        circuit.successful_calls += 1
                        circuit.consecutive_429s = 0
                        if circuit.state == CircuitState.HALF_OPEN:
                            circuit.state = CircuitState.CLOSED
                            self._emit(
                                "llm.circuit_closed",
                                {"provider": p_name, "message": "Provider guéri avec succès."},
                            )

                    self._emit(
                        "llm.request_completed",
                        {
                            "provider": p_name,
                            "agent": agent_name,
                            "attempt": attempt,
                            "status": "success",
                        },
                    )
                    return result

                except Exception as exc:
                    if is_rate_limit_error(exc):
                        now = time.monotonic()
                        if is_gemini:
                            print("[GeminiProvider] 429 détecté", flush=True)

                        quota_exhausted = is_permanent_quota_exhausted(exc)
                        if quota_exhausted:
                            if is_gemini:
                                print("[GeminiProvider] Quota épuisé", flush=True)
                            with self._lock:
                                circuit.state = CircuitState.OPEN
                                circuit.cooldown_until = now + self.cooldown_after_429
                                circuit.rate_limited_calls += 1
                                circuit.consecutive_429s += 1

                            self._emit(
                                "llm.circuit_open",
                                {
                                    "provider": p_name,
                                    "cooldown_seconds": self.cooldown_after_429,
                                    "consecutive_429s": circuit.consecutive_429s,
                                    "reason": "quota_exhausted",
                                },
                            )

                            if self.fallback_enabled and effective_fallback is not None:
                                print("[Orchestrator] Fallback provider utilisé", flush=True)
                                return effective_fallback(*args, **kwargs)

                            raise RateLimitExhaustedError(
                                f"Quota réellement épuisé sur le provider '{p_name}'. "
                                "Les retries inutiles ont été arrêtés immédiatement."
                            ) from exc

                        # 429 temporaire
                        with self._lock:
                            circuit.rate_limited_calls += 1
                            circuit.consecutive_429s += 1
                            circuit.last_429_time = now
                            circuit.recent_429_timestamps.append(now)

                        self._emit(
                            "llm.rate_limited",
                            {
                                "provider": p_name,
                                "agent": agent_name,
                                "attempt": attempt,
                                "consecutive_429s": circuit.consecutive_429s,
                                "error": str(exc),
                            },
                        )

                        # Déclenchement du Circuit Breaker si seuil dépassé
                        if circuit.consecutive_429s >= self.circuit_breaker_threshold:
                            with self._lock:
                                circuit.state = CircuitState.OPEN
                                circuit.cooldown_until = now + self.cooldown_after_429
                            self._emit(
                                "llm.circuit_open",
                                {
                                    "provider": p_name,
                                    "cooldown_seconds": self.cooldown_after_429,
                                    "consecutive_429s": circuit.consecutive_429s,
                                },
                            )
                            if self.fallback_enabled and effective_fallback is not None:
                                print("[Orchestrator] Fallback provider utilisé", flush=True)
                                return effective_fallback(*args, **kwargs)

                        if attempt < self.max_retries:
                            api_retry_after = extract_retry_after(exc)
                            backoff_delay = self.calculate_backoff(attempt)
                            if api_retry_after is not None and api_retry_after > 0:
                                delay = round(api_retry_after + random.uniform(*self.jitter_range), 2)
                            else:
                                delay = backoff_delay

                            if is_gemini:
                                print(f"[GeminiProvider] Retry dans {delay:.1f} secondes", flush=True)

                            self._emit(
                                "llm.retry_scheduled",
                                {
                                    "provider": p_name,
                                    "agent": agent_name,
                                    "attempt": attempt + 1,
                                    "max_retries": self.max_retries,
                                    "delay_seconds": delay,
                                    "message": f"Rate limit {p_name} — retry dans {delay:.1f} s",
                                },
                            )
                            attempt += 1
                            time.sleep(delay)
                            continue
                        else:
                            if self.fallback_enabled and effective_fallback is not None:
                                print("[Orchestrator] Fallback provider utilisé", flush=True)
                                return effective_fallback(*args, **kwargs)
                            raise RateLimitExhaustedError(
                                f"Limite de débit (429) persistante sur le provider '{p_name}' "
                                f"après {attempt} tentatives de retry. Quotas épuisés."
                            ) from exc
                    else:
                        raise

        finally:
            self._thread_local.in_call = False
            if gemini_acquired:
                with self._lock:
                    self._active_gemini_calls = max(0, self._active_gemini_calls - 1)
                self._gemini_semaphore.release()
            if global_acquired:
                with self._lock:
                    self._active_calls = max(0, self._active_calls - 1)
                self._semaphore.release()

    def wrap_provider(
        self,
        provider: BaseProvider,
        agent_name: str = "agent",
        fallback_provider_getter: Callable[[], tuple[str, BaseProvider] | None] | None = None,
    ) -> BaseProvider:
        """Encapsule un provider pour que tous ses appels passent par ce gestionnaire."""
        return attach_rate_limit_to_provider(
            provider,
            self,
            agent_name=agent_name,
            fallback_provider_getter=fallback_provider_getter,
        )


def attach_rate_limit_to_provider(
    provider: BaseProvider,
    rate_limit_manager: RateLimitManager,
    agent_name: str = "agent",
    fallback_provider_getter: Callable[[], tuple[str, BaseProvider] | None] | None = None,
) -> BaseProvider:
    """Attache dynamiquement le RateLimitManager à un provider sans briser son identité objet."""
    if getattr(provider, "_has_rate_limit_wrapped", False):
        return provider

    orig_generate = provider.generate
    orig_generate_agent_turn = getattr(provider, "generate_agent_turn", None)
    orig_execute = getattr(provider, "execute", None)

    def _make_fallback(method_name: str):
        if not fallback_provider_getter:
            return None
        def _fb(*fb_args, **fb_kwargs):
            res = fallback_provider_getter()
            if res is None:
                raise RuntimeError("Aucun provider de secours disponible.")
            next_name, next_prov = res
            m = getattr(next_prov, method_name, None)
            if m is None:
                raise RuntimeError(f"Le provider de secours {next_name} ne possède pas la méthode {method_name}.")
            return m(*fb_args, **fb_kwargs)
        return _fb

    fallback_generate = _make_fallback("generate")
    fallback_turn = _make_fallback("generate_agent_turn")
    fallback_exec = _make_fallback("execute")

    def wrapped_generate(prompt: str = "") -> str:
        p_name = provider.get_name() if hasattr(provider, "get_name") else "default"
        return rate_limit_manager.execute_call(
            orig_generate,
            prompt,
            provider_name=p_name,
            agent_name=agent_name,
            fallback_fn=fallback_generate,
        )

    def wrapped_generate_agent_turn(
        prompt: str | None,
        tools: list[dict[str, Any]],
        continuation: Any = None,
        tool_results: list[dict[str, Any]] | None = None,
    ) -> AgentTurn:
        p_name = provider.get_name() if hasattr(provider, "get_name") else "default"
        target_fn = orig_generate_agent_turn if orig_generate_agent_turn is not None else provider.generate_agent_turn
        return rate_limit_manager.execute_call(
            target_fn,
            prompt,
            tools,
            continuation=continuation,
            tool_results=tool_results,
            provider_name=p_name,
            agent_name=agent_name,
            fallback_fn=fallback_turn,
        )

    def wrapped_execute(instruction: str = "") -> str:
        p_name = provider.get_name() if hasattr(provider, "get_name") else "default"
        target_fn = orig_execute if orig_execute is not None else provider.execute
        return rate_limit_manager.execute_call(
            target_fn,
            instruction,
            provider_name=p_name,
            agent_name=agent_name,
            fallback_fn=fallback_exec,
        )

    try:
        provider.generate = wrapped_generate  # type: ignore[method-assign]
        provider.generate_agent_turn = wrapped_generate_agent_turn  # type: ignore[method-assign]
        provider.execute = wrapped_execute  # type: ignore[method-assign]
        provider._has_rate_limit_wrapped = True
        provider._rate_limit_manager = rate_limit_manager
    except Exception:
        # Si l'objet est gelé (frozen) ou ne permet pas l'assignation d'attributs, fallback sur le proxy
        return RateLimitedProviderProxy(
            provider,
            rate_limit_manager,
            agent_name=agent_name,
            fallback_provider_getter=fallback_provider_getter,
        )

    return provider


def is_free_tier_provider(provider_or_name: str | BaseProvider, model_name: str = "") -> bool:
    """Détecte si un provider ou modèle appartient à une offre Free Tier soumise à de stricts quotas."""
    name = ""
    m_name = (model_name or "").lower().strip()
    if isinstance(provider_or_name, str):
        name = provider_or_name.lower().strip()
    elif hasattr(provider_or_name, "get_name"):
        name = provider_or_name.get_name().lower().strip()
        if not m_name and hasattr(provider_or_name, "get_model_name"):
            m_name = provider_or_name.get_model_name().lower().strip()

    free_markers = ("free", "flash-lite", "flash_lite", "gemini-2.0-flash-lite", "gemini_flash_lite", "qwen", "ollama")
    return any(marker in name or marker in m_name for marker in free_markers)


class RateLimitedProviderProxy(BaseProvider):
    """Proxy transparent garantissant que TOUT appel passe par le RateLimitManager."""

    def __init__(
        self,
        target_provider: BaseProvider,
        rate_limit_manager: RateLimitManager,
        agent_name: str = "agent",
        fallback_provider_getter: Callable[[], tuple[str, BaseProvider] | None] | None = None,
    ) -> None:
        self._target = target_provider
        self._rlm = rate_limit_manager
        self._agent_name = agent_name
        self._fallback_getter = fallback_provider_getter

    def _make_fallback(self, method_name: str):
        if not self._fallback_getter:
            return None
        def _fb(*fb_args, **fb_kwargs):
            res = self._fallback_getter()
            if res is None:
                raise RuntimeError("Aucun provider de secours disponible.")
            next_name, next_prov = res
            m = getattr(next_prov, method_name, None)
            if m is None:
                raise RuntimeError(f"Le provider de secours {next_name} ne possède pas la méthode {method_name}.")
            return m(*fb_args, **fb_kwargs)
        return _fb

    @property
    def target(self) -> BaseProvider:
        return self._target

    def generate(self, prompt: str = "") -> str:
        p_name = self.get_name()
        return self._rlm.execute_call(
            self._target.generate,
            prompt,
            provider_name=p_name,
            agent_name=self._agent_name,
            fallback_fn=self._make_fallback("generate"),
        )

    def generate_agent_turn(
        self,
        prompt: str | None,
        tools: list[dict[str, Any]],
        continuation: Any = None,
        tool_results: list[dict[str, Any]] | None = None,
    ) -> AgentTurn:
        p_name = self.get_name()
        return self._rlm.execute_call(
            self._target.generate_agent_turn,
            prompt,
            tools,
            continuation=continuation,
            tool_results=tool_results,
            provider_name=p_name,
            agent_name=self._agent_name,
            fallback_fn=self._make_fallback("generate_agent_turn"),
        )

    def execute(self, instruction: str = "") -> str:
        p_name = self.get_name()
        return self._rlm.execute_call(
            self._target.execute,
            instruction,
            provider_name=p_name,
            agent_name=self._agent_name,
            fallback_fn=self._make_fallback("execute"),
        )

    def get_name(self) -> str:
        return self._target.get_name()

    def get_model_name(self) -> str:
        return self._target.get_model_name()

    def get_status_label(self) -> str:
        return self._target.get_status_label()

    def __eq__(self, other: Any) -> bool:
        if other is self or other is self._target:
            return True
        if isinstance(other, RateLimitedProviderProxy):
            return self._target == other._target
        return self._target == other

    def __hash__(self) -> int:
        return hash(self._target)

    def __repr__(self) -> str:
        return f"<RateLimitedProviderProxy for {self._target!r} (agent={self._agent_name})>"

    def __getattr__(self, name: str) -> Any:
        return getattr(self._target, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ("_target", "_rlm", "_agent_name"):
            super().__setattr__(name, value)
        else:
            setattr(self._target, name, value)
