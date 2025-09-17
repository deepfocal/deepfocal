import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Alert,
  Divider
} from '@mui/material';
import { Add, Delete } from '@mui/icons-material';
import axios from 'axios';

function CompetitorManager({ selectedProject, onProjectUpdate }) {
  const [competitors, setCompetitors] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Add competitor dialog
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [newCompetitor, setNewCompetitor] = useState({
    app_id: '',
    app_name: ''
  });

  useEffect(() => {
    if (selectedProject) {
      fetchProjectDetails();
    }
  }, [selectedProject]);

  const fetchProjectDetails = async () => {
    if (!selectedProject) return;

    try {
      setLoading(true);
      const response = await axios.get(`http://localhost:8000/api/projects/${selectedProject.id}/`);
      setCompetitors(response.data.competitors);
    } catch (error) {
      setError('Error loading project details');
      console.error('Error fetching project details:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAddCompetitor = async () => {
    try {
      setLoading(true);
      const response = await axios.post('http://localhost:8000/api/projects/add-competitor/', {
        project_id: selectedProject.id,
        ...newCompetitor
      });

      // Refresh project details to get updated competitor list
      await fetchProjectDetails();

      // Notify parent component of project update
      if (onProjectUpdate) {
        onProjectUpdate();
      }

      setAddDialogOpen(false);
      setNewCompetitor({ app_id: '', app_name: '' });

      // Show success message with import status
      if (response.data.review_import?.status === 'started') {
        setError(''); // Clear any previous errors
        // You could add a success notification here
      }
    } catch (error) {
      setError(error.response?.data?.error || 'Error adding competitor');
    } finally {
      setLoading(false);
    }
  };

  const handleRemoveCompetitor = async (competitorId, competitorName) => {
    if (!window.confirm(`Are you sure you want to remove ${competitorName} from this project?`)) {
      return;
    }

    try {
      setLoading(true);
      await axios.delete(`http://localhost:8000/api/competitors/${competitorId}/delete/`);

      // Refresh project details
      await fetchProjectDetails();

      // Notify parent component of project update
      if (onProjectUpdate) {
        onProjectUpdate();
      }
    } catch (error) {
      setError(error.response?.data?.error || 'Error removing competitor');
    } finally {
      setLoading(false);
    }
  };

  if (!selectedProject) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Competitor Management
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Select a project to manage competitors
          </Typography>
        </CardContent>
      </Card>
    );
  }

  return (
    <Box>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      <Card>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6">
              Competitors ({competitors.length})
            </Typography>
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => setAddDialogOpen(true)}
              disabled={loading}
              size="small"
            >
              Add Competitor
            </Button>
          </Box>

          <Typography variant="body2" color="text.secondary" gutterBottom>
            Project: {selectedProject.name}
          </Typography>

          {/* Home App */}
          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              Your App:
            </Typography>
            <Box sx={{ p: 2, bgcolor: 'rgba(25, 118, 210, 0.04)', border: '1px solid #1976d2', borderRadius: 1 }}>
              <Typography variant="body1">
                {selectedProject.home_app_name}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {selectedProject.home_app_id}
              </Typography>
            </Box>
          </Box>

          <Divider sx={{ my: 2 }} />

          {/* Competitors List */}
          <Typography variant="subtitle2" gutterBottom>
            Competitors:
          </Typography>

          {competitors.length === 0 ? (
            <Typography variant="body2" color="text.secondary" align="center" sx={{ py: 4 }}>
              No competitors added yet. Add competitors to start competitive analysis!
            </Typography>
          ) : (
            <List>
              {competitors.map((competitor) => (
                <ListItem
                  key={competitor.id}
                  sx={{
                    border: '1px solid #e0e0e0',
                    borderRadius: 1,
                    mb: 1
                  }}
                >
                  <ListItemText
                    primary={competitor.app_name}
                    secondary={
                      <Box>
                        <Typography variant="body2">
                          {competitor.app_id}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Added: {new Date(competitor.added_at).toLocaleDateString()}
                        </Typography>
                      </Box>
                    }
                  />
                  <ListItemSecondaryAction>
                    <IconButton
                      edge="end"
                      onClick={() => handleRemoveCompetitor(competitor.id, competitor.app_name)}
                      disabled={loading}
                      color="error"
                    >
                      <Delete />
                    </IconButton>
                  </ListItemSecondaryAction>
                </ListItem>
              ))}
            </List>
          )}
        </CardContent>
      </Card>

      {/* Add Competitor Dialog */}
      <Dialog open={addDialogOpen} onClose={() => setAddDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Add Competitor</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Competitor App ID (e.g., com.competitor.app)"
            fullWidth
            value={newCompetitor.app_id}
            onChange={(e) => setNewCompetitor({ ...newCompetitor, app_id: e.target.value })}
          />
          <TextField
            margin="dense"
            label="Competitor App Name"
            fullWidth
            value={newCompetitor.app_name}
            onChange={(e) => setNewCompetitor({ ...newCompetitor, app_name: e.target.value })}
          />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            We'll automatically import the latest reviews for competitive analysis.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAddDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleAddCompetitor}
            disabled={!newCompetitor.app_id || !newCompetitor.app_name || loading}
          >
            Add & Import Reviews
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

export default CompetitorManager;