// src/PainPointsCard.jsx
import React, { useState, useEffect } from 'react';
import { Card, CardContent, Typography, Box, Chip } from '@mui/material';
import axios from 'axios';

function PainPointsCard({ selectedProject, updateTrigger }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!selectedProject) {
      setLoading(false);
      return;
    }

    const fetchData = async () => {
      try {
        setLoading(true);
        const response = await axios.get(`http://localhost:8000/api/enhanced-insights/?app_id=${selectedProject.home_app_id}`);
        setData(response.data);
        setLoading(false);
      } catch (error) {
        console.error('Error fetching insights data:', error);
        setLoading(false);
      }
    };

    fetchData();
  }, [selectedProject, updateTrigger]);

  if (loading) return (
    <Card>
      <CardContent>
        <Typography variant="h6">Loading pain points...</Typography>
      </CardContent>
    </Card>
  );

  if (!selectedProject) return (
    <Card>
      <CardContent>
        <Typography variant="h6">Select a project to view pain points</Typography>
      </CardContent>
    </Card>
  );

  if (!data) return (
    <Card>
      <CardContent>
        <Typography variant="h6">Error loading data</Typography>
      </CardContent>
    </Card>
  );

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Top Pain Points - {selectedProject.home_app_name}
        </Typography>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          LDA-discovered themes from {data.review_count_analyzed} negative reviews
        </Typography>

        <Box sx={{ mt: 2 }}>
          {data.lda_pain_points && data.lda_pain_points.length > 0 ? (
            data.lda_pain_points.map((painPoint, index) => (
              <Box key={index} sx={{ mb: 2, p: 2, border: '1px solid #e0e0e0', borderRadius: 1 }}>
                <Typography variant="subtitle1" gutterBottom>
                  #{index + 1} {painPoint.issue}
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
        </Box>      </CardContent>
    </Card>
  );
}

export default PainPointsCard;