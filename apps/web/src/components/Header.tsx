import React from 'react';
import { Activity, Play, RefreshCw, CheckCircle2, AlertCircle } from 'lucide-react';
import { HealthStatus } from '../types';

interface HeaderProps {
  health: HealthStatus | null;
  isTriggeringDemo: boolean;
  onTriggerDemo: () => void;
  onRefresh: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  health,
  isTriggeringDemo,
  onTriggerDemo,
  onRefresh,
}) => {
  return (
    <header
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '1.25rem 2rem',
        borderBottom: '1px solid var(--border-subtle)',
        background: 'rgba(10, 14, 23, 0.8)',
        backdropFilter: 'blur(12px)',
        position: 'sticky',
        top: 0,
        zIndex: 50,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <div
          style={{
            width: '40px',
            height: '40px',
            borderRadius: 'var(--radius-md)',
            background: 'linear-gradient(135deg, #6366f1, #06b6d4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 15px rgba(99, 102, 241, 0.4)',
          }}
        >
          <Activity size={22} color="#ffffff" />
        </div>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <h1 style={{ fontSize: '1.4rem', fontWeight: '700', letterSpacing: '-0.025em', color: '#ffffff' }}>
              Incident<span style={{ color: 'var(--accent-primary)' }}>IQ</span>
            </h1>
            <span
              style={{
                fontSize: '0.65rem',
                fontWeight: '700',
                padding: '0.15rem 0.4rem',
                borderRadius: 'var(--radius-full)',
                background: 'rgba(99, 102, 241, 0.2)',
                color: '#a5b4fc',
                letterSpacing: '0.05em',
                textTransform: 'uppercase',
              }}
            >
              Autonomous Agent
            </span>
          </div>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
            Evidence-Grounded AI Incident Investigation Platform
          </p>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        {/* System Health Badge */}
        {health && (
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
              padding: '0.35rem 0.75rem',
              borderRadius: 'var(--radius-full)',
              background: health.status === 'ready' ? 'rgba(16, 185, 129, 0.12)' : 'rgba(234, 179, 8, 0.12)',
              border: `1px solid ${health.status === 'ready' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(234, 179, 8, 0.3)'}`,
              color: health.status === 'ready' ? 'var(--color-low)' : 'var(--color-medium)',
              fontSize: '0.75rem',
              fontWeight: '600',
            }}
          >
            {health.status === 'ready' ? <CheckCircle2 size={13} /> : <AlertCircle size={13} />}
            <span>System {health.status.toUpperCase()}</span>
          </div>
        )}

        {/* Refresh Button */}
        <button
          onClick={onRefresh}
          title="Refresh incident list"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '36px',
            height: '36px',
            borderRadius: 'var(--radius-md)',
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            color: 'var(--text-secondary)',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = '#ffffff')}
          onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-secondary)')}
        >
          <RefreshCw size={15} />
        </button>

        {/* Primary One-Click Demo Action */}
        <button
          onClick={onTriggerDemo}
          disabled={isTriggeringDemo}
          id="btn-run-demo"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.55rem 1.15rem',
            borderRadius: 'var(--radius-md)',
            background: isTriggeringDemo
              ? 'var(--bg-surface)'
              : 'linear-gradient(135deg, var(--accent-primary), #4338ca)',
            border: 'none',
            color: '#ffffff',
            fontWeight: '600',
            fontSize: '0.85rem',
            cursor: isTriggeringDemo ? 'not-allowed' : 'pointer',
            boxShadow: isTriggeringDemo ? 'none' : '0 4px 12px rgba(99, 102, 241, 0.35)',
            transition: 'all 0.2s ease',
          }}
        >
          {isTriggeringDemo ? (
            <>
              <RefreshCw size={15} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
              <span>Simulating Incident...</span>
            </>
          ) : (
            <>
              <Play size={15} fill="#ffffff" />
              <span>Run Demo Incident</span>
            </>
          )}
        </button>
      </div>

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </header>
  );
};
