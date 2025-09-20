import React, { useEffect, useState } from 'react';
import apiClient from '../apiClient';

function ClassicDashboard() {
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState(null);
  const [statusData, setStatusData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadProjects = async () => {
      try {
        const response = await apiClient.get('/api/projects/');
        const list = response.data?.projects || [];
        setProjects(list);
        if (list.length > 0) {
          setSelectedProjectId(list[0].id);
        }
      } catch (err) {
        console.error(err);
        setError('Unable to load projects');
      } finally {
        setLoading(false);
      }
    };

    loadProjects();
  }, []);

  useEffect(() => {
    const loadStatus = async () => {
      if (!selectedProjectId) {
        return;
      }
      try {
        const response = await apiClient.get(`/api/projects/${selectedProjectId}/status/`);
        setStatusData(response.data);
      } catch (err) {
        console.error(err);
        setError('Unable to load project status');
      }
    };

    loadStatus();
  }, [selectedProjectId]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-background text-gray-base">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-primary/20 border-t-primary" />
      </div>
    );
  }

  const selectedProject = projects.find((project) => project.id === selectedProjectId);

  return (
    <div className="min-h-screen bg-gray-background px-6 py-12 text-gray-base">
      <div className="mx-auto max-w-4xl space-y-8">
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <h1 className="text-2xl font-semibold text-gray-base">Deepfocal Dashboard (Legacy)</h1>
          <p className="mt-2 text-sm text-gray-500">
            Premium dashboard is disabled. Enable the feature flag to unlock the full experience.
          </p>
        </div>

        {error && (
          <div className="rounded-xl border border-danger/20 bg-danger/10 px-4 py-3 text-sm text-danger">
            {error}
          </div>
        )}

        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <label className="text-xs font-medium text-gray-500">Project</label>
          <select
            value={selectedProjectId || ''}
            onChange={(event) => setSelectedProjectId(Number(event.target.value))}
            className="mt-2 w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40"
          >
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </div>

        {selectedProject && statusData && (
          <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="text-xl font-semibold text-gray-base">{selectedProject.name}</h2>
            <p className="text-sm text-gray-500">
              {selectedProject.home_app_name} vs {statusData.project_info?.competitors_count || 0} competitors
            </p>

            <table className="mt-4 w-full table-fixed border-separate border-spacing-y-2 text-left text-sm">
              <thead>
                <tr className="text-xs uppercase tracking-wide text-gray-500">
                  <th className="px-3 py-2">App</th>
                  <th className="px-3 py-2">Positive %</th>
                  <th className="px-3 py-2">Negative %</th>
                  <th className="px-3 py-2">Reviews</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(statusData.competitor_analysis || {}).map(([appId, data]) => (
                  <tr key={appId} className="rounded-lg bg-gray-50">
                    <td className="px-3 py-2">
                      <div className="font-medium text-gray-base">{data.app_name}</div>
                      <div className="text-xs text-gray-500">
                        {data.app_type === 'home' ? 'Your App' : 'Competitor'}
                      </div>
                    </td>
                    <td className="px-3 py-2">{data.positive_percentage}%</td>
                    <td className="px-3 py-2">{data.negative_percentage}%</td>
                    <td className="px-3 py-2">{data.total_reviews}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default ClassicDashboard;
