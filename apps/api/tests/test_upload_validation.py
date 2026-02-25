import json
import asyncio
import unittest
from io import BytesIO
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from starlette.datastructures import Headers, UploadFile

from app.api.upload import upload_document
from app.core.reliability import RetryableDependencyError


def make_upload_file(
    content: bytes, *, filename: str = "sample.txt", content_type: str = "text/plain"
) -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def parse_json_response(response) -> dict:
    return json.loads(response.body.decode("utf-8"))


class UploadValidationTests(unittest.TestCase):
    def test_invalid_embeddings_returns_structured_validation_error(self):
        response = asyncio.run(
            upload_document(
            file=make_upload_file(b"hello world"),
            embeddings_provider="not-a-provider",
            chunk_chars=700,
            overlap_chars=100,
            )
        )

        self.assertEqual(response.status_code, 400)
        payload = parse_json_response(response)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("embeddings_provider", payload["error"]["fields"])

    def test_invalid_chunk_bounds_returns_structured_validation_error(self):
        response = asyncio.run(
            upload_document(
            file=make_upload_file(b"hello world"),
            embeddings_provider="hash",
            chunk_chars=100,
            overlap_chars=100,
            )
        )

        self.assertEqual(response.status_code, 400)
        payload = parse_json_response(response)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "VALIDATION_ERROR")
        self.assertEqual(
            payload["error"]["fields"]["overlap_chars"],
            "overlap_chars must be less than chunk_chars",
        )

    @patch("app.api.upload.insert_document_and_chunks")
    @patch("app.api.upload.EmbeddingsProvider")
    @patch("app.api.upload.get_db_vector_dim_session")
    @patch("app.api.upload.session_scope")
    @patch("app.api.upload.lc_recursive_ch_text")
    @patch("app.api.upload.extract_text_from_file", new_callable=AsyncMock)
    def test_success_response_echoes_chunk_config(
        self,
        mock_extract_text,
        mock_chunk_text,
        mock_session_scope,
        mock_get_dim,
        mock_embeddings_provider,
        mock_insert,
    ):
        mock_extract_text.return_value = "hello world"
        mock_chunk_text.return_value = ["hello world"]
        mock_get_dim.return_value = 384

        mock_session = mock_session_scope.return_value.__enter__.return_value
        mock_session.execute.return_value = None

        mock_embeddings_impl = mock_embeddings_provider.return_value
        mock_embeddings_impl.embed_documents.return_value = [[0.1] * 384]
        mock_insert.return_value = ("doc-123", 1)

        response = asyncio.run(
            upload_document(
                file=make_upload_file(b"hello world"),
                collection="default",
                embeddings_provider="hash",
                chunk_chars=512,
                overlap_chars=64,
            )
        )

        self.assertTrue(response["ok"])
        self.assertEqual(response["chunk_config"]["chunk_chars"], 512)
        self.assertEqual(response["chunk_config"]["overlap_chars"], 64)

    @patch("app.api.upload.insert_document_and_chunks")
    @patch("app.api.upload.EmbeddingsProvider")
    @patch("app.api.upload.get_db_vector_dim_session")
    @patch("app.api.upload.session_scope")
    @patch("app.api.upload.lc_recursive_ch_text")
    @patch("app.api.upload.extract_text_from_file", new_callable=AsyncMock)
    def test_dependency_failure_returns_503_http_exception(
        self,
        mock_extract_text,
        mock_chunk_text,
        mock_session_scope,
        mock_get_dim,
        mock_embeddings_provider,
        mock_insert,
    ):
        mock_extract_text.return_value = "hello world"
        mock_chunk_text.return_value = ["hello world"]
        mock_get_dim.return_value = 384
        mock_insert.return_value = ("doc-123", 1)

        mock_session = mock_session_scope.return_value.__enter__.return_value
        mock_session.execute.return_value = None

        mock_embeddings_impl = mock_embeddings_provider.return_value
        mock_embeddings_impl.embed_documents.side_effect = RetryableDependencyError("provider down")

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(
                upload_document(
                    file=make_upload_file(b"hello world"),
                    collection="default",
                    embeddings_provider="hash",
                    chunk_chars=512,
                    overlap_chars=64,
                )
            )

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("retryable=True", str(ctx.exception.detail))


if __name__ == "__main__":
    unittest.main()
