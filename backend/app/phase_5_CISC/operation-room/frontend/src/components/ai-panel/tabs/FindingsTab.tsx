/**
 * Findings Tab - Investigation findings with hypothesis verdicts
 */

'use client';

import { useInvestigationStore } from '@operation-room/stores/investigationStore';
import { Finding } from '@operation-room/types/investigation';
import { useMemo, useState } from 'react';

export default function FindingsTab() {
  const { findings } = useInvestigationStore();
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [sortBy, setSortBy] = useState<'timestamp' | 'confidence'>('timestamp');
  const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null);

  const getConfidenceValue = (finding: Finding): number | undefined => {
    if (typeof finding.confidence_score === 'number') {
      return finding.confidence_score;
    }
    if (typeof finding.confidence === 'number') {
      return finding.confidence;
    }
    return undefined;
  };

  // Filter and sort findings
  const processedFindings = useMemo(() => {
    let filtered = findings;

    // Filter by status
    if (filterStatus !== 'all') {
      filtered = filtered.filter(f => f.verdict === filterStatus);
    }

    // Sort
    const sorted = [...filtered].sort((a, b) => {
      if (sortBy === 'timestamp') {
        return new Date(b.timestamp || 0).getTime() - new Date(a.timestamp || 0).getTime();
      } else {
        return (getConfidenceValue(b) || 0) - (getConfidenceValue(a) || 0);
      }
    });

    return sorted;
  }, [findings, filterStatus, sortBy]);

  // Statistics
  const stats = useMemo(() => {
    const confirmed = findings.filter(f => f.verdict === 'confirmed').length;
    const rejected = findings.filter(f => f.verdict === 'rejected').length;
    const inconclusive = findings.filter(f => f.verdict === 'inconclusive').length;
    const confidenceValues = findings
      .map((finding) => getConfidenceValue(finding))
      .filter((value): value is number => typeof value === 'number');
    const avgConfidence = findings.length > 0
      ? confidenceValues.reduce((sum, value) => sum + value, 0) / Math.max(1, confidenceValues.length)
      : 0;

    return { confirmed, rejected, inconclusive, avgConfidence };
  }, [findings]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'confirmed': return 'bg-green-100 text-green-800 border-green-300';
      case 'rejected': return 'bg-red-100 text-red-800 border-red-300';
      case 'inconclusive': return 'bg-yellow-100 text-yellow-800 border-yellow-300';
      default: return 'bg-gray-100 text-gray-700 border-gray-300';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'confirmed': return '✅';
      case 'rejected': return '❌';
      case 'inconclusive': return '❓';
      default: return '⏳';
    }
  };

  const getConfidenceLabel = (score: number) => {
    if (score >= 0.9) return 'Very High';
    if (score >= 0.75) return 'High';
    if (score >= 0.5) return 'Moderate';
    if (score >= 0.25) return 'Low';
    return 'Very Low';
  };

  if (findings.length === 0) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-50 p-8">
        <div className="text-center">
          <div className="text-6xl mb-4">🔍</div>
          <h3 className="text-lg font-semibold text-gray-800 mb-2">
            No Findings Yet
          </h3>
          <p className="text-gray-600 max-w-md">
            As the AI tests hypotheses and analyzes evidence, findings will appear here.
            Each finding includes confidence scores and supporting evidence.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-gray-50">
      {/* Header with stats */}
      <div className="bg-white border-b border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">
          Investigation Findings ({findings.length})
        </h3>

        {/* Statistics Grid */}
        <div className="grid grid-cols-4 gap-4 mb-4">
          <div className="bg-green-50 rounded-lg p-3 border border-green-200">
            <div className="text-sm text-green-700 mb-1">Confirmed</div>
            <div className="text-2xl font-bold text-green-900">{stats.confirmed}</div>
          </div>

          <div className="bg-red-50 rounded-lg p-3 border border-red-200">
            <div className="text-sm text-red-700 mb-1">Rejected</div>
            <div className="text-2xl font-bold text-red-900">{stats.rejected}</div>
          </div>

          <div className="bg-yellow-50 rounded-lg p-3 border border-yellow-200">
            <div className="text-sm text-yellow-700 mb-1">Inconclusive</div>
            <div className="text-2xl font-bold text-yellow-900">{stats.inconclusive}</div>
          </div>

          <div className="bg-blue-50 rounded-lg p-3 border border-blue-200">
            <div className="text-sm text-blue-700 mb-1">Avg. Confidence</div>
            <div className="text-2xl font-bold text-blue-900">
              {Math.round(stats.avgConfidence * 100)}%
            </div>
          </div>
        </div>

        {/* Filters and sorting */}
        <div className="flex items-center gap-3">
          <div className="flex-1">
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
            >
              <option value="all">All Findings ({findings.length})</option>
              <option value="confirmed">Confirmed ({stats.confirmed})</option>
              <option value="rejected">Rejected ({stats.rejected})</option>
              <option value="inconclusive">Inconclusive ({stats.inconclusive})</option>
            </select>
          </div>

          <div className="flex-1">
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as 'timestamp' | 'confidence')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
            >
              <option value="timestamp">Sort by Time</option>
              <option value="confidence">Sort by Confidence</option>
            </select>
          </div>
        </div>
      </div>

      {/* Findings list */}
      <div className="flex-1 overflow-y-auto p-4">
        {processedFindings.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-4xl mb-2">🔍</div>
            <div className="text-gray-600">No findings match your filter</div>
          </div>
        ) : (
          <div className="space-y-3">
            {processedFindings.map((finding) => {
              const confidenceValue = getConfidenceValue(finding);
              const verdict = finding.verdict || 'inconclusive';
              const findingKey = `${finding.hypothesis_id}-${finding.timestamp || 'na'}-${verdict}-${finding.summary}`;

              return (
                <div
                  key={findingKey}
                  onClick={() => setSelectedFinding(finding)}
                  className="bg-white rounded-lg border-2 border-gray-200 hover:border-blue-300 p-4 hover:shadow-md transition-all cursor-pointer"
                >
                  {/* Header */}
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3 flex-1">
                      <span className="text-3xl">{getStatusIcon(verdict)}</span>
                      <div className="flex-1">
                        <div className="font-semibold text-gray-800 mb-1">
                          {finding.hypothesis_name}
                        </div>
                        <div className="text-sm text-gray-600">
                          {finding.summary}
                        </div>
                      </div>
                    </div>

                    <span className={`text-xs px-2 py-1 rounded-full font-medium border ${getStatusColor(verdict)
                      }`}>
                      {verdict.toUpperCase()}
                    </span>
                  </div>

                  {/* Confidence score */}
                  {confidenceValue !== undefined && (
                    <div className="mb-3">
                      <div className="flex items-center justify-between text-sm mb-1">
                        <span className="text-gray-600">
                          Confidence: {getConfidenceLabel(confidenceValue)}
                        </span>
                        <span className="font-semibold text-blue-700">
                          {Math.round(confidenceValue * 100)}%
                        </span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full ${confidenceValue >= 0.8 ? 'bg-green-500' :
                            confidenceValue >= 0.5 ? 'bg-blue-500' :
                              confidenceValue >= 0.25 ? 'bg-yellow-500' :
                                'bg-red-500'
                            }`}
                          style={{ width: `${confidenceValue * 100}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Evidence references */}
                  {finding.evidence_for && finding.evidence_for.length > 0 && (
                    <div className="flex items-center gap-2 text-sm text-gray-600">
                      <span>📎</span>
                      <span>{finding.evidence_for.length} pieces of evidence</span>
                    </div>
                  )}

                  {/* Timestamp */}
                  <div className="text-xs text-gray-500 mt-2">
                    {new Date(finding.timestamp || 0).toLocaleString()}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Finding details modal */}
      {selectedFinding && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          {(() => {
            const selectedVerdict = selectedFinding.verdict || 'inconclusive';

            return (
              <div className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[90vh] overflow-hidden flex flex-col">
                {/* Modal header */}
                <div className={`p-6 ${selectedVerdict === 'confirmed' ? 'bg-green-600' :
                  selectedVerdict === 'rejected' ? 'bg-red-600' :
                    'bg-yellow-600'
                  } text-white`}>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="text-3xl mb-2">{getStatusIcon(selectedVerdict)}</div>
                      <h3 className="text-xl font-semibold mb-2">
                        {selectedFinding.hypothesis_name}
                      </h3>
                      <div className="text-sm opacity-90">
                        {new Date(selectedFinding.timestamp || 0).toLocaleString()}
                      </div>
                    </div>
                    <button
                      onClick={() => setSelectedFinding(null)}
                      className="text-white hover:bg-white hover:bg-opacity-20 rounded-lg p-2 transition-colors"
                    >
                      ✕
                    </button>
                  </div>
                </div>

                {/* Modal content */}
                <div className="flex-1 overflow-y-auto p-6 space-y-6">
                  {/* Description */}
                  <div>
                    <h4 className="font-semibold text-gray-700 mb-2">Description</h4>
                    <p className="text-gray-600">{selectedFinding.summary}</p>
                  </div>

                  {/* Confidence */}
                  {getConfidenceValue(selectedFinding) !== undefined && (
                    <div>
                      <h4 className="font-semibold text-gray-700 mb-3">Confidence Assessment</h4>
                      <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm text-gray-700">
                            {getConfidenceLabel(getConfidenceValue(selectedFinding) || 0)}
                          </span>
                          <span className="text-lg font-bold text-blue-700">
                            {Math.round((getConfidenceValue(selectedFinding) || 0) * 100)}%
                          </span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-3">
                          <div
                            className={`h-3 rounded-full ${(getConfidenceValue(selectedFinding) || 0) >= 0.8 ? 'bg-green-500' :
                              (getConfidenceValue(selectedFinding) || 0) >= 0.5 ? 'bg-blue-500' :
                                (getConfidenceValue(selectedFinding) || 0) >= 0.25 ? 'bg-yellow-500' :
                                  'bg-red-500'
                              }`}
                            style={{ width: `${(getConfidenceValue(selectedFinding) || 0) * 100}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Evidence references */}
                  {selectedFinding.evidence_for && selectedFinding.evidence_for.length > 0 && (
                    <div>
                      <h4 className="font-semibold text-gray-700 mb-3">
                        Supporting Evidence ({selectedFinding.evidence_for.length})
                      </h4>
                      <div className="space-y-2">
                        {selectedFinding.evidence_for.map((ref, index) => (
                          <div
                            key={index}
                            className="bg-blue-50 border border-blue-200 rounded-lg p-3"
                          >
                            <div className="font-mono text-xs text-blue-800">{ref}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Metadata */}
                  <div>
                    <h4 className="font-semibold text-gray-700 mb-3">Metadata</h4>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <div className="text-gray-600 mb-1">Finding ID</div>
                        <div className="font-mono">{selectedFinding.hypothesis_id}</div>
                      </div>
                      <div>
                        <div className="text-gray-600 mb-1">Status</div>
                        <div className="font-semibold capitalize">{selectedVerdict}</div>
                      </div>
                      {selectedFinding.hypothesis_id && (
                        <div className="col-span-2">
                          <div className="text-gray-600 mb-1">Related Hypothesis</div>
                          <div className="font-mono">{selectedFinding.hypothesis_id}</div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Modal footer */}
                <div className="border-t border-gray-200 p-4 bg-gray-50 flex gap-3">
                  <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                    📤 Export Finding
                  </button>
                  <button
                    onClick={() => setSelectedFinding(null)}
                    className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-100 transition-colors ml-auto"
                  >
                    Close
                  </button>
                </div>
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}
