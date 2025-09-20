import React, { useEffect, useMemo, useState } from 'react';
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
  Calendar,

  Plus,
  RefreshCw,
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

const clamp = (value, min = 0, max = 100) => Math.max(min, Math.min(max, value));

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
  const [selectedAppKey, setSelectedAppKey] = useState('home');
  const [dateRange, setDateRange] = useState('30d');

  const [statusData, setStatusData] = useState(null);
  const [sentimentSeries, setSentimentSeries] = useState([]);
  const [painPoints, setPainPoints] = useState([]);
  const [strengths, setStrengths] = useState([]);

  const [loadingDashboard, setLoadingDashboard] = useState(false);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [panelMessage, setPanelMessage] = useState('');

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
    };
  }, [selectedAppMeta, selectedProject, statusData]);
  const activeTasks = statusData?.active_tasks || [];

  const loadProjects = async () => {
    try {
      setLoadingProjects(true);
      const response = await apiClient.get('/api/projects/');
      const { projects = [], user_limits: userLimits } = response.data || {};
      setProjectsState({ projects, userLimits });

      if (!selectedProjectId && projects.length > 0) {
        setSelectedProjectId(projects[0].id);
      }
      setPanelMessage('');
    } catch (error) {
      console.error('Failed to load projects', error);
      setPanelMessage('Unable to load projects. Please refresh.');
    } finally {
      setLoadingProjects(false);
    }
  };

  useEffect(() => {
    loadProjects();
  }, []);
  const loadProjectAnalytics = async (projectId, appMeta) => {
    if (!projectId || !appMeta?.appId) {
      return;
    }

    try {
      setLoadingDashboard(true);

      const [statusResponse, sentimentResponse, painResponse, strengthResponse] = await Promise.all([
          apiClient.get(`/api/projects/${projectId}/status/`),
          apiClient.get(`/api/projects/${projectId}/sentiment-trends/`, {
            params: {
              app_id: appMeta.appId,
              date_range: dateRange,
              ...(appMeta.compareTo ? { compare_to: appMeta.compareTo } : {}),
            },
          }),
          apiClient.get('/api/enhanced-insights/', {
            params: { app_id: appMeta.appId },
          }),
          apiClient.get('/api/strengths/', {
            params: { app_id: appMeta.appId },
          }),
        ]);

      setStatusData(statusResponse.data);
      setSentimentSeries(sentimentResponse.data?.series || []);

      const painPayload = painResponse.data || {};
      const totalNeg = painPayload.review_count_analyzed || 0;
      const mappedPain = (painPayload.lda_pain_points || []).map((item, index) => {
        const mentions = item.review_count || item.sample_size || item.quotes?.length || 0;
        const denominator = totalNeg || item.review_count || 1;
        const baseValue = item.review_percentage || mentions;
        const percentage = Math.round(((baseValue || 0) / denominator) * 1000) / 10;
        return {
          id: `${appMeta.appId}-pain-${index}`,
          title: item.issue,
          mentions,
          percentage: Number.isFinite(percentage) ? percentage : 0,
          quotes: item.quotes || [],
        };
      });
      setPainPoints(mappedPain.slice(0, 3));

      const strengthPayload = strengthResponse.data || {};
      const totalPos = strengthPayload.review_count_analyzed || 0;
      const mappedStrengths = (strengthPayload.lda_strengths || []).map((item, index) => {
        const mentions = item.review_count || item.sample_size || item.quotes?.length || 0;
        const denominator = totalPos || item.review_count || 1;
        const baseValue = item.review_percentage || mentions;
        const percentage = Math.round(((baseValue || 0) / denominator) * 1000) / 10;
        return {
          id: `${appMeta.appId}-strength-${index}`,
          title: item.issue,
          mentions,
          percentage: Number.isFinite(percentage) ? percentage : 0,
          quotes: item.quotes || [],
        };
      });
      setStrengths(mappedStrengths.slice(0, 3));

      setPanelMessage('');
    } catch (error) {
      console.error('Failed to load dashboard analytics', error);
      setPanelMessage('Unable to load dashboard analytics. Please retry.');
    } finally {
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
    const form = event.target;
    const payload = {
      name: form.name.value.trim(),
      home_app_id: form.home_app_id.value.trim(),
      home_app_name: form.home_app_name.value.trim(),
    };

    if (!payload.name || !payload.home_app_id || !payload.home_app_name) {
      return;
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

    try {
      await apiClient.post('/api/projects/add-competitor/', payload);
      form.reset();
      await loadProjectAnalytics(selectedProjectId, selectedAppMeta);
    } catch (error) {
      console.error('Failed to add competitor', error);
      setPanelMessage(error.response?.data?.error || 'Unable to add competitor');
    }
  };

  const handleStartAnalysis = async (appId, analysisType = 'quick') => {
    if (!selectedProjectId || !appId) {
      return;
    }
    try {
      await apiClient.post('/api/analysis/start/', {
        project_id: selectedProjectId,
        app_id: appId,
        analysis_type: analysisType,
      });
      await loadProjectAnalytics(selectedProjectId, selectedAppMeta);
    } catch (error) {
      console.error('Failed to start analysis', error);
      setPanelMessage(error.response?.data?.error || 'Unable to start analysis');
    }
  };

  return (
    <div className="flex h-screen bg-gray-background text-gray-base">
      <aside className="flex w-64 flex-col bg-gray-base text-white">
        <div className="border-b border-white/10 p-6">
          <h1 className="text-xl font-semibold">Deepfocal</h1>
          <p className="mt-1 text-xs text-white/70">{user?.username || 'Analyst'}</p>
        </div>
        <nav className="flex-1 overflow-y-auto py-6">
          {navigationItems.map((group) => (
            <div key={group.group} className="mb-8">
              <h3 className="px-6 text-xs font-medium uppercase tracking-wider text-white/50">
                {group.group}
              </h3>
              <div className="mt-3 space-y-1">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const isActive = activeTab === item.id;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setActiveTab(item.id)}
                      className={clsx(
                        'flex w-full items-center px-6 py-3 text-sm transition-colors',
                        isActive
                          ? 'border-r-2 border-primary bg-white/5 font-medium text-white'
                          : 'text-white/70 hover:bg-white/10 hover:text-white',
                      )}
                    >
                      <Icon className="mr-3 h-5 w-5" />
                      {item.label}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <GlobalHeader
          projects={projectsState.projects}
          selectedProjectId={selectedProjectId}
          onSelectProject={handleProjectChange}
          appOptions={appOptions}
          selectedAppKey={selectedAppKey}
          onSelectApp={setSelectedAppKey}
          dateRange={dateRange}
          onSelectDateRange={setDateRange}
        />

        <div className="mx-auto max-w-7xl px-8 py-8">
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
                />
              )}

              {activeTab === 'pain-points' && (
                <PainStrengthsTab painPoints={painPoints} strengths={strengths} />
              )}

              {activeTab === 'project-settings' && (
                <ProjectSettingsTab
                  selectedProject={selectedProject}
                  projectsState={projectsState}
                  onCreateProject={handleCreateProject}
                  onAddCompetitor={handleAddCompetitor}
                />
              )}

              {['review-explorer', 'collections', 'alerts'].includes(activeTab) && (
                <ComingSoon title={navigationItems.flatMap((group) => group.items).find((item) => item.id === activeTab)?.label || 'Coming Soon'} />
              )}
            </section>
          )}
        </div>
      </main>
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
}) {
  return (
    <div className="border-b border-gray-200 bg-white px-8 py-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <label className="text-xs font-medium text-gray-500">Project</label>
            <select
              value={selectedProjectId || ''}
              onChange={(event) => onSelectProject(Number(event.target.value))}
              className="mt-1 w-56 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-base focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40"
            >
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
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

  const sentimentData = sentimentSeries.map((row) => ({
    date: row.date,
    positive: row.positive,
    negative: row.negative,
    competitor: row.competitor ?? null,
  }));

  return (
    <div className="space-y-8">
      <section className="rounded-xl border border-gray-200 bg-white p-8 shadow-sm">
        <header className="mb-6 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-base">Strategic Performance · {contextLabel}</h2>
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
          <div className="rounded-xl border border-gray-200 p-6 text-center">
            <div className="text-3xl font-bold text-primary">{categoryRanking.label}</div>
            <p className="mt-2 text-sm font-medium text-gray-base">Category Ranking</p>
            <div
              className={clsx(
                'mt-3 inline-flex items-center rounded-full px-3 py-1 text-xs font-medium',
                rankingBadgeTone === 'danger' ? 'bg-danger/10 text-danger' : 'bg-primary/10 text-primary',
              )}
            >
              <RankingIcon className="mr-1 h-3 w-3" />{' '}
              {rankingDirection === 'down' ? 'Down' : 'Up'} {categoryRanking.trend?.delta ?? 2} spots
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-gray-200 bg-white p-8 shadow-sm">
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
    <div className="flex items-center gap-4 text-sm text-gray-500">
      <LegendDot color="#14b8a6" label="Positive Sentiment" />
      <LegendDot color="#ef4444" label="Negative Sentiment" />
      {compareEnabled && (
        <LegendDot color="#9ca3af" label={referenceLabel} dashed />
      )}
    </div>
  </div>
</header>
        <div className={chartExpanded ? "h-96" : "h-48"}>
          {sentimentData.length === 0 ? (
            <div className="flex h-full items-center justify-center text-sm text-gray-500">
              Not enough data yet. Trigger an analysis run to populate this chart.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
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

      <section className="grid gap-8 md:grid-cols-2">
        <ExpandableCard
          title="Top 3 Pain Points"
          accent="danger"
          items={painPoints}
          emptyMessage="No negative themes detected yet."
        />
        <ExpandableCard
          title="Top 3 Strengths"
          accent="primary"
          items={strengths}
          emptyMessage="No positive themes detected yet."
        />
      </section>
    </div>
  );
}
function ScoreCard({ title, value, badgeLabel, badgeTone = 'primary' }) {
  const toneClasses = {
    primary: 'bg-primary/10 text-primary',
    warning: 'bg-warning/10 text-warning',
    danger: 'bg-danger/10 text-danger',
  };

  return (
    <div className="rounded-xl border border-gray-200 p-6 text-center">
      <div className="text-3xl font-bold text-gray-base">{value}</div>
      <p className="mt-2 text-sm font-medium text-gray-base">{title}</p>
      <div
        className={clsx(
          'mt-3 inline-flex items-center rounded-full px-3 py-1 text-xs font-medium',
          toneClasses[badgeTone] || toneClasses.primary,
        )}
      >
        {badgeLabel}
      </div>
    </div>
  );
}

function LegendDot({ color, label, dashed = false }) {
  return (
    <div className="flex items-center gap-2">
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
    <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
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
                  <h4 className="font-medium text-gray-base">{item.title}</h4>
                  <p className="text-xs text-gray-500">
                    {item.mentions || 0} mentions • {item.percentage || 0}% of reviews
                  </p>
                </div>
              </div>
              <ChevronDown
                className={clsx('h-4 w-4 text-gray-400 transition-transform', expandedId === item.id && 'rotate-180')}
              />
            </button>
            {expandedId === item.id && (
              <div className="mt-4 space-y-3">
                {(item.quotes || []).map((quote, quoteIndex) => (
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
        ))}
      </div>
    </div>
  );
}
function CompetitorAnalysisTab({ statusData, selectedProject, onStartAnalysis }) {
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
                    >
                      Quick Analysis
                    </button>
                    <button
                      type="button"
                      onClick={() => onStartAnalysis(appId, 'full')}
                      className="inline-flex items-center gap-2 rounded-lg border border-warning/30 px-3 py-1.5 text-xs font-semibold text-warning hover:bg-warning/10"
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
                {task.app_name}: {task.task_type} Ã‚Â· {Math.round(task.progress_percent || 0)}%
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
        emptyMessage="No negative sentiment detected."
      />
      <ExpandableCard
        title="Positive Themes"
        accent="primary"
        items={strengths}
        emptyMessage="No positive sentiment detected."
      />
    </div>
  );
}

function ProjectSettingsTab({ selectedProject, projectsState, onCreateProject, onAddCompetitor }) {
  const userLimits = projectsState.userLimits || {};

  return (
    <div className="space-y-8">
      <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-base">Create Project</h2>
        <p className="mt-1 text-sm text-gray-500">
          Projects ({projectsState.projects.length}/{userLimits.project_limit || 1}) Ã‚Â· Subscription tier:{' '}
          {userLimits.subscription_tier?.toUpperCase()}
        </p>
        <form onSubmit={onCreateProject} className="mt-4 grid gap-4 md:grid-cols-3">
          <input
            name="name"
            type="text"
            placeholder="Project name"
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40"
            required
          />
          <input
            name="home_app_id"
            type="text"
            placeholder="Your App ID (e.g. com.deepfocal.app)"
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40"
            required
          />
          <input
            name="home_app_name"
            type="text"
            placeholder="Your App Name"
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40"
            required
          />
          <div className="md:col-span-3">
            <button
              type="submit"
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white shadow hover:bg-primary/90"
            >
              <Plus className="h-4 w-4" /> Create Project
            </button>
          </div>
        </form>
      </section>

      {selectedProject && (
        <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-base">Add Competitor</h2>
          <p className="mt-1 text-sm text-gray-500">Project: {selectedProject.name}</p>
          <form onSubmit={onAddCompetitor} className="mt-4 grid gap-4 md:grid-cols-3">
            <input
              name="app_id"
              type="text"
              placeholder="Competitor App ID"
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40"
              required
            />
            <input
              name="app_name"
              type="text"
              placeholder="Competitor App Name"
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40"
              required
            />
            <div className="flex items-center">
              <button
                type="submit"
                className="inline-flex items-center gap-2 rounded-lg border border-primary/30 px-4 py-2 text-sm font-semibold text-primary hover:bg-primary/10"
              >
                Add Competitor
              </button>
            </div>
          </form>
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






















