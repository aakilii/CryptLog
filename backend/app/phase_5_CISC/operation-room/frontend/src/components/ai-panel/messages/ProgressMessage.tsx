/**
 * Progress Message Component - Shows investigation progress update
 */

import React from 'react';
import { Message } from '@operation-room/types/investigation';

interface ProgressMessageProps {
  message: Message;
}

export default function ProgressMessage({ message }: ProgressMessageProps) {
  const progress = message.metadata?.progress || 0;
  const phase = message.metadata?.phase || 'Processing';
  const currentTask = message.metadata?.current_task;
  
  return (
    <div className="mb-4 bg-blue-50 border border-blue-200 rounded-lg p-4">
      {/* Icon and phase */}
      <div className="flex items-center gap-2 mb-2">
        <div className="animate-spin text-blue-600">⚙️</div>
        <span className="font-semibold text-blue-900 text-sm">
          {phase}
        </span>
      </div>
      
      {/* Message */}
      <div className="text-gray-700 text-sm mb-3">
        {message.content}
      </div>
      
      {/* Progress bar */}
      <div className="mb-2">
        <div className="flex items-center justify-between text-xs mb-1">
          <span className="text-gray-600">{currentTask || 'In progress...'}</span>
          <span className="font-semibold text-blue-700">{Math.round(progress)}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-1.5">
          <div 
            className="h-1.5 rounded-full bg-blue-600 transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
      
      {/* Timestamp */}
      <div className="text-xs text-gray-500">
        {new Date(message.timestamp).toLocaleTimeString()}
      </div>
    </div>
  );
}
