// direction-a.jsx — Clinical Lab aesthetic (IBM Plex Mono + Inter)
// Scientific instrument vibe: mono micro-labels, segmented confidence gauge, tight rules.

function DirA_Shell({ theme, children }) {
  const p = PAGE.A[theme];
  return (
    <div style={{
      width: '100%', height: '100%',
      background: p.bg, color: p.ink,
      fontFamily: 'Inter, -apple-system, system-ui, sans-serif',
      position: 'relative', overflow: 'hidden',
      paddingTop: 88,
    }}>
      <HeaderTitle dir="A" theme={theme} />
      <DoneButton dir="A" theme={theme} />
      <div style={{ position: 'absolute', left: 20, right: 20, top: 90, height: 1, background: p.line }} />
      {children}
    </div>
  );
}

function DirA_MonoLabel({ children, color, style }) {
  return <div style={{
    fontFamily: '"IBM Plex Mono", ui-monospace, monospace',
    fontSize: 10, letterSpacing: 1.6, textTransform: 'uppercase',
    fontWeight: 500, color, ...style,
  }}>{children}</div>;
}

// Segmented dotted confidence gauge — 20 segments
function DirA_Gauge({ value, color, muted }) {
  const segs = 20;
  const filled = value == null ? 0 : Math.round((value / 100) * segs);
  return (
    <div style={{ display: 'flex', gap: 3, alignItems: 'center' }}>
      {Array.from({ length: segs }).map((_, i) => (
        <div key={i} style={{
          width: 8, height: 14, borderRadius: 1,
          background: i < filled ? color : 'transparent',
          border: `1px solid ${i < filled ? color : muted}`,
        }} />
      ))}
    </div>
  );
}

// ─── Processing ───────────────────────────────────────────────────────
function DirA_Processing({ theme, activeStep = 2 }) {
  const p = PAGE.A[theme];
  const steps = STEPS_REEL;
  return (
    <DirA_Shell theme={theme}>
      <div style={{ padding: '32px 24px' }}>
        <DirA_MonoLabel color={p.muted} style={{ marginBottom: 10 }}>STATUS · RUNNING</DirA_MonoLabel>
        <div style={{ fontSize: 28, lineHeight: 1.15, letterSpacing: -0.4, fontWeight: 500, marginBottom: 6 }}>
          Fact-checking.
        </div>
        <div style={{ fontSize: 14, color: p.muted, lineHeight: 1.5, marginBottom: 28 }}>
          Analyzing the shared reel. Avg. runtime 12 s.
        </div>

        {/* Pipeline */}
        <div style={{ border: `1px solid ${p.line}`, borderRadius: 4 }}>
          <div style={{ padding: '10px 14px', borderBottom: `1px solid ${p.line}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <DirA_MonoLabel color={p.muted}>PIPELINE</DirA_MonoLabel>
            <DirA_MonoLabel color={p.muted}>{String(activeStep + 1).padStart(2, '0')} / {String(steps.length).padStart(2, '0')}</DirA_MonoLabel>
          </div>
          {steps.map((s, i) => {
            const done = i < activeStep;
            const active = i === activeStep;
            return (
              <div key={s} style={{
                display: 'flex', alignItems: 'center', gap: 14,
                padding: '14px 14px',
                borderBottom: i < steps.length - 1 ? `1px solid ${p.line}` : 'none',
                opacity: i > activeStep ? 0.4 : 1,
              }}>
                <div style={{ width: 18, height: 18, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {done && (
                    <svg width="14" height="14" viewBox="0 0 14 14">
                      <path d="M2 7L6 11L12 3" stroke="#3d8a5a" strokeWidth="1.8" fill="none" strokeLinecap="square"/>
                    </svg>
                  )}
                  {active && (
                    <div style={{ width: 8, height: 8, borderRadius: 99, background: '#3677d4', boxShadow: '0 0 0 4px rgba(54,119,212,0.18)' }} />
                  )}
                  {!done && !active && (
                    <div style={{ width: 8, height: 8, border: `1px solid ${p.muted}`, borderRadius: 99 }} />
                  )}
                </div>
                <div style={{ flex: 1, fontSize: 14, fontWeight: active ? 500 : 400 }}>{s}</div>
                <DirA_MonoLabel color={p.muted}>{String(i + 1).padStart(2, '0')}</DirA_MonoLabel>
              </div>
            );
          })}
        </div>

        <div style={{ marginTop: 20, fontFamily: '"IBM Plex Mono", ui-monospace, monospace', fontSize: 10, color: p.muted, letterSpacing: 0.5, lineHeight: 1.7 }}>
          t+02.4s · claude-sonnet-4-6 · web_search=on<br/>
          req=ig_reel · shortcode=C8f4xP2qL9n
        </div>
      </div>
    </DirA_Shell>
  );
}

// ─── Verdict ──────────────────────────────────────────────────────────
function DirA_Verdict({ theme, state = 'false', showAllSources = false }) {
  const p = PAGE.A[theme];
  const d = SAMPLE[state];
  const t = TONES.A[theme][d.tone];
  const srcs = showAllSources ? d.sources : d.sources.slice(0, 3);
  const moreCount = Math.max(0, d.sources.length - 3);

  return (
    <DirA_Shell theme={theme}>
      <div style={{ overflowY: 'auto', height: '100%', paddingBottom: 60 }}>
        {/* Banner */}
        <div style={{
          margin: '16px 20px 0', padding: '18px 18px 20px',
          background: t.bg, border: `1px solid ${t.rule}`, borderRadius: 4,
          position: 'relative',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
            <DirA_MonoLabel color={t.fg}>VERDICT</DirA_MonoLabel>
            <DirA_MonoLabel color={t.fg}>{new Date().toISOString().slice(0, 10)}</DirA_MonoLabel>
          </div>
          <div style={{
            fontSize: 38, lineHeight: 1, letterSpacing: -0.8, fontWeight: 600,
            color: t.ink, marginBottom: 16,
            textTransform: d.tone === 'unverified' ? 'none' : 'uppercase',
          }}>{d.verdict}</div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <DirA_MonoLabel color={t.fg}>VERDICT CERTAINTY</DirA_MonoLabel>
            <div style={{
              fontFamily: '"IBM Plex Mono", ui-monospace, monospace',
              fontSize: 14, color: t.ink, fontWeight: 500, letterSpacing: 0.5,
            }}>{d.confidence == null ? '—' : `${d.confidence}%`}</div>
          </div>
          <DirA_Gauge value={d.confidence} color={t.fg} muted={t.fg + '55'} />
        </div>

        {/* Claim */}
        <div style={{ padding: '28px 24px 0' }}>
          <DirA_MonoLabel color={p.muted} style={{ marginBottom: 10 }}>THE CLAIM</DirA_MonoLabel>
          <div style={{
            fontFamily: '"Instrument Serif", Georgia, serif',
            fontSize: 20, lineHeight: 1.35, color: p.ink,
            borderLeft: `2px solid ${t.rule}`, paddingLeft: 14, fontStyle: 'italic',
          }}>{d.claim}</div>
          <div style={{ display: 'flex', gap: 6, marginTop: 14 }}>
            <div style={{
              fontFamily: '"IBM Plex Mono", ui-monospace, monospace',
              fontSize: 10, letterSpacing: 0.8, border: `1px solid ${p.line}`,
              borderRadius: 2, padding: '3px 7px', color: p.muted,
            }}>{d.author}</div>
            <div style={{
              fontFamily: '"IBM Plex Mono", ui-monospace, monospace',
              fontSize: 10, letterSpacing: 0.8, border: `1px solid ${p.line}`,
              borderRadius: 2, padding: '3px 7px', color: p.muted,
            }}>{d.kind}</div>
          </div>
        </div>

        {/* Transcript (reels only) */}
        {d.transcript && (
          <div style={{ padding: '22px 24px 0' }}>
            <DirA_MonoLabel color={p.muted} style={{ marginBottom: 10 }}>AUDIO TRANSCRIPT · EXCERPT</DirA_MonoLabel>
            <div style={{
              fontSize: 13, lineHeight: 1.55, color: p.muted,
              background: p.card, border: `1px dashed ${p.line}`,
              padding: '12px 14px', borderRadius: 3,
            }}>{d.transcript}</div>
          </div>
        )}

        {/* Findings */}
        <div style={{ padding: '22px 24px 0' }}>
          <DirA_MonoLabel color={p.muted} style={{ marginBottom: 10 }}>WHAT WE FOUND</DirA_MonoLabel>
          <div style={{ fontSize: 15, lineHeight: 1.55, color: p.ink }}>{d.tldr}</div>
        </div>

        {/* Sources */}
        {srcs.length > 0 && (
          <div style={{ padding: '24px 24px 0' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 10 }}>
              <DirA_MonoLabel color={p.muted}>SOURCES</DirA_MonoLabel>
              <DirA_MonoLabel color={p.muted}>N = {d.sources.length}</DirA_MonoLabel>
            </div>
            <div style={{ border: `1px solid ${p.line}`, borderRadius: 3 }}>
              {srcs.map((s, i) => (
                <div key={i} style={{
                  padding: '12px 14px',
                  borderBottom: i < srcs.length - 1 ? `1px solid ${p.line}` : 'none',
                  display: 'flex', alignItems: 'center', gap: 12,
                }}>
                  <DirA_MonoLabel color={p.muted} style={{ minWidth: 20 }}>
                    [{String(i + 1).padStart(2, '0')}]
                  </DirA_MonoLabel>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, color: p.ink, lineHeight: 1.35, marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.title}</div>
                    <div style={{ fontFamily: '"IBM Plex Mono", ui-monospace, monospace', fontSize: 10, color: p.muted, letterSpacing: 0.4 }}>{s.domain}</div>
                  </div>
                  <div style={{ color: p.muted, fontSize: 14 }}>↗</div>
                </div>
              ))}
            </div>
            {moreCount > 0 && !showAllSources && (
              <div style={{
                marginTop: 10, padding: '10px 14px',
                border: `1px solid ${p.line}`, borderRadius: 3,
                textAlign: 'center', fontSize: 12, color: p.ink,
                fontFamily: '"IBM Plex Mono", ui-monospace, monospace',
                letterSpacing: 1, textTransform: 'uppercase',
              }}>SHOW {moreCount} MORE ↓</div>
            )}
          </div>
        )}
      </div>
    </DirA_Shell>
  );
}

// ─── Error ────────────────────────────────────────────────────────────
function DirA_Error({ theme }) {
  const p = PAGE.A[theme];
  return (
    <DirA_Shell theme={theme}>
      <div style={{ padding: '60px 28px 0', textAlign: 'left' }}>
        <DirA_MonoLabel color="#c94444" style={{ marginBottom: 14 }}>ERROR · E_IG_UNREACHABLE</DirA_MonoLabel>
        <div style={{ fontSize: 26, lineHeight: 1.2, letterSpacing: -0.3, fontWeight: 500, marginBottom: 12 }}>
          Sorry, unable to process! :(
        </div>
        <div style={{ fontSize: 14, color: p.muted, lineHeight: 1.55, marginBottom: 28 }}>
          The post might be from a private account, deleted, or temporarily unreachable.
        </div>
        <div style={{ border: `1px solid ${p.line}`, borderRadius: 3, padding: '14px' }}>
          <DirA_MonoLabel color={p.muted} style={{ marginBottom: 10 }}>TRACE</DirA_MonoLabel>
          <div style={{ fontFamily: '"IBM Plex Mono", ui-monospace, monospace', fontSize: 11, color: p.muted, lineHeight: 1.7 }}>
            → GET instagram.com/reel/C8f4xP2qL9n<br/>
            ← 200 OK · 0.82 s<br/>
            → parse xdt_api__v1__media<br/>
            <span style={{ color: '#c94444' }}>✕ no media object in response</span>
          </div>
        </div>
      </div>
    </DirA_Shell>
  );
}

Object.assign(window, { DirA_Processing, DirA_Verdict, DirA_Error });
