# RÔLE DE CE FICHIER :
# Vérifie l'accès au modèle Gemini avec le SDK officiel google-genai, transmet les
# prompts des Agents à l'API Gemini et retourne uniquement le texte généré.
#
# GESTION DES QUOTAS (version corrigée) :
#   - Un 429 est classé "journalier" UNIQUEMENT d'après les détails structurés de
#     Google (quotaId ...PerDay...) ou des marqueurs précis. Le texte standard
#     "check your plan and billing details" n'est plus un signal d'épuisement.
#   - Les quotas Gemini sont PAR MODÈLE : si un modèle est épuisé, on bascule sur
#     le suivant au lieu d'abandonner.
#   - Un modèle épuisé / absent est mis en "cooldown" : plus aucune requête inutile
#     n'est envoyée tant que le cooldown n'est pas terminé.
#   - Un limiteur de débit local (requêtes/minute) évite de provoquer les 429.
#   - Un seul chemin de retry (plus de cascade stream -> generate -> fallback).
#
# VARIABLES D'ENVIRONNEMENT OPTIONNELLES :
#   GEMINI_API_KEY            clé API (obligatoire)
#   GEMINI_MAX_RPM            requêtes/minute max côté client (défaut 8, 0 = désactivé)
#   GEMINI_MAX_RETRY_WAIT     attente max (s) avant de renoncer à un retry (défaut 20)
#   GEMINI_FALLBACK_MODELS    modèles de repli séparés par des virgules
#                             (chaîne vide = aucun repli)

import json
import os
import random
import re
import threading
import time
from collections import deque
from types import SimpleNamespace
from typing import Any, Callable

from providers.base_provider import AgentTurn, BaseProvider, ProviderToolCall


DEFAULT_MODEL = "gemini-3.5-flash-lite"
DEFAULT_FALLBACK_MODELS = (
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
)

DAILY_COOLDOWN_SECONDS = 900.0     # on re-teste un modèle "journalier" au bout de 15 min
MISSING_COOLDOWN_SECONDS = 3600.0  # modèle introuvable (404) : on l'ignore 1 h
DEFAULT_RATE_COOLDOWN_SECONDS = 30.0


# --------------------------------------------------------------------------- #
# Erreur dédiée
# --------------------------------------------------------------------------- #
class GeminiProviderError(RuntimeError):
    """Erreur de configuration, d'accès ou de génération Gemini."""

    def __init__(
        self,
        message: str,
        category: str = "provider",
        retry_after: float | None = None,
        is_quota_exhausted: bool = False,
        status: int | None = None,
        no_retry: bool = False,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.retry_after = retry_after
        self.is_quota_exhausted = is_quota_exhausted
        self.status = status
        self.no_retry = no_retry


# --------------------------------------------------------------------------- #
# Analyse des erreurs
# --------------------------------------------------------------------------- #
def _walk_error_payload(error: Exception) -> list[dict]:
    """Aplatit tous les dictionnaires imbriqués dans les détails de l'erreur."""
    found: list[dict] = []

    def walk(node: Any, depth: int = 0) -> None:
        if depth > 8:
            return
        if isinstance(node, dict):
            found.append(node)
            for value in node.values():
                walk(value, depth + 1)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value, depth + 1)

    for attr in ("details", "response_json", "body"):
        try:
            walk(getattr(error, attr, None))
        except Exception:
            pass
    return found


def extract_gemini_retry_after(error: Exception) -> float | None:
    """Extrait le délai Retry-After (en secondes) depuis l'exception, headers ou message."""
    if error is None:
        return None
    value = getattr(error, "retry_after", None)
    if isinstance(value, (int, float)) and value > 0:
        return float(value)

    # 1. Headers HTTP
    for holder in (getattr(error, "response", None), error):
        headers = getattr(holder, "headers", None)
        if headers is not None and hasattr(headers, "items"):
            try:
                for k, v in headers.items():
                    if str(k).lower() in ("retry-after", "retry_after"):
                        try:
                            return float(v)
                        except (ValueError, TypeError):
                            pass
            except Exception:
                pass

    # 2. Détails structurés Google RPC (RetryInfo.retryDelay, ex: "37s")
    for node in _walk_error_payload(error):
        retry_delay = node.get("retryDelay") or node.get("retry_delay")
        if retry_delay:
            m = re.search(r"([0-9]+(?:\.[0-9]+)?)", str(retry_delay))
            if m:
                try:
                    val = float(m.group(1))
                    if val > 0:
                        return val
                except ValueError:
                    pass

    # 3. Regex dans le texte du message
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


# Marqueurs utilisés seulement si l'API ne fournit AUCUN quotaId structuré.
# Volontairement SANS "current plan" / "plan and billing" : ces mots figurent dans
# le message standard de tous les 429 (même ceux par minute).
_DAILY_MARKERS = (
    "perday",
    "per day",
    "requests per day",
    "daily quota",
    "daily limit",
    "for the day",
    "free_tier_requests_per_day",
    "billing not enabled",
    "insufficient_quota",
    "credit balance",
    "prepayment credits",
    "credits are depleted",
)


def classify_gemini_quota(error: Exception) -> dict[str, Any]:
    """Analyse un 429 : portée (journalière / minute / inconnue) et quota nul."""
    daily = False
    minute = False
    limit_zero = False

    for node in _walk_error_payload(error):
        quota_id = node.get("quotaId")
        if isinstance(quota_id, str) and quota_id:
            low = quota_id.lower()
            if "perday" in low:
                daily = True
            elif "perminute" in low:
                minute = True
        if "quotaValue" in node and str(node.get("quotaValue")).strip() == "0":
            limit_zero = True

    msg = str(error).lower()
    if not (daily or minute):
        daily = any(marker in msg for marker in _DAILY_MARKERS)
    if re.search(r"limit:\s*0\b", msg):
        limit_zero = True

    scope = "daily" if daily else ("minute" if minute else "unknown")
    return {"scope": scope, "limit_zero": limit_zero}


def is_gemini_quota_exhausted(error: Exception) -> bool:
    """Distingue un quota réellement épuisé (journalier/compte/nul) d'un 429 temporaire (RPM/TPM)."""
    if error is None:
        return False
    if getattr(error, "is_quota_exhausted", False) or getattr(error, "category", "") == "quota_exhausted":
        return True
    if getattr(error, "category", "") == "rate_limit":
        return False

    msg = str(error).lower()
    if "quota réellement épuisé" in msg or "quotas épuisés" in msg:
        return True

    info = classify_gemini_quota(error)
    return info["scope"] == "daily" or bool(info["limit_zero"])


# --------------------------------------------------------------------------- #
# Limiteur de débit local + cooldowns partagés entre toutes les instances
# --------------------------------------------------------------------------- #
class _SlidingWindowLimiter:
    """Limite le nombre d'appels par fenêtre glissante (défaut : 60 s)."""

    def __init__(self, max_calls: int, period: float = 60.0) -> None:
        self.max_calls = max_calls
        self.period = period
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self, max_wait: float) -> None:
        if self.max_calls <= 0:
            return
        while True:
            with self._lock:
                now = time.monotonic()
                while self._calls and now - self._calls[0] >= self.period:
                    self._calls.popleft()
                if len(self._calls) < self.max_calls:
                    self._calls.append(now)
                    return
                wait = self.period - (now - self._calls[0])
            if wait > max_wait:
                raise GeminiProviderError(
                    "Limite de débit locale Gemini atteinte : "
                    f"réessaie dans {wait:.0f} secondes.",
                    category="rate_limit",
                    retry_after=wait,
                )
            time.sleep(min(wait + 0.05, max_wait))


_limiter_lock = threading.Lock()
_limiter: _SlidingWindowLimiter | None = None


def _get_limiter() -> _SlidingWindowLimiter:
    global _limiter
    try:
        rpm = int(os.environ.get("GEMINI_MAX_RPM", "8"))
    except ValueError:
        rpm = 15
    with _limiter_lock:
        if _limiter is None or _limiter.max_calls != rpm:
            _limiter = _SlidingWindowLimiter(rpm)
        return _limiter


def _max_retry_wait() -> float:
    try:
        return max(0.0, float(os.environ.get("GEMINI_MAX_RETRY_WAIT", "20")))
    except ValueError:
        return 20.0


# --------------------------------------------------------------------------- #
# Provider
# --------------------------------------------------------------------------- #
class GeminiProvider(BaseProvider):
    _cached_models: list[dict[str, str]] | None = None
    _cached_models_time: float = 0.0

    # clé "modèle|portée" -> (fin_du_cooldown, nature) ; nature : daily | rate | missing
    _cooldowns: dict[str, tuple[float, str]] = {}
    _cooldown_lock = threading.Lock()

    def __init__(self, model: str | None = None) -> None:
        if model is not None and (not isinstance(model, str) or not model.strip()):
            raise GeminiProviderError(
                "Gemini — configuration invalide : modèle vide.",
                category="configuration",
            )
        self.model = model.strip() if model else DEFAULT_MODEL
        self.last_used_model: str = self.model
        self.last_usage: dict[str, int] = {}
        self._client = None
        self._verified = False
        self._available_models: dict[str, str] = {}
        self.max_output_tokens: int | None = None
        self.max_retries = 2
        self.base_backoff_seconds = 1.0
        self.enable_extended_thinking = False
        self.stream_callback: Any = None
        self.pending_images: list[dict[str, Any]] = []

    def _is_real_sdk_client(self) -> bool:
        """Retourne True uniquement lorsque self._client est le vrai client google.genai."""
        if self._client is None:
            return True
        mod = getattr(type(self._client), "__module__", "") or ""
        return mod.startswith("google")

    def _record_usage(self, response_or_chunk: Any) -> None:
        """Extrait usage_metadata de la réponse Gemini et met à jour self.last_usage."""
        meta = getattr(response_or_chunk, "usage_metadata", None)
        if meta is None:
            return
        try:
            prompt_tok = int(getattr(meta, "prompt_token_count", 0) or 0)
            cand_tok = int(getattr(meta, "candidates_token_count", 0) or 0)
            total_tok = int(getattr(meta, "total_token_count", 0) or (prompt_tok + cand_tok))
            if total_tok > 0 or prompt_tok > 0 or cand_tok > 0:
                self.last_usage = {
                    "prompt_tokens": prompt_tok,
                    "completion_tokens": cand_tok,
                    "total_tokens": total_tok or (prompt_tok + cand_tok),
                }
        except Exception:
            pass

    # ------------------------------------------------------------------ client
    def _get_client(self):
        if self._client is not None:
            return self._client
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise GeminiProviderError(
                "GEMINI_API_KEY n'est pas configurée.",
                category="missing_key",
            )

        try:
            from google import genai
        except ImportError:
            raise GeminiProviderError(
                "Le SDK Google GenAI n'est pas installé. Lance : "
                "python -m pip install -r requirements.txt",
                category="sdk_missing",
            ) from None

        try:
            from google.genai import types

            self._client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(timeout=90_000),
            )
        except Exception:
            raise GeminiProviderError(
                "Le client Google GenAI n'a pas pu être initialisé.",
                category="configuration",
            ) from None
        return self._client

    # ------------------------------------------------------ traduction d'erreurs
    @staticmethod
    def _api_error(error: Exception, phase: str) -> "GeminiProviderError":
        """Traduit les erreurs SDK sans renvoyer leurs détails ou une clé éventuelle."""
        if isinstance(error, GeminiProviderError):
            return error

        error_type = type(error).__name__
        if error_type in {
            "ConnectError",
            "ConnectTimeout",
            "ReadTimeout",
            "TimeoutException",
        } or isinstance(error, (ConnectionError, TimeoutError)):
            return GeminiProviderError(
                f"Impossible de joindre l'API Gemini pendant {phase}.",
                category="unavailable",
            )

        status = getattr(error, "code", None)
        if not isinstance(status, int):
            status = getattr(error, "status_code", None)
        if not isinstance(status, int):
            status = None

        msg_str = str(error)
        msg_lower = msg_str.lower()
        is_429 = (
            status == 429
            or (status is None and re.search(r"\b429\b", msg_str) is not None)
            or "resource_exhausted" in msg_lower
            or "resource has been exhausted" in msg_lower
            or "exceeded your current quota" in msg_lower
            or "too many requests" in msg_lower
            or "rate limit" in msg_lower
            or "ratelimit" in msg_lower
        )

        if is_429:
            retry_after = extract_gemini_retry_after(error)
            if is_gemini_quota_exhausted(error):
                print("[GeminiProvider] Quota épuisé pour ce modèle", flush=True)
                return GeminiProviderError(
                    f"Le quota Gemini est épuisé pendant {phase} "
                    "(limite journalière ou quota nul pour ce modèle).",
                    category="quota_exhausted",
                    retry_after=None,
                    is_quota_exhausted=True,
                    status=429,
                )
            print("[GeminiProvider] 429 temporaire détecté", flush=True)
            return GeminiProviderError(
                f"Limite de débit (429) Gemini atteinte pendant {phase}.",
                category="rate_limit",
                retry_after=retry_after,
                is_quota_exhausted=False,
                status=429,
            )

        if status == 404:
            return GeminiProviderError(
                "Gemini — configuration invalide : modèle introuvable.",
                category="configuration",
                status=404,
            )
        if status == 400:
            print(f"[GeminiProvider] HTTP 400 pendant {phase} : {msg_str[:400]}", flush=True)
            return GeminiProviderError(
                "Gemini — configuration invalide : requête ou modèle incompatible "
                "avec l'API.",
                category="configuration",
                status=400,
            )
        if status in {401, 403}:
            return GeminiProviderError(
                "La clé Gemini a été refusée. Vérifie GEMINI_API_KEY.",
                category="authentication",
                status=status,
            )
        if "503" in msg_str or "unavailable" in msg_lower or "overloaded" in msg_lower:
            status = status or 503
        if status in {408, 500, 502, 503, 504}:
            return GeminiProviderError(
                f"L'API Gemini est temporairement indisponible pendant {phase} "
                f"(HTTP {status}).",
                category="unavailable",
                status=status,
            )
        return GeminiProviderError(
            f"La requête Gemini a échoué pendant {phase}"
            + (f" (HTTP {status})." if status else "."),
            category="unavailable",
            status=status,
        )

    # ------------------------------------------------------------- cooldowns
    @staticmethod
    def _cd_key(model: str, scope: str) -> str:
        return f"{model}|{scope}"

    @classmethod
    def _set_cooldown(cls, model: str, scope: str, seconds: float, kind: str) -> None:
        with cls._cooldown_lock:
            cls._cooldowns[cls._cd_key(model, scope)] = (time.monotonic() + seconds, kind)

    @classmethod
    def _get_cooldown(cls, model: str, scope: str) -> tuple[float, str] | None:
        """Retourne (secondes_restantes, nature) ou None si le modèle est utilisable."""
        key = cls._cd_key(model, scope)
        with cls._cooldown_lock:
            entry = cls._cooldowns.get(key)
            if entry is None:
                return None
            remaining = entry[0] - time.monotonic()
            if remaining <= 0:
                cls._cooldowns.pop(key, None)
                return None
            return remaining, entry[1]

    @classmethod
    def reset_cooldowns(cls) -> None:
        """Efface tous les cooldowns (utile après changement de clé ou de forfait)."""
        with cls._cooldown_lock:
            cls._cooldowns.clear()

    # ----------------------------------------------------- modèles candidats
    def _candidate_models(self) -> list[str]:
        env = os.environ.get("GEMINI_FALLBACK_MODELS")
        if env is not None:
            fallbacks = [m.strip() for m in env.split(",") if m.strip()]
        else:
            fallbacks = list(DEFAULT_FALLBACK_MODELS)

        primary = self.model
        if primary and self._available_models and primary not in self._available_models:
            close = sorted(
                (m for m in self._available_models if m.startswith(primary) or primary.startswith(m)),
                key=len,
            )
            if close:
                print(f"[GeminiProvider] Modèle {primary} -> identifiant réel {close[0]}", flush=True)
                primary = close[0]
            else:
                print(f"[GeminiProvider] Modèle {primary} absent de la liste de votre clé", flush=True)
                primary = None

        candidates = [primary] if primary else []
        for name in fallbacks:
            if name in candidates:
                continue
            if self._available_models and name not in self._available_models:
                continue  # inutile d'interroger un modèle que la clé ne voit pas
            candidates.append(name)
        return candidates

    # -------------------------------------------- exécution unique avec repli
    def _execute(
        self,
        call: Callable[[str], Any],
        phase: str,
        scope: str = "base",
    ) -> Any:
        """Point d'entrée UNIQUE des appels API : limiteur, retries bornés, repli de modèle."""
        if not self._available_models and not self._verified:
            try:
                self.list_available_models()  # mis en cache 5 min, évite les 404 sur des identifiants inconnus
            except GeminiProviderError as error:
                if error.category in {"authentication", "missing_key", "sdk_missing"}:
                    raise
        candidates = self._candidate_models()
        if not candidates:
            names = ", ".join(sorted(self._available_models)[:10]) or "liste indisponible"
            raise GeminiProviderError(
                "Gemini — configuration invalide : aucun modèle configuré n'existe pour votre clé. "
                f"Modèles disponibles : {names}.",
                category="configuration",
            )

        kinds: dict[str, str] = {}
        usable: list[str] = []
        for model in candidates:
            cd = self._get_cooldown(model, scope)
            if cd is None:
                usable.append(model)
            else:
                kinds[model] = cd[1]

        if not usable:
            raise self._final_error(candidates, kinds, phase, None, scope)

        max_wait = _max_retry_wait()
        use_rate_limiter = self._is_real_sdk_client()
        last_mapped: GeminiProviderError | None = None

        for model in usable:
            for attempt in range(self.max_retries + 1):
                if use_rate_limiter:
                    _get_limiter().acquire(max_wait)  # peut lever rate_limit local (0 requête API)
                try:
                    result = call(model)
                except Exception as error:
                    mapped = self._api_error(error, phase)
                    last_mapped = mapped

                    if mapped.no_retry:
                        raise mapped from None
                    if mapped.category in {"authentication", "missing_key", "sdk_missing"}:
                        raise mapped from None

                    if mapped.category == "configuration":
                        if mapped.status == 404:
                            self._set_cooldown(model, scope, MISSING_COOLDOWN_SECONDS, "missing")
                            kinds[model] = "missing"
                            print(f"[GeminiProvider] Modèle introuvable : {model}", flush=True)
                            break  # modèle suivant
                        raise mapped from None  # 400 : inutile de réessayer ailleurs

                    if mapped.is_quota_exhausted:
                        self._set_cooldown(model, scope, DAILY_COOLDOWN_SECONDS, "daily")
                        kinds[model] = "daily"
                        print(f"[GeminiProvider] {model} épuisé -> modèle suivant", flush=True)
                        break

                    if mapped.category == "rate_limit":
                        wait = mapped.retry_after or min(
                            self.base_backoff_seconds * (2 ** attempt), 8.0
                        )
                        wait = round(wait + random.uniform(0.1, 0.4), 2)
                        if attempt >= self.max_retries or wait > max_wait:
                            self._set_cooldown(
                                model, scope, mapped.retry_after or DEFAULT_RATE_COOLDOWN_SECONDS, "rate"
                            )
                            kinds[model] = "rate"
                            break
                        print(f"[GeminiProvider] Retry dans {wait:.1f} secondes", flush=True)
                        time.sleep(wait)
                        continue

                    if mapped.category == "unavailable":
                        if mapped.status in {503, 504}:
                            kinds[model] = "unavailable"
                            break  # surcharge : on bascule sans attendre
                        if attempt >= self.max_retries:
                            kinds[model] = "unavailable"
                            break
                        wait = round(
                            min(self.base_backoff_seconds * (2 ** attempt) + random.uniform(0.05, 0.2), 8.0),
                            2,
                        )
                        print(f"[GeminiProvider] Retry dans {wait:.1f} secondes", flush=True)
                        time.sleep(wait)
                        continue

                    raise mapped from None
                else:
                    self.last_used_model = model
                    if model != self.model:
                        print(f"[GeminiProvider] Repli ponctuel sur le modèle {model}", flush=True)
                    return result

        raise self._final_error(candidates, kinds, phase, last_mapped, scope)

    def _final_error(
        self,
        candidates: list[str],
        kinds: dict[str, str],
        phase: str,
        last_mapped: "GeminiProviderError | None",
        scope: str,
    ) -> "GeminiProviderError":
        """Construit l'erreur finale quand plus aucun modèle n'est utilisable."""
        real = {m: k for m, k in kinds.items() if k != "missing"}
        tried = ", ".join(candidates)

        if real and len(real) == len([m for m in candidates if kinds.get(m) != "missing"]):
            if all(k == "daily" for k in real.values()):
                return GeminiProviderError(
                    f"Quota Gemini épuisé sur tous les modèles essayés ({tried}) pendant "
                    f"{phase}. Attends la réinitialisation journalière, change de clé ou "
                    "active la facturation.",
                    category="quota_exhausted",
                    is_quota_exhausted=True,
                    status=429,
                )
            if all(k in {"daily", "rate"} for k in real.values()):
                waits = []
                for m in real:
                    cd = self._get_cooldown(m, scope)
                    if cd is not None and real[m] == "rate":
                        waits.append(cd[0])
                retry_after = min(waits) if waits else DEFAULT_RATE_COOLDOWN_SECONDS
                return GeminiProviderError(
                    f"Limite de débit Gemini atteinte sur tous les modèles ({tried}). "
                    f"Réessaie dans environ {retry_after:.0f} secondes.",
                    category="rate_limit",
                    retry_after=retry_after,
                    is_quota_exhausted=False,
                    status=429,
                )
        if kinds and all(k == "missing" for k in kinds.values()):
            available = ", ".join(sorted(self._available_models)[:10]) or "liste indisponible"
            return GeminiProviderError(
                f"Gemini — modèle introuvable : aucun de ces modèles n'existe pour votre clé ({tried}). "
                f"Modèles disponibles : {available}. Corrige le modèle dans config/config.yaml.",
                category="configuration",
                status=404,
            )
        if last_mapped is not None:
            return last_mapped
        return GeminiProviderError(
            f"Aucun modèle Gemini disponible pendant {phase} ({tried}).",
            category="unavailable",
        )

    # ------------------------------------------------------------ configuration
    def _default_config(self, model: str):
        """Config rapide : pas de réflexion inutile sur les modèles Flash."""
        try:
            from google.genai import types
        except Exception:
            return None
        kwargs: dict[str, Any] = {"http_options": types.HttpOptions(timeout=60_000)}
        if "flash" in model and "2.5" in model and not self.enable_extended_thinking:
            try:
                kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
            except Exception:
                pass
        try:
            return types.GenerateContentConfig(**kwargs)
        except Exception:
            return None

    def _generate_content(self, contents: Any, *, config: Any = None, phase: str, scope: str = "base"):
        """Appel non-streaming unique, avec limiteur, retries et repli de modèle."""
        client = self._get_client()

        def call(model: str):
            cfg = config if config is not None else self._default_config(model)
            options: dict[str, Any] = {"model": model, "contents": contents}
            if cfg is not None:
                options["config"] = cfg
            resp = client.models.generate_content(**options)
            self._record_usage(resp)
            return resp

        return self._execute(call, phase, scope=scope)

    # ----------------------------------------------------------------- modèles
    def list_available_models(self) -> list[dict[str, str]]:
        """Liste les modèles accessibles qui prennent en charge generateContent (cache 5 min)."""
        now = time.monotonic()
        if (
            self._client is None
            and GeminiProvider._cached_models
            and (now - GeminiProvider._cached_models_time < 300.0)
        ):
            self._available_models = {
                item["model"]: item["display_name"] for item in GeminiProvider._cached_models
            }
            return list(GeminiProvider._cached_models)

        client = self._get_client()
        try:
            discovered = []
            for model_info in client.models.list():
                actions = getattr(model_info, "supported_actions", None) or []
                if "generateContent" not in actions:
                    continue
                resource_name = getattr(model_info, "name", "")
                if not isinstance(resource_name, str) or not resource_name.strip():
                    continue
                model_id = resource_name.strip()
                if model_id.startswith("models/"):
                    model_id = model_id.removeprefix("models/")
                display_name = getattr(model_info, "display_name", None)
                if not isinstance(display_name, str) or not display_name.strip():
                    display_name = model_id
                discovered.append(
                    {"model": model_id, "display_name": display_name.strip()}
                )
        except Exception as error:
            raise self._api_error(error, "la liste des modèles") from None

        unique_models = {item["model"]: item for item in discovered}
        discovered = list(unique_models.values())
        if not discovered:
            raise GeminiProviderError(
                "Gemini — configuration invalide : aucun modèle accessible ne "
                "prend en charge la génération de texte.",
                category="configuration",
            )
        GeminiProvider._cached_models = list(discovered)
        GeminiProvider._cached_models_time = now
        self._available_models = {
            item["model"]: item["display_name"] for item in discovered
        }
        return discovered

    def select_model(self, model: str) -> None:
        """Sélectionne un modèle parmi ceux retournés par l'API Gemini."""
        if model not in self._available_models:
            raise GeminiProviderError(
                "Gemini — configuration invalide : le modèle choisi n'est pas "
                "dans la liste des modèles accessibles.",
                category="configuration",
            )
        self.model = model
        self.last_used_model = model
        self._verified = True

    def with_model(self, model: str) -> "GeminiProvider":
        """Crée un provider pour un modèle déjà validé par la même liste API."""
        if model not in self._available_models:
            raise GeminiProviderError(
                "Gemini — configuration invalide : le modèle n'est pas accessible.",
                category="configuration",
            )
        provider = GeminiProvider(model=model)
        provider._client = self._client
        provider._available_models = dict(self._available_models)
        provider._verified = True
        provider.max_output_tokens = self.max_output_tokens
        provider.max_retries = self.max_retries
        provider.base_backoff_seconds = self.base_backoff_seconds
        provider.enable_extended_thinking = self.enable_extended_thinking
        return provider

    def supports_model(self, model: str) -> bool:
        """Indique si la liste vérifiée de l'API contient ce modèle."""
        return model in self._available_models

    def check_available(self) -> None:
        """Vérifie la clé, le SDK et l'accès au modèle configuré sans génération."""
        if self._verified:
            return
        self.list_available_models()
        if self.model is None:
            raise GeminiProviderError(
                "Gemini — configuration invalide : aucun modèle n'a été sélectionné.",
                category="configuration",
            )
        if self.model not in self._available_models:
            replacement = (
                next((m for m in DEFAULT_FALLBACK_MODELS if m in self._available_models), None)
                if self.model in DEFAULT_FALLBACK_MODELS and self._is_real_sdk_client()
                else None
            )
            if replacement is None:
                raise GeminiProviderError(
                    "Gemini — configuration invalide : le modèle configuré "
                    "n'est pas accessible.",
                    category="configuration",
                )
            print(
                f"[GeminiProvider] Modèle {self.model} inaccessible, utilisation de {replacement}",
                flush=True,
            )
            self.model = replacement
            self.last_used_model = replacement
        self._verified = True

    def _consume_multimodal_contents(self, prompt: str) -> Any:
        """Si des images jointes sont en attente et que le vrai SDK est actif, construit un Content multimodal."""
        images = list(getattr(self, "pending_images", []) or [])
        self.pending_images = []
        if not images or not self._is_real_sdk_client():
            return prompt
        try:
            from google.genai import types

            parts = [
                types.Part.from_bytes(data=img["bytes"], mime_type=img["mime_type"])
                for img in images
                if isinstance(img, dict) and img.get("bytes") and img.get("mime_type")
            ]
            if not parts:
                return prompt
            parts.append(types.Part.from_text(text=prompt))
            return [types.Content(role="user", parts=parts)]
        except Exception:
            return prompt

    # -------------------------------------------------------------- génération
    def generate(self, prompt: str = "") -> str:
        """Envoie le prompt (et les éventuelles images jointes) à Gemini via google-genai."""
        if not prompt.strip():
            raise GeminiProviderError("Le prompt transmis à Gemini est vide.")
        if not self._verified:
            self.check_available()

        contents_payload = self._consume_multimodal_contents(prompt)
        response = self._generate_content(contents_payload, phase="la génération")

        answer = getattr(response, "text", "")
        if not isinstance(answer, str) or not answer.strip():
            raise GeminiProviderError(
                "Gemini n'a retourné aucun texte pour le prompt."
            )
        return answer.strip()

    def generate_structured(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Demande un objet JSON contraint par un schéma Gemini officiel."""
        if not prompt.strip():
            raise GeminiProviderError("Le prompt transmis à Gemini est vide.")
        if not isinstance(schema, dict) or schema.get("type") != "object":
            raise ValueError("Le schéma de sortie doit être un JSON Schema object.")
        if not self._verified:
            self.check_available()
        try:
            from google.genai import types
        except ImportError:
            raise GeminiProviderError(
                "Le SDK Google GenAI n'est pas installé.", category="sdk_missing"
            ) from None
        config: dict[str, Any] = {
            "response_mime_type": "application/json",
            "response_json_schema": schema,
            "http_options": types.HttpOptions(timeout=90_000),
        }
        if self.max_output_tokens:
            config["max_output_tokens"] = self.max_output_tokens
        response = self._generate_content(
            prompt,
            config=types.GenerateContentConfig(**config),
            phase="la génération structurée",
        )
        raw = getattr(response, "text", "")
        try:
            result = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            raise GeminiProviderError(
                "Gemini n'a pas retourné un JSON conforme à la réponse structurée."
            ) from None
        if not isinstance(result, dict):
            raise GeminiProviderError("La réponse structurée Gemini n'est pas un objet JSON.")
        return result

    def generate_stream(self, prompt: str):
        """Expose les fragments texte du SDK (avec support multimodal si des images sont jointes)."""
        if not prompt.strip():
            raise GeminiProviderError("Le prompt transmis à Gemini est vide.")
        if not self._verified:
            self.check_available()
        client = self._get_client()
        contents_payload = self._consume_multimodal_contents(prompt)

        def open_stream(model: str):
            iterator = iter(
                client.models.generate_content_stream(
                    model=model,
                    contents=contents_payload,
                    config={"http_options": {"timeout": 90_000}},
                )
            )
            # On lit jusqu'au premier texte ici : une erreur de quota survient
            # avant le premier fragment et peut donc encore déclencher un repli.
            for chunk in iterator:
                self._record_usage(chunk)
                text = getattr(chunk, "text", "")
                if isinstance(text, str) and text:
                    return text, iterator
            return None, iterator

        first, iterator = self._execute(open_stream, "la génération en streaming")
        if first:
            yield first
        try:
            for chunk in iterator:
                self._record_usage(chunk)
                text = getattr(chunk, "text", "")
                if isinstance(text, str) and text:
                    yield text
        except Exception as error:
            raise self._api_error(error, "la génération en streaming") from None

    # ---------------------------------------------------------- tour d'agent
    def _stream_turn(self, model: str, contents: list, cfg: Any, types: Any):
        """Un appel streaming complet. Retourne None si le flux est vide."""
        streamed_text: list[str] = []
        all_parts: list = []
        last_candidate = None
        stream_grounding = None
        last_usage_meta = None
        try:
            stream = self._get_client().models.generate_content_stream(
                model=model, contents=contents, config=cfg
            )
            for chunk in stream:
                self._record_usage(chunk)
                if getattr(chunk, "usage_metadata", None) is not None:
                    last_usage_meta = chunk.usage_metadata
                cands = getattr(chunk, "candidates", None) or []
                if not cands:
                    continue
                last_candidate = cands[0]
                if getattr(last_candidate, "grounding_metadata", None):
                    stream_grounding = last_candidate.grounding_metadata
                for part in getattr(getattr(last_candidate, "content", None), "parts", None) or []:
                    all_parts.append(part)
                    txt = getattr(part, "text", None)
                    if txt and not getattr(part, "thought", False):
                        streamed_text.append(txt)
                        try:
                            self.stream_callback(txt, "".join(streamed_text))
                        except Exception:
                            pass
        except Exception as error:
            mapped = self._api_error(error, "la génération en streaming")
            if streamed_text:
                # Du texte est déjà affiché : relancer dupliquerait la réponse.
                mapped.no_retry = True
            raise mapped from None

        if not all_parts:
            return None
        return SimpleNamespace(
            text="".join(streamed_text),
            usage_metadata=last_usage_meta,
            candidates=[
                SimpleNamespace(
                    content=types.Content(role="model", parts=all_parts),
                    finish_reason=getattr(last_candidate, "finish_reason", ""),
                    grounding_metadata=stream_grounding,
                )
            ],
        )

    def generate_agent_turn(
        self,
        prompt: str | None,
        tools: list[dict[str, Any]],
        continuation: Any = None,
        tool_results: list[dict[str, Any]] | None = None,
    ) -> AgentTurn:
        """Utilise function calling natif et garde les Content/Part intacts.

        L'objet Content complet renvoyé par Gemini reste dans l'historique. Le SDK
        peut ainsi retransmettre les thought signatures à l'appel suivant, sans les
        convertir en texte ni les afficher à l'utilisateur.
        """
        if not self._verified:
            self.check_available()
        try:
            from google.genai import types
        except ImportError:
            raise GeminiProviderError(
                "Le SDK Google GenAI n'est pas installé.", category="sdk_missing"
            ) from None

        history = continuation.get("contents", []) if isinstance(continuation, dict) else []
        contents = list(history)
        if prompt:
            user_parts: list[Any] = []
            images = list(getattr(self, "pending_images", []) or [])
            self.pending_images = []
            if images and self._is_real_sdk_client():
                for img in images:
                    if isinstance(img, dict) and img.get("bytes") and img.get("mime_type"):
                        try:
                            user_parts.append(
                                types.Part.from_bytes(
                                    data=img["bytes"],
                                    mime_type=img["mime_type"],
                                )
                            )
                        except Exception:
                            pass
            user_parts.append(types.Part(text=prompt))
            contents.append(types.Content(role="user", parts=user_parts))
        if tool_results:
            function_parts = []
            for result in tool_results:
                response_payload = {
                    "status": result.get("status", "unknown"),
                    "summary": result.get("summary", ""),
                    "output": result.get("output", ""),
                }
                function_response = types.FunctionResponse(
                    id=result.get("call_id") or None,
                    name=result.get("name", ""),
                    response=response_payload,
                )
                function_parts.append(
                    types.Part(function_response=function_response)
                )
            contents.append(types.Content(role="user", parts=function_parts))

        builtin_google_search = any(
            item.get("builtin") == "google_search" for item in tools
        )
        declarations = [
            types.FunctionDeclaration(
                name=item["name"],
                description=item["description"],
                parameters_json_schema=item["parameters"],
            )
            for item in tools
            if not item.get("builtin")
        ]
        config: dict[str, Any] = {
            "automatic_function_calling": types.AutomaticFunctionCallingConfig(
                disable=True
            ),
            "http_options": types.HttpOptions(timeout=90_000),
        }
        if self.max_output_tokens:
            config["max_output_tokens"] = self.max_output_tokens
        configured_tools = []
        # Search intégré et fonctions locales sont faits en tours distincts.
        # Cela évite de dépendre du mode combiné preview de Gemini 3.
        if builtin_google_search:
            configured_tools.append(types.Tool(google_search=types.GoogleSearch()))
        elif declarations:
            configured_tools.append(types.Tool(function_declarations=declarations))
        if configured_tools:
            config["tools"] = configured_tools

        client = self._get_client()
        use_stream = callable(getattr(self, "stream_callback", None)) and hasattr(
            getattr(client, "models", None), "generate_content_stream"
        )

        def run(cfg_dict: dict[str, Any], scope: str):
            cfg = types.GenerateContentConfig(**cfg_dict)
            phase = "la génération avec outils"
            if use_stream:
                streamed = self._execute(
                    lambda m: self._stream_turn(m, contents, cfg, types),
                    phase,
                    scope=scope,
                )
                if streamed is not None:
                    self._record_usage(streamed)
                    return streamed
            resp = self._execute(
                lambda m: client.models.generate_content(model=m, contents=contents, config=cfg),
                phase,
                scope=scope,
            )
            self._record_usage(resp)
            return resp

        try:
            response = run(config, "search" if builtin_google_search else "base")
        except GeminiProviderError as error:
            # Le quota de Google Search (grounding) est distinct de celui du modèle :
            # on retente UNE fois avec les seules fonctions locales.
            if (
                builtin_google_search
                and declarations
                and not error.no_retry
                and error.category in {"rate_limit", "quota_exhausted", "configuration"}
            ):
                fallback_config = dict(config)
                fallback_config["tools"] = [types.Tool(function_declarations=declarations)]
                response = run(fallback_config, "base")
            else:
                raise

        candidates = getattr(response, "candidates", None) or []
        candidate = candidates[0] if candidates else None
        response_content = getattr(candidate, "content", None)
        if response_content is not None:
            # Garder l'objet original, notamment ses parts thought_signature.
            contents.append(response_content)

        calls: list[ProviderToolCall] = []
        text_parts: list[str] = []
        sources: list[dict[str, str]] = []
        for part in getattr(response_content, "parts", None) or []:
            function_call = getattr(part, "function_call", None)
            if function_call is not None:
                arguments = getattr(function_call, "args", None) or {}
                calls.append(
                    ProviderToolCall(
                        name=getattr(function_call, "name", "") or "",
                        arguments=dict(arguments) if isinstance(arguments, dict) else {},
                        call_id=getattr(function_call, "id", "") or "",
                    )
                )
            elif getattr(part, "text", None) and not getattr(part, "thought", False):
                text_parts.append(part.text)

        grounding = getattr(candidate, "grounding_metadata", None)
        for chunk in getattr(grounding, "grounding_chunks", None) or []:
            web_source = getattr(chunk, "web", None)
            url = getattr(web_source, "uri", "") if web_source is not None else ""
            title = getattr(web_source, "title", "") if web_source is not None else ""
            if isinstance(url, str) and url.startswith("https://"):
                item = {"url": url, "title": title or url}
                if item not in sources:
                    sources.append(item)

        finish_reason = str(getattr(candidate, "finish_reason", ""))
        partial = "MAX_TOKENS" in finish_reason.upper()
        text = "".join(text_parts).strip()
        if not text and not calls and not partial:
            text = (getattr(response, "text", "") or "").strip()
        return AgentTurn(
            text=text,
            tool_calls=calls,
            continuation={"contents": contents},
            partial=partial,
            sources=sources,
        )

    # --------------------------------------------------------------- divers
    def execute(self, instruction: str = "") -> str:
        return "GeminiProvider génère du texte et n'exécute pas de commandes."

    def get_name(self) -> str:
        return "GeminiProvider"

    def get_model_name(self) -> str:
        return self.model or "Gemini (aucun modèle sélectionné)"

    def get_status_label(self) -> str:
        return "[RÉEL]"