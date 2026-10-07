export type ReliabilityLevel = "Poor" | "Average" | "Good" | "Excellent";

export interface HealthResponse {
  status: string;
  model_loaded: boolean;
  model: string;
}

export type CustomerFeatureMap = Record<string, number | string>;

export interface PredictionResponse {
  frie_score: number;
  reliability_level: ReliabilityLevel;
}

export interface AssessmentRecord extends PredictionResponse {
  id: number;
  model_version: string;
  created_at: string;
  stale?: boolean;
  assessment_state?: "complete" | "estimated";
  source_readiness?: AssessmentSource[];
  indicators?: Record<string, number | null>;
  indicator_details?: Record<string, IndicatorDetail>;
  recommendations?: FrieRecommendation[];
}

export interface IndicatorDetail {
  score: number | null;
  available: boolean;
  availability?: "AVAILABLE" | "LIMITED";
  component_count?: number;
  unavailable_reason?: string | null;
  measures: string;
  based_on: string[];
  methodology_note: string;
}

export interface AssessmentSource {
  key: "profile" | "income" | "bank" | "credit" | "insurance" | "investments" | "loans";
  title: string;
  status: "complete" | "required" | "recommended" | "optional" | "unknown";
  description: string;
}

export interface AssessmentStatus {
  assessment_state: "complete" | "estimated" | "insufficient";
  can_assess: boolean;
  sources: AssessmentSource[];
  message: string;
}

export interface FrieRecommendation {
  category: string;
  title: string;
  description: string;
  priority: "High" | "Medium" | "Low";
  related_indicator: string;
  related_indicator_label: string;
  indicator_score: number | null;
  reason: string;
}

export interface LocalExplanation {
  score: number;
  reliability_level: ReliabilityLevel;
  base_value: number;
  method: string;
  model: string;
  scope: "LOCAL";
  top_features: { feature: string; value: string | number; contribution: number }[];
  top_positive: { feature: string; value: string | number; contribution: number }[];
  top_negative: { feature: string; value: string | number; contribution: number }[];
  disclaimer: string;
}

export class FrieApiError extends Error {
  readonly status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "FrieApiError";
    this.status = status;
  }
}

export interface AuthAccount {
  id: number;
  email: string;
}

export interface AuthSession {
  token: string;
  id: number;
  email: string;
}

export interface ProfileData {
  gender?: string | null;
  date_of_birth?: string | null;
  children_count?: number | null;
  family_size?: number | null;
  family_status?: string | null;
  education_level?: string | null;
  housing_type?: string | null;
  owns_car?: string | null;
  owns_property?: string | null;
  income_type?: string | null;
  occupation?: string | null;
  organization_type?: string | null;
  contract_type?: string | null;
  city?: string | null;
  monthly_income?: number | null;
  employment_start?: string | null;
}

interface TokenPayload {
  access_token: string;
  token_type: string;
  user: AuthAccount;
}

const SESSION_KEY = "frie_auth_session";

function notifyDataChanged(): void {
  if (typeof window !== "undefined") window.dispatchEvent(new Event("frie:data-changed"));
}

export function saveSession(session: AuthSession): void {
  try {
    localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  } catch {
    // Private-mode storage failures keep the session memory-only.
  }
}

export function loadSession(): AuthSession | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<AuthSession>;
    if (typeof parsed.token !== "string" || typeof parsed.email !== "string") return null;
    return { token: parsed.token, id: typeof parsed.id === "number" ? parsed.id : 0, email: parsed.email };
  } catch {
    return null;
  }
}

export function clearSession(): void {
  try {
    localStorage.removeItem(SESSION_KEY);
  } catch {
    // Nothing to clean up.
  }
}

async function authRequest(path: string, email: string, password: string): Promise<AuthSession> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
  } catch {
    throw new FrieApiError("Unable to reach the FRIE service.");
  }

  if (response.status === 409) {
    throw new FrieApiError("An account with this email already exists.", 409);
  }
  if (response.status === 401) {
    throw new FrieApiError("Invalid email or password.", 401);
  }
  if (!response.ok) {
    throw new FrieApiError("Unable to complete the request.", response.status);
  }

  const body = await readJson<TokenPayload>(response);
  if (!body.access_token || !body.user?.email) {
    throw new FrieApiError("The FRIE service returned an incomplete session.");
  }
  return { token: body.access_token, id: body.user.id, email: body.user.email };
}

export function registerUser(email: string, password: string): Promise<AuthSession> {
  return authRequest("/auth/register", email, password);
}

export function loginUser(email: string, password: string): Promise<AuthSession> {
  return authRequest("/auth/login", email, password);
}

async function authorizedFetch(path: string, init?: RequestInit): Promise<Response> {
  const session = loadSession();
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      ...init,
      headers: { ...(init?.headers ?? {}), ...(session ? { Authorization: `Bearer ${session.token}` } : {}) },
    });
  } catch {
    throw new FrieApiError("Unable to reach the FRIE service.");
  }
  return response;
}

export async function fetchAccount(): Promise<AuthAccount> {
  const response = await authorizedFetch("/auth/me");
  if (response.status === 401) {
    throw new FrieApiError("Your session has expired. Please sign in again.", 401);
  }
  if (!response.ok) {
    throw new FrieApiError("Unable to load the account.", response.status);
  }
  return readJson<AuthAccount>(response);
}

export async function fetchProfile(): Promise<ProfileEnvelope | null> {
  const response = await authorizedFetch("/profile");
  if (response.status === 401) {
    throw new FrieApiError("Your session has expired. Please sign in again.", 401);
  }
  if (!response.ok) {
    throw new FrieApiError("Unable to load the profile.", response.status);
  }
  return readJson<ProfileEnvelope>(response);
}

export async function saveProfile(profile: ProfileData): Promise<ProfileEnvelope> {
  const response = await authorizedFetch("/profile", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile),
  });
  if (response.status === 401) {
    throw new FrieApiError("Your session has expired. Please sign in again.", 401);
  }
  if (!response.ok) {
    throw new FrieApiError("Unable to save the profile. Check the highlighted fields.", response.status);
  }
  const result = await readJson<ProfileEnvelope>(response);
  notifyDataChanged();
  return result;
}

export interface CompletenessInfo {
  completed: number;
  required: number;
  percentage: number;
  missing: { feature: string; label: string }[];
}

export interface ReadinessInfo {
  profile_status: string;
  profile_ready: boolean;
  frie_scoring_ready: boolean;
}

export interface ProfileEnvelope {
  profile: ProfileData | null;
  completeness: CompletenessInfo;
  readiness: ReadinessInfo;
}

export type DocumentType =
  | "salary_income_proof"
  | "bank_statement"
  | "bank_import"
  | "credit_report"
  | "loan_document"
  | "insurance_document"
  | "investment_statement";

export const DOCUMENT_LABELS: Record<DocumentType, string> = {
  salary_income_proof: "Salary / Income Proof",
  bank_statement: "Bank Statement (PDF/Image)",
  bank_import: "Bank Import (CSV/Excel/TXT)",
  credit_report: "Credit Report",
  loan_document: "Loan Document",
  insurance_document: "Insurance Document",
  investment_statement: "Investment Statement",
};

export const DOCUMENT_TYPES = Object.keys(DOCUMENT_LABELS) as DocumentType[];

export interface DocumentRecord {
  id: number;
  user_id: number;
  document_type: string;
  original_filename: string;
  uploaded_at: string;
  processing_status: string;
  extraction_status: string;
  review_status: string;
}

const ACCEPTED_UPLOAD_EXTENSIONS = [".pdf", ".png", ".jpg", ".jpeg"];

const BANK_IMPORT_EXTENSIONS = [".csv", ".xlsx", ".xls", ".txt", ".pdf", ".png", ".jpg", ".jpeg"];

export function isAcceptedUploadFile(name: string): boolean {
  const lower = name.toLowerCase();
  return ACCEPTED_UPLOAD_EXTENSIONS.some(ext => lower.endsWith(ext));
}

export function isBankImportFile(name: string): boolean {
  const lower = name.toLowerCase();
  return BANK_IMPORT_EXTENSIONS.some(ext => lower.endsWith(ext));
}

export function uploadDocument(
  documentType: DocumentType,
  file: File,
  onProgress?: (percent: number) => void,
): Promise<DocumentRecord> {
  const form = new FormData();
  form.append("document_type", documentType);
  form.append("file", file, file.name);
  const session = loadSession();

  return new Promise<DocumentRecord>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${apiBaseUrl()}/documents/upload`);
    if (session) {
      request.setRequestHeader("Authorization", `Bearer ${session.token}`);
    }
    request.upload.onprogress = event => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };
    request.onerror = () => reject(new FrieApiError("Unable to reach the FRIE service."));
    request.onload = () => {
      if (request.status === 201) {
        try {
          const created = JSON.parse(request.responseText) as DocumentRecord;
          notifyDataChanged();
          resolve(created);
        } catch {
          reject(new FrieApiError("The FRIE service returned an unreadable response.", request.status));
        }
        return;
      }
      if (request.status === 401) {
        reject(new FrieApiError("Your session has expired. Please sign in again.", 401));
        return;
      }
      if (request.status === 413) {
        reject(new FrieApiError("The file exceeds the 10 MB upload limit.", 413));
        return;
      }
      if (request.status === 415) {
        reject(new FrieApiError("Unsupported file type. Use PDF, PNG, or JPEG.", 415));
        return;
      }
      reject(new FrieApiError("Unable to store the document.", request.status));
    };
    request.send(form);
  });
}

export async function listDocuments(): Promise<DocumentRecord[]> {
  const response = await authorizedFetch("/documents");
  if (response.status === 401) {
    throw new FrieApiError("Your session has expired. Please sign in again.", 401);
  }
  if (!response.ok) {
    throw new FrieApiError("Unable to load the documents.", response.status);
  }
  return readJson<DocumentRecord[]>(response);
}

export async function deleteDocument(id: number): Promise<void> {
  const response = await authorizedFetch(`/documents/${id}`, { method: "DELETE" });
  if (response.status === 401) throw new FrieApiError("Your session has expired. Please sign in again.", 401);
  if (!response.ok) throw await responseError(response, "Unable to delete the document.");
  notifyDataChanged();
}

export async function editExtraction(id: number, changes: Record<string, string | number>): Promise<ExtractionResult> {
  const response = await authorizedFetch(`/documents/${id}/extraction`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(changes),
  });
  if (!response.ok) throw await responseError(response, "Unable to save extracted field edits.");
  const result = await readJson<ExtractionResult>(response); notifyDataChanged(); return result;
}

export async function editBankTransaction(id: number, operation: "edit" | "add" | "delete", index?: number, transaction?: Record<string, unknown>): Promise<{document_id:number; transactions:number; review_status:string}> {
  const response = await authorizedFetch(`/documents/${id}/transactions`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ operation, index, transaction }),
  });
  if (!response.ok) throw await responseError(response, "Unable to update the bank transaction.");
  const result = await readJson<{document_id:number; transactions:number; review_status:string}>(response); notifyDataChanged(); return result;
}

export async function downloadDocument(id: number): Promise<Blob> {
  const response = await authorizedFetch(`/documents/${id}/file`);
  if (response.status === 401) {
    throw new FrieApiError("Your session has expired. Please sign in again.", 401);
  }
  if (!response.ok) {
    throw new FrieApiError("Unable to download the document.", response.status);
  }
  return response.blob();
}

export interface ExtractionResult {
  id: number;
  document_id: number;
  raw_text: string;
  structured_data: Record<string, unknown>;
  extraction_status: string;
  review_status: string;
  engine: string;
  confidence: number | null;
  error_message: string | null;
}

export async function triggerExtraction(id: number): Promise<ExtractionResult> {
  const response = await authorizedFetch(`/documents/${id}/extract`, { method: "POST" });
  if (response.status === 401) {
    throw new FrieApiError("Your session has expired. Please sign in again.", 401);
  }
  if (response.status === 404) {
    throw new FrieApiError("The document is not available for extraction.", 404);
  }
  if (!response.ok) {
    throw new FrieApiError("Unable to extract the document.", response.status);
  }
  const result = await readJson<ExtractionResult>(response); notifyDataChanged(); return result;
}

export async function fetchExtraction(id: number): Promise<ExtractionResult | null> {
  const response = await authorizedFetch(`/documents/${id}/extraction`);
  if (response.status === 401) {
    throw new FrieApiError("Your session has expired. Please sign in again.", 401);
  }
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new FrieApiError("Unable to load the extraction.", response.status);
  }
  return readJson<ExtractionResult>(response);
}

export async function reviewExtraction(id: number, decision: "accept" | "flag"): Promise<ExtractionResult> {
  const response = await authorizedFetch(`/documents/${id}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision }),
  });
  if (response.status === 401) {
    throw new FrieApiError("Your session has expired. Please sign in again.", 401);
  }
  if (response.status === 404) {
    throw new FrieApiError("The document is not available for review.", 404);
  }
  if (!response.ok) {
    throw new FrieApiError(
      decision === "accept"
        ? "Only successfully extracted output can be accepted."
        : "Unable to flag the document.",
      response.status,
    );
  }
  const result = await readJson<ExtractionResult>(response); notifyDataChanged(); return result;
}

export interface FinancialStatus {
  has_loan?: string | null;
  insurance_status?: string | null;
  inv_fd?: string | null;
  inv_rd?: string | null;
  inv_sip?: string | null;
  inv_mutual_fund?: string | null;
  inv_ppf?: string | null;
  inv_nps?: string | null;
}

export async function fetchFinancialStatus(): Promise<FinancialStatus | null> {
  const response = await authorizedFetch("/profile/financial-status");
  if (response.status === 401) {
    throw new FrieApiError("Your session has expired. Please sign in again.", 401);
  }
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new FrieApiError("Unable to load the financial status.", response.status);
  }
  return readJson<FinancialStatus>(response);
}

export async function saveFinancialStatus(status: FinancialStatus): Promise<FinancialStatus> {
  const response = await authorizedFetch("/profile/financial-status", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(status),
  });
  if (response.status === 401) {
    throw new FrieApiError("Your session has expired. Please sign in again.", 401);
  }
  if (!response.ok) {
    throw new FrieApiError("Unable to save the financial status.", response.status);
  }
  const result = await readJson<FinancialStatus>(response); notifyDataChanged(); return result;
}

export interface StoredFeature {
  feature_name: string;
  feature_type: string;
  value_num: number | null;
  value_text: string | null;
  provenance: string;
  status: string;
  source_document_id: number | null;
}

export interface FeatureReadiness {
  total_required: number;
  available: number;
  missing: { feature: string; reason: string; block: string }[];
  status: string;
  by_provenance: Record<string, number>;
}

export interface BuildSummary extends FeatureReadiness {
  stored: number;
}

export async function buildFeatures(): Promise<BuildSummary> {
  const response = await authorizedFetch("/features/build", { method: "POST" });
  if (response.status === 401) {
    throw new FrieApiError("Your session has expired. Please sign in again.", 401);
  }
  if (!response.ok) {
    throw new FrieApiError("Unable to build the features.", response.status);
  }
  return readJson<BuildSummary>(response);
}

export async function listFeatures(): Promise<StoredFeature[]> {
  const response = await authorizedFetch("/features");
  if (response.status === 401) {
    throw new FrieApiError("Your session has expired. Please sign in again.", 401);
  }
  if (!response.ok) {
    throw new FrieApiError("Unable to load the features.", response.status);
  }
  return readJson<StoredFeature[]>(response);
}

export async function fetchFeatureReadiness(): Promise<FeatureReadiness> {
  const response = await authorizedFetch("/features/readiness");
  if (response.status === 401) {
    throw new FrieApiError("Your session has expired. Please sign in again.", 401);
  }
  if (!response.ok) {
    throw new FrieApiError("Unable to load feature readiness.", response.status);
  }
  return readJson<FeatureReadiness>(response);
}

export async function fetchAssessmentStatus(): Promise<AssessmentStatus> {
  const response = await authorizedFetch("/analysis/status");
  if (response.status === 401) throw new FrieApiError("Your session has expired. Please sign in again.", 401);
  if (!response.ok) throw await responseError(response, "Unable to load assessment readiness.");
  return readJson<AssessmentStatus>(response);
}

function apiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL?.trim();
  if (!configured) {
    throw new FrieApiError("The FRIE API base URL is not configured.");
  }
  return configured.replace(/\/$/, "");
}

async function readJson<T>(response: Response): Promise<T> {
  try {
    return (await response.json()) as T;
  } catch {
    throw new FrieApiError("The FRIE service returned an unreadable response.", response.status);
  }
}

function publicApiFailure(status: number): FrieApiError {
  if (status === 422) {
    return new FrieApiError("The scoring request was rejected.", status);
  }
  if (status === 503) {
    return new FrieApiError("FRIE scoring is temporarily unavailable.", status);
  }
  return new FrieApiError("Unable to complete FRIE scoring.", status);
}

async function responseError(response: Response, fallback: string): Promise<FrieApiError> {
  let detail = "";
  try {
    const body = await response.json();
    const raw = body?.detail ?? body?.message;
    if (typeof raw === "string") detail = raw;
    else if (raw && typeof raw === "object") {
      detail = raw.message ?? raw.msg ?? "";
      if (!detail && Array.isArray(raw.missing_groups) && raw.missing_groups.length) {
        detail = `Missing data for: ${raw.missing_groups.join(", ")}.`;
      }
    }
    if (!detail && Array.isArray(body?.errors)) detail = body.errors.join("; ");
  } catch {
    // Keep the status-aware fallback if the response is not JSON.
  }
  return new FrieApiError(detail || fallback, response.status);
}

export async function getHealth(): Promise<HealthResponse> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}/health`);
  } catch {
    throw new FrieApiError("Unable to reach the FRIE scoring service.");
  }

  const body = await readJson<HealthResponse>(response);
  if (!response.ok) {
    throw new FrieApiError("FRIE scoring is temporarily unavailable.", response.status);
  }
  return body;
}

export async function predictFrieScore(features: CustomerFeatureMap): Promise<PredictionResponse> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}/predict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ features }),
    });
  } catch {
    throw new FrieApiError("Unable to reach the FRIE scoring service.");
  }

  if (!response.ok) {
    throw await responseError(response, publicApiFailure(response.status).message);
  }

  const body = await readJson<PredictionResponse>(response);
  if (!Number.isFinite(body.frie_score) || !body.reliability_level) {
    throw new FrieApiError("The FRIE service returned an incomplete score.");
  }
  return body;
}

export async function createAssessment(): Promise<AssessmentRecord> {
  const response = await authorizedFetch("/analysis/assess", { method: "POST" });
  if (!response.ok) throw await responseError(response, "Unable to calculate your FRIE assessment.");
  const result = await readJson<AssessmentRecord>(response);
  if (typeof window !== "undefined") window.dispatchEvent(new Event("frie:assessment-created"));
  return result;
}

export async function fetchLatestAssessment(): Promise<AssessmentRecord | null> {
  const response = await authorizedFetch("/analysis/latest");
  if (!response.ok) throw await responseError(response, "Unable to load the latest assessment.");
  return readJson<AssessmentRecord | null>(response);
}

export async function fetchAssessmentHistory(): Promise<AssessmentRecord[]> {
  const response = await authorizedFetch("/analysis/history");
  if (!response.ok) throw await responseError(response, "Unable to load assessment history.");
  return readJson<AssessmentRecord[]>(response);
}

export async function fetchLocalExplanation(): Promise<LocalExplanation> {
  const response = await authorizedFetch("/analysis/explanation");
  if (!response.ok) throw await responseError(response, "Unable to load the local model explanation.");
  return readJson<LocalExplanation>(response);
}

// ============================================
// NEW: Bank Import (CSV/XLSX/TXT)
// ============================================

export interface BankImportSummary {
  months_covered: number;
  transactions_imported: number;
  detected_format: string;
  date_range: [string, string] | null;
  total_credits: number;
  total_debits: number;
  warnings: string[];
  monthly_features: Record<string, number>;
  extraction_id: number;
  document_id: number;
}

export async function importBankTransactions(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<BankImportSummary> {
  const form = new FormData();
  form.append("file", file, file.name);
  const session = loadSession();

  return new Promise<BankImportSummary>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${apiBaseUrl()}/documents/import/bank`);
    if (session) {
      request.setRequestHeader("Authorization", `Bearer ${session.token}`);
    }
    request.upload.onprogress = event => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };
    request.onerror = () => reject(new FrieApiError("Unable to reach the FRIE service."));
    request.onload = () => {
      if (request.status === 201) {
        try {
          const result = JSON.parse(request.responseText) as BankImportSummary;
          notifyDataChanged();
          resolve(result);
        } catch {
          reject(new FrieApiError("The FRIE service returned an unreadable response.", request.status));
        }
        return;
      }
      if (request.status === 401) {
        reject(new FrieApiError("Your session has expired. Please sign in again.", 401));
        return;
      }
      if (request.status === 413) {
        reject(new FrieApiError("The file exceeds the 10 MB upload limit.", 413));
        return;
      }
      if (request.status === 415) {
        reject(new FrieApiError("Unsupported file type. Use CSV, XLSX, XLS, TXT, PDF, PNG, or JPEG.", 415));
        return;
      }
      if (request.status === 422) {
        let detail = "Bank import failed.";
        try {
          const body = JSON.parse(request.responseText);
          if (body.errors) detail = body.errors.join("; ");
          else if (body.detail) detail = body.detail;
        } catch {
          // ignore
        }
        reject(new FrieApiError(detail, 422));
        return;
      }
      reject(new FrieApiError("Unable to import bank transactions.", request.status));
    };
    request.send(form);
  });
}

// ============================================
// NEW: Completeness with Group Breakdown
// ============================================

export interface GroupCompleteness {
  available: number;
  total: number;
  percentage: number;
}

export interface CompletenessResponse {
  total_required: number;
  available: number;
  status: string;
  by_provenance: Record<string, number>;
  by_status: Record<string, number>;
  group_completeness: Record<string, GroupCompleteness>;
}

export async function fetchCompleteness(): Promise<CompletenessResponse> {
  const response = await authorizedFetch("/features/completeness");
  if (response.status === 401) {
    throw new FrieApiError("Your session has expired. Please sign in again.", 401);
  }
  if (!response.ok) {
    throw new FrieApiError("Unable to load feature completeness.", response.status);
  }
  return readJson<CompletenessResponse>(response);
}

// ============================================
// NEW: Partial Prediction
// ============================================

export interface PartialPredictionRequest {
  features: Record<string, number | string | null>;
}

export interface PartialPredictionResponse {
  frie_score: number;
  reliability_level: ReliabilityLevel;
  data_coverage: number;
  available_features: number;
  total_features: number;
  missing_groups: string[];
  model_used: string;
  warning: string | null;
}

export async function predictPartial(features: Record<string, number | string | null>): Promise<PartialPredictionResponse> {
  let response: Response;
  try {
    response = await authorizedFetch("/predict/partial", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ features }),
    });
  } catch {
    throw new FrieApiError("Unable to reach the FRIE scoring service.");
  }

  if (!response.ok) {
    throw await responseError(
      response,
      response.status === 422 ? "Insufficient financial information." : publicApiFailure(response.status).message,
    );
  }

  const body = await readJson<PartialPredictionResponse>(response);
  if (!Number.isFinite(body.frie_score) || !body.reliability_level) {
    throw new FrieApiError("The FRIE service returned an incomplete partial score.");
  }
  return body;
}
