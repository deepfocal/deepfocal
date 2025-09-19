import React, { useState, useEffect, useMemo } from 'react';
import PropTypes from 'prop-types';
import { Box, Typography, Chip, CircularProgress, Alert } from '@mui/material';
import apiClient from './apiClient';

const PainPointsList = ({ appId, appIds, appName, refreshKey, emptyMessage }) => {
  const [loading, setLoading] = useState(true);
  const [insights, setInsights] = useState([]);
  const [reviewCount, setReviewCount] = useState(0);
  const [error, setError] = useState(null);

  const requestedIds = useMemo(() => {
    if (Array.isArray(appIds) && appIds.length) {
      return appIds.filter(Boolean);
    }
    if (appId) {
      return [appId];
    }
    return [];
  }, [appId, appIds]);

  const combinedView = requestedIds.length > 1;
  const targetLabel = appName || (combinedView ? 'Combined Platforms' : requestedIds[0] || '');

  useEffect(() => {
    if (!requestedIds.length) {
      setLoading(false);
      setInsights([]);
      setReviewCount(0);
      return;
    }

    let isMounted = true;

    const fetchInsights = async () => {
      try {
        setLoading(true);
        const params = { app_id: requestedIds };
        const response = await apiClient.get('/api/enhanced-insights/', {
          params,
          paramsSerializer: (queryParams) => {
            const searchParams = new URLSearchParams();
            const ids = Array.isArray(queryParams.app_id) ? queryParams.app_id : [queryParams.app_id];
            ids.filter(Boolean).forEach((id) => searchParams.append('app_id', id));
            return searchParams.toString();
          },
        });

        if (!isMounted) {
          return;
        }

        const data = response.data || {};
        const painPoints = data.lda_pain_points || [];
        setInsights(painPoints);
        setReviewCount(data.review_count_analyzed || 0);
        setError(data.error || null);
      } catch (fetchError) {
        if (!isMounted) {
          return;
        }
        console.error('Error fetching pain point insights:', fetchError);
        setError('Unable to load pain points right now.');
        setInsights([]);
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchInsights();

    return () => {
      isMounted = false;
    };
  }, [requestedIds, refreshKey]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 1 }}>
        <CircularProgress size={18} thickness={5} />
        <Typography variant="body2" color="text.secondary">
          Analyzing feedback for {targetLabel}...
        </Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="warning" sx={{ mt: 1 }}>
        {error}
      </Alert>
    );
  }

  if (!insights.length) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
        {emptyMessage || 'No significant pain points detected yet.'}
      </Typography>
    );
  }

  return (
    <Box sx={{ mt: 1 }}>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
        Derived from {reviewCount} negative reviews
      </Typography>
      {insights.map((point, index) => {
        const shareSource = typeof point.review_percentage === 'number'
          ? point.review_percentage
          : reviewCount
            ? (point.review_count / reviewCount) * 100
            : 0;
        const shareValue = Number.isFinite(shareSource) ? shareSource : 0;
        const shareFormatted = shareValue.toFixed(1).replace(/\.0$/, '');
        const shareLabel = `${point.review_count} mentions (${shareFormatted}% of negative reviews)`;
        const coherenceScore = typeof point.coherence_score === 'number'
          ? point.coherence_score.toFixed(1)
          : 'N/A';
        const keywordList = Array.isArray(point.keywords) ? point.keywords.join(', ') : '';
        const averageRating = typeof point.average_rating === 'number'
          ? point.average_rating.toFixed(1)
          : null;

        return (
          <Box key={`${requestedIds.join('-')}-pain-${index}`} sx={{ mb: 2, p: 1.5, border: '1px solid #e0e0e0', borderRadius: 1 }}>
            <Typography variant="subtitle2" gutterBottom>
              #{index + 1} {point.issue}
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 1 }}>
              <Chip
                label={`Keywords: ${keywordList}`}
                color="warning"
                variant="outlined"
                size="small"
              />
              <Chip
                label={`Coherence: ${coherenceScore}`}
                variant="outlined"
                size="small"
              />
              <Chip
                label={shareLabel}
                variant="outlined"
                size="small"
              />
              {averageRating !== null && (
                <Chip
                  label={`Avg rating: ${averageRating} stars`}
                  variant="outlined"
                  size="small"
                />
              )}
            </Box>
            {point.representative_review && (
              <Typography variant="body2" color="text.secondary">
                "{point.representative_review}"
              </Typography>
            )}
          </Box>
        );
      })}
    </Box>
  );
};

PainPointsList.propTypes = {
  appId: PropTypes.string,
  appIds: PropTypes.arrayOf(PropTypes.string),
  appName: PropTypes.string,
  refreshKey: PropTypes.oneOfType([
    PropTypes.number,
    PropTypes.string,
  ]),
  emptyMessage: PropTypes.string,
};

PainPointsList.defaultProps = {
  appId: '',
  appIds: null,
  appName: '',
  refreshKey: null,
  emptyMessage: null,
};

export default PainPointsList;
