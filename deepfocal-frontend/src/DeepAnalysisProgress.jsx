import React, { useState, useEffect, useRef, useCallback } from 'react';
import PropTypes from 'prop-types';
import apiClient from './apiClient';
import { Box, Button, LinearProgress, Typography, Alert } from '@mui/material';
import { Psychology } from '@mui/icons-material';

const POLL_INTERVAL_MS = 3000;
const TERMINAL_STATUSES = ['success', 'failure', 'revoked'];

const DeepAnalysisProgress = ({
  appId,
  projectId,
  appName,
  onComplete,
  initialTask,
  buttonLabel = 'Continue for Deeper Analysis',
}) => {
  const [taskId, setTaskId] = useState(initialTask?.task_id || null);
  const [status, setStatus] = useState(initialTask?.status || null);
  const [progressPercent, setProgressPercent] = useState(initialTask?.progress_percent || 0);
  const [currentReviews, setCurrentReviews] = useState(initialTask?.current_reviews || 0);
  const [targetReviews, setTargetReviews] = useState(initialTask?.target_reviews || 0);
  const [taskType, setTaskType] = useState(initialTask?.task_type || null);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState(null);
  const pollingRef = useRef(null);
  const completionNotifiedRef = useRef(false);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const isTerminal = useCallback(
    (state) => TERMINAL_STATUSES.includes((state || '').toLowerCase()),
    [],
  );

  const handleCompletion = useCallback(
    (payload) => {
      if (completionNotifiedRef.current) return;
      completionNotifiedRef.current = true;
      if (onComplete) {
        onComplete(payload);
      }
    },
    [onComplete],
  );

  const fetchStatus = useCallback(
    async (id) => {
      try {
        const response = await apiClient.get(`/api/analysis/deep/status/${id}/`);
        const data = response.data;
        setStatus(data.status);
        setProgressPercent(Math.round((data.progress_percent || 0) * 10) / 10);
        setCurrentReviews(data.current_reviews || 0);
        setTargetReviews(data.target_reviews || 0);
        setTaskType(prev => data.task_type || prev || null);
        setError(null);

        if (isTerminal(data.status)) {
          stopPolling();
          if (data.status === 'success') {
            handleCompletion({
              taskId: id,
              appId: data.app_id,
              appName: data.app_name,
              taskType: data.task_type || taskType,
              resultMessage: data.result_message,
            });
          }
        }
      } catch (err) {
        stopPolling();
        setError(err.response?.data?.error || 'Unable to retrieve task status.');
      }
    },
    [handleCompletion, isTerminal, stopPolling],
  );

  const startPolling = useCallback(
    (id) => {
      stopPolling();
      fetchStatus(id);
      pollingRef.current = setInterval(() => fetchStatus(id), POLL_INTERVAL_MS);
    },
    [fetchStatus, stopPolling],
  );

  const handleStart = async () => {
    if (!appId || !projectId) {
      setError('App ID and Project ID are required to start deep analysis.');
      return;
    }

    setIsStarting(true);
    setError(null);
    completionNotifiedRef.current = false;

    try {
      const response = await apiClient.post('/api/analysis/deep/start/', {
        app_id: appId,
        project_id: projectId,
      });

      const {
        task_id: newTaskId,
        status: taskStatus,
        progress_percent: progress,
        current_reviews: current,
        target_reviews: target,
        task_type: responseTaskType,
        quick_task_in_progress: quickInProgress,
        quick_task_id: quickTaskId,
      } = response.data;

      const normalizedStatus = ['already_running', 'already_running_full'].includes(taskStatus)
        ? 'progress'
        : (taskStatus || 'pending');
      setTaskId(newTaskId);
      setStatus(normalizedStatus);
      setProgressPercent(progress || 0);
      setCurrentReviews(current || 0);
      setTargetReviews(target || 0);
      setTaskType(prev => responseTaskType || prev || null);
      startPolling(newTaskId);
    } catch (err) {
      setError(err.response?.data?.error || 'Unable to start deep analysis.');
    } finally {
      setIsStarting(false);
    }
  };

  // Resume polling if component mounts with an existing in-flight task
  useEffect(() => {
    if (initialTask?.task_id && !isTerminal(initialTask.status)) {
      setTaskId(initialTask.task_id);
      setStatus(initialTask.status);
      setProgressPercent(initialTask.progress_percent || 0);
      setCurrentReviews(initialTask.current_reviews || 0);
      setTargetReviews(initialTask.target_reviews || 0);
      setTaskType(initialTask.task_type || null);
      startPolling(initialTask.task_id);
    }
  }, [initialTask, isTerminal, startPolling]);

  // Clean up interval on unmount
  useEffect(() => () => {
    stopPolling();
  }, [stopPolling]);

  const buttonDisabled = isStarting || (!!taskId && !isTerminal(status));
  const showProgress = !!taskId && !isTerminal(status);

  return (
    <Box sx={{ mt: 3 }}>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Button
        variant="contained"
        size="large"
        onClick={handleStart}
        disabled={buttonDisabled}
        startIcon={<Psychology />}
      >
        {buttonDisabled ? 'Analysis Running…' : buttonLabel}
      </Button>

      {showProgress && (
        <Box sx={{ mt: 2 }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            Fetching additional reviews for {appName || appId}…
          </Typography>
          <LinearProgress
            variant="determinate"
            value={Math.min(100, progressPercent || 0)}
            sx={{ height: 10, borderRadius: 5 }}
          />
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
            <Typography variant="caption" color="text.secondary">
              {Math.round(progressPercent)}%
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {currentReviews}/{targetReviews || '—'} reviews processed
            </Typography>
          </Box>
          {taskType === 'full' && (
            <Typography variant="caption" color="text.secondary">
              Full analysis in progress — this step typically takes 2–3 minutes.
            </Typography>
          )}
        </Box>
      )}

      {taskId && isTerminal(status) && (
        <Box sx={{ mt: 2 }}>
          <Alert severity={status === 'success' ? 'success' : 'warning'}>
            {status === 'success'
              ? 'Deep analysis complete. Your dashboard has the latest data.'
              : 'Deep analysis ended before completion. Please review the task log.'}
          </Alert>
        </Box>
      )}
    </Box>
  );
};

DeepAnalysisProgress.propTypes = {
  appId: PropTypes.string.isRequired,
  projectId: PropTypes.number.isRequired,
  appName: PropTypes.string,
  onComplete: PropTypes.func,
  initialTask: PropTypes.shape({
    task_id: PropTypes.string,
    status: PropTypes.string,
    progress_percent: PropTypes.number,
    current_reviews: PropTypes.number,
    target_reviews: PropTypes.number,
  }),
  buttonLabel: PropTypes.string,
};

DeepAnalysisProgress.defaultProps = {
  appName: '',
  onComplete: undefined,
  initialTask: null,
  buttonLabel: 'Continue for Deeper Analysis',
};

export default DeepAnalysisProgress;
