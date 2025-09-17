import React, { useState } from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Drawer,
  Box,
  Card,
  CardContent,
  Grid,
  List,
  ListItem,
  ListItemText,
  Container,
  Button,
  IconButton
} from '@mui/material';
import { Logout } from '@mui/icons-material';
import { useAuth } from './AuthContext';
import ProjectManager from './ProjectManager';
import CompetitorManager from './CompetitorManager';
import PainPointsCard from './PainPointsCard';
import CompetitorCard from './CompetitorCard';

const drawerWidth = 240;

function Dashboard() {
  const [selectedProject, setSelectedProject] = useState(null);
  const [projectUpdateTrigger, setProjectUpdateTrigger] = useState(0);
  const { user, logout } = useAuth();

  const handleProjectUpdate = () => {
    setProjectUpdateTrigger(prev => prev + 1);
  };

  return (
    <Box sx={{ display: 'flex' }}>
      {/* Header */}
      <AppBar position="fixed" sx={{ zIndex: 1201 }}>
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            Deepfocal
          </Typography>
          <Typography variant="body2" sx={{ mr: 2 }}>
            {user?.username} ({user?.subscription_tier})
          </Typography>
          <IconButton color="inherit" onClick={logout}>
            <Logout />
          </IconButton>
        </Toolbar>
      </AppBar>

      {/* Sidebar */}
      <Drawer
        variant="permanent"
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: drawerWidth,
            boxSizing: 'border-box',
          },
        }}
      >
        <Toolbar />
        <Box sx={{ overflow: 'auto', p: 2 }}>
          <ProjectManager
            onProjectSelect={setSelectedProject}
            selectedProject={selectedProject}
            updateTrigger={projectUpdateTrigger}
          />

          {selectedProject && (
            <Box sx={{ mt: 2 }}>
              <CompetitorManager
                selectedProject={selectedProject}
                onProjectUpdate={handleProjectUpdate}
              />
            </Box>
          )}
        </Box>
      </Drawer>

      {/* Main Content */}
      <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
        <Toolbar />
        <Container maxWidth="xl">
          {selectedProject ? (
            <>
              <Typography variant="h4" gutterBottom>
                {selectedProject.name}
              </Typography>
              <Typography variant="body1" color="text.secondary" gutterBottom>
                Analyzing {selectedProject.home_app_name} vs {selectedProject.competitors_count} competitors
              </Typography>

              <Grid container spacing={3}>
                <Grid item xs={12} md={6}>
                  <CompetitorCard
                    selectedProject={selectedProject}
                    updateTrigger={projectUpdateTrigger}
                  />
                </Grid>

                <Grid item xs={12} md={6}>
                  <PainPointsCard
                    selectedProject={selectedProject}
                    updateTrigger={projectUpdateTrigger}
                  />
                </Grid>
              </Grid>
            </>
          ) : (
            <Box sx={{ textAlign: 'center', mt: 8 }}>
              <Typography variant="h5" gutterBottom>
                Welcome to Deepfocal
              </Typography>
              <Typography variant="body1" color="text.secondary">
                Select a project from the sidebar to view competitive intelligence
              </Typography>
            </Box>
          )}
        </Container>
      </Box>
    </Box>
  );
}

export default Dashboard;