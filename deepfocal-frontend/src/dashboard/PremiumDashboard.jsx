import { useTask } from '../contexts/TaskContext';
import LoadingOverlay from '../components/LoadingOverlay';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  LayoutDashboard,
  BarChart3,
  Activity,
  Search,
  Bookmark,
  Settings,
  Bell,
  ChevronDown,
  TrendingUp,
  TrendingDown,
  Calendar,
  Plus,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Trash2,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import clsx from 'clsx';
import apiClient from '../apiClient';
import { useAuth } from '../AuthContext';
import MarketMentionsSection from './MarketMentionsSection';

const clamp = (value, min = 0, max = 100) => Math.max(min, Math.min(max, value));

const toneBadgeClasses = {
  primary: 'bg-primary/10 text-primary',
  warning: 'bg-warning/10 text-warning',
  danger: 'bg-danger/10 text-danger',
};

const toneValueClasses = {
  primary: 'text-primary',
  warning: 'text-warning',
  danger: 'text-danger',
};

const SIDEBAR_PREF_KEY = 'premium-dashboard.sidebarCollapsed';

const getStoredSidebarPref = () => {
  if (typeof window === 'undefined') {
    return false;
  }
  return window.localStorage.getItem(SIDEBAR_PREF_KEY) === 'true';
};

const navigationItems = [
  {
    group: 'Analytics Suite',
    items: [
      { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
      { id: 'competitor-analysis', label: 'Competitor Analysis', icon: BarChart3 },
      { id: 'pain-points', label: 'Pain Points & Strengths', icon: Activity },
    ],
  },
  {
    group: 'Research Tools',
    items: [
      { id: 'review-explorer', label: 'Review Explorer', icon: Search },
      { id: 'collections', label: 'Collections', icon: Bookmark },
    ],
  },
  {
    group: 'Configuration',
    items: [
      { id: 'project-settings', label: 'Project Settings', icon: Settings },
      { id: 'alerts', label: 'Alerts', icon: Bell },
    ],
  },
];

const dateRanges = [
  { value: '7d', label: 'Last 7 Days' },
  { value: '30d', label: 'Last 30 Days' },
  { value: '90d', label: 'Last 90 Days' },
];

const initialProjectState = { projects: [], userLimits: null };

function PremiumDashboard() {
  const { user } = useAuth();

  const [activeTab, setActiveTab] = useState('dashboard');
  const [projectsState, setProjectsState] = useState(initialProjectState);
  const [selectedProjectId, setSelectedProjectId] = useState(null);

  const getInitialSelectedAppKey = () => {
    if (typeof window === 'undefined') {
      return 'home';
    }
    const params = new URLSearchParams(window.location.search);
    return params.get('app') || 'home';
  };

  const initialAppKeyRef = useRef(null);
  if (initialAppKeyRef.current === null) {
    initialAppKeyRef.current = getInitialSelectedAppKey();
  }

  const [selectedAppKey, setSelectedAppKeyInternal] = useState(initialAppKeyRef.current);
  const [dateRange, setDateRange] = useState('30d');

  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(() => {
    if (typeof window === 'undefined') {
      return false;
    }
    return getStoredSidebarPref();
  });

  const setSelectedAppKey = useCallback(
    (nextKey, options = {}) => {
      const resolvedKey = nextKey || 'home';
      setSelectedAppKeyInternal(resolvedKey);

      if (options.skipUrl || typeof window === 'undefined') {
        return;
      }

      const url = new URL(window.location.href);
      if (!resolvedKey || resolvedKey === 'home') {
        url.searchParams.delete('app');
      } else {
        url.searchParams.set('app', resolvedKey);
      }

      window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`);
    },
    [setSelectedAppKeyInternal],
  );

  const [statusData, setStatusData] = useState(null);
  const [sentimentSeries, setSentimentSeries] = useState([]);
  const [painPoints, setPainPoints] = useState([]);
  const [strengths, setStrengths] = useState([]);

  const [loadingDashboard, setLoadingDashboard] = useState(false);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [panelMessage, setPanelMessage] = useState('');
  const [isDemoMode] = useState(() => {
    if (typeof window === 'undefined') {
      return false;
    }
    return new URLSearchParams(window.location.search).get('demo') === 'true';
  });
  const [demoDataset, setDemoDataset] = useState(null);
  const [deletingProjectId, setDeletingProjectId] = useState(null);
  const { startTask, isTaskRunning, runningTasks } = useTask();

  const selectedProject = useMemo(
    () => projectsState.projects.find((project) => project.id === selectedProjectId) || null,
    [projectsState.projects, selectedProjectId],
  );

  const appOptions = useMemo(() => {
    if (!selectedProject || !statusData?.competitor_analysis) {
      return [];
    }

    const apps = [
      {
        key: 'home',
        appId: selectedProject.home_app_id,
        label: 'Your App',
        subtitle: selectedProject.home_app_name,
      },
    ];

    Object.entries(statusData.competitor_analysis)
      .filter(([, value]) => value.app_type === 'competitor')
      .forEach(([appId, value]) => {
        apps.push({
          key: appId,
          appId,
          label: `vs. ${value.app_name}`,
          subtitle: value.app_name,
        });
      });

    return apps;
  }, [selectedProject, statusData]);

  useEffect(() => {
    if (!Array.isArray(appOptions) || appOptions.length === 0) {
      return;
    }

    const isValidSelection = appOptions.some((option) => option.key === selectedAppKey);
    if (isValidSelection) {
      return;
    }

    const fallbackOption = appOptions.find((option) => option.key === 'home') || appOptions[0];
    if (fallbackOption) {
      setSelectedAppKey(fallbackOption.key);
    }
  }, [appOptions, selectedAppKey, setSelectedAppKey]);

  const selectedAppMeta = useMemo(() => {
    if (!selectedProject) {
      return null;
    }
    if (selectedAppKey === 'home') {
      return {
        appId: selectedProject.home_app_id,
        label: 'Your App',
        displayName: selectedProject.home_app_name,
        compareTo: null,
      };
    }

    const compareTo = selectedProject.home_app_id;
    const competitor = statusData?.competitor_analysis?.[selectedAppKey];

    return {
      appId: selectedAppKey,
      label: competitor ? `vs. ${competitor.app_name}` : selectedAppKey,
      displayName: competitor?.app_name || selectedAppKey,
      compareTo,
    };
  }, [selectedAppKey, selectedProject, statusData]);

  const competitorsList = useMemo(() => {
    const apps = statusData?.competitor_analysis || {};
    return Object.entries(apps)
      .filter(([, item]) => item.app_type === 'competitor')
      .map(([appId, item]) => ({
        appId,
        competitorId: item.competitor_id ?? null,
        name: item.app_name,
        addedAt: item.added_at ?? null,
        status: item.status ?? item.review_import?.status ?? null,
      }))
      .sort((a, b) => ((b.addedAt || '') ?? '').localeCompare((a.addedAt || '') ?? ''));
  }, [statusData]);

  const strategicSnapshot = useMemo(() => {
    if (!statusData || !selectedProject || !selectedAppMeta?.appId) {
      return null;
    }

    const apps = statusData.competitor_analysis || {};
    const homeId = selectedProject.home_app_id;
    const homeMetrics = apps[homeId];
    if (!homeMetrics) {
      return null;
    }

    const targetId = selectedAppMeta.appId;
    const targetMetrics = targetId === homeId ? homeMetrics : apps[targetId];
    if (!targetMetrics) {
      return null;
    }

    const toNumber = (value) => Number(value || 0);
    const targetPositive = toNumber(targetMetrics.positive_percentage);
    const churnRisk = clamp(100 - targetPositive * 1.2);

    const homePositive = toNumber(homeMetrics.positive_percentage);
    const competitorEntries = Object.entries(apps).filter(([appId]) => appId !== homeId);
    const competitorAveragePositive = competitorEntries.length
      ? competitorEntries.reduce((sum, [, data]) => sum + toNumber(data.positive_percentage), 0) / competitorEntries.length
      : homePositive;

    const referencePositive = targetId === homeId ? competitorAveragePositive : homePositive;
    const competitiveGap = clamp(50 + (targetPositive - referencePositive));

    const rankingOrder = Object.entries(apps).sort(
      (a, b) => toNumber(b[1].positive_percentage) - toNumber(a[1].positive_percentage),
    );
    const rankIndex = rankingOrder.findIndex(([appId]) => appId === targetId);
    const homeRankIndex = rankingOrder.findIndex(([appId]) => appId === homeId);
    const rank = rankIndex >= 0 ? rankIndex + 1 : rankingOrder.length;
    const homeRank = homeRankIndex >= 0 ? homeRankIndex + 1 : rankingOrder.length;

    const sentimentDifference = targetPositive - competitorAveragePositive;
    const sentimentBenchmark = sentimentDifference >= 5 ? "Above Average" : sentimentDifference <= -5 ? "Below Average" : "Average";

    return {
      churnRisk,
      competitiveGap,
      ranking: {
        label: `#${rank} in Productivity`,
        trend: {
          direction: rank <= homeRank ? 'up' : 'down',
          delta: Math.max(1, Math.abs(rank - homeRank)),
        },
      },
      contextLabel: targetId === homeId ? 'Your App' : selectedAppMeta.displayName || 'Competitor',
      referenceLabel: targetId === homeId ? 'Competitor Avg' : homeMetrics.app_name || 'Your App',
      sentimentBenchmark,
    };
  }, [selectedAppMeta, selectedProject, statusData]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    window.localStorage.setItem(SIDEBAR_PREF_KEY, String(isSidebarCollapsed));
  }, [isSidebarCollapsed]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    const mediaQuery = window.matchMedia('(max-width: 1023.98px)');
    const syncFromQuery = (query) => {
      if (query.matches) {
        setIsSidebarCollapsed(true);
      } else {
        setIsSidebarCollapsed(getStoredSidebarPref());
      }
    };

    syncFromQuery(mediaQuery);
    const handler = (event) => syncFromQuery(event);
    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const handlePopState = () => {
      const params = new URLSearchParams(window.location.search);
      const nextApp = params.get('app') || 'home';
      setSelectedAppKey(nextApp, { skipUrl: true });
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [setSelectedAppKey]);


  const loadProjects = async () => {
    if (isDemoMode) {
      try {
        setLoadingProjects(true);
        setLoadingDashboard(true);
        const response = await apiClient.get('/api/demo/dashboard/');
        const {
          projects = [],
          user_limits: userLimits = {},
          status,
          sentiment,
          default_project_id: defaultProjectId,
          default_app_id: defaultAppId,
        } = response.data || {};

        setDemoDataset(response.data || {});
        setProjectsState({ projects, userLimits });

        const resolvedProjectId = defaultProjectId ?? projects[0]?.id ?? null;
        setSelectedProjectId(resolvedProjectId);

        if (status) {
          setStatusData(status);
        }

        const resolvedProject =
          resolvedProjectId != null
            ? projects.find((project) => project.id === resolvedProjectId)
            : projects[0] ?? null;
        const homeAppId = defaultAppId ?? resolvedProject?.home_app_id ?? null;
        const seriesMap = sentiment?.series || {};
        if (homeAppId && seriesMap[homeAppId]) {
          setSentimentSeries(seriesMap[homeAppId]);
        } else {
          setSentimentSeries([]);
        }

        setPanelMessage('Demo mode: sample data loaded.');
        return { projects, userLimits };
      } catch (error) {
        console.error('Failed to load demo data', error);
        setPanelMessage('Unable to load demo data. Please refresh.');
        return null;
      } finally {
        setLoadingProjects(false);
        setLoadingDashboard(false);
      }
    }

    try {
      setLoadingProjects(true);
      const response = await apiClient.get('/api/projects/');
      const { projects = [], user_limits: userLimits } = response.data || {};
      setProjectsState({ projects, userLimits });
      setPainPoints([]);
      setStrengths([]);

      setSelectedProjectId((currentSelection) => {
        if (currentSelection && projects.some((project) => project.id === currentSelection)) {
          return currentSelection;
        }
        return projects[0]?.id ?? null;
      });
      setPanelMessage('');
      return { projects, userLimits };
    } catch (error) {
      console.error('Failed to load projects', error);
      setPanelMessage('Unable to load projects. Please refresh.');
      return null;
    } finally {
      setLoadingProjects(false);
    }
  };

  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjectAnalytics = async (projectId, appMeta) => {
    if (isDemoMode) {
      const dataset = demoDataset;
      if (!dataset) {
        return;
      }

      const resolvedProject =
        selectedProject ||
        projectsState.projects.find((project) => project.id === projectId) ||
        null;
      const fallbackAppId =
        appMeta?.appId ||
        resolvedProject?.home_app_id ||
        dataset.default_app_id ||
        null;

      const seriesMap = dataset.sentiment?.series || {};
      if (fallbackAppId && seriesMap[fallbackAppId]) {
        setSentimentSeries(seriesMap[fallbackAppId]);
      } else {
        setSentimentSeries([]);
      }

      setPainPoints([]);
      setStrengths([]);

      if (dataset.status) {
        setStatusData(dataset.status);
      }

      setLoadingDashboard(false);
      return;
    }

    const effectiveAppId = appMeta?.appId || selectedAppKey || selectedProject?.home_app_id;
    if (!projectId || !effectiveAppId) {
      return;
    }

    setLoadingDashboard(true);
    setPainPoints([]);
    setStrengths([]);
    try {
      const statusPromise = apiClient.get(`/api/projects/${projectId}/status/`);
      const sentimentPromise = apiClient.get(`/api/projects/${projectId}/sentiment-trends/`, {
        params: {
          app_id: effectiveAppId,
          date_range: dateRange,
          ...(appMeta?.compareTo ? { compare_to: appMeta.compareTo } : {}),
        },
      });

      const [statusResponse, sentimentResponse] = await Promise.all([statusPromise, sentimentPromise]);

      setStatusData(statusResponse.data);
      setSentimentSeries(sentimentResponse.data?.series || []);
      setPanelMessage('');
      setLoadingDashboard(false);

      const insightsAppId = effectiveAppId || 'com.clickup.app';

      const [painResult, strengthResult] = await Promise.allSettled([
        apiClient.get('/api/enhanced-insights/', {
          params: { app_id: insightsAppId },
        }),
        apiClient.get('/api/strengths/', {
          params: { app_id: insightsAppId },
        }),
      ]);

      if (painResult.status === 'fulfilled') {
        const painPayload = painResult.value.data || {};
        const totalNeg = painPayload.review_count_analyzed || 0;
        const rawPainPoints = Array.isArray(painPayload.lda_pain_points)
          ? painPayload.lda_pain_points
          : [];
        const mappedPain = rawPainPoints.map((item, index) => {
          const quotes = Array.isArray(item.quotes) ? item.quotes.filter(Boolean) : [];
          const mentionsRaw =
            typeof item.mentions === 'number'
              ? item.mentions
              : Number(item.review_count ?? item.sample_size ?? quotes.length ?? 0);
          const mentions = Number.isFinite(mentionsRaw) ? mentionsRaw : 0;
          const denominator = totalNeg || item.review_count || 1;
          const baseValue =
            typeof item.review_percentage === 'number'
              ? item.review_percentage
              : mentions;
          const percentage =
            typeof item.review_percentage === 'number'
              ? item.review_percentage
              : Math.round(((baseValue || 0) / (denominator || 1)) * 1000) / 10;
          const keywords = Array.isArray(item.keywords) ? item.keywords.filter(Boolean) : [];
          const coherenceScore =
            typeof item.coherence_score === 'number' ? Math.round(item.coherence_score * 100) / 100 : null;
          const averageProbability =
            typeof item.average_probability === 'number'
              ? Math.round(item.average_probability * 1000) / 1000
              : null;
          return {
            id: `${insightsAppId}-pain-${index}`,
            title: item.issue,
            mentions,
            percentage: Number.isFinite(percentage) ? percentage : 0,
            quotes,
            keywords,
            coherenceScore,
            averageProbability,
          };
        });
        const cleanedPain = mappedPain
          .filter((item) => Boolean(item.title))
          .slice(0, 3);
        setPainPoints(cleanedPain);
      } else {
        console.warn('Pain point insights unavailable', painResult.reason);
        setPainPoints([]);
      }

      if (strengthResult.status === 'fulfilled') {
        const strengthPayload = strengthResult.value.data || {};
        const totalPos = strengthPayload.review_count_analyzed || 0;
        const rawStrengths = Array.isArray(strengthPayload.lda_strengths)
          ? strengthPayload.lda_strengths
          : [];
        const mappedStrengths = rawStrengths.map((item, index) => {
          const quotes = Array.isArray(item.quotes) ? item.quotes.filter(Boolean) : [];
          const mentionsRaw =
            typeof item.mentions === 'number'
              ? item.mentions
              : Number(item.review_count ?? item.sample_size ?? quotes.length ?? 0);
          const mentions = Number.isFinite(mentionsRaw) ? mentionsRaw : 0;
          const denominator = totalPos || item.review_count || 1;
          const baseValue =
            typeof item.review_percentage === 'number'
              ? item.review_percentage
              : mentions;
          const percentage =
            typeof item.review_percentage === 'number'
              ? item.review_percentage
              : Math.round(((baseValue || 0) / (denominator || 1)) * 1000) / 10;
          const keywords = Array.isArray(item.keywords) ? item.keywords.filter(Boolean) : [];
          const coherenceScore =
            typeof item.coherence_score === 'number' ? Math.round(item.coherence_score * 100) / 100 : null;
          const averageProbability =
            typeof item.average_probability === 'number'
              ? Math.round(item.average_probability * 1000) / 1000
              : null;
          return {
            id: `${insightsAppId}-strength-${index}`,
            title: item.issue,
            mentions,
            percentage: Number.isFinite(percentage) ? percentage : 0,
            quotes,
            keywords,
            coherenceScore,
            averageProbability,
          };
        });
        const cleanedStrengths = mappedStrengths
          .filter((item) => Boolean(item.title))
          .slice(0, 3);
        setStrengths(cleanedStrengths);
      } else {
        console.warn('Strength insights unavailable', strengthResult.reason);
        setStrengths([]);
      }
    } catch (error) {
      console.error('Failed to load dashboard analytics', error);
      setPanelMessage('Unable to load dashboard analytics. Please retry.');
      setLoadingDashboard(false);
    }
  };

  useEffect(() => {
    if (!selectedProjectId) {
      return;
    }
    loadProjectAnalytics(selectedProjectId, selectedAppMeta ?? { appId: null });
  }, [selectedProjectId, selectedAppKey, dateRange]);

  const handleProjectChange = (projectId) => {
    setSelectedProjectId(projectId);
    setSelectedAppKey('home');
  };

  const handleCreateProject = async (event) => {
    event.preventDefault();
    if (isDemoMode) {
      setPanelMessage('Demo mode: project creation is disabled.');
      return;
    }
    const form = event.target;
    const payload = {
      name: form.name.value.trim(),
      home_app_id: form.home_app_id.value.trim(),
      home_app_name: form.home_app_name.value.trim(),
    };

    if (!payload.name || !payload.home_app_id || !payload.home_app_name) {
      return;
    }

    const appleAppId = form.apple_app_id?.value.trim();
    if (appleAppId) {
      payload.apple_app_id = appleAppId;
    }

    try {
      await apiClient.post('/api/projects/create/', payload);
      form.reset();
      await loadProjects();
    } catch (error) {
      console.error('Failed to create project', error);
      setPanelMessage(error.response?.data?.error || 'Unable to create project');
    }
  };

  const handleAddCompetitor = async (event) => {
    event.preventDefault();
    if (isDemoMode) {
      setPanelMessage('Demo mode: competitor management is disabled.');
      return;
    }
    if (!selectedProjectId) {
      return;
    }

    const form = event.target;
    const payload = {
      project_id: selectedProjectId,
      app_id: form.app_id.value.trim(),
      app_name: form.app_name.value.trim(),
    };

    if (!payload.app_id || !payload.app_name) {
      return;
    }

    const homeAppId =
      selectedProject?.home_app_id ||
      projectsState.projects.find((project) => project.id === selectedProjectId)?.home_app_id ||
      null;

    try {
      const response = await apiClient.post('/api/projects/add-competitor/', payload);
      const competitorRecord = response?.data || {};
      form.reset();

      setStatusData((previous) => {
        const previousAnalysis = previous?.competitor_analysis || {};
        if (previousAnalysis[payload.app_id]) {
          return previous;
        }

        const reviewImport = competitorRecord.review_import || {};

        return {
          ...(previous || {}),
          competitor_analysis: {
            ...previousAnalysis,
            [payload.app_id]: {
              app_id: payload.app_id,
              app_name: payload.app_name,
              app_type: 'competitor',
              competitor_id: competitorRecord.id ?? null,
              added_at: competitorRecord.added_at ?? null,
              positive_percentage: 0,
              negative_percentage: 0,
              review_count: 0,
              status: reviewImport.status || previousAnalysis[payload.app_id]?.status || 'pending',
              review_import: reviewImport,
            },
          },
        };
      });

      setSelectedAppKey(payload.app_id);

      await Promise.all([
        loadProjectAnalytics(selectedProjectId, {
          appId: payload.app_id,
          label: `vs. ${payload.app_name}`,
          displayName: payload.app_name,
          compareTo: homeAppId,
        }),
        loadProjects(),
      ]);
      setPanelMessage(`${payload.app_name} added as competitor.`);
    } catch (error) {
      if (error.response?.status === 400) {
        const message = error.response?.data?.error || '';
        if (message.toLowerCase().includes('already')) {
          setPanelMessage(message || 'Competitor already exists in this project. Switching to it.');
          setSelectedAppKey(payload.app_id);
          await loadProjectAnalytics(selectedProjectId, {
            appId: payload.app_id,
            label: `vs. ${payload.app_name}`,
            displayName: payload.app_name,
            compareTo: homeAppId,
          });
          return;
        }
      }

      console.error('Failed to add competitor', error);
      setPanelMessage(error.response?.data?.error || 'Unable to add competitor');
    }
  };

  const handleSelectExistingCompetitor = (appId) => {
    if (!appId) {
      return;
    }
    setSelectedAppKey(appId);
    setPanelMessage('');
  };

  const handleDeleteCompetitor = async (competitorId, appId) => {
    if (!competitorId) {
      setPanelMessage('Unable to remove competitor: identifier missing.');
      return;
    }

    if (isDemoMode) {
      setPanelMessage('Demo mode: competitor management is disabled.');
      return;
    }
    const confirmationMessage = 'Remove this competitor from the project? This will also stop future comparisons.';
    if (typeof window !== 'undefined' && !window.confirm(confirmationMessage)) {
      return;
    }

    const currentSelectionKey = selectedAppKey;
    const currentAppMeta = selectedAppMeta;
    const fallbackHomeMeta = selectedProject
      ? {
          appId: selectedProject.home_app_id,
          label: 'Your App',
          displayName: selectedProject.home_app_name,
          compareTo: null,
        }
      : null;

    try {
      await apiClient.delete(`/api/competitors/${competitorId}/delete/`);

      setStatusData((previous) => {
        if (!previous?.competitor_analysis) {
          return previous;
        }
        const nextAnalysis = { ...previous.competitor_analysis };
        delete nextAnalysis[appId];
        return { ...previous, competitor_analysis: nextAnalysis };
      });

      if (currentSelectionKey === appId) {
        setSelectedAppKey('home');
      }

      setPanelMessage('Competitor removed.');

      const nextAppMeta = currentSelectionKey === appId ? fallbackHomeMeta : currentAppMeta;

      await Promise.all([
        loadProjects(),
        nextAppMeta?.appId ? loadProjectAnalytics(selectedProjectId, nextAppMeta) : Promise.resolve(),
      ]);
    } catch (error) {
      console.error('Failed to delete competitor', error);
      setPanelMessage(error.response?.data?.error || 'Unable to remove competitor');
    }
  };

  const handleDeleteProject = async (projectId) => {
    if (isDemoMode) {
      setPanelMessage('Demo mode: project management is disabled.');
      return;
    }
    const project = projectsState.projects.find((item) => item.id === projectId);
    if (!project) {
      setPanelMessage('Project not found or already removed.');
      return;
    }

    const confirmationMessage = `Are you sure you want to delete ${project.name}? This will remove all competitors and data.`;
    if (typeof window !== 'undefined' && !window.confirm(confirmationMessage)) {
      return;
    }

    const wasSelected = selectedProjectId === projectId;
    setDeletingProjectId(projectId);

    try {
      await apiClient.delete(`/api/projects/${projectId}/delete/`);

      if (wasSelected) {
        setStatusData(null);
        setSentimentSeries([]);
        setPainPoints([]);
        setStrengths([]);
      }

      const result = await loadProjects();
      if (wasSelected) {
        setSelectedAppKey('home');
        if (!result?.projects?.length) {
          setSelectedProjectId(null);
        }
      }

      setPanelMessage(`Project "${project.name}" deleted.`);
    } catch (error) {
      console.error('Failed to delete project', error);
      setPanelMessage(error.response?.data?.error || 'Unable to delete project');
    } finally {
      setDeletingProjectId(null);
    }
  };

  const handleStartAnalysis = async (appId, analysisType = 'quick') => {
    if (isDemoMode) {
      setPanelMessage('Demo mode: analysis runs are disabled.');
      return;
    }
    if (!selectedProjectId || !appId) {
      return;
    }

    if (isTaskRunning(appId)) {
      setPanelMessage('Analysis already in progress for this app');
      return;
    }

    const normalizedType = (analysisType || 'quick').toLowerCase();
    const analysisLabel = normalizedType === 'full' ? 'Full analysis' : 'Quick analysis';

    try {
      await startTask(appId, selectedProjectId, normalizedType);
      setPanelMessage(`${analysisLabel} started in background. You can continue using the dashboard.`);

      const handleTaskComplete = (event) => {
        if (event.detail.appId !== appId) {
          return;
        }
        const completedType = (event.detail.analysisType || event.detail.result?.task_type || 'quick').toLowerCase();
        const completedLabel = completedType === 'full' ? 'Full analysis' : 'Quick analysis';
        loadProjectAnalytics(selectedProjectId, selectedAppMeta);
        setPanelMessage(`${completedLabel} complete! Data has been refreshed.`);
        cleanupListeners();
      };

      const handleTaskFailed = (event) => {
        if (event.detail.appId !== appId) {
          return;
        }
        const failedType = (event.detail.analysisType || event.detail.result?.task_type || 'quick').toLowerCase();
        const failedLabel = failedType === 'full' ? 'Full analysis' : 'Quick analysis';
        setPanelMessage(event.detail.error || `${failedLabel} failed. Please try again.`);
        cleanupListeners();
      };

      const handleTaskTimeoutEvent = (event) => {
        if (event.detail.appId !== appId) {
          return;
        }
        const timeoutType = (event.detail.analysisType || event.detail.result?.task_type || 'quick').toLowerCase();
        const timedOutLabel = timeoutType === 'full' ? 'Full analysis' : 'Quick analysis';
        setPanelMessage(`${timedOutLabel} is taking longer than expected. Please try again soon.`);
        cleanupListeners();
      };

      const cleanupListeners = () => {
        window.removeEventListener('taskCompleted', handleTaskComplete);
        window.removeEventListener('taskFailed', handleTaskFailed);
        window.removeEventListener('taskTimeout', handleTaskTimeoutEvent);
      };

      window.addEventListener('taskCompleted', handleTaskComplete);
      window.addEventListener('taskFailed', handleTaskFailed);
      window.addEventListener('taskTimeout', handleTaskTimeoutEvent);
    } catch (error) {
      console.error('Failed to start analysis', error);
      setPanelMessage(error.response?.data?.error || 'Unable to start analysis');
    }
  };

  const sidebarWidthClass = isSidebarCollapsed ? 'w-16' : 'w-64';
  const toggleSidebar = () => setIsSidebarCollapsed((prev) => !prev);

  return (
    <div className="flex min-h-screen bg-gray-background text-gray-base">
      <aside
        className={clsx(
          'flex flex-col bg-gray-base text-white transition-[width] duration-300 ease-in-out',
          sidebarWidthClass,
        )}
      >
        <div className="flex h-16 items-center gap-3 border-b border-white/10 px-4">
          <div
            className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/10 text-lg font-semibold"
            title="Deepfocal"
          >
            DF
          </div>
          {!isSidebarCollapsed && (
            <div className="flex flex-col">
              <h1 className="text-xl font-semibold leading-tight">Deepfocal</h1>
              <p className="text-xs text-white/70">{user?.username || 'Analyst'}</p>
            </div>
          )}
        </div>
        <nav className="flex-1 overflow-y-auto py-6">
          {navigationItems.map((group) => (
            <div
              key={group.group}
              className={clsx('mb-6', isSidebarCollapsed ? 'px-2' : 'px-4')}
            >
              {!isSidebarCollapsed && (
                <h3 className="px-2 text-xs font-medium uppercase tracking-wider text-white/50">
                  {group.group}
                </h3>
              )}
              <div className="mt-3 space-y-1">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const isActive = activeTab === item.id;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      title={isSidebarCollapsed ? item.label : undefined}
                      onClick={() => setActiveTab(item.id)}
                      className={clsx(
                        'group flex w-full items-center rounded-lg py-2 text-sm font-medium transition-colors duration-200',
                        isActive
                          ? 'border-r-2 border-primary bg-white/10 text-white'
                          : 'text-white/70 hover:bg-white/10 hover:text-white',
                        isSidebarCollapsed ? 'justify-center px-2' : 'gap-3 px-3',
                      )}
                    >
                      <Icon className="h-5 w-5 shrink-0" />
                      {!isSidebarCollapsed && <span className="whitespace-nowrap">{item.label}</span>}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
      </aside>

      <main
        className={clsx(
          'flex-1 overflow-y-auto transition-[padding] duration-300 ease-in-out',
          isSidebarCollapsed ? 'lg:pl-4' : 'lg:pl-0',
        )}
      >
        <GlobalHeader
          projects={projectsState.projects}
          selectedProjectId={selectedProjectId}
          onSelectProject={handleProjectChange}
          appOptions={appOptions}
          selectedAppKey={selectedAppKey}
          onSelectApp={setSelectedAppKey}
          dateRange={dateRange}
          onSelectDateRange={setDateRange}
          isSidebarCollapsed={isSidebarCollapsed}
          onToggleSidebar={toggleSidebar}
          isDemoMode={isDemoMode}
        />

        <div className="mx-auto max-w-7xl px-8 py-6">
          {panelMessage && (
            <div className="mb-6 rounded-lg border border-danger/20 bg-danger/10 px-4 py-3 text-sm text-danger">
              {panelMessage}
            </div>
          )}

          {loadingProjects || loadingDashboard ? (
            <div className="flex min-h-[400px] items-center justify-center">
              <div className="h-10 w-10 animate-spin rounded-full border-4 border-primary/20 border-t-primary" />
            </div>
          ) : (
            <section>
              {activeTab === 'dashboard' && (
                <DashboardTab
                  strategicSnapshot={strategicSnapshot}
                  sentimentSeries={sentimentSeries}
                  selectedAppMeta={selectedAppMeta}
                  painPoints={painPoints}
                  strengths={strengths}
                  compareEnabled={Boolean(selectedAppMeta?.compareTo)}
                />
              )}

              {activeTab === 'competitor-analysis' && (
                <CompetitorAnalysisTab
                  statusData={statusData}
                  selectedProject={selectedProject}
                  onStartAnalysis={handleStartAnalysis}
                  isDemoMode={isDemoMode}
                />
              )}

              {activeTab === 'pain-points' && (
                <PainStrengthsTab painPoints={painPoints} strengths={strengths} />
              )}

              {activeTab === 'project-settings' && (
                <ProjectSettingsTab
                  selectedProject={selectedProject}
                  selectedProjectId={selectedProjectId}
                  projectsState={projectsState}
                  onSelectProject={handleProjectChange}
                  onDeleteProject={handleDeleteProject}
                  deletingProjectId={deletingProjectId}
                  onCreateProject={handleCreateProject}
                  onAddCompetitor={handleAddCompetitor}
                  competitors={competitorsList}
                  onSelectCompetitor={handleSelectExistingCompetitor}
                  onDeleteCompetitor={handleDeleteCompetitor}
                  isDemoMode={isDemoMode}
                />
              )}

              {['review-explorer', 'collections', 'alerts'].includes(activeTab) && (
                <ComingSoon title={navigationItems.flatMap((group) => group.items).find((item) => item.id === activeTab)?.label || 'Coming Soon'} />
              )}
            </section>
          )}
        </div>
      </main>

      {/* Add loading overlays for running tasks */}
      {selectedAppMeta?.appId && isTaskRunning(selectedAppMeta.appId) && (
        <LoadingOverlay appId={selectedAppMeta.appId} />
      )}

      {/* Show overlay for any other running tasks in this project */}
      {Array.from(runningTasks.values())
        .filter(task => task.projectId === selectedProjectId && task.appId !== selectedAppMeta?.appId)
        .map(task => (
          <LoadingOverlay key={task.appId} appId={task.appId} />
        ))}
    </div>
  );
}
function GlobalHeader({
  projects,
  selectedProjectId,
  onSelectProject,
  appOptions,
  selectedAppKey,
  onSelectApp,
  dateRange,
  onSelectDateRange,
  isSidebarCollapsed,
  onToggleSidebar,
  isDemoMode,
}) {
  const SidebarToggleIcon = isSidebarCollapsed ? ChevronRight : ChevronLeft;

  return (
    <div className="border-b border-gray-200 bg-white px-8 py-4">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onToggleSidebar}
              className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-gray-200 text-gray-500 transition hover:border-primary/40 hover:text-primary focus:outline-none focus:ring-2 focus:ring-primary/40"
              aria-label={isSidebarCollapsed ? 'Expand sidebar navigation' : 'Collapse sidebar navigation'}
            >
              <SidebarToggleIcon className="h-4 w-4" />
            </button>
            {isDemoMode && (
              <span className="inline-flex items-center rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
                Demo Mode
              </span>
            )}
            <div>
              <label className="text-xs font-medium text-gray-500">Project</label>
              <div className="relative mt-1">
                <select
                  value={selectedProjectId || ''}
                  onChange={(event) => onSelectProject(Number(event.target.value))}
                  className="w-56 appearance-none rounded-lg border border-gray-300 px-4 py-2 pr-10 text-sm font-medium text-gray-base focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40"
                >
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-3 top-3 h-4 w-4 text-gray-400" />
              </div>
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-gray-500">Compare</label>
            <div className="relative mt-1">
              <select
                value={selectedAppKey}
                onChange={(event) => onSelectApp(event.target.value)}
                className="w-56 appearance-none rounded-lg border border-gray-300 px-4 py-2 pr-10 text-sm font-medium text-gray-base focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40"
              >
                {appOptions.map((option) => (
                  <option key={option.key} value={option.key}>
                    {option.label}
                  </option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-3 top-3 h-4 w-4 text-gray-400" />
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-gray-500">Date Range</label>
            <div className="relative mt-1">
              <select
                value={dateRange}
                onChange={(event) => onSelectDateRange(event.target.value)}
                className="w-44 appearance-none rounded-lg border border-gray-300 px-4 py-2 pr-10 text-sm font-medium text-gray-base focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40"
              >
                {dateRanges.map((range) => (
                  <option key={range.value} value={range.value}>
                    {range.label}
                  </option>
                ))}
              </select>
              <Calendar className="pointer-events-none absolute right-3 top-3 h-4 w-4 text-gray-400" />
            </div>
          </div>
        </div>

        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-gray-400" />
          <input
            type="search"
            placeholder="Search insights"
            className="w-80 rounded-lg border border-gray-300 pl-10 pr-4 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40"
          />
        </div>
      </div>
    </div>
  );
}

function DashboardTab({ strategicSnapshot,
  sentimentSeries,
  selectedAppMeta,
  painPoints,
  strengths,
  compareEnabled,
}) {
  const [chartExpanded, setChartExpanded] = useState(false);
  const churnRisk = strategicSnapshot?.churnRisk ?? 0;
  const competitiveGap = strategicSnapshot?.competitiveGap ?? 50;
  const categoryRanking =
    strategicSnapshot?.ranking ?? { label: '#27 in Productivity', trend: { direction: 'up', delta: 2 } };
  const contextLabel = strategicSnapshot?.contextLabel ?? 'Your App';
  const referenceLabel = strategicSnapshot?.referenceLabel ?? 'Competitor Avg';

  const churnBadgeLabel =
    churnRisk >= 60 ? 'High Risk' : churnRisk >= 40 ? 'Elevated' : 'Healthy';
  const churnBadgeTone = churnRisk >= 60 ? 'danger' : churnRisk >= 40 ? 'warning' : 'primary';

  const gapDelta = competitiveGap - 50;
  const gapBadgeLabel =
    gapDelta <= -10
      ? 'Critical Gap'
      : gapDelta < 0
      ? 'Needs Attention'
      : gapDelta >= 10
      ? 'Strong Advantage'
      : 'Advantage';
  const gapBadgeTone = gapDelta < 0 ? 'danger' : 'primary';

  const rankingDirection = categoryRanking.trend?.direction === 'down' ? 'down' : 'up';
  const RankingIcon = rankingDirection === 'down' ? TrendingDown : TrendingUp;
  const rankingBadgeTone = rankingDirection === 'down' ? 'danger' : 'primary';
  const sentimentBenchmarkLabel = strategicSnapshot?.sentimentBenchmark || 'No Data';
  const sentimentTone =
    sentimentBenchmarkLabel === 'Above Average'
      ? 'primary'
      : sentimentBenchmarkLabel === 'Below Average'
      ? 'danger'
      : 'warning';

  const sentimentData = sentimentSeries.map((row) => ({
    date: row.date,
    positive: row.positive,
    negative: row.negative,
    competitor: row.competitor ?? null,
  }));

  return (
    <div className="space-y-8">
      <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <header className="mb-6 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-base">Strategic Performance - {contextLabel}</h2>
            <p className="text-sm text-gray-500">
              Snapshot for {contextLabel} vs {referenceLabel}.
            </p>
          </div>
        </header>
        <div className="grid gap-6 md:grid-cols-3">
          <ScoreCard
            title="Churn Risk Score"
            value={`${churnRisk.toFixed(1)}/100`}
            badgeLabel={churnBadgeLabel}
            badgeTone={churnBadgeTone}
          />
          <ScoreCard
            title="Competitive Gap Score"
            value={`${competitiveGap.toFixed(1)}/100`}
            badgeLabel={gapBadgeLabel}
            badgeTone={gapBadgeTone}
          />
          <div className="rounded-xl border border-gray-200 px-5 py-4 text-center">
            <div
              className={clsx(
                'mb-2 font-bold tracking-tight',
                toneValueClasses[sentimentTone] ?? 'text-gray-base',
              )}
              style={{ fontSize: 'clamp(1rem, 2.5vw, 1.5rem)' }}
            >
              {sentimentBenchmarkLabel}
            </div>
            <p className="mt-2 text-sm font-medium text-gray-base">Sentiment Benchmark</p>
            <div
              className={clsx(
                'mt-3 inline-flex items-center rounded-full px-3 py-1 text-xs font-medium',
                toneBadgeClasses[sentimentTone] ?? toneBadgeClasses.warning,
              )}
            >
              vs Competitors
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <header className="mb-6 flex items-center justify-between">
  <div>
    <h2 className="text-lg font-semibold text-gray-base">Sentiment Analysis</h2>
    <p className="text-sm text-gray-500">
      Tracking {selectedAppMeta?.displayName || 'your app'} over time.
    </p>
  </div>
  <div className="flex items-center gap-4">
    <button
      onClick={() => setChartExpanded(!chartExpanded)}
      className="text-sm text-primary hover:text-primary/80 font-medium"
    >
      {chartExpanded ? 'Collapse Chart' : 'Expand Chart'}
    </button>
    <div className="flex items-center gap-1 sm:gap-4 text-xs sm:text-sm text-gray-500 flex-wrap">
  <div className="block sm:hidden">
    <LegendDot color="#14b8a6" label="Pos" />
    <LegendDot color="#ef4444" label="Neg" />
  </div>
  <div className="hidden sm:block">
    <LegendDot color="#14b8a6" label="Positive Sentiment" />
    <LegendDot color="#ef4444" label="Negative Sentiment" />
  </div>
  {compareEnabled && (
    <LegendDot color="#9ca3af" label={referenceLabel} dashed />
  )}
</div>
  </div>
</header>
       <div className={chartExpanded ? "h-96" : "h-48"} style={{ width: '100%', overflow: 'hidden' }}>
  {sentimentData.length === 0 ? (
    <div className="flex h-full items-center justify-center text-sm text-gray-500">
      Not enough data yet. Trigger an analysis run to populate this chart.
    </div>
  ) : (
    <ResponsiveContainer width="100%" height="100%" minWidth={0}>
      <LineChart data={sentimentData}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="date" stroke="#666" fontSize={12} tickLine={false} axisLine={false} />
        <YAxis stroke="#666" fontSize={12} tickLine={false} axisLine={false} domain={[0, 100]} />
        <Tooltip
          contentStyle={{
            backgroundColor: '#fff',
            border: '1px solid #e2e8f0',
            borderRadius: '8px',
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
          }}
        />
        <Line
          type="monotone"
          dataKey="positive"
          stroke="#14b8a6"
          strokeWidth={3}
          dot={{ r: 4, strokeWidth: 2, fill: '#14b8a6' }}
          activeDot={{ r: 6, fill: '#14b8a6' }}
        />
        <Line
          type="monotone"
          dataKey="negative"
          stroke="#ef4444"
          strokeWidth={3}
          dot={{ r: 4, strokeWidth: 2, fill: '#ef4444' }}
          activeDot={{ r: 6, fill: '#ef4444' }}
        />
        {compareEnabled && (
          <Line
            type="monotone"
            dataKey="competitor"
            stroke="#9ca3af"
            strokeWidth={2}
            strokeDasharray="5 5"
            dot={{ r: 3, strokeWidth: 2, fill: '#9ca3af' }}
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  )}
</div>
      </section>

      <section className="grid gap-4 sm:gap-8 grid-cols-1 lg:grid-cols-2">
        <ExpandableCard
          title="Top 3 Pain Points"
          accent="danger"
          items={painPoints}
          emptyMessage="No themes discovered."
        />
        <ExpandableCard
          title="Top 3 Strengths"
          accent="primary"
          items={strengths}
          emptyMessage="No themes discovered."
        />
      </section>

      <section className="mt-8">
        <MarketMentionsSection appId={selectedAppMeta?.appId} />
      </section>
    </div>
  );
}
function ScoreCard({ title, value, badgeLabel, badgeTone = 'primary' }) {

  return (
    <div className="rounded-xl border border-gray-200 px-5 py-4 text-center">
      <div
        className={clsx(
          'font-bold tracking-tight',
          toneValueClasses[badgeTone] ?? 'text-gray-base',
        )}
        style={{ fontSize: 'clamp(1rem, 2.5vw, 1.5rem)' }}
      >
        {value}
      </div>
      <p className="mt-2 text-sm font-medium text-gray-base">{title}</p>
      <div
        className={clsx(
          'mt-3 inline-flex items-center rounded-full px-3 py-1 text-xs font-medium',
          toneBadgeClasses[badgeTone] ?? toneBadgeClasses.primary,
        )}
      >
        {badgeLabel}
      </div>
    </div>
  );
}
function LegendDot({ color, label, dashed = false, className }) {

  return (
    <div className={clsx("flex items-center gap-2", className)}>
      <span
        className={clsx('h-3 w-3 rounded-full', dashed && 'border border-dashed')}
        style={{ backgroundColor: dashed ? 'transparent' : color, borderColor: color }}
      />
      <span>{label}</span>
    </div>
  );
}

function ExpandableCard({ title, accent, items, emptyMessage }) {
  const [expandedId, setExpandedId] = useState(null);
  const toneStyles =
    accent === 'danger'
      ? { badge: 'bg-danger/10 text-danger', border: 'border-danger/40' }
      : { badge: 'bg-primary/10 text-primary', border: 'border-primary/40' };

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm overflow-hidden">
      <h3 className="text-lg font-semibold text-gray-base">{title}</h3>
      <div className="mt-6 space-y-4">
        {(!items || items.length === 0) && <p className="text-sm text-gray-500">{emptyMessage}</p>}
        {items?.map((item, index) => (
          <div key={item.id ?? index} className="rounded-xl border border-gray-200 p-4">
            <button
              type="button"
              onClick={() => setExpandedId(expandedId === item.id ? null : item.id)}
              className="flex w-full items-start justify-between text-left"
            >
              <div className="flex items-start gap-3">
                <span className={clsx('flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold', toneStyles.badge)}>
                  {index + 1}
                </span>
                <div>
                  <h4 className="text-sm sm:text-base font-medium text-gray-base break-words leading-tight">{item.title}</h4>
                  <p className="text-xs text-gray-500 break-words">
                    {item.mentions || 0} mentions - {item.percentage || 0}% of reviews
                  </p>
                  {typeof item.coherenceScore === 'number' && (
                    <p className="mt-1 text-[11px] text-gray-400">
                      Coherence score: {item.coherenceScore}
                    </p>
                  )}
                  {item.keywords?.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {item.keywords.map((keyword) => (
                        <span
                          key={`${item.id}-keyword-${keyword}`}
                          className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-600"
                        >
                          {keyword}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              <ChevronDown
                className={clsx('h-4 w-4 text-gray-400 transition-transform', expandedId === item.id && 'rotate-180')}
              />
            </button>
            {expandedId === item.id && (
              <div className="mt-4 space-y-4">
                {item.quotes?.length > 0 && (
                  <div className="space-y-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Example quotes</p>
                    {item.quotes.map((quote, quoteIndex) => (
                      <div
                        key={`${item.id}-quote-${quoteIndex}`}
                        className={clsx(
                          'rounded-lg border-l-4 bg-gray-50 px-4 py-3 text-sm italic text-gray-600',
                          toneStyles.border,
                        )}
                      >
                        "{quote}"
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
function CompetitorAnalysisTab({ statusData, selectedProject, onStartAnalysis, isDemoMode = false }) {
  const apps = statusData?.competitor_analysis || {};
  const activeTasks = statusData?.active_tasks || [];

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-gray-base">Competitive Landscape</h2>
          <p className="text-sm text-gray-500">
            {selectedProject?.name
              ? `Evaluating ${selectedProject.name}`
              : 'Select a project to view competitor metrics.'}
          </p>
        </div>
        {statusData?.has_active_tasks && (
          <div className="inline-flex items-center gap-2 rounded-full bg-warning/10 px-3 py-1 text-xs font-medium text-warning">
            <RefreshCw className="h-3 w-3 animate-spin" /> Refresh in progress
          </div>
        )}
      </header>
      {isDemoMode && (
        <p className="text-xs font-medium text-primary">Demo mode uses static insights. Analysis actions are disabled.</p>
      )}

      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
        <table className="min-w-full divide-y divide-gray-200 text-left">
          <thead className="bg-gray-50">
            <tr className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              <th className="px-6 py-3">App</th>
              <th className="px-6 py-3">Sentiment</th>
              <th className="px-6 py-3">Review Mix</th>
              <th className="px-6 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 text-sm text-gray-base">
            {Object.entries(apps).map(([appId, data]) => (
              <tr key={appId}>
                <td className="px-6 py-4">
                  <div className="font-medium text-gray-base">{data.app_name}</div>
                  <div className="text-xs text-gray-500">
                    {data.app_type === 'home' ? 'Your App' : 'Competitor'}
                  </div>
                </td>
                <td className="px-6 py-4">
                  <div className="text-sm font-semibold text-primary">
                    {(data.positive_percentage || 0).toFixed
                      ? data.positive_percentage.toFixed(1)
                      : data.positive_percentage}
                    % positive
                  </div>
                  <div className="text-xs text-gray-500">{data.total_reviews} reviews</div>
                </td>
                <td className="px-6 py-4">
                  <div className="flex items-center gap-2 text-xs text-gray-500">
                    <span className="inline-flex items-center gap-1">
                      <span className="h-2 w-2 rounded-full bg-primary" /> {data.positive_count} pos
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <span className="h-2 w-2 rounded-full bg-danger" /> {data.negative_count} neg
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <span className="h-2 w-2 rounded-full bg-gray-300" /> {data.neutral_count} neu
                    </span>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => onStartAnalysis(appId, 'quick')}
                      className="inline-flex items-center gap-2 rounded-lg border border-primary/30 px-3 py-1.5 text-xs font-semibold text-primary hover:bg-primary/10"
                      disabled={isDemoMode}
                      aria-disabled={isDemoMode}
                    >
                      Quick Analysis
                    </button>
                    <button
                      type="button"
                      onClick={() => onStartAnalysis(appId, 'full')}
                      className="inline-flex items-center gap-2 rounded-lg border border-warning/30 px-3 py-1.5 text-xs font-semibold text-warning hover:bg-warning/10"
                      disabled={isDemoMode}
                      aria-disabled={isDemoMode}
                    >
                      Full Analysis
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {activeTasks.length > 0 && (
        <div className="rounded-xl border border-warning/30 bg-warning/5 p-6">
          <h3 className="text-sm font-semibold text-warning">Active Tasks</h3>
          <ul className="mt-3 space-y-2 text-xs text-warning/80">
            {activeTasks.map((task) => (
              <li key={task.task_id}>
                {task.app_name}: {task.task_type} - {Math.round(task.progress_percent || 0)}%
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function PainStrengthsTab({ painPoints, strengths }) {

  return (
    <div className="grid gap-8 md:grid-cols-2">
      <ExpandableCard
        title="Negative Themes"
        accent="danger"
        items={painPoints}
        emptyMessage="No themes discovered."
      />
      <ExpandableCard
        title="Positive Themes"
        accent="primary"
        items={strengths}
        emptyMessage="No themes discovered."
      />
    </div>
  );
}

function ProjectSettingsTab({
  selectedProject,
  selectedProjectId,
  projectsState = { projects: [], userLimits: {} },
  onSelectProject,
  onDeleteProject,
  deletingProjectId,
  isDemoMode = false,
  onCreateProject,
  onAddCompetitor,
  competitors = [],
  onSelectCompetitor,
  onDeleteCompetitor,
}) {
  const userLimits = projectsState.userLimits || {};
  const projects = projectsState.projects || [];
  const projectLimitRaw = userLimits.project_limit;
  const projectLimitValue =
    projectLimitRaw === null || projectLimitRaw === undefined ? null : Number(projectLimitRaw);
  const projectLimitLabel =
    projectLimitValue !== null ? `${projects.length}/${projectLimitValue}` : `${projects.length}/Unlimited`;
  const projectLimitReached = projectLimitValue !== null && projects.length >= projectLimitValue;
  const subscriptionLabel = (userLimits.subscription_tier || '').toUpperCase();

  const competitorLimitValueRaw = userLimits.competitor_limit;
  const competitorLimitValue =
    competitorLimitValueRaw === null || competitorLimitValueRaw === undefined
      ? null
      : Number(competitorLimitValueRaw);
  const competitorCount = competitors.length;
  const competitorLimitReached = competitorLimitValue !== null && competitorCount >= competitorLimitValue;
  const competitorLimitLabel =
    competitorLimitValue !== null ? `${competitorCount}/${competitorLimitValue}` : `${competitorCount}/Unlimited`;
  const remainingCompetitors =
    competitorLimitValue !== null ? Math.max(competitorLimitValue - competitorCount, 0) : null;
  const tierLabel = (userLimits.subscription_tier || '').replace(/\b\w/g, (char) => char.toUpperCase());
  const upgradeHref = '/pricing';
  const projectActionsDisabled = projectLimitReached || isDemoMode;
  const competitorActionsDisabled = competitorLimitReached || isDemoMode;

  return (
    <div className="space-y-8">
      <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-base">Manage Projects</h2>
        <p className="mt-1 text-sm text-gray-500">
          Projects ({projectLimitLabel}) - Subscription tier: {subscriptionLabel || 'CURRENT'}
        </p>
        {isDemoMode && (
          <p className="mt-3 text-xs font-semibold text-primary">
            Demo mode uses sample data. Project actions are read-only.
          </p>
        )}
        {projects.length === 0 ? (
          <p className="mt-4 text-sm text-gray-500">
            No projects yet. Create your first project below to start tracking competitors.
          </p>
        ) : (
          <div className="mt-4 space-y-3">
            {projects.map((project) => {
              const isSelected = project.id === selectedProjectId;
              const isDeleting = deletingProjectId === project.id;
              const createdDate = project.created_at ? new Date(project.created_at) : null;
              const createdLabel =
                createdDate && !Number.isNaN(createdDate.valueOf()) ? createdDate.toLocaleDateString() : null;

              return (
                <div
                  key={project.id}
                  className={clsx(
                    'flex flex-col gap-3 rounded-lg border border-gray-200 bg-gray-50 p-4 sm:flex-row sm:items-center sm:justify-between',
                    isSelected && 'border-primary/40 bg-primary/5',
                  )}
                >
                  <div>
                    <div className="text-sm font-semibold text-gray-base">
                      {project.name}
                      {isSelected && <span className="ml-2 text-xs text-primary">Active</span>}
                    </div>
                    <div className="mt-1 text-xs text-gray-500">
                      Home app: {project.home_app_name}
                      {' - '}
                      Competitors: {project.competitors_count ?? 0}
                      {createdLabel ? (
                        <>
                          {' - '}
                          Created {createdLabel}
                        </>
                      ) : null}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => onSelectProject?.(project.id)}
                      className={clsx(
                        'inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-semibold transition',
                        isSelected
                          ? 'border-primary bg-primary text-white shadow-sm'
                          : 'border-primary/30 text-primary hover:bg-primary/10',
                      )}
                      disabled={isSelected || Boolean(deletingProjectId) || !onSelectProject}
                      aria-disabled={isSelected || Boolean(deletingProjectId) || !onSelectProject}
                    >
                      {isSelected ? 'Active Project' : 'Switch to Project'}
                    </button>
                    <button
                      type="button"
                      onClick={() => onDeleteProject?.(project.id)}
                      className="inline-flex items-center gap-2 rounded-lg border border-danger/40 px-3 py-1.5 text-xs font-semibold text-danger hover:bg-danger/10 disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={isDeleting || !onDeleteProject || isDemoMode}
                      aria-disabled={isDeleting || !onDeleteProject || isDemoMode}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      {isDeleting ? 'Deleting...' : 'Delete'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-base">Create Project</h2>
        <p className="mt-1 text-sm text-gray-500">
          Monitor a new home app and its competitors. Project slots used: {projectLimitLabel}.
        </p>
        <form onSubmit={onCreateProject} className="mt-4 grid gap-4 md:grid-cols-3">
          <input
            name="name"
            type="text"
            placeholder="Project name"
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:cursor-not-allowed disabled:bg-gray-100"
            required
            disabled={projectActionsDisabled}
          />
          <input
            name="home_app_id"
            type="text"
            placeholder="Your App ID (e.g. com.deepfocal.app)"
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:cursor-not-allowed disabled:bg-gray-100"
            required
            disabled={projectActionsDisabled}
          />
          <input
            name="home_app_name"
            type="text"
            placeholder="Your App Name"
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:cursor-not-allowed disabled:bg-gray-100"
            required
            disabled={projectActionsDisabled}
          />
          <div className="md:col-span-3 flex flex-col gap-1">
            <label htmlFor="apple_app_id" className="text-sm font-semibold text-gray-base">
              Apple App Store ID (optional)
            </label>
            <input
              id="apple_app_id"
              name="apple_app_id"
              type="text"
              placeholder="e.g., 1033231837"
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:cursor-not-allowed disabled:bg-gray-100"
              disabled={projectActionsDisabled}
            />
            <p className="text-xs text-gray-500">
              Find in App Store URL: apps.apple.com/us/app/name/[ID]
            </p>
          </div>
          <div className="md:col-span-3">
            <button
              type="submit"
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white shadow hover:bg-primary/90 disabled:cursor-not-allowed disabled:bg-primary/50"
              disabled={projectActionsDisabled}
            >
              <Plus className="h-4 w-4" /> Create Project
            </button>
          </div>
        </form>
        {isDemoMode ? (
          <p className="mt-3 text-xs font-medium text-primary">
            Demo mode uses sample data. Project creation is disabled.
          </p>
        ) : projectLimitReached ? (
          <p className="mt-3 text-xs font-medium text-warning">
            Project limit reached for your {tierLabel || 'current'} plan. Delete a project or upgrade to add more.
          </p>
        ) : null}
      </section>

      {selectedProject && (
        <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-base">Add Competitor</h2>
          <p className="mt-1 text-sm text-gray-500">
            Project: {selectedProject.name}
            <span className="ml-2 text-xs text-gray-400">Competitors ({competitorLimitLabel})</span>
          </p>
          <form onSubmit={onAddCompetitor} className="mt-4 grid gap-4 md:grid-cols-3">
            <input
              name="app_id"
              type="text"
              placeholder="Competitor App ID"
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:cursor-not-allowed disabled:bg-gray-100"
              required
              disabled={competitorActionsDisabled}
            />
            <input
              name="app_name"
              type="text"
              placeholder="Competitor App Name"
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:cursor-not-allowed disabled:bg-gray-100"
              required
              disabled={competitorActionsDisabled}
            />
            <div className="flex items-center">
              <button
                type="submit"
                className="inline-flex items-center gap-2 rounded-lg border border-primary/30 px-4 py-2 text-sm font-semibold text-primary hover:bg-primary/10 disabled:cursor-not-allowed disabled:border-gray-200 disabled:text-gray-400 disabled:hover:bg-transparent disabled:opacity-60"
                disabled={competitorActionsDisabled}
                aria-disabled={competitorActionsDisabled}
              >
                Add Competitor
              </button>
            </div>
          </form>

          {isDemoMode ? (
            <p className="mt-3 text-xs font-medium text-primary">
              Demo mode uses sample data. Competitor management is disabled.
            </p>
          ) : competitorLimitReached ? (
            <p className="mt-3 text-xs font-medium text-warning">
              Your {tierLabel || 'current'} plan allows {competitorLimitValue} competitor{competitorLimitValue === 1 ? '' : 's'}. Upgrade to add more.
              {' '}
              <a href={upgradeHref} className="text-primary underline hover:text-primary/80">
                Upgrade plan
              </a>
            </p>
          ) : (
            competitorLimitValue !== null && remainingCompetitors !== null && (
              <p className="mt-3 text-xs text-gray-500">
                You can add {remainingCompetitors} more competitor{remainingCompetitors === 1 ? '' : 's'} on your plan.
              </p>
            )
          )}

          {competitors.length > 0 && (
            <div className="mt-6 space-y-3">
              <h3 className="text-sm font-semibold text-gray-base">
                Existing Competitors ({competitorLimitLabel})
              </h3>
              <div className="grid gap-3 sm:grid-cols-2">
                {competitors.map((competitor) => (
                  <div
                    key={competitor.appId}
                    className="flex items-center justify-between rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm"
                  >
                    <div>
                      <div className="font-medium text-gray-base">{competitor.name}</div>
                      <div className="text-xs text-gray-500">{competitor.status ? `Import ${competitor.status}` : 'Ready'}</div>
                    </div>
                    <div className="flex flex-col gap-2 sm:flex-row">
                      <button
                        type="button"
                        onClick={() => onSelectCompetitor?.(competitor.appId)}
                        className="rounded-lg border border-primary/30 px-3 py-1 text-xs font-semibold text-primary hover:bg-primary/10"
                      >
                        View
                      </button>
                      <button
                        type="button"
                        onClick={() => onDeleteCompetitor?.(competitor.competitorId, competitor.appId)}
                        className="rounded-lg border border-danger/30 px-3 py-1 text-xs font-semibold text-danger hover:bg-danger/10"
                        disabled={isDemoMode}
                        aria-disabled={isDemoMode}
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

function ComingSoon({ title }) {

  return (
    <div className="rounded-xl border border-dashed border-gray-300 bg-white p-16 text-center shadow-sm">
      <h2 className="text-2xl font-semibold text-gray-base">{title}</h2>
      <p className="mt-3 text-sm text-gray-500">This section is coming soon.</p>
    </div>
  );
}

export default PremiumDashboard;

