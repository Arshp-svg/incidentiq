/**
 * IncidentIQ API Client for communication with FastAPI backend.
 */

import {
  Incident,
  IncidentListResponse,
  TelemetryEvent,
  InvestigationJob,
  IncidentReport,
  DemoRunResponse,
  Feedback,
  FeedbackRating,
  HealthStatus,
} from '../types';

const API_BASE = (((import.meta as any).env?.VITE_API_URL as string) || '').replace(/\/+$/, '');

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorText = await response.text();
    let detail = errorText;
    try {
      const parsed = JSON.parse(errorText);
      detail = parsed.detail || errorText;
    } catch {
      // Keep raw text
    }
    throw new Error(`API Error [${response.status}]: ${detail}`);
  }
  return response.json();
}

export const api = {
  /** Fetch system readiness status */
  async checkHealth(): Promise<HealthStatus> {
    const res = await fetch(`${API_BASE}/health/ready`);
    return handleResponse<HealthStatus>(res);
  },

  /** Fetch paginated incidents list */
  async fetchIncidents(limit = 20, offset = 0): Promise<IncidentListResponse> {
    const res = await fetch(`${API_BASE}/api/v1/incidents?limit=${limit}&offset=${offset}`);
    return handleResponse<IncidentListResponse>(res);
  },

  /** Fetch incident details by ID */
  async fetchIncident(id: string): Promise<Incident> {
    const res = await fetch(`${API_BASE}/api/v1/incidents/${id}`);
    return handleResponse<Incident>(res);
  },

  /** Fetch chronological telemetry events for an incident */
  async fetchIncidentEvents(id: string): Promise<TelemetryEvent[]> {
    const res = await fetch(`${API_BASE}/api/v1/incidents/${id}/events`);
    return handleResponse<TelemetryEvent[]>(res);
  },

  /** Fetch final investigation report */
  async fetchIncidentReport(id: string): Promise<IncidentReport> {
    const res = await fetch(`${API_BASE}/api/v1/incidents/${id}/report`);
    return handleResponse<IncidentReport>(res);
  },

  /** Poll investigation job status */
  async pollJob(jobId: string): Promise<InvestigationJob> {
    const res = await fetch(`${API_BASE}/api/v1/jobs/${jobId}`);
    return handleResponse<InvestigationJob>(res);
  },

  /** Trigger one-click demo incident */
  async runDemoIncident(idempotencyKey?: string): Promise<DemoRunResponse> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (idempotencyKey) {
      headers['Idempotency-Key'] = idempotencyKey;
    }
    const res = await fetch(`${API_BASE}/api/v1/demo/run`, {
      method: 'POST',
      headers,
    });
    return handleResponse<DemoRunResponse>(res);
  },

  /** Submit user feedback on report */
  async submitFeedback(
    incidentId: string,
    rating: FeedbackRating,
    comment?: string
  ): Promise<Feedback> {
    const res = await fetch(`${API_BASE}/api/v1/incidents/${incidentId}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rating, comment }),
    });
    return handleResponse<Feedback>(res);
  },
};
