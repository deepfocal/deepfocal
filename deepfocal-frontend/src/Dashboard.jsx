import PainPointsCard from './PainPointsCard';
import CompetitorCard from './CompetitorCard';
// src/Dashboard.jsx
import React from 'react';
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
  Container
} from '@mui/material';

const drawerWidth = 240;

function Dashboard() {
  return (
    <Box sx={{ display: 'flex' }}>
      {/* Header */}
      <AppBar position="fixed" sx={{ zIndex: 1201 }}>
        <Toolbar>
          <Typography variant="h6" component="div">
            Deepfocal
          </Typography>
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
        <Box sx={{ overflow: 'auto' }}>
          <List>
            <ListItem>
              <ListItemText primary="Overview" />
            </ListItem>
            <ListItem>
              <ListItemText primary="Competitor Analysis" />
            </ListItem>
            <ListItem>
              <ListItemText primary="Pain Points" />
            </ListItem>
            <ListItem>
              <ListItemText primary="Trends" />
            </ListItem>
          </List>
        </Box>
      </Drawer>

      {/* Main Content */}
      <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
        <Toolbar />
        <Container maxWidth="xl">
          <Typography variant="h4" gutterBottom>
            Review Intelligence Dashboard
          </Typography>

          <Grid container spacing={3}>
            {/* Placeholder cards for future charts */}
            <Grid item xs={12} md={6}>
  <CompetitorCard />
</Grid>

            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Competitor Comparison
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    How your sentiment compares to competitors
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12}>
  <PainPointsCard />
</Grid>
          </Grid>
        </Container>
      </Box>
    </Box>
  );
}

export default Dashboard;