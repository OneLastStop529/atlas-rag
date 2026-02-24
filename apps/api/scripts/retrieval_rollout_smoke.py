from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.core.retrieval_flags import resolve_advanced_retrieval_config
from app.rag.retrieval_strategy import resolve_retrieval_plan, should_run_shadow_eval


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    request_id: str
    advanced_enabled: bool
    strategy: str
    use_reranking: bool
    shadow_eval: bool


def _find_request_id_for_percent(percent: int, want_enabled: bool) -> str:
    for i in range(10000):
        request_id = f"smoke-{percent}-{i}"
        cfg = resolve_advanced_retrieval_config(request_payload={}, request_id=request_id)
        if cfg.enabled == want_enabled:
            return request_id
    raise RuntimeError(f"Could not find request_id for percent={percent}, enabled={want_enabled}")


def _run_case(name: str, request_id: str) -> ScenarioResult:
    cfg = resolve_advanced_retrieval_config(request_payload={}, request_id=request_id)
    plan = resolve_retrieval_plan(request_use_reranking=False, advanced_cfg=cfg)
    shadow = should_run_shadow_eval(advanced_cfg=cfg, request_id=request_id)
    return ScenarioResult(
        name=name,
        request_id=request_id,
        advanced_enabled=cfg.enabled,
        strategy=plan.retrieval_strategy,
        use_reranking=plan.use_reranking,
        shadow_eval=shadow,
    )


def main() -> None:
    original = {
        "adv_retrieval_enabled": settings.adv_retrieval_enabled,
        "retrieval_strategy": settings.retrieval_strategy,
        "reranker_variant": settings.reranker_variant,
        "query_rewrite_policy": settings.query_rewrite_policy,
        "adv_retrieval_rollout_percent": settings.adv_retrieval_rollout_percent,
        "adv_retrieval_eval_mode": settings.adv_retrieval_eval_mode,
        "adv_retrieval_eval_sample_percent": settings.adv_retrieval_eval_sample_percent,
        "adv_retrieval_eval_timeout_ms": settings.adv_retrieval_eval_timeout_ms,
    }

    try:
        settings.adv_retrieval_enabled = True
        settings.retrieval_strategy = "advanced_hybrid"
        settings.reranker_variant = "rrf_simple"
        settings.query_rewrite_policy = "simple"
        settings.adv_retrieval_eval_mode = "shadow"
        settings.adv_retrieval_eval_sample_percent = 5
        settings.adv_retrieval_eval_timeout_ms = 2000

        settings.adv_retrieval_rollout_percent = 0
        baseline = _run_case("baseline_only_rollout_0", request_id="smoke-rollout-0")
        assert baseline.advanced_enabled is False

        settings.adv_retrieval_rollout_percent = 100
        advanced = _run_case("advanced_rollout_100", request_id="smoke-rollout-100")
        assert advanced.advanced_enabled is True
        assert advanced.use_reranking is True

        # Toggle safety without deploy rollback: flip off then on in-process.
        settings.adv_retrieval_enabled = False
        toggled_off = _run_case("toggle_off", request_id="smoke-toggle-off")
        assert toggled_off.advanced_enabled is False
        settings.adv_retrieval_enabled = True
        toggled_on = _run_case("toggle_on", request_id="smoke-toggle-on")
        assert toggled_on.advanced_enabled is True

        settings.adv_retrieval_rollout_percent = 50
        partial_on_id = _find_request_id_for_percent(50, want_enabled=True)
        partial_off_id = _find_request_id_for_percent(50, want_enabled=False)
        partial_on = _run_case("advanced_rollout_50_enabled", request_id=partial_on_id)
        partial_off = _run_case("advanced_rollout_50_disabled", request_id=partial_off_id)
        assert partial_on.advanced_enabled is True
        assert partial_off.advanced_enabled is False

        settings.adv_retrieval_eval_sample_percent = 0
        shadow_off = _run_case("shadow_sampling_0", request_id="smoke-shadow-off")
        assert shadow_off.shadow_eval is False
        settings.adv_retrieval_eval_sample_percent = 100
        shadow_on = _run_case("shadow_sampling_100", request_id="smoke-shadow-on")
        assert shadow_on.shadow_eval is True
        settings.adv_retrieval_eval_sample_percent = 5

        results = [
            baseline,
            advanced,
            toggled_off,
            toggled_on,
            partial_on,
            partial_off,
            shadow_off,
            shadow_on,
        ]
        print("Retrieval rollout smoke scenarios:")
        for r in results:
            print(
                f"- {r.name}: request_id={r.request_id} "
                f"advanced_enabled={r.advanced_enabled} strategy={r.strategy} "
                f"use_reranking={r.use_reranking} shadow_eval={r.shadow_eval}"
            )
        print("Retrieval rollout smoke completed successfully.")
    finally:
        for key, value in original.items():
            setattr(settings, key, value)


if __name__ == "__main__":
    main()
