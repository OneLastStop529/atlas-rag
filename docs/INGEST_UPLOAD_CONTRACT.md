# Ingestion Upload Contract (Milestone 4)

This document is the single source of truth for the upload API and the upload UI payload.

## Endpoint

- Method: `POST`
- Path: `/upload`
- Content-Type: `multipart/form-data`

## Request Fields

- `file` (required, file)
- Accepted MIME types: `text/plain`, `application/pdf`
- `collection` (optional, string, default: `"default"`)
- `chunk_chars` (optional, integer, default: `2000`)
- `overlap_chars` (optional, integer, default: `200`)
- `embeddings` (optional, enum, default: `"hash"`)
- Allowed `embeddings` values: `"hash"`, `"sentence-transformers"`

## Validation Rules

- `file` must be present and have a filename.
- `file` MIME type must be in supported list.
- `embeddings` must be one of allowed enum values.
- `chunk_chars` must be a positive integer.
- `overlap_chars` must be a non-negative integer.
- `overlap_chars` must be `< chunk_chars`.

## Success Response

```json
{
  "ok": true,
  "doc_id": "uuid",
  "filename": "example.pdf",
  "collection": "default",
  "status": "ingested",
  "chunks_count": 12,
  "chunk_config": {
    "chunk_chars": 2000,
    "overlap_chars": 200
  },
  "embeddings_provider": "hash"
}
```

## Error Response (Target for Milestone 4 UI Validation UX)

Use this shape for all `4xx` validation failures so UI can map errors to fields.

```json
{
  "ok": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid upload payload",
    "fields": {
      "chunk_chars": "chunk_chars must be > 0",
      "overlap_chars": "overlap_chars must be less than chunk_chars"
    }
  }
}
```

## Current Implementation Snapshot

- Backend route and payload parsing: `apps/api/app/api/upload.py`
- UI payload builder: `apps/web/src/lib/upload.ts`
- Upload page controls: `apps/web/src/app/upload/page.tsx`

Observed behavior today:

- API already accepts PDF and text uploads.
- UI already sends `chunk_chars` and `overlap_chars`, but upload page does not expose controls for them yet.
- API validates MIME type, filename, and `embeddings` enum.
- API does not yet enforce numeric bounds for `chunk_chars` and `overlap_chars`.
- API currently returns FastAPI default error shape (`detail`) rather than field-level errors.
