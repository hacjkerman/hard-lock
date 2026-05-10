// Shared primitives: WinWindow chrome, Button, Toggle, Segmented, Slider, Chip

function WinWindow({ t, title, subtitle, width, height, children, noChrome, accent, style }) {
  // Simulated Windows 11 window — titlebar with traffic light controls on right
  return (
    <div style={{
      width, height, display: 'flex', flexDirection: 'column',
      background: t.mica, color: t.text, fontFamily: HL_FONT,
      borderRadius: 8, overflow: 'hidden',
      border: `1px solid ${t.borderStrong}`,
      boxShadow: t.shadowLg,
      ...style,
    }}>
      {!noChrome && (
        <div style={{
          height: 40, display: 'flex', alignItems: 'center',
          background: t.titlebar,
          borderBottom: `1px solid ${t.divider}`,
          paddingLeft: 14, fontSize: 12, fontWeight: 400, color: t.textSecondary,
          userSelect: 'none', flexShrink: 0,
        }}>
          {accent && <div style={{ width: 14, height: 14, borderRadius: 3, background: accent, marginRight: 10 }} />}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            <div style={{ fontSize: 12, color: t.text, fontWeight: 500 }}>{title}</div>
            {subtitle && <div style={{ fontSize: 11, color: t.textTertiary }}>{subtitle}</div>}
          </div>
          <div style={{ flex: 1 }} />
          <WinControls t={t} />
        </div>
      )}
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        {children}
      </div>
    </div>
  );
}

function WinControls({ t }) {
  const Btn = ({ children, hover, last }) => (
    <div style={{
      width: 46, height: 40, display: 'flex', alignItems: 'center', justifyContent: 'center',
      color: t.textSecondary, fontSize: 10,
    }}>
      {children}
    </div>
  );
  return (
    <div style={{ display: 'flex' }}>
      <Btn>
        <svg width="10" height="10" viewBox="0 0 10 10" stroke="currentColor" fill="none" strokeWidth="1"><path d="M0 5h10"/></svg>
      </Btn>
      <Btn>
        <svg width="10" height="10" viewBox="0 0 10 10" stroke="currentColor" fill="none" strokeWidth="1"><rect x="0.5" y="0.5" width="9" height="9"/></svg>
      </Btn>
      <div style={{ width: 46, height: 40, display: 'flex', alignItems: 'center', justifyContent: 'center', color: t.text }}>
        <svg width="10" height="10" viewBox="0 0 10 10" stroke="currentColor" fill="none" strokeWidth="1"><path d="M0 0l10 10M10 0L0 10"/></svg>
      </div>
    </div>
  );
}

function Btn({ t, children, variant = 'default', size = 'md', style, onClick, icon, danger }) {
  const sizes = {
    sm: { padding: '4px 10px', fontSize: 12, height: 26, gap: 6 },
    md: { padding: '6px 14px', fontSize: 13, height: 32, gap: 8 },
    lg: { padding: '9px 18px', fontSize: 14, height: 40, gap: 10 },
  };
  const variants = {
    default: {
      background: t.surface, color: t.text,
      border: `1px solid ${t.borderStrong}`,
      boxShadow: `inset 0 -1px 0 ${t.border}`,
    },
    primary: {
      background: danger ? t.red : t.accent, color: '#fff',
      border: `1px solid ${danger ? 'rgba(0,0,0,0.15)' : 'rgba(0,0,0,0.15)'}`,
      boxShadow: `inset 0 -1px 0 rgba(0,0,0,0.2)`,
    },
    ghost: {
      background: 'transparent', color: t.text,
      border: `1px solid transparent`,
    },
    danger: {
      background: t.surface, color: t.red,
      border: `1px solid ${t.borderStrong}`,
    },
  };
  return (
    <button onClick={onClick} style={{
      ...sizes[size], ...variants[variant],
      borderRadius: 6, fontFamily: HL_FONT, fontWeight: 400,
      cursor: 'pointer', display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      whiteSpace: 'nowrap',
      ...style,
    }}>
      {icon && <span style={{ display: 'inline-flex' }}>{icon}</span>}
      {children}
    </button>
  );
}

function Toggle({ t, on, label, disabled }) {
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 10, opacity: disabled ? 0.55 : 1 }}>
      <div style={{
        width: 40, height: 20, borderRadius: 10,
        background: on ? t.accent : 'transparent',
        border: `1px solid ${on ? t.accent : t.borderStrong}`,
        position: 'relative', transition: 'background .15s',
      }}>
        <div style={{
          position: 'absolute', top: 3, left: on ? 22 : 3,
          width: 12, height: 12, borderRadius: 6,
          background: on ? '#fff' : t.textSecondary,
          transition: 'left .15s',
        }} />
      </div>
      {label && <span style={{ fontSize: 13, color: t.text }}>{label}</span>}
    </div>
  );
}

function Segmented({ t, options, value, style }) {
  return (
    <div style={{
      display: 'inline-flex',
      background: t.surfaceSunken,
      border: `1px solid ${t.border}`,
      borderRadius: 6, padding: 2, gap: 2,
      ...style,
    }}>
      {options.map((o) => (
        <div key={o} style={{
          padding: '4px 12px', fontSize: 12, borderRadius: 4, cursor: 'pointer',
          background: value === o ? t.surface : 'transparent',
          color: value === o ? t.text : t.textSecondary,
          boxShadow: value === o ? t.shadow : 'none',
          fontWeight: value === o ? 500 : 400,
        }}>{o}</div>
      ))}
    </div>
  );
}

function Chip({ t, tone = 'neutral', children, style, icon }) {
  const tones = {
    neutral: { bg: t.surfaceSunken, fg: t.textSecondary, border: t.border },
    green: { bg: t.greenBg, fg: t.green, border: 'transparent' },
    amber: { bg: t.amberBg, fg: t.amber, border: 'transparent' },
    red: { bg: t.redBg, fg: t.red, border: 'transparent' },
    accent: { bg: t.accentSubtle, fg: t.accent, border: 'transparent' },
  }[tone];
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: '2px 8px', fontSize: 11, fontWeight: 500,
      background: tones.bg, color: tones.fg,
      border: `1px solid ${tones.border}`,
      borderRadius: 10, lineHeight: 1.5,
      ...style,
    }}>
      {icon}
      {children}
    </span>
  );
}

function Dot({ color, size = 8, style }) {
  return <span style={{
    display: 'inline-block', width: size, height: size,
    borderRadius: size / 2, background: color, flexShrink: 0, ...style,
  }} />;
}

// Progress bar with traffic-light tinted fill
function ProgressBar({ t, pct, tone = 'accent', thickness = 4, style }) {
  const color = { accent: t.accent, green: t.green, amber: t.amber, red: t.red }[tone];
  return (
    <div style={{
      width: '100%', height: thickness, borderRadius: thickness / 2,
      background: t.surfaceSunken,
      border: `1px solid ${t.border}`,
      overflow: 'hidden', ...style,
    }}>
      <div style={{
        height: '100%', width: `${pct}%`, background: color,
        borderRadius: thickness / 2, transition: 'width .3s',
      }} />
    </div>
  );
}

// Fluent-y Icon set (stroked, minimal)
const HLIcons = {
  clock: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"><circle cx="8" cy="8" r="6.5"/><path d="M8 4.5V8l2.5 1.5"/></svg>,
  lock: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"><rect x="3" y="7" width="10" height="7" rx="1.5"/><path d="M5 7V5a3 3 0 016 0v2"/></svg>,
  shield: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"><path d="M8 1.5l5.5 2v4.5c0 3.5-2.5 6-5.5 6.5-3-.5-5.5-3-5.5-6.5V3.5L8 1.5z"/></svg>,
  settings: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"><circle cx="8" cy="8" r="2"/><path d="M8 1v2M8 13v2M3 8H1M15 8h-2M3.5 3.5l1.4 1.4M11.1 11.1l1.4 1.4M3.5 12.5l1.4-1.4M11.1 4.9l1.4-1.4"/></svg>,
  chart: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"><path d="M2 13h12M3.5 11V7M7 11V4M10.5 11V8M14 11V5"/></svg>,
  power: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"><path d="M5.5 3.5A5.5 5.5 0 1011 3.6M8 2v5"/></svg>,
  warning: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"><path d="M8 2l6.5 11h-13L8 2z"/><path d="M8 6.5v3.5M8 11.5v.5"/></svg>,
  check: <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M3 7.5l2.5 2.5L11 4"/></svg>,
  chevronR: <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"><path d="M4 2l4 4-4 4"/></svg>,
  chevronD: <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"><path d="M2 4l4 4 4-4"/></svg>,
  plus: <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"><path d="M6 2v8M2 6h8"/></svg>,
  minus: <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"><path d="M2 6h8"/></svg>,
  pause: <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor"><rect x="3" y="2" width="2" height="8"/><rect x="7" y="2" width="2" height="8"/></svg>,
  flame: <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"><path d="M7 1s2 2 2 4.5S7 9 7 9s-2-1-2-3.5c0 0-2 1-2 4a4 4 0 008 0c0-4-4-8.5-4-8.5z"/></svg>,
  refresh: <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"><path d="M11 5.5a4.5 4.5 0 11-1.5-3.5M11 1v3h-3"/></svg>,
  info: <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"><circle cx="7" cy="7" r="5.5"/><path d="M7 6.5v4M7 4v.5"/></svg>,
  x: <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"><path d="M1 1l8 8M9 1l-8 8"/></svg>,
};

Object.assign(window, { WinWindow, WinControls, Btn, Toggle, Segmented, Chip, Dot, ProgressBar, HLIcons });
