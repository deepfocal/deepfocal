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
  Chip,
  Alert
} from '@mui/material';
import { Add } from '@mui/icons-material';
import axios from 'axios';

function ProjectManager({ onProjectSelect, selectedProject, updateTrigger }) {
  const [projects, setProjects] = useState([]);
  const [userLimits, setUserLimits] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Project creation dialog
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [newProject, setNewProject] = useState({
    name: '',
    home_app_id: '',
    home_app_name: ''
  });

  // Competitor dialog
  const [competitorDialogOpen, setCompetitorDialogOpen] = useState(false);
  const [selectedProjectForCompetitor, setSelectedProjectForCompetitor] = useState(null);
  const [newCompetitor, setNewCompetitor] = useState({
    app_id: '',
    app_name: ''
  });

  useEffect(() => {
    fetchProjects();
  }, [updateTrigger]);

  const fetchProjects = async () => {
    try {
      const response = await axios.get('http://localhost:8000/api/projects/');
      setProjects(response.data.projects);
      setUserLimits(response.data.user_limits);

      if (response.data.projects.length > 0 && !selectedProject) {
        onProjectSelect(response.data.projects[0]);
      }
    } catch (error) {
      setError('Error loading projects');
      console.error('Error fetching projects:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateProject = async () => {
    try {
      const response = await axios.post('http://localhost:8000/api/projects/create/', newProject);
      await fetchProjects();
      setCreateDialogOpen(false);
      setNewProject({ name: '', home_app_id: '', home_app_name: '' });
      onProjectSelect(response.data);
    } catch (error) {
      setError(error.response?.data?.error || 'Error creating project');
    }
  };

  const handleAddCompetitor = async () => {
    try {
      await axios.post('http://localhost:8000/api/projects/add-competitor/', {
        project_id: selectedProjectForCompetitor.id,
        ...newCompetitor
      });
      await fetchProjects();
      setCompetitorDialogOpen(false);
      setNewCompetitor({ app_id: '', app_name: '' });

      if (selectedProject && selectedProject.id === selectedProjectForCompetitor.id) {
        const updatedProject = projects.find(p => p.id === selectedProject.id);
        onProjectSelect(updatedProject);
      }
    } catch (error) {
      setError(error.response?.data?.error || 'Error adding competitor');
    }
  };

  if (loading) return <Typography>Loading projects...</Typography>;

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
              My Projects ({projects.length}/{userLimits.project_limit})
            </Typography>
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => setCreateDialogOpen(true)}
              disabled={projects.length >= userLimits.project_limit}
            >
              New Project
            </Button>
          </Box>

          <Typography variant="body2" color="text.secondary" gutterBottom>
            Subscription: {userLimits.subscription_tier?.toUpperCase()}
            • {userLimits.review_collection_limit || 500} reviews per app
            • Unlimited dashboard access
          </Typography>

          <List>
            {projects.map((project) => (
              <ListItem
                key={project.id}
                button
                selected={selectedProject?.id === project.id}
                onClick={() => onProjectSelect(project)}
                sx={{
                  border: selectedProject?.id === project.id ? '2px solid #1976d2' : '1px solid #e0e0e0',
                  borderRadius: 1,
                  mb: 1
                }}
              >
                <ListItemText
                  primary={project.name}
                  secondary={
                    <Box>
                      <Typography variant="body2">
                        Home: {project.home_app_name}
                      </Typography>
                      <Box sx={{ mt: 1 }}>
                        <Chip
                          size="small"
                          label={`${project.competitors_count} competitors`}
                          color={project.competitors_count > 0 ? 'primary' : 'default'}
                        />
                      </Box>
                    </Box>
                  }
                />
                <ListItemSecondaryAction>
                  <IconButton
                    edge="end"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedProjectForCompetitor(project);
                      setCompetitorDialogOpen(true);
                    }}
                    disabled={false} // No longer limiting competitor count, only analysis usage
                  >
                    <Add />
                  </IconButton>
                </ListItemSecondaryAction>
              </ListItem>
            ))}
          </List>

          {projects.length === 0 && (
            <Typography variant="body2" color="text.secondary" align="center" sx={{ py: 4 }}>
              No projects yet. Create your first project to get started!
            </Typography>
          )}
        </CardContent>
      </Card>

      {/* Create Project Dialog */}
      <Dialog open={createDialogOpen} onClose={() => setCreateDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Create New Project</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Project Name"
            fullWidth
            value={newProject.name}
            onChange={(e) => setNewProject({ ...newProject, name: e.target.value })}
          />
          <TextField
            margin="dense"
            label="Your App ID (e.g., com.yourcompany.app)"
            fullWidth
            value={newProject.home_app_id}
            onChange={(e) => setNewProject({ ...newProject, home_app_id: e.target.value })}
          />
          <TextField
            margin="dense"
            label="Your App Name"
            fullWidth
            value={newProject.home_app_name}
            onChange={(e) => setNewProject({ ...newProject, home_app_name: e.target.value })}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleCreateProject}
            disabled={!newProject.name || !newProject.home_app_id || !newProject.home_app_name}
          >
            Create
          </Button>
        </DialogActions>
      </Dialog>

      {/* Add Competitor Dialog */}
      <Dialog open={competitorDialogOpen} onClose={() => setCompetitorDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>
          Add Competitor to {selectedProjectForCompetitor?.name}
        </DialogTitle>
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
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCompetitorDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleAddCompetitor}
            disabled={!newCompetitor.app_id || !newCompetitor.app_name}
          >
            Add Competitor
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

export default ProjectManager;