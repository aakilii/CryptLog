/**
 * Finding Card Component - Shows hypothesis evaluation result
 */

import React from 'react';
import { Message } from '@operation-room/types/investigation';

interface FindingCardProps {
  message: Message;
}

export default function FindingCard({ message }: FindingCardProps) {
  const finding = message.metadata;
  
  if (!finding) {
    return <div className="mb-4 text-gray-500">Invalid finding data</div>;
  }
  
  const verdict = finding.verdict || 'inconclusive';
  const confidence = finding.confidence || 0;
  
  const verdictStyles = {
    confirmed: {
      bg: 'bg-green-50',
      border: 'border-green-300',
      text: 'text-green-900',
      badge: 'bg-green-100 text-green-800',
      icon: '✅',
    },
    rejected: {
      bg: 'bg-red-50',
      border: 'border-red-300',
      text: 'text-red-900',
      badge: 'bg-red-100 text-red-800',
      icon: '❌',
    },
    inconclusive: {
      bg: 'bg-yellow-50',
      border: 'border-yellow-300',
      text: 'text-yellow-900',
      badge: 'bg-yellow-100 text-yellow-800',
      icon: '⚠️',
    },
  };
  
  const style = verdictStyles[verdict as keyof typeof verdictStyles] || verdictStyles.inconclusive;
  
  return (
    <div className={`mb-4 border rounded-lg p-4 ${style.bg} ${style.border}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{style.icon}</span>
          <span className={`text-xs px-2 py-1 rounded-full font-semibold ${style.badge}`}>
            {verdict.toUpperCase()}
          </span>
        </div>
        <div className="text-xs opacity-70">
          {new Date(message.timestamp).toLocaleTimeString()}
        </div>
      </div>
      
      {/* Hypothesis name */}
      <div className={`font-semibold mb-2 ${style.text}`}>
        {finding.hypothesis_name}
      </div>
      
      {/* Confidence meter */}
      <div className="mb-3">
        <div className="flex items-center justify-between text-sm mb-1">
          <span className="text-gray-700">Confidence</span>
          <span className={`font-semibold ${style.text}`}>
            {(confidence * 100).toFixed(0)}%
          </span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div 
            className={`h-2 rounded-full transition-all ${
              verdict === 'confirmed' ? 'bg-green-600' :
              verdict === 'rejected' ? 'bg-red-600' :
              'bg-yellow-600'
            }`}
            style={{ width: `${confidence * 100}%` }}
          />
        </div>
      </div>
      
      {/* Summary */}
      {finding.summary && (
        <div className="text-sm text-gray-700 mb-3">
          {finding.summary}
        </div>
      )}
      
      {/* Evidence count */}
      <div className="flex gap-4 text-xs">
        {finding.evidence_for && finding.evidence_for.length > 0 && (
          <div className="flex items-center gap-1">
            <span className="text-green-600 font-semibold">
              {finding.evidence_for.length}
            </span>
            <span className="text-gray-600">evidence items</span>
          </div>
        )}
        {finding.evidence_against && finding.evidence_against.length > 0 && (
          <div className="flex items-center gap-1">
            <span className="text-red-600 font-semibold">
              {finding.evidence_against.length}
            </span>
            <span className="text-gray-600">contradictions</span>
          </div>
        )}
      </div>
      
      {/* View details button */}
      <button className="mt-3 text-sm text-blue-600 hover:text-blue-800 font-medium">
        View Full Analysis →
      </button>
    </div>
  );
}
