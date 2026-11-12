/**
 * Question Card Component - AI asks user for clarification
 */

import { useInvestigationStore } from '@operation-room/stores/investigationStore';
import { Message } from '@operation-room/types/investigation';
import { useState } from 'react';
import QuestionTimer from './QuestionTimer';

interface QuestionCardProps {
  message: Message;
}

export default function QuestionCard({ message }: QuestionCardProps) {
  const { investigationId, markQuestionAnswered } = useInvestigationStore();
  const [selectedChoice, setSelectedChoice] = useState<string | null>(null);
  const [customAnswer, setCustomAnswer] = useState('');
  const [isAnswered, setIsAnswered] = useState(message.metadata?.answered || false);

  const priority = (message.metadata?.priority || 'medium') as 'high' | 'medium' | 'low';
  const choices: string[] = message.metadata?.choices || [];
  const allowFreeform = message.metadata?.allowFreeform !== false;

  const handleAnswer = async (answer?: string, skipped = false) => {
    const finalAnswer = answer || selectedChoice || customAnswer;
    if (!finalAnswer || !investigationId) return;

    try {
      const response = await fetch(`/api/deep-research/investigations/${investigationId}/questions/${message.id}/answer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question_id: message.id,
          answer: finalAnswer,
        }),
      });

      if (!response.ok) {
        throw new Error(`Question answer failed (${response.status})`);
      }

      setIsAnswered(true);
      markQuestionAnswered(message.id, finalAnswer, skipped);
    } catch (error) {
      useInvestigationStore.getState().addChatMessage({
        id: `question-error-${Date.now()}`,
        sender: 'system',
        content: `❌ Failed to submit answer: ${error}`,
        type: 'error',
        timestamp: new Date().toISOString(),
      });
    }
  };

  const handleTimeout = () => {
    // Auto-select best answer after 60 seconds
    let bestAnswer = '';

    if (choices.length > 0) {
      // Select first recommended choice
      bestAnswer = choices[0];
    } else if (priority === 'high') {
      bestAnswer = 'Proceed with investigation';
    } else {
      bestAnswer = 'Skip';
    }

    handleAnswer(bestAnswer);
  };

  const handleSkip = () => {
    handleAnswer('Skip for now', true);
  };

  if (isAnswered) {
    return (
      <div className="mb-4 bg-green-50 border border-green-200 rounded-lg p-4">
        <div className="text-sm font-semibold text-green-900 mb-2">
          ✅ Question Answered
        </div>
        <div className="text-gray-700 mb-2">{message.content}</div>
        <div className="text-green-700 font-medium">
          {message.metadata?.skipped
            ? '⏭️ Skipped'
            : `Answer: ${message.metadata?.answer}`}
        </div>
      </div>
    );
  }

  const priorityColors = {
    high: 'bg-red-50 border-red-300 text-red-900',
    medium: 'bg-blue-50 border-blue-200 text-blue-900',
    low: 'bg-gray-50 border-gray-200 text-gray-700',
  };

  const priorityBadges = {
    high: 'bg-red-100 text-red-800',
    medium: 'bg-blue-100 text-blue-800',
    low: 'bg-gray-100 text-gray-700',
  };

  return (
    <div className={`mb-4 border rounded-lg p-4 ${priorityColors[priority]}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-semibold flex items-center gap-2">
          🔍 AI Question
          {priority === 'high' && (
            <span className={`text-xs px-2 py-0.5 rounded-full ${priorityBadges[priority]}`}>
              HIGH PRIORITY
            </span>
          )}
        </div>
        <div className="text-xs opacity-70">
          {new Date(message.timestamp).toLocaleTimeString()}
        </div>
      </div>

      {/* Question */}
      <div className="text-gray-900 mb-4 font-medium">
        {message.content}
      </div>

      {/* Multiple choice options */}
      {choices.length > 0 && (
        <div className="space-y-2 mb-4">
          {choices.map((choice: string, i: number) => (
            <label
              key={i}
              className="flex items-center gap-2 cursor-pointer hover:bg-white/50 p-2 rounded transition-colors"
            >
              <input
                type="radio"
                name={`question-${message.id}`}
                value={choice}
                checked={selectedChoice === choice}
                onChange={() => {
                  setSelectedChoice(choice);
                  setCustomAnswer(''); // Clear custom answer
                }}
                className="w-4 h-4 text-blue-600"
              />
              <span className="text-gray-800">{choice}</span>
            </label>
          ))}
        </div>
      )}

      {/* Freeform input */}
      {allowFreeform && (
        <div className="mb-4">
          <input
            type="text"
            value={customAnswer}
            onChange={(e) => {
              setCustomAnswer(e.target.value);
              setSelectedChoice(null); // Clear radio selection
            }}
            placeholder={choices.length > 0 ? "Or type your own answer..." : "Type your answer..."}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
      )}

      {/* Actions */}
      <div className="flex flex-col gap-2">
        <div className="flex gap-2">
          <button
            onClick={() => handleAnswer()}
            disabled={!selectedChoice && !customAnswer}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
          >
            Answer
          </button>
          <button
            onClick={handleSkip}
            className="px-4 py-2 border border-gray-300 rounded-md hover:bg-white/50 transition-colors"
          >
            Skip for now
          </button>
        </div>

        {/* Auto-answer timer */}
        <QuestionTimer
          questionId={message.id}
          onTimeout={handleTimeout}
          timeoutSeconds={60}
        />
      </div>
    </div>
  );
}
