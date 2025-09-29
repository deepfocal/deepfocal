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
  const normalizeStatus = (status) => (status || '').toString().toUpperCase();

  const getStatusMessage = (status) => {
    switch (normalizeStatus(status)) {
      case 'PENDING':
      case 'STARTED':
        return 'Queued for processing...';
      case 'PROGRESS':
        return 'Analyzing reviews...';
      case 'SUCCESS':
        return 'Analysis complete!';
      case 'FAILURE':
      case 'REVOKED':
        return 'Analysis failed';
      default:
        return 'Processing...';
    }
  };

  const handleTaskSuccess = useCallback((appId, result) => {
    const currentTask = runningTasks.get(appId);

    setRunningTasks((prev) => {
      const newMap = new Map(prev);
      newMap.delete(appId);
      setGlobalLoading(newMap.size > 0);
      return newMap;
    });

    setTaskResults((prev) => {
      const newMap = new Map(prev);
      newMap.set(appId, result);
      return newMap;
    });

    const resolvedType = (result?.task_type || currentTask?.analysisType || 'quick').toLowerCase();

    window.dispatchEvent(new CustomEvent('taskCompleted', {
      detail: {
        appId,
        result,
        success: true,
        analysisType: resolvedType,
      },
    }));
  }, [runningTasks]);

  const handleTaskFailure = useCallback((appId, error) => {
    const currentTask = runningTasks.get(appId);

    setRunningTasks((prev) => {
      const newMap = new Map(prev);
      newMap.delete(appId);
      setGlobalLoading(newMap.size > 0);
      return newMap;
    });

    console.error(`Task failed for ${appId}:`, error);

    const resolvedType = (currentTask?.analysisType || 'quick').toLowerCase();

    window.dispatchEvent(new CustomEvent('taskFailed', {
      detail: {
        appId,
        error,
        analysisType: resolvedType,
      },
    }));
  }, [runningTasks]);

  const handleTaskTimeout = useCallback((appId) => {
    const currentTask = runningTasks.get(appId);

    setRunningTasks((prev) => {
      const newMap = new Map(prev);
      newMap.delete(appId);
      setGlobalLoading(newMap.size > 0);
      return newMap;
    });

    const resolvedType = (currentTask?.analysisType || 'quick').toLowerCase();

    window.dispatchEvent(new CustomEvent('taskTimeout', {
      detail: {
        appId,
        analysisType: resolvedType,
      },
    }));
  }, [runningTasks]);

  // Poll task status with exponential backoff
  const pollTaskStatus = useCallback(async (taskId, appId) => {
    let pollInterval = 2000; // Start with 2 seconds
    let pollCount = 0;
    const maxPolls = 150; // 5 minutes maximum

    const poll = async () => {
      try {
        const response = await apiClient.get(`/api/tasks/${taskId}/detail/`);
        const data = response.data || {};
        const status = (data.status || 'pending').toLowerCase();

        setRunningTasks((prev) => {
          const newMap = new Map(prev);
          if (newMap.has(appId)) {
            const existingTask = newMap.get(appId);

            const parsedProgress = Number.parseFloat(data.progress_percent ?? data.progressPercent);
            const parsedCurrent = Number.parseInt(data.current_reviews ?? data.currentReviews, 10);
            const parsedTotal = Number.parseInt(data.target_reviews ?? data.totalReviews, 10);
            const nextProgress = Number.isFinite(parsedProgress) ? Math.max(0, Math.min(100, parsedProgress)) : existingTask.progress || 0;
            const nextCurrent = Number.isFinite(parsedCurrent) ? Math.max(parsedCurrent, 0) : existingTask.currentReviews ?? 0;
            const nextTotal = Number.isFinite(parsedTotal) ? Math.max(parsedTotal, 0) : existingTask.totalReviews ?? 1000;
            const taskType = (data.task_type || data.analysis_type || existingTask.analysisType || 'quick').toLowerCase();

            newMap.set(appId, {
              ...existingTask,
              analysisType: taskType,
              status,
              progress: nextProgress,
              step: data.result_message || data.status || getStatusMessage(status),
              currentReviews: nextCurrent,
              totalReviews: nextTotal,
            });
          }
          return newMap;
        });

        if (status === 'success') {
          handleTaskSuccess(appId, data);
          return;
        }

        if (status === 'failure' || status === 'revoked') {
          handleTaskFailure(appId, data.error_message || data);
          return;
        }

        if (status === 'pending' || status === 'started' || status === 'progress') {
          pollCount++;

          if (pollCount > 10) pollInterval = 3000;
          if (pollCount > 30) pollInterval = 5000;

          if (pollCount < maxPolls) {
            setTimeout(poll, pollInterval);
          } else {
            handleTaskTimeout(appId);
          }
        }
      } catch (error) {
        console.error('Error polling task:', error);
        handleTaskFailure(appId, error.message);
      }
    };

    poll();
  }, [handleTaskSuccess, handleTaskFailure, handleTaskTimeout, getStatusMessage]);

  // Start a new background task
  const startTask = useCallback(async (appId, projectId = null, analysisType = 'quick') => {
    const normalizedType = (analysisType || 'quick').toLowerCase();

    try {
      const payload = {
        app_id: appId,
        analysis_type: normalizedType,
      };

      if (projectId) {
        payload.project_id = projectId;
      }

      const response = await apiClient.post('/api/analysis/start/', payload);
      const taskId = response.data.task_id;

      setRunningTasks((prev) => {
        const newMap = new Map(prev);
        newMap.set(appId, {
          taskId,
          appId,
          projectId,
          analysisType: normalizedType,
          status: 'pending',
          progress: 0,
          step: 'Initializing analysis...',
          startTime: new Date(),
          estimatedDuration: normalizedType === 'full' ? 300000 : 60000,
        });
        return newMap;
      });

      setGlobalLoading(true);

      pollTaskStatus(taskId, appId);

      return taskId;
    } catch (error) {
      if (error.response?.status === 409 && error.response?.data?.existing_task_id) {
        const taskId = error.response.data.existing_task_id;
        const existingStatus = error.response.data.task_status || 'pending';
        const existingType = (error.response.data.task_type || normalizedType || 'quick').toLowerCase();

        setRunningTasks((prev) => {
          const newMap = new Map(prev);
          newMap.set(appId, {
            taskId,
            appId,
            projectId,
            analysisType: existingType,
            status: existingStatus,
            progress: 0,
            step: getStatusMessage(existingStatus),
            startTime: new Date(),
            estimatedDuration: existingType === 'full' ? 300000 : 60000,
          });
          return newMap;
        });

        setGlobalLoading(true);
        pollTaskStatus(taskId, appId);
        return taskId;
      }

      console.error('Error starting task:', error);
      throw error;
    }
  }, [pollTaskStatus, getStatusMessage]);

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
