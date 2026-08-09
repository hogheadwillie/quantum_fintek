/**
 * QuantumFintek API client.
 * All methods throw an Error with a human-readable message on non-2xx responses.
 */

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const TOKEN_KEY = 'qf_access_token';
export const REFRESH_KEY = 'qf_refresh_token';

// ── low-level fetch ──────────────────────────────────────────────────────────

async function request<T>(
  path: string,
  init: RequestInit = {},
  token?: string,
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init.headers as Record<string, string>),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, { ...init, headers });
  let data: unknown;
  try {
    data = await res.json();
  } catch {
    data = {};
  }
  if (!res.ok) {
    const d = data as Record<string, unknown>;
    const detail = typeof d?.detail === 'string' ? d.detail : `HTTP ${res.status}`;
    throw new Error(detail);
  }
  return data as T;
}

// ── auth ─────────────────────────────────────────────────────────────────────

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserResponse {
  id: string;
  email: string;
  username: string;
  status: string;
  roles: string[];
}

export async function apiRegister(
  email: string,
  username: string,
  password: string,
): Promise<UserResponse> {
  return request<UserResponse>('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, username, password }),
  });
}

export async function apiLogin(
  email: string,
  password: string,
): Promise<TokenResponse> {
  return request<TokenResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export async function apiMe(token: string): Promise<UserResponse> {
  return request<UserResponse>('/auth/me', {}, token);
}

// ── quant ─────────────────────────────────────────────────────────────────────

export interface OptimizeResult {
  weights: number[];
  n_assets: number;
}

export interface RiskResult {
  historical_var: number;
  cvar: number;
  volatility_annual: number;
}

export interface BacktestResult {
  total_return: number;
  annualised_return: number;
  annualised_volatility: number;
  sharpe_ratio: number;
  max_drawdown: number;
  n_periods: number;
  strategy: string;
  equity: number[];
}

export interface FactorResult {
  alpha: number;
  annualised_alpha: number;
  betas: number[];
  factor_names: string[];
  r_squared: number;
  t_stats: number[];
  residual_volatility: number;
}

export async function apiOptimize(
  token: string,
  expected_returns: number[],
  covariance: number[][],
  risk_free_rate = 0.02,
): Promise<OptimizeResult> {
  return request<OptimizeResult>(
    '/quant/optimize',
    { method: 'POST', body: JSON.stringify({ expected_returns, covariance, risk_free_rate }) },
    token,
  );
}

export async function apiRisk(
  token: string,
  returns: number[],
  confidence = 0.95,
): Promise<RiskResult> {
  return request<RiskResult>(
    '/quant/risk',
    { method: 'POST', body: JSON.stringify({ returns, confidence }) },
    token,
  );
}

export async function apiBacktest(
  token: string,
  returns: number[][],
  weights: number[],
  risk_free_rate = 0.02,
): Promise<BacktestResult> {
  return request<BacktestResult>(
    '/quant/backtest',
    {
      method: 'POST',
      body: JSON.stringify({ returns, weights, risk_free_rate, periods_per_year: 252, strategy: 'custom' }),
    },
    token,
  );
}

export async function apiFactorModel(
  token: string,
  asset_returns: number[],
  factor_returns: number[][],
  factor_names: string[],
): Promise<FactorResult> {
  return request<FactorResult>(
    '/quant/factor',
    { method: 'POST', body: JSON.stringify({ asset_returns, factor_returns, factor_names, periods_per_year: 252 }) },
    token,
  );
}

// ── ai ────────────────────────────────────────────────────────────────────────

export interface AnomalyResult {
  labels: number[];
  scores: number[];
  n_anomalies: number;
}

export interface SentimentItem {
  label: string;
  score: number;
  confidence: number;
  positive_count: number;
  negative_count: number;
  uncertainty_count: number;
  word_count: number;
}

export interface SentimentResult {
  results: SentimentItem[];
  n_positive: number;
  n_negative: number;
  n_neutral: number;
  average_score: number;
}

export async function apiAnomaly(
  token: string,
  samples: number[][],
  contamination = 0.05,
): Promise<AnomalyResult> {
  return request<AnomalyResult>(
    '/ai/anomaly',
    { method: 'POST', body: JSON.stringify({ samples, contamination }) },
    token,
  );
}

export async function apiSentiment(
  token: string,
  texts: string[],
): Promise<SentimentResult> {
  return request<SentimentResult>(
    '/ai/sentiment',
    { method: 'POST', body: JSON.stringify({ texts }) },
    token,
  );
}

// ── trading ───────────────────────────────────────────────────────────────────

export interface OrderOut {
  id: string;
  symbol: string;
  side: string;
  order_type: string;
  quantity: number;
  limit_price: number | null;
  stop_price: number | null;
  status: string;
  fill_price: number | null;
  notes: string;
  created_at: string;
  updated_at: string;
  actor_id: string;
}

export interface OrderListResponse {
  orders: OrderOut[];
  total: number;
  page: number;
  page_size: number;
}

export interface PositionItem {
  symbol: string;
  quantity: number;
  avg_fill_price: number;
  current_value_estimate: number;
  side: string;
}

export interface PositionsResponse {
  positions: PositionItem[];
  total_symbols: number;
}

export interface MarketQuote {
  symbol: string;
  bid: number;
  ask: number;
  last: number;
  volume: number;
  change_pct: number;
  timestamp: string;
}

export interface MarketDataResponse {
  quotes: MarketQuote[];
}

export interface PlaceOrderBody {
  symbol: string;
  side: 'buy' | 'sell';
  order_type: 'market' | 'limit' | 'stop';
  quantity: number;
  limit_price?: number;
  stop_price?: number;
  notes?: string;
}

export async function apiPlaceOrder(
  token: string,
  body: PlaceOrderBody,
): Promise<OrderOut> {
  return request<OrderOut>(
    '/trading/orders',
    { method: 'POST', body: JSON.stringify(body) },
    token,
  );
}

export async function apiListOrders(
  token: string,
  page = 1,
  pageSize = 50,
): Promise<OrderListResponse> {
  return request<OrderListResponse>(
    `/trading/orders?page=${page}&page_size=${pageSize}`,
    {},
    token,
  );
}

export async function apiPositions(token: string): Promise<PositionsResponse> {
  return request<PositionsResponse>('/trading/positions', {}, token);
}

export async function apiMarketData(
  token: string,
  symbols = 'AAPL,MSFT,GOOGL,AMZN,NVDA',
): Promise<MarketDataResponse> {
  return request<MarketDataResponse>(
    `/trading/market-data?symbols=${encodeURIComponent(symbols)}`,
    {},
    token,
  );
}

// ── admin ─────────────────────────────────────────────────────────────────────

export interface AuditEventOut {
  id: string;
  actor_id: string | null;
  action: string;
  resource: string;
  detail: string;
  created_at: string;
}

export interface AuditListResponse {
  events: AuditEventOut[];
  total: number;
  page: number;
  page_size: number;
}

export interface UserOut {
  id: string;
  email: string;
  username: string;
  status: string;
  created_at: string;
  last_login: string | null;
}

export interface UserListResponse {
  users: UserOut[];
  total: number;
}

export async function apiAdminAudit(
  token: string,
  page = 1,
  pageSize = 100,
): Promise<AuditListResponse> {
  return request<AuditListResponse>(
    `/admin/audit?page=${page}&page_size=${pageSize}`,
    {},
    token,
  );
}

export async function apiAdminUsers(
  token: string,
  page = 1,
  pageSize = 100,
): Promise<UserListResponse> {
  return request<UserListResponse>(
    `/admin/users?page=${page}&page_size=${pageSize}`,
    {},
    token,
  );
}

// ── compliance ────────────────────────────────────────────────────────────────

export interface EvidenceItem {
  control: string;
  title: string;
  status: string;
  evidence: string;
  collected_at: string;
}

export interface ComplianceResponse {
  framework: string;
  items: EvidenceItem[];
  audit_event_count: number;
}

export async function apiCompliance(token: string): Promise<ComplianceResponse> {
  return request<ComplianceResponse>('/compliance/evidence', {}, token);
}

// ── z/OS ──────────────────────────────────────────────────────────────────────

export interface ZOSLPARMetrics {
  lpar_name: string;
  status: string;
  cpu_utilization_pct: number;
  memory_used_gb: number;
  memory_total_gb: number;
  memory_used_pct: number;
  ziip_utilization_pct: number;
  active_jobs: number;
  active_initiators: number;
  mips: number;
  timestamp: string;
}

export interface ZOSHealthResponse {
  sysplex: string;
  lpars: ZOSLPARMetrics[];
  total_lpars: number;
  online_lpars: number;
  mq_queues: Record<string, number>;
}

export interface LPAROut {
  lpar_name: string;
  sysplex_name: string;
  system_nickname: string;
  zos_version: string;
  cpu_model: string;
  max_memory_gb: number;
  mq_queue_manager: string;
  status: string;
}

export interface JobOut {
  job_id: string;
  job_name: string;
  lpar: string;
  owner: string;
  status: string;
  return_code: number | null;
  abend_code: string | null;
  completion: string | null;
  submitted_at: string;
  started_at: string | null;
  ended_at: string | null;
}

export interface JobListResponse {
  jobs: JobOut[];
  total: number;
}

export interface JobSubmitBody {
  job_name: string;
  lpar: string;
  program?: string;
  parm?: string;
  jcl?: string;
  notify_userid?: string;
  input_dsn?: string;
}

export interface DatasetOut {
  dsn: string;
  recfm: string;
  lrecl: number;
  blksize: number;
  size_tracks: number;
}

export interface DatasetListResponse {
  datasets: DatasetOut[];
  total: number;
}

export interface DatasetUploadBody {
  dsn: string;
  lines: string[];
  recfm?: string;
  lrecl?: number;
  code_page?: string;
}

export interface DatasetUploadResponse {
  dsn: string;
  records_written: number;
  byte_count: number;
  recfm: string;
  lrecl: number;
  ebcdic_b64: string;
}

export interface DatasetDownloadBody {
  dsn: string;
  code_page?: string;
  max_records?: number;
}

export interface DatasetDownloadResponse {
  dsn: string;
  records: string[];
  record_count: number;
  code_page: string;
}

export interface TranscodeBody {
  text: string;
  code_page?: string;
  record_length?: number;
  mode?: string;
  include_hex_dump?: boolean;
}

export interface TranscodeResponse {
  code_page: string;
  mode: string;
  record_length: number;
  ebcdic_b64: string;
  byte_count: number;
  hex_dump: string | null;
}

export interface MQBridgeStatusResponse {
  queue_manager: string;
  connected: boolean;
  queues: Record<string, number>;
}

export interface MQPutBody {
  queue_name: string;
  payload: string;
  msg_type?: string;
  reply_to_q?: string;
  persist?: boolean;
}

export interface MQPutResponse {
  queue_name: string;
  msg_id: string;
  queue_depth: number;
}

export interface MQGetResponse {
  queue_name: string;
  msg_id: string | null;
  payload: string | null;
  msg_type: string | null;
  put_time: string | null;
  queue_depth: number;
}

export async function apiZosHealth(token: string): Promise<ZOSHealthResponse> {
  return request<ZOSHealthResponse>('/zos/health', {}, token);
}

export async function apiZosLpars(token: string): Promise<LPAROut[]> {
  return request<LPAROut[]>('/zos/lpars', {}, token);
}

export async function apiZosJobs(token: string, lpar = 'SYSA'): Promise<JobListResponse> {
  return request<JobListResponse>(`/zos/jobs?lpar=${lpar}`, {}, token);
}

export async function apiZosSubmitJob(token: string, body: JobSubmitBody): Promise<JobOut> {
  return request<JobOut>('/zos/jobs', { method: 'POST', body: JSON.stringify(body) }, token);
}

export const apiZosDatasets = {
  list: (token: string, hlq = 'QFINTEK') =>
    request<DatasetListResponse>(`/zos/datasets?hlq=${encodeURIComponent(hlq)}`, {}, token),
  upload: (token: string, body: DatasetUploadBody) =>
    request<DatasetUploadResponse>('/zos/datasets/upload', { method: 'POST', body: JSON.stringify(body) }, token),
  download: (token: string, body: DatasetDownloadBody) =>
    request<DatasetDownloadResponse>('/zos/datasets/download', { method: 'POST', body: JSON.stringify(body) }, token),
};

export async function apiZosTranscode(token: string, body: TranscodeBody): Promise<TranscodeResponse> {
  return request<TranscodeResponse>('/zos/transcode', { method: 'POST', body: JSON.stringify(body) }, token);
}

export async function apiZosMQStatus(token: string): Promise<MQBridgeStatusResponse> {
  return request<MQBridgeStatusResponse>('/zos/mqbridge', {}, token);
}

export async function apiZosMQPut(token: string, body: MQPutBody): Promise<MQPutResponse> {
  return request<MQPutResponse>('/zos/mqbridge/put', { method: 'POST', body: JSON.stringify(body) }, token);
}

export async function apiZosMQGet(token: string, queueName: string): Promise<MQGetResponse> {
  return request<MQGetResponse>(`/zos/mqbridge/get?queue_name=${encodeURIComponent(queueName)}`, {}, token);
}

// ── helpers ───────────────────────────────────────────────────────────────────

export function sampleReturns(n = 252): number[] {
  const out: number[] = [];
  for (let i = 0; i < n; i++) out.push(0.0005 + (Math.random() - 0.48) * 0.02);
  return out;
}

export function sampleReturnMatrix(T = 252, N = 3): number[][] {
  return Array.from({ length: T }, () =>
    Array.from({ length: N }, () => 0.0004 + (Math.random() - 0.49) * 0.018),
  );
}

export function sampleMatrix(rows = 50, cols = 4): number[][] {
  return Array.from({ length: rows }, () =>
    Array.from({ length: cols }, () => (Math.random() - 0.5) * 2),
  );
}

export function sampleFactorMatrix(T = 252, K = 3): number[][] {
  return Array.from({ length: T }, () =>
    Array.from({ length: K }, () => (Math.random() - 0.5) * 0.015),
  );
}

export function fmt(n: number, decimals = 4): string {
  return n.toFixed(decimals);
}

export function pct(n: number, decimals = 2): string {
  return `${(n * 100).toFixed(decimals)}%`;
}
