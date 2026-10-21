import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Header } from '../components/Header';
import { IncidentList } from '../components/IncidentList';
import { EvidenceTimeline } from '../components/EvidenceTimeline';
import { InvestigationReportView } from '../components/InvestigationReportView';
import { api } from '../api/client';
import {
  Incident,
  TelemetryEvent,
  IncidentReport,
  HealthStatus,
  JobStatus,
} from '../types';
import { FileText, GitCommit, RefreshCw, AlertCircle } from 'lucide-react';

export const DashboardPage: React.FC = () => {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(null);
  const [events, setEvents] = useState<TelemetryEvent[]>([]);
  const [report, setReport] = useState<IncidentReport | null>(null);

  // Active investigation & polling state
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [highlightedEvidenceIds, setHighlightedEvidenceIds] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<'report' | 'timeline'>('report');

  // Loading flags
  const [isLoadingIncidents, setIsLoadingIncidents] = useState(false);
  const [isTriggeringDemo, setIsTriggeringDemo] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);

  const pollingRef = useRef<number | null>(null);

  // 1. Initial Load: Check health & fetch incident list
  const loadIncidents = useCallback(async () => {
    setIsLoadingIncidents(true);
    try {
      const data = await api.fetchIncidents(25, 0);
      setIncidents(data.items);
      // Select the first incident if none selected
      if (!selectedIncidentId && data.items.length > 0) {
        setSelectedIncidentId(data.items[0].id);
      }
    } catch (err) {
      console.error('Failed to load incidents:', err);
    } finally {
      setIsLoadingIncidents(false);
    }
  }, [selectedIncidentId]);

  useEffect(() => {
    api.checkHealth().then(setHealth).catch(console.error);
    loadIncidents();
  }, []);

  // 2. When selectedIncidentId changes, load its events and report
  useEffect(() => {
    if (!selectedIncidentId) return;

    setReport(null);
    setEvents([]);
    setReportError(null);

    // Fetch timeline events
    api
      .fetchIncidentEvents(selectedIncidentId)
      .then(setEvents)
      .catch((err) => console.error('Failed to load events:', err));

    // Fetch final investigation report
    api
      .fetchIncidentReport(selectedIncidentId)
      .then((rep) => {
        setReport(rep);
        setHighlightedEvidenceIds(rep.root_cause?.evidence_ids || []);
      })
      .catch(() => {
        setReportError('Investigation in progress or report not ready yet.');
      });
  }, [selectedIncidentId]);

  // 3. Real-time Job Polling
  useEffect(() => {
    if (!activeJobId) return;

    const checkJob = async () => {
      try {
        const job = await api.pollJob(activeJobId);
        setJobStatus(job.status);

        if (job.status === 'completed') {
          if (pollingRef.current) clearInterval(pollingRef.current);
          setActiveJobId(null);
          // Reload incidents and report
          await loadIncidents();
          if (selectedIncidentId) {
            const updatedReport = await api.fetchIncidentReport(selectedIncidentId);
            setReport(updatedReport);
            setHighlightedEvidenceIds(updatedReport.root_cause?.evidence_ids || []);
            setReportError(null);
          }
        } else if (job.status === 'failed') {
          if (pollingRef.current) clearInterval(pollingRef.current);
          setActiveJobId(null);
          setReportError('Investigation failed. Please check worker logs.');
        }
      } catch (err) {
        console.error('Polling error:', err);
      }
    };

    pollingRef.current = setInterval(checkJob, 1200);
    checkJob();

    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [activeJobId, selectedIncidentId, loadIncidents]);

  // 4. One-Click Demo Trigger
  const handleTriggerDemo = async () => {
    setIsTriggeringDemo(true);
    try {
      const demoRes = await api.runDemoIncident();
      setSelectedIncidentId(demoRes.incident_id);
      setActiveJobId(demoRes.job_id);
      setJobStatus('queued');
      setActiveTab('report');
      // Refresh list to show newly created incident
      await loadIncidents();
    } catch (err) {
      console.error('Failed to trigger demo incident:', err);
    } finally {
      setIsTriggeringDemo(false);
    }
  };

  const selectedIncident = incidents.find((i) => i.id === selectedIncidentId);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', background: 'var(--bg-primary)' }}>
      <Header
        health={health}
        isTriggeringDemo={isTriggeringDemo}
        onTriggerDemo={handleTriggerDemo}
        onRefresh={loadIncidents}
      />

      <div style={{ display: 'flex', flex: 1 }}>
        {/* Left Drawer: Incident List */}
        <IncidentList
          incidents={incidents}
          selectedIncidentId={selectedIncidentId}
          onSelectIncident={setSelectedIncidentId}
          isLoading={isLoadingIncidents}
        />

        {/* Right Pane: Incident Details, Investigation, and Timeline */}
        <div style={{ flex: 1, padding: '1.5rem 2rem', overflowY: 'auto', maxHeight: 'calc(100vh - 75px)' }}>
          {selectedIncident ? (
            <div>
              {/* Incident Header & Tab Switcher */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  paddingBottom: '1.25rem',
                  marginBottom: '1.5rem',
                  borderBottom: '1px solid var(--border-subtle)',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                    <span
                      style={{
                        padding: '0.15rem 0.5rem',
                        borderRadius: 'var(--radius-sm)',
                        background: 'rgba(99, 102, 241, 0.15)',
                        color: '#a5b4fc',
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.75rem',
                        fontWeight: '700',
                      }}
                    >
                      {selectedIncident.service_name}
                    </span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      Started at {new Date(selectedIncident.started_at).toLocaleString()}
                    </span>
                  </div>
                  <h2 style={{ fontSize: '1.35rem', fontWeight: '700', color: '#ffffff' }}>
                    {selectedIncident.title}
                  </h2>
                </div>

                {/* Tab switcher */}
                <div
                  style={{
                    display: 'flex',
                    background: 'var(--bg-surface)',
                    padding: '0.25rem',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  <button
                    onClick={() => setActiveTab('report')}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.35rem',
                      padding: '0.4rem 0.85rem',
                      borderRadius: 'var(--radius-sm)',
                      background: activeTab === 'report' ? 'var(--accent-primary)' : 'transparent',
                      color: activeTab === 'report' ? '#ffffff' : 'var(--text-secondary)',
                      border: 'none',
                      fontSize: '0.8rem',
                      fontWeight: '600',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <FileText size={14} />
                    <span>Investigation Report</span>
                  </button>

                  <button
                    onClick={() => setActiveTab('timeline')}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.35rem',
                      padding: '0.4rem 0.85rem',
                      borderRadius: 'var(--radius-sm)',
                      background: activeTab === 'timeline' ? 'var(--accent-primary)' : 'transparent',
                      color: activeTab === 'timeline' ? '#ffffff' : 'var(--text-secondary)',
                      border: 'none',
                      fontSize: '0.8rem',
                      fontWeight: '600',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <GitCommit size={14} />
                    <span>Evidence Timeline ({events.length})</span>
                  </button>
                </div>
              </div>

              {/* Active Polling Status Banner */}
              {activeJobId && (
                <div
                  className="glass-panel"
                  style={{
                    padding: '1rem 1.25rem',
                    marginBottom: '1.5rem',
                    borderLeft: '4px solid var(--accent-primary)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.75rem',
                  }}
                >
                  <RefreshCw size={18} className="spin" style={{ animation: 'spin 1s linear infinite', color: 'var(--accent-primary)' }} />
                  <div>
                    <div style={{ fontSize: '0.85rem', fontWeight: '700', color: '#ffffff' }}>
                      LangGraph Investigation Workflow Active: {jobStatus?.toUpperCase()}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                      Querying pgvector runbooks, inspecting Neo4j service graph, and synthesizing grounded root cause claims...
                    </div>
                  </div>
                </div>
              )}

              {/* Main Content Area */}
              {activeTab === 'report' ? (
                report ? (
                  <InvestigationReportView
                    report={report}
                    onSelectEvidenceId={(id) => {
                      setHighlightedEvidenceIds([id]);
                      setActiveTab('timeline');
                    }}
                  />
                ) : (
                  <div
                    className="glass-panel"
                    style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-secondary)' }}
                  >
                    {activeJobId ? (
                      <div>
                        <RefreshCw size={28} className="spin" style={{ animation: 'spin 1s linear infinite', margin: '0 auto 1rem', color: 'var(--accent-primary)' }} />
                        <h3 style={{ color: '#ffffff', marginBottom: '0.25rem' }}>Autonomous Investigation in Progress</h3>
                        <p style={{ fontSize: '0.85rem' }}>Extracting evidence and correlating service signals...</p>
                      </div>
                    ) : (
                      <div>
                        <AlertCircle size={28} style={{ margin: '0 auto 1rem', color: 'var(--color-medium)' }} />
                        <h3 style={{ color: '#ffffff', marginBottom: '0.25rem' }}>No Final Report Yet</h3>
                        <p style={{ fontSize: '0.85rem' }}>{reportError || 'Trigger a demo or run investigation to generate findings.'}</p>
                      </div>
                    )}
                  </div>
                )
              ) : (
                <EvidenceTimeline
                  events={events}
                  highlightedEventIds={highlightedEvidenceIds}
                />
              )}
            </div>
          ) : (
            <div style={{ padding: '4rem', textAlign: 'center', color: 'var(--text-muted)' }}>
              Select an incident from the left sidebar or click "Run Demo Incident".
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
