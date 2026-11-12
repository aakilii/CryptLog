import Link from 'next/link';                                                   
import { ArrowUpRight, Clock3, FolderArchive, UserRound, Trash2 } from 'lucide-react';
import StatusBadge from './StatusBadge';

export default function CaseCard({ c, onDelete, isSelected, onSelect }) {
  const priorityClass = `priority-${(c.priority || 'medium').toLowerCase()}`;
  const createdOn = c.created_at ? new Date(c.created_at).toLocaleDateString() : '—';

  const handleDelete = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (onDelete) {
      onDelete(c.case_id);
    }
  };

  const handleSelect = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (onSelect) {
      onSelect(c.case_id);
    }
  };

  return (
    <Link href={`/cases/${c.case_id}`} className="case-card-link">
      <div className={`glass-card case-card ${priorityClass} ${isSelected ? 'ring-2 ring-sky-500 bg-sky-50/50 dark:bg-sky-900/20' : ''}`}>
        <div className="case-card-header flex items-start gap-2">
          {onSelect && (
            <input 
              type="checkbox" 
              checked={isSelected || false} 
              onChange={handleSelect} 
              onClick={(e) => e.stopPropagation()}
              className="mt-1 h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500 cursor-pointer"
            />
          )}
          <span className="case-card-title flex-1">{c.title}</span>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>   
            <button
              onClick={handleDelete}
              title="Delete Case"
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444', padding: '4px' }}
            >
              <Trash2 size={15} />
            </button>
            <ArrowUpRight size={15} className="case-card-open-indicator" />     
          </div>
        </div>
        <div className="case-card-badges mt-2">
          <StatusBadge type="status" value={c.status} />
          <StatusBadge type="priority" value={c.priority} />
        </div>

        <div className="case-card-meta">
          <span>
            <UserRound size={14} />
            {c.lead_investigator || 'investigator'}
          </span>
          <span>
            <FolderArchive size={14} />
            {c.evidence_count ?? 0} artefacts
          </span>
          <span>
            <Clock3 size={14} />
            {createdOn}
          </span>
        </div>
      </div>
    </Link>
  );
}
