/**
 * Progress Tab - Real-time investigation progress tracking
 */

'use client';

import { useInvestigationStore } from '@operation-room/stores/investigationStore';

export default function ProgressTab() {
  const { progressUpdate, phase, progress, findings, evidence, chatMessages, investigationId, reset, setActiveTab } = useInvestigationStore();

  // Extract progress messages from chat
  const progressMessages = chatMessages.filter(msg => msg.type === 'progress');

  // Build timeline from progress updates
  const timeline = progressMessages.map((msg, idx) => ({
    id: `phase-${idx}`,
    name: msg.metadata?.phase || msg.content,
    status: msg.metadata?.progress === 100 ? 'complete' : 'in_progress',
    progress: msg.metadata?.progress || 0,
    message: msg.content,
    timestamp: msg.timestamp,
    subTasks: msg.metadata?.sub_tasks || []
  }));

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'complete': return '✅';
      case 'in_progress': return '🔄';
      case 'pending': return '⏳';
      case 'failed': return '❌';
      default: return '⏳';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'complete': return 'text-green-600';
      case 'in_progress': return 'text-blue-600';
      case 'pending': return 'text-gray-400';
      case 'failed': return 'text-red-600';
      default: return 'text-gray-400';
    }
  };

  const overallProgress = progress || 0;

  const handleEndSession = () => {
    if (!investigationId) {
      return;
    }

    const confirmed = window.confirm('End the current AI investigation session?');
    if (!confirmed) {
      return;
    }

    reset();
  };

  return (
    <div className="h-full overflow-y-auto bg-gray-50">
      {/* Overall Progress Header */}
      <div className="bg-white border-b border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">Investigation Progress</h3>

        {/* Overall progress bar */}
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

        {/* Current phase info */}
        <div className="flex items-center justify-between text-sm">
          <div className="flex items-center gap-2">
            <span className="text-gray-600">Current Phase:</span>
            <span className="font-semibold text-gray-800 capitalize">{phase || 'Idle'}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-gray-600">Est. Time Remaining:</span>
            <span className="font-semibold text-gray-800">
              {progressUpdate?.estimated_time_remaining || 'N/A'}
            </span>
          </div>
        </div>
      </div>

      {/* Phase Timeline */}
      <div className="p-6">
        <h4 className="font-semibold text-gray-700 mb-4">Timeline View</h4>

        {timeline.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <div className="text-4xl mb-2">⏳</div>
            <p>Start an investigation to see progress here</p>
          </div>
        ) : (
          <div className="space-y-4">
            {timeline.map((item, index) => (
              <div key={item.id} className="bg-white rounded-lg border border-gray-200 p-4">
                {/* Phase header */}
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <span className={`text-2xl ${item.status === 'in_progress' ? 'animate-spin' : ''
                      }`}>
                      {getStatusIcon(item.status)}
                    </span>
                    <div>
                      <div className="font-semibold text-gray-800">
                        {index + 1}. {item.name}
                      </div>
                      <div className="text-xs text-gray-500">
                        {new Date(item.timestamp).toLocaleTimeString()}
                      </div>
                    </div>
                  </div>

                  <div className={`text-sm font-semibold ${getStatusColor(item.status)}`}>
                    {item.progress}%
                  </div>
                </div>

                {/* Phase progress bar */}
                <div className="mb-3">
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full transition-all duration-300 ${item.status === 'complete' ? 'bg-green-500' :
                          item.status === 'in_progress' ? 'bg-blue-500' :
                            'bg-gray-400'
                        }`}
                      style={{ width: `${item.progress}%` }}
                    />
                  </div>
                </div>

                {/* Message */}
                <div className="text-sm text-gray-600">{item.message}</div>

                {/* Sub-tasks */}
                {item.subTasks && item.subTasks.length > 0 && (
                  <div className="mt-3 pl-8 space-y-2">
                    {item.subTasks.map((task: any, taskIdx: number) => (
                      <div key={taskIdx} className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-2">
                          <span className={
                            task.status === 'complete' ? 'text-green-600' :
                              task.status === 'in_progress' ? 'text-blue-600' :
                                'text-gray-400'
                          }>
                            {getStatusIcon(task.status || 'in_progress')}
                          </span>
                          <span className="text-gray-700">{task.name}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="w-20 bg-gray-200 rounded-full h-1.5">
                            <div
                              className={`h-1.5 rounded-full ${task.status === 'complete' ? 'bg-green-500' : 'bg-blue-500'
                                }`}
                              style={{ width: `${task.progress || 0}%` }}
                            />
                          </div>
                          <span className="text-xs text-gray-500 w-10 text-right">
                            {task.progress || 0}%
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Statistics */}
      <div className="p-6 bg-white border-t border-gray-200">
        <h4 className="font-semibold text-gray-700 mb-4">Statistics</h4>

        <div className="grid grid-cols-2 gap-4">
          <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
            <div className="text-sm text-blue-700 mb-1">Events Parsed</div>
            <div className="text-2xl font-bold text-blue-900">
              {evidence.length}
            </div>
          </div>

          <div className="bg-green-50 rounded-lg p-4 border border-green-200">
            <div className="text-sm text-green-700 mb-1">Hypotheses Tested</div>
            <div className="text-2xl font-bold text-green-900">
              {findings.length}
            </div>
          </div>

          <div className="bg-purple-50 rounded-lg p-4 border border-purple-200">
            <div className="text-sm text-purple-700 mb-1">Evidence Collected</div>
            <div className="text-2xl font-bold text-purple-900">
              {evidence.length}
            </div>
          </div>

          <div className="bg-amber-50 rounded-lg p-4 border border-amber-200">
            <div className="text-sm text-amber-700 mb-1">Report Progress</div>
            <div className="text-2xl font-bold text-amber-900">
              {Math.round(overallProgress)}%
            </div>
          </div>
        </div>
      </div>

      {/* Control buttons */}
      <div className="p-6 bg-white border-t border-gray-200 flex gap-3">
        <button
          onClick={() => setActiveTab('chat')}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
        >
          💬 Open Chat Stream
        </button>
        <button
          onClick={handleEndSession}
          disabled={!investigationId}
          className="px-4 py-2 border border-red-300 text-red-700 rounded-lg hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          ⏹ End Session
        </button>
      </div>
    </div>
  );
}
