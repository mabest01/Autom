import React, { useState } from 'react';
import { Job } from '../api';

export type JobsTableActions = {
  onApply: (jobId: number) => void;
  onUpdateMessage: (jobId: number, message: string) => void;
  onRegenerate: (jobId: number) => void;
  onDelete: (jobId: number) => void;
};

interface JobsTableProps {
  jobs: Job[];
  onApply: (jobId: number) => void;
  onUpdateMessage: (jobId: number, message: string) => void;
  onRegenerate: (jobId: number) => void;
  onDelete: (jobId: number) => void;
  loading: boolean;
}

const PAGE_SIZE = 10;

const StatusBadge: React.FC<{ status: Job['status'] }> = ({ status }) => {
  const config: Record<Job['status'], { bg: string; color: string; label: string }> = {
    pending: { bg: '#fef3c7', color: '#b45309', label: 'Pending' },
    applied: { bg: '#d1fae5', color: '#065f46', label: 'Applied' },
    failed: { bg: '#fee2e2', color: '#991b1b', label: 'Failed' },
    skipped: { bg: '#f3f4f6', color: '#374151', label: 'Skipped' },
  };
  const c = config[status] ?? config.pending;
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 10px',
        borderRadius: '9999px',
        fontSize: '12px',
        fontWeight: '600',
        background: c.bg,
        color: c.color,
        whiteSpace: 'nowrap',
      }}
    >
      {c.label}
    </span>
  );
};

const SkeletonRow: React.FC = () => (
  <tr>
    {[1, 2, 3, 4, 5, 6, 7].map((i) => (
      <td key={i} style={{ padding: '12px 16px' }}>
        <div
          style={{
            height: '16px',
            borderRadius: '4px',
            background: 'linear-gradient(90deg, #e8e8e8 25%, #f5f5f5 50%, #e8e8e8 75%)',
            backgroundSize: '200% 100%',
            animation: 'shimmer 1.5s infinite',
          }}
        />
      </td>
    ))}
  </tr>
);

const JobsTable: React.FC<JobsTableProps> = ({ jobs, onApply, onUpdateMessage, onRegenerate, onDelete, loading }) => {
  const [currentPage, setCurrentPage] = useState(1);
  const [expandedMessages, setExpandedMessages] = useState<Set<number>>(new Set());
  const [editingJobId, setEditingJobId] = useState<number | null>(null);
  const [editingText, setEditingText] = useState<string>('');
  const [applyingJobId, setApplyingJobId] = useState<number | null>(null);
  const [savingJobId, setSavingJobId] = useState<number | null>(null);
  const [regeneratingJobId, setRegeneratingJobId] = useState<number | null>(null);
  const [deletingJobId, setDeletingJobId] = useState<number | null>(null);

  const totalPages = Math.ceil(jobs.length / PAGE_SIZE);
  const startIndex = (currentPage - 1) * PAGE_SIZE;
  const paginatedJobs = jobs.slice(startIndex, startIndex + PAGE_SIZE);

  const toggleExpand = (jobId: number) => {
    setExpandedMessages((prev) => {
      const next = new Set(prev);
      if (next.has(jobId)) next.delete(jobId);
      else next.add(jobId);
      return next;
    });
  };

  const startEditing = (job: Job) => {
    setEditingJobId(job.id);
    setEditingText(job.generated_message ?? '');
  };

  const cancelEditing = () => {
    setEditingJobId(null);
    setEditingText('');
  };

  const saveMessage = async (jobId: number) => {
    setSavingJobId(jobId);
    try {
      await onUpdateMessage(jobId, editingText);
    } finally {
      setSavingJobId(null);
      setEditingJobId(null);
      setEditingText('');
    }
  };

  const handleApply = async (jobId: number) => {
    setApplyingJobId(jobId);
    try {
      await onApply(jobId);
    } finally {
      setApplyingJobId(null);
    }
  };

  const handleRegenerate = async (jobId: number) => {
    setRegeneratingJobId(jobId);
    try {
      await onRegenerate(jobId);
    } finally {
      setRegeneratingJobId(null);
    }
  };

  const handleDelete = async (jobId: number) => {
    if (!window.confirm('Delete this job? This cannot be undone.')) return;
    setDeletingJobId(jobId);
    try {
      await onDelete(jobId);
    } finally {
      setDeletingJobId(null);
    }
  };

  const cellStyle: React.CSSProperties = {
    padding: '12px 16px',
    borderBottom: '1px solid #f0f0f0',
    verticalAlign: 'top',
    fontSize: '14px',
    color: '#374151',
  };

  const headerStyle: React.CSSProperties = {
    padding: '12px 16px',
    textAlign: 'left',
    fontSize: '12px',
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    color: '#6b7280',
    borderBottom: '2px solid #e5e7eb',
    whiteSpace: 'nowrap',
  };

  const formatDate = (dateStr: string | null): string => {
    if (!dateStr) return '—';
    try {
      return new Date(dateStr).toLocaleDateString('fr-FR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div
      style={{
        background: '#fff',
        borderRadius: '12px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
        overflow: 'hidden',
      }}
    >
      <style>{`
        @keyframes shimmer {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
        .jobs-table tr:hover td {
          background: #f9fafb;
        }
        .btn-action {
          padding: 5px 12px;
          border-radius: 6px;
          border: none;
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          transition: background 0.2s;
          white-space: nowrap;
        }
        .btn-apply {
          background: #10b981;
          color: #fff;
        }
        .btn-apply:hover {
          background: #059669;
        }
        .btn-apply:disabled {
          background: #9ca3af;
          cursor: not-allowed;
        }
        .btn-edit {
          background: #e0e7ff;
          color: #3730a3;
        }
        .btn-edit:hover {
          background: #c7d2fe;
        }
        .btn-save {
          background: #3b82f6;
          color: #fff;
        }
        .btn-save:hover {
          background: #2563eb;
        }
        .btn-cancel {
          background: #f3f4f6;
          color: #374151;
        }
        .btn-cancel:hover {
          background: #e5e7eb;
        }
        .btn-regen {
          background: #fef3c7;
          color: #92400e;
        }
        .btn-regen:hover {
          background: #fde68a;
        }
        .btn-regen:disabled {
          background: #9ca3af;
          color: #fff;
          cursor: not-allowed;
        }
        .btn-delete {
          background: #fee2e2;
          color: #991b1b;
        }
        .btn-delete:hover {
          background: #fecaca;
        }
        .btn-delete:disabled {
          background: #9ca3af;
          color: #fff;
          cursor: not-allowed;
        }
      `}</style>

      {/* Table header info */}
      <div
        style={{
          padding: '16px 20px',
          borderBottom: '1px solid #e5e7eb',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <span style={{ fontSize: '15px', fontWeight: '600', color: '#1f2937' }}>
          Jobs ({jobs.length})
        </span>
        {totalPages > 1 && (
          <span style={{ fontSize: '13px', color: '#6b7280' }}>
            Page {currentPage} / {totalPages}
          </span>
        )}
      </div>

      {/* Scrollable table */}
      <div style={{ overflowX: 'auto' }}>
        <table className="jobs-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead style={{ background: '#f9fafb' }}>
            <tr>
              <th style={headerStyle}>Title</th>
              <th style={headerStyle}>Company</th>
              <th style={headerStyle}>Location</th>
              <th style={headerStyle}>Status</th>
              <th style={{ ...headerStyle, minWidth: '240px' }}>Cover Message</th>
              <th style={headerStyle}>Date</th>
              <th style={{ ...headerStyle, textAlign: 'center' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)
            ) : paginatedJobs.length === 0 ? (
              <tr>
                <td
                  colSpan={7}
                  style={{
                    textAlign: 'center',
                    padding: '48px',
                    color: '#9ca3af',
                    fontSize: '15px',
                  }}
                >
                  No jobs found. Try adjusting filters or trigger a scrape.
                </td>
              </tr>
            ) : (
              paginatedJobs.map((job) => {
                const isExpanded = expandedMessages.has(job.id);
                const isEditing = editingJobId === job.id;
                const message = job.generated_message ?? '';
                const truncatedMsg = message.length > 100 ? message.slice(0, 100) + '…' : message;

                return (
                  <tr key={job.id}>
                    {/* Title */}
                    <td style={cellStyle}>
                      <a
                        href={job.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          color: '#3b82f6',
                          textDecoration: 'none',
                          fontWeight: '500',
                        }}
                        onMouseOver={(e) => (e.currentTarget.style.textDecoration = 'underline')}
                        onMouseOut={(e) => (e.currentTarget.style.textDecoration = 'none')}
                      >
                        {job.title}
                      </a>
                    </td>

                    {/* Company */}
                    <td style={{ ...cellStyle, whiteSpace: 'nowrap' }}>
                      {job.company || '—'}
                    </td>

                    {/* Location */}
                    <td style={{ ...cellStyle, whiteSpace: 'nowrap', color: '#6b7280' }}>
                      {job.location || '—'}
                    </td>

                    {/* Status */}
                    <td style={cellStyle}>
                      <StatusBadge status={job.status} />
                    </td>

                    {/* Generated Message */}
                    <td style={{ ...cellStyle, minWidth: '240px' }}>
                      {isEditing ? (
                        <div>
                          <textarea
                            value={editingText}
                            onChange={(e) => setEditingText(e.target.value)}
                            rows={4}
                            style={{
                              width: '100%',
                              padding: '8px',
                              borderRadius: '6px',
                              border: '1px solid #d1d5db',
                              fontSize: '13px',
                              resize: 'vertical',
                              outline: 'none',
                              fontFamily: 'inherit',
                            }}
                          />
                          <div style={{ display: 'flex', gap: '6px', marginTop: '6px' }}>
                            <button
                              className="btn-action btn-save"
                              onClick={() => saveMessage(job.id)}
                              disabled={savingJobId === job.id}
                            >
                              {savingJobId === job.id ? 'Saving…' : 'Save'}
                            </button>
                            <button className="btn-action btn-cancel" onClick={cancelEditing}>
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div>
                          <p style={{ fontSize: '13px', color: '#4b5563', lineHeight: '1.4', margin: 0 }}>
                            {message
                              ? isExpanded
                                ? message
                                : truncatedMsg
                              : <span style={{ color: '#9ca3af', fontStyle: 'italic' }}>No message yet</span>}
                          </p>
                          {message.length > 100 && (
                            <button
                              onClick={() => toggleExpand(job.id)}
                              style={{
                                background: 'none',
                                border: 'none',
                                color: '#3b82f6',
                                cursor: 'pointer',
                                fontSize: '12px',
                                padding: '2px 0',
                                marginTop: '4px',
                              }}
                            >
                              {isExpanded ? 'Show less' : 'Show more'}
                            </button>
                          )}
                        </div>
                      )}
                    </td>

                    {/* Date */}
                    <td style={{ ...cellStyle, whiteSpace: 'nowrap', fontSize: '12px', color: '#6b7280' }}>
                      {formatDate(job.created_at)}
                    </td>

                    {/* Actions */}
                    <td style={{ ...cellStyle, textAlign: 'center' }}>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', justifyContent: 'center' }}>
                        {job.status === 'pending' && !isEditing && (
                          <button
                            className="btn-action btn-apply"
                            onClick={() => handleApply(job.id)}
                            disabled={applyingJobId === job.id}
                          >
                            {applyingJobId === job.id ? 'Applying…' : 'Apply'}
                          </button>
                        )}
                        {!isEditing && (
                          <button
                            className="btn-action btn-edit"
                            onClick={() => startEditing(job)}
                          >
                            Edit
                          </button>
                        )}
                        {!isEditing && (
                          <button
                            className="btn-action btn-regen"
                            onClick={() => handleRegenerate(job.id)}
                            disabled={regeneratingJobId === job.id}
                            title="Re-generate AI cover message"
                          >
                            {regeneratingJobId === job.id ? '…' : 'AI ↺'}
                          </button>
                        )}
                        {!isEditing && (
                          <button
                            className="btn-action btn-delete"
                            onClick={() => handleDelete(job.id)}
                            disabled={deletingJobId === job.id}
                            title="Delete job"
                          >
                            ✕
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination controls */}
      {totalPages > 1 && (
        <div
          style={{
            padding: '12px 20px',
            display: 'flex',
            justifyContent: 'center',
            gap: '8px',
            borderTop: '1px solid #e5e7eb',
          }}
        >
          <button
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            disabled={currentPage === 1}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              border: '1px solid #d1d5db',
              background: currentPage === 1 ? '#f9fafb' : '#fff',
              color: currentPage === 1 ? '#9ca3af' : '#374151',
              cursor: currentPage === 1 ? 'not-allowed' : 'pointer',
              fontSize: '14px',
            }}
          >
            Previous
          </button>

          {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
            let page: number;
            if (totalPages <= 7) {
              page = i + 1;
            } else if (currentPage <= 4) {
              page = i + 1;
            } else if (currentPage >= totalPages - 3) {
              page = totalPages - 6 + i;
            } else {
              page = currentPage - 3 + i;
            }
            return (
              <button
                key={page}
                onClick={() => setCurrentPage(page)}
                style={{
                  padding: '6px 12px',
                  borderRadius: '6px',
                  border: '1px solid',
                  borderColor: currentPage === page ? '#3b82f6' : '#d1d5db',
                  background: currentPage === page ? '#3b82f6' : '#fff',
                  color: currentPage === page ? '#fff' : '#374151',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: currentPage === page ? '600' : '400',
                }}
              >
                {page}
              </button>
            );
          })}

          <button
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              border: '1px solid #d1d5db',
              background: currentPage === totalPages ? '#f9fafb' : '#fff',
              color: currentPage === totalPages ? '#9ca3af' : '#374151',
              cursor: currentPage === totalPages ? 'not-allowed' : 'pointer',
              fontSize: '14px',
            }}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
};

export default JobsTable;
