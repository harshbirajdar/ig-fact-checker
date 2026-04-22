// direction-c.jsx — Calm System (iOS-native)
// Feels like a well-made Apple system sheet: soft cards, SF type, circular confidence ring.
// Surfaces inside Instagram's in-app browser (IGBrowserChrome adds the top/bottom chrome).

function IGBrowserChrome({ theme, url = '4265648.us-central1.run.app', children }) {
  const p = PAGE.C[theme];
  const dark = theme === 'dark';

  // Instagram's in-app browser is always dark-ish, regardless of theme.
  // When the page is light, the chrome still sits at the top as the system status bar area.
  const chromeBg = dark ? '#000000' : '#f2f2f7';
  const chromeInk = dark ? '#ffffff' : '#1c1c1e';
  const chromeBtn = dark ? 'rgba(255,255,255,0.14)' : 'rgba(60,60,67,0.10)';
  const chromeBtnInk = dark ? 'rgba(255,255,255,0.9)' : 'rgba(60,60,67,0.85)';
  const pillBg = dark ? 'rgba(40,40,45,0.92)' : 'rgba(255,255,255,0.92)';
  const pillInk = dark ? '#ffffff' : '#1c1c1e';
  const pillBorder = dark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';

  const TopUrlBar = () => (
    <div style={{
      position: 'absolute', top: 56, left: 0, right: 0,
      height: 52, display: 'flex', alignItems: 'center',
      padding: '0 16px', gap: 10, zIndex: 30, background: chromeBg,
    }}>
      {/* close X */}
      <div style={{
        width: 32, height: 32, borderRadius: 99, background: chromeBtn,
        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
      }}>
        <svg width="12" height="12" viewBox="0 0 12 12">
          <path d="M2 2L10 10M10 2L2 10" stroke={chromeBtnInk} strokeWidth="1.8" strokeLinecap="round"/>
        </svg>
      </div>
      {/* url */}
      <div style={{
        flex: 1, minWidth: 0,
        fontSize: 15, fontWeight: 500, color: chromeInk, letterSpacing: -0.1,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>{url}</div>
      {/* open-in-safari icon */}
      <div style={{
        width: 32, height: 32, borderRadius: 99, background: chromeBtn,
        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
      }}>
        <svg width="16" height="16" viewBox="0 0 16 16">
          <rect x="1.5" y="3" width="13" height="10" rx="1.8" stroke={chromeBtnInk} strokeWidth="1.4" fill="none"/>
          <path d="M1.5 6H14.5" stroke={chromeBtnInk} strokeWidth="1.4"/>
        </svg>
      </div>
    </div>
  );

  const BottomPill = () => (
    <div style={{
      position: 'absolute', bottom: 22, left: 0, right: 0,
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '0 16px', zIndex: 30, pointerEvents: 'none',
    }}>
      {/* back arrow (separate pill) */}
      <div style={{
        width: 46, height: 46, borderRadius: 99,
        background: pillBg,
        border: `0.5px solid ${pillBorder}`,
        boxShadow: '0 8px 20px rgba(0,0,0,0.25)',
        backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <svg width="16" height="16" viewBox="0 0 16 16">
          <path d="M10 3L5 8L10 13" stroke={pillInk} strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>
      {/* tools pill (share, reload, compass) */}
      <div style={{
        height: 46, borderRadius: 99,
        background: pillBg,
        border: `0.5px solid ${pillBorder}`,
        boxShadow: '0 8px 20px rgba(0,0,0,0.25)',
        backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
        display: 'flex', alignItems: 'center', gap: 8, padding: '0 14px',
      }}>
        {/* share */}
        <div style={{ width: 34, height: 34, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <svg width="18" height="18" viewBox="0 0 18 18">
            <path d="M9 2V12M9 2L5.5 5.5M9 2L12.5 5.5" stroke={pillInk} strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M3 10V14C3 15.1 3.9 16 5 16H13C14.1 16 15 15.1 15 14V10" stroke={pillInk} strokeWidth="1.6" fill="none" strokeLinecap="round"/>
          </svg>
        </div>
        {/* reload */}
        <div style={{ width: 34, height: 34, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <svg width="18" height="18" viewBox="0 0 18 18">
            <path d="M15 9A6 6 0 1 1 13.5 5M15 3V5.5H12.5" stroke={pillInk} strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
        {/* compass */}
        <div style={{ width: 34, height: 34, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <svg width="18" height="18" viewBox="0 0 18 18">
            <circle cx="9" cy="9" r="7" stroke={pillInk} strokeWidth="1.6" fill="none"/>
            <path d="M12 6L10 10L6 12L8 8L12 6Z" fill={pillInk}/>
          </svg>
        </div>
      </div>
    </div>
  );

  return (
    <>
      <TopUrlBar />
      {/* content area — padded under top bar, extra bottom padding for pill */}
      <div style={{
        position: 'absolute', top: 108, left: 0, right: 0, bottom: 0,
        overflowY: 'auto',
        paddingBottom: 90,
      }}>
        {children}
      </div>
      <BottomPill />
    </>
  );
}

function DirC_Shell({ theme, children }) {
  const p = PAGE.C[theme];
  return (
    <div style={{
      width: '100%', height: '100%',
      background: p.bg, color: p.ink,
      fontFamily: '-apple-system, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
      position: 'relative', overflow: 'hidden',
      WebkitFontSmoothing: 'antialiased',
    }}>
      <IGBrowserChrome theme={theme}>{children}</IGBrowserChrome>
    </div>
  );
}

// Circular confidence ring
function DirC_Ring({ value, color, track, size = 56, stroke = 5 }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const off = value == null ? c : c - (value / 100) * c;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ display: 'block' }}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={track} strokeWidth={stroke} />
      {value != null && (
        <circle
          cx={size/2} cy={size/2} r={r} fill="none"
          stroke={color} strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={off}
          transform={`rotate(-90 ${size/2} ${size/2})`}
        />
      )}
    </svg>
  );
}

// ─── Processing ───────────────────────────────────────────────────────
function DirC_Processing({ theme, activeStep = 2 }) {
  const p = PAGE.C[theme];
  const steps = STEPS_REEL;
  return (
    <DirC_Shell theme={theme}>
      <div style={{ padding: '4px 20px 0' }}>
        <div style={{ fontSize: 34, fontWeight: 700, letterSpacing: -0.6, color: p.ink, marginBottom: 4 }}>
          Fact-checking…
        </div>
        <div style={{ fontSize: 16, color: p.muted, marginBottom: 24 }}>
          Analyzing the shared reel
        </div>

        <div style={{
          background: p.card, borderRadius: 16,
          border: theme === 'light' ? 'none' : `1px solid ${p.cardLine}`,
          boxShadow: theme === 'light' ? '0 1px 2px rgba(0,0,0,0.04)' : 'none',
          overflow: 'hidden',
        }}>
          {steps.map((s, i) => {
            const done = i < activeStep;
            const active = i === activeStep;
            return (
              <div key={s} style={{
                display: 'flex', alignItems: 'center', gap: 14,
                padding: '14px 16px',
                borderBottom: i < steps.length - 1 ? `0.5px solid ${p.line}` : 'none',
              }}>
                <div style={{ width: 22, height: 22, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {done && (
                    <div style={{
                      width: 22, height: 22, borderRadius: 99,
                      background: '#34C759', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      <svg width="13" height="13" viewBox="0 0 13 13">
                        <path d="M3 7L5.5 9.5L10 4" stroke="white" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </div>
                  )}
                  {active && (
                    <DirC_Spinner color="#007AFF" />
                  )}
                  {!done && !active && (
                    <div style={{ width: 16, height: 16, border: `1.5px solid ${p.muted}`, opacity: 0.4, borderRadius: 99 }} />
                  )}
                </div>
                <div style={{
                  flex: 1, fontSize: 16,
                  color: done ? p.muted : p.ink,
                  fontWeight: active ? 600 : 400,
                }}>{s}</div>
              </div>
            );
          })}
        </div>

        <div style={{ marginTop: 24, textAlign: 'center', fontSize: 13, color: p.muted }}>
          This usually takes 8–15 seconds
        </div>
      </div>
    </DirC_Shell>
  );
}

function DirC_Spinner({ color = '#007AFF' }) {
  return (
    <div style={{
      width: 18, height: 18, borderRadius: 99,
      border: `2px solid ${color}33`,
      borderTopColor: color,
      animation: 'dirC_spin 0.9s linear infinite',
    }} />
  );
}

// ─── Verdict ──────────────────────────────────────────────────────────
function DirC_Verdict({ theme, state = 'false', showAllSources = false }) {
  const p = PAGE.C[theme];
  const d = SAMPLE[state];
  const t = TONES.C[theme][d.tone];
  const srcs = showAllSources ? d.sources : d.sources.slice(0, 3);
  const moreCount = Math.max(0, d.sources.length - 3);

  // Subtle gradient banner using the accent
  const bannerBg = `linear-gradient(135deg, ${t.bg} 0%, ${t.bg} 60%, ${shade(t.bg, -10)} 100%)`;
  const bannerFg = t.fg;

  return (
    <DirC_Shell theme={theme}>
      <div style={{ paddingLeft: 16, paddingRight: 16 }}>
        {/* Banner card */}
        <div style={{
          borderRadius: 22, padding: '18px 20px 20px',
          background: bannerBg, color: bannerFg,
          position: 'relative', overflow: 'hidden',
          boxShadow: `0 6px 20px ${t.accent}25`,
          marginTop: 6,
        }}>
          {/* sheen */}
          <div style={{
            position: 'absolute', top: -40, right: -40, width: 160, height: 160,
            borderRadius: 99, background: 'rgba(255,255,255,0.1)', pointerEvents: 'none',
          }} />
          <div style={{ fontSize: 11, letterSpacing: 1.4, textTransform: 'uppercase', fontWeight: 700, opacity: 0.9, marginBottom: 10 }}>Verdict</div>
          <div style={{
            fontSize: 44, lineHeight: 1, letterSpacing: -1.0, fontWeight: 700,
            marginBottom: 22,
          }}>{d.verdictWord}</div>
          {/* Certainty row — ring + label + number clustered tight together */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            paddingTop: 14,
            borderTop: '1px solid rgba(255,255,255,0.2)',
          }}>
            <DirC_Ring
              value={d.confidence}
              color="#ffffff"
              track="rgba(0,0,0,0.2)"
              size={42} stroke={5}
            />
            <div style={{ fontSize: 12, fontWeight: 500, opacity: 0.85, letterSpacing: 0.1 }}>
              Verdict certainty
            </div>
            <div style={{
              marginLeft: 'auto', fontSize: 15, fontWeight: 700,
              fontVariantNumeric: 'tabular-nums', letterSpacing: -0.2,
            }}>
              {d.confidence == null ? '—' : `${d.confidence}%`}
            </div>
          </div>
        </div>

        {/* Claim */}
        <div style={{
          marginTop: 14,
          background: p.card, borderRadius: 18, padding: '16px 18px',
          border: theme === 'light' ? 'none' : `1px solid ${p.cardLine}`,
        }}>
          <div style={{ fontSize: 12, letterSpacing: 0.4, textTransform: 'uppercase', color: p.muted, fontWeight: 600, marginBottom: 8 }}>The claim</div>
          <div style={{
            fontSize: 17, lineHeight: 1.4, color: p.ink, fontStyle: 'italic',
          }}>{d.claim}</div>
          <div style={{ display: 'flex', gap: 6, marginTop: 12, flexWrap: 'wrap' }}>
            <Chip theme={theme}>{d.author}</Chip>
            <Chip theme={theme}>{d.kind}</Chip>
          </div>
        </div>

        {d.transcript && (
          <div style={{
            marginTop: 12,
            background: p.card, borderRadius: 18, padding: '16px 18px',
            border: theme === 'light' ? 'none' : `1px solid ${p.cardLine}`,
          }}>
            <div style={{ fontSize: 12, letterSpacing: 0.4, textTransform: 'uppercase', color: p.muted, fontWeight: 600, marginBottom: 8 }}>Transcript</div>
            <div style={{ fontSize: 14, lineHeight: 1.5, color: p.muted }}>{d.transcript}</div>
          </div>
        )}

        <div style={{
          marginTop: 12,
          background: p.card, borderRadius: 18, padding: '16px 18px',
          border: theme === 'light' ? 'none' : `1px solid ${p.cardLine}`,
        }}>
          <div style={{ fontSize: 12, letterSpacing: 0.4, textTransform: 'uppercase', color: p.muted, fontWeight: 600, marginBottom: 8 }}>What we found</div>
          <div style={{ fontSize: 15, lineHeight: 1.5, color: p.ink }}>{d.tldr}</div>
        </div>

        {srcs.length > 0 && (
          <div style={{
            marginTop: 12,
            background: p.card, borderRadius: 18, padding: '4px 0 0',
            border: theme === 'light' ? 'none' : `1px solid ${p.cardLine}`,
            overflow: 'hidden',
          }}>
            <div style={{ padding: '14px 18px 8px', fontSize: 12, letterSpacing: 0.4, textTransform: 'uppercase', color: p.muted, fontWeight: 600 }}>
              Sources · {d.sources.length}
            </div>
            {srcs.map((s, i) => (
              <div key={i} style={{
                padding: '12px 18px',
                borderTop: `0.5px solid ${p.line}`,
                display: 'flex', alignItems: 'center', gap: 10,
              }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 15, color: p.ink, lineHeight: 1.3, marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.title}</div>
                  <div style={{ fontSize: 12, color: t.accent, fontWeight: 500 }}>{s.domain}</div>
                </div>
                <svg width="14" height="14" viewBox="0 0 14 14" style={{ color: p.muted, opacity: 0.5 }}>
                  <path d="M5 3h6v6M11 3L4 10" stroke="currentColor" strokeWidth="1.6" fill="none" strokeLinecap="round"/>
                </svg>
              </div>
            ))}
            {moreCount > 0 && !showAllSources && (
              <div style={{
                padding: '13px 18px', borderTop: `0.5px solid ${p.line}`,
                textAlign: 'center', fontSize: 15, color: t.accent, fontWeight: 500,
              }}>Show {moreCount} more</div>
            )}
          </div>
        )}
        <div style={{ height: 16 }} />
      </div>
    </DirC_Shell>
  );
}

function Chip({ theme, children }) {
  const p = PAGE.C[theme];
  return (
    <div style={{
      fontSize: 12, padding: '4px 9px', borderRadius: 99,
      background: theme === 'light' ? 'rgba(120,120,128,0.12)' : 'rgba(120,120,128,0.24)',
      color: p.ink, fontWeight: 500,
    }}>{children}</div>
  );
}

// ─── Error ────────────────────────────────────────────────────────────
function DirC_Error({ theme }) {
  const p = PAGE.C[theme];
  return (
    <DirC_Shell theme={theme}>
      <div style={{ padding: '40px 24px 0' }}>
        <div style={{
          width: 64, height: 64, borderRadius: 99,
          background: theme === 'light' ? '#FFE5E3' : '#3a1f1d',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          marginBottom: 20,
        }}>
          <svg width="32" height="32" viewBox="0 0 32 32">
            <circle cx="16" cy="16" r="13" stroke="#FF3B30" strokeWidth="2.2" fill="none"/>
            <path d="M16 9v8M16 21v1.5" stroke="#FF3B30" strokeWidth="2.4" strokeLinecap="round"/>
          </svg>
        </div>
        <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: -0.4, color: p.ink, marginBottom: 10 }}>
          Sorry, unable to process! :(
        </div>
        <div style={{ fontSize: 16, color: p.muted, lineHeight: 1.45, marginBottom: 28 }}>
          The post might be from a private account, deleted, or temporarily unreachable.
        </div>
        <div style={{
          background: p.card, borderRadius: 14, padding: '14px 16px',
          border: theme === 'light' ? 'none' : `1px solid ${p.cardLine}`,
          fontSize: 14, color: p.muted, lineHeight: 1.5,
        }}>
          Try sharing again in a moment. If the account is private, Fact Check can't see the post.
        </div>
      </div>
    </DirC_Shell>
  );
}

// tiny color shade helper — darken by percent
function shade(hex, pct) {
  // supports short hex too
  let h = hex.replace('#', '');
  if (h.length === 3) h = h.split('').map(x => x + x).join('');
  const num = parseInt(h, 16);
  let r = (num >> 16) & 0xff, g = (num >> 8) & 0xff, b = num & 0xff;
  const amt = pct / 100;
  r = Math.max(0, Math.min(255, Math.round(r + r * amt)));
  g = Math.max(0, Math.min(255, Math.round(g + g * amt)));
  b = Math.max(0, Math.min(255, Math.round(b + b * amt)));
  return '#' + [r, g, b].map(x => x.toString(16).padStart(2, '0')).join('');
}

Object.assign(window, { DirC_Processing, DirC_Verdict, DirC_Error });
