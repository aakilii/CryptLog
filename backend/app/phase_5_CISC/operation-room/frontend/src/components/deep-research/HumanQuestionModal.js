/**
 * Human-in-Loop Question Components
 * 
 * - HumanQuestionModal: Blocking modal for critical questions
 * - HumanQuestionPanel: Side panel for non-blocking questions
 */

import React, { useState, useEffect } from 'react';

const PRIORITY_COLORS = {
  blocking: 'bg-red-500',
  high: 'bg-orange-500',
  medium: 'bg-yellow-500',
  low: 'bg-blue-500',
};

const PRIORITY_LABELS = {
  blocking: 'Blocking - Must answer to proceed',
  high: 'High Priority',
  medium: 'Medium Priority',
  low: 'Low Priority - Can skip',
};

export function HumanQuestionModal({
  question,
  onAnswer,
  onClose,
  isOpen = false,
}) {
  const [answer, setAnswer] = useState('');
  const [selectedOption, setSelectedOption] = useState(null);
  
  useEffect(() => {
    if (isOpen) {
      setAnswer('');
      setSelectedOption(null);
    }
  }, [isOpen, question]);
  
  if (!isOpen || !question) return null;
  
  const hasOptions = question.options && question.options.length > 0;
  const priorityColor = PRIORITY_COLORS[question.priority] || PRIORITY_COLORS.medium;
  
  const handleSubmit = () => {
    const finalAnswer = hasOptions ? selectedOption : answer;
    if (finalAnswer) {
      onAnswer(question.id, finalAnswer);
    }
  };
  
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full mx-4 overflow-hidden">
        {/* Header */}
        <div className={`px-6 py-4 ${priorityColor} text-white`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-2xl">❓</span>
              <span className="font-semibold">Clarification Needed</span>
            </div>
            {question.priority !== 'blocking' && (
              <button
                onClick={onClose}
                className="text-white/70 hover:text-white"
              >
                ×
              </button>
            )}
          </div>
          <p className="text-sm text-white/80 mt-1">
            {PRIORITY_LABELS[question.priority]}
          </p>
        </div>
        
        {/* Content */}
        <div className="px-6 py-4">
          <p className="text-lg text-gray-900 mb-4">
            {question.question}
          </p>
          
          {/* Context */}
          {question.context && (
            <div className="mb-4 p-3 bg-gray-50 rounded-lg text-sm text-gray-600">
              <span className="font-medium">Context:</span>
              <p className="mt-1">{question.context}</p>
            </div>
          )}
          
          {/* Options */}
          {hasOptions ? (
            <div className="space-y-2">
              {question.options.map((option, index) => (
                <button
                  key={index}
                  onClick={() => setSelectedOption(option)}
                  className={`
                    w-full p-3 text-left rounded-lg border-2 transition-colors
                    ${selectedOption === option 
                      ? 'border-blue-500 bg-blue-50' 
                      : 'border-gray-200 hover:border-gray-300'
                    }
                  `}
                >
                  <span className="font-medium">{option}</span>
                </button>
              ))}
            </div>
          ) : (
            <textarea
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="Type your answer..."
              className="w-full p-3 border rounded-lg resize-none h-24 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              autoFocus
            />
          )}
        </div>
        
        {/* Actions */}
        <div className="px-6 py-4 bg-gray-50 flex justify-end gap-3">
          {question.priority !== 'blocking' && (
            <button
              onClick={onClose}
              className="px-4 py-2 text-gray-600 hover:text-gray-800"
            >
              Skip for Now
            </button>
          )}
          <button
            onClick={handleSubmit}
            disabled={hasOptions ? !selectedOption : !answer.trim()}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Submit Answer
          </button>
        </div>
      </div>
    </div>
  );
}

export function HumanQuestionPanel({
  questions = [],
  onAnswer,
  onDismiss,
  isOpen = true,
  className = '',
}) {
  const [expandedId, setExpandedId] = useState(null);
  const [answers, setAnswers] = useState({});
  
  const sortedQuestions = [...questions].sort((a, b) => {
    const priorityOrder = { blocking: 0, high: 1, medium: 2, low: 3 };
    return (priorityOrder[a.priority] || 3) - (priorityOrder[b.priority] || 3);
  });
  
  if (!isOpen) return null;
  
  return (
    <div className={`flex flex-col h-full bg-white ${className}`}>
      {/* Header */}
      <div className="px-4 py-3 border-b flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-gray-900">Questions</h3>
          <p className="text-sm text-gray-500">
            {questions.length} pending
          </p>
        </div>
        <span className="relative flex h-3 w-3">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-3 w-3 bg-yellow-500"></span>
        </span>
      </div>
      
      {/* Question List */}
      <div className="flex-1 overflow-auto">
        {sortedQuestions.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            <p>No pending questions</p>
          </div>
        ) : (
          <div className="divide-y">
            {sortedQuestions.map(question => {
              const isExpanded = expandedId === question.id;
              const priorityColor = PRIORITY_COLORS[question.priority] || PRIORITY_COLORS.medium;
              const hasOptions = question.options && question.options.length > 0;
              
              return (
                <div key={question.id} className="p-4">
                  {/* Question Header */}
                  <div 
                    className="flex items-start gap-3 cursor-pointer"
                    onClick={() => setExpandedId(isExpanded ? null : question.id)}
                  >
                    <span className={`w-2 h-2 mt-2 rounded-full ${priorityColor}`} />
                    <div className="flex-1">
                      <p className="font-medium text-gray-900">{question.question}</p>
                      <span className="text-xs text-gray-500 capitalize">
                        {question.thought_type || 'general'} • {question.priority}
                      </span>
                    </div>
                    <span className="text-gray-400">
                      {isExpanded ? '▼' : '▶'}
                    </span>
                  </div>
                  
                  {/* Expanded Content */}
                  {isExpanded && (
                    <div className="mt-3 ml-5">
                      {question.context && (
                        <p className="text-sm text-gray-600 mb-3">{question.context}</p>
                      )}
                      
                      {hasOptions ? (
                        <div className="space-y-2">
                          {question.options.map((option, i) => (
                            <button
                              key={i}
                              onClick={() => onAnswer(question.id, option)}
                              className="w-full p-2 text-left text-sm rounded border hover:bg-gray-50"
                            >
                              {option}
                            </button>
                          ))}
                        </div>
                      ) : (
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={answers[question.id] || ''}
                            onChange={(e) => setAnswers(prev => ({
                              ...prev,
                              [question.id]: e.target.value,
                            }))}
                            placeholder="Type answer..."
                            className="flex-1 p-2 text-sm border rounded"
                          />
                          <button
                            onClick={() => {
                              if (answers[question.id]) {
                                onAnswer(question.id, answers[question.id]);
                                setAnswers(prev => {
                                  const next = { ...prev };
                                  delete next[question.id];
                                  return next;
                                });
                              }
                            }}
                            disabled={!answers[question.id]}
                            className="px-3 py-2 bg-blue-600 text-white text-sm rounded disabled:opacity-50"
                          >
                            Send
                          </button>
                        </div>
                      )}
                      
                      {question.priority !== 'blocking' && (
                        <button
                          onClick={() => onDismiss?.(question.id)}
                          className="mt-2 text-xs text-gray-500 hover:text-gray-700"
                        >
                          Skip for now
                        </button>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default HumanQuestionModal;
