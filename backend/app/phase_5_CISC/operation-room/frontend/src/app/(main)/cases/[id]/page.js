'use client';

import React, { useEffect, useState, useRef } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { Download, FolderPlus, Link2, Package, Search, PlayCircle, Loader2, CheckCircle2, ShieldAlert } from 'lucide-react';
import { api } from '@operation-room/lib/api';
import StatusBadge from '@operation-room/components/StatusBadge';

const orHome =
  typeof process !== 'undefined' && process.env.NEXT_PUBLIC_OR_OPERATION_HOME
    ? process.env.NEXT_PUBLIC_OR_OPERATION_HOME
    : '/';

// Playbook Definitions
const PLAYBOOKS = {
  FULL_AUDIT: {
    id: 'FULL_AUDIT',
    label: 'Full Audit',
    modules: ['timeline', 'anomaly', 'network', 'crud', 'correlation', 'depth'],
    color: 'var(--primary)'
  },
  RANSOMWARE: {
    id: 'RANSOMWARE',
    label: 'Ransomware Fast-Triage',
    modules: ['timeline', 'network', 'crud', 'depth'],
    color: '#e11d48'
  },
  EXFILTRATION: {
    id: 'EXFILTRATION',
    label: 'Data Exfiltration Scan',
    modules: ['timeline', 'anomaly', 'network', 'correlation'],
    color: '#f59e0b'
  }
};

export default function CaseDetailPage() {
  const { id } = useParams();
  const [caseData, setCaseData] = useState(null);
  const [evidence, setEvidence] = useState([]);
  const [evidenceCards, setEvidenceCards] = useState([]);
  const [exportsList, setExportsList] = useState([]);
  const [selectedExports, setSelectedExports] = useState([]);
  const [cocFeed, setCocFeed] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  // Playbook execution state
  const [activePlaybook, setActivePlaybook] = useState(null);
  const [moduleStatus, setModuleStatus] = useState({}); // 'pending' | 'running' | 'completed' | 'error'
  const isRunningRef = useRef(false);

  const fetchCoc = async () => {
    try {
      const feed = await api.getChainOfCustody(id);
      setCocFeed(feed || []);
    } catch(e) {}
  };

  const fetchExports = async () => {
    try {
      const res = await api.get(`/v4/studio/cases/${id}/exports`);
      setExportsList(res.exports || []);
    } catch (e) {
      console.warn("Failed fetching exports", e);
    }
  };

  const handleDeleteExport = async (filename) => {
    if (!confirm('Are you sure you want to delete this export?')) return;
    try {
      await api.delete(`/v4/studio/cases/${id}/exports/${filename}`);
      fetchExports(); // refresh list
      setSelectedExports(selectedExports.filter(f => f !== filename));
    } catch (e) {
      alert("Failed to delete export: " + e.message);
    }
  };

  const handleSelectExport = (filename) => {
    if (selectedExports.includes(filename)) {
      setSelectedExports(selectedExports.filter(f => f !== filename));
    } else {
      setSelectedExports([...selectedExports, filename]);
    }
  };

  const handleSelectAllExports = (e) => {
    if (e.target.checked) {
      setSelectedExports(exportsList.map(exp => exp.filename));
    } else {
      setSelectedExports([]);
    }
  };

  const handleBulkDeleteExports = async () => {
    if (!confirm(`Are you sure you want to permanently delete ${selectedExports.length} exports?`)) return;
    try {
      for (const filename of selectedExports) {
        await api.delete(`/v4/studio/cases/${id}/exports/${filename}`);
      }
      setSelectedExports([]);
      fetchExports();
    } catch (e) {
      alert("Failed to bulk delete exports: " + e.message);
    }
  };

  const handleBulkDownloadExports = () => {
    if (!confirm(`Download ${selectedExports.length} files?`)) return;
    selectedExports.forEach(filename => {
       window.open(`/api/v4/studio/cases/${id}/exports/download/${filename}`, '_blank');
    });
  };

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    setCaseData(null);

    (async () => {
      try {
        const c = await api.getCase(id);
        if (cancelled) return;
        setCaseData(c);
        const [ev, cards] = await Promise.all([
          api.listEvidence(id),
          api.getEvidenceCards(id).catch(() => []),
        ]);
        if (cancelled) return;
        setEvidence(ev);
        setEvidenceCards(cards);
        fetchCoc();
        fetchExports();
      } catch (e) {
        if (cancelled) return;
        const msg = e instanceof Error ? e.message : String(e);
        setLoadError(msg);
        setCaseData(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    const interval = setInterval(() => {
      if (isRunningRef.current) {
        fetchCoc();
      }
    }, 2000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [id]);

  const runPlaybook = async (playbookKey) => {
    if (isRunningRef.current) return;
    const playbook = PLAYBOOKS[playbookKey];
    setActivePlaybook(playbook);
    isRunningRef.current = true;

    // Initialize statuses
    const initialStatus = {};
    playbook.modules.forEach(m => initialStatus[m] = 'pending');
    setModuleStatus(initialStatus);

    // Sequential execute
    for (const mod of playbook.modules) {
      setModuleStatus(prev => ({ ...prev, [mod]: 'running' }));
      try {
        let endpoint = `/cases/${id}/${mod}/run`;
        if (mod === 'timeline') endpoint = `/cases/${id}/timeline/build`;
        await api.post(endpoint, {}); // Run empty spec
        setModuleStatus(prev => ({ ...prev, [mod]: 'completed' }));
      } catch (err) {
        console.error(`Failed executing ${mod}:`, err);
        setModuleStatus(prev => ({ ...prev, [mod]: 'error' }));
        break; // Stop playbook on error
      }
    }
    
    isRunningRef.current = false;
    fetchCoc(); // Final fetch
  };

  if (loading) {
    return <div className="loading-overlay"><div className="spinner" /><span>Loading case…</span></div>;
  }

  if (loadError) {
    return (
      <div className="glass-card-static animate-in" style={{ maxWidth: 520 }}>
        <h2 style={{ fontSize: 18, marginBottom: 8 }}>Case unavailable</h2>
        <p style={{ color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 16 }}>
          {loadError}
        </p>
        <p style={{ color: 'var(--text-muted)', fontSize: 14, marginBottom: 20 }}>
          The case may have been removed, or this URL is outdated. Open the dashboard to see current cases.
        </p>
        <Link href={orHome} className="btn btn-primary">
          Back to dashboard
        </Link>
      </div>
    );
  }

  if (!caseData) {
    return (
      <div className="glass-card-static">
        <p>Case not found.</p>
        <Link href={orHome} className="btn btn-secondary" style={{ marginTop: 16 }}>
          Back to dashboard
        </Link>
      </div>
    );
  }

  return (
    <>
      <div className="page-header animate-in">
        <div>
          <h1>{caseData.title}</h1>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginTop: 6 }}>
            <StatusBadge value={caseData.status} />
            <StatusBadge value={caseData.priority} />
            <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>
              Created {new Date(caseData.created_at).toLocaleString()}
            </span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <Link href={`/cases/${id}/import`} className="btn btn-primary">
            <Download size={15} /> Magic Query
          </Link>
          <Link href={`/cases/${id}/timeline`} className="btn btn-secondary">
            <Search size={15} /> Timeline
          </Link>
          <Link href={`/cases/${id}/chain-of-custody`} className="btn btn-secondary">
            <Link2 size={15} /> Chain of Custody
          </Link>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.2fr) minmax(0, 0.8fr)', gap: 24, marginBottom: 28 }}>
        
        {/* Left Column: Metadata & Evidence */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {/* Case Info Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
            <div className="glass-card-static animate-in animate-in-delay-1">
              <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 14 }}>
                CASE METADATA
              </h3>
              <table className="data-table">
                <tbody>
                  <tr><td style={{ fontWeight: 600, width: 130 }}>Case ID</td>
                      <td><span className="hash-value" style={{ fontSize: 11 }}>{caseData.case_id}</span></td></tr>
                  <tr><td style={{ fontWeight: 600 }}>Classification</td><td>{caseData.classification}</td></tr>
                  <tr><td style={{ fontWeight: 600 }}>Lead Investigator</td><td>{caseData.lead_investigator}</td></tr>
                  <tr><td style={{ fontWeight: 600 }}>Reason</td><td>{caseData.investigation_reason || '—'}</td></tr>
                </tbody>
              </table>
            </div>
            <div className="glass-card-static animate-in animate-in-delay-2">
              <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 14 }}>
                DESCRIPTION
              </h3>
              <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.7 }}>
                {caseData.description || 'No description provided.'}
              </p>
              <div style={{ marginTop: 20, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div className="stat-card glass-card" style={{ padding: 12 }}>
                  <div className="stat-value" style={{ fontSize: 20 }}>{caseData.evidence_count}</div>
                  <div className="stat-label">Evidence</div>
                </div>
                <div className="stat-card glass-card" style={{ padding: 12 }}>
                  <div className="stat-value" style={{ fontSize: 20 }}>{cocFeed.length || caseData.coc_count}</div>
                  <div className="stat-label">CoC Events</div>
                </div>
              </div>
            </div>
          </div>

          {/* Evidence Table */}
          <div className="glass-card-static animate-in animate-in-delay-3" style={{ flex: 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-muted)' }}>
                EVIDENCE ARTEFACTS
              </h3>
            </div>

            {evidence.length === 0 ? (
              <div className="empty-state" style={{ padding: 36 }}>
                <Package size={40} className="empty-state-glyph" />
                <h3>No Evidence Imported Yet</h3>
                <p>Import logs via the NLP Query Agent to start your analysis.</p>
              </div>
            ) : (
              <div style={{ overflowX: 'auto', maxHeight: 300 }}>
                <table className="data-table">
                  <thead style={{ position: 'sticky', top: 0, backgroundColor: '#fff', zIndex: 10 }}>
                    <tr>
                      <th>Artefact</th>
                      <th>Type</th>
                      <th>Records</th>
                      <th>Size</th>
                      <th>Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {evidence.map((ev) => (
                      <tr key={ev.hash_id}>
                        <td style={{ color: '#1e293b', fontWeight: 500 }}>{ev.artefact_name}</td>
                        <td><span className="hash-value">{ev.artefact_type}</span></td>
                        <td>{ev.record_count?.toLocaleString()}</td>
                        <td>{ev.byte_size ? `${(ev.byte_size / 1024).toFixed(1)} KB` : '—'}</td>
                        <td>{new Date(ev.created_at).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>              )}
            </div>

            {/* Saved Evidence Vault Table */}
            <div className="glass-card-static animate-in animate-in-delay-4" style={{ flex: 1, marginTop: 24 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-muted)' }}>
                  SAVED EVIDENCE VAULT (PINNED SEQUENCES)
                </h3>
              </div>

              {evidenceCards.length === 0 ? (
                <div className="empty-state" style={{ padding: 36 }}>
                  <Package size={40} className="empty-state-glyph" />
                  <h3>No Pinned Sequences</h3>
                  <p>Pin events in the Timeline Flow and save them to the Vault.</p>
                </div>
              ) : (
                <div style={{ overflowX: 'auto', maxHeight: 300 }}>
                  <table className="data-table">
                    <thead style={{ position: 'sticky', top: 0, backgroundColor: '#fff', zIndex: 10 }}>
                      <tr>
                        <th>Title</th>
                        <th>Description</th>
                        <th>Events</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {evidenceCards.map((card) => (
                        <tr key={card.id}>
                          <td style={{ color: '#1e293b', fontWeight: 600 }}>{card.title}</td>
                          <td style={{ color: 'var(--text-muted)', fontSize: 13 }}>{card.description || '—'}</td>
                          <td><span className="hash-value">{(card.evidence_ref?.pointers?.length || 0).toLocaleString()} events</span></td>
                          <td>
                            <button
                              className="btn btn-primary btn-sm"
                              style={{ fontSize: 12, padding: '4px 10px', display: 'flex', alignItems: 'center' }}
                              onClick={() => window.location.href = `/cases/${id}/timeline?card=${card.id}`}
                            >
                              Timeline View
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Generated Reports Table */}
          <div className="glass-card-static animate-in animate-in-delay-4" style={{ flex: 1, marginTop: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-muted)' }}>
                GENERATED EXPORTS & REPORTS
              </h3>
            </div>

            {exportsList.length === 0 ? (
              <div className="empty-state" style={{ padding: 36 }}>
                <FolderPlus size={40} className="empty-state-glyph" />
                <h3>No Reports Generated</h3>
                <p>Use the Ghost Writer in the Case Editor to generate PDFs and HTML reports.</p>
              </div>
            ) : (
              <div style={{ overflowX: 'auto', maxHeight: 300 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px', padding: '8px 12px', background: '#f8fafc', borderRadius: '6px', border: '1px solid #e2e8f0' }}>                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>                    <input type="checkbox" checked={selectedExports.length === exportsList.length && exportsList.length > 0} onChange={handleSelectAllExports} style={{ cursor: 'pointer' }} />
                    <span style={{ fontSize: '13px', fontWeight: 500, color: '#334155' }}>Select All</span>
                  </div>
                  {selectedExports.length > 0 && (
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      <span style={{ fontSize: '13px', color: '#64748b', marginRight: '8px' }}>{selectedExports.length} selected</span>
                      <button onClick={handleBulkDownloadExports} className="btn btn-sm" style={{ backgroundColor: '#2563eb', color: 'white', padding: '4px 10px', fontSize: 12, display: 'flex', gap: 4, alignItems: 'center', border: 'none' }}>
                        <Download size={14} /> Download
                      </button>
                      <button onClick={handleBulkDeleteExports} className="btn btn-sm" style={{ border: '1px solid #dc2626', backgroundColor: '#fef2f2', color: '#dc2626', padding: '4px 10px', fontSize: 12, display: 'flex', gap: 4, alignItems: 'center' }}>
                         Delete
                      </button>
                    </div>
                  )}
                </div>
                <table className="data-table">
                  <thead style={{ position: 'sticky', top: 0, backgroundColor: '#fff', zIndex: 10 }}>
                    <tr>
                      <th style={{ width: '40px' }}></th>
                      <th>Filename</th>
                      <th>Format</th>
                      <th>Size</th>
                      <th>Created</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {exportsList.map((exp) => (
                      <tr key={exp.filename} style={selectedExports.includes(exp.filename) ? { backgroundColor: '#eff6ff' } : {}}>
                        <td>
                          <input type="checkbox" checked={selectedExports.includes(exp.filename)} onChange={() => handleSelectExport(exp.filename)} style={{ cursor: 'pointer' }} />
                        </td>
                        <td style={{ color: '#1e293b', fontWeight: 500, fontSize: '0.8rem' }}>{exp.filename}</td>
                        <td><span className="hash-value">{exp.format.toUpperCase()}</span></td>
                        <td style={{ fontSize: '0.8rem' }}>{(exp.size_bytes / 1024).toFixed(1)} KB</td>
                        <td style={{ fontSize: '0.8rem' }}>{new Date(exp.modified_at * 1000).toLocaleString()}</td>
                        <td>
                          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                            <a 
                              href={`/api/v4/studio/cases/${id}/exports/download/${exp.filename}`} 
                              target="_blank" 
                              rel="noreferrer" 
                              className="btn btn-sm" 
                              style={{ backgroundColor: '#2563eb', color: 'white', padding: '4px 10px', fontSize: 12, display: 'flex', gap: 4, alignItems: 'center', textDecoration: 'none' }}
                            >
                              <Download size={14} /> Download
                            </a>
                            <button 
                              onClick={() => handleDeleteExport(exp.filename)} 
                              className="btn btn-sm" 
                              style={{ border: '1px solid #dc2626', backgroundColor: '#fef2f2', color: '#dc2626', padding: '4px 10px', fontSize: 12, display: 'flex', gap: 4, alignItems: 'center' }}
                            >
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

        </div>

        {/* Right Column: Playbook UI & CoC Ledger */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {/* Playbook Orchestrator */}
          <div className="glass-card-static flex flex-col">
            <h3 style={{ fontSize: 14, fontWeight: 600, color: '#0f172a', marginBottom: 6, display: 'flex', gap: 8, alignItems: 'center' }}>
              <PlayCircle size={16} className="text-blue-500" /> Playbook Orchestrator
            </h3>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
              Execute 1-click execution sequences to hydrate the DuckDB analytical vault schemas synchronously.
            </p>
            
            <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
              {Object.keys(PLAYBOOKS).map(k => (
                <button 
                  key={k} 
                  onClick={() => runPlaybook(k)} 
                  disabled={isRunningRef.current}
                  className="btn btn-sm"
                  style={{ flex: 1, justifyContent: 'center', backgroundColor: isRunningRef.current && activePlaybook?.id !== k ? '#e2e8f0' : PLAYBOOKS[k].color, color: '#fff', border: 'none', opacity: isRunningRef.current && activePlaybook?.id !== k ? 0.5 : 1 }}
                >
                  {isRunningRef.current && activePlaybook?.id === k ? <Loader2 className="animate-spin" size={14} /> : null}
                  {PLAYBOOKS[k].label}
                </button>
              ))}
            </div>

            {/* Dependency Graph Visualizer */}
            {activePlaybook && (
              <div style={{ backgroundColor: '#f8fafc', borderRadius: 8, padding: 16, border: '1px solid #e2e8f0' }}>
                <h4 style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 12 }}>
                  Execution Graph
                </h4>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 4px', alignItems: 'center' }}>
                  {activePlaybook.modules.map((mod, i) => {
                    const st = moduleStatus[mod] || 'pending';
                    return (
                      <React.Fragment key={mod}>
                        <div style={{
                          padding: '6px 12px', borderRadius: 20, fontSize: 12, fontWeight: 500, display: 'flex', gap: 6, alignItems: 'center',
                          backgroundColor: st === 'running' ? '#dbeafe' : st === 'completed' ? '#dcfce7' : st === 'error' ? '#fee2e2' : '#fff',
                          color: st === 'running' ? '#1d4ed8' : st === 'completed' ? '#15803d' : st === 'error' ? '#b91c1c' : '#64748b',
                          border: `1px solid ${st === 'running' ? '#bfdbfe' : st === 'completed' ? '#bbf7d0' : st === 'error' ? '#fecaca' : '#e2e8f0'}`
                        }}>
                          {st === 'running' && <Loader2 size={14} className="animate-spin" />}
                          {st === 'completed' && <CheckCircle2 size={14} />}
                          {st === 'error' && <ShieldAlert size={14} />}
                          {mod.toUpperCase()}
                        </div>
                        {i < activePlaybook.modules.length - 1 && (
                          <div style={{ width: 16, height: 2, backgroundColor: st === 'completed' ? '#22c55e' : '#cbd5e1' }} />
                        )}
                      </React.Fragment>
                    )
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Live CoC Ledger Feed */}
          <div className="glass-card-static" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <h3 style={{ fontSize: 14, fontWeight: 600, color: '#0f172a', marginBottom: 12, display: 'flex', gap: 8, alignItems: 'center' }}>
              <Link2 size={16} className="text-slate-500" /> Live Chain of Custody
            </h3>
            <div style={{ overflowY: 'auto', flex: 1, paddingRight: 4 }}>
              {cocFeed.length === 0 ? (
                <p style={{ fontSize: 12, color: "var(--text-muted)" }}>Ledger is empty.</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {cocFeed.slice(0, 10).map((event, idx) => (
                    <div key={idx} style={{ paddingLeft: 12, borderLeft: '2px solid #3b82f6', fontSize: 12 }}>
                      <div style={{ fontWeight: 600, color: '#1e293b' }}>{event.action}</div>
                      <div style={{ color: '#64748b', marginTop: 2 }}>{event.target_artefact}</div>
                      <div style={{ color: '#94a3b8', fontSize: 11, marginTop: 4, fontFamily: 'monospace' }}>
                        {new Date(event.timestamp).toLocaleTimeString()} · {event.hash_after?.slice(0, 12)}
                      </div>
                    </div>
                  ))}
                  {cocFeed.length > 10 && (
                    <div style={{ fontSize: 11, color: '#94a3b8', textAlign: 'center', marginTop: 4 }}>
                      + {cocFeed.length - 10} earlier events
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
