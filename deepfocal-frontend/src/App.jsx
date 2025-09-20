import React from 'react';
import { AuthProvider, useAuth } from './AuthContext';
import { TaskProvider } from './contexts/TaskContext'; // Add this import
import LoginForm from './LoginForm';
import PremiumDashboard from './dashboard/PremiumDashboard';
import ClassicDashboard from './legacy/ClassicDashboard';

function LoadingScreen() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-background">
      <div className="h-12 w-12 animate-spin rounded-full border-4 border-primary/20 border-t-primary" />
    </div>
  );
}

function AppContent() {
  const { isAuthenticated, loading, user } = useAuth();

  if (loading) {
    return <LoadingScreen />;
  }

  if (!isAuthenticated) {
    return <LoginForm />;
  }

  const enablePremium = Boolean(user?.enable_premium_dashboard);

  // Wrap the dashboards with TaskProvider
  return (
    <TaskProvider>
      {enablePremium ? <PremiumDashboard /> : <ClassicDashboard />}
    </TaskProvider>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;