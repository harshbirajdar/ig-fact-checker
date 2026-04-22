// direction-b.jsx — Editorial Authority (Instrument Serif + Inter)
// Newspaper correction-desk vibe: big serif headlines, rules, drop cap.

function DirB_Shell({ theme, children }) {
  const p = PAGE.B[theme];
  return (
    <div style={{
      width: '100%', height: '100%',
      background: p.bg, color: p.ink,
      fontFamily: 'Inter, -apple-system, system-ui, sans-serif',
      position: 'relative', overflow: 'hidden',
      paddingTop: 88,
    }}>
      <HeaderTitle dir="B" theme={theme} />
      <DoneButton dir="B" theme={theme} />
      <div style={{ position: 'absolute', left: 20, right: 20, top: 94, height: 1, background: p.ink, opacity: 0.85 }} />
      <div style={{ position: 'absolute', left: 20, right: 20, top: 98, height: 3, display: 'flex', gap: 3 }}>
        <div style={{ flex: 1, borderTop: `1px solid ${p.ink}`, opacity: 0.45 }} />
      </div>
      {children}
    </div>
  );
}

function DirB_Caps({ children, color, style }) {
  return <div style={{
    fontFamily: 'Inter, sans-serif',
    fontSize: 10, letterSpacing: 2.6, textTransform: 'uppercase',
    fontWeight: 600, color, ...style,
  }}>{children}</div>;
}

// Progress: horizontal rule that fills
function DirB_Progress({ value, color, muted }) {
  const v = value == null ? 0 : value;
  return (
    <div style={{ position: 'relative', height: 2, background: muted, borderRadius: 2, overflow: 'hidden' }}>
      <div style={{ position: 'absolute', inset: 0, width: `${v}%`, background: color }} />
    </div>
  );
}

// ─── Processing ───────────────────────────────────────────────────────
function DirB_Processing({ theme, activeStep = 2 }) {
  const p = PAGE.B[theme];
  const steps = STEPS_REEL;
  return (
    <DirB_Shell theme={theme}>
      <div style={{ padding: '30px 24px' }}>
        <DirB_Caps color={p.muted} style={{ marginBottom: 18 }}>In review</DirB_Caps>
        <div style={{
          fontFamily: '"Instrument Serif", Georgia, serif',
          fontSize: 46, lineHeight: 1.0, letterSpacing: -0.5, fontWeight: 400,
          color: p.ink, marginBottom: 12,
        }}>Fact-checking<span style={{ fontStyle: 'italic' }}>.</span></div>
        <div style={{ fontSize: 14, color: p.muted, lineHeight: 1.55, fontStyle: 'italic', marginBottom: 28 }}>
          A reel shared to the desk. Verdict expected in ten to fifteen seconds.
        </div>

        {/* steps as a numbered list with rules */}
        <div style={{ borderTop: `1px solid ${p.line}` }}>
          {steps.map((s, i) => {
            const done = i < activeStep;
            const active = i === activeStep;
            const colorFg = done ? p.ink : active ? p.ink : p.muted;
            return (
              <div key={s} style={{
                display: 'flex', alignItems: 'center', gap: 14,
                padding: '14px 0',
                borderBottom: `1px solid ${p.line}`,
                opacity: i > activeStep ? 0.45 : 1,
              }}>
                <div style={{
                  fontFamily: '"Instrument Serif", Georgia, serif',
                  fontSize: 22, fontStyle: 'italic', color: p.muted, minWidth: 26,
                }}>{String(i + 1).padStart(2, '0')}</div>
                <div style={{ flex: 1, fontSize: 15, color: colorFg, fontWeight: active ? 500 : 400 }}>{s}</div>
                {done && (
                  <div style={{ fontFamily: '"Instrument Serif", serif', fontSize: 18, color: p.ink, fontStyle: 'italic' }}>✓</div>
                )}
                {active && (
                  <div style={{ display: 'flex', gap: 4 }}>
                    <div style={{ width: 5, height: 5, borderRadius: 99, background: p.ink, opacity: 0.85 }} />
                    <div style={{ width: 5, height: 5, borderRadius: 99, background: p.ink, opacity: 0.45 }} />
                    <div style={{ width: 5, height: 5, borderRadius: 99, background: p.ink, opacity: 0.2 }} />
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div style={{ marginTop: 24, fontSize: 12, color: p.muted, fontStyle: 'italic', textAlign: 'center' }}>
          Cross-referencing {(activeStep + 1) * 3} web sources.
        </div>
      </div>
    </DirB_Shell>
  );
}

// ─── Verdict ──────────────────────────────────────────────────────────
function DirB_Verdict({ theme, state = 'false', showAllSources = false }) {
  const p = PAGE.B[theme];
  const d = SAMPLE[state];
  const t = TONES.B[theme][d.tone];
  const srcs = showAllSources ? d.sources : d.sources.slice(0, 3);
  const moreCount = Math.max(0, d.sources.length - 3);

  const claimText = d.claim;
  const firstChar = claimText.charAt(0);
  const restClaim = claimText.slice(1);

  return (
    <DirB_Shell theme={theme}>
      <div style={{ overflowY: 'auto', height: '100%', paddingBottom: 60 }}>
        {/* Banner — full-bleed but with serif verdict */}
        <div style={{
          margin: '14px 0 0', padding: '22px 24px 24px',
          background: t.bg,
          position: 'relative',
          borderTop: `2px solid ${t.rule}`,
          borderBottom: `2px solid ${t.rule}`,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
            <DirB_Caps color={t.fg}>Verdict</DirB_Caps>
            <DirB_Caps color={t.fg} style={{ opacity: 0.75 }}>Vol. I · Entry 214</DirB_Caps>
          </div>
          <div style={{
            fontFamily: '"Instrument Serif", Georgia, serif',
            fontSize: 58, lineHeight: 0.95, letterSpacing: -1.2, fontWeight: 400,
            color: t.ink, margin: '8px 0 18px',
            fontStyle: d.tone === 'unverified' ? 'italic' : 'normal',
          }}>{d.verdictWord}<span style={{ color: t.fg }}>.</span></div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <DirB_Caps color={t.fg} style={{ opacity: 0.85 }}>Verdict certainty</DirB_Caps>
            <div style={{
              fontFamily: '"Instrument Serif", Georgia, serif',
              fontSize: 22, color: t.ink, fontWeight: 400,
            }}>{d.confidence == null ? '—' : `${d.confidence}%`}</div>
          </div>
          <DirB_Progress value={d.confidence} color={t.fg} muted={t.fg + '33'} />
        </div>

        {/* Claim with drop cap */}
        <div style={{ padding: '28px 24px 0' }}>
          <DirB_Caps color={p.muted} style={{ marginBottom: 14 }}>The claim</DirB_Caps>
          <div style={{
            fontFamily: '"Instrument Serif", Georgia, serif',
            fontSize: 24, lineHeight: 1.3, color: p.ink,
            fontStyle: 'italic',
            letterSpacing: -0.2,
          }}>
            <span style={{
              fontStyle: 'normal', float: 'left',
              fontSize: 64, lineHeight: 0.85, fontWeight: 400,
              color: t.rule, paddingRight: 8, paddingTop: 6,
            }}>{firstChar}</span>
            {restClaim}
          </div>
          <div style={{ clear: 'both' }} />
          <div style={{ display: 'flex', gap: 16, marginTop: 18, fontSize: 12, color: p.muted }}>
            <div><span style={{ opacity: 0.7 }}>by </span><span style={{ fontStyle: 'italic' }}>{d.author}</span></div>
            <div style={{ borderLeft: `1px solid ${p.line}`, paddingLeft: 16 }}>{d.kind}</div>
          </div>
        </div>

        {d.transcript && (
          <div style={{ padding: '26px 24px 0' }}>
            <DirB_Caps color={p.muted} style={{ marginBottom: 12 }}>From the voiceover</DirB_Caps>
            <div style={{
              fontFamily: '"Instrument Serif", Georgia, serif',
              fontSize: 16, lineHeight: 1.5, color: p.muted,
              borderLeft: `3px double ${t.rule}`, paddingLeft: 14, fontStyle: 'italic',
            }}>{d.transcript}</div>
          </div>
        )}

        {/* Findings */}
        <div style={{ padding: '28px 24px 0' }}>
          <DirB_Caps color={p.muted} style={{ marginBottom: 12 }}>What we found</DirB_Caps>
          <div style={{ fontSize: 16, lineHeight: 1.55, color: p.ink }}>{d.tldr}</div>
        </div>

        {/* Sources */}
        {srcs.length > 0 && (
          <div style={{ padding: '30px 24px 0' }}>
            <div style={{ borderTop: `1px solid ${p.ink}`, paddingTop: 12, marginBottom: 4 }} />
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
              <DirB_Caps color={p.ink}>Sources</DirB_Caps>
              <div style={{ fontSize: 12, color: p.muted, fontStyle: 'italic' }}>{d.sources.length} consulted</div>
            </div>
            {srcs.map((s, i) => (
              <div key={i} style={{
                padding: '14px 0',
                borderBottom: `1px solid ${p.line}`,
                display: 'flex', alignItems: 'flex-start', gap: 12,
              }}>
                <div style={{
                  fontFamily: '"Instrument Serif", Georgia, serif',
                  fontSize: 18, fontStyle: 'italic', color: p.muted, minWidth: 22,
                }}>{i + 1}.</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontFamily: '"Instrument Serif", Georgia, serif',
                    fontSize: 17, color: p.ink, lineHeight: 1.3, marginBottom: 3,
                  }}>{s.title}</div>
                  <div style={{ fontSize: 11, color: p.muted, letterSpacing: 0.8, textTransform: 'uppercase' }}>{s.domain}</div>
                </div>
              </div>
            ))}
            {moreCount > 0 && !showAllSources && (
              <div style={{
                marginTop: 16, textAlign: 'center', fontSize: 13, color: p.ink,
                fontFamily: '"Instrument Serif", Georgia, serif', fontStyle: 'italic',
                textDecoration: 'underline', textUnderlineOffset: 4,
              }}>Show {moreCount} more sources</div>
            )}
          </div>
        )}
      </div>
    </DirB_Shell>
  );
}

// ─── Error ────────────────────────────────────────────────────────────
function DirB_Error({ theme }) {
  const p = PAGE.B[theme];
  return (
    <DirB_Shell theme={theme}>
      <div style={{ padding: '40px 28px 0' }}>
        <DirB_Caps color="#8c1111" style={{ marginBottom: 18 }}>Errata</DirB_Caps>
        <div style={{
          fontFamily: '"Instrument Serif", Georgia, serif',
          fontSize: 38, lineHeight: 1.0, letterSpacing: -0.5, fontWeight: 400,
          color: p.ink, marginBottom: 16,
        }}>Sorry, unable <span style={{ fontStyle: 'italic' }}>to process</span>! :(</div>
        <div style={{ fontSize: 15, color: p.muted, lineHeight: 1.55, fontStyle: 'italic', marginBottom: 28 }}>
          The post might be from a private account, deleted, or temporarily unreachable.
        </div>
        <div style={{ borderTop: `1px solid ${p.line}`, borderBottom: `1px solid ${p.line}`, padding: '16px 0' }}>
          <DirB_Caps color={p.muted} style={{ marginBottom: 8 }}>What you can do</DirB_Caps>
          <ul style={{ margin: 0, paddingLeft: 20, fontSize: 14, color: p.ink, lineHeight: 1.7 }}>
            <li>Confirm the account is public.</li>
            <li>Re-open Instagram and try sharing again.</li>
            <li>If it persists, the post may have been removed.</li>
          </ul>
        </div>
      </div>
    </DirB_Shell>
  );
}

Object.assign(window, { DirB_Processing, DirB_Verdict, DirB_Error });
