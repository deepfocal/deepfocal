// src/PainPointsCard.jsx
import React, { useState, useEffect } from 'react';
import { Card, CardContent, Typography, Box, Chip } from '@mui/material';
import axios from 'axios';

function PainPointsCard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await axios.get('http://localhost:8000/api/insights/');
        setData(response.data);
        setLoading(false);
      } catch (error) {
        console.error('Error fetching insights data:', error);
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) return (
    <Card>
      <CardContent>
        <Typography variant="h6">Loading pain points...</Typography>
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
          Top Pain Points
        </Typography>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          Most frequently mentioned issues in {data.sentiment_breakdown.negative_count} negative reviews
        </Typography>

        <Box sx={{ mt: 2 }}>
          {data.top_pain_points.length > 0 ? (
            data.top_pain_points.map((painPoint, index) => (
              <Box key={index} sx={{ mb: 2, p: 2, border: '1px solid #e0e0e0', borderRadius: 1 }}>
                <Typography variant="subtitle1" gutterBottom>
                  #{index + 1} {painPoint.issue}
                </Typography>
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  <Chip
                    label={`${painPoint.mentions} mentions`}
                    color="warning"
                    variant="outlined"
                  />
                  <Chip
                    label={`${painPoint.percentage_of_negative}% of negative reviews`}
                    variant="outlined"
                  />
                </Box>
              </Box>
            ))
          ) : (
            <Typography variant="body2" color="text.secondary">
              No significant pain points detected in current dataset.
            </Typography>
          )}
        </Box>
      </CardContent>
    </Card>
  );
}

export default PainPointsCard;