# FRIE Phase 4 -- Document Upload + Storage Foundation

## 1. Objective

Let an authenticated user upload a financial document, store the file
safely on local disk, persist honest metadata, list and re-download
their own documents with ownership enforcement. Foundation only for
Phase 5 OCR/extraction: no text extraction, no parsing, no features,
no scoring in this phase.

## 2. Existing Phase 2 Document Schema

Reused unchanged: the `documents` table (id, user_id, document_type,
original_filename, storage_reference, uploaded_at, processing_status,
extraction_status, source_type, review_status, timestamps) plus the
`POST /documents/metadata`, `GET /documents`, `GET /documents/{id}`
routes. Phase 4 adds upload/storage around this schema; no second
document table exists.

## 3. Supported Document Types

Exactly the six Phase 1.5 classes (no new categories invented):
`salary_income_proof`, `bank_statement`, `credit_report`,
`loan_document`, `insurance_document`, `investment_statement`. The UI
shows human-readable labels (e.g. "Salary / Income Proof",
"Bank Statement"); unknown types are rejected with 422.

## 4. Supported File Formats

PDF, PNG, JPG/JPEG. Enforcement is by extension allow-list plus
magic-byte verification (PDF `%PDF-` header, PNG 8-byte signature,
JPEG SOI marker); the browser MIME is advisory only and must not
contradict the magic bytes. No other format is accepted.

## 5. Upload API

`POST /documents/upload` (multipart/form-data, 201 on success):
`document_type` form field (required, validated against the six types)
plus `file` part (required). Authenticated user owns the created row.
On success returns the stored metadata. Status mapping: 401
unauthenticated, 422 missing part/unknown type/empty file, 413 over
limit, 415 unsupported extension or content mismatch, 500 only if the
database write fails after a successful file write (with orphan
cleanup, below).

## 6. Storage Architecture

Local filesystem under a configured root: `FRIE_STORAGE_DIR`, default
`<backend>/storage/documents/` (created automatically). Files live
outside source code; the directory is git-ignored so customer
documents can never be committed. The database stores only the
generated filename as `storage_reference`; absolute paths are never
persisted and never leave the server.

## 7. Filename Safety

Stored names are `uuid4().hex + validated extension`
(e.g. `b3c14...ef.pdf`); the original filename is kept solely as
display metadata (basename only). Every resolution is containment-
checked against the storage root, blocking `../`, absolute paths, and
filename injection. Verified live: a `"my statement.pdf"` upload
stored as hex with metadata intact.

## 8. File Validation

Implemented in `app/services/storage_service.py` and only there:
non-empty check, size cap before buffering completes (never truncated),
extension allow-list, magic-byte match, advisory MIME consistency
check. Documented limits of the approach: no antivirus scanning, no
encrypted storage, no production hardening -- none claimed.

## 9. File-Size Limit

10 MB per file by default, configurable via `FRIE_MAX_UPLOAD_MB`
(clamped to a positive integer). Oversized uploads are rejected whole
with HTTP 413; files are never truncated.

## 10. Database Metadata

New uploads populate the existing row as: `processing_status =
UPLOADED`, `extraction_status = PENDING`, `review_status = PENDING`,
`source_type = "user_upload"`, plus type, original filename, storage
reference, and timestamps. No state claims EXTRACTED, PROCESSED, or
VERIFIED anywhere in Phase 4.

## 11. Processing/Extraction States

Upload sets UPLOADED/PENDING/PENDING (verified live). The allowed
status vocabularies already exist in the model for Phase 5, which will
be the first code permitted to advance them. The UI labels pending
extraction explicitly and notes that extraction arrives in Phase 5.

## 12. Ownership/Security

Bearer-token authentication on every document route; all reads/writes
filtered by the authenticated user; cross-user metadata and file
access return 404 without revealing existence; download streams bytes
with a generated `attachment; filename="document-{id}.{ext}"` header
(original names never enter HTTP headers or URLs); `Cache-Control:
no-store`; safe error messages without paths or file contents. Not
claimed: bank-grade/encrypted/scanned storage or production security.

## 13. Frontend UX

`src/services/api.ts` gained `uploadDocument` (XMLHttpRequest with
real progress percent; boundary left to the browser),
`listDocuments`, `downloadDocument` (authenticated blob), plus
`DOCUMENT_LABELS`/`DOCUMENT_TYPES` and extension pre-checks; no raw
fetch calls in components. The Documents page shows an upload card
(type selector, file picker with name/size, progress bar, loading,
success, and error states; upload requires both type and file; success
renders only after the backend 201) and six per-type cards with
uploaded filename/date/extraction state or an honest "Not uploaded".
Download works per document. Profile readiness now shows the real
uploaded-type count (`X / 6`), and a "profile ready" banner links
Profile -> Documents. Profile completeness logic is untouched
(documents never inflate the 18/18).

## 14. Test Strategy

Synthetic in-memory files only (minimal valid PDF/PNG/JPEG byte
strings; no real documents): format acceptance, extension/MIME/content
rejection, empty/oversized/missing-part/missing-type/unauthenticated
cases, metadata defaults, on-disk existence, reference safety, original
name preservation, initial statuses, list/detail/file isolation across
users, DB-failure orphan cleanup (simulated), all-six-types
acceptance, and storage-location/ignore assertions. Test storage is
redirected per-test to temp dirs via `FRIE_STORAGE_DIR` (never the
real directory) and auto-cleaned.

## 15. Test Results

`pytest -q`: **66 passed** (51 pre-existing + 15 new), 1 pre-existing
third-party warning. Live verification against a running backend:
register 201, PDF upload 201 with UPLOADED/PENDING, owner list 1 vs
other user 0, owner download 200 with correct bytes, cross-user
download 404, bad extension 415. `/health` 200; empty `/predict`
still 422.

## 16. Limitations

Local disk only (no cloud); 10 MB default cap; no OCR/extraction (Phase
5); no transaction parsing; statuses advance only in later phases;
opaque tokens without rotation (Phase 2 scope); demo seed unchanged.

## 17. Phase 5 Handoff

Phase 5 receives: authenticated per-user file bytes retrievable by
document id with type/filename metadata, honest UPLOADED/PENDING rows,
and the six-class taxonomy. Suggested starting point: a background or
on-demand extraction job reading `storage_reference` for rows in
UPLOADED/PENDING state and writing extracted values plus status
transitions -- without touching upload, storage, validation, or the
prediction contract.

IMPLEMENTED IN PHASE 4: everything in Sections 3-15.
PLANNED FOR PHASE 5+: OCR, extraction, parsing, features, scoring.
