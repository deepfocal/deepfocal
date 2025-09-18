// src/CompetitorCard.jsx - Fixed infinite reloading loop
import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, Typography, Box, Chip, LinearProgress, Button } from '@mui/material';
import { Refresh, Psychology } from '@mui/icons-material';
import axios from 'axios';

// Progressive disclosure states based on review count and task status
const getProgressiveState = (reviewCount, activeTasks, appId) => {
  const hasActiveTask = activeTasks.some(task => task.app_id === appId);

  if (hasActiveTask) {
    const task = activeTasks.find(task => task.app_id === appId);
    if (task.task_type === 'quick') {
      return 'collecting_initial';
    } else {
      return 'collecting_full';
    }
  }

  if (reviewCount < 50) {
    return 'no_data';
  } else if (reviewCount >= 50 && reviewCount < 300) {
    return 'initial_ready';
  } else if (reviewCount >= 300 && reviewCount < 800) {
    return 'quick_complete';
  } else {
    return 'full_complete';
  }
};

function CompetitorCard({ selectedProject, updateTrigger }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTasks, setActiveTasks] = useState([]);
  const [isPolling, setIsPolling] = useState(false);

  // Use refs to prevent dependency loops
  const pollingRef = useRef(null);
  const lastUpdateTriggerRef = useRef(0);
  const selectedProjectRef = useRef(null);

  // Simple fetch function without useCallback to prevent loops
  const fetchProjectStatus = async (isManual = false) => {
    if (!selectedProjectRef.current) return;

    try {
      if (isManual) setRefreshing(true);

      const response = await axios.get(`http://localhost:8000/api/projects/${selectedProjectRef.current.id}/status/`);

      setData(response.data);
      setActiveTasks(response.data.active_tasks || []);

      // Simple polling control
      const hasActiveTasks = response.data.has_active_tasks;

      if (hasActiveTasks && !pollingRef.current) {
        console.log('Starting polling');
        setIsPolling(true);
        pollingRef.current = setInterval(() => {
          fetchProjectStatus(false);
        }, 3000);
      } else if (!hasActiveTasks && pollingRef.current) {
        console.log('Stopping polling');
        clearInterval(pollingRef.current);
        pollingRef.current = null;
        setIsPolling(false);
      }

    } catch (error) {
      console.error('Error fetching project status:', error);
    } finally {
      setLoading(false);
      if (isManual) setRefreshing(false);
    }
  };

  // Start analysis function
  const startAnalysis = async (appId, appName, analysisType = 'full') => {
    try {
      console.log(`Starting ${analysisType} analysis for ${appName}`);

      const response = await axios.post('http://localhost:8000/api/analysis/start/', {
        app_id: appId,
        analysis_type: analysisType,
        project_id: selectedProjectRef.current.id
      });

      console.log('Analysis started:', response.data);

      // Refresh after a short delay
      setTimeout(() => fetchProjectStatus(false), 500);

    } catch (error) {
      console.error('Error starting analysis:', error);
      if (error.response?.status === 409) {
        fetchProjectStatus(false);
      }
    }
  };

  // Update project ref when it changes
  useEffect(() => {
    selectedProjectRef.current = selectedProject;
  }, [selectedProject]);

  // Handle project changes - SIMPLE effect
  useEffect(() => {
    if (selectedProject) {
      setLoading(true);
      fetchProjectStatus(false);
    }

    // Cleanup function
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
        setIsPolling(false);
      }
    };
  }, [selectedProject?.id]); // Only depend on project ID

  // Handle external update triggers - SEPARATE effect
  useEffect(() => {
    if (updateTrigger !== lastUpdateTriggerRef.current && updateTrigger > 0 && !isPolling) {
      lastUpdateTriggerRef.current = updateTrigger;
      console.log('External update trigger');
      fetchProjectStatus(false);
    }
  }, [updateTrigger, isPolling]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, []);

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6">Loading competitor data...</Typography>
        </CardContent>
      </Card>
    );
  }

  if (!selectedProject || !data) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6">Select a project to view analysis</Typography>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Typography variant="h6">Competitor Analysis</Typography>
          <Button
            variant="outlined"
            size="small"
            startIcon={<Refresh />}
            onClick={() => fetchProjectStatus(true)}
            disabled={refreshing}
          >
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </Button>
        </Box>

        <Typography variant="body2" color="text.secondary" gutterBottom>
          {data.project_info?.project_name} - {data.project_info?.competitors_count} competitors
        </Typography>

        {/* Active Tasks Global Indicator */}
        {activeTasks.length > 0 && (
          <Box sx={{ mt: 2, mb: 2, p: 2, bgcolor: 'primary.lighter', borderRadius: 1 }}>
            <Typography variant="body2" color="primary.main" sx={{ fontWeight: 'bold' }}>
              ⚡ Progressive Analysis Active - {activeTasks.length} task(s) running
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Quick insights in ~30 seconds, full analysis in ~2-3 minutes
            </Typography>
          </Box>
        )}

        <Box sx={{ mt: 2 }}>
          {Object.entries(data.competitor_analysis).map(([appId, appData]) => {
            const progressiveState = getProgressiveState(appData.total_reviews, activeTasks, appId);
            const activeTask = activeTasks.find(task => task.app_id === appId);
            const tierReviewLimit = appData.review_limit ?? data.review_limit ?? null;
            const hasReachedLimit = tierReviewLimit !== null && appData.total_reviews >= tierReviewLimit;
            const tierLabel = data.subscription_tier
              ? data.subscription_tier.toUpperCase()
              : 'CURRENT';
            const buttonLabel = hasReachedLimit
              ? 'Review Limit Reached'
              : progressiveState === 'initial_ready'
                ? 'Start Analysis'
                : 'Continue Analysis';

            return (
              <Box
                key={appId}
                sx={{
                  mb: 2,
                  p: 2,
                  border: appData.app_type === 'home' ? '2px solid #1976d2' : '1px solid #e0e0e0',
                  borderRadius: 1,
                  bgcolor: appData.app_type === 'home' ? 'rgba(25, 118, 210, 0.04)' : 'inherit',
                }}
              >
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <Typography variant="subtitle1" gutterBottom>
                    {appData.app_name} {appData.app_type === 'home' && '(Your App)'}

                    {/* Progressive State Indicators */}
                    {progressiveState === 'no_data' && (
                      <Chip size="small" label="Initializing" color="default" variant="outlined" sx={{ ml: 1 }} />
                    )}
                    {progressiveState === 'initial_ready' && (
                      <Chip size="small" label="Initial Data" color="info" variant="outlined" sx={{ ml: 1 }} />
                    )}
                    {progressiveState === 'quick_complete' && (
                      <Chip size="small" label="Quick Analysis" color="primary" variant="outlined" sx={{ ml: 1 }} />
                    )}
                    {progressiveState === 'full_complete' && (
                      <Chip size="small" label="Full Analysis" color="success" variant="outlined" sx={{ ml: 1 }} />
                    )}
                  </Typography>

                  {/* Action Buttons Based on State */}
                  {(progressiveState === 'initial_ready' || progressiveState === 'quick_complete') && (
                    <Button
                      size="small"
                      variant="contained"
                      color="primary"
                      startIcon={<Psychology />}
                      onClick={() => startAnalysis(appId, appData.app_name, 'full')}
                      disabled={hasReachedLimit}
                    >
                      {buttonLabel}
                    </Button>
                  )}

                  {(progressiveState === 'collecting_initial' || progressiveState === 'collecting_full') && (
                    <Button size="small" variant="contained" color="warning" disabled>
                      🔄 Analyzing...
                    </Button>
                  )}
                </Box>

                {/* Review Statistics */}
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 1 }}>
                  <Chip label={`${appData.positive_percentage}% Positive`} color="success" variant="outlined" />
                  <Chip label={`${appData.negative_percentage}% Negative`} color="error" variant="outlined" />
                  <Chip label={`${appData.neutral_percentage}% Neutral`} variant="outlined" />
                  <Chip label={`${appData.total_reviews} Reviews`} variant="outlined" />
                  {tierReviewLimit !== null && (
                    <Chip
                      label={`${Math.min(appData.total_reviews, tierReviewLimit)}/${tierReviewLimit} Tier Limit`}
                      color={hasReachedLimit ? 'warning' : 'default'}
                      variant={hasReachedLimit ? 'filled' : 'outlined'}
                    />
                  )}
                </Box>

                {/* Progress Display for Active Tasks */}
                {activeTask && (
                  <Box sx={{ mt: 2, p: 2, bgcolor: 'rgba(255, 152, 0, 0.08)', borderRadius: 1 }}>
                    <Typography variant="body2" color="warning.main" sx={{ mb: 1, fontWeight: 'bold' }}>
                      🔄 {activeTask.task_type === 'quick' ? 'Quick Analysis' : 'Full Analysis'} in Progress
                    </Typography>

                    <Box sx={{ mb: 1 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                        <Typography variant="body2">
                          Reviews: {activeTask.current_reviews}/{activeTask.target_reviews}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {Math.round(activeTask.progress_percent)}%
                        </Typography>
                      </Box>

                      <LinearProgress
                        variant="determinate"
                        value={activeTask.progress_percent}
                        sx={{
                          height: 8,
                          borderRadius: 4,
                          backgroundColor: 'rgba(255, 152, 0, 0.2)',
                          '& .MuiLinearProgress-bar': {
                            backgroundColor: '#ff9800',
                          }
                        }}
                      />
                    </Box>

                    <Typography variant="caption" color="text.secondary">
                      {activeTask.task_type === 'quick'
                        ? "Collecting initial insights for quick analysis (~30 seconds)"
                        : "Collecting comprehensive data for detailed analysis (~2-3 minutes)"
                      }
                    </Typography>
                  </Box>
                )}

                {/* Success Messages */}
                {progressiveState === 'quick_complete' && !activeTask && !hasReachedLimit && (
                  <Box sx={{ mt: 2, p: 1.5, bgcolor: 'rgba(76, 175, 80, 0.08)', borderRadius: 1 }}>
                    <Typography variant="body2" color="success.main" sx={{ fontWeight: 'medium' }}>
                      🎉 Quick analysis complete! Got insights in ~30 seconds. Click "Continue Analysis" for deeper insights.
                    </Typography>
                  </Box>
                )}

                {progressiveState === 'full_complete' && !activeTask && (
                  <Box sx={{ mt: 2, p: 1.5, bgcolor: 'rgba(76, 175, 80, 0.08)', borderRadius: 1 }}>
                    <Typography variant="body2" color="success.main" sx={{ fontWeight: 'medium' }}>
                      ✅ Full analysis complete! Comprehensive insights available with {appData.total_reviews} reviews.
                    </Typography>
                  </Box>
                )}

                {hasReachedLimit && !activeTask && (
                  <Box sx={{ mt: 2, p: 1.5, bgcolor: 'rgba(255, 193, 7, 0.12)', borderRadius: 1 }}>
                    <Typography variant="body2" color="warning.main" sx={{ fontWeight: 'medium' }}>
                      Review limit reached for your {tierLabel === 'CURRENT' ? 'current plan' : `${tierLabel} plan`}. Upgrade to analyze more reviews.
                    </Typography>
                  </Box>
                )}
              </Box>
            );
          })}
        </Box>

        {/* Debug Info */}
        {process.env.NODE_ENV === 'development' && (
          <Box sx={{ mt: 2, p: 1, bgcolor: 'grey.100', borderRadius: 1 }}>
            <Typography variant="caption">
              Active Tasks: {activeTasks.length} | Polling: {isPolling ? 'ON' : 'OFF'}
            </Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  );
}

export default CompetitorCard;
