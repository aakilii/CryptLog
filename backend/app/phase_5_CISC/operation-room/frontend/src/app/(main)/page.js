'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { AlertTriangle, FolderOpen, LockOpen, Plus, ShieldCheck, Download, Trash } from 'lucide-react';
import { api } from '@operation-room/lib/api';
import StatsCard from '@operation-room/components/StatsCard';
import CaseCard from '@operation-room/components/CaseCard';

export default function Dashboard() {
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCases, setSelectedCases] = useState([]);

  const fetchCases = () => {
    setLoading(true);
    api.listCases()
      .then(setCases)
      .catch(() => setCases([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchCases();
  }, []);

  const handleDeleteCase = async (caseId) => {
    if (!confirm('Are you sure you want to permanently delete this case? This cannot be undone.')) return;
    try {
      await api.deleteCase(caseId);
      setCases(cases.filter((c) => c.case_id !== caseId));
      setSelectedCases(selectedCases.filter(id => id !== caseId));
    } catch (e) {
      alert("Failed to delete case: " + e.message);
    }
  };

  const handleSelectCase = (caseId) => {
    if (selectedCases.includes(caseId)) {
      setSelectedCases(selectedCases.filter(id => id !== caseId));
    } else {
      setSelectedCases([...selectedCases, caseId]);
    }
  };

  const handleSelectAll = (e) => {
    if (e.target.checked) {
      setSelectedCases(cases.map(c => c.case_id));
    } else {
      setSelectedCases([]);
    }
  };

  const handleBulkDelete = async () => {
    if (!confirm(`Are you sure you want to permanently delete ${selectedCases.length} cases? This cannot be undone.`)) return;
    try {
      for (const caseId of selectedCases) {
        await api.deleteCase(caseId);
      }
      setCases(cases.filter(c => !selectedCases.includes(c.case_id)));
      setSelectedCases([]);
    } catch (e) {
      alert("Failed to bulk delete cases: " + e.message);
    }
  };

  const handleBulkDownload = async () => {
    if (!confirm(`Generate and download reports for ${selectedCases.length} cases? This may take a moment per case.`)) return;
    
    for (const caseId of selectedCases) {
       try {
         const docsResp = await api.get(`/v4/studio/cases/${caseId}/docs`);
         const docs = Array.isArray(docsResp) ? docsResp : docsResp?.documents || [];
         if (!docs || docs.length === 0) continue;
         
         const docId = docs[0].doc_id;
         
         const result = await api.post(`/v4/studio/cases/${caseId}/exports/pdf`, {
            doc_id: docId,
            actor: 'investigator',
            frontend_url: window.location.origin,
            focus_mode: 'Story'
         });
         
         if (result?.url) {
            window.open(result.url, '_blank');
         }
       } catch (err) {
         console.error(`Failed PDF export for case ${caseId}`, err);
       }
    }
  };

  const openCases     = cases.filter((c) => c.status === 'OPEN' || c.status === 'IN_PROGRESS');
  const criticalCases = cases.filter((c) => c.priority === 'CRITICAL');
  const totalEvidence  = cases.reduce((sum, c) => sum + (c.evidence_count || 0), 0);

  return (
    <>
      <div className="page-header animate-in">
        <div>
          <h1>Investigation Dashboard</h1>
          <p>Case management &amp; evidence preservation overview</p>
        </div>
        <Link href="/cases/new" className="btn btn-primary btn-lg">
          <Plus size={16} /> New Case
        </Link>
      </div>

      <div className="stats-grid">
        <StatsCard icon={FolderOpen} iconClass="case" value={cases.length} label="Total Cases" delay={1} />
        <StatsCard icon={LockOpen} iconClass="open" value={openCases.length} label="Open / Active" delay={2} />
        <StatsCard icon={AlertTriangle} iconClass="critical" value={criticalCases.length} label="Critical" delay={3} />
        <StatsCard icon={ShieldCheck} iconClass="evidence" value={totalEvidence} label="Evidence Artefacts" delay={4} />
      </div>

      {loading ? (
        <div className="loading-overlay">
          <div className="spinner" />
          <span>Loading cases…</span>
        </div>
      ) : cases.length === 0 ? (
        <div className="glass-card-static empty-state animate-in">
          <ShieldCheck size={42} className="empty-state-glyph" />
          <h3>No Cases Yet</h3>
          <p>
            Start your first forensic investigation by creating a new case.
            Evidence will be cryptographically hashed and chain‑of‑custody
            tracked from the moment of collection.
          </p>
          <Link href="/cases/new" className="btn btn-primary">
            <Plus size={15} /> Create First Case
          </Link>
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between mb-4 glass-card p-3 animate-in fade-in slide-in-from-bottom-2 duration-500">
            <div className="flex items-center gap-2">
              <input 
                type="checkbox" 
                checked={selectedCases.length === cases.length && cases.length > 0} 
                onChange={handleSelectAll} 
                className="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500 cursor-pointer"
                id="select-all"
              />
              <label htmlFor="select-all" className="text-sm font-medium text-slate-700 dark:text-slate-300 cursor-pointer">
                Select All
              </label>
            </div>
            {selectedCases.length > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-sm text-slate-500 font-medium mr-2">
                  {selectedCases.length} selected
                </span>
                <button onClick={handleBulkDownload} className="btn bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 dark:text-slate-300 dark:border-slate-700">
                  <Download size={14} /> Download PDF
                </button>
                <button onClick={handleBulkDelete} className="btn bg-red-50 hover:bg-red-100 text-red-600 border border-red-200 dark:bg-red-900/20 dark:hover:bg-red-900/40 dark:text-red-400 dark:border-red-900/50">
                  <Trash size={14} /> Delete
                </button>
              </div>
            )}
          </div>
          <div className="cases-grid">
            {cases.map((c, i) => (
              <div key={c.case_id} className={`animate-in animate-in-delay-${(i % 4) + 1}`}>
                <CaseCard 
                  c={c} 
                  onDelete={handleDeleteCase} 
                  isSelected={selectedCases.includes(c.case_id)}
                  onSelect={handleSelectCase}
                />
              </div>
            ))}
          </div>
        </>
      )}
    </>
  );
}
