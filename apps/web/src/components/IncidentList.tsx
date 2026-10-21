import React from 'react';
import { ShieldAlert, AlertTriangle, Info, Clock, CheckCircle } from 'lucide-react';
import { Incident, IncidentSeverity } from '../types';

interface IncidentListProps {
  incidents: Incident[];
  selectedIncidentId: string | null;
  onSelectIncident: (id: string) => void;
  isLoading: boolean;
}

export const IncidentList: React.FC<IncidentListProps> = ({
  incidents,
  selectedIncidentId,
  onSelectIncident,
  isLoading,
}) => {
  const getSeverityBadge = (sev: IncidentSeverity) => {
    switch (sev) {
      case 'critical':
        return {
          bg: 'rgba(244, 63, 94, 0.15)',
          color: 'var(--color-critical)',
          border: 'rgba(244, 63, 94, 0.3)',
          icon: <ShieldAlert size={12} />,
        };
      case 'high':
        return {
          bg: 'rgba(249, 115, 22, 0.15)',
          color: 'var(--color-high)',
          border: 'rgba(249, 115, 22, 0.3)',
          icon: <AlertTriangle size={12} />,
        };
      case 'medium':
        return {
          bg: 'rgba(234, 179, 8, 0.15)',
          color: 'var(--color-medium)',
          border: 'rgba(234, 179, 8, 0.3)',
          icon: <Info size={12} />,
        };
      default:
        return {
          bg: 'rgba(16, 185, 129, 0.15)',
          color: 'var(--color-low)',
          border: 'rgba(16, 185, 129, 0.3)',
          icon: <CheckCircle size={12} />,
        };
    }
  };

  const formatTime = (isoString: string) => {
    try {
      const dt = new Date(isoString);
      return dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return isoString;
    }
  };

  return (
    <div
      style={{
        width: '340px',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        height: 'calc(100vh - 75px)',
        background: 'var(--bg-secondary)',
      }}
    >
      <div
        style={{
          padding: '1rem 1.25rem',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <h2 style={{ fontSize: '0.9rem', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>
          Incidents ({incidents.length})
        </h2>
        {isLoading && <span style={{ fontSize: '0.75rem', color: 'var(--accent-primary)' }}>Refreshing...</span>}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '0.75rem' }}>
        {incidents.length === 0 ? (
          <div style={{ padding: '2rem 1rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            <p style={{ fontSize: '0.85rem' }}>No incidents recorded.</p>
            <p style={{ fontSize: '0.75rem', marginTop: '0.25rem' }}>Click "Run Demo Incident" to simulate an outage.</p>
          </div>
        ) : (
          incidents.map((inc) => {
            const isSelected = inc.id === selectedIncidentId;
            const badge = getSeverityBadge(inc.severity);

            return (
              <div
                key={inc.id}
                onClick={() => onSelectIncident(inc.id)}
                style={{
                  padding: '1rem',
                  borderRadius: 'var(--radius-md)',
                  marginBottom: '0.5rem',
                  cursor: 'pointer',
                  backgroundColor: isSelected ? 'var(--bg-surface)' : 'rgba(255, 255, 255, 0.02)',
                  border: `1px solid ${isSelected ? 'var(--border-focus)' : 'var(--border-subtle)'}`,
                  boxShadow: isSelected ? '0 0 15px rgba(99, 102, 241, 0.15)' : 'none',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  if (!isSelected) e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.04)';
                }}
                onMouseLeave={(e) => {
                  if (!isSelected) e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.02)';
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.25rem',
                      fontSize: '0.7rem',
                      fontWeight: '700',
                      textTransform: 'uppercase',
                      padding: '0.15rem 0.45rem',
                      borderRadius: 'var(--radius-full)',
                      background: badge.bg,
                      color: badge.color,
                      border: `1px solid ${badge.border}`,
                    }}
                  >
                    {badge.icon}
                    {inc.severity}
                  </span>

                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                    <Clock size={11} />
                    {formatTime(inc.started_at)}
                  </span>
                </div>

                <h3
                  style={{
                    fontSize: '0.85rem',
                    fontWeight: '600',
                    color: '#ffffff',
                    lineHeight: '1.3',
                    marginBottom: '0.5rem',
                  }}
                >
                  {inc.title}
                </h3>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem' }}>
                  <span
                    style={{
                      padding: '0.1rem 0.4rem',
                      borderRadius: 'var(--radius-sm)',
                      background: 'rgba(255, 255, 255, 0.06)',
                      color: 'var(--text-secondary)',
                      fontFamily: 'var(--font-mono)',
                      fontSize: '0.7rem',
                    }}
                  >
                    {inc.service_name}
                  </span>

                  <span
                    style={{
                      fontSize: '0.7rem',
                      fontWeight: '600',
                      color: inc.status === 'resolved' ? 'var(--color-low)' : inc.status === 'investigating' ? 'var(--accent-primary)' : 'var(--text-muted)',
                      textTransform: 'capitalize',
                    }}
                  >
                    ● {inc.status}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
