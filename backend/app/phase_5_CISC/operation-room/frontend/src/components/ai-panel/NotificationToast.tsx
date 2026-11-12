/**
 * Notification Toast - Display system notifications and alerts
 */

'use client';

import React, { useEffect, useState } from 'react';
import { useInvestigationStore } from '@operation-room/stores/investigationStore';

interface Notification {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error' | 'question';
  message: string;
  timestamp: number;
  autoClose?: boolean;
  duration?: number;
}

export default function NotificationToast() {
  const { chatMessages, setActiveTab } = useInvestigationStore();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  
  // Watch for new questions and important messages
  useEffect(() => {
    const lastMessage = chatMessages[chatMessages.length - 1];
    if (!lastMessage) return;
    
    // Check if it's a question requiring attention
    if (lastMessage.type === 'question' && !lastMessage.metadata?.answered) {
      const notification: Notification = {
        id: `notif-${lastMessage.id}`,
        type: 'question',
        message: '🔔 AI needs your input!',
        timestamp: Date.now(),
        autoClose: false,
      };
      
      setNotifications(prev => {
        if (prev.some(n => n.id === notification.id)) return prev;
        return [...prev, notification];
      });
    }
    
    // Check for errors
    if (lastMessage.type === 'error') {
      const notification: Notification = {
        id: `notif-${lastMessage.id}`,
        type: 'error',
        message: lastMessage.content,
        timestamp: Date.now(),
        autoClose: true,
        duration: 5000,
      };
      
      setNotifications(prev => [...prev, notification]);
    }
    
    // Check for findings
    if (lastMessage.type === 'finding') {
      const notification: Notification = {
        id: `notif-${lastMessage.id}`,
        type: 'success',
        message: '🎯 New finding discovered!',
        timestamp: Date.now(),
        autoClose: true,
        duration: 3000,
      };
      
      setNotifications(prev => [...prev, notification]);
    }
  }, [chatMessages]);
  
  // Auto-close notifications
  useEffect(() => {
    const timer = setInterval(() => {
      setNotifications(prev => 
        prev.filter(n => {
          if (!n.autoClose) return true;
          return Date.now() - n.timestamp < (n.duration || 5000);
        })
      );
    }, 1000);
    
    return () => clearInterval(timer);
  }, []);
  
  const removeNotification = (id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  };
  
  const handleNotificationClick = (notification: Notification) => {
    if (notification.type === 'question') {
      setActiveTab('chat');
    }
    removeNotification(notification.id);
  };
  
  const getTypeStyles = (type: string) => {
    switch (type) {
      case 'question':
        return 'bg-blue-600 text-white border-blue-700';
      case 'success':
        return 'bg-green-600 text-white border-green-700';
      case 'warning':
        return 'bg-yellow-500 text-white border-yellow-600';
      case 'error':
        return 'bg-red-600 text-white border-red-700';
      default:
        return 'bg-gray-700 text-white border-gray-800';
    }
  };
  
  if (notifications.length === 0) return null;
  
  return (
    <div className="fixed bottom-4 right-4 z-50 space-y-2">
      {notifications.map((notification) => (
        <div
          key={notification.id}
          onClick={() => handleNotificationClick(notification)}
          className={`
            px-4 py-3 rounded-lg shadow-lg cursor-pointer border
            transform transition-all duration-300 hover:scale-105
            ${getTypeStyles(notification.type)}
          `}
        >
          <div className="flex items-center gap-3">
            <span className="text-lg">
              {notification.type === 'question' && '❓'}
              {notification.type === 'success' && '✅'}
              {notification.type === 'warning' && '⚠️'}
              {notification.type === 'error' && '❌'}
              {notification.type === 'info' && 'ℹ️'}
            </span>
            <div className="flex-1">
              <div className="font-medium">{notification.message}</div>
              {notification.type === 'question' && (
                <div className="text-sm opacity-80">Click to respond</div>
              )}
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                removeNotification(notification.id);
              }}
              className="opacity-70 hover:opacity-100"
            >
              ✕
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
