import React, { useState } from 'react';
import { scrapeJobs, JobFilters } from '../api';

interface FilterBarProps {
  onFilter: (filters: JobFilters) => void;
}

const FilterBar: React.FC<FilterBarProps> = ({ onFilter }) => {
  const [status, setStatus] = useState<string>('');
  const [keyword, setKeyword] = useState<string>('');
  const [dateRange, setDateRange] = useState<string>('all');
  const [scraping, setScraping] = useState<boolean>(false);
  const [scrapeMessage, setScrapeMessage] = useState<string>('');

  const getDateFrom = (range: string): string | undefined => {
    if (range === 'today') {
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      return today.toISOString().split('T')[0];
    }
    if (range === 'last7') {
      const d = new Date();
      d.setDate(d.getDate() - 7);
      return d.toISOString().split('T')[0];
    }
    return undefined;
  };

  const handleFilter = () => {
    const filters: JobFilters = {};
    if (status) filters.status = status;
    if (keyword.trim()) filters.keyword = keyword.trim();
    const dateFrom = getDateFrom(dateRange);
    if (dateFrom) filters.date_from = dateFrom;
    onFilter(filters);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleFilter();
  };

  const handleScrape = async () => {
    setScraping(true);
    setScrapeMessage('');
    try {
      const result = await scrapeJobs();
      setScrapeMessage(result.message || 'Scrape triggered successfully');
    } catch (err: any) {
      setScrapeMessage(err?.response?.data?.detail || 'Failed to trigger scrape');
    } finally {
      setScraping(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    padding: '8px 12px',
    borderRadius: '8px',
    border: '1px solid #d1d5db',
    fontSize: '14px',
    outline: 'none',
    background: '#fff',
    color: '#1a1a2e',
    transition: 'border-color 0.2s',
  };

  const buttonStyle: React.CSSProperties = {
    padding: '8px 20px',
    borderRadius: '8px',
    border: 'none',
    fontSize: '14px',
    fontWeight: '600',
    cursor: 'pointer',
    transition: 'background 0.2s, transform 0.1s',
  };

  return (
    <div
      style={{
        background: '#fff',
        borderRadius: '12px',
        padding: '16px 20px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
        marginBottom: '20px',
      }}
    >
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '12px',
          alignItems: 'center',
        }}
      >
        {/* Status filter */}
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          style={{ ...inputStyle, minWidth: '140px' }}
        >
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="applied">Applied</option>
          <option value="failed">Failed</option>
          <option value="skipped">Skipped</option>
        </select>

        {/* Keyword filter */}
        <input
          type="text"
          placeholder="Search keyword..."
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onKeyDown={handleKeyDown}
          style={{ ...inputStyle, minWidth: '200px', flexGrow: 1 }}
        />

        {/* Date filter */}
        <select
          value={dateRange}
          onChange={(e) => setDateRange(e.target.value)}
          style={{ ...inputStyle, minWidth: '140px' }}
        >
          <option value="all">All time</option>
          <option value="today">Today</option>
          <option value="last7">Last 7 days</option>
        </select>

        {/* Apply filters button */}
        <button
          onClick={handleFilter}
          style={{
            ...buttonStyle,
            background: '#3b82f6',
            color: '#fff',
          }}
          onMouseOver={(e) => (e.currentTarget.style.background = '#2563eb')}
          onMouseOut={(e) => (e.currentTarget.style.background = '#3b82f6')}
        >
          Apply Filters
        </button>

        {/* Trigger scrape button */}
        <button
          onClick={handleScrape}
          disabled={scraping}
          style={{
            ...buttonStyle,
            background: scraping ? '#9ca3af' : '#10b981',
            color: '#fff',
            cursor: scraping ? 'not-allowed' : 'pointer',
          }}
        >
          {scraping ? (
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span
                style={{
                  display: 'inline-block',
                  width: '12px',
                  height: '12px',
                  border: '2px solid #fff',
                  borderTopColor: 'transparent',
                  borderRadius: '50%',
                  animation: 'spin 0.8s linear infinite',
                }}
              />
              Scraping...
            </span>
          ) : (
            'Trigger Scrape'
          )}
        </button>
      </div>

      {/* Scrape status message */}
      {scrapeMessage && (
        <div
          style={{
            marginTop: '10px',
            padding: '8px 12px',
            borderRadius: '6px',
            background: scrapeMessage.toLowerCase().includes('fail') ? '#fef2f2' : '#f0fdf4',
            color: scrapeMessage.toLowerCase().includes('fail') ? '#dc2626' : '#15803d',
            fontSize: '13px',
          }}
        >
          {scrapeMessage}
        </div>
      )}

      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};

export default FilterBar;
