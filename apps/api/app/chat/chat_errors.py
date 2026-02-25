from app.core.reliability import DependencyError


def chat_error_code(exc: Exception, stage: str | None) -> str:
    message = str(exc).lower()
    if stage == "generate":
        return "llm_stream_error"
    if "embed" in message:
        return "embeddings_unavailable"
    if "timeout" in message or "statement_timeout" in message:
        return "db_timeout"
    if isinstance(exc, DependencyError):
        return "dependency_unavailable"
    return "chat_pipeline_error"


def dependency_from_error_code(error_code: str) -> str:
    if error_code == "llm_stream_error":
        return "llm"
    if error_code == "embeddings_unavailable":
        return "embeddings"
    if error_code == "db_timeout":
        return "db"
    return "chat"


# Backward-compatible aliases while refactor is in progress.
_chat_error_code = chat_error_code
_dependency_from_error_code = dependency_from_error_code
