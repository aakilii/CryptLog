'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  AlertTriangle,
  Clock3,
  Compass,
  Database,
  Flame,
  GitBranch,
  Globe2,
  Home,
  Plus,
  ScanSearch,
} from 'lucide-react';

const orHome =
  typeof process !== 'undefined' && process.env.NEXT_PUBLIC_OR_OPERATION_HOME
    ? process.env.NEXT_PUBLIC_OR_OPERATION_HOME
    : '/';

const MAIN_NAV_ITEMS = [
  {
    href: orHome,
    icon: Home,
    label: 'Main Dashboard',
    module: 'case',
    isActive: (pathname) =>
      pathname === orHome || (orHome === '/' && pathname === '/') || pathname === '/operation-room',
  },
  { href: '/cases/new', icon: Plus, label: 'New Case', module: 'case', isActive: (pathname) => pathname === '/cases/new' },
];

const INVESTIGATION_ITEMS = [
  {
    key: 'timeline',
    icon: Clock3,
    label: 'Timeline Recon',
    module: 'timeline',
    path: (caseId) => `/cases/${caseId}/timeline`,
    isActive: (pathname) => pathname.includes('/timeline'),
  },
  {
    key: 'anomalies',
    icon: AlertTriangle,
    label: 'Anomaly Detection',
    module: 'anomaly',
    path: (caseId) => `/cases/${caseId}/anomalies`,
    isActive: (pathname) => pathname.includes('/anomalies'),
  },
  {
    key: 'correlation',
    icon: GitBranch,
    label: 'Correlation & RCA',
    module: 'correlation',
    path: (caseId) => `/cases/${caseId}/correlation`,
    isActive: (pathname) => pathname.includes('/correlation'),
  },
  {
    key: 'crud',
    icon: Database,
    label: 'CRUD Analysis',
    module: 'crud',
    path: (caseId) => `/cases/${caseId}/crud`,
    isActive: (pathname) => pathname.includes('/crud'),
  },
  {
    key: 'network',
    icon: Globe2,
    label: 'Network & Exfil',
    module: 'network',
    path: (caseId) => `/cases/${caseId}/network`,
    isActive: (pathname) => pathname.includes('/network'),
  },
  {
    key: 'exfiltration',
    icon: ScanSearch,
    label: 'Exfil Intelligence',
    module: 'network',
    path: (caseId) => `/cases/${caseId}/exfiltration`,
    isActive: (pathname) => pathname.includes('/exfiltration'),
  },
  {
    key: 'depth',
    icon: Flame,
    label: 'Depth & Impact',
    module: 'depth',
    path: (caseId) => `/cases/${caseId}/depth`,
    isActive: (pathname) => pathname.includes('/depth'),
  },
  {
    key: 'studio-v4',
    icon: Compass,
    label: 'Report Studio V4',
    module: 'case',
    path: (caseId) => `/cases/${caseId}/studio-v4`,
    isActive: (pathname) => pathname.includes('/studio-v4'),
  },
];

const resolveCaseId = (pathname) => {
  const m1 = pathname.match(/^\/cases\/([^/]+)/);
  if (m1) return m1[1];
  const m2 = pathname.match(/^\/operation-room\/cases\/([^/]+)/);
  return m2 ? m2[1] : null;
};

export default function Sidebar() {
  const pathname = usePathname();
  const caseId = resolveCaseId(pathname);

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-brand-logo" aria-hidden>
          <img src="/sakshi-logo.jpg" alt="SAKSHI LEDGER" />
        </div>
        <div>
          <h1>SAKSHI LEDGER</h1>
          <span>Forensic Intelligence</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        <div className="sidebar-section-label">Security Protocol Phases</div>
        {MAIN_NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const active = item.isActive(pathname);
          return (
          <Link
            key={item.href}
            href={item.href}
            className={`${active ? 'active' : ''} module-${item.module}`.trim()}
          >
            <span className="nav-icon"><Icon size={15} /></span>
            {item.label}
            <span className="sidebar-module-dot" aria-hidden="true" />
          </Link>
          );
        })}

        <div className="sidebar-section-label">Investigation Modules</div>
        {INVESTIGATION_ITEMS.map((item, idx) => {
          const enabled = !!caseId;
          const href = enabled ? item.path(caseId) : '#';
          const active = enabled && item.isActive(pathname);
          const Icon = item.icon;

          const sectionBreak = idx === INVESTIGATION_ITEMS.length - 1;

          return (
            <div key={item.key}>
              {sectionBreak && <div className="sidebar-section-label">Reporting Phase</div>}
              <Link
                href={href}
                className={`${active ? 'active ' : ''}${enabled ? '' : 'is-disabled '}module-${item.module}`.trim()}
              >
                <span className="nav-icon"><Icon size={15} /></span>
                {item.label}
                <span className="sidebar-module-dot" aria-hidden="true" />
              </Link>
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
