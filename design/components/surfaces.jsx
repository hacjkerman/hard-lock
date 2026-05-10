// Warning popups (30/10/5/1 min) + shutdown takeover + cooldown confirm + tray + history + onboarding

// ─────────── Warning popups ───────────
function WarningPopup({ t, minsLeft = 10, variant = 'toast' }) {
  const tone = minsLeft <= 1 ? t.red : minsLeft <= 5 ? t.red : minsLeft <= 10 ? t.amber : t.amber;
  const toneBg = minsLeft <= 5 ? t.redBg : t.amberBg;
  const title = {
    30: 'Wrap up soon.',
    10: 'Ten minutes left.',
    5: 'Five minutes. Save your work.',
    1: 'One minute. Save now.',
  }[minsLeft] || `${minsLeft} minutes left.`;
  const body = {
    30: "You've got half an hour of active use left on your daily cap. Start wrapping up whatever you're in the middle of.",
    10: 'Start closing what you can. The shutdown cannot be canceled.',
    5: 'Save any open files. This shutdown cannot be canceled.',
    1: 'Save your work NOW. Shutdown begins in 60 seconds.',
  }[minsLeft] || 'Shutdown is imminent.';

  if (variant === 'toast') {
    return (
      <div style={{
        width: 360, fontFamily: HL_FONT,
        background: t.mica, color: t.text,
        border: `1px solid ${t.borderStrong}`,
        borderLeft: `3px solid ${tone}`,
        borderRadius: 8, boxShadow: t.shadowLg,
        padding: '14px 16px 16px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <div style={{ color: tone }}>{HLIcons.warning}</div>
          <div style={{ fontSize: 10, color: t.textTertiary, letterSpacing: 0.6, textTransform: 'uppercase', fontWeight: 600 }}>Hard Lock · Warning</div>
          <div style={{ flex: 1 }} />
          <div style={{ color: t.textTertiary }}>{HLIcons.x}</div>
        </div>
        <div style={{ fontSize: 17, fontWeight: 600, letterSpacing: -0.2, marginBottom: 6 }}>{title}</div>
        <div style={{ fontSize: 12, color: t.textSecondary, lineHeight: 1.5 }}>{body}</div>
        <div style={{
          marginTop: 12, padding: '8px 10px',
          background: toneBg, borderRadius: 5,
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <span style={{ fontSize: 11, color: t.textSecondary }}>Shutdown at</span>
          <span style={{ fontSize: 12, fontWeight: 600, color: tone, fontVariantNumeric: 'tabular-nums' }}>23:30</span>
          <div style={{ flex: 1 }} />
          <span style={{ fontSize: 11, color: t.textSecondary }}>in</span>
          <span style={{ fontSize: 14, fontWeight: 600, color: tone, fontVariantNumeric: 'tabular-nums' }}>
            {minsLeft < 1 ? '0:47' : `${minsLeft}:00`}
          </span>
        </div>
      </div>
    );
  }
  // banner variant (wide, for 1-minute)
  return (
    <div style={{
      width: 560, fontFamily: HL_FONT,
      background: t.red, color: '#fff',
      borderRadius: 10, boxShadow: '0 20px 60px rgba(196,43,28,0.4)',
      padding: '18px 22px',
      display: 'flex', alignItems: 'center', gap: 18,
    }}>
      <div style={{ color: '#fff' }}>{HLIcons.warning}</div>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 18, fontWeight: 600 }}>One minute. Save now.</div>
        <div style={{ fontSize: 12, opacity: 0.85, marginTop: 2 }}>Shutdown in 60 seconds. Cannot be canceled.</div>
      </div>
      <div style={{ fontSize: 40, fontWeight: 300, fontVariantNumeric: 'tabular-nums', letterSpacing: -1 }}>0:58</div>
    </div>
  );
}

// ─────────── Fullscreen shutdown takeover ───────────
function ShutdownTakeover({ t, secs = 43, variant = 'classic', width = 960, height = 540 }) {
  if (variant === 'minimal') return <ShutdownMinimal secs={secs} width={width} height={height} />;
  if (variant === 'terminal') return <ShutdownTerminal secs={secs} width={width} height={height} />;
  return <ShutdownClassic secs={secs} width={width} height={height} />;
}

function ShutdownClassic({ secs, width, height }) {
  return (
    <div style={{
      width, height, position: 'relative', overflow: 'hidden',
      background: '#9a0000',
      backgroundImage: `radial-gradient(circle at 50% 40%, #c42b1c 0%, #9a0000 60%, #5a0000 100%)`,
      color: '#fff', fontFamily: HL_FONT,
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      padding: 40,
    }}>
      {/* subtle scanline texture */}
      <div style={{ position: 'absolute', inset: 0, background: 'repeating-linear-gradient(0deg, rgba(0,0,0,0.04) 0, rgba(0,0,0,0.04) 1px, transparent 1px, transparent 4px)', pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', top: 28, left: 32, display: 'flex', alignItems: 'center', gap: 10, opacity: 0.9 }}>
        <div style={{ width: 18, height: 18, borderRadius: 4, background: '#fff', color: '#9a0000', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {HLIcons.lock}
        </div>
        <div style={{ fontSize: 12, letterSpacing: 2, fontWeight: 600, textTransform: 'uppercase' }}>Hard Lock</div>
      </div>
      <div style={{ position: 'absolute', top: 28, right: 32, fontSize: 11, opacity: 0.7, fontVariantNumeric: 'tabular-nums', letterSpacing: 1, textTransform: 'uppercase' }}>
        DAILY CAP · 8h 00m · REACHED
      </div>

      <div style={{ fontSize: 12, letterSpacing: 3, opacity: 0.8, marginBottom: 24, textTransform: 'uppercase', fontWeight: 500 }}>
        Shutting down
      </div>
      <div style={{
        fontSize: 240, fontWeight: 200, letterSpacing: -10, lineHeight: 0.9,
        fontVariantNumeric: 'tabular-nums',
        textShadow: '0 4px 40px rgba(0,0,0,0.3)',
      }}>
        0:{String(secs).padStart(2, '0')}
      </div>
      <div style={{ fontSize: 20, fontWeight: 500, marginTop: 16, letterSpacing: -0.2 }}>
        Wrap up. Save your work.
      </div>
      <div style={{ fontSize: 13, opacity: 0.75, marginTop: 8, maxWidth: 480, textAlign: 'center', lineHeight: 1.5 }}>
        This cannot be canceled. You set this limit yourself. Take tonight back.
      </div>

      <div style={{ position: 'absolute', bottom: 28, left: 0, right: 0, display: 'flex', justifyContent: 'center', gap: 40, opacity: 0.7, fontSize: 10, letterSpacing: 1, textTransform: 'uppercase' }}>
        <div>Esc · disabled</div>
        <div>Win · disabled</div>
        <div>Ctrl+Alt+Del · disabled</div>
      </div>
      {/* bottom progress to zero */}
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 3, background: 'rgba(255,255,255,0.15)' }}>
        <div style={{ height: '100%', width: `${(60 - secs) / 60 * 100}%`, background: '#fff' }} />
      </div>
    </div>
  );
}

function ShutdownMinimal({ secs, width, height }) {
  return (
    <div style={{
      width, height, background: '#0a0a0a', color: '#fff',
      fontFamily: HL_FONT, position: 'relative',
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
    }}>
      <div style={{ fontSize: 11, letterSpacing: 3, color: '#ff5a4a', textTransform: 'uppercase', marginBottom: 20 }}>Hard Lock · shutdown</div>
      <div style={{ fontSize: 180, fontWeight: 100, letterSpacing: -6, lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>0:{String(secs).padStart(2,'0')}</div>
      <div style={{ fontSize: 14, color: '#888', marginTop: 20 }}>Save your work.</div>
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 2, background: '#1a0505' }}>
        <div style={{ height: '100%', width: `${(60 - secs) / 60 * 100}%`, background: '#c42b1c' }} />
      </div>
    </div>
  );
}

function ShutdownTerminal({ secs, width, height }) {
  return (
    <div style={{
      width, height, background: '#1a0000', color: '#ff5a4a',
      fontFamily: HL_FONT_MONO, padding: 40,
      display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
    }}>
      <div>
        <div style={{ fontSize: 11, opacity: 0.6, marginBottom: 18 }}>HardLock.exe · v1.3.0 · daily_cap=8h · reached</div>
        <div style={{ fontSize: 13, lineHeight: 1.8, opacity: 0.85 }}>
          <div>&gt; initiating shutdown sequence...</div>
          <div>&gt; reason: daily_cap_reached</div>
          <div>&gt; grace_period: 60s</div>
          <div>&gt; cancel: <span style={{ color: '#fff' }}>not available</span></div>
          <div>&gt; dry_run: <span style={{ color: '#fff' }}>false</span></div>
          <div style={{ marginTop: 10, color: '#fff' }}>&gt; save your work.</div>
        </div>
      </div>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 160, fontWeight: 300, letterSpacing: -4, color: '#fff', fontVariantNumeric: 'tabular-nums', lineHeight: 1 }}>
          0:{String(secs).padStart(2,'0')}
        </div>
        <div style={{ fontSize: 11, opacity: 0.6, marginTop: 14, letterSpacing: 2 }}>SECONDS TO POWEROFF</div>
      </div>
      <div style={{ fontSize: 10, opacity: 0.4, textAlign: 'right' }}>
        you configured this. tired-you is not allowed to undo rested-you's decisions.
      </div>
    </div>
  );
}

// ─────────── Cooldown confirm modal ───────────
function CooldownConfirm({ t, width = 480, height = 440 }) {
  return (
    <WinWindow t={t} noChrome width={width} height={height} style={{ borderRadius: 10 }}>
      <div style={{ padding: '24px 26px 22px', flex: 1, display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
          <div style={{ width: 32, height: 32, borderRadius: 6, background: t.amberBg, color: t.amber, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            {HLIcons.shield}
          </div>
          <div>
            <div style={{ fontSize: 10, color: t.amber, letterSpacing: 0.6, textTransform: 'uppercase', fontWeight: 600 }}>Weakening the lock</div>
            <div style={{ fontSize: 18, fontWeight: 600, letterSpacing: -0.2 }}>Queue this change?</div>
          </div>
        </div>
        <p style={{ fontSize: 13, color: t.textSecondary, lineHeight: 1.55, margin: '0 0 16px' }}>
          You're raising the daily cap. This makes the lock less strict, so it doesn't take effect for <strong style={{ color: t.text }}>24 hours</strong>.
        </p>

        <div style={{
          padding: '14px 16px', background: t.surfaceSunken,
          border: `1px solid ${t.border}`, borderRadius: 8, marginBottom: 14,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: t.textTertiary, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>
            <span>Daily cap</span>
            <span>Weakening</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, fontVariantNumeric: 'tabular-nums' }}>
            <div style={{ fontSize: 20, color: t.textTertiary, textDecoration: 'line-through', fontWeight: 500 }}>8h 00m</div>
            <div style={{ fontSize: 16, color: t.textTertiary }}>→</div>
            <div style={{ fontSize: 26, color: t.text, fontWeight: 600, letterSpacing: -0.5 }}>10h 00m</div>
          </div>
        </div>

        <div style={{
          padding: '10px 14px', background: t.accentSubtle,
          border: `1px solid ${t.accent}22`, borderRadius: 6,
          fontSize: 12, color: t.textSecondary, lineHeight: 1.5,
        }}>
          <div style={{ color: t.text, fontWeight: 500, marginBottom: 2 }}>Activates at <span style={{ fontVariantNumeric: 'tabular-nums' }}>Fri Apr 22, 14:04</span></div>
          Between now and then, the cap stays at 8h 00m. You can cancel anytime before activation.
        </div>

        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Btn t={t} size="md">Cancel</Btn>
          <Btn t={t} size="md" variant="primary">Queue change</Btn>
        </div>
      </div>
    </WinWindow>
  );
}

// ─────────── System tray menu ───────────
function TrayMenu({ t, width = 280 }) {
  const Item = ({ label, value, icon, danger, disabled }) => (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '7px 12px', fontSize: 13,
      color: disabled ? t.textDisabled : danger ? t.red : t.text,
      borderRadius: 4,
    }}>
      {icon && <span style={{ color: disabled ? t.textDisabled : danger ? t.red : t.textSecondary, width: 16, display: 'inline-flex' }}>{icon}</span>}
      <span style={{ flex: 1 }}>{label}</span>
      {value && <span style={{ color: t.textTertiary, fontSize: 11, fontVariantNumeric: 'tabular-nums' }}>{value}</span>}
    </div>
  );
  return (
    <div style={{
      width, fontFamily: HL_FONT,
      background: t.mica, color: t.text,
      border: `1px solid ${t.borderStrong}`,
      borderRadius: 8, boxShadow: t.shadowLg,
      padding: 4, overflow: 'hidden',
    }}>
      <div style={{ padding: '10px 14px 12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 6, height: 6, borderRadius: 3, background: t.green }}/>
          <div style={{ fontSize: 12, fontWeight: 600 }}>Hard Lock · armed</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginTop: 6 }}>
          <span style={{ fontSize: 22, fontWeight: 300, letterSpacing: -0.5, fontVariantNumeric: 'tabular-nums', color: t.amber }}>2:14</span>
          <span style={{ fontSize: 11, color: t.textTertiary }}>left today</span>
        </div>
        <ProgressBar t={t} pct={72} tone="amber" thickness={3} style={{ marginTop: 6 }} />
      </div>
      <div style={{ height: 1, background: t.divider, margin: '2px 8px' }} />
      <Item label="Used today" value="5h 46m" icon={HLIcons.clock} />
      <Item label="Daily cap" value="8h 00m" icon={HLIcons.shield} />
      <Item label="Hard cutoff" value="23:30" icon={HLIcons.power} />
      <div style={{ height: 1, background: t.divider, margin: '2px 8px' }} />
      <Item label="Open settings" icon={HLIcons.settings} />
      <Item label="View history" icon={HLIcons.chart} />
      <Item label="Show HUD" icon={HLIcons.clock} />
      <div style={{ height: 1, background: t.divider, margin: '2px 8px' }} />
      <Item label="Pause for idle" value="disabled" icon={HLIcons.pause} disabled />
      <Item label="Quit is disabled" icon={HLIcons.x} disabled />
      <div style={{ padding: '8px 12px 4px', fontSize: 10, color: t.textTertiary, lineHeight: 1.45 }}>
        Dry-run: <span style={{ color: t.amber, fontWeight: 500 }}>ON</span> · Shutdown will be simulated.
      </div>
    </div>
  );
}

// ─────────── History / stats ───────────
function HistoryView({ t, width = 900, height = 620 }) {
  // 42 days of mock data
  const days = Array.from({ length: 42 }, (_, i) => {
    const seed = (i * 37 + 11) % 100;
    const active = 4 + (seed % 60) / 10; // 4 to 10
    const capped = active > 8;
    return { i, active, capped, cutoff: seed % 7 === 0 };
  });

  return (
    <WinWindow t={t} title="Hard Lock" subtitle="History" width={width} height={height} accent={t.red}>
      <div style={{ flex: 1, overflow: 'auto', padding: '24px 28px' }}>
        <div style={{ fontSize: 11, color: t.textTertiary, letterSpacing: 0.5, textTransform: 'uppercase' }}>Last 42 days</div>
        <h1 style={{ fontSize: 26, fontWeight: 600, letterSpacing: -0.3, margin: '0 0 4px' }}>History</h1>
        <p style={{ fontSize: 13, color: t.textSecondary, margin: '0 0 20px' }}>Active computer time per day. Shutdowns marked.</p>

        {/* top stats */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 }}>
          <BigStat t={t} label="Current streak" value="11 days" note="under cap" tone={t.green} icon={HLIcons.flame} />
          <BigStat t={t} label="Best streak" value="23 days" note="Mar 2 — Mar 24" />
          <BigStat t={t} label="Avg active" value="6h 41m" note="per day, 42d" />
          <BigStat t={t} label="Shutdowns" value="4" note="in last 42 days" tone={t.red} />
        </div>

        {/* bar chart */}
        <div style={{
          padding: '18px 20px', background: t.surface,
          border: `1px solid ${t.border}`, borderRadius: 8, marginBottom: 18,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
            <div style={{ fontSize: 13, fontWeight: 600 }}>Active time per day</div>
            <div style={{ flex: 1 }} />
            <div style={{ display: 'flex', gap: 12, fontSize: 11, color: t.textSecondary }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><Dot color={t.accent} size={8}/>active</span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><Dot color={t.red} size={8}/>hit cap</span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><div style={{ width: 8, height: 8, border: `1.5px solid ${t.red}`, borderRadius: 4 }}/>shutdown</span>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 180, position: 'relative' }}>
            {/* cap line */}
            <div style={{ position: 'absolute', left: 0, right: 0, bottom: `${8/12 * 100}%`, borderTop: `1px dashed ${t.amber}`, opacity: 0.6 }}>
              <span style={{ position: 'absolute', right: 0, top: -14, fontSize: 9, color: t.amber, fontWeight: 600, letterSpacing: 0.5 }}>CAP 8h</span>
            </div>
            {days.map(d => (
              <div key={d.i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end', height: '100%', position: 'relative' }}>
                {d.cutoff && <div style={{ position: 'absolute', top: -6, width: 10, height: 10, borderRadius: 5, border: `1.5px solid ${t.red}`, background: t.surface }} />}
                <div style={{
                  width: '100%', height: `${d.active / 12 * 100}%`,
                  background: d.capped ? t.red : t.accent,
                  borderRadius: '2px 2px 0 0', opacity: 0.9,
                }} />
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: t.textTertiary, marginTop: 6, fontVariantNumeric: 'tabular-nums' }}>
            <span>Mar 11</span><span>Mar 25</span><span>Apr 8</span><span>Apr 21</span>
          </div>
        </div>

        {/* recent events */}
        <div style={{
          padding: '14px 18px', background: t.surface,
          border: `1px solid ${t.border}`, borderRadius: 8,
        }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>Recent lock events</div>
          {[
            { d: 'Today · 14:04', label: 'Cap raise queued · 8h → 10h', tone: 'amber' },
            { d: 'Apr 18 · 23:30', label: 'Cutoff shutdown (60s grace, no cancel)', tone: 'red' },
            { d: 'Apr 14 · 22:17', label: 'Daily cap reached (8h 00m active)', tone: 'red' },
            { d: 'Apr 10 · 08:02', label: 'Dry-run disabled · tightening · applied', tone: 'green' },
            { d: 'Apr 08 · 14:04', label: 'Cap raise (9h → 10h) activated', tone: 'neutral' },
          ].map((e, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 12, fontSize: 12,
              padding: '9px 0', borderTop: i === 0 ? 'none' : `1px solid ${t.divider}`,
            }}>
              <div style={{ width: 110, color: t.textTertiary, fontVariantNumeric: 'tabular-nums', flexShrink: 0 }}>{e.d}</div>
              <Dot color={{ red: t.red, amber: t.amber, green: t.green, neutral: t.textTertiary }[e.tone]} size={6}/>
              <div>{e.label}</div>
            </div>
          ))}
        </div>
      </div>
    </WinWindow>
  );
}

function BigStat({ t, label, value, note, tone, icon }) {
  return (
    <div style={{
      padding: '14px 16px', background: t.surface,
      border: `1px solid ${t.border}`, borderRadius: 8,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10, color: t.textTertiary, letterSpacing: 0.5, textTransform: 'uppercase', marginBottom: 6 }}>
        {icon && <span style={{ color: tone || t.textTertiary }}>{icon}</span>}
        {label}
      </div>
      <div style={{ fontSize: 24, fontWeight: 600, letterSpacing: -0.5, color: tone || t.text, fontVariantNumeric: 'tabular-nums' }}>{value}</div>
      {note && <div style={{ fontSize: 11, color: t.textTertiary, marginTop: 2 }}>{note}</div>}
    </div>
  );
}

// ─────────── Onboarding ───────────
function Onboarding({ t, width = 760, height = 540, step = 2 }) {
  return (
    <WinWindow t={t} title="Hard Lock · Setup" width={width} height={height} accent={t.red}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '28px 48px 24px' }}>
        {/* step dots */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 22 }}>
          {[0,1,2,3,4].map(i => (
            <div key={i} style={{
              height: 3, borderRadius: 2, flex: 1,
              background: i <= step ? t.accent : t.surfaceSunken,
            }}/>
          ))}
        </div>

        <div style={{ fontSize: 10, color: t.textTertiary, letterSpacing: 0.6, textTransform: 'uppercase', fontWeight: 600, marginBottom: 4 }}>
          Step 3 of 5 · Set your limits
        </div>
        <h1 style={{ fontSize: 30, fontWeight: 600, letterSpacing: -0.5, margin: '0 0 10px', maxWidth: 540 }}>
          How much computer is too much?
        </h1>
        <p style={{ fontSize: 14, color: t.textSecondary, margin: '0 0 26px', maxWidth: 520, lineHeight: 1.5 }}>
          Pick numbers your <em>rested</em> self would pick. You won't be able to raise either of these without waiting 24 hours.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 20 }}>
          <div style={{
            padding: '18px 20px', background: t.surface,
            border: `1px solid ${t.border}`, borderRadius: 8,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <div style={{ color: t.accent }}>{HLIcons.clock}</div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>Daily active cap</div>
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 14 }}>
              <div style={{ fontSize: 42, fontWeight: 300, letterSpacing: -1, fontVariantNumeric: 'tabular-nums', lineHeight: 1 }}>8h</div>
              <div style={{ fontSize: 14, color: t.textSecondary }}>of active use per day</div>
            </div>
            {/* slider mock */}
            <div style={{ position: 'relative', height: 18, display: 'flex', alignItems: 'center' }}>
              <div style={{ width: '100%', height: 3, background: t.surfaceSunken, borderRadius: 2 }}>
                <div style={{ width: '50%', height: '100%', background: t.accent, borderRadius: 2 }}/>
              </div>
              <div style={{ position: 'absolute', left: '50%', width: 16, height: 16, borderRadius: 8, background: t.accent, border: '2px solid #fff', boxShadow: t.shadow, transform: 'translateX(-50%)' }}/>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: t.textTertiary, marginTop: 6 }}>
              <span>2h</span><span>16h</span>
            </div>
          </div>

          <div style={{
            padding: '18px 20px', background: t.surface,
            border: `1px solid ${t.border}`, borderRadius: 8,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <div style={{ color: t.red }}>{HLIcons.power}</div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>Hard cutoff time</div>
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 14 }}>
              <div style={{ fontSize: 42, fontWeight: 300, letterSpacing: -1, fontVariantNumeric: 'tabular-nums', lineHeight: 1 }}>23:30</div>
              <div style={{ fontSize: 14, color: t.textSecondary }}>wall-clock</div>
            </div>
            <div style={{ position: 'relative', height: 18, display: 'flex', alignItems: 'center' }}>
              <div style={{ width: '100%', height: 3, background: t.surfaceSunken, borderRadius: 2 }}>
                <div style={{ width: '79%', height: '100%', background: t.red, borderRadius: 2 }}/>
              </div>
              <div style={{ position: 'absolute', left: '79%', width: 16, height: 16, borderRadius: 8, background: t.red, border: '2px solid #fff', boxShadow: t.shadow, transform: 'translateX(-50%)' }}/>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: t.textTertiary, marginTop: 6 }}>
              <span>18:00</span><span>03:00</span>
            </div>
          </div>
        </div>

        <div style={{
          padding: '10px 14px', background: t.amberBg, borderRadius: 6,
          border: `1px solid ${t.amber}22`, fontSize: 12, color: t.textSecondary, lineHeight: 1.5,
          display: 'flex', gap: 10, alignItems: 'flex-start',
        }}>
          <div style={{ color: t.amber, marginTop: 1 }}>{HLIcons.warning}</div>
          <div><strong style={{ color: t.text }}>This is the decision.</strong> After setup, raising the cap or pushing the cutoff later always waits 24h.</div>
        </div>

        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 16 }}>
          <Btn t={t} size="lg">Back</Btn>
          <div style={{ flex: 1 }} />
          <span style={{ fontSize: 11, color: t.textTertiary }}>cooldown defaults to 24h</span>
          <Btn t={t} size="lg" variant="primary">Continue</Btn>
        </div>
      </div>
    </WinWindow>
  );
}

Object.assign(window, { WarningPopup, ShutdownTakeover, CooldownConfirm, TrayMenu, HistoryView, Onboarding });
