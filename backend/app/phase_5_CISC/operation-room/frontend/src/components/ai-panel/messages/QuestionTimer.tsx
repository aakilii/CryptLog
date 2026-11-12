/**
 * QuestionTimer - Auto-answer questions after 60 seconds
 */

'use client';

import React, { useState, useEffect } from 'react';

interface QuestionTimerProps {
  questionId: string;
  onTimeout: () => void;
  timeoutSeconds?: number;
}

export default function QuestionTimer({ 
  questionId, 
  onTimeout, 
  timeoutSeconds = 60 
}: QuestionTimerProps) {
  const [secondsLeft, setSecondsLeft] = useState(timeoutSeconds);
  const [isExpired, setIsExpired] = useState(false);
  
  useEffect(() => {
    if (secondsLeft <= 0 && !isExpired) {
      setIsExpired(true);
      onTimeout();
      return;
    }
    
    const timer = setInterval(() => {
      setSecondsLeft((prev) => Math.max(0, prev - 1));
    }, 1000);
    
    return () => clearInterval(timer);
  }, [secondsLeft, isExpired, onTimeout]);
  
  const percentage = (secondsLeft / timeoutSeconds) * 100;
  const isWarning = secondsLeft <= 10;
  
  return (
    <div className="mt-2">
      <div className="flex items-center justify-between text-xs mb-1">
        <span className={`font-medium ${isWarning ? 'text-red-600' : 'text-gray-600'}`}>
          {isExpired ? '⏱️ Auto-answered' : `⏱️ Auto-answering in ${secondsLeft}s`}
        </span>
        {isExpired && (
          <span className="text-green-600 font-semibold">
            ✓ Best answer selected
          </span>
        )}
      </div>
      
      {!isExpired && (
        <div className="w-full bg-gray-200 rounded-full h-1.5">
          <div
            className={`h-1.5 rounded-full transition-all duration-1000 ${
              isWarning ? 'bg-red-500' : 'bg-blue-500'
            }`}
            style={{ width: `${percentage}%` }}
          />
        </div>
      )}
    </div>
  );
}
