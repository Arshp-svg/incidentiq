/**
 * TypeScript definitions mirroring IncidentIQ API contracts.
 */

export type IncidentSeverity = 'low' | 'medium' | 'high' | 'critical';
export type IncidentStatus = 'open' | 'investigating' | 'resolved';
export type JobStatus = 'queued' | 'running' | 'completed' | 'failed';
export type FeedbackRating = 'helpful' | 'incorrect' | 'incomplete';

export interface Incident {
  id: string;
  title: string;
  service_name: string;
  severity: IncidentSeverity;
  status: IncidentStatus;
  started_at: string;
  created_at: string;
}

export interface IncidentListResponse {
  items: Incident[];
  total: number;
  limit: number;
  offset: number;
}

export interface TelemetryEvent {
  id: string;
  incident_id: string;
  source_event_id: string;
  service_name: string;
  event_type: string;
  occurred_at: string;
  payload: Record<string, any>;
  s3_key?: string | null;
}

export interface InvestigationJob {
  job_id: string;
  incident_id: string;
  status: JobStatus;
  attempt_count: number;
  started_at?: string | null;
  finished_at?: string | null;
  error_message?: string | null;
}

export interface RootCauseHypothesis {
  claim: string;
  confidence: number;
  evidence_ids: string[];
}

export interface IncidentReport {
  incident_id: string;
  summary: string;
  root_cause: RootCauseHypothesis;
  affected_services: string[];
  alternatives: string[];
  recommended_checks: string[];
  limitations: string[];
}

export interface DemoRunResponse {
  incident_id: string;
  job_id: string;
  status: JobStatus;
  status_url: string;
}

export interface Feedback {
  id: string;
  incident_id: string;
  rating: FeedbackRating;
  comment?: string | null;
  created_at: string;
}

export interface HealthStatus {
  status: 'live' | 'ready' | 'degraded';
  timestamp: string;
  details: Record<string, string>;
}
