/**
 * History Tab - Report version history and diff viewer
 */

'use client';

import { useInvestigationStore } from '@operation-room/stores/investigationStore';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';

type DiffPayload = {
    version_from?: string;
    version_to?: string;
    changes?: unknown[];
    alignment_delta?: number;
    completeness_delta?: number;
    sections_added?: string[];
    sections_removed?: string[];
    sections_modified?: string[];
};

function getTimeAgo(timestamp: string) {
    const now = new Date();
    const then = new Date(timestamp);
    const seconds = Math.floor((now.getTime() - then.getTime()) / 1000);

    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
}

function formatChange(change: unknown, index: number): string {
    if (typeof change === 'string') {
        return change;
    }

    if (change && typeof change === 'object') {
        const value = change as Record<string, unknown>;
        const changeType = typeof value.change_type === 'string' ? value.change_type : 'updated';
        const target = typeof value.target_element === 'string' ? value.target_element : 'report';
        return `${changeType.replace(/_/g, ' ')}: ${target}`;
    }

    return `Change ${index + 1}`;
}

export default function HistoryTab() {
    const params = useParams();
    const caseId = params?.id as string || '';

    const {
        versions,
        reportDocumentId,
        setVersions,
        setReportDocumentId,
        setActiveTab,
    } = useInvestigationStore();

    const [selectedVersions, setSelectedVersions] = useState<string[]>([]);
    const [viewMode, setViewMode] = useState<'list' | 'diff'>('list');
    const [diffData, setDiffData] = useState<DiffPayload | null>(null);
    const [isLoadingVersions, setIsLoadingVersions] = useState(false);
    const [isLoadingDiff, setIsLoadingDiff] = useState(false);
    const [isRollingBack, setIsRollingBack] = useState(false);
    const [statusMessage, setStatusMessage] = useState('');

    const inferredDocId = useMemo(() => {
        for (const version of versions) {
            if (version.document_id) {
                return version.document_id;
            }
            if (version.report_id) {
                return version.report_id;
            }
        }
        return null;
    }, [versions]);

    const effectiveDocId = reportDocumentId || inferredDocId;

    useEffect(() => {
        if (!reportDocumentId && inferredDocId) {
            setReportDocumentId(inferredDocId);
        }
    }, [reportDocumentId, inferredDocId, setReportDocumentId]);

    const refreshVersions = useCallback(async () => {
        if (!caseId || !effectiveDocId) {
            return;
        }

        setIsLoadingVersions(true);
        setStatusMessage('');

        try {
            const response = await fetch(`/api/deep-research/cases/${caseId}/reports/${effectiveDocId}/versions?limit=100`);
            if (!response.ok) {
                throw new Error(`Failed to load versions (${response.status})`);
            }

            const data = await response.json();
            if (Array.isArray(data.versions)) {
                setVersions(data.versions);
            }
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Unknown error';
            setStatusMessage(`❌ ${message}`);
        } finally {
            setIsLoadingVersions(false);
        }
    }, [caseId, effectiveDocId, setVersions]);

    useEffect(() => {
        if (effectiveDocId) {
            refreshVersions();
        }
    }, [effectiveDocId, refreshVersions]);

    const toggleVersionSelection = (versionId: string) => {
        setSelectedVersions((current) => {
            if (current.includes(versionId)) {
                return current.filter((id) => id !== versionId);
            }
            if (current.length >= 2) {
                return [current[1], versionId];
            }
            return [...current, versionId];
        });
    };

    const compareSelectedVersions = async () => {
        if (!caseId || !effectiveDocId || selectedVersions.length !== 2) {
            return;
        }

        const [v1, v2] = selectedVersions;
        setIsLoadingDiff(true);
        setStatusMessage('');

        try {
            const response = await fetch(
                `/api/deep-research/cases/${caseId}/reports/${effectiveDocId}/diff?v1=${encodeURIComponent(v1)}&v2=${encodeURIComponent(v2)}`
            );
            if (!response.ok) {
                throw new Error(`Failed to compare versions (${response.status})`);
            }

            const data = await response.json();
            setDiffData(data);
            setViewMode('diff');
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Unknown error';
            setStatusMessage(`❌ ${message}`);
        } finally {
            setIsLoadingDiff(false);
        }
    };

    const handleRollback = async (versionId: string) => {
        if (!caseId || !effectiveDocId || isRollingBack) {
            return;
        }

        const confirmed = window.confirm(`Rollback report to ${versionId}? This creates a new version.`);
        if (!confirmed) {
            return;
        }

        setIsRollingBack(true);
        setStatusMessage('');

        try {
            const response = await fetch(`/api/deep-research/cases/${caseId}/reports/${effectiveDocId}/rollback/${versionId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    reason: `Rollback requested from history tab to ${versionId}`,
                    created_by: 'investigator',
                }),
            });

            if (!response.ok) {
                throw new Error(`Rollback failed (${response.status})`);
            }

            const payload = await response.json();
            setStatusMessage(`✅ Rolled back. New version: ${payload.new_version_id}`);
            setViewMode('list');
            setDiffData(null);
            setSelectedVersions([]);
            await refreshVersions();
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Unknown error';
            setStatusMessage(`❌ ${message}`);
        } finally {
            setIsRollingBack(false);
        }
    };

    if (!effectiveDocId && versions.length === 0) {
        return (
            <div className="h-full flex items-center justify-center bg-gray-50 p-8">
                <div className="text-center">
                    <div className="text-6xl mb-4">🕐</div>
                    <h3 className="text-lg font-semibold text-gray-800 mb-2">
                        No Version History Yet
                    </h3>
                    <p className="text-gray-600 max-w-md mb-4">
                        Save the report to the case first. Then version history and diffs will appear here.
                    </p>
                    <button
                        onClick={() => setActiveTab('report')}
                        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                    >
                        Go To Report Tab
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col bg-gray-50">
            <div className="bg-white border-b border-gray-200 p-6">
                <div className="flex items-center justify-between mb-3">
                    <div>
                        <h3 className="text-lg font-semibold text-gray-800 mb-1">Version History</h3>
                        <div className="text-sm text-gray-600">
                            {versions.length} version{versions.length === 1 ? '' : 's'}
                            {effectiveDocId && <span> • Doc {effectiveDocId.slice(0, 10)}...</span>}
                        </div>
                    </div>

                    <div className="flex items-center gap-2">
                        <button
                            onClick={refreshVersions}
                            disabled={isLoadingVersions || !effectiveDocId}
                            className="px-3 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-sm"
                        >
                            {isLoadingVersions ? '⏳ Refreshing...' : '🔄 Refresh'}
                        </button>
                        {selectedVersions.length === 2 && viewMode === 'list' && (
                            <button
                                onClick={compareSelectedVersions}
                                disabled={isLoadingDiff}
                                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
                            >
                                {isLoadingDiff ? '⏳ Comparing...' : '🔍 Compare Versions'}
                            </button>
                        )}
                        {viewMode === 'diff' && (
                            <button
                                onClick={() => setViewMode('list')}
                                className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-sm"
                            >
                                ← Back To List
                            </button>
                        )}
                    </div>
                </div>

                {statusMessage && (
                    <div className={`text-sm ${statusMessage.includes('✅') ? 'text-green-600' : 'text-red-600'}`}>
                        {statusMessage}
                    </div>
                )}
            </div>

            <div className="flex-1 overflow-y-auto">
                {viewMode === 'list' ? (
                    <div className="p-6">
                        <div className="space-y-4">
                            {versions.map((version, index) => {
                                const isSelected = selectedVersions.includes(version.version_id);
                                const isLatest = index === 0;

                                const alignment = version.quality_metrics?.alignment_score
                                    ?? version.alignment_score
                                    ?? 0;
                                const completeness = version.quality_metrics?.completeness_score
                                    ?? version.completeness_score
                                    ?? 0;

                                const changes = Array.isArray(version.changes) ? version.changes : [];

                                return (
                                    <div
                                        key={version.version_id}
                                        className={`bg-white rounded-lg border-2 p-4 transition-all ${isSelected
                                                ? 'border-blue-400 shadow-md'
                                                : 'border-gray-200 hover:border-gray-300'
                                            }`}
                                    >
                                        <div className="flex items-start justify-between mb-3">
                                            <div className="flex-1">
                                                <div className="flex items-center gap-2 mb-1">
                                                    <span className="font-mono text-sm font-semibold text-gray-800">
                                                        {version.version_id}
                                                    </span>
                                                    {isLatest && (
                                                        <span className="text-xs px-2 py-0.5 bg-green-100 text-green-800 rounded-full font-medium border border-green-300">
                                                            LATEST
                                                        </span>
                                                    )}
                                                    {version.branch && version.branch !== 'main' && (
                                                        <span className="text-xs px-2 py-0.5 bg-purple-100 text-purple-800 rounded-full font-medium border border-purple-300">
                                                            {version.branch}
                                                        </span>
                                                    )}
                                                </div>
                                                <div className="font-medium text-gray-700 mb-1">
                                                    {version.commit_message || version.message || 'Version checkpoint'}
                                                </div>
                                                <div className="text-sm text-gray-500">
                                                    {version.created_by} • {getTimeAgo(version.created_at)}
                                                </div>
                                            </div>

                                            <input
                                                type="checkbox"
                                                checked={isSelected}
                                                onChange={() => toggleVersionSelection(version.version_id)}
                                                className="w-5 h-5 text-blue-600 rounded focus:ring-2 focus:ring-blue-500"
                                            />
                                        </div>

                                        <div className="mb-3">
                                            <div className="text-xs font-semibold text-gray-700 mb-2">
                                                Changes ({changes.length})
                                            </div>
                                            <div className="space-y-1">
                                                {changes.slice(0, 3).map((change, changeIndex) => (
                                                    <div key={`${version.version_id}-change-${changeIndex}`} className="text-sm text-gray-600 flex items-center gap-2">
                                                        <span className="text-green-600">+</span>
                                                        <span>{formatChange(change, changeIndex)}</span>
                                                    </div>
                                                ))}
                                                {changes.length > 3 && (
                                                    <div className="text-xs text-gray-500">
                                                        +{changes.length - 3} more changes
                                                    </div>
                                                )}
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-2 gap-3 pt-3 border-t border-gray-200">
                                            <div>
                                                <div className="text-xs text-gray-600 mb-1">Alignment</div>
                                                <div className="flex items-center gap-2">
                                                    <div className="flex-1 bg-gray-200 rounded-full h-1.5">
                                                        <div className="h-1.5 rounded-full bg-green-500" style={{ width: `${Math.round(alignment * 100)}%` }} />
                                                    </div>
                                                    <span className="text-xs font-semibold text-gray-800">
                                                        {Math.round(alignment * 100)}%
                                                    </span>
                                                </div>
                                            </div>
                                            <div>
                                                <div className="text-xs text-gray-600 mb-1">Completeness</div>
                                                <div className="flex items-center gap-2">
                                                    <div className="flex-1 bg-gray-200 rounded-full h-1.5">
                                                        <div className="h-1.5 rounded-full bg-blue-500" style={{ width: `${Math.round(completeness * 100)}%` }} />
                                                    </div>
                                                    <span className="text-xs font-semibold text-gray-800">
                                                        {Math.round(completeness * 100)}%
                                                    </span>
                                                </div>
                                            </div>
                                        </div>

                                        <div className="flex gap-2 mt-3 pt-3 border-t border-gray-200">
                                            <button
                                                onClick={() => toggleVersionSelection(version.version_id)}
                                                className="text-xs px-3 py-1.5 bg-blue-50 text-blue-700 rounded hover:bg-blue-100 transition-colors font-medium"
                                            >
                                                {isSelected ? 'Unselect' : 'Select'}
                                            </button>
                                            <button
                                                onClick={() => handleRollback(version.version_id)}
                                                disabled={isRollingBack}
                                                className="text-xs px-3 py-1.5 bg-gray-50 text-gray-700 rounded hover:bg-gray-100 transition-colors font-medium disabled:opacity-60"
                                            >
                                                ↩️ Rollback
                                            </button>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                ) : (
                    <div className="p-6">
                        <div className="bg-white rounded-lg border border-gray-200 p-6">
                            <div className="mb-6">
                                <h4 className="font-semibold text-gray-700 mb-4">Version Comparison</h4>
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                                        <div className="text-xs text-red-700 mb-1">Old Version</div>
                                        <div className="font-mono text-sm font-semibold text-red-900">
                                            {diffData?.version_from || selectedVersions[0] || 'N/A'}
                                        </div>
                                    </div>
                                    <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                                        <div className="text-xs text-green-700 mb-1">New Version</div>
                                        <div className="font-mono text-sm font-semibold text-green-900">
                                            {diffData?.version_to || selectedVersions[1] || 'N/A'}
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div className="space-y-4">
                                <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                                    <div className="font-semibold text-gray-700 mb-3">Diff Summary</div>
                                    <div className="space-y-2 text-sm text-gray-700">
                                        <div>Sections added: {(diffData?.sections_added || []).length}</div>
                                        <div>Sections removed: {(diffData?.sections_removed || []).length}</div>
                                        <div>Sections modified: {(diffData?.sections_modified || []).length}</div>
                                        <div>Alignment delta: {Math.round((diffData?.alignment_delta || 0) * 100)}%</div>
                                        <div>Completeness delta: {Math.round((diffData?.completeness_delta || 0) * 100)}%</div>
                                    </div>
                                </div>

                                <div className="bg-white rounded-lg border border-gray-200 p-4">
                                    <div className="font-semibold text-gray-700 mb-3">Changed Elements</div>
                                    <div className="space-y-2 max-h-80 overflow-y-auto text-sm">
                                        {(diffData?.changes || []).length === 0 ? (
                                            <div className="text-gray-500">No detailed changes returned for this diff.</div>
                                        ) : (
                                            (diffData?.changes || []).map((change, index) => (
                                                <div key={`diff-change-${index}`} className="text-gray-700 flex items-start gap-2">
                                                    <span className="text-blue-600">•</span>
                                                    <span>{formatChange(change, index)}</span>
                                                </div>
                                            ))
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}