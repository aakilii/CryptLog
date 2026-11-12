/**
 * Evidence Tab - Evidence vault browser with filtering and export
 */

'use client';

import React, { useState, useMemo } from 'react';
import { useInvestigationStore } from '@operation-room/stores/investigationStore';
import { Evidence } from '@operation-room/types/investigation';

export default function EvidenceTab() {
  const { evidence } = useInvestigationStore();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedType, setSelectedType] = useState<string>('all');
  const [selectedSource, setSelectedSource] = useState<string>('all');
  const [selectedEvidence, setSelectedEvidence] = useState<Evidence | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  
  // Extract unique types and sources
  const types = useMemo(() => {
    const uniqueTypes = new Set(evidence.map(e => e.evidence_type));
    return Array.from(uniqueTypes);
  }, [evidence]);
  
  const sources = useMemo(() => {
    const uniqueSources = new Set(evidence.map(e => e.source_log));
    return Array.from(uniqueSources);
  }, [evidence]);
  
  // Filter evidence
  const filteredEvidence = useMemo(() => {
    return evidence.filter(e => {
      const matchesSearch = 
        searchQuery === '' || 
        e.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        JSON.stringify(e.data).toLowerCase().includes(searchQuery.toLowerCase());
      
      const matchesType = selectedType === 'all' || e.evidence_type === selectedType;
      const matchesSource = selectedSource === 'all' || e.source_log === selectedSource;
      
      return matchesSearch && matchesType && matchesSource;
    });
  }, [evidence, searchQuery, selectedType, selectedSource]);
  
  const handleEvidenceClick = (ev: Evidence) => {
    setSelectedEvidence(ev);
    setShowDetails(true);
  };
  
  const handleExport = () => {
    const dataStr = JSON.stringify(filteredEvidence, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
    const exportFileDefaultName = `evidence-export-${new Date().toISOString()}.json`;
    
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };
  
  const getTypeIcon = (type: string) => {
    const icons: Record<string, string> = {
      'log_entry': '📝',
      'timeline_event': '⏱️',
      'anomaly': '⚠️',
      'correlation': '🔗',
      'network_flow': '🌐',
      'file_access': '📁',
      'registry': '🔧',
      'process': '⚙️',
      'email': '📧',
      'usb': '💾',
      'bluetooth': '📡',
    };
    return icons[type] || '📄';
  };
  
  if (evidence.length === 0) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-50 p-8">
        <div className="text-center">
          <div className="text-6xl mb-4">🗂️</div>
          <h3 className="text-lg font-semibold text-gray-800 mb-2">
            No Evidence Collected Yet
          </h3>
          <p className="text-gray-600 max-w-md">
            As the AI investigates, evidence will be collected and stored here.
            Each piece of evidence is cryptographically hashed for integrity.
          </p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="h-full flex flex-col bg-gray-50">
      {/* Header with search and filters */}
      <div className="bg-white border-b border-gray-200 p-4">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex-1">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search evidence..."
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <button
            onClick={handleExport}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors whitespace-nowrap"
          >
            📤 Export ({filteredEvidence.length})
          </button>
        </div>
        
        {/* Filters */}
        <div className="flex items-center gap-3">
          <div className="flex-1">
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
            >
              <option value="all">All Types ({evidence.length})</option>
              {types.map(type => (
                <option key={type} value={type}>
                  {type} ({evidence.filter(e => e.evidence_type === type).length})
                </option>
              ))}
            </select>
          </div>
          
          <div className="flex-1">
            <select
              value={selectedSource}
              onChange={(e) => setSelectedSource(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
            >
              <option value="all">All Sources ({evidence.length})</option>
              {sources.map(source => (
                <option key={source} value={source}>
                  {source} ({evidence.filter(e => e.source_log === source).length})
                </option>
              ))}
            </select>
          </div>
        </div>
        
        {/* Stats */}
        <div className="mt-4 flex items-center gap-4 text-sm text-gray-600">
          <div>
            <span className="font-semibold text-gray-800">{filteredEvidence.length}</span> items shown
          </div>
          <div className="h-4 w-px bg-gray-300" />
          <div>
            <span className="font-semibold text-gray-800">{evidence.length}</span> total evidence
          </div>
        </div>
      </div>
      
      {/* Evidence list */}
      <div className="flex-1 overflow-y-auto p-4">
        {filteredEvidence.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-4xl mb-2">🔍</div>
            <div className="text-gray-600">No evidence matches your filters</div>
          </div>
        ) : (
          <div className="space-y-2">
            {filteredEvidence.map((ev) => (
              <div
                key={ev.evidence_id}
                onClick={() => handleEvidenceClick(ev)}
                className="bg-white rounded-lg border border-gray-200 p-4 hover:shadow-md transition-shadow cursor-pointer"
              >
                <div className="flex items-start gap-3">
                  <div className="text-2xl">
                    {getTypeIcon(ev.evidence_type)}
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    {/* Header */}
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-semibold text-gray-800 truncate">
                        {ev.description}
                      </span>
                      {ev.verified && (
                        <span className="text-green-600 text-xs">✓ Verified</span>
                      )}
                    </div>
                    
                    {/* Metadata */}
                    <div className="flex items-center gap-3 text-xs text-gray-500">
                      <span>
                        {new Date(ev.timestamp).toLocaleString()}
                      </span>
                      <span>•</span>
                      <span className="font-mono">
                        {ev.hash ? ev.hash.substring(0, 12) + '...' : 'No hash'}
                      </span>
                    </div>
                    
                    {/* Tags */}
                    <div className="flex items-center gap-2 mt-2">
                      <span className="text-xs px-2 py-0.5 bg-blue-50 text-blue-700 rounded border border-blue-200">
                        {ev.evidence_type}
                      </span>
                      <span className="text-xs px-2 py-0.5 bg-purple-50 text-purple-700 rounded border border-purple-200">
                        {ev.source_log}
                      </span>
                      {ev.confidence_score && (
                        <span className={`text-xs px-2 py-0.5 rounded border ${
                          ev.confidence_score >= 0.8 ? 'bg-green-50 text-green-700 border-green-200' :
                          ev.confidence_score >= 0.5 ? 'bg-yellow-50 text-yellow-700 border-yellow-200' :
                          'bg-red-50 text-red-700 border-red-200'
                        }`}>
                          Confidence: {(ev.confidence_score * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      
      {/* Evidence details modal */}
      {showDetails && selectedEvidence && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[90vh] overflow-hidden flex flex-col">
            {/* Modal header */}
            <div className="bg-gradient-to-r from-blue-600 to-blue-700 text-white p-6">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="text-2xl mb-2">{getTypeIcon(selectedEvidence.evidence_type)}</div>
                  <h3 className="text-xl font-semibold mb-2">
                    {selectedEvidence.description}
                  </h3>
                  <div className="text-sm opacity-90">
                    {new Date(selectedEvidence.timestamp).toLocaleString()}
                  </div>
                </div>
                <button
                  onClick={() => setShowDetails(false)}
                  className="text-white hover:bg-white hover:bg-opacity-20 rounded-lg p-2 transition-colors"
                >
                  ✕
                </button>
              </div>
            </div>
            
            {/* Modal content */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* Metadata */}
              <div>
                <h4 className="font-semibold text-gray-700 mb-3">Metadata</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-sm text-gray-600 mb-1">Evidence ID</div>
                    <div className="font-mono text-sm">{selectedEvidence.evidence_id}</div>
                  </div>
                  <div>
                    <div className="text-sm text-gray-600 mb-1">Type</div>
                    <div className="text-sm font-medium">{selectedEvidence.evidence_type}</div>
                  </div>
                  <div>
                    <div className="text-sm text-gray-600 mb-1">Source</div>
                    <div className="text-sm font-medium">{selectedEvidence.source_log}</div>
                  </div>
                  <div>
                    <div className="text-sm text-gray-600 mb-1">Verification</div>
                    <div className={`text-sm font-medium ${
                      selectedEvidence.verified ? 'text-green-600' : 'text-gray-400'
                    }`}>
                      {selectedEvidence.verified ? '✓ Verified' : 'Pending'}
                    </div>
                  </div>
                  {selectedEvidence.confidence_score && (
                    <div className="col-span-2">
                      <div className="text-sm text-gray-600 mb-1">Confidence Score</div>
                      <div className="flex items-center gap-2">
                        <div className="flex-1 bg-gray-200 rounded-full h-2">
                          <div 
                            className={`h-2 rounded-full ${
                              selectedEvidence.confidence_score >= 0.8 ? 'bg-green-500' :
                              selectedEvidence.confidence_score >= 0.5 ? 'bg-yellow-500' :
                              'bg-red-500'
                            }`}
                            style={{ width: `${selectedEvidence.confidence_score * 100}%` }}
                          />
                        </div>
                        <span className="text-sm font-semibold">
                          {(selectedEvidence.confidence_score * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
              
              {/* Hash */}
              {selectedEvidence.hash && (
                <div>
                  <h4 className="font-semibold text-gray-700 mb-3">Cryptographic Hash</h4>
                  <div className="bg-gray-50 rounded-lg p-3 font-mono text-xs break-all border border-gray-200">
                    {selectedEvidence.hash}
                  </div>
                  <p className="text-xs text-gray-500 mt-2">
                    SHA-256 hash ensures evidence integrity. Any modification will invalidate this hash.
                  </p>
                </div>
              )}
              
              {/* Raw data */}
              <div>
                <h4 className="font-semibold text-gray-700 mb-3">Raw Data</h4>
                <div className="bg-gray-900 text-green-400 rounded-lg p-4 overflow-x-auto max-h-96">
                  <pre className="text-xs font-mono">
                    {JSON.stringify(selectedEvidence.data, null, 2)}
                  </pre>
                </div>
              </div>
            </div>
            
            {/* Modal footer */}
            <div className="border-t border-gray-200 p-4 bg-gray-50 flex gap-3">
              <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                📋 Copy Hash
              </button>
              <button className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-100 transition-colors">
                📤 Export
              </button>
              <button 
                onClick={() => setShowDetails(false)}
                className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-100 transition-colors ml-auto"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
