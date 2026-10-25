# RÔLE DE CE FICHIER :
# Rejoue l'exécution complète d'une mission enregistrée à partir de son run_id.
# Affiche la chronologie exacte des événements, des appels d'outils et des décisions.

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


def replay_mission(
    run_id: str,
    log_dir: str | Path = "workspace/.harness",
    speed: float = 0.0,
) -> bool:
    """Rejoue pas à pas les événements et métriques associés à un run_id."""
    log_dir_p = Path(log_dir)
    events_file = log_dir_p / "events.jsonl"
    metrics_file = log_dir_p / "metrics.jsonl"

    events: list[dict[str, Any]] = []
    if events_file.exists():
        for line in events_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if rec.get("task_id") == run_id or rec.get("data", {}).get("task_id") == run_id:
                    events.append(rec)
            except Exception:
                continue

    metric_record: dict[str, Any] | None = None
    if metrics_file.exists():
        for line in metrics_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if rec.get("task_id") == run_id:
                    metric_record = rec
                    break
            except Exception:
                continue

    if not events and not metric_record:
        print(f"❌ Aucun enregistrement trouvé pour le run_id '{run_id}' dans {log_dir}")
        return False

    print("=" * 65)
    print(f"🔄 REPLAY CHRONOLOGIQUE DE LA MISSION : {run_id}")
    print("=" * 65)

    if metric_record:
        print(f"🎯 Objectif : {metric_record.get('objective')}")
        print(f"📊 Statut final : {metric_record.get('status')} ({metric_record.get('duration_seconds')}s)")
        print(f"💰 Coût estimé : ${metric_record.get('user_cost_approx_usd')} (Tokens : {metric_record.get('total_tokens')})")
        print("-" * 65)

    if not events:
        print("ℹ️ Seul le résumé de métriques est disponible pour ce run_id.")
        return True

    start_t = events[0].get("timestamp", 0.0) if events else 0.0
    for idx, ev in enumerate(events, 1):
        name = ev.get("name", "unknown")
        data = ev.get("data", {})
        ts = ev.get("timestamp", 0.0)
        rel_t = max(0.0, ts - start_t) if start_t else 0.0

        if name in {"task.started", "agent.started"}:
            print(f"[{rel_t:.2f}s] 🚀 DÉBUT DE MISSION | Agent : {data.get('agent')} | Mode : {data.get('mode')}")
        elif name == "plan.created":
            print(f"[{rel_t:.2f}s] 📋 PLAN CRÉÉ : {data.get('steps_count')} étape(s)")
        elif name == "tool.called":
            args_str = json.dumps(data.get("arguments", {}), ensure_ascii=False)
            print(f"[{rel_t:.2f}s] ⚙️ OUTIL APPELÉ : {data.get('tool')} {args_str[:80]}")
        elif name == "tool.completed":
            print(f"[{rel_t:.2f}s] ✅ OUTIL COMPLÉTÉ : {data.get('tool')} ({data.get('status')})")
        elif name == "provider.failover":
            print(f"[{rel_t:.2f}s] 🔀 FAILOVER PROVIDER : {data.get('from')} -> {data.get('to')} (Raison : {data.get('reason')})")
        elif name == "checkpoint.created":
            print(f"[{rel_t:.2f}s] 📸 CHECKPOINT SHADOW GIT : {data.get('checkpoint_id')}")
        elif name == "checkpoint.rollback":
            print(f"[{rel_t:.2f}s] ⏪ ROLLBACK DÉCLENCHÉ vers {data.get('checkpoint_id')}")
        elif name == "verification.completed":
            print(f"[{rel_t:.2f}s] 🔍 VÉRIFICATION : {data.get('status')} | Résumé : {data.get('summary', '')[:80]}")
        elif name == "critic.evaluated":
            print(f"[{rel_t:.2f}s] ⚖️ CRITIC INDÉPENDANT : {data.get('decision')} (Défauts : {len(data.get('defects', []))})")
        elif name == "delivery.completed":
            print(f"[{rel_t:.2f}s] 📦 LIVRABLE VALIDÉ : {data.get('summary', '')[:100]}")
        elif name == "delivery.failed":
            print(f"[{rel_t:.2f}s] ❌ MISSION ÉCHOUÉE : {data.get('reason', '')[:100]}")
        else:
            print(f"[{rel_t:.2f}s] 🔹 {name} : {json.dumps(data, ensure_ascii=False)[:80]}")

    print("=" * 65)
    print("🏁 FIN DU REPLAY")
    print("=" * 65)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Rejoue une mission agentique NeoHarness par son run_id.")
    parser.add_argument("run_id", help="Identifiant unique de la tâche / mission")
    parser.add_argument("--log-dir", default="workspace/.harness", help="Dossier contenant les journaux metrics.jsonl et events.jsonl")
    args = parser.parse_args()

    success = replay_mission(args.run_id, log_dir=args.log_dir)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
