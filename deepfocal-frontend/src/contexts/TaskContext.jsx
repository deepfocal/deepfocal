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

    window.dispatchEvent(new CustomEvent('taskCompleted', {
      detail: {
        appId,
        result,
        success: true,
        analysisType: currentTask?.analysisType || 'quick',
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

    window.dispatchEvent(new CustomEvent('taskFailed', {
      detail: {
        appId,
        error,
        analysisType: currentTask?.analysisType || 'quick',
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

    window.dispatchEvent(new CustomEvent('taskTimeout', {
      detail: {
        appId,
        analysisType: currentTask?.analysisType || 'quick',
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
            newMap.set(appId, {
              ...existingTask,
              status,
              progress: Number.isFinite(data.progress_percent) ? data.progress_percent : existingTask.progress || 0,
              step: data.result_message || getStatusMessage(status),
              currentReviews: data.current_reviews ?? existingTask.currentReviews ?? 0,
              totalReviews: data.target_reviews ?? existingTask.totalReviews ?? 1000,
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
    try {
      const payload = {
        app_id: appId,
        analysis_type: analysisType,
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
          analysisType,
          status: 'pending',
          progress: 0,
          step: 'Initializing analysis...',
          startTime: new Date(),
          estimatedDuration: analysisType === 'full' ? 300000 : 60000,
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

        setRunningTasks((prev) => {
          const newMap = new Map(prev);
          newMap.set(appId, {
            taskId,
            appId,
            projectId,
            analysisType,
            status: existingStatus,
            progress: 0,
            step: getStatusMessage(existingStatus),
            startTime: new Date(),
            estimatedDuration: analysisType === 'full' ? 300000 : 60000,
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
