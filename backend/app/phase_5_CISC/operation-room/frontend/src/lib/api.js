const API_BASE = '/api';

export async function request(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const config = {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  };

  const res = await fetch(url, config);

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API error ${res.status}`);
  }

  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  // ── Generic HTTP Methods ─────────────────────────────────
  get:    (path)          => request(path),
  post:   (path, data)    => request(path, { method: 'POST', body: data ? JSON.stringify(data) : undefined }),
  put:    (path, data)    => request(path, { method: 'PUT', body: data ? JSON.stringify(data) : undefined }),
  delete: (path)          => request(path, { method: 'DELETE' }),

  // ── Cases ────────────────────────────────────────────────
  listCases:    ()            => request('/cases'),
  createCase:   (data)        => request('/cases', { method: 'POST', body: JSON.stringify(data) }),
  getCase:      (id)          => request(`/cases/${id}`),
  updateCase:   (id, data)    => request(`/cases/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteCase:   (id)          => request(`/cases/${id}`, { method: 'DELETE' }),

  // ── Evidence ─────────────────────────────────────────────
  listEvidence: (caseId)      => request(`/cases/${caseId}/evidence`),
  importLogs:   (caseId, data)=> request(`/cases/${caseId}/evidence/import`, { method: 'POST', body: JSON.stringify(data) }),
  importMagicQueryRows: (caseId, data) =>
    request(`/cases/${caseId}/evidence/import-magic-query`, { method: 'POST', body: JSON.stringify(data) }),
  verifyHash:   (caseId, hashId) => request(`/cases/${caseId}/evidence/verify`, { method: 'POST', body: JSON.stringify({ hash_id: hashId }) }),

  // ── Evidence Vault ───────────────────────────────────────
  addEvidenceCard:   (caseId, data)   => request(`/cases/${caseId}/evidence-cards`, { method: 'POST', body: JSON.stringify(data) }),
  getEvidenceCards:  (caseId)         => request(`/cases/${caseId}/evidence-cards`),

  // ── Chain of Custody ─────────────────────────────────────
  getChainOfCustody: (caseId) => request(`/cases/${caseId}/chain-of-custody`),

  // ── Timeline ─────────────────────────────────────────────
  buildTimeline:     (caseId, data)   => request(`/cases/${caseId}/timeline/build`, { method: 'POST', body: JSON.stringify(data) }),
  getTimeline:       (caseId, params) => request(`/cases/${caseId}/timeline${params ? '?' + new URLSearchParams(params) : ''}`),
  searchTimeline:    (caseId, data, params) => request(`/cases/${caseId}/timeline/search${params ? '?' + new URLSearchParams(params) : ''}`, { method: 'POST', body: JSON.stringify(data) }),
  getAnchors:        (caseId)         => request(`/cases/${caseId}/timeline/anchors`),
  toggleAnchor:      (caseId, data)   => request(`/cases/${caseId}/timeline/anchors`, { method: 'POST', body: JSON.stringify(data) }),
  getTimelineStats:  (caseId)         => request(`/cases/${caseId}/timeline/stats`),
  searchTimelineStats: (caseId, data, params) => request(`/cases/${caseId}/timeline/stats/search${params ? '?' + new URLSearchParams(params) : ''}`, { method: 'POST', body: JSON.stringify(data) }),

  // ── Anomaly Detection ───────────────────────────────────
  runAnomalyDetection: (caseId, data)  => request(`/cases/${caseId}/anomalies/run`, { method: 'POST', body: JSON.stringify(data) }),
  getAnomalies:        (caseId, params)=> request(`/cases/${caseId}/anomalies${params ? '?' + new URLSearchParams(params) : ''}`),
  searchAnomalies:   (caseId, data, params) => request(`/cases/${caseId}/anomalies/search${params ? '?' + new URLSearchParams(params) : ''}`, { method: 'POST', body: JSON.stringify(data) }),
  getAnomalySummary:   (caseId, runId) => request(`/cases/${caseId}/anomalies/summary${runId ? '?run_id=' + runId : ''}`),
  getAnomalySequences: (caseId, runId) => request(`/cases/${caseId}/anomalies/sequences${runId ? '?run_id=' + runId : ''}`),
  getAnomalyRuns:      (caseId)        => request(`/cases/${caseId}/anomalies/runs`),

  // ── Correlation & RCA ───────────────────────────────────
  runCorrelation:      (caseId, data)  => request(`/cases/${caseId}/correlation/run`, { method: 'POST', body: JSON.stringify(data) }),
  getCorrelationGraph: (caseId, runId, graphEngine) => request(`/cases/${caseId}/correlation/graph${runId ? '?run_id=' + runId : ''}${graphEngine ? `${runId ? '&' : '?'}graph_engine=${encodeURIComponent(graphEngine)}` : ''}${runId || graphEngine ? '&' : '?'}strict_source=true`),
  getCorrelationNarrative: (caseId, runId) => request(`/cases/${caseId}/correlation/narrative${runId ? '?run_id=' + runId : ''}`),
  getCorrelationRuns:  (caseId)        => request(`/cases/${caseId}/correlation/runs`),
  correlationChat:     (caseId, data)  => request(`/cases/${caseId}/correlation/chat`, { method: 'POST', body: JSON.stringify(data) }),
  getCorrelationRules: (caseId)        => request(`/cases/${caseId}/correlation/rules`),
  toggleCorrelationRule: (caseId, ruleId, data) => request(`/cases/${caseId}/correlation/rules/${ruleId}`, { method: 'PUT', body: JSON.stringify(data) }),
  getCorrelationProviders: (caseId)    => request(`/cases/${caseId}/correlation/providers`),

  // ── CRUD & Data-Access ──────────────────────────────────
  runCrud:             (caseId, data)  => request(`/cases/${caseId}/crud/run`, { method: 'POST', body: JSON.stringify(data) }),
  getCrudEvents:       (caseId, params) => request(`/cases/${caseId}/crud/events${params ? '?' + new URLSearchParams(params) : ''}`),
  searchCrudEvents:  (caseId, data, params) => request(`/cases/${caseId}/crud/events/search${params ? '?' + new URLSearchParams(params) : ''}`, { method: 'POST', body: JSON.stringify(data) }),
  searchCrudStats:   (caseId, data)  => request(`/cases/${caseId}/crud/events/stats/search`, { method: 'POST', body: JSON.stringify(data) }),
  getCrudSummary:      (caseId, runId) => request(`/cases/${caseId}/crud/summary${runId ? '?run_id=' + runId : ''}`),
  getCrudRuns:         (caseId)        => request(`/cases/${caseId}/crud/runs`),

  // ── Network & Exfiltration ──────────────────────────────
  runNetwork:          (caseId, data)  => request(`/cases/${caseId}/network/run`, { method: 'POST', body: JSON.stringify(data) }),
  getNetworkFlows:     (caseId, params) => request(`/cases/${caseId}/network/flows${params ? '?' + new URLSearchParams(params) : ''}`),
  searchNetworkFlows: (caseId, data, params) => request(`/cases/${caseId}/network/flows/search${params ? '?' + new URLSearchParams(params) : ''}`, { method: 'POST', body: JSON.stringify(data) }),
  searchNetworkStats: (caseId, data) => request(`/cases/${caseId}/network/flows/stats/search`, { method: 'POST', body: JSON.stringify(data) }),
  getExfilCandidates:  (caseId, runId) => request(`/cases/${caseId}/network/exfil${runId ? '?run_id=' + runId : ''}`),
  getDestinations:     (caseId, runId) => request(`/cases/${caseId}/network/destinations${runId ? '?run_id=' + runId : ''}`),
  getNetworkRuns:      (caseId)        => request(`/cases/${caseId}/network/runs`),

  // ── Data Exfiltration Intelligence ──────────────────────────
  runExfilIntel:          (caseId, data)  => request(`/cases/${caseId}/exfiltration/run`, { method: 'POST', body: JSON.stringify(data) }),
  streamExfilIntel:       (caseId) => `${API_BASE}/cases/${caseId}/exfiltration/run/stream`,
  getExfilIntelSummary:   (caseId, runId) => request(`/cases/${caseId}/exfiltration/summary${runId ? '?run_id=' + runId : ''}`),
  getExfilIntelIncidents: (caseId, runId) => request(`/cases/${caseId}/exfiltration/incidents${runId ? '?run_id=' + runId : ''}`),
  getExfilIntelGraph:     (caseId, runId) => request(`/cases/${caseId}/exfiltration/graph${runId ? '?run_id=' + runId : ''}`),
  getExfilIntelChannels:  (caseId, runId) => request(`/cases/${caseId}/exfiltration/channels${runId ? '?run_id=' + runId : ''}`),
  getExfilIntelRuns:      (caseId)        => request(`/cases/${caseId}/exfiltration/runs`),

  // ── Depth & Impact Assessment ──────────────────────────────
  runDepth:            (caseId, data)  => request(`/cases/${caseId}/depth/run`, { method: 'POST', body: JSON.stringify(data) }),
  getDepthResults:     (caseId, runId) => request(`/cases/${caseId}/depth/results${runId ? '?run_id=' + runId : ''}`),
  getDepthDetails:     (caseId, params) => request(`/cases/${caseId}/depth/details${params ? '?' + new URLSearchParams(params) : ''}`),
  genDepthNarrative:   (caseId, data)  => request(`/cases/${caseId}/depth/narrative`, { method: 'POST', body: JSON.stringify(data) }),
  getDepthNarrative:   (caseId, runId) => request(`/cases/${caseId}/depth/narrative${runId ? '?run_id=' + runId : ''}`),
  getDepthRuns:        (caseId)        => request(`/cases/${caseId}/depth/runs`),

  // ── Global Audit ─────────────────────────────────────────
  getAuditLog: (limit = 200)  => request(`/audit-log?limit=${limit}`),
};
