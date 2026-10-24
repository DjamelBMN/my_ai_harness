# RÔLE DE CE FICHIER : compare des réponses de providers chargés puis délègue la
# synthèse au ReviewAgent. Un échec individuel n'annule pas les autres réponses.

from __future__ import annotations

from core.task import Task


def _provider_failure_category(error: Exception) -> tuple[str, str]:
    category = str(getattr(error, "category", "provider")).casefold()
    status = getattr(error, "status_code", None) or getattr(error, "code", None)
    message = str(error).casefold()
    if status == 429 or category in {"quota", "rate_limit", "rate-limit"} or any(
        marker in message for marker in ("quota", "rate limit", "http 429", "429")
    ):
        return "quota", "quota atteint"
    if category in {"network", "unavailable", "connection"} or any(
        marker in message for marker in ("timeout", "connexion", "connection", "network")
    ):
        return "network", "erreur réseau ou fournisseur indisponible"
    if category in {"authentication", "missing_key", "configuration"}:
        return category, "configuration ou authentification"
    return category, "erreur du provider"


def handle(runtime, mission, skill):
    request = mission.strip()
    if not request:
        print("Utilisation : /compare <mission> (plusieurs appels API peuvent être facturés)")
        return

    candidates = []
    seen = set()
    for key, provider in runtime.orchestrator.router.providers.items():
        identity = (provider.get_name(), provider.get_model_name())
        if identity not in seen:
            seen.add(identity)
            candidates.append((key, provider))
    candidates = candidates[:4]
    if len(candidates) < 2:
        print("[COMPARE] Il faut au moins deux providers réellement chargés.")
        return

    runtime.agent_loop._event("delivery.started", skill=skill.name, operation="compare")
    responses = []
    failures = []
    for key, provider in candidates:
        label = f"{provider.get_name()} / {provider.get_model_name()}"
        runtime.agent_loop._event(
            "provider.started",
            provider=provider.get_name(),
            model=provider.get_model_name(),
            operation="compare",
        )
        try:
            answer = provider.generate(request)
            if not isinstance(answer, str) or not answer.strip():
                raise RuntimeError("réponse vide")
        except Exception as error:
            category, cause = _provider_failure_category(error)
            failures.append((label, cause))
            runtime.agent_loop._event(
                "provider.error",
                provider=provider.get_name(),
                category=category,
                operation="compare",
            )
            runtime.agent_loop._event(
                "tool.completed", tool="provider.generate", status="error"
            )
            print(f"\n[PROVIDER ERROR] Provider : {provider.get_name()} | Cause : {cause}")
            print(f"[COMPARE INDISPONIBLE] {label} — {cause}")
            continue

        responses.append((key, label, answer.strip()))
        runtime.agent_loop._event(
            "tool.completed", tool="provider.generate", status="success"
        )
        print(f"\n[COMPARE OK] {label}\n{answer.strip()[:3000]}")

    if failures:
        if responses:
            print(
                f"\n[DELIVERY STATUS] Comparaison partielle : {len(responses)}/"
                f"{len(candidates)} providers ont répondu; les échecs sont signalés."
            )
        else:
            print(
                "\n[DELIVERY STATUS] Livraison complète impossible : aucun provider "
                "n'a fourni de réponse."
            )

    if not responses:
        runtime.agent_loop._event(
            "delivery.failed", reason="compare_no_provider_response"
        )
        return

    try:
        _, reviewer = runtime.orchestrator.agent_registry.resolve("reviewer")
        successful_keys = {key for key, _, _ in responses}
        preferred = runtime.orchestrator.router.get_provider(
            reviewer.routing_key,
            intent="review",
            complexity="complex",
        )
        review_provider = preferred
        if not any(
            key in successful_keys and candidate is preferred
            for key, candidate in candidates
        ):
            review_provider = next(
                provider for key, provider in candidates if key in successful_keys
            )
        reviewer.set_provider(review_provider)
        evidence = "\n\n".join(
            f"Réponse de {label} :\n{answer[:8000]}"
            for _, label, answer in responses
        )
        task = Task(
            "Compare les réponses ci-dessous, explique les accords et divergences "
            "justifiables, puis synthétise sans inventer.",
            type="reviewer",
            context=runtime.orchestrator.context,
            explicit_agent=True,
            mode=runtime.agent_loop.tools.permissions.mode,
            skill_name=skill.name,
        )
        task.instructions = evidence
        runtime.agent_loop._event(
            "provider.started",
            provider=review_provider.get_name(),
            model=review_provider.get_model_name(),
            operation="compare_review",
        )
        print("\n[REVIEW SYNTHESIS]\n" + reviewer.run(task))
    except Exception as error:
        category, cause = _provider_failure_category(error)
        runtime.agent_loop._event(
            "provider.error", category=category, operation="compare_review"
        )
        runtime.agent_loop._event(
            "delivery.failed", reason="compare_synthesis_failed"
        )
        print(
            f"\n[REVIEW INDISPONIBLE] Synthèse impossible ({cause}); "
            "les réponses reçues restent disponibles."
        )
        return

    runtime.agent_loop._event(
        "delivery.completed", skill=skill.name, partial=bool(failures)
    )
