// HUD — tiny pill and expanded widget. Several size / density variations.

function HudPill({ t, state = 'green', time = '3:42', usedPct = 54, style }) {
  // state: green | amber | red
  const tone = { green: t.green, amber: t.amber, red: t.red }[state];
  const toneBg = { green: t.greenBg, amber: t.amberBg, red: t.redBg }[state];
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 8,
      background: t.surface,
      border: `1px solid ${t.borderStrong}`,
      borderRadius: 999, padding: '5px 10px 5px 8px',
      fontFamily: HL_FONT, fontSize: 12, color: t.text,
      boxShadow: t.shadow,
      ...style,
    }}>
      <div style={{
        width: 18, height: 18, borderRadius: 9, background: toneBg,
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        color: tone,
      }}>
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round">
          <circle cx="5" cy="5" r="3.8"/><path d="M5 2.8V5l1.4.9"/>
        </svg>
      </div>
      <span style={{ fontFeatureSettings: '"tnum"', fontVariantNumeric: 'tabular-nums', fontWeight: 500 }}>
        {time}
      </span>
      <span style={{ color: t.textTertiary, fontSize: 11 }}>left</span>
    </div>
  );
}

// Even tinier: pill-as-progress (expresses state via fill, not color dot)
function HudPillProgress({ t, usedPct = 65, time = '2:14', state = 'amber', style }) {
  const tone = { green: t.green, amber: t.amber, red: t.red }[state];
  return (
    <div style={{
      position: 'relative',
      display: 'inline-flex', alignItems: 'center', gap: 8,
      background: t.surface,
      border: `1px solid ${t.borderStrong}`,
      borderRadius: 999, padding: '5px 12px',
      fontFamily: HL_FONT, fontSize: 12, color: t.text,
      boxShadow: t.shadow,
      overflow: 'hidden', minWidth: 100,
      ...style,
    }}>
      <div style={{
        position: 'absolute', top: 0, bottom: 0, left: 0,
        width: `${usedPct}%`,
        background: state === 'red' ? t.redBg : state === 'amber' ? t.amberBg : t.greenBg,
      }} />
      <span style={{ position: 'relative', fontVariantNumeric: 'tabular-nums', fontWeight: 500, color: tone }}>{time}</span>
      <span style={{ position: 'relative', color: t.textTertiary, fontSize: 11 }}>remaining</span>
    </div>
  );
}

function HudPillMinimal({ t, time = '47m', state = 'red' }) {
  const tone = { green: t.green, amber: t.amber, red: t.red }[state];
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      background: t.surface,
      border: `1px solid ${t.borderStrong}`,
      borderRadius: 999, padding: '4px 10px 4px 8px',
      fontFamily: HL_FONT, fontSize: 12,
      boxShadow: t.shadow,
    }}>
      <Dot color={tone} size={7} />
      <span style={{ fontVariantNumeric: 'tabular-nums', fontWeight: 600, color: tone }}>{time}</span>
    </div>
  );
}

// Expanded widget (what shows when you click the pill or drag it open)
function HudWidget({ t, width = 300, state = 'amber', style }) {
  const tone = { green: t.green, amber: t.amber, red: t.red }[state];
  const toneBg = { green: t.greenBg, amber: t.amberBg, red: t.redBg }[state];
  return (
    <div style={{
      width, fontFamily: HL_FONT,
      background: t.mica, color: t.text,
      border: `1px solid ${t.borderStrong}`,
      borderRadius: 8, boxShadow: t.shadowLg,
      overflow: 'hidden',
      ...style,
    }}>
      {/* drag handle */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '6px 10px',
        borderBottom: `1px solid ${t.divider}`,
        background: t.titlebar,
      }}>
        <div style={{ display: 'flex', gap: 3 }}>
          <Dot color={t.textTertiary} size={3}/><Dot color={t.textTertiary} size={3}/>
          <Dot color={t.textTertiary} size={3}/><Dot color={t.textTertiary} size={3}/>
        </div>
        <div style={{ fontSize: 11, color: t.textSecondary, fontWeight: 500, letterSpacing: 0.3 }}>HARD LOCK</div>
        <div style={{ flex: 1 }} />
        <Chip t={t} tone={state === 'green' ? 'green' : state === 'amber' ? 'amber' : 'red'}>
          <Dot color={tone} size={6} />
          {state === 'green' ? 'healthy' : state === 'amber' ? 'warning' : 'critical'}
        </Chip>
        <div style={{ color: t.textTertiary, fontSize: 10 }}>{HLIcons.x}</div>
      </div>

      <div style={{ padding: '14px 16px 16px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 4 }}>
          <span style={{ fontSize: 38, fontWeight: 300, letterSpacing: -1, fontVariantNumeric: 'tabular-nums', color: tone, lineHeight: 1 }}>
            2:14
          </span>
          <span style={{ fontSize: 13, color: t.textSecondary }}>remaining today</span>
        </div>
        <div style={{ fontSize: 11, color: t.textTertiary, marginBottom: 12 }}>
          of 8h daily cap · 5h 46m used
        </div>

        <ProgressBar t={t} pct={72} tone={state === 'green' ? 'green' : state === 'amber' ? 'amber' : 'red'} thickness={6} />

        <div style={{
          marginTop: 14, padding: '10px 12px',
          background: t.surface,
          border: `1px solid ${t.border}`,
          borderRadius: 6,
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <div style={{ color: t.textSecondary }}>{HLIcons.power}</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 11, color: t.textTertiary, textTransform: 'uppercase', letterSpacing: 0.5 }}>Hard cutoff</div>
            <div style={{ fontSize: 13, fontWeight: 500, fontVariantNumeric: 'tabular-nums' }}>23:30 <span style={{ color: t.textTertiary, fontWeight: 400 }}>· in 4h 12m</span></div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
          <Btn t={t} size="sm" style={{ flex: 1 }}>Settings</Btn>
          <Btn t={t} size="sm" style={{ flex: 1 }} icon={HLIcons.pause}>Pause idle</Btn>
        </div>
      </div>
    </div>
  );
}

// Detailed widget with today's usage sparkline + breakdown
function HudWidgetDetailed({ t, width = 340, state = 'red' }) {
  const tone = { green: t.green, amber: t.amber, red: t.red }[state];
  // Fake per-hour usage data (24 hours)
  const usage = [0,0,0,0,0,0,0,0, 0.8, 0.95, 0.9, 0.6, 0.3, 0.85, 0.9, 0.7, 0.8, 0.5, 0.3, 0.9, 0.4, 0, 0, 0];
  return (
    <div style={{
      width, fontFamily: HL_FONT,
      background: t.mica, color: t.text,
      border: `1px solid ${t.borderStrong}`,
      borderRadius: 8, boxShadow: t.shadowLg,
      overflow: 'hidden',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '8px 10px 8px 12px',
        borderBottom: `1px solid ${t.divider}`,
        background: t.titlebar,
      }}>
        <div style={{ width: 12, height: 12, borderRadius: 3, background: tone }} />
        <div style={{ fontSize: 11, color: t.text, fontWeight: 600, letterSpacing: 0.4 }}>HARD LOCK</div>
        <div style={{ flex: 1 }} />
        <div style={{ fontSize: 11, color: t.textTertiary, fontVariantNumeric: 'tabular-nums' }}>Thu · 19:18</div>
      </div>

      <div style={{ padding: '14px 16px' }}>
        <div style={{ display: 'flex', gap: 16, marginBottom: 14 }}>
          <Stat t={t} label="REMAINING" value="0:23" tone={tone} big />
          <Stat t={t} label="USED" value="7:37" />
          <Stat t={t} label="CUTOFF" value="23:30" />
        </div>

        <div style={{ fontSize: 10, color: t.textTertiary, letterSpacing: 0.5, marginBottom: 4, textTransform: 'uppercase' }}>
          Today's activity
        </div>
        {/* sparkline */}
        <div style={{
          display: 'flex', alignItems: 'flex-end', gap: 2, height: 32,
          background: t.surfaceSunken,
          padding: '4px 6px', borderRadius: 4,
          border: `1px solid ${t.border}`,
        }}>
          {usage.map((v, i) => (
            <div key={i} style={{
              flex: 1, height: `${Math.max(v * 100, 3)}%`,
              background: v > 0 ? (i >= 18 ? tone : t.accent) : t.border,
              borderRadius: 1, opacity: v > 0 ? 0.85 : 0.3,
            }} />
          ))}
        </div>
        <div style={{
          display: 'flex', justifyContent: 'space-between',
          fontSize: 9, color: t.textTertiary, marginTop: 3,
          fontVariantNumeric: 'tabular-nums',
        }}>
          <span>00</span><span>06</span><span>12</span><span>18</span><span>24</span>
        </div>

        <div style={{ height: 1, background: t.divider, margin: '14px -16px' }} />

        <div style={{ display: 'flex', gap: 6 }}>
          <Btn t={t} size="sm" style={{ flex: 1 }}>Open settings</Btn>
          <Btn t={t} size="sm">History</Btn>
        </div>
      </div>
    </div>
  );
}

function Stat({ t, label, value, tone, big }) {
  return (
    <div style={{ flex: 1 }}>
      <div style={{ fontSize: 9, color: t.textTertiary, letterSpacing: 0.5, textTransform: 'uppercase', marginBottom: 2 }}>{label}</div>
      <div style={{
        fontSize: big ? 24 : 17, fontWeight: big ? 300 : 500,
        letterSpacing: big ? -0.5 : 0,
        fontVariantNumeric: 'tabular-nums',
        color: tone || t.text, lineHeight: 1,
      }}>{value}</div>
    </div>
  );
}

// A mock desktop background with a Windows 11 taskbar, so HUDs can sit on top
function DesktopCanvas({ t, children, wallpaper = 'mountain', style }) {
  const walls = {
    mountain: 'linear-gradient(180deg, #6ab0d8 0%, #81a9c4 40%, #4a6a82 70%, #2a3f52 100%)',
    dusk: 'linear-gradient(180deg, #1a1a2e 0%, #3d2e52 50%, #8b4565 100%)',
    dark: 'linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%)',
    bloom: 'radial-gradient(circle at 30% 40%, #c7a5e8 0%, #6a5cc7 40%, #2a2d5f 100%)',
  };
  return (
    <div style={{
      position: 'relative', width: '100%', height: '100%',
      background: walls[wallpaper],
      overflow: 'hidden',
      ...style,
    }}>
      {children}
      {/* taskbar */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: 44,
        background: t === HL_THEMES.dark ? 'rgba(32,32,32,0.82)' : 'rgba(243,243,243,0.78)',
        backdropFilter: 'blur(20px)',
        borderTop: `1px solid ${t === HL_THEMES.dark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
      }}>
        {/* fake icons */}
        {[0,1,2,3,4,5,6].map(i => (
          <div key={i} style={{
            width: 32, height: 32, borderRadius: 4,
            background: t === HL_THEMES.dark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)',
          }} />
        ))}
        {/* Hard Lock taskbar icon (highlighted) */}
        <div style={{
          width: 32, height: 32, borderRadius: 4,
          background: t.accentSubtle,
          border: `1px solid ${t.accent}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: t.accent,
        }}>{HLIcons.lock}</div>
        <div style={{ position: 'absolute', right: 14, fontSize: 11, color: t === HL_THEMES.dark ? '#fff' : '#000', fontVariantNumeric: 'tabular-nums', textAlign: 'right', lineHeight: 1.2 }}>
          <div>19:18</div>
          <div>4/21/2026</div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { HudPill, HudPillProgress, HudPillMinimal, HudWidget, HudWidgetDetailed, DesktopCanvas });
