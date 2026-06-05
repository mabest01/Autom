import React from 'react';
import { Stats } from '../api';

interface StatsPanelProps {
  stats: Stats | null;
  loading: boolean;
}

interface StatCardProps {
  label: string;
  value: string | number;
  color: string;
  bgColor: string;
  loading: boolean;
}

const StatCard: React.FC<StatCardProps> = ({ label, value, color, bgColor, loading }) => (
  <div
    style={{
      background: '#ffffff',
      borderRadius: '12px',
      padding: '24px',
      boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
      borderLeft: `4px solid ${color}`,
      flex: '1',
      minWidth: '180px',
    }}
  >
    {loading ? (
      <div>
        <div
          style={{
            height: '36px',
            width: '60%',
            borderRadius: '6px',
            background: 'linear-gradient(90deg, #e8e8e8 25%, #f5f5f5 50%, #e8e8e8 75%)',
            backgroundSize: '200% 100%',
            animation: 'shimmer 1.5s infinite',
            marginBottom: '8px',
          }}
        />
        <div
          style={{
            height: '16px',
            width: '80%',
            borderRadius: '4px',
            background: 'linear-gradient(90deg, #e8e8e8 25%, #f5f5f5 50%, #e8e8e8 75%)',
            backgroundSize: '200% 100%',
            animation: 'shimmer 1.5s infinite',
          }}
        />
      </div>
    ) : (
      <div>
        <div
          style={{
            fontSize: '36px',
            fontWeight: '700',
            color: color,
            lineHeight: '1.1',
            marginBottom: '6px',
          }}
        >
          {value}
        </div>
        <div
          style={{
            fontSize: '14px',
            color: '#666',
            fontWeight: '500',
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
          }}
        >
          {label}
        </div>
      </div>
    )}
  </div>
);

const StatsPanel: React.FC<StatsPanelProps> = ({ stats, loading }) => {
  return (
    <>
      <style>{`
        @keyframes shimmer {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
      `}</style>
      <div
        style={{
          display: 'flex',
          gap: '16px',
          flexWrap: 'wrap',
          marginBottom: '24px',
        }}
      >
        <StatCard
          label="Total Jobs Found"
          value={stats?.total ?? 0}
          color="#3b82f6"
          bgColor="#eff6ff"
          loading={loading}
        />
        <StatCard
          label="Applied Today"
          value={stats?.applied_today ?? 0}
          color="#10b981"
          bgColor="#ecfdf5"
          loading={loading}
        />
        <StatCard
          label="Pending"
          value={stats?.pending ?? 0}
          color="#f59e0b"
          bgColor="#fffbeb"
          loading={loading}
        />
        <StatCard
          label="Success Rate"
          value={`${stats?.success_rate ?? 0}%`}
          color="#8b5cf6"
          bgColor="#f5f3ff"
          loading={loading}
        />
      </div>
    </>
  );
};

export default StatsPanel;
