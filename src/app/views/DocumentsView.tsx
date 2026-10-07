import { useEffect, useState } from "react";
import { AlertCircle, CheckCircle, ChevronRight, Download, FileSpreadsheet, Loader2, Trash2, Upload, Pencil } from "lucide-react";
import {
  FrieApiError, downloadDocument, deleteDocument, editBankTransaction, editExtraction, fetchExtraction, fetchFinancialStatus, isAcceptedUploadFile, isBankImportFile, listDocuments,
  reviewExtraction, triggerExtraction, uploadDocument, importBankTransactions,
  DOCUMENT_LABELS, DOCUMENT_TYPES,
  type DocumentRecord, type DocumentType, type ExtractionResult, type FinancialStatus, type BankImportSummary,
} from "../../services/api";
import { BankImportCard } from "../components/shared";
import { friendlyFeatureLabel } from "../readinessPresentation";

function ReviewedValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span>Not provided</span>;
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return <span>{String(value)}</span>;
  if (Array.isArray(value)) return <div className="space-y-2">{value.length === 0 ? "None recorded" : value.map((item, index) => <div key={index} className="rounded border border-slate-100 p-2"><ReviewedValue value={item} /></div>)}</div>;
  return <dl className="space-y-1">{Object.entries(value as Record<string, unknown>).filter(([key]) => !key.startsWith("__") && key !== "detected_format").map(([key, item]) => <div key={key}><dt className="text-slate-400">{friendlyFeatureLabel(key)}</dt><dd><ReviewedValue value={item} /></dd></div>)}</dl>;
}

export function formatUploadSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${bytes} B`;
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);
}

export function visibleDocumentTypes(status: FinancialStatus | null): DocumentType[] {
  if (!status) return [...DOCUMENT_TYPES];
  const visible: DocumentType[] = ["bank_statement", "bank_import", "salary_income_proof", "credit_report"];
  if (status.has_loan !== "no") {
    visible.push("loan_document");
  }
  if (status.insurance_status !== "none") {
    visible.push("insurance_document");
  }
  const investments = [status.inv_fd, status.inv_rd, status.inv_sip, status.inv_mutual_fund, status.inv_ppf, status.inv_nps];
  if (!investments.every(value => value === "no")) {
    visible.push("investment_statement");
  }
  return visible;
}

function ExtractionPreview({ documentId, result, reviewing, onReview, onEdit }: {
  documentId: number;
  result: ExtractionResult;
  reviewing: boolean;
  onReview: (decision: "accept" | "flag") => void;
  onEdit: (changes: Record<string, string | number>) => void;
}) {
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [transactionError, setTransactionError] = useState("");
  useEffect(() => {
    const initial: Record<string, string> = {};
    for (const [key, value] of Object.entries(result.structured_data ?? {})) {
      if (typeof value === "string" || typeof value === "number") initial[key] = String(value);
    }
    setDraft(initial);
  }, [result]);
  const entries = Object.entries(result.structured_data ?? {}).filter(([key]) => !key.startsWith("__"));
  const editableKeys = new Set(["employee_name", "employer_name", "basic_salary", "gross_salary", "net_salary", "salary_period", "lender", "account_type", "account_status", "sanctioned_amount", "outstanding_amount", "overdue_amount", "overdue_days", "credit_limit", "loan_amount", "emi", "tenure_months", "outstanding_balance", "contract_info", "provider", "policy_type", "premium", "premium_frequency", "policy_number", "fd", "rd", "sip", "mutual_fund", "ppf", "nps"]);
  async function saveEdits() {
    const changes: Record<string, string | number> = {};
    for (const key of editableKeys) {
      const original = result.structured_data[key];
      if ((typeof original === "string" || typeof original === "number") && draft[key] !== String(original)) {
        if (typeof original === "number") {
          const parsed = Number(draft[key]);
          if (!Number.isFinite(parsed) || parsed < 0) { setTransactionError(`${friendlyFeatureLabel(key)} must be a non-negative number.`); return; }
          changes[key] = parsed;
        } else changes[key] = draft[key];
      }
    }
    if (!Object.keys(changes).length) return;
    setSaving(true); setTransactionError("");
    try { await editExtraction(documentId, changes); onEdit(changes); }
    catch (err) { setTransactionError(err instanceof FrieApiError ? err.message : "Unable to save edits."); }
    finally { setSaving(false); }
  }
  const transactions = Array.isArray(result.structured_data.imported_transactions) ? result.structured_data.imported_transactions as Record<string, unknown>[] : null;
  async function saveTransaction(index: number, transaction: Record<string, unknown>, operation: "edit" | "add" = "edit") {
    setSaving(true); setTransactionError("");
    try { await editBankTransaction(documentId, operation, index, transaction); onEdit({}); }
    catch (err) { setTransactionError(err instanceof FrieApiError ? err.message : "Unable to update transaction."); }
    finally { setSaving(false); }
  }
  async function deleteTransaction(index: number) {
    if (!window.confirm("Remove this transaction from the imported statement?")) return;
    setSaving(true); setTransactionError("");
    try { await editBankTransaction(documentId, "delete", index); onEdit({}); }
    catch (err) { setTransactionError(err instanceof FrieApiError ? err.message : "Unable to remove transaction."); }
    finally { setSaving(false); }
  }
  return (
    <div className="mt-3 bg-[#F8FAFC] border border-[#F1F5F9] rounded-lg p-3">
      <p className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Review extracted information</p>
      <p className="text-[11px] text-slate-400 mt-0.5">Check the extracted details and correct anything that needs an update.</p>
      <p className="text-[11px] text-slate-400 mt-1">
        Review status: {result.review_status === "REVIEW_REQUIRED" ? "Required" : result.review_status}
      </p>
      {result.extraction_status === "FAILED" && (
        <p className="text-[12px] text-red-600 mt-1.5">{result.error_message || "Extraction failed."}</p>
      )}
      {entries.length > 0 && (
        <div className="mt-2 space-y-1">
          {entries.map(([key, value]) => (
            <div key={key} className="flex items-start justify-between gap-2">
              <p className="text-[11px] text-slate-400">{friendlyFeatureLabel(key)}</p>
              {editableKeys.has(key) && (typeof value === "string" || typeof value === "number")
                ? <input aria-label={`Edit ${friendlyFeatureLabel(key)}`} type={typeof value === "number" ? "number" : "text"} value={draft[key] ?? ""} onChange={e => setDraft(current => ({ ...current, [key]: e.target.value }))} className="w-36 text-[11px] text-right bg-white border rounded px-2 py-1" />
                : key === "imported_transactions" || key === "transactions" ? <p className="text-[11px] text-slate-600">{Array.isArray(value) ? `${value.length} transactions extracted` : "Not provided"}</p> : <div className="text-[11px] font-semibold text-[#0F172A] text-right break-words max-w-[60%]"><ReviewedValue value={value} /></div>}
            </div>
          ))}
        </div>
      )}
      {entries.some(([key, value]) => editableKeys.has(key) && (typeof value === "string" || typeof value === "number")) && <button type="button" disabled={saving} onClick={() => void saveEdits()} className="mt-2 text-[11px] font-semibold text-blue-700 disabled:opacity-50">{saving ? "Saving…" : "Save field corrections"}</button>}
      {transactions && <div className="mt-3 overflow-x-auto"><p className="text-[11px] font-bold text-slate-600 mb-2">Imported transactions · {transactions.length}</p><table className="w-full text-[10px]"><thead><tr>{["Date", "Description", "Debit", "Credit", "Balance", "Category", ""].map(label => <th key={label} className="text-left p-1">{label}</th>)}</tr></thead><tbody>{transactions.map((txn, index) => <tr key={`${String(txn.source_row ?? index)}-${index}`} className="border-t"><td className="p-1">{String(txn.date ?? "—")}</td><td className="p-1">{String(txn.description ?? "—")}</td><td className="p-1">{String(txn.debit_amount ?? "—")}</td><td className="p-1">{String(txn.credit_amount ?? "—")}</td><td className="p-1">{String(txn.balance ?? "—")}</td><td className="p-1">{String(txn.category ?? "Auto")}</td><td className="p-1"><button type="button" disabled={saving} onClick={() => { const dateValue = window.prompt("Date (YYYY-MM-DD)", String(txn.date ?? "")); if (dateValue === null) return; const description = window.prompt("Description", String(txn.description ?? "")); if (description === null) return; const debit = window.prompt("Debit amount (leave empty if none)", String(txn.debit_amount ?? "")); if (debit === null) return; const credit = window.prompt("Credit amount (leave empty if none)", String(txn.credit_amount ?? "")); if (credit === null) return; const balance = window.prompt("Balance (leave empty if unavailable)", String(txn.balance ?? "")); if (balance === null) return; const category = window.prompt("Category (food, rent, education, healthcare, transport, utilities, discretionary, emi_debt, investment, insurance, salary_income, transfer, upi, other_expense, other_income)", String(txn.category ?? "")); if (category === null) return; const numberOrNull = (value: string) => value.trim() ? Number(value) : null; const debitValue = numberOrNull(debit); const creditValue = numberOrNull(credit); const balanceValue = numberOrNull(balance); if ([debitValue, creditValue, balanceValue].some(value => value !== null && !Number.isFinite(value))) { setTransactionError("Transaction amounts must be numbers."); return; } void saveTransaction(index, { date: dateValue, description, debit_amount: debitValue, credit_amount: creditValue, balance: balanceValue, category }); }} aria-label={`Edit transaction ${index + 1}`}><Pencil size={11}/></button> <button type="button" disabled={saving} onClick={() => void deleteTransaction(index)} aria-label={`Delete transaction ${index + 1}`}><Trash2 size={11}/></button></td></tr>)}</tbody></table><button type="button" disabled={saving} className="mt-2 text-[11px] font-semibold text-blue-700" onClick={() => { const dateValue = window.prompt("Date (YYYY-MM-DD)"); if (!dateValue) return; const description = window.prompt("Description"); if (!description) return; const type = window.prompt("Type: debit or credit"); if (type !== "debit" && type !== "credit") return; const amount = window.prompt("Amount"); if (amount === null || !Number.isFinite(Number(amount)) || Number(amount) < 0) return; const category = window.prompt("Category (optional; blank uses automatic classification)") ?? ""; void saveTransaction(transactions.length, { date: dateValue, description, transaction_type: type, debit_amount: type === "debit" ? Number(amount) : 0, credit_amount: type === "credit" ? Number(amount) : 0, ...(category.trim() ? { category: category.trim() } : {}) }, "add"); }}>Add transaction</button></div>}
      {transactionError && <p role="alert" className="text-[11px] text-red-700 mt-2">{transactionError}</p>}
      {entries.length === 0 && result.extraction_status === "EXTRACTED" && (
        <p className="text-[12px] text-slate-500 mt-1.5">No structured fields were found in this document.</p>
      )}
      {!!result.raw_text && (
        <div className="mt-2 max-h-24 overflow-y-auto bg-white border border-[#F1F5F9] rounded p-2">
          <p className="text-[11px] text-slate-500 whitespace-pre-wrap">{result.raw_text.slice(0, 600)}</p>
        </div>
      )}
      {result.review_status !== "REVIEWED" && (
        <div className="flex items-center gap-2 mt-2.5">
          <button
            onClick={() => onReview("accept")}
            disabled={reviewing || result.extraction_status !== "EXTRACTED"}
            className="text-[12px] font-semibold text-emerald-600 hover:text-emerald-700 disabled:opacity-50 transition-colors"
          >
            {reviewing ? "Saving..." : "Accept"}
          </button>
          <button
            onClick={() => onReview("flag")}
            disabled={reviewing}
            className="text-[12px] font-semibold text-amber-600 hover:text-amber-700 disabled:opacity-50 transition-colors"
          >
            Flag for review
          </button>
        </div>
      )}
      {result.review_status === "REVIEWED" && (
        <p className="text-[11px] font-semibold text-emerald-600 mt-2">Reviewed and accepted.</p>
      )}
    </div>
  );
}

export default function DocumentsView({ onContinue }: { onContinue?: () => void }) {
  const [documents, setDocuments] = useState<DocumentRecord[] | null>(null);
  const [extractions, setExtractions] = useState<Record<number, ExtractionResult | null>>({});
  const [extracting, setExtracting] = useState<Record<number, boolean>>({});
  const [reviewing, setReviewing] = useState<Record<number, boolean>>({});
  const [deleting, setDeleting] = useState<Record<number, boolean>>({});
  const [status, setStatus] = useState<FinancialStatus | null>(null);
  const [docType, setDocType]     = useState<DocumentType>("bank_statement");
  const [file, setFile]           = useState<File | null>(null);
  const [progress, setProgress]   = useState<number | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError]         = useState("");
  const [notice, setNotice]       = useState("");

  // Bank import state
  const [bankImportProgress, setBankImportProgress] = useState<number | null>(null);
  const [bankImportUploading, setBankImportUploading] = useState(false);
  const [bankImportError, setBankImportError] = useState("");
  const [bankImportResult, setBankImportResult] = useState<BankImportSummary | null>(null);

  function refresh() {
    listDocuments()
      .then(list => {
        setDocuments(list);
        return Promise.all(list.map(item =>
          fetchExtraction(item.id)
            .then(result => ({ id: item.id, result }))
            .catch(() => ({ id: item.id, result: null as ExtractionResult | null })),
        ));
      })
      .then(entries => {
        const next: Record<number, ExtractionResult | null> = {};
        for (const { id, result } of entries) next[id] = result;
        setExtractions(next);
      })
      .catch(err => {
        setDocuments([]);
        setNotice("");
        setError(err instanceof FrieApiError && err.message ? err.message : "Unable to load the documents.");
      });
  }

  useEffect(() => {
    let live = true;
    fetchFinancialStatus()
      .then(current => { if (live) { setStatus(current); if (current) setDocType(visibleDocumentTypes(current)[0] ?? "bank_statement"); } })
      .catch(() => { if (live) setStatus(null); });
    listDocuments()
      .then(async list => {
        if (!live) return;
        setDocuments(list);
        const entries = await Promise.all(list.map(async item => {
          try {
            return { id: item.id, result: await fetchExtraction(item.id) };
          } catch {
            return { id: item.id, result: null as ExtractionResult | null };
          }
        }));
        if (!live) return;
        const next: Record<number, ExtractionResult | null> = {};
        for (const { id, result } of entries) next[id] = result;
        setExtractions(next);
      })
      .catch(err => {
        if (!live) return;
        setDocuments([]);
        setError(err instanceof FrieApiError && err.message ? err.message : "Unable to load the documents.");
      });
    return () => { live = false; };
  }, []);

  function pickFile(next: File | null) {
    setNotice("");
    setError("");
    setBankImportError("");
    setProgress(null);
    if (next && docType === "bank_import") {
      if (!isBankImportFile(next.name)) {
        setFile(null);
        setBankImportError("Unsupported file type. Use CSV, XLSX, XLS, TXT, PDF, PNG, or JPEG.");
        return;
      }
    } else if (next && !isAcceptedUploadFile(next.name)) {
      setFile(null);
      setError("Unsupported file type. Use PDF, PNG, or JPEG.");
      return;
    }
    setFile(next);
  }

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (uploading || !file) return;
    setError("");
    setNotice("");
    setUploading(true);
    setProgress(0);
    try {
      const created = await uploadDocument(docType, file, setProgress);
      setFile(null);
      setProgress(null);
      setNotice(`${DOCUMENT_LABELS[created.document_type as DocumentType] ?? "Document"} stored. Use Extract Information to run text extraction.`);
      refresh();
    } catch (err) {
      setProgress(null);
      setError(err instanceof FrieApiError && err.message ? err.message : "Unable to store the document.");
    } finally {
      setUploading(false);
    }
  }

  async function handleBankImport(e: React.FormEvent) {
    e.preventDefault();
    if (bankImportUploading || !file) return;
    setBankImportError("");
    setBankImportUploading(true);
    setBankImportProgress(0);
    try {
      const summary = await importBankTransactions(file, setBankImportProgress);
      setBankImportResult(summary);
      setFile(null);
      setBankImportProgress(null);
      setNotice("Bank statement imported and analysed.");
      refresh();
    } catch (err) {
      setBankImportProgress(null);
      setBankImportError(err instanceof FrieApiError && err.message ? err.message : "Bank import failed.");
    } finally {
      setBankImportUploading(false);
    }
  }

  async function handleDownload(document: DocumentRecord) {
    setError("");
    try {
      const blob = await downloadDocument(document.id);
      const url = URL.createObjectURL(blob);
      const anchor = window.document.createElement("a");
      anchor.href = url;
      anchor.download = document.original_filename;
      window.document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    } catch (err) {
      setError(err instanceof FrieApiError && err.message ? err.message : "Unable to download the document.");
    }
  }

  async function handleExtract(document: DocumentRecord) {
    if (extracting[document.id]) return;
    setError("");
    setNotice("");
    setExtracting(state => ({ ...state, [document.id]: true }));
    try {
      const result = await triggerExtraction(document.id);
      setExtractions(state => ({ ...state, [document.id]: result }));
      refresh();
    } catch (err) {
      setError(err instanceof FrieApiError && err.message ? err.message : "Unable to extract the document.");
    } finally {
      setExtracting(state => ({ ...state, [document.id]: false }));
    }
  }

  async function handleReview(document: DocumentRecord, decision: "accept" | "flag") {
    if (reviewing[document.id]) return;
    setError("");
    setReviewing(state => ({ ...state, [document.id]: true }));
    try {
      const result = await reviewExtraction(document.id, decision);
      setExtractions(state => ({ ...state, [document.id]: result }));
      refresh();
    } catch (err) {
      setError(err instanceof FrieApiError && err.message ? err.message : "Unable to save the review decision.");
    } finally {
      setReviewing(state => ({ ...state, [document.id]: false }));
    }
  }

  async function handleDelete(document: DocumentRecord) {
    if (!window.confirm(`Delete ${document.original_filename}? Its extracted data will be removed and the score may become stale.`)) return;
    setDeleting(state => ({ ...state, [document.id]: true })); setError(""); setNotice("");
    try {
      await deleteDocument(document.id);
      setNotice(`${document.original_filename} was deleted. Readiness has been refreshed.`);
      refresh();
    } catch (err) {
      setError(err instanceof FrieApiError ? err.message : "Unable to delete the document.");
    } finally { setDeleting(state => ({ ...state, [document.id]: false })); }
  }

  async function handleEdit(document: DocumentRecord) {
    setNotice("Corrections saved. Review the edited source again; the previous assessment is stale.");
    refresh();
  }

  const byType = new Map<string, DocumentRecord>();
  for (const document of documents ?? []) {
    if (!byType.has(document.document_type)) byType.set(document.document_type, document);
  }
  const visibleTypes = visibleDocumentTypes(status);

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-[#0F172A] text-white">
          Real upload + storage
        </span>
        <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-white border border-[#F1F5F9] text-slate-500">
          Text extraction + OCR available
        </span>
      </div>

      <div>
        <form onSubmit={handleUpload} className="bg-white rounded-xl border border-[#F1F5F9] p-6">
          <h3 className="text-[14px] font-bold text-[#0F172A]">Upload Financial Document</h3>
          <p className="text-[12px] text-slate-500 mt-1 mb-4">
            Stored securely, then run Extract Information on each document. PDF, PNG, or JPEG up to 10 MB.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-[12px] font-semibold text-slate-600">
                Document Type <span className="text-red-500">*</span>
              </label>
              <select
                value={docType}
                onChange={e => setDocType(e.target.value as DocumentType)}
                className="bg-[#F8FAFC] border border-[#F1F5F9] rounded-[8px] px-3 py-2.5 text-[13px] text-[#334155] outline-none focus-within:border-blue-300"
              >
                {visibleTypes.map(type => (
                  <option key={type} value={type}>{DOCUMENT_LABELS[type]}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-[12px] font-semibold text-slate-600">
                File <span className="text-red-500">*</span>
              </label>
              <label className="bg-[#F8FAFC] border border-[#F1F5F9] hover:border-blue-200 rounded-[8px] px-3 py-2.5 text-[13px] text-[#334155] cursor-pointer transition-colors truncate">
                <input
                  type="file"
                  accept={docType === "bank_import" ? ".csv,.xlsx,.xls,.txt,.pdf,.png,.jpg,.jpeg" : ".pdf,.png,.jpg,.jpeg"}
                  className="hidden"
                  onChange={e => pickFile(e.target.files?.[0] ?? null)}
                />
                {file ? `${file.name} (${formatUploadSize(file.size)})` : docType === "bank_import" ? "Choose CSV, XLSX, XLS, TXT, PDF, PNG, or JPEG" : "Choose PDF, PNG, or JPEG"}
              </label>
            </div>
          </div>

          {uploading && progress !== null && (
            <div className="mt-4">
              <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                <div className="h-full bg-[#3B82F6] rounded-full transition-all" style={{ width: `${progress}%` }} />
              </div>
              <p className="text-[12px] text-slate-500 mt-1.5">Uploading... {progress}%</p>
            </div>
          )}
          {uploading && progress === null && (
            <div className="flex items-center gap-3 mt-4">
              <div className="w-5 h-5 border-2 border-[#0F172A] border-t-transparent rounded-full animate-spin" />
              <p className="text-[13px] font-semibold text-slate-600">Uploading...</p>
            </div>
          )}

          {error && (
            <div className="flex items-start gap-2.5 bg-red-50 border border-red-100 rounded-lg px-3 py-2.5 mt-4">
              <AlertCircle size={14} className="text-red-500 shrink-0 mt-0.5" />
              <p className="text-red-600 text-[13px]">{error}</p>
            </div>
          )}
          {notice && (
            <div className="flex items-start gap-2.5 bg-emerald-50 border border-emerald-100 rounded-lg px-3 py-2.5 mt-4">
              <CheckCircle size={14} className="text-emerald-500 shrink-0 mt-0.5" />
              <p className="text-emerald-700 text-[13px]">{notice}</p>
            </div>
          )}

          <div className="flex justify-end mt-5">
            <button
              type="submit"
              disabled={uploading || !file}
              className="bg-[#0F172A] hover:bg-slate-800 disabled:opacity-60 text-white font-semibold text-[13px] px-6 py-2.5 rounded-lg transition-colors"
            >
              {uploading ? "Uploading..." : "Upload Document"}
            </button>
          </div>
        </form>

        {/* Bank Import Section */}
        {docType === "bank_import" && (
          <form onSubmit={handleBankImport} className="bg-white rounded-xl border border-[#F1F5F9] p-6 mt-6">
            <h3 className="text-[14px] font-bold text-[#0F172A]">Bank Transactions Import (CSV / Excel / TXT)</h3>
            <p className="text-[12px] text-slate-500 mt-1 mb-4">
              CSV / Excel recommended for transaction-heavy statements.
              <br />Supported: CSV, XLSX, XLS, TXT, PDF, PNG, JPEG up to 10 MB.
            </p>
            <div className="flex flex-col gap-1.5">
              <label className="text-[12px] font-semibold text-slate-600">
                File <span className="text-red-500">*</span>
              </label>
              <label className="bg-[#F8FAFC] border border-[#F1F5F9] hover:border-blue-200 rounded-[8px] px-3 py-2.5 text-[13px] text-[#334155] cursor-pointer transition-colors truncate">
                <input
                  type="file"
                  accept=".csv,.xlsx,.xls,.txt,.pdf,.png,.jpg,.jpeg"
                  className="hidden"
                  onChange={e => pickFile(e.target.files?.[0] ?? null)}
                  disabled={bankImportUploading}
                />
                {file ? `${file.name} (${formatUploadSize(file.size)})` : "Choose CSV, XLSX, XLS, TXT, PDF, PNG, or JPEG"}
              </label>
            </div>

            {bankImportUploading && bankImportProgress !== null && (
              <div className="mt-4">
                <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full bg-[#3B82F6] rounded-full transition-all" style={{ width: `${bankImportProgress}%` }} />
                </div>
                <p className="text-[12px] text-slate-500 mt-1.5">Uploading... {bankImportProgress}%</p>
              </div>
            )}
            {bankImportUploading && bankImportProgress === null && (
              <div className="flex items-center gap-3 mt-4">
                <div className="w-5 h-5 border-2 border-[#0F172A] border-t-transparent rounded-full animate-spin" />
                <p className="text-[13px] font-semibold text-slate-600">Uploading...</p>
              </div>
            )}

            {bankImportError && (
              <div className="flex items-start gap-2.5 bg-red-50 border border-red-100 rounded-lg px-3 py-2.5 mt-4">
                <AlertCircle size={14} className="text-red-500 shrink-0 mt-0.5" />
                <p className="text-red-600 text-[13px]">{bankImportError}</p>
              </div>
            )}
            {notice && (
              <div className="flex items-start gap-2.5 bg-emerald-50 border border-emerald-100 rounded-lg px-3 py-2.5 mt-4">
                <CheckCircle size={14} className="text-emerald-500 shrink-0 mt-0.5" />
                <p className="text-emerald-700 text-[13px]">{notice}</p>
              </div>
            )}

            <div className="flex justify-end mt-5">
              <button
                type="submit"
                disabled={bankImportUploading || !file}
                className="bg-[#0F172A] hover:bg-slate-800 disabled:opacity-60 text-white font-semibold text-[13px] px-6 py-2.5 rounded-lg transition-colors"
              >
                {bankImportUploading ? "Uploading..." : "Upload Bank Statement"}
              </button>
            </div>
          </form>
        )}

        {bankImportResult && (
          <div className="bg-emerald-50 border border-emerald-100 rounded-xl p-4 mt-6 space-y-3">
            <div className="flex items-center gap-2">
              <CheckCircle size={16} className="text-emerald-500 shrink-0" />
              <p className="text-[13px] font-semibold text-emerald-700">Bank statement imported successfully</p>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-[12px]">
              <div><p className="text-slate-400">Transactions</p><p className="font-semibold text-[#0F172A]">{bankImportResult.transactions_imported}</p></div>
              <div><p className="text-slate-400">Date Range</p><p className="font-semibold text-[#0F172A]">{bankImportResult.date_range ? `${bankImportResult.date_range[0]} – ${bankImportResult.date_range[1]}` : "—"}</p></div>
              <div><p className="text-slate-400">Months covered</p><p className="font-semibold text-[#0F172A]">{bankImportResult.months_covered ?? "—"}</p></div>
              <div><p className="text-slate-400">Credits / Debits</p><p className="font-semibold text-[#0F172A]">{formatCurrency(bankImportResult.total_credits)} / {formatCurrency(bankImportResult.total_debits)}</p></div>
            </div>
            {bankImportResult.warnings && bankImportResult.warnings.length > 0 && (
              <div className="bg-amber-50 border border-amber-100 rounded-lg p-3">
                <p className="text-[11px] font-semibold text-amber-700 mb-1">Import Warnings</p>
                <ul className="text-[11px] text-amber-600 space-y-0.5 list-disc list-inside">
                  {bankImportResult.warnings.map((w, i) => <li key={i}>{w}</li>)}
                </ul>
              </div>
            )}
            <div className="flex items-center gap-2 pt-2">
              <button
                type="button"
                onClick={() => setBankImportResult(null)}
                className="text-[12px] font-semibold text-red-600 hover:text-red-700 flex items-center gap-1"
              >
                <Trash2 size={14} /> Clear result
              </button>
            </div>
          </div>
        )}

      <div className="bg-white rounded-xl border border-[#F1F5F9] p-6">
        <h3 className="text-[14px] font-bold text-[#0F172A] mb-1">My Financial Documents</h3>
        <p className="text-[12px] text-slate-500 mb-4">Recommended documents based on your declared financial products. Only your records are listed.</p>
        {documents === null ? (
          <div className="flex items-center gap-3 py-4">
            <div className="w-5 h-5 border-2 border-[#0F172A] border-t-transparent rounded-full animate-spin" />
            <p className="text-[13px] font-semibold text-slate-600">Loading documents...</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {visibleTypes.map(type => {
              const document = byType.get(type);
              return (
                <div key={type} data-testid={`document-${type}`} className="border border-[#F1F5F9] rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-1.5">
                    {document
                      ? <CheckCircle size={14} className="text-emerald-500 shrink-0" />
                      : <div className="w-[14px] h-[14px] rounded-full border-2 border-slate-200 shrink-0" />}
                    <p className="text-[13px] font-bold text-[#0F172A]">{DOCUMENT_LABELS[type]}</p>
                  </div>
                  {document ? (
                    <div>
                      <p className="text-[12px] text-slate-600 truncate">{document.original_filename}</p>
                      <p className="text-[11px] text-slate-400 mt-0.5">
                        Uploaded {new Date(document.uploaded_at).toLocaleDateString()} • Extraction: {
                          document.extraction_status === "PENDING" ? "Pending"
                          : document.extraction_status === "EXTRACTED" ? "Extracted"
                          : document.extraction_status
                        }
                      </p>
                      <div className="flex flex-wrap items-center gap-3 mt-2">
                        <button
                          onClick={() => handleDownload(document)}
                          className="text-[12px] font-semibold text-[#3B82F6] hover:text-blue-700 flex items-center gap-1 transition-colors"
                        >
                          <Download size={12} /> Download
                        </button>
                        <button onClick={() => void handleDelete(document)} disabled={!!deleting[document.id]} className="text-[12px] font-semibold text-red-600 hover:text-red-700 disabled:opacity-50 flex items-center gap-1"><Trash2 size={12}/>{deleting[document.id] ? "Deleting…" : "Delete"}</button>
                        {document.document_type !== "bank_import" && (
                          <button
                            onClick={() => handleExtract(document)}
                            disabled={!!extracting[document.id]}
                            className="text-[12px] font-semibold text-[#3B82F6] hover:text-blue-700 disabled:opacity-60 flex items-center gap-1 transition-colors"
                          >
                            {extracting[document.id] ? "Extracting..." : "Extract Information"}
                          </button>
                        )}
                      </div>
                      {extracting[document.id] && (
                        <div className="flex items-center gap-2 mt-3">
                          <div className="w-4 h-4 border-2 border-[#3B82F6] border-t-transparent rounded-full animate-spin" />
                          <p className="text-[12px] text-slate-500">Processing extraction...</p>
                        </div>
                      )}
                      {extractions[document.id] && (
                        <ExtractionPreview
                          documentId={document.id}
                          result={extractions[document.id] as ExtractionResult}
                          reviewing={!!reviewing[document.id]}
                          onReview={decision => handleReview(document, decision)}
                          onEdit={() => void handleEdit(document)}
                        />
                      )}
                    </div>
                  ) : (
                    <p className="text-[12px] text-slate-400">Not uploaded</p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
      {onContinue && <div className="flex justify-end"><button type="button" onClick={onContinue} className="bg-[#0F172A] hover:bg-slate-800 text-white font-semibold text-[13px] px-6 py-2.5 rounded-lg">Continue to Dashboard</button></div>}
    </div>
  </div>
  );
}
