import { getApiBaseUrl } from '@/lib/public-env'

const API_BASE_URL = getApiBaseUrl()

// ============================================================================
// AUTHENTICATION TYPES
// ============================================================================

export interface LoginRequest {
  email: string
  password: string
  otp?: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: {
    id: string
    email: string
    full_name: string | null
    is_admin: boolean
  }
  expires_in: number
}

export interface UserInfo {
  id: string
  email: string
  full_name: string | null
  is_admin: boolean
}

export interface RegisterRequest {
  email: string
  password: string
  full_name?: string
}

export interface RegisterResponse {
  message: string
  user: UserInfo
}

// ============================================================================
// INGESTION TYPES
// ============================================================================

export interface ManualSessionRequest {
  source_ip?: string
}

export interface ManualSessionResponse {
  session_id: string
  websocket_url: string
  expires_at: string
}

export interface CloudIngestRequest {
  oauth_token: string
  cloud_provider?: string
}

export interface CloudSessionResponse {
  session_id: string
  websocket_url: string
  expires_at: string
  cloud_provider: string
}

export interface TelemetryLinkResponse {
  ephemeral_token: string
  websocket_url: string
  expires_at: string
  usage_instructions: string
}

export interface AuditResponse {
  id: string
  filename: string
  sha256_hash: string
  upload_time: string
  file_size: number
  uploader?: string
  source_ip?: string
  ingestion_mode?: string
  status: string
}

export interface IntegrityCheckResponse {
  status: string
  audit_id: string
  sha256: string
  verified: boolean
  message?: string
}

export interface HashChainResponse {
  status: string
  total_entries: number
  broken_at?: string
  message?: string
}

// ============================================================================
// LEDGER TYPES
// ============================================================================

export interface LedgerEntry {
  id: string
  filename: string
  sha256_hash: string
  previous_hash?: string
  merkle_root?: string
  upload_time: string
  file_size: number
  uploader?: string
  source_ip?: string
  ingestion_mode?: string
  status: string
}

type LedgerItemResponse = {
  status: string
  item?: LedgerEntry
}

export interface LedgerListResponse {
  items: LedgerEntry[]
  total: number
  limit: number
  offset: number
}

// ============================================================================
// DASHBOARD TYPES
// ============================================================================

export interface DashboardSummary {
  status?: string
  total_logs: number
  total_sessions: number
  quarantined_files: number
  active_alerts: number
  total_events?: number
  earliest_log?: string | null
  latest_log?: string | null
  critical_threats?: number
  source?: string
  recent_activity?: any[]
}

export interface DashboardTimeline {
  status?: string
  series?: number[]
  timeline: Array<{
    timestamp: string
    event: string
    count: number
  }>
}

export interface DashboardSeverity {
  status?: string
  source?: string
  critical?: number
  warning?: number
  info?: number
  severity_distribution: Array<{
    level: string
    count: number
  }>
}

export interface RecentUpload {
  id: string
  audit_id?: string
  filename: string
  upload_time: string
  file_size: number
  status: string
  sha256_hash?: string
  merkle_root?: string
  ingestion_mode?: string
}

// ============================================================================
// FEATURES TYPES
// ============================================================================

export interface FeatureGenerationRequest {
  audit_id?: string
}

export interface FeatureGenerationResponse {
  status: string
  features_generated?: number
  message?: string
}

export interface FeaturePreviewResponse {
  status: string
  total: number
  items: any[]
}

// ============================================================================
// DETECTION TYPES
// ============================================================================

export interface DetectionSummaryResponse {
  status: string
  total: number
  anomalies: number
  buckets: Array<{
    label: string
    count: number
  }>
  top_users: Array<{
    user: string
    count: number
  }>
  top_ips: Array<{
    ip: string
    count: number
  }>
}

export interface DetectionResult {
  id?: string
  audit_id?: string
  user?: string
  source_ip?: string
  action?: string
  risk_score: number
  is_anomaly: boolean
  timestamp?: string
  [key: string]: any
}

export interface DetectionResultsResponse {
  status: string
  total: number
  items: DetectionResult[]
}

// ============================================================================
// PHASE 2 TYPES
// ============================================================================

export interface Phase2ProcessRequest {
  audit_id: string
  file_path: string
  source_ip?: string
}

export interface Phase2ProcessResponse {
  status: string
  staging_ids: string[]
  audit_id: string
  message?: string
}

export interface StagingPreview {
  staging_id: string
  audit_id: string
  row_hash?: string
  status?: string
  decoded_payload?: any | null
  decode_trace?: any | null
  extracted_variables?: Record<string, any> | null
  ner_tags?: Record<string, any> | null
  normalized_timestamp?: string | null
  human_overrides?: Record<string, any> | null
  created_at?: string | null
  immutable_pointer?: string | null
  lineage?: any
  template?: any
  audit?: {
    audit_id: string
    filename: string
    sha256_hash: string
    source_ip?: string | null
    upload_time?: string | null
  }
}

export interface StagingPreviewsResponse {
  audit_id: string
  count: number
  previews: StagingPreview[]
}

export interface CommitRequest {
  human_overrides?: Record<string, any>
  confirm?: boolean
}

export interface CommitResponse {
  status: string
  message: string
  committed_count?: number
}

// ============================================================================
// PHASE 3 TYPES (hot/cold gateway under /api/phase3)
// ============================================================================

export interface Phase3HealthResponse {
  ok: boolean
  phase: number
  hot_db_path: string
  cold_dir: string
  ttl_seconds: number
}

export interface Phase3ColdRow {
  Target_User?: string
  Notes?: string
  Lineage?: string
  created_at?: string | null
}

export interface Phase3GraphqlQueryResponse {
  ok: boolean
  status: string
  depth: number
  count: number
  data: Phase3ColdRow[]
}

// ============================================================================
// REPORTING TYPES
// ============================================================================

export interface ReportGenerationRequest {
  template_id: string
  audit_id?: string
}

// ============================================================================
// API CLIENT CLASS
// ============================================================================

class ApiClient {
  private baseUrl: string
  private token: string | null = null

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
    if (typeof window !== 'undefined') {
      this.token = localStorage.getItem('auth_token')
    }
  }

  setToken(token: string | null) {
    this.token = token
    if (typeof window !== 'undefined') {
      if (token) {
        localStorage.setItem('auth_token', token)
      } else {
        localStorage.removeItem('auth_token')
      }
    }
  }

  getToken(): string | null {
    if (!this.token && typeof window !== 'undefined') {
      this.token = localStorage.getItem('auth_token')
    }
    return this.token
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    }

    const token = this.getToken()
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    let response: Response
    try {
      response = await fetch(url, {
        ...options,
        headers,
      })
    } catch (error) {
      if (error instanceof TypeError && error.message.includes('fetch')) {
        throw new Error(`Cannot connect to server at ${url}. Is the backend running?`)
      }
      throw error
    }

    if (!response.ok) {
      let errorMessage = `HTTP ${response.status}: ${response.statusText}`
      try {
        const error = await response.json()
        errorMessage = error.detail || error.message || errorMessage
      } catch {
        if (response.status === 404) {
          errorMessage = `Endpoint not found: ${endpoint}. Check if the backend server is running and the route is correct.`
        }
      }
      throw new Error(errorMessage)
    }

    return response.json()
  }

  private async requestFormData<T>(
    endpoint: string,
    formData: FormData,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`
    const headers: HeadersInit = {
      ...options.headers,
    }

    const token = this.getToken()
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    let response: Response
    try {
      response = await fetch(url, {
        ...options,
        method: options.method || 'POST',
        headers,
        body: formData,
      })
    } catch (error) {
      if (error instanceof TypeError && error.message.includes('fetch')) {
        throw new Error(`Cannot connect to server at ${url}. Is the backend running?`)
      }
      throw error
    }

    if (!response.ok) {
      let errorMessage = `HTTP ${response.status}: ${response.statusText}`
      try {
        const error = await response.json()
        errorMessage = error.detail || error.message || errorMessage
      } catch {
        if (response.status === 404) {
          errorMessage = `Endpoint not found: ${endpoint}. Check if the backend server is running and the route is correct.`
        }
      }
      throw new Error(errorMessage)
    }

    return response.json()
  }

  // ==========================================================================
  // AUTHENTICATION METHODS
  // ==========================================================================

  async register(credentials: RegisterRequest): Promise<RegisterResponse> {
    return this.request<RegisterResponse>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify(credentials),
    })
  }

  async login(credentials: LoginRequest): Promise<LoginResponse> {
    const response = await this.request<LoginResponse>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
    })
    this.setToken(response.access_token)
    return response
  }

  async getCurrentUser(): Promise<UserInfo> {
    return this.request<UserInfo>('/api/auth/me')
  }

  async logout(): Promise<void> {
    try {
      await this.request('/api/auth/logout', { method: 'POST' })
    } finally {
      this.setToken(null)
    }
  }

  // ==========================================================================
  // INGESTION METHODS
  // ==========================================================================

  async createManualSession(): Promise<ManualSessionResponse> {
    return this.request<ManualSessionResponse>('/api/ingestion/manual', {
      method: 'POST',
    })
  }

  async createCloudSession(request: CloudIngestRequest): Promise<CloudSessionResponse> {
    return this.request<CloudSessionResponse>('/api/ingestion/cloud', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  async generateTelemetryLink(): Promise<TelemetryLinkResponse> {
    return this.request<TelemetryLinkResponse>('/api/ingestion/generate-telemetry-link', {
      method: 'POST',
    })
  }

  async uploadLog(
    file: File,
    source?: string,
    uploader?: string
  ): Promise<AuditResponse> {
    const formData = new FormData()
    formData.append('file', file)
    if (source) formData.append('source', source)
    if (uploader) formData.append('uploader', uploader)

    return this.requestFormData<AuditResponse>('/api/ingestion/upload-log', formData)
  }

  async uploadWithAuditTrail(
    file: File,
    source?: string,
    uploader?: string
  ): Promise<any> {
    const formData = new FormData()
    formData.append('file', file)
    if (source) formData.append('source', source)
    if (uploader) formData.append('uploader', uploader)

    return this.requestFormData<any>('/api/ingestion/audit-trail', formData)
  }

  async verifyIntegrity(auditId: string): Promise<IntegrityCheckResponse> {
    return this.request<IntegrityCheckResponse>(`/api/ingestion/verify/${auditId}`)
  }

  async verifyHashChain(): Promise<HashChainResponse> {
    return this.request<HashChainResponse>('/api/ingestion/verify-chain')
  }

  // ==========================================================================
  // LEDGER METHODS
  // ==========================================================================

  async listLedger(
    limit: number = 200,
    offset: number = 0,
    query: string = ''
  ): Promise<LedgerListResponse> {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
    })
    if (query) params.append('q', query)

    return this.request<LedgerListResponse>(`/api/ledger/list?${params.toString()}`)
  }

  async getLedgerItem(auditId: string): Promise<LedgerEntry> {
    const res = await this.request<LedgerItemResponse>(`/api/ledger/${auditId}`)
    if (!res?.item) {
      throw new Error(`Ledger item not found: ${auditId}`)
    }
    return res.item
  }

  // ==========================================================================
  // DASHBOARD METHODS
  // ==========================================================================

  async getDashboardSummary(): Promise<DashboardSummary> {
    return this.request<DashboardSummary>('/api/dashboard/summary')
  }

  async getDashboardTimeline(): Promise<DashboardTimeline> {
    return this.request<DashboardTimeline>('/api/dashboard/timeline')
  }

  async getDashboardSeverity(): Promise<DashboardSeverity> {
    return this.request<DashboardSeverity>('/api/dashboard/severity')
  }

  async getRecentUploads(): Promise<RecentUpload[]> {
    const res = await this.request<{ status: string; items: RecentUpload[] }>(
      '/api/dashboard/recent-uploads'
    )
    return res.items ?? []
  }

  // ==========================================================================
  // FEATURES METHODS
  // ==========================================================================

  async generateFeatures(auditId?: string): Promise<FeatureGenerationResponse> {
    const body: any = {}
    if (auditId) body.audit_id = auditId

    return this.request<FeatureGenerationResponse>('/api/generate-features', {
      method: 'POST',
      body: Object.keys(body).length > 0 ? JSON.stringify(body) : undefined,
    })
  }

  async previewFeatures(
    limit: number = 50,
    offset: number = 0,
    auditId?: string
  ): Promise<FeaturePreviewResponse> {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
    })
    if (auditId) params.append('audit_id', auditId)

    return this.request<FeaturePreviewResponse>(`/api/features/preview?${params.toString()}`)
  }

  // ==========================================================================
  // DETECTION METHODS
  // ==========================================================================

  async runDetection(): Promise<any> {
    return this.request<any>('/api/run-detection', {
      method: 'POST',
    })
  }

  async getDetectionSummary(auditId?: string): Promise<DetectionSummaryResponse> {
    const params = auditId ? `?audit_id=${auditId}` : ''
    return this.request<DetectionSummaryResponse>(`/api/detection/summary${params}`)
  }

  async getDetectionResults(
    limit: number = 200,
    offset: number = 0,
    onlyAnomalies: boolean = true,
    minRisk: number = 25,
    query: string = '',
    sort: string = 'risk_desc',
    auditId?: string
  ): Promise<DetectionResultsResponse> {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
      only_anomalies: onlyAnomalies.toString(),
      min_risk: minRisk.toString(),
      sort,
    })
    if (query) params.append('q', query)
    if (auditId) params.append('audit_id', auditId)

    return this.request<DetectionResultsResponse>(`/api/detection/results?${params.toString()}`)
  }

  // ==========================================================================
  // PHASE 2 METHODS
  // ==========================================================================

  async processPhase2(request: Phase2ProcessRequest): Promise<Phase2ProcessResponse> {
    return this.request<Phase2ProcessResponse>('/api/phase2/process', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  async getStagingPreview(stagingId: string): Promise<StagingPreview> {
    return this.request<StagingPreview>(`/api/phase2/preview/${stagingId}`)
  }

  async getStagingPreviews(
    auditId: string,
    limit: number = 10
  ): Promise<StagingPreviewsResponse> {
    return this.request<StagingPreviewsResponse>(
      `/api/phase2/preview/audit/${auditId}?limit=${limit}`
    )
  }

  async commitStaging(
    stagingId: string,
    request: CommitRequest
  ): Promise<CommitResponse> {
    return this.request<CommitResponse>(`/api/phase2/commit/${stagingId}`, {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  async commitStagingBatch(
    auditId: string,
    request: CommitRequest
  ): Promise<CommitResponse> {
    return this.request<CommitResponse>(`/api/phase2/commit/audit/${auditId}`, {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  async rejectStaging(stagingId: string, reason?: string): Promise<{ status: string }> {
    return this.request<{ status: string }>(`/api/phase2/reject/${stagingId}`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    })
  }

  async queryStaging(params: {
    audit_id?: string
    status?: string
    has_template?: boolean
    has_ner_tags?: boolean
    has_timestamp?: boolean
    limit?: number
    offset?: number
  }): Promise<{
    total: number
    limit: number
    offset: number
    count: number
    entries: Array<{
      staging_id: string
      audit_id: string
      status: string
      has_template: boolean
      has_ner_tags: boolean
      has_timestamp: boolean
      created_at: string | null
    }>
  }> {
    const queryParams = new URLSearchParams()
    if (params.audit_id) queryParams.append('audit_id', params.audit_id)
    if (params.status) queryParams.append('status', params.status)
    if (params.has_template !== undefined) queryParams.append('has_template', params.has_template.toString())
    if (params.has_ner_tags !== undefined) queryParams.append('has_ner_tags', params.has_ner_tags.toString())
    if (params.has_timestamp !== undefined) queryParams.append('has_timestamp', params.has_timestamp.toString())
    if (params.limit !== undefined) queryParams.append('limit', params.limit.toString())
    if (params.offset !== undefined) queryParams.append('offset', params.offset.toString())

    return this.request(`/api/phase2/query?${queryParams.toString()}`)
  }

  async getPhase2Statistics(auditId?: string): Promise<Record<string, any>> {
    const q = auditId ? `?audit_id=${auditId}` : ''
    return this.request<Record<string, any>>(`/api/phase2/statistics${q}`)
  }

  // ==========================================================================
  // PHASE 3 GATEWAY (mounted at /api/phase3)
  // ==========================================================================

  async getPhase3Health(): Promise<Phase3HealthResponse> {
    return this.request<Phase3HealthResponse>('/api/phase3/health')
  }

  async phase3GraphqlQuery(params: {
    depth?: number
    Target_User: string
    limit?: number
    offset?: number
  }): Promise<Phase3GraphqlQueryResponse> {
    return this.request<Phase3GraphqlQueryResponse>('/api/phase3/graphql_query', {
      method: 'POST',
      body: JSON.stringify({
        depth: params.depth ?? 2,
        Target_User: params.Target_User,
        limit: params.limit ?? 25,
        offset: params.offset ?? 0,
      }),
    })
  }

  // ==========================================================================
  // REPORTING METHODS
  // ==========================================================================

  async generateReport(request: ReportGenerationRequest): Promise<Blob> {
    const formData = new FormData()
    formData.append('template_id', request.template_id)
    if (request.audit_id) formData.append('audit_id', request.audit_id)

    const url = `${this.baseUrl}/api/reports/generate-demo`
    const headers: HeadersInit = {}
    const token = this.getToken()
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: formData,
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(error.detail || `HTTP error! status: ${response.status}`)
    }

    return response.blob()
  }

  async getReportDemoData(): Promise<any> {
    return this.request<any>('/api/reports/demo-data-transformed')
  }

  // ==========================================================================
  // HEALTH CHECK
  // ==========================================================================

  async healthCheck(): Promise<{ status: string }> {
    return this.request<{ status: string }>('/')
  }
}

export const apiClient = new ApiClient(API_BASE_URL)
