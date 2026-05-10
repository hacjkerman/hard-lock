// Main settings app with pending-changes queue sidebar

function SettingsApp({ t, width = 900, height = 620, variant = 'sidebar' }) {
  // variant: sidebar (default) | split | unified
  if (variant === 'split') return <SettingsAppSplit t={t} width={width} height={height} />;
  if (variant === 'unified') return <SettingsAppUnified t={t} width={width} height={height} />;
  return <SettingsAppSidebar t={t} width={width} height={height} />;
}

const NAV = [
  { id: 'limits', label: 'Limits', icon: HLIcons.clock },
  { id: 'warnings', label: 'Warnings', icon: HLIcons.warning },
  { id: 'cooldown', label: 'Cooldown', icon: HLIcons.shield },
  { id: 'appearance', label: 'Appearance', icon: HLIcons.settings },
  { id: 'history', label: 'History', icon: HLIcons.chart },
  { id: 'advanced', label: 'Advanced', icon: HLIcons.settings },
];

function SettingsAppSidebar({ t, width, height }) {
  return (
    <WinWindow t={t} title="Hard Lock" subtitle="Settings" width={width} height={height}
      accent={t.red}>
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        {/* Left nav */}
        <div style={{
          width: 220, flexShrink: 0, padding: '16px 10px',
          borderRight: `1px solid ${t.divider}`,
          background: t.titlebar,
        }}>
          <div style={{ fontSize: 10, color: t.textTertiary, letterSpacing: 0.6, padding: '4px 10px 8px', textTransform: 'uppercase' }}>Configure</div>
          {NAV.map((n, i) => (
            <div key={n.id} style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '8px 10px', borderRadius: 5, fontSize: 13,
              color: i === 0 ? t.text : t.textSecondary,
              background: i === 0 ? t.surface : 'transparent',
              boxShadow: i === 0 ? `inset 2px 0 0 ${t.accent}` : 'none',
              marginBottom: 2,
            }}>
              <span style={{ color: i === 0 ? t.accent : t.textSecondary }}>{n.icon}</span>
              {n.label}
            </div>
          ))}

          <div style={{ height: 1, background: t.divider, margin: '14px 6px' }} />

          <div style={{ padding: '8px 10px', display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 8, height: 8, borderRadius: 4, background: t.green, boxShadow: `0 0 8px ${t.green}` }} />
            <div>
              <div style={{ fontSize: 12, fontWeight: 500 }}>Lock armed</div>
              <div style={{ fontSize: 10, color: t.textTertiary }}>running as service</div>
            </div>
          </div>
        </div>

        {/* Main content */}
        <div style={{ flex: 1, overflow: 'auto', padding: '24px 28px', minWidth: 0 }}>
          <PageLimits t={t} />
        </div>

        {/* Pending queue sidebar */}
        <PendingQueue t={t} />
      </div>
    </WinWindow>
  );
}

function PageLimits({ t }) {
  return (
    <div>
      <div style={{ marginBottom: 6, fontSize: 11, color: t.textTertiary, letterSpacing: 0.5, textTransform: 'uppercase' }}>
        Configure · Limits
      </div>
      <h1 style={{ fontSize: 26, fontWeight: 600, letterSpacing: -0.3, margin: '0 0 4px' }}>
        Limits
      </h1>
      <p style={{ fontSize: 13, color: t.textSecondary, margin: '0 0 24px', maxWidth: 520 }}>
        Whichever comes first shuts down your computer. Tightening applies immediately. Loosening waits out your cooldown.
      </p>

      <Section t={t} title="Daily cap" subtitle="Total active computer time allowed per day. Idle time doesn't count.">
        <ValueRow t={t} label="Cap">
          <StepperField t={t} value="8h 00m" />
          <Chip t={t} tone="green" style={{ marginLeft: 10 }}>tightening applies immediately</Chip>
        </ValueRow>
        <ValueRow t={t} label="Today" note="resets at 04:00 local">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1 }}>
            <ProgressBar t={t} pct={72} tone="amber" thickness={6} style={{ maxWidth: 240 }} />
            <span style={{ fontSize: 12, color: t.textSecondary, fontVariantNumeric: 'tabular-nums' }}>5h 46m / 8h</span>
          </div>
        </ValueRow>
        <ValueRow t={t} label="Idle threshold" note="no input for this long pauses the timer">
          <StepperField t={t} value="90s" width={88} />
        </ValueRow>
      </Section>

      <Section t={t} title="Hard cutoff" subtitle="Wall-clock time after which the computer shuts down regardless of usage.">
        <ValueRow t={t} label="Cutoff time">
          <StepperField t={t} value="23:30" width={96} />
          <span style={{ color: t.textTertiary, fontSize: 12, marginLeft: 10 }}>in 4h 12m</span>
        </ValueRow>
        <ValueRow t={t} label="Grace period" note="fullscreen red countdown before shutdown">
          <StepperField t={t} value="60s" width={88} />
        </ValueRow>
      </Section>

      <Section t={t} title="Dry-run mode" subtitle="Everything works the same, except the final shutdown is skipped. For testing.">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 500 }}>Dry-run is <span style={{ color: t.amber }}>ON</span></div>
            <div style={{ fontSize: 12, color: t.textSecondary, marginTop: 2 }}>
              Turning this off is <span style={{ color: t.green }}>tightening</span> — takes effect now.
            </div>
          </div>
          <Toggle t={t} on={true} />
        </div>
      </Section>

      <div style={{
        marginTop: 20, padding: 14, display: 'flex', alignItems: 'flex-start', gap: 10,
        background: t.accentSubtle,
        border: `1px solid ${t.accent}22`,
        borderRadius: 6,
      }}>
        <div style={{ color: t.accent, marginTop: 1 }}>{HLIcons.info}</div>
        <div style={{ fontSize: 12, color: t.textSecondary, lineHeight: 1.55 }}>
          <strong style={{ color: t.text }}>Anti-cheat:</strong> the design here is that <em>tired-you-at-11pm</em> can't weaken the lock to get more screen time.
          Only <em>rested-you-tomorrow</em> can, via the 24h cooldown queue on the right.
        </div>
      </div>
    </div>
  );
}

function Section({ t, title, subtitle, children }) {
  return (
    <div style={{
      marginBottom: 18, padding: '16px 18px',
      background: t.surface,
      border: `1px solid ${t.border}`,
      borderRadius: 8,
    }}>
      <div style={{ marginBottom: 14 }}>
        <div style={{ fontSize: 14, fontWeight: 600 }}>{title}</div>
        {subtitle && <div style={{ fontSize: 12, color: t.textSecondary, marginTop: 2 }}>{subtitle}</div>}
      </div>
      {children}
    </div>
  );
}

function ValueRow({ t, label, note, children }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 16,
      padding: '10px 0',
      borderTop: `1px solid ${t.divider}`,
    }}>
      <div style={{ width: 140, flexShrink: 0 }}>
        <div style={{ fontSize: 13, color: t.text }}>{label}</div>
        {note && <div style={{ fontSize: 11, color: t.textTertiary, marginTop: 1 }}>{note}</div>}
      </div>
      <div style={{ flex: 1, display: 'flex', alignItems: 'center' }}>{children}</div>
    </div>
  );
}

function StepperField({ t, value, width = 110 }) {
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center',
      background: t.surface, border: `1px solid ${t.borderStrong}`,
      borderRadius: 6, height: 32, width,
      boxShadow: `inset 0 -1px 0 ${t.border}`,
    }}>
      <div style={{ flex: 1, padding: '0 10px', fontSize: 13, fontVariantNumeric: 'tabular-nums', fontWeight: 500 }}>{value}</div>
      <div style={{ display: 'flex', flexDirection: 'column', borderLeft: `1px solid ${t.border}` }}>
        <div style={{ padding: '0 6px', height: 15, display: 'flex', alignItems: 'center', color: t.textSecondary, borderBottom: `1px solid ${t.border}` }}>
          <svg width="8" height="5" viewBox="0 0 8 5" stroke="currentColor" fill="none" strokeWidth="1"><path d="M1 4l3-3 3 3"/></svg>
        </div>
        <div style={{ padding: '0 6px', height: 15, display: 'flex', alignItems: 'center', color: t.textSecondary }}>
          <svg width="8" height="5" viewBox="0 0 8 5" stroke="currentColor" fill="none" strokeWidth="1"><path d="M1 1l3 3 3-3"/></svg>
        </div>
      </div>
    </div>
  );
}

function PendingQueue({ t }) {
  return (
    <div style={{
      width: 280, flexShrink: 0,
      borderLeft: `1px solid ${t.divider}`,
      background: t.surfaceSunken,
      display: 'flex', flexDirection: 'column', minHeight: 0,
    }}>
      <div style={{
        padding: '14px 16px 12px',
        borderBottom: `1px solid ${t.divider}`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ color: t.amber }}>{HLIcons.shield}</div>
          <div style={{ fontSize: 13, fontWeight: 600 }}>Pending changes</div>
          <Chip t={t} tone="amber" style={{ marginLeft: 'auto' }}>2</Chip>
        </div>
        <div style={{ fontSize: 11, color: t.textTertiary, marginTop: 4 }}>
          Weakening changes are deferred 24h. You cannot benefit from them tonight.
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '10px 12px' }}>
        <PendingItem t={t}
          field="Daily cap"
          from="8h 00m"
          to="10h 00m"
          submitted="Today · 14:02"
          activates="Tomorrow · 14:02"
          progress={0.19}
        />
        <PendingItem t={t}
          field="Cutoff time"
          from="23:30"
          to="00:30"
          submitted="Today · 14:04"
          activates="Tomorrow · 14:04"
          progress={0.19}
        />

        <div style={{
          marginTop: 14,
          padding: '12px',
          border: `1px dashed ${t.borderStrong}`,
          borderRadius: 6,
          fontSize: 11, color: t.textTertiary, lineHeight: 1.5,
        }}>
          <div style={{ color: t.textSecondary, marginBottom: 4, fontWeight: 500 }}>No other queued items</div>
          Tightening changes (lower cap / earlier cutoff / disable dry-run) apply instantly and don't appear here.
        </div>
      </div>

      <div style={{
        padding: '10px 14px',
        borderTop: `1px solid ${t.divider}`,
        fontSize: 11, color: t.textTertiary,
        display: 'flex', alignItems: 'center', gap: 6,
      }}>
        <div style={{ color: t.green }}>{HLIcons.check}</div>
        Changes can be canceled before activating.
      </div>
    </div>
  );
}

function PendingItem({ t, field, from, to, submitted, activates, progress }) {
  return (
    <div style={{
      background: t.surface,
      border: `1px solid ${t.border}`,
      borderRadius: 6, padding: '10px 12px', marginBottom: 8,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <div style={{ fontSize: 12, fontWeight: 600 }}>{field}</div>
        <Chip t={t} tone="amber" style={{ marginLeft: 'auto', padding: '1px 6px', fontSize: 10 }}>weakening</Chip>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, fontVariantNumeric: 'tabular-nums' }}>
        <span style={{ color: t.textTertiary, textDecoration: 'line-through' }}>{from}</span>
        <span style={{ color: t.textTertiary }}>→</span>
        <span style={{ color: t.text, fontWeight: 500 }}>{to}</span>
      </div>
      <div style={{ marginTop: 8 }}>
        <ProgressBar t={t} pct={progress * 100} tone="amber" thickness={3} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: t.textTertiary, marginTop: 4, fontVariantNumeric: 'tabular-nums' }}>
        <span>queued {submitted}</span>
        <span>activates {activates}</span>
      </div>
      <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
        <Btn t={t} size="sm" variant="danger" style={{ flex: 1, fontSize: 11, height: 24 }}>Cancel</Btn>
      </div>
    </div>
  );
}

// SPLIT variant — pending at top (horizontal banner) instead of right rail
function SettingsAppSplit({ t, width, height }) {
  return (
    <WinWindow t={t} title="Hard Lock" subtitle="Settings · split view" width={width} height={height} accent={t.red}>
      {/* Pending banner across top */}
      <div style={{
        padding: '10px 20px',
        background: t.amberBg,
        borderBottom: `1px solid ${t.amber}33`,
        display: 'flex', alignItems: 'center', gap: 14,
      }}>
        <div style={{ color: t.amber }}>{HLIcons.shield}</div>
        <div style={{ fontSize: 12 }}>
          <span style={{ fontWeight: 600 }}>2 pending weakening changes</span>
          <span style={{ color: t.textSecondary }}> · activating in 19h 32m</span>
        </div>
        <div style={{ flex: 1 }} />
        <Btn t={t} size="sm">Review queue</Btn>
      </div>
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        <div style={{
          width: 220, flexShrink: 0, padding: '16px 10px',
          borderRight: `1px solid ${t.divider}`, background: t.titlebar,
        }}>
          {NAV.map((n, i) => (
            <div key={n.id} style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '8px 10px', borderRadius: 5, fontSize: 13,
              color: i === 0 ? t.text : t.textSecondary,
              background: i === 0 ? t.surface : 'transparent',
            }}>
              <span style={{ color: i === 0 ? t.accent : t.textSecondary }}>{n.icon}</span>
              {n.label}
            </div>
          ))}
        </div>
        <div style={{ flex: 1, overflow: 'auto', padding: '24px 28px' }}>
          <PageLimits t={t} />
        </div>
      </div>
    </WinWindow>
  );
}

// UNIFIED — single scrolling page, pending inline with affected fields
function SettingsAppUnified({ t, width, height }) {
  return (
    <WinWindow t={t} title="Hard Lock" subtitle="Settings · unified" width={width} height={height} accent={t.red}>
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        <div style={{
          width: 60, flexShrink: 0, padding: '16px 0',
          borderRight: `1px solid ${t.divider}`, background: t.titlebar,
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
        }}>
          {NAV.map((n, i) => (
            <div key={n.id} title={n.label} style={{
              width: 40, height: 40, borderRadius: 6,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: i === 0 ? t.accentSubtle : 'transparent',
              color: i === 0 ? t.accent : t.textSecondary,
            }}>{n.icon}</div>
          ))}
        </div>
        <div style={{ flex: 1, overflow: 'auto', padding: '24px 28px' }}>
          <div style={{ fontSize: 11, color: t.textTertiary, letterSpacing: 0.5, textTransform: 'uppercase' }}>Configure</div>
          <h1 style={{ fontSize: 26, fontWeight: 600, letterSpacing: -0.3, margin: '0 0 20px' }}>Limits</h1>

          <Section t={t} title="Daily cap">
            <ValueRow t={t} label="Cap">
              <StepperField t={t} value="8h 00m" />
              <div style={{ marginLeft: 14, padding: '6px 10px', background: t.amberBg, border: `1px solid ${t.amber}33`, borderRadius: 4, fontSize: 11, color: t.amber }}>
                → 10h 00m queued · activates in 19h 32m · <span style={{ textDecoration: 'underline', cursor: 'pointer' }}>cancel</span>
              </div>
            </ValueRow>
          </Section>
        </div>
      </div>
    </WinWindow>
  );
}

Object.assign(window, { SettingsApp, PendingQueue, PendingItem });
