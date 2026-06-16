import axios from 'axios';

// Base URL: proxied through nginx at /api or falls back to direct backend
const BASE_URL = process.env.REACT_APP_API_URL || '/api';

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// -------------------------
// TypeScript interfaces
// -------------------------

export interface Job {
  id: number;
  title: string;
  company: string | null;
  location: string | null;
  salary: string | null;
  url: string;
  description: string | null;
  generated_message: string | null;
  status: 'pending' | 'applied' | 'failed' | 'skipped';
  applied_at: string | null;
  created_at: string | null;
  error_message: string | null;
  screenshot_path: string | null;
}

export interface Stats {
  total: number;
  applied_today: number;
  pending: number;
  failed: number;
  success_rate: number;
}

export interface JobFilters {
  status?: string;
  keyword?: string;
  date_from?: string;
}

export interface ScrapeResult {
  message: string;
  status: string;
}

export interface ApplyResult {
  success: boolean;
  message: string;
}

export interface SessionStatus {
  logged_in: boolean;
  last_check: string | null;
  last_login: string | null;
  consecutive_failures: number;
  blocked_until: string | null;
}

// -------------------------
// API functions
// -------------------------

/**
 * Fetch jobs with optional filters.
 */
export async function getJobs(filters?: JobFilters): Promise<Job[]> {
  const params: Record<string, string> = {};
  if (filters?.status) params.status = filters.status;
  if (filters?.keyword) params.keyword = filters.keyword;
  if (filters?.date_from) params.date_from = filters.date_from;

  const response = await api.get<Job[]>('/jobs', { params });
  return response.data;
}

/**
 * Trigger the scraper in the background.
 */
export async function scrapeJobs(): Promise<ScrapeResult> {
  const response = await api.post<ScrapeResult>('/scrape');
  return response.data;
}

/**
 * Trigger an application for a specific job.
 */
export async function applyJob(jobId: number): Promise<ApplyResult> {
  const response = await api.post<ApplyResult>(`/apply/${jobId}`);
  return response.data;
}

/**
 * Update the cover message for a specific job.
 */
export async function updateMessage(jobId: number, message: string): Promise<void> {
  await api.put(`/jobs/${jobId}/message`, { message });
}

/**
 * Fetch aggregated statistics.
 */
export async function getStats(): Promise<Stats> {
  const response = await api.get<Stats>('/stats');
  return response.data;
}

/**
 * Health check.
 */
export async function healthCheck(): Promise<{ status: string }> {
  const response = await api.get<{ status: string }>('/health');
  return response.data;
}

/**
 * Get HelloWork session status (logged in, last check, failures, block).
 */
export async function getSessionStatus(): Promise<SessionStatus> {
  const response = await api.get<SessionStatus>('/session/status');
  return response.data;
}

/**
 * Re-generate the AI cover message for a job (runs in background on server).
 */
export async function regenerateMessage(jobId: number): Promise<{ message: string; job_id: number }> {
  const response = await api.post(`/jobs/${jobId}/regenerate`);
  return response.data;
}

/**
 * Seed a test job (for local testing without HelloWork access).
 */
export async function seedJob(data: {
  title: string;
  company: string;
  url: string;
  description: string;
  location?: string;
  salary?: string;
}): Promise<Job> {
  const response = await api.post<Job>('/jobs/seed', data);
  return response.data;
}

/**
 * Delete a job by ID.
 */
export async function deleteJob(jobId: number): Promise<void> {
  await api.delete(`/jobs/${jobId}`);
}

/**
 * Fetch a single job by ID.
 */
export async function getJob(jobId: number): Promise<Job> {
  const response = await api.get<Job>(`/jobs/${jobId}`);
  return response.data;
}

export default api;
