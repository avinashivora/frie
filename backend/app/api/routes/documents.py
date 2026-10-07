"""Document metadata and file-upload endpoints. Phase 4 stores files; no OCR yet."""

import json
from datetime import date
from math import isfinite

from fastapi import APIRouter, Body, Depends, File, Form, UploadFile, status
from fastapi.exceptions import HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import Document, Extraction, FinancialFeature, User
from app.db.session import get_db
from app.schemas.documents import DocumentCreate, DocumentRead
from app.schemas.extraction import ExtractionRead
from app.schemas.financial_status import ReviewRequest
from app.services import document_service
from app.services import extraction_service
from app.services import storage_service
from app.services.bank_import import import_bank_statement, ImportResult
from app.services.storage_service import UploadValidationError

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/metadata", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def create_metadata(
    payload: DocumentCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> DocumentRead:
    try:
        document = document_service.create_document_metadata(
            db,
            user=user,
            document_type=payload.document_type,
            original_filename=payload.original_filename,
            storage_reference=payload.storage_reference,
            source_type=payload.source_type,
        )
    except document_service.UnknownDocumentTypeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return DocumentRead.model_validate(document)


@router.get("", response_model=list[DocumentRead])
def list_own_documents(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[DocumentRead]:
    return [DocumentRead.model_validate(item) for item in document_service.list_documents(db, user=user)]


@router.get("/{document_id}", response_model=DocumentRead)
def read_own_document(
    document_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> DocumentRead:
    document = document_service.get_document(db, user=user, document_id=document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return DocumentRead.model_validate(document)


_STATUS_BY_KIND = {"too_large": 413, "extension": 415, "content": 415, "empty": 422, "path": 422}


@router.post("/upload", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_own_document(
    document_type: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentRead:
    try:
        document_service.require_known_type(document_type)
    except document_service.UnknownDocumentTypeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    data = b""
    try:
        data = await _read_bounded(file)
        extension = storage_service.validate_upload(
            filename=file.filename, content_type=file.content_type, data=data
        )
    except UploadValidationError as exc:
        raise HTTPException(
            status_code=_STATUS_BY_KIND.get(exc.kind, 422), detail=str(exc)
        ) from exc

    filename = storage_service.store_file(data, extension)
    try:
        document = document_service.create_document_metadata(
            db,
            user=user,
            document_type=document_type,
            original_filename=storage_service.original_basename(file.filename),
            storage_reference=filename,
            source_type="user_upload",
        )
    except Exception:
        storage_service.delete_file(filename)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to store the document.")
    return DocumentRead.model_validate(document)


@router.post("/import/bank", status_code=status.HTTP_201_CREATED)
async def import_bank_transactions(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Import bank transactions from CSV, XLSX, or TXT file.
    
    Returns normalized transactions and derived FRIE features.
    """
    try:
        data = await _read_bounded(file)
        extension = (file.filename or "").rsplit(".", 1)[-1].lower()
        if not data:
            raise UploadValidationError("empty", "The uploaded file is empty.")
        if extension not in ("csv", "xlsx", "xls", "txt"):
            raise UploadValidationError("extension", "Bank import only supports CSV, XLSX, or TXT files.")
    except UploadValidationError as exc:
        raise HTTPException(
            status_code=_STATUS_BY_KIND.get(exc.kind, 422), detail=str(exc)
        ) from exc

    # Store the import file
    filename = storage_service.store_file(data, extension)
    
    try:
        # Import and normalize transactions
        result: ImportResult = import_bank_statement(data, file.filename or f"import.{extension}")
        
        if result.errors:
            raise HTTPException(status_code=422, detail={
                "message": "Bank statement import had errors",
                "errors": result.errors,
                "warnings": result.warnings,
            })
        
        # Create document metadata for the import
        document = document_service.create_document_metadata(
            db,
            user=user,
            document_type="bank_import",
            original_filename=storage_service.original_basename(file.filename),
            storage_reference=filename,
            source_type="bank_import",
        )
        
        # Store structured data in extraction-like format
        import_fields = {
            "imported_transactions": [
                {
                    "date": t.transaction_date.isoformat(),
                    "description": t.description,
                    "transaction_type": t.transaction_type,
                    "debit_amount": t.debit_amount,
                    "credit_amount": t.credit_amount,
                    "balance": t.balance,
                    "source_row": t.source_row,
                }
                for t in result.transactions
            ],
            "import_summary": {
                "detected_format": result.detected_format,
                "row_count": result.row_count,
                "date_range": [d.isoformat() for d in result.date_range] if result.date_range else None,
                "total_credits": result.total_credits,
                "total_debits": result.total_debits,
            },
            "warnings": result.warnings,
        }
        
        extraction = extraction_service.run_extraction(db, document=document)
        # Update with import data
        extraction.structured_data = __import__("json").dumps(import_fields)
        extraction.extraction_status = "EXTRACTED"
        extraction.review_status = "REVIEW_REQUIRED"
        extraction.engine = "bank_import"
        extraction.error_message = None
        document.processing_status = "EXTRACTED"
        document.extraction_status = "EXTRACTED"
        document.review_status = "REVIEW_REQUIRED"
        db.flush()
        
        # Derive monthly features
        from app.services.bank_import import derive_monthly_features
        monthly_features = derive_monthly_features(result.transactions)
        
        return {
            "document_id": document.id,
            "transactions_imported": len(result.transactions),
            "months_covered": len({(transaction.date.year, transaction.date.month) for transaction in result.transactions}),
            "detected_format": result.detected_format,
            "date_range": [d.isoformat() for d in result.date_range] if result.date_range else None,
            "total_credits": result.total_credits,
            "total_debits": result.total_debits,
            "warnings": result.warnings,
            "monthly_features": monthly_features,
            "extraction_id": extraction.id,
        }
    except HTTPException:
        storage_service.delete_file(filename)
        raise
    except Exception as e:
        storage_service.delete_file(filename)
        raise HTTPException(status_code=500, detail=f"Import failed: {e}")


async def _read_bounded(file: UploadFile) -> bytes:
    """Read at most limit+1MB so oversized uploads are rejected, never truncated."""

    limit = storage_service.max_upload_bytes()
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise UploadValidationError("too_large", "The uploaded file exceeds the size limit.")
        chunks.append(chunk)
    return b"".join(chunks)


@router.get("/{document_id}/file")
def download_own_file(
    document_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    document = document_service.get_document(db, user=user, document_id=document_id)
    if document is None or not document.storage_reference:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    try:
        data, content_type = storage_service.load_file(document.storage_reference)
    except (OSError, UploadValidationError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    extension = document.storage_reference.rsplit(".", 1)[-1].lower()
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="document-{document.id}.{extension}"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/{document_id}/extract", response_model=ExtractionRead)
def extract_own_document(
    document_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ExtractionRead:
    document = document_service.get_document(db, user=user, document_id=document_id)
    if document is None or not document.storage_reference:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    extraction = extraction_service.run_extraction(db, document=document)
    return ExtractionRead.model_validate(extraction_service.to_read_model(extraction))


@router.get("/{document_id}/extraction", response_model=ExtractionRead)
def read_own_extraction(
    document_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ExtractionRead:
    document = document_service.get_document(db, user=user, document_id=document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    extraction = extraction_service.get_extraction(db, user=user, document=document)
    if extraction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extraction not found.")
    return ExtractionRead.model_validate(extraction_service.to_read_model(extraction))


@router.post("/{document_id}/review", response_model=ExtractionRead)
def review_own_extraction(
    document_id: int, payload: ReviewRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ExtractionRead:
    try:
        extraction = document_service.review_document(db, user=user, document_id=document_id, decision=payload.decision)
    except document_service.ReviewNotAllowedError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if extraction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return ExtractionRead.model_validate(extraction_service.to_read_model(extraction))


_EDITABLE_FIELDS = {
    "salary_income_proof": {"employee_name", "employer_name", "basic_salary", "gross_salary", "net_salary", "salary_period"},
    "credit_report": {"lender", "account_type", "account_status", "sanctioned_amount", "outstanding_amount", "overdue_amount", "overdue_days", "credit_limit"},
    "loan_document": {"lender", "loan_amount", "emi", "tenure_months", "outstanding_balance", "contract_info"},
    "insurance_document": {"provider", "policy_type", "premium", "premium_frequency", "policy_number"},
    "investment_statement": {"fd", "rd", "sip", "mutual_fund", "ppf", "nps"},
}


@router.patch("/{document_id}/extraction", response_model=ExtractionRead)
def edit_extracted_fields(
    document_id: int, changes: dict = Body(...),
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> ExtractionRead:
    """Correct supported extracted fields; edited sources require re-review."""
    document = document_service.get_document(db, user=user, document_id=document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    extraction = db.query(Extraction).filter(Extraction.document_id == document.id).first()
    if extraction is None:
        raise HTTPException(status_code=404, detail="Extraction not found.")
    fields = json.loads(extraction.structured_data or "{}")
    allowed = _EDITABLE_FIELDS.get(document.document_type, set())
    if not changes or any(key not in allowed or key not in fields for key in changes):
        raise HTTPException(status_code=422, detail="Only existing supported extracted fields can be edited.")
    originals = fields.setdefault("__original_values__", {})
    provenance = fields.setdefault("__field_provenance__", {})
    for key, value in changes.items():
        previous = fields[key]
        if value is None or isinstance(value, (dict, list, bool)):
            raise HTTPException(status_code=422, detail=f"{key} must be a scalar value.")
        if isinstance(previous, (int, float)) and (not isinstance(value, (int, float)) or not isfinite(float(value)) or value < 0):
            raise HTTPException(status_code=422, detail=f"{key} must be a non-negative finite number.")
        if isinstance(previous, str) and not isinstance(value, str):
            raise HTTPException(status_code=422, detail=f"{key} must be text.")
        originals.setdefault(key, previous)
        fields[key] = value
        provenance[key] = "USER_EDITED"
    extraction.structured_data = json.dumps(fields, ensure_ascii=False)
    extraction.review_status = document.review_status = "REVIEW_REQUIRED"
    db.query(FinancialFeature).filter(FinancialFeature.user_id == user.id).delete()
    db.flush()
    return ExtractionRead.model_validate(extraction_service.to_read_model(extraction))


@router.patch("/{document_id}/transactions")
def edit_bank_transactions(
    document_id: int, body: dict = Body(...),
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> dict:
    document = document_service.get_document(db, user=user, document_id=document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if document.document_type != "bank_import":
        raise HTTPException(status_code=422, detail="Transaction editing is supported for structured bank imports only.")
    extraction = db.query(Extraction).filter(Extraction.document_id == document.id).first()
    if extraction is None:
        raise HTTPException(status_code=404, detail="Imported transactions not found.")
    fields = json.loads(extraction.structured_data or "{}")
    rows = fields.get("imported_transactions")
    if not isinstance(rows, list):
        raise HTTPException(status_code=422, detail="The bank import has no editable transaction rows.")
    operation = body.get("operation")
    if operation == "delete":
        index = body.get("index")
        if not isinstance(index, int) or not 0 <= index < len(rows):
            raise HTTPException(status_code=422, detail="A valid transaction index is required.")
        rows.pop(index)
    elif operation in ("edit", "add"):
        txn = body.get("transaction")
        if not isinstance(txn, dict) or set(txn) - {"date", "description", "transaction_type", "debit_amount", "credit_amount", "balance", "category"}:
            raise HTTPException(status_code=422, detail="Provide supported transaction fields only.")
        if "date" in txn:
            try:
                date.fromisoformat(str(txn["date"]))
            except ValueError as exc:
                raise HTTPException(status_code=422, detail="Transaction date must use YYYY-MM-DD.") from exc
        if "description" in txn and not isinstance(txn["description"], str):
            raise HTTPException(status_code=422, detail="Transaction description must be text.")
        if "transaction_type" in txn and txn["transaction_type"] not in ("debit", "credit"):
            raise HTTPException(status_code=422, detail="Transaction type must be debit or credit.")
        if "category" in txn and txn["category"] not in ("", "food", "rent", "education", "healthcare", "transport", "utilities", "discretionary", "emi_debt", "investment", "insurance", "salary_income", "transfer", "upi", "other", "other_expense", "other_income"):
            raise HTTPException(status_code=422, detail="Unsupported transaction category.")
        for name in ("debit_amount", "credit_amount", "balance"):
            value = txn.get(name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(float(value))):
                raise HTTPException(status_code=422, detail=f"{name} must be a finite number.")
            if value is not None and name != "balance" and value < 0:
                raise HTTPException(status_code=422, detail=f"{name} cannot be negative.")
        if operation == "add":
            if not {"date", "description", "transaction_type"}.issubset(txn):
                raise HTTPException(status_code=422, detail="New rows require date, description, and transaction type.")
            rows.append(txn)
        else:
            index = body.get("index")
            if not isinstance(index, int) or not 0 <= index < len(rows):
                raise HTTPException(status_code=422, detail="A valid transaction index is required.")
            rows[index].update(txn)
        fields.setdefault("__field_provenance__", {})["imported_transactions"] = "USER_EDITED"
    else:
        raise HTTPException(status_code=422, detail="Operation must be edit, add, or delete.")
    fields["imported_transactions"] = rows
    extraction.structured_data = json.dumps(fields, ensure_ascii=False)
    extraction.review_status = document.review_status = "REVIEW_REQUIRED"
    db.query(FinancialFeature).filter(FinancialFeature.user_id == user.id).delete()
    db.flush()
    return {"document_id": document.id, "transactions": len(rows), "review_status": "REVIEW_REQUIRED"}


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_own_document(
    document_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    document = document_service.get_document(db, user=user, document_id=document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    storage_reference = document.storage_reference
    db.query(Extraction).filter(Extraction.document_id == document.id).delete(synchronize_session=False)
    db.query(FinancialFeature).filter(
        FinancialFeature.user_id == user.id,
        FinancialFeature.source_document_id == document.id,
    ).delete(synchronize_session=False)
    db.delete(document)
    db.flush()
    from app.services import feature_engineering
    feature_engineering.build_features(db, user)
    if storage_reference:
        storage_service.delete_file(storage_reference)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
