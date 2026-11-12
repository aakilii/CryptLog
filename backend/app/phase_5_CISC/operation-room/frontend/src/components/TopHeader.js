'use client';
import { usePathname, useRouter } from 'next/navigation';
import { ArrowLeft, ShieldCheck, UserRound } from 'lucide-react';

const PAGE_TITLES = {
  '/': { title: 'Main Dashboard', subtitle: 'National Forensic Log Intelligence Platform' },
  '/cases/new': { title: 'Create New Case', subtitle: 'Case Initialization & Evidence Preservation' },
};

function normalizePathname(pathname) {
  if (pathname.startsWith('/operation-room')) {
    const rest = pathname.slice('/operation-room'.length);
    if (!rest || rest === '') return '/';
    return rest.startsWith('/') ? rest : `/${rest}`;
  }
  return pathname;
}

function getPageInfo(pathname) {
  const p = normalizePathname(pathname);
  if (PAGE_TITLES[p]) return PAGE_TITLES[p];
  if (p.includes('/timeline'))    return { title: 'Timeline Reconstruction', subtitle: 'Unified Event Timeline Analysis' };
  if (p.includes('/anomalies'))   return { title: 'Anomaly Detection', subtitle: 'Explainable AI · IF, LOF, Ensemble, DistilBERT' };
  if (p.includes('/correlation')) return { title: 'Correlation & Root-Cause', subtitle: 'Entity Graph · MITRE ATT&CK Mapping' };
  if (p.includes('/crud'))        return { title: 'CRUD & Data-Access', subtitle: 'Operation Classification & Sensitivity Analysis' };
  if (p.includes('/exfiltration')) return { title: 'Data Exfiltration Intelligence', subtitle: '9-Engine Pipeline · Behaviour Graphs · Intent-Aware Detection' };
  if (p.includes('/network'))     return { title: 'Network & Exfiltration', subtitle: 'Flow Analysis · Threat Intelligence · Exfil Detection' };
  if (p.includes('/depth'))       return { title: 'Depth & Impact', subtitle: '4D Penetration Assessment · Business Impact' };
  if (p.includes('/studio-v4'))   return { title: 'Report Studio V4', subtitle: 'Canva-style Forensic Workspace · Evidence-Bound Editing' };
  if (p.includes('/cases/'))      return { title: 'Case Dashboard', subtitle: 'Evidence & Chain-of-Custody Management' };
  return { title: 'SAKSHI LEDGER', subtitle: 'National Forensic Log Intelligence Platform' };
}

export default function TopHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const { title, subtitle } = getPageInfo(pathname);

  return (
    <div className="top-header">
      <div>
        <div className="top-header-title">{title}</div>
        <div className="top-header-subtitle">{subtitle}</div>
      </div>
      <div className="top-header-right">
        <span className="session-badge">
          <ShieldCheck size={13} />
          Session Active
        </span>
        <span className="header-user-pill">
          <UserRound size={13} />
          Investigator
        </span>
        <button
          className="btn btn-sm"
          style={{ backgroundColor: '#2563eb', color: '#fff', border: 'none', borderRadius: '6px', padding: '6px 14px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 500, fontSize: '13px' }}
          onClick={() => router.push('/')}
        >
          <ArrowLeft size={13} />
          Main Dashboard
        </button>
      </div>
    </div>
  );
}
