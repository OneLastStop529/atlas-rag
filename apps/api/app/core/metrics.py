from __future__ import annotations

from collections import defaultdict
from threading import Lock
from typing import Iterable

_lock = Lock()

_HTTP_LATENCY_BUCKETS = (0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
_SHADOW_JACCARD_BUCKETS = (
    0.0,
    0.1,
    0.2,
    0.3,
    0.4,
    0.5,
    0.6,
    0.7,
    0.8,
    0.9,
    1.0,
)
_SHADOW_LATENCY_DELTA_MS_BUCKETS = (
    -500.0,
    -250.0,
    -100.0,
    -50.0,
    0.0,
    50.0,
    100.0,
    250.0,
    500.0,
    1000.0,
    2000.0,
    5000.0,
)
_SHADOW_CONTEXT_TOKEN_DELTA_BUCKETS = (
    -500.0,
    -250.0,
    -100.0,
    -50.0,
    0.0,
    50.0,
    100.0,
    250.0,
    500.0,
    1000.0,
    2000.0,
)

_http_requests_total: dict[tuple[str, str, str], int] = defaultdict(int)
_http_request_latency_bucket: dict[tuple[str, str, str], int] = defaultdict(int)
_http_request_latency_sum: dict[tuple[str, str], float] = defaultdict(float)
_http_request_latency_count: dict[tuple[str, str], int] = defaultdict(int)

_provider_failures_total: dict[tuple[str, str], int] = defaultdict(int)
_chat_stream_lifecycle_total: dict[str, int] = defaultdict(int)
_ingestion_files_total = 0
_ingestion_chunks_total = 0
_retrieval_shadow_eval_total: dict[tuple[str, str, str], int] = defaultdict(int)
_retrieval_shadow_top1_total: dict[str, int] = defaultdict(int)
_retrieval_shadow_jaccard_bucket: dict[tuple[str, str, str, str], int] = defaultdict(
    int
)
_retrieval_shadow_jaccard_sum: dict[tuple[str, str, str], float] = defaultdict(float)
_retrieval_shadow_jaccard_count: dict[tuple[str, str, str], int] = defaultdict(int)
_retrieval_shadow_latency_delta_ms_bucket: dict[tuple[str, str, str, str], int] = (
    defaultdict(int)
)
_retrieval_shadow_latency_delta_ms_sum: dict[tuple[str, str, str], float] = defaultdict(
    float
)
_retrieval_shadow_latency_delta_ms_count: dict[tuple[str, str, str], int] = defaultdict(
    int
)
_retrieval_shadow_context_token_delta_bucket: dict[tuple[str, str, str, str], int] = (
    defaultdict(int)
)
_retrieval_shadow_context_token_delta_sum: dict[tuple[str, str, str], float] = (
    defaultdict(float)
)
_retrieval_shadow_context_token_delta_count: dict[tuple[str, str, str], int] = (
    defaultdict(int)
)


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _labels(**labels: str) -> str:
    ordered = [f'{k}="{_escape_label(v)}"' for k, v in sorted(labels.items())]
    return "{" + ",".join(ordered) + "}"


def _iter_histogram_buckets(value_seconds: float) -> Iterable[str]:
    for upper_bound in _HTTP_LATENCY_BUCKETS:
        if value_seconds <= upper_bound:
            yield str(upper_bound)
    yield "+Inf"


def _iter_buckets(value: float, buckets: Iterable[float]) -> Iterable[str]:
    for upper_bound in buckets:
        if value <= upper_bound:
            yield str(upper_bound)
    yield "+Inf"


def observe_http_request(
    *,
    route: str,
    method: str,
    status_code: int,
    latency_ms: int,
) -> None:
    method_u = method.upper()
    status = str(status_code)
    latency_seconds = max(latency_ms, 0) / 1000.0

    with _lock:
        _http_requests_total[(route, method_u, status)] += 1
        _http_request_latency_sum[(route, method_u)] += latency_seconds
        _http_request_latency_count[(route, method_u)] += 1
        for bucket in _iter_histogram_buckets(latency_seconds):
            _http_request_latency_bucket[(route, method_u, bucket)] += 1


def inc_provider_failure(*, dependency: str, error_code: str) -> None:
    with _lock:
        _provider_failures_total[(dependency, error_code)] += 1


def inc_chat_stream_lifecycle(*, status: str) -> None:
    with _lock:
        _chat_stream_lifecycle_total[status] += 1


def observe_ingestion_throughput(*, files: int, chunks: int) -> None:
    with _lock:
        global _ingestion_files_total, _ingestion_chunks_total
        _ingestion_files_total += files
        _ingestion_chunks_total += chunks


def observe_retrieval_shadow_eval(
    *,
    status: str,
    primary_strategy: str,
    shadow_strategy: str,
    jaccard: float,
    latency_delta_ms: int,
    context_token_delta: int,
    top1_source_same: bool,
) -> None:
    status_label = status or "unknown"
    primary_label = primary_strategy or "unknown"
    shadow_label = shadow_strategy or "unknown"
    metric_key = (status_label, primary_label, shadow_label)

    jaccard_value = max(0.0, min(1.0, float(jaccard)))
    latency_delta_value = float(latency_delta_ms)
    context_token_delta_value = float(context_token_delta)
    top1_label = "true" if top1_source_same else "false"

    with _lock:
        _retrieval_shadow_eval_total[metric_key] += 1
        _retrieval_shadow_top1_total[top1_label] += 1

        _retrieval_shadow_jaccard_sum[metric_key] += jaccard_value
        _retrieval_shadow_jaccard_count[metric_key] += 1
        for bucket in _iter_buckets(jaccard_value, _SHADOW_JACCARD_BUCKETS):
            _retrieval_shadow_jaccard_bucket[(*metric_key, bucket)] += 1

        _retrieval_shadow_latency_delta_ms_sum[metric_key] += latency_delta_value
        _retrieval_shadow_latency_delta_ms_count[metric_key] += 1
        for bucket in _iter_buckets(
            latency_delta_value, _SHADOW_LATENCY_DELTA_MS_BUCKETS
        ):
            _retrieval_shadow_latency_delta_ms_bucket[(*metric_key, bucket)] += 1

        _retrieval_shadow_context_token_delta_sum[metric_key] += (
            context_token_delta_value
        )
        _retrieval_shadow_context_token_delta_count[metric_key] += 1
        for bucket in _iter_buckets(
            context_token_delta_value, _SHADOW_CONTEXT_TOKEN_DELTA_BUCKETS
        ):
            _retrieval_shadow_context_token_delta_bucket[(*metric_key, bucket)] += 1


def render_prometheus_text() -> str:
    lines: list[str] = []
    with _lock:
        lines.append(
            "# HELP atlas_http_requests_total HTTP request count by route, method, and status."
        )
        lines.append("# TYPE atlas_http_requests_total counter")
        for (route, method, status), value in sorted(_http_requests_total.items()):
            lines.append(
                f"atlas_http_requests_total{_labels(route=route, method=method, status=status)} {value}"
            )

        lines.append("# HELP atlas_http_request_latency_seconds HTTP request latency.")
        lines.append("# TYPE atlas_http_request_latency_seconds histogram")
        for (route, method, le), value in sorted(_http_request_latency_bucket.items()):
            lines.append(
                f"atlas_http_request_latency_seconds_bucket{_labels(route=route, method=method, le=le)} {value}"
            )
        for (route, method), value in sorted(_http_request_latency_count.items()):
            labels = _labels(route=route, method=method)
            lines.append(f"atlas_http_request_latency_seconds_count{labels} {value}")
        for (route, method), value in sorted(_http_request_latency_sum.items()):
            labels = _labels(route=route, method=method)
            lines.append(f"atlas_http_request_latency_seconds_sum{labels} {value:.6f}")

        lines.append(
            "# HELP atlas_provider_failures_total Provider failures by dependency and normalized code."
        )
        lines.append("# TYPE atlas_provider_failures_total counter")
        for (dependency, error_code), value in sorted(_provider_failures_total.items()):
            lines.append(
                f"atlas_provider_failures_total{_labels(dependency=dependency, error_code=error_code)} {value}"
            )

        lines.append(
            "# HELP atlas_chat_stream_lifecycle_total Chat stream lifecycle counts."
        )
        lines.append("# TYPE atlas_chat_stream_lifecycle_total counter")
        for status, value in sorted(_chat_stream_lifecycle_total.items()):
            lines.append(
                f"atlas_chat_stream_lifecycle_total{_labels(status=status)} {value}"
            )

        lines.append("# HELP atlas_ingestion_files_total Number of ingested files.")
        lines.append("# TYPE atlas_ingestion_files_total counter")
        lines.append(f"atlas_ingestion_files_total {_ingestion_files_total}")

        lines.append("# HELP atlas_ingestion_chunks_total Number of ingested chunks.")
        lines.append("# TYPE atlas_ingestion_chunks_total counter")
        lines.append(f"atlas_ingestion_chunks_total {_ingestion_chunks_total}")

        lines.append(
            "# HELP atlas_retrieval_shadow_eval_total Retrieval shadow-eval sample count."
        )
        lines.append("# TYPE atlas_retrieval_shadow_eval_total counter")
        for (status, primary_strategy, shadow_strategy), value in sorted(
            _retrieval_shadow_eval_total.items()
        ):
            lines.append(
                "atlas_retrieval_shadow_eval_total"
                + _labels(
                    status=status,
                    primary_strategy=primary_strategy,
                    shadow_strategy=shadow_strategy,
                )
                + f" {value}"
            )

        lines.append(
            "# HELP atlas_retrieval_shadow_top1_agreement_total Top-1 source agreement counts."
        )
        lines.append("# TYPE atlas_retrieval_shadow_top1_agreement_total counter")
        for matched, value in sorted(_retrieval_shadow_top1_total.items()):
            lines.append(
                "atlas_retrieval_shadow_top1_agreement_total"
                + _labels(match=matched)
                + f" {value}"
            )

        lines.append(
            "# HELP atlas_retrieval_shadow_jaccard Jaccard overlap between primary and shadow chunks."
        )
        lines.append("# TYPE atlas_retrieval_shadow_jaccard histogram")
        for (status, primary_strategy, shadow_strategy, le), value in sorted(
            _retrieval_shadow_jaccard_bucket.items()
        ):
            lines.append(
                "atlas_retrieval_shadow_jaccard_bucket"
                + _labels(
                    status=status,
                    primary_strategy=primary_strategy,
                    shadow_strategy=shadow_strategy,
                    le=le,
                )
                + f" {value}"
            )
        for (status, primary_strategy, shadow_strategy), value in sorted(
            _retrieval_shadow_jaccard_count.items()
        ):
            lines.append(
                "atlas_retrieval_shadow_jaccard_count"
                + _labels(
                    status=status,
                    primary_strategy=primary_strategy,
                    shadow_strategy=shadow_strategy,
                )
                + f" {value}"
            )
        for (status, primary_strategy, shadow_strategy), value in sorted(
            _retrieval_shadow_jaccard_sum.items()
        ):
            lines.append(
                "atlas_retrieval_shadow_jaccard_sum"
                + _labels(
                    status=status,
                    primary_strategy=primary_strategy,
                    shadow_strategy=shadow_strategy,
                )
                + f" {value:.6f}"
            )

        lines.append(
            "# HELP atlas_retrieval_shadow_latency_delta_ms Shadow minus primary retrieval latency."
        )
        lines.append("# TYPE atlas_retrieval_shadow_latency_delta_ms histogram")
        for (status, primary_strategy, shadow_strategy, le), value in sorted(
            _retrieval_shadow_latency_delta_ms_bucket.items()
        ):
            lines.append(
                "atlas_retrieval_shadow_latency_delta_ms_bucket"
                + _labels(
                    status=status,
                    primary_strategy=primary_strategy,
                    shadow_strategy=shadow_strategy,
                    le=le,
                )
                + f" {value}"
            )
        for (status, primary_strategy, shadow_strategy), value in sorted(
            _retrieval_shadow_latency_delta_ms_count.items()
        ):
            lines.append(
                "atlas_retrieval_shadow_latency_delta_ms_count"
                + _labels(
                    status=status,
                    primary_strategy=primary_strategy,
                    shadow_strategy=shadow_strategy,
                )
                + f" {value}"
            )
        for (status, primary_strategy, shadow_strategy), value in sorted(
            _retrieval_shadow_latency_delta_ms_sum.items()
        ):
            lines.append(
                "atlas_retrieval_shadow_latency_delta_ms_sum"
                + _labels(
                    status=status,
                    primary_strategy=primary_strategy,
                    shadow_strategy=shadow_strategy,
                )
                + f" {value:.6f}"
            )

        lines.append(
            "# HELP atlas_retrieval_shadow_context_token_delta Shadow minus primary context token proxy."
        )
        lines.append("# TYPE atlas_retrieval_shadow_context_token_delta histogram")
        for (status, primary_strategy, shadow_strategy, le), value in sorted(
            _retrieval_shadow_context_token_delta_bucket.items()
        ):
            lines.append(
                "atlas_retrieval_shadow_context_token_delta_bucket"
                + _labels(
                    status=status,
                    primary_strategy=primary_strategy,
                    shadow_strategy=shadow_strategy,
                    le=le,
                )
                + f" {value}"
            )
        for (status, primary_strategy, shadow_strategy), value in sorted(
            _retrieval_shadow_context_token_delta_count.items()
        ):
            lines.append(
                "atlas_retrieval_shadow_context_token_delta_count"
                + _labels(
                    status=status,
                    primary_strategy=primary_strategy,
                    shadow_strategy=shadow_strategy,
                )
                + f" {value}"
            )
        for (status, primary_strategy, shadow_strategy), value in sorted(
            _retrieval_shadow_context_token_delta_sum.items()
        ):
            lines.append(
                "atlas_retrieval_shadow_context_token_delta_sum"
                + _labels(
                    status=status,
                    primary_strategy=primary_strategy,
                    shadow_strategy=shadow_strategy,
                )
                + f" {value:.6f}"
            )

    lines.append("")
    return "\n".join(lines)
