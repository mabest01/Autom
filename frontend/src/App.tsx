import React, { useState, useEffect, useCallback } from 'react';
import { getJobs, getStats, applyJob, updateMessage, Job, Stats, JobFilters } from './api';
import StatsPanel from './components/StatsPanel';
import FilterBar from './components/FilterBar';
import JobsTable from './components/JobsTable';

const REFRESH_INTERVAL_MS = 30000; // 30 seconds

const App: React.FC = () => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [filters, setFilters] = useState<JobFilters>({});
  const [loadingJobs, setLoadingJobs] = useState<boolean>(true);
  const [loadingStats, setLoadingStats] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);

  const fetchStats = useCallback(async () => {
    setLoadingStats(true);
    try {
      const s = await getStats();
      setStats(s);
      setBackendOnline(true);
    } catch (err) {
      setBackendOnline(false);
    } finally {
      setLoadingStats(false);
    }
  }, []);

  const fetchJobs = useCallback(async (activeFilters: JobFilters = {}) => {
    setLoadingJobs(true);
    setError(null);
    try {
      const j = await getJobs(activeFilters);
      setJobs(j);
      setLastRefreshed(new Date());
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to load jobs');
    } finally {
      setLoadingJobs(false);
    }
  }, []);

  const refreshAll = useCallback(
    (activeFilters: JobFilters = filters) => {
      fetchStats();
      fetchJobs(activeFilters);
    },
    [filters, fetchStats, fetchJobs]
  );

  // Initial load
  useEffect(() => {
    refreshAll({});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      refreshAll(filters);
    }, REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [filters, refreshAll]);

  const handleFilter = (newFilters: JobFilters) => {
    setFilters(newFilters);
    refreshAll(newFilters);
  };

  const handleApply = async (jobId: number) => {
    try {
      await applyJob(jobId);
      // Refresh after a short delay to pick up status change
      setTimeout(() => refreshAll(filters), 3000);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to trigger application');
    }
  };

  const handleUpdateMessage = async (jobId: number, message: string) => {
    try {
      await updateMessage(jobId, message);
      // Update local state immediately
      setJobs((prev) =>
        prev.map((j) => (j.id === jobId ? { ...j, generated_message: message } : j))
      );
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to update message');
    }
  };

  const formatLastRefreshed = (date: Date | null): string => {
    if (!date) return '';
    return date.toLocaleTimeString('fr-FR', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        background: '#f0f2f5',
        fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      }}
    >
      {/* Header */}
      <header
        style={{
          background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
          color: '#fff',
          padding: '0 24px',
          boxShadow: '0 2px 12px rgba(0,0,0,0.3)',
        }}
      >
        <div
          style={{
            maxWidth: '1400px',
            margin: '0 auto',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            height: '64px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '8px',
                background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '18px',
                fontWeight: '700',
              }}
            >
              H
            </div>
            <div>
              <h1 style={{ fontSize: '18px', fontWeight: '700', margin: 0, letterSpacing: '-0.3px' }}>
                HelloWork Automation Dashboard
              </h1>
              <p style={{ fontSize: '12px', color: '#93c5fd', margin: 0 }}>
                Job Application Automation System
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            {/* Backend status indicator */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <div
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background:
                    backendOnline === null
                      ? '#f59e0b'
                      : backendOnline
                      ? '#10b981'
                      : '#ef4444',
                  boxShadow: backendOnline
                    ? '0 0 6px #10b981'
                    : backendOnline === false
                    ? '0 0 6px #ef4444'
                    : 'none',
                }}
              />
              <span style={{ fontSize: '13px', color: '#d1d5db' }}>
                {backendOnline === null ? 'Connecting…' : backendOnline ? 'Online' : 'Offline'}
              </span>
            </div>

            {/* Last refreshed */}
            {lastRefreshed && (
              <span style={{ fontSize: '12px', color: '#9ca3af' }}>
                Last updated: {formatLastRefreshed(lastRefreshed)}
              </span>
            )}

            {/* Manual refresh button */}
            <button
              onClick={() => refreshAll(filters)}
              style={{
                background: 'rgba(255,255,255,0.1)',
                border: '1px solid rgba(255,255,255,0.2)',
                borderRadius: '8px',
                color: '#fff',
                padding: '6px 14px',
                fontSize: '13px',
                cursor: 'pointer',
                transition: 'background 0.2s',
              }}
              onMouseOver={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.2)')}
              onMouseOut={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.1)')}
            >
              Refresh
            </button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main
        style={{
          maxWidth: '1400px',
          margin: '0 auto',
          padding: '24px',
        }}
      >
        {/* Error banner */}
        {error && (
          <div
            style={{
              background: '#fef2f2',
              border: '1px solid #fecaca',
              borderRadius: '8px',
              padding: '12px 16px',
              marginBottom: '20px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <span style={{ color: '#dc2626', fontSize: '14px' }}>{error}</span>
            <button
              onClick={() => setError(null)}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: '#dc2626',
                fontSize: '18px',
                lineHeight: 1,
              }}
            >
              x
            </button>
          </div>
        )}

        {/* Stats Panel */}
        <StatsPanel stats={stats} loading={loadingStats} />

        {/* Filter Bar */}
        <FilterBar onFilter={handleFilter} />

        {/* Jobs Table */}
        <JobsTable
          jobs={jobs}
          onApply={handleApply}
          onUpdateMessage={handleUpdateMessage}
          loading={loadingJobs}
        />
      </main>

      {/* Footer */}
      <footer
        style={{
          textAlign: 'center',
          padding: '20px',
          color: '#9ca3af',
          fontSize: '12px',
        }}
      >
        HelloWork Automation Dashboard — Auto-refreshes every 30 seconds
      </footer>
    </div>
  );
};

export default App;
