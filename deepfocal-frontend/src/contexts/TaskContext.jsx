// src/contexts/TaskContext.jsx - Task management for background processing
import React, { createContext, useContext, useState, useCallback } from 'react';
import apiClient from '../apiClient';

const TaskContext = createContext();

export const useTask = () => {
  const context = useContext(TaskContext);
  if (!context) {
    throw new Error('useTask must be used within TaskProvider');
  }
  return context;
};

export const TaskProvider = ({ children }) => {
  const [runningTasks, setRunningTasks] = useState(new Map());
  const [taskResults, setTaskResults] = useState(new Map());
  const [globalLoading, setGlobalLoading] = useState(false);

  // Helper functions defined first
  const getStatusMessage = (status) => {
    switch (status) {
      case 'PENDING': return 'Queued for processing...';
      case 'PROGRESS': return 'Analyzing reviews...';
      case 'SUCCESS': return 'Analysis complete!';
      case 'FAILURE': return 'Analysis failed';
      default: return 'Processing...';
    }
  };

  const handleTaskSuccess = useCallback((appId, result) => {
    setRunningTasks(prev => {
      const newMap = new Map(prev);
      newMap.delete(appId);
      return newMap;
    });

    setTaskResults(prev => new Map(prev.set(appId, result)));
    setGlobalLoading(prev => {
      const newMap = new Map(runningTasks);
      newMap.delete(appId);
      return newMap.size > 0;
    });

    // Trigger data refresh
    window.dispatchEvent(new CustomEvent('taskCompleted', {
      detail: { appId, result, success: true }
    }));
  }, [runningTasks]);

  const handleTaskFailure = useCallback((appId, error) => {
    setRunningTasks(prev => {
      const newMap = new Map(prev);
      newMap.delete(appId);
      return newMap;
    });

    setGlobalLoading(prev => {
      const newMap = new Map(runningTasks);
      newMap.delete(appId);
      return newMap.size > 0;
    });

    console.error(`Task failed for ${appId}:`, error);

    // Trigger error handling
    window.dispatchEvent(new CustomEvent('taskFailed', {
      detail: { appId, error }
    }));
  }, [runningTasks]);

  const handleTaskTimeout = useCallback((appId) => {
    setRunningTasks(prev => {
      const newMap = new Map(prev);
      newMap.delete(appId);
      return newMap;
    });

    setGlobalLoading(prev => {
      const newMap = new Map(runningTasks);
      newMap.delete(appId);
      return newMap.size > 0;
    });

    window.dispatchEvent(new CustomEvent('taskTimeout', {
      detail: { appId }
    }));
  }, [runningTasks]);

  // Start a new background task
  const startTask = useCallback(async (appId, projectId = null) => {
    try {
      const payload = { app_id: appId };
      if (projectId) payload.project_id = projectId;

      const response = await apiClient.post('/api/trigger-insights/', payload);
      const taskId = response.data.task_id;

      setRunningTasks(prev => new Map(prev.set(appId, {
        taskId,
        appId,
        projectId,
        status: 'PENDING',
        progress: 0,
        step: 'Initializing analysis...',
        startTime: new Date(),
        estimatedDuration: 60000 // 1 minute estimate
      })));

      setGlobalLoading(true);

      // Start polling for this specific task
      pollTaskStatus(taskId, appId);

      return taskId;
    } catch (error) {
      console.error('Error starting task:', error);
      throw error;
    }
  }, []);

  // Poll task status with exponential backoff
  const pollTaskStatus = useCallback(async (taskId, appId) => {
    let pollInterval = 2000; // Start with 2 seconds
    let pollCount = 0;
    const maxPolls = 150; // 5 minutes maximum

    const poll = async () => {
      try {
        const response = await apiClient.get(`/api/task-status/${taskId}/`);
        const { status, result, progress } = response.data;

        setRunningTasks(prev => {
          const newMap = new Map(prev);
          if (newMap.has(appId)) {
            const existingTask = newMap.get(appId);
            newMap.set(appId, {
              ...existingTask,
              status,
              progress: progress?.progress || 0,
              step: progress?.step || getStatusMessage(status),
              currentReviews: progress?.current_reviews || 0,
              totalReviews: progress?.total_reviews || 1000
            });
          }
          return newMap;
        });

        // Handle completion
        if (status === 'SUCCESS') {
          handleTaskSuccess(appId, result);
          return; // Stop polling
        }

        if (status === 'FAILURE') {
          handleTaskFailure(appId, result);
          return; // Stop polling
        }

        // Continue polling if still running
        if (status === 'PENDING' || status === 'PROGRESS') {
          pollCount++;

          // Exponential backoff: increase interval slightly over time
          if (pollCount > 10) pollInterval = 3000; // 3s after 20 seconds
          if (pollCount > 30) pollInterval = 5000; // 5s after 1 minute

          if (pollCount < maxPolls) {
            setTimeout(poll, pollInterval);
          } else {
            // Timeout after max polls
            handleTaskTimeout(appId);
          }
        }
      } catch (error) {
        console.error('Error polling task:', error);
        handleTaskFailure(appId, error.message);
      }
    };

    poll();
  }, [handleTaskSuccess, handleTaskFailure, handleTaskTimeout]);

  const getTaskStatus = useCallback((appId) => {
    return runningTasks.get(appId);
  }, [runningTasks]);

  const getTaskResult = useCallback((appId) => {
    return taskResults.get(appId);
  }, [taskResults]);

  const clearTaskResult = useCallback((appId) => {
    setTaskResults(prev => {
      const newMap = new Map(prev);
      newMap.delete(appId);
      return newMap;
    });
  }, []);

  const isTaskRunning = useCallback((appId) => {
    return runningTasks.has(appId);
  }, [runningTasks]);

  return (
    <TaskContext.Provider value={{
      startTask,
      getTaskStatus,
      getTaskResult,
      clearTaskResult,
      isTaskRunning,
      runningTasks,
      taskResults,
      globalLoading
    }}>
      {children}
    </TaskContext.Provider>
  );
};