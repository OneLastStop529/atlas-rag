import os
import unittest
from contextlib import contextmanager

from app.core.startup_config import validate_startup_config


@contextmanager
def _temp_env(overrides: dict[str, str | None]):
    original = {key: os.environ.get(key) for key in overrides}
    try:
        for key, value in overrides.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class StartupConfigValidationTests(unittest.TestCase):
    def test_valid_ollama_hash_configuration_passes(self):
        with _temp_env(
            {
                "DATABASE_URL": "postgresql://rag:rag@localhost:5432/rag",
                "LLM_PROVIDER": "ollama",
                "OLLAMA_BASE_URL": "http://localhost:11434",
                "EMBEDDINGS_PROVIDER": "hash",
                "HASH_EMBEDDING_DIM": "384",
                "EXPECTED_EMBEDDING_DIM": "384",
            }
        ):
            validate_startup_config()

    def test_missing_database_url_fails(self):
        with _temp_env(
            {
                "DATABASE_URL": None,
                "LLM_PROVIDER": "ollama",
                "OLLAMA_BASE_URL": "http://localhost:11434",
                "EMBEDDINGS_PROVIDER": "hash",
            }
        ):
            with self.assertRaises(RuntimeError) as ctx:
                validate_startup_config()
            self.assertIn("DATABASE_URL is required", str(ctx.exception))

    def test_invalid_llm_provider_fails(self):
        with _temp_env(
            {
                "DATABASE_URL": "postgresql://rag:rag@localhost:5432/rag",
                "LLM_PROVIDER": "bad_provider",
                "EMBEDDINGS_PROVIDER": "hash",
            }
        ):
            with self.assertRaises(RuntimeError) as ctx:
                validate_startup_config()
            self.assertIn("LLM_PROVIDER must be one of", str(ctx.exception))

    def test_invalid_embedding_dimension_combination_fails(self):
        with _temp_env(
            {
                "DATABASE_URL": "postgresql://rag:rag@localhost:5432/rag",
                "LLM_PROVIDER": "ollama",
                "OLLAMA_BASE_URL": "http://localhost:11434",
                "EMBEDDINGS_PROVIDER": "hash",
                "HASH_EMBEDDING_DIM": "768",
                "EXPECTED_EMBEDDING_DIM": "384",
            }
        ):
            with self.assertRaises(RuntimeError) as ctx:
                validate_startup_config()
            self.assertIn("must match EXPECTED_EMBEDDING_DIM", str(ctx.exception))

    def test_invalid_openai_base_url_fails(self):
        with _temp_env(
            {
                "DATABASE_URL": "postgresql://rag:rag@localhost:5432/rag",
                "LLM_PROVIDER": "openai",
                "OPENAI_BASE_URL": "not-a-url",
                "EMBEDDINGS_PROVIDER": "hash",
                "HASH_EMBEDDING_DIM": "384",
                "EXPECTED_EMBEDDING_DIM": "384",
            }
        ):
            with self.assertRaises(RuntimeError) as ctx:
                validate_startup_config()
            self.assertIn("OPENAI_BASE_URL must be a valid http(s) URL", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
