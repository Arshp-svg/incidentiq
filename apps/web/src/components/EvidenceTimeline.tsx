import React, { useState } from 'react';
import { Terminal, ChevronDown, ChevronRight, AlertCircle, AlertTriangle, Info } from 'lucide-react';
import { TelemetryEvent } from '../types';

interface EvidenceTimelineProps {
  events: TelemetryEvent[];
  highlightedEventIds?: string[];
}

export const EvidenceTimeline: React.FC<EvidenceTimelineProps> = ({
  events,
  highlightedEventIds = [],
}) => {
  const [expandedEvents, setExpandedEvents] = useState<Record<string, boolean>>({});

  const toggleExpand = (id: string) => {
    setExpandedEvents((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const getEventIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case 'error':
        return <AlertCircle size={14} color="var(--color-critical)" />;
      case 'warn':
      case 'warning':
        return <AlertTriangle size={14} color="var(--color-high)" />;
      default:
        return <Info size={14} color="var(--color-info)" />;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ fontSize: '0.85rem', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>
          Telemetry Evidence Timeline ({events.length} Events)
        </h3>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Chronological Order</span>
      </div>

      {events.length === 0 ? (
        <div className="glass-panel" style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>
          No telemetry events attached to this incident.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', position: 'relative' }}>
          {events.map((evt) => {
            const isHighlighted = highlightedEventIds.includes(evt.source_event_id);
            const isExpanded = !!expandedEvents[evt.id];

            return (
              <div
                key={evt.id}
                style={{
                  padding: '0.85rem 1rem',
                  borderRadius: 'var(--radius-md)',
                  background: isHighlighted ? 'rgba(99, 102, 241, 0.08)' : 'rgba(17, 24, 39, 0.6)',
                  border: `1px solid ${isHighlighted ? 'rgba(99, 102, 241, 0.5)' : 'var(--border-subtle)'}`,
                  boxShadow: isHighlighted ? '0 0 15px rgba(99, 102, 241, 0.2)' : 'none',
                  transition: 'all 0.15s ease',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    {getEventIcon(evt.event_type)}
                    <span
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.75rem',
                        fontWeight: '700',
                        color: isHighlighted ? '#a5b4fc' : 'var(--text-primary)',
                        padding: '0.1rem 0.4rem',
                        borderRadius: 'var(--radius-sm)',
                        background: isHighlighted ? 'rgba(99, 102, 241, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                      }}
                    >
                      {evt.source_event_id}
                    </span>
                    <span
                      style={{
                        padding: '0.1rem 0.45rem',
                        borderRadius: 'var(--radius-sm)',
                        background: 'rgba(255, 255, 255, 0.04)',
                        color: 'var(--text-secondary)',
                        fontSize: '0.7rem',
                      }}
                    >
                      {evt.service_name}
                    </span>
                  </div>

                  <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    {new Date(evt.occurred_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </span>
                </div>

                {/* Event Message */}
                <div style={{ fontSize: '0.825rem', color: 'var(--text-primary)', fontWeight: '500', marginBottom: '0.4rem' }}>
                  {evt.payload?.message || `${evt.event_type} event on ${evt.service_name}`}
                </div>

                {/* Expandable Payload Inspector */}
                <button
                  onClick={() => toggleExpand(evt.id)}
                  style={{
                    background: 'none',
                    border: 'none',
                    padding: 0,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.25rem',
                    fontSize: '0.7rem',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    marginTop: '0.25rem',
                  }}
                >
                  {isExpanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                  <Terminal size={11} />
                  <span>{isExpanded ? 'Hide attributes' : 'Inspect payload'}</span>
                </button>

                {isExpanded && (
                  <pre
                    style={{
                      marginTop: '0.5rem',
                      padding: '0.75rem',
                      borderRadius: 'var(--radius-sm)',
                      background: 'rgba(0, 0, 0, 0.4)',
                      border: '1px solid var(--border-subtle)',
                      fontFamily: 'var(--font-mono)',
                      fontSize: '0.7rem',
                      color: '#a5b4fc',
                      overflowX: 'auto',
                    }}
                  >
                    {JSON.stringify(evt.payload, null, 2)}
                  </pre>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
