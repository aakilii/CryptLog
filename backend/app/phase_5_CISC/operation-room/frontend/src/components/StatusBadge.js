const PRIORITY_VALUES = new Set(['critical', 'high', 'medium', 'low']);

const normalize = (value) => (value || 'unknown').toLowerCase().replace(/_/g, '-');

const inferType = (normalized, explicitType) => {
  if (explicitType) return explicitType;
  return PRIORITY_VALUES.has(normalized) ? 'priority' : 'status';
};

const toLabel = (normalized) =>
  normalized
    .split('-')
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(' ');

export default function StatusBadge({ type, value }) {
  const normalized = normalize(value);
  const badgeType = inferType(normalized, type);
  const cls = `badge badge-kind-${badgeType} badge-${normalized}`;

  return <span className={cls}>{toLabel(normalized)}</span>;
}
