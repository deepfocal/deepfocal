// src/CompetitorCard.jsx
import React, { useState, useEffect } from 'react';
import { Card, CardContent, Typography, Box, Chip } from '@mui/material';
import axios from 'axios';

function CompetitorCard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await axios.get('http://localhost:8000/api/competitor-analysis/');
        setData(response.data);
        setLoading(false);
      } catch (error) {
        console.error('Error fetching competitor data:', error);
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) return (
    <Card>
      <CardContent>
        <Typography variant="h6">Loading competitor data...</Typography>
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
          Competitor Comparison
        </Typography>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          {data.market_insight}
        </Typography>

        <Box sx={{ mt: 2 }}>
          {Object.entries(data.competitor_analysis).map(([appId, appData]) => (
            <Box key={appId} sx={{ mb: 2, p: 2, border: '1px solid #e0e0e0', borderRadius: 1 }}>
              <Typography variant="subtitle1" gutterBottom>
                {appId.replace('com.', '').replace('.', ' ').replace('alltrails', 'AllTrails')}
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                <Chip
                  label={`${appData.positive_percentage}% Positive`}
                  color="success"
                  variant="outlined"
                />
                <Chip
                  label={`${appData.negative_percentage}% Negative`}
                  color="error"
                  variant="outlined"
                />
                <Chip
                  label={`${appData.total_reviews} Reviews`}
                  variant="outlined"
                />
              </Box>
            </Box>
          ))}
        </Box>
      </CardContent>
    </Card>
  );
}

export default CompetitorCard;