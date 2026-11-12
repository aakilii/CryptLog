/**
 * Report Tab - Live report generation progress and preview
 */

'use client';

import { useInvestigationStore } from '@operation-room/stores/investigationStore';
import { useParams, useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';

interface Section {
  id: string;
  name: string;
  status: 'pending' | 'writing' | 'complete' | 'error';
  progress: number;
  pageNumbers?: number[];
  wordCount?: number;
  lastUpdated?: string;
}

const toSectionStatus = (status: unknown): Section['status'] => {
  if (status === 'completed' || status === 'complete') {
    return 'complete';
  }
  if (status === 'in_progress' || status === 'writing') {
    return 'writing';
  }
  if (status === 'failed' || status === 'error') {
    return 'error';
  }
  return 'pending';
};

export default function ReportTab() {
  const params = useParams();
  const router = useRouter();
  const caseId = params?.id as string || '';

  const {
    reportProgress,
    versions,
    investigationId,
    findings,
    evidence,
    reportDocumentId,
    setReportDocumentId,
    setReportProgress,
    setVersions,
    addVersion,
  } = useInvestigationStore();

  const [selectedSection, setSelectedSection] = useState<Section | null>(null);
  const [viewMode, setViewMode] = useState<'progress' | 'preview'>('progress');
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');
  const [isLoadingVersions, setIsLoadingVersions] = useState(false);
  const [checkpointMessage, setCheckpointMessage] = useState('AI panel checkpoint');
  const [isCommitting, setIsCommitting] = useState(false);

  const sections: Section[] = useMemo(() => {
    const source = reportProgress?.sections;
    const sectionList = Array.isArray(source)
      ? source
      : (source && typeof source === 'object' ? Object.values(source) : []);

    return sectionList.map((raw: any, index) => {
      const status = toSectionStatus(raw?.status);
      const progress = typeof raw?.progress === 'number'
        ? raw.progress
        : (status === 'complete' ? 100 : 0);

      return {
        id: raw?.id || raw?.section_id || `section-${index + 1}`,
        name: raw?.title || raw?.name || raw?.type || `Section ${index + 1}`,
        status,
        progress,
        pageNumbers: Array.isArray(raw?.pages) ? raw.pages : undefined,
        wordCount: typeof raw?.word_count === 'number' ? raw.word_count : undefined,
        lastUpdated: raw?.updated_at ? new Date(raw.updated_at).toLocaleTimeString() : undefined,
      } as Section;
    });
  }, [reportProgress]);

  const totalSections = sections.length || 1;
  const completedSections = sections.filter((section) => section.status === 'complete').length;
  const overallProgress = reportProgress?.progress ?? (completedSections / totalSections) * 100;
  const currentPage = reportProgress?.current_page || 0;
  const totalPages = reportProgress?.total_pages || sections.length || 0;
  const wordCount = sections.reduce((sum, section) => sum + (section.wordCount || 0), 0);

  const latestVersion = versions[0];
  const alignmentScore = reportProgress?.alignment_score
    ?? latestVersion?.alignment_score
    ?? latestVersion?.quality_metrics?.alignment_score
    ?? 0;
  const completenessScore = reportProgress?.completeness_score
    ?? latestVersion?.completeness_score
    ?? latestVersion?.quality_metrics?.completeness_score
    ?? 0;

  const refreshReportProgress = useCallback(async () => {
    if (!investigationId) {
      return;
    }

    try {
      const response = await fetch(`/api/deep-research/investigations/${investigationId}/report/progress`);
      if (!response.ok) {
        return;
      }

      const data = await response.json();
      setReportProgress(data);
    } catch (error) {
      console.error('Failed to load report progress:', error);
    }
  }, [investigationId, setReportProgress]);

  const refreshVersions = useCallback(async () => {
    if (!caseId || !reportDocumentId) {
      return;
    }

    setIsLoadingVersions(true);
    try {
      const response = await fetch(`/api/deep-research/cases/${caseId}/reports/${reportDocumentId}/versions?limit=50`);
      if (!response.ok) {
        throw new Error(`Failed to load versions (${response.status})`);
      }

      const data = await response.json();
      if (Array.isArray(data.versions)) {
        setVersions(data.versions);
      }
    } catch (error) {
      console.error('Failed to load versions:', error);
    } finally {
      setIsLoadingVersions(false);
    }
  }, [caseId, reportDocumentId, setVersions]);

  useEffect(() => {
    if (!reportProgress && investigationId) {
      refreshReportProgress();
    }
  }, [reportProgress, investigationId, refreshReportProgress]);

  useEffect(() => {
    if (reportDocumentId) {
      refreshVersions();
    }
  }, [reportDocumentId, refreshVersions]);

  const handleSaveToCase = async () => {
    if (!caseId || !investigationId || isSaving) {
      return;
    }

    setIsSaving(true);
    setSaveMessage('');

    try {
      const response = await fetch(`/api/deep-research/cases/${caseId}/report/generate-canvas`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          investigation_id: investigationId,
          findings: findings.map((finding) => ({
            hypothesis_id: finding.hypothesis_id,
            hypothesis_name: finding.hypothesis_name,
            verdict: finding.verdict,
            confidence: finding.confidence ?? finding.confidence_score ?? 0,
            evidence_for: finding.evidence_for || [],
            evidence_against: finding.evidence_against || [],
            summary: finding.summary || '',
            details: finding.details || {},
          })),
          evidence: evidence.map((item) => ({
            evidence_id: item.evidence_id,
            evidence_type: item.evidence_type,
            description: item.description,
            timestamp: item.timestamp,
            source_log: item.source_log,
            hash: item.hash,
            data: item.data || {},
          })),
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to save report (${response.status})`);
      }

      const payload = await response.json();
      if (typeof payload.document_id === 'string' && payload.document_id) {
        setReportDocumentId(payload.document_id);
      }

      setSaveMessage('✅ Report saved to case and linked to version history.');
    } catch (error) {
      console.error('Save failed:', error);
      setSaveMessage('❌ Failed to save report to case.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCreateCheckpoint = async () => {
    if (!caseId || !reportDocumentId || isCommitting) {
      return;
    }

    setIsCommitting(true);
    setSaveMessage('');

    try {
      const response = await fetch(`/api/deep-research/cases/${caseId}/reports/${reportDocumentId}/commit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          commit_message: checkpointMessage.trim() || 'AI panel checkpoint',
          created_by: 'investigator',
        }),
      });

      if (!response.ok) {
        throw new Error(`Commit failed (${response.status})`);
      }

      const payload = await response.json();
      addVersion({
        version_id: payload.version_id,
        document_id: reportDocumentId,
        created_at: payload.created_at || new Date().toISOString(),
        created_by: 'investigator',
        commit_message: checkpointMessage.trim() || 'AI panel checkpoint',
        changes: [],
        alignment_score: payload.alignment_score,
        completeness_score: payload.completeness_score,
      });

      setSaveMessage(`✅ Version ${payload.version_id} created.`);
      await refreshVersions();
    } catch (error) {
      console.error('Version commit failed:', error);
      setSaveMessage('❌ Failed to create version checkpoint.');
    } finally {
      setIsCommitting(false);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'complete': return '✅';
      case 'writing': return '✍️';
      case 'pending': return '⏳';
      case 'error': return '❌';
      default: return '⏳';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'complete': return 'text-green-600';
      case 'writing': return 'text-blue-600';
      case 'pending': return 'text-gray-400';
      case 'error': return 'text-red-600';
      default: return 'text-gray-400';
    }
  };

  if (!reportProgress && sections.length === 0 && versions.length === 0) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-50 p-8">
        <div className="text-center">
          <div className="text-6xl mb-4">📄</div>
          <h3 className="text-lg font-semibold text-gray-800 mb-2">
            No Report Generated Yet
          </h3>
          <p className="text-gray-600 max-w-md">
            Once the investigation plan is approved and executed, report generation progress and checkpoints appear here.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-gray-50">
      <div className="bg-white border-b border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-800 mb-1">
              Forensic Report Generation
            </h3>
            <div className="text-sm text-gray-600">
              {completedSections} of {totalSections} sections complete
              {reportDocumentId && <span> • Doc {reportDocumentId.slice(0, 10)}...</span>}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="flex items-center bg-gray-100 rounded-lg p-1">
              <button
                onClick={() => setViewMode('progress')}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${viewMode === 'progress'
                    ? 'bg-white text-gray-800 shadow-sm'
                    : 'text-gray-600 hover:text-gray-800'
                  }`}
              >
                📊 Progress
              </button>
              <button
                onClick={() => setViewMode('preview')}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${viewMode === 'preview'
                    ? 'bg-white text-gray-800 shadow-sm'
                    : 'text-gray-600 hover:text-gray-800'
                  }`}
              >
                👁️ Preview
              </button>
            </div>

            <button
              onClick={handleSaveToCase}
              disabled={isSaving || !investigationId}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors text-sm font-medium"
            >
              {isSaving ? '💾 Saving...' : '💾 Save to Case'}
            </button>

            <button
              onClick={refreshReportProgress}
              className="px-3 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-sm"
            >
              🔄 Refresh
            </button>
          </div>
        </div>

        {saveMessage && (
          <div className={`mt-2 text-sm ${saveMessage.includes('✅') ? 'text-green-600' : 'text-red-600'}`}>
            {saveMessage}
          </div>
        )}

        <div className="mb-4">
          <div className="flex items-center justify-between text-sm mb-2">
            <span className="text-gray-700 font-medium">Overall Progress</span>
            <span className="text-blue-700 font-bold">{Math.round(overallProgress)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-3">
            <div
              className="h-3 rounded-full bg-gradient-to-r from-blue-500 to-blue-600 transition-all duration-500"
              style={{ width: `${overallProgress}%` }}
            />
          </div>
        </div>

        <div className="grid grid-cols-4 gap-4">
          <div className="bg-blue-50 rounded-lg p-3 border border-blue-200">
            <div className="text-sm text-blue-700 mb-1">Pages</div>
            <div className="text-2xl font-bold text-blue-900">{currentPage}/{totalPages}</div>
          </div>

          <div className="bg-green-50 rounded-lg p-3 border border-green-200">
            <div className="text-sm text-green-700 mb-1">Sections</div>
            <div className="text-2xl font-bold text-green-900">{completedSections}/{totalSections}</div>
          </div>

          <div className="bg-purple-50 rounded-lg p-3 border border-purple-200">
            <div className="text-sm text-purple-700 mb-1">Words</div>
            <div className="text-2xl font-bold text-purple-900">{wordCount.toLocaleString()}</div>
          </div>

          <div className="bg-amber-50 rounded-lg p-3 border border-amber-200">
            <div className="text-sm text-amber-700 mb-1">Versions</div>
            <div className="text-2xl font-bold text-amber-900">
              {isLoadingVersions ? '...' : versions.length}
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {viewMode === 'progress' ? (
          <div className="p-6">
            <h4 className="font-semibold text-gray-700 mb-4">Section Progress</h4>

            <div className="space-y-3">
              {sections.map((section) => (
                <div
                  key={section.id}
                  onClick={() => setSelectedSection(section)}
                  className={`bg-white rounded-lg border-2 p-4 cursor-pointer transition-all ${selectedSection?.id === section.id
                      ? 'border-blue-400 shadow-md'
                      : 'border-gray-200 hover:border-gray-300 hover:shadow-sm'
                    }`}
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <span className={`text-2xl ${section.status === 'writing' ? 'animate-pulse' : ''}`}>
                        {getStatusIcon(section.status)}
                      </span>
                      <div>
                        <div className="font-semibold text-gray-800">{section.name}</div>
                        {section.pageNumbers && section.pageNumbers.length > 0 && (
                          <div className="text-xs text-gray-500">
                            Page{section.pageNumbers.length > 1 ? 's' : ''} {section.pageNumbers.join(', ')}
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="text-right">
                      <div className={`text-sm font-semibold ${getStatusColor(section.status)}`}>
                        {section.status === 'complete' && 'Complete'}
                        {section.status === 'writing' && 'Writing...'}
                        {section.status === 'pending' && 'Pending'}
                        {section.status === 'error' && 'Error'}
                      </div>
                      {section.lastUpdated && (
                        <div className="text-xs text-gray-500">{section.lastUpdated}</div>
                      )}
                    </div>
                  </div>

                  {section.status !== 'pending' && (
                    <div className="mb-2">
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full transition-all duration-300 ${section.status === 'complete' ? 'bg-green-500' :
                              section.status === 'writing' ? 'bg-blue-500' :
                                'bg-red-500'
                            }`}
                          style={{ width: `${section.progress}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {section.wordCount !== undefined && (
                    <div className="text-sm text-gray-600">
                      {section.wordCount.toLocaleString()} words
                    </div>
                  )}
                </div>
              ))}

              {sections.length === 0 && (
                <div className="bg-white rounded-lg border border-gray-200 p-4 text-sm text-gray-600">
                  Section-level progress is not available yet.
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="p-6">
            <div className="bg-white rounded-lg border border-gray-200 p-6 mb-4">
              <div className="flex items-center justify-between mb-4">
                <h4 className="font-semibold text-gray-700">Report Preview</h4>
                <button
                  onClick={() => router.push(`/cases/${caseId}/studio-v4`)}
                  className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                >
                  📄 Open in Report Studio
                </button>
              </div>

              <div className="bg-gray-100 rounded-lg border-2 border-dashed border-gray-300 aspect-[8.5/11] flex items-center justify-center">
                <div className="text-center p-8">
                  <div className="text-4xl mb-3">📄</div>
                  <div className="text-gray-600 mb-2">Canvas Report Preview</div>
                  <div className="text-sm text-gray-500">
                    Page {currentPage || 1} of {Math.max(totalPages, 1)}
                  </div>
                  {reportDocumentId && (
                    <div className="text-xs text-gray-500 mt-2">Document: {reportDocumentId}</div>
                  )}
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h4 className="font-semibold text-gray-700 mb-4">Quality Metrics</h4>

              <div className="space-y-4">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-700">Alignment Score</span>
                    <span className="text-sm font-bold text-green-700">{Math.round(alignmentScore * 100)}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div className="h-2 rounded-full bg-green-500" style={{ width: `${Math.round(alignmentScore * 100)}%` }} />
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-700">Completeness Score</span>
                    <span className="text-sm font-bold text-blue-700">{Math.round(completenessScore * 100)}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div className="h-2 rounded-full bg-blue-500" style={{ width: `${Math.round(completenessScore * 100)}%` }} />
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="bg-white border-t border-gray-200 p-4 flex gap-3 items-center">
        <input
          value={checkpointMessage}
          onChange={(event) => setCheckpointMessage(event.target.value)}
          placeholder="Checkpoint message"
          className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
        />
        <button
          onClick={handleCreateCheckpoint}
          disabled={!reportDocumentId || isCommitting}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 transition-colors font-medium"
        >
          {isCommitting ? '💾 Saving...' : '💾 Save Version'}
        </button>
        <button
          onClick={refreshVersions}
          disabled={!reportDocumentId || isLoadingVersions}
          className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
        >
          🕐 Refresh History
        </button>
      </div>
    </div>
  );
}