/**
 * Chat Message Component - Renders different message types
 */

import { Message } from '@operation-room/types/investigation';
import FindingCard from './FindingCard';
import ProgressMessage from './ProgressMessage';
import QuestionCard from './QuestionCard';

interface ChatMessageProps {
  message: Message;
}

export default function ChatMessage({ message }: ChatMessageProps) {
  // Render specialized components for different message types
  if (message.type === 'question') {
    return <QuestionCard message={message} />;
  }

  if (message.type === 'finding') {
    return <FindingCard message={message} />;
  }

  if (message.type === 'progress') {
    return <ProgressMessage message={message} />;
  }

  // Default text message
  const isUser = message.sender === 'user';
  const isSystem = message.sender === 'system';
  const isError = message.type === 'error';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div className={`max-w-[85%] rounded-lg px-4 py-3 ${isUser
          ? 'bg-blue-600 text-white rounded-br-none'
          : isSystem
            ? 'bg-gray-100 text-gray-700 italic border border-gray-200'
            : isError
              ? 'bg-red-50 text-red-900 border border-red-200'
              : 'bg-white text-gray-900 shadow-sm border border-gray-200 rounded-bl-none'
        }`}>
        {/* Sender label for AI messages */}
        {!isUser && !isSystem && (
          <div className="text-xs font-semibold mb-1 text-blue-600">
            🤖 AI Assistant
          </div>
        )}

        {/* Message content with markdown support */}
        <div
          className="whitespace-pre-wrap break-words"
          dangerouslySetInnerHTML={{
            __html: formatMessage(message.content)
          }}
        />

        {/* Timestamp */}
        <div className={`text-xs mt-2 ${isUser ? 'text-blue-100' : 'text-gray-500'
          }`}>
          {formatTime(message.timestamp)}
        </div>
      </div>
    </div>
  );
}

function formatMessage(content: string): string {
  // Escape HTML first so model/user content cannot inject arbitrary markup.
  const escaped = content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

  // Simple markdown-like formatting
  return escaped
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') // **bold**
    .replace(/__(.*?)__/g, '<em>$1</em>') // __italic__
    .replace(/`(.*?)`/g, '<code class="px-1 py-0.5 bg-gray-100 rounded text-sm">$1</code>') // `code`
    .replace(/\n/g, '<br/>'); // line breaks
}

function formatTime(timestamp: string): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;

  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
