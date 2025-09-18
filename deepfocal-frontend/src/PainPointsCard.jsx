// src/PainPointsCard.jsx
import React, { useState, useEffect } from 'react';
import { Card, CardContent, Typography, Box, Chip, Divider } from '@mui/material';
import axios from 'axios';

function PainPointsCard({ selectedProject, updateTrigger }) {
  const [appPainPoints, setAppPainPoints] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!selectedProject) {
      setLoading(false);
      setAppPainPoints([]);
      setError('');
      return;
    }

    let isCancelled = false;

    const fetchPainPointsOverview = async () => {
      try {
        setLoading(true);
        setError('');

        const statusResponse = await axios.get(
          `http://localhost:8000/api/projects/${selectedProject.id}/status/`
        );

        const analysis = statusResponse.data?.competitor_analysis || {};
        const apps = Object.entries(analysis).map(([appId, appData]) => ({
          app_id: appId,
          app_name: appData.app_name,
          app_type: appData.app_type,
          total_reviews: appData.total_reviews,
          negative_count: appData.negative_count,
          review_limit: appData.review_limit,
          can_collect_more: appData.can_collect_more,
          remaining_reviews: appData.remaining_reviews
        }));

        if (apps.length === 0) {
          if (!isCancelled) {
            setAppPainPoints([]);
          }
          return;
        }

        const painPointResults = await Promise.all(
          apps.map(async (app) => {
            try {
              const response = await axios.get(
                `http://localhost:8000/api/enhanced-insights/?app_id=${app.app_id}`
              );

              return {
                ...app,
                ...response.data,
                error: response.data.error || ''
              };
            } catch (insightsError) {
              console.error(`Error fetching pain points for ${app.app_name}:`, insightsError);
              return {
                ...app,
                lda_pain_points: [],
                review_count: 0,
                raw_review_count: app.negative_count ?? 0,
                usable_review_count: 0,
                filtered_out_reviews: app.negative_count ?? 0,
                review_count_analyzed: 0,
                error: 'Unable to load pain points. Analysis may still be running.'
              };
            }
          })
        );

        if (!isCancelled) {
          setAppPainPoints(painPointResults);
        }
      } catch (statusError) {
        console.error('Error fetching pain points overview:', statusError);
        if (!isCancelled) {
          setError('Unable to load pain points overview. Try refreshing after analysis completes.');
          setAppPainPoints([]);
        }
      } finally {
        if (!isCancelled) {
          setLoading(false);
        }
      }
    };

    fetchPainPointsOverview();

    return () => {
      isCancelled = true;
    };
  }, [selectedProject?.id, updateTrigger]);

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6">Loading pain points...</Typography>
        </CardContent>
      </Card>
    );
  }

  if (!selectedProject) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6">Select a project to view pain points</Typography>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6">Pain Points Overview</Typography>
          <Typography variant="body2" color="error">
            {error}
          </Typography>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Pain Points Overview
        </Typography>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          Automatically discovered themes for your app and competitors
        </Typography>

        {appPainPoints.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            No review data available yet. Start or refresh an analysis to populate pain points.
          </Typography>
        ) : (
          <Box sx={{ mt: 2 }}>
            {appPainPoints.map((app, index) => {
              const rawCount = app.raw_review_count ?? app.review_count_analyzed ?? 0;
              const usableCount = app.review_count_analyzed ?? app.usable_review_count ?? 0;
              const filteredOut = app.filtered_out_reviews ?? Math.max(rawCount - usableCount, 0);

              return (
                <Box key={app.app_id} sx={{ mb: 3 }}>
                  <Typography variant="subtitle1" gutterBottom>
                    {app.app_name} {app.app_type === 'home' ? '(Your App)' : '(Competitor)'}
                  </Typography>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    display="block"
                    gutterBottom
                  >
                    {app.app_id} • {(app.negative_count ?? 0)} negative / {(app.total_reviews ?? 0)} total reviews
                  </Typography>

                  {app.error ? (
                    <Typography variant="body2" color="error">
                      {app.error}
                    </Typography>
                  ) : (
                    <>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        {filteredOut > 0
                          ? `LDA-discovered themes from ${usableCount} detailed negative reviews (filtered out ${filteredOut} short or low-signal reviews).`
                          : `LDA-discovered themes from ${usableCount} negative reviews.`}
                      </Typography>

                      {app.lda_pain_points && app.lda_pain_points.length > 0 ? (
                        app.lda_pain_points.map((painPoint, painIndex) => (
                          <Box
                            key={`${app.app_id}-${painIndex}`}
                            sx={{ mb: 1.5, p: 2, border: '1px solid #e0e0e0', borderRadius: 1 }}
                          >
                            <Typography variant="subtitle2" gutterBottom>
                              #{painIndex + 1} {painPoint.issue}
                            </Typography>
                            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                              <Chip
                                label={`Keywords: ${painPoint.keywords.join(', ')}`}
                                color="warning"
                                variant="outlined"
                              />
                              <Chip
                                label={`Coherence: ${painPoint.coherence_score.toFixed(1)}`}
                                variant="outlined"
                              />
                            </Box>
                          </Box>
                        ))
                      ) : (
                        <Typography variant="body2" color="text.secondary">
                          No significant pain points detected.
                        </Typography>
                      )}
                    </>
                  )}

                  {index !== appPainPoints.length - 1 && <Divider sx={{ mt: 2 }} />}
                </Box>
              );
            })}
          </Box>
        )}
      </CardContent>
    </Card>
  );
}

export default PainPointsCard;
