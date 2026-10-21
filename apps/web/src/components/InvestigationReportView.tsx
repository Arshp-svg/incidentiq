import React, { useState } from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  Layers,
  ListChecks,
  AlertOctagon,
  ThumbsUp,
  ThumbsDown,
  Sparkles,
} from 'lucide-react';
import { IncidentReport, FeedbackRating } from '../types';
import { api } from '../api/client';

interface InvestigationReportViewProps {
  report: IncidentReport;
  onSelectEvidenceId?: (id: string) => void;
}

export const InvestigationReportView: React.FC<InvestigationReportViewProps> = ({
  report,
  onSelectEvidenceId,
}) => {
  const [feedbackRating, setFeedbackRating] = useState<FeedbackRating | null>(null);
  const [comment, setComment] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submittedFeedback, setSubmittedFeedback] = useState(false);

  const handleFeedbackSubmit = async (rating: FeedbackRating) => {
    setFeedbackRating(rating);
    setIsSubmitting(true);
    try {
      await api.submitFeedback(report.incident_id, rating, comment || undefined);
      setSubmittedFeedback(true);
    } catch (err) {
      console.error('Failed to submit feedback:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const confidencePercent = Math.round((report.root_cause?.confidence ?? 0) * 100);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* 1. Summary Card */}
      <div
        className="glass-panel"
        style={{
          padding: '1.25rem 1.5rem',
          borderLeft: '4px solid var(--accent-primary)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
          <Sparkles size={16} color="var(--accent-primary)" />
          <span style={{ fontSize: '0.75rem', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#a5b4fc' }}>
            Executive Incident Summary
          </span>
        </div>
        <p style={{ fontSize: '1rem', color: '#ffffff', fontWeight: '500', lineHeight: '1.4' }}>
          {report.summary}
        </p>
      </div>

      {/* 2. Leading Root Cause Card */}
      <div
        className="glass-panel"
        style={{
          padding: '1.5rem',
          background: 'linear-gradient(180deg, rgba(30, 41, 59, 0.7) 0%, rgba(17, 24, 39, 0.9) 100%)',
          border: '1px solid rgba(99, 102, 241, 0.3)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
          <div>
            <span style={{ fontSize: '0.75rem', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>
              Primary Root Cause Hypothesis
            </span>
            <h3 style={{ fontSize: '1.15rem', fontWeight: '700', color: '#ffffff', marginTop: '0.25rem' }}>
              {report.root_cause.claim}
            </h3>
          </div>

          {/* Confidence Meter */}
          <div
            style={{
              textAlign: 'right',
              padding: '0.5rem 0.85rem',
              borderRadius: 'var(--radius-md)',
              background: 'rgba(99, 102, 241, 0.1)',
              border: '1px solid rgba(99, 102, 241, 0.25)',
            }}
          >
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: '600' }}>Confidence</div>
            <div style={{ fontSize: '1.25rem', fontWeight: '800', color: '#a5b4fc' }}>
              {confidencePercent}%
            </div>
          </div>
        </div>

        {/* Verifiable Supporting Evidence Chips */}
        <div style={{ marginTop: '0.75rem' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.4rem' }}>
            Traceable Evidence References:
          </span>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
            {report.root_cause.evidence_ids.map((evId) => (
              <button
                key={evId}
                onClick={() => onSelectEvidenceId && onSelectEvidenceId(evId)}
                title="Click to view event in timeline"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.3rem',
                  padding: '0.25rem 0.6rem',
                  borderRadius: 'var(--radius-sm)',
                  background: 'rgba(99, 102, 241, 0.18)',
                  border: '1px solid rgba(99, 102, 241, 0.4)',
                  color: '#e0e7ff',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.75rem',
                  fontWeight: '600',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(99, 102, 241, 0.35)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(99, 102, 241, 0.18)')}
              >
                <CheckCircle2 size={12} color="#818cf8" />
                <span>{evId}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 3. Affected Topology Services */}
      <div className="glass-panel" style={{ padding: '1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
          <Layers size={16} color="var(--color-info)" />
          <h4 style={{ fontSize: '0.85rem', fontWeight: '700', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
            Affected Service Topology
          </h4>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
          {report.affected_services.map((svc) => (
            <span
              key={svc}
              style={{
                padding: '0.3rem 0.65rem',
                borderRadius: 'var(--radius-sm)',
                background: 'rgba(6, 182, 212, 0.1)',
                border: '1px solid rgba(6, 182, 212, 0.3)',
                color: '#67e8f9',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.8rem',
                fontWeight: '500',
              }}
            >
              {svc}
            </span>
          ))}
        </div>
      </div>

      {/* 4. Alternative Hypotheses & Actionable Checks */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        {/* Alternatives */}
        <div className="glass-panel" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <AlertTriangle size={15} color="var(--color-high)" />
            <h4 style={{ fontSize: '0.8rem', fontWeight: '700', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
              Alternative Explanations
            </h4>
          </div>
          <ul style={{ paddingLeft: '1.2rem', fontSize: '0.85rem', color: 'var(--text-primary)', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            {report.alternatives.map((alt, idx) => (
              <li key={idx} style={{ lineHeight: '1.4' }}>{alt}</li>
            ))}
          </ul>
        </div>

        {/* Recommended Checks */}
        <div className="glass-panel" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <ListChecks size={15} color="var(--color-low)" />
            <h4 style={{ fontSize: '0.8rem', fontWeight: '700', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
              Recommended Checks
            </h4>
          </div>
          <ul style={{ paddingLeft: '1.2rem', fontSize: '0.85rem', color: 'var(--text-primary)', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            {report.recommended_checks.map((chk, idx) => (
              <li key={idx} style={{ lineHeight: '1.4' }}>{chk}</li>
            ))}
          </ul>
        </div>
      </div>

      {/* 5. Known Limitations */}
      {report.limitations.length > 0 && (
        <div
          className="glass-panel"
          style={{
            padding: '1rem 1.25rem',
            background: 'rgba(255, 255, 255, 0.02)',
            border: '1px dashed var(--border-subtle)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.4rem' }}>
            <HelpCircle size={14} color="var(--text-muted)" />
            <span style={{ fontSize: '0.75rem', fontWeight: '600', color: 'var(--text-muted)' }}>
              Investigation Limitations & Missing Signals
            </span>
          </div>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            {report.limitations.join('; ')}
          </p>
        </div>
      )}

      {/* 6. Human Feedback Widget */}
      <div
        className="glass-panel"
        style={{
          padding: '1.25rem',
          borderTop: '2px solid var(--border-subtle)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h4 style={{ fontSize: '0.85rem', fontWeight: '700', color: '#ffffff' }}>
              Engineer Investigation Feedback
            </h4>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Was this evidence-grounded diagnosis accurate and helpful?
            </p>
          </div>

          {submittedFeedback ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--color-low)', fontSize: '0.8rem', fontWeight: '600' }}>
              <CheckCircle2 size={16} />
              <span>Feedback recorded! Thank you.</span>
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <input
                type="text"
                placeholder="Optional notes..."
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                style={{
                  padding: '0.35rem 0.65rem',
                  borderRadius: 'var(--radius-sm)',
                  background: 'rgba(0, 0, 0, 0.3)',
                  border: '1px solid var(--border-subtle)',
                  color: '#ffffff',
                  fontSize: '0.75rem',
                  outline: 'none',
                  width: '140px',
                }}
              />
              <button
                onClick={() => handleFeedbackSubmit('helpful')}
                disabled={isSubmitting}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.3rem',
                  padding: '0.4rem 0.8rem',
                  borderRadius: 'var(--radius-md)',
                  background: feedbackRating === 'helpful' ? 'rgba(16, 185, 129, 0.25)' : 'var(--bg-surface)',
                  border: '1px solid var(--border-subtle)',
                  color: 'var(--color-low)',
                  fontSize: '0.75rem',
                  fontWeight: '600',
                  cursor: 'pointer',
                }}
              >
                <ThumbsUp size={13} />
                <span>Helpful</span>
              </button>

              <button
                onClick={() => handleFeedbackSubmit('incomplete')}
                disabled={isSubmitting}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.3rem',
                  padding: '0.4rem 0.8rem',
                  borderRadius: 'var(--radius-md)',
                  background: feedbackRating === 'incomplete' ? 'rgba(234, 179, 8, 0.25)' : 'var(--bg-surface)',
                  border: '1px solid var(--border-subtle)',
                  color: 'var(--color-medium)',
                  fontSize: '0.75rem',
                  fontWeight: '600',
                  cursor: 'pointer',
                }}
              >
                <AlertOctagon size={13} />
                <span>Incomplete</span>
              </button>

              <button
                onClick={() => handleFeedbackSubmit('incorrect')}
                disabled={isSubmitting}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.3rem',
                  padding: '0.4rem 0.8rem',
                  borderRadius: 'var(--radius-md)',
                  background: feedbackRating === 'incorrect' ? 'rgba(244, 63, 94, 0.25)' : 'var(--bg-surface)',
                  border: '1px solid var(--border-subtle)',
                  color: 'var(--color-critical)',
                  fontSize: '0.75rem',
                  fontWeight: '600',
                  cursor: 'pointer',
                }}
              >
                <ThumbsDown size={13} />
                <span>Incorrect</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
