// Hard Lock — top-level canvas composition + tweaks

const TWEAKS = /*EDITMODE-BEGIN*/{
  "theme": "light",
  "hudPreset": "pill-dot"
}/*EDITMODE-END*/;

function App() {
  const [tweaks, setTweaks] = React.useState(TWEAKS);
  const [tweaksOpen, setTweaksOpen] = React.useState(false);

  React.useEffect(() => {
    const onMsg = (e) => {
      if (!e.data || typeof e.data !== 'object') return;
      if (e.data.type === '__activate_edit_mode') setTweaksOpen(true);
      else if (e.data.type === '__deactivate_edit_mode') setTweaksOpen(false);
    };
    window.addEventListener('message', onMsg);
    window.parent.postMessage({ type: '__edit_mode_available' }, '*');
    return () => window.removeEventListener('message', onMsg);
  }, []);

  const setKey = (k, v) => {
    setTweaks((x) => ({ ...x, [k]: v }));
    window.parent.postMessage({ type: '__edit_mode_set_keys', edits: { [k]: v } }, '*');
  };

  // Global theme for most artboards; individual artboards can override.
  const tGlobal = HL_THEMES[tweaks.theme] || HL_THEMES.light;
  const tLight = HL_THEMES.light;
  const tDark = HL_THEMES.dark;

  // Pick HUD variant from tweak
  const hudFor = (state, t) => {
    switch (tweaks.hudPreset) {
      case 'pill-progress': return <HudPillProgress t={t} state={state} time="2:14" usedPct={72} />;
      case 'pill-minimal':  return <HudPillMinimal t={t} state={state} time={state === 'red' ? '0:23' : state === 'amber' ? '2:14' : '5:47'} />;
      case 'pill-dot':
      default:              return <HudPill t={t} state={state} time={state === 'red' ? '0:23' : state === 'amber' ? '2:14' : '5:47'} />;
    }
  };

  return (
    <>
      <DesignCanvas>
        {/* ═══════════ Cover / overview ═══════════ */}
        <DCSection id="overview" title="Hard Lock" subtitle="A Windows self-discipline app that forces shutdown when you've used the computer too long. Windows 11 Fluent · light + dark · traffic-light states.">
          <DCArtboard id="overview-hero" label="System overview" width={1240} height={560}>
            <OverviewHero t={tGlobal} />
          </DCArtboard>
        </DCSection>

        {/* ═══════════ HUD — on desktop, in context ═══════════ */}
        <DCSection id="hud-live" title="Always-on-top HUD · in context" subtitle="The pill sits near the taskbar or a corner. Clicking expands into the widget.">
          <DCArtboard id="hud-desktop-pill" label="Pill on desktop · healthy" width={640} height={400}>
            <DesktopCanvas t={tLight} wallpaper="mountain">
              <div style={{ position: 'absolute', top: 16, right: 16 }}>
                <HudPill t={tLight} state="green" time="5:47" />
              </div>
            </DesktopCanvas>
          </DCArtboard>
          <DCArtboard id="hud-desktop-widget" label="Widget expanded · warning" width={640} height={400}>
            <DesktopCanvas t={tDark} wallpaper="dusk">
              <div style={{ position: 'absolute', top: 16, right: 16 }}>
                <HudWidget t={tDark} state="amber" />
              </div>
            </DesktopCanvas>
          </DCArtboard>
          <DCArtboard id="hud-desktop-critical" label="Detailed widget · critical" width={640} height={400}>
            <DesktopCanvas t={tDark} wallpaper="dark">
              <div style={{ position: 'absolute', top: 16, right: 16 }}>
                <HudWidgetDetailed t={tDark} state="red" />
              </div>
            </DesktopCanvas>
          </DCArtboard>
        </DCSection>

        {/* ═══════════ HUD variations ═══════════ */}
        <DCSection id="hud-variations" title="HUD variations" subtitle="Three pill styles × three states. Pick one via the Tweaks panel.">
          <DCArtboard id="hud-pills-light" label="Light · pill with status dot" width={320} height={260}>
            <HudSwatchSheet t={tLight}>
              <HudPill t={tLight} state="green" time="5:47" />
              <HudPill t={tLight} state="amber" time="2:14" />
              <HudPill t={tLight} state="red" time="0:23" />
            </HudSwatchSheet>
          </DCArtboard>
          <DCArtboard id="hud-pills-dark" label="Dark · pill with status dot" width={320} height={260}>
            <HudSwatchSheet t={tDark}>
              <HudPill t={tDark} state="green" time="5:47" />
              <HudPill t={tDark} state="amber" time="2:14" />
              <HudPill t={tDark} state="red" time="0:23" />
            </HudSwatchSheet>
          </DCArtboard>
          <DCArtboard id="hud-progress-light" label="Light · progress-fill pill" width={320} height={260}>
            <HudSwatchSheet t={tLight}>
              <HudPillProgress t={tLight} state="green" time="5:47" usedPct={28} />
              <HudPillProgress t={tLight} state="amber" time="2:14" usedPct={72} />
              <HudPillProgress t={tLight} state="red" time="0:23" usedPct={95} />
            </HudSwatchSheet>
          </DCArtboard>
          <DCArtboard id="hud-progress-dark" label="Dark · progress-fill pill" width={320} height={260}>
            <HudSwatchSheet t={tDark}>
              <HudPillProgress t={tDark} state="green" time="5:47" usedPct={28} />
              <HudPillProgress t={tDark} state="amber" time="2:14" usedPct={72} />
              <HudPillProgress t={tDark} state="red" time="0:23" usedPct={95} />
            </HudSwatchSheet>
          </DCArtboard>
          <DCArtboard id="hud-minimal-light" label="Light · minimal (tiniest)" width={320} height={260}>
            <HudSwatchSheet t={tLight}>
              <HudPillMinimal t={tLight} state="green" time="5h 47m" />
              <HudPillMinimal t={tLight} state="amber" time="2h 14m" />
              <HudPillMinimal t={tLight} state="red" time="23m" />
            </HudSwatchSheet>
          </DCArtboard>
          <DCArtboard id="hud-widget-compact" label="Expanded widget · compact" width={340} height={380}>
            <HudSwatchSheet t={tLight} center><HudWidget t={tLight} state="amber" /></HudSwatchSheet>
          </DCArtboard>
          <DCArtboard id="hud-widget-detailed" label="Expanded widget · detailed" width={380} height={380}>
            <HudSwatchSheet t={tLight} center><HudWidgetDetailed t={tLight} state="red" /></HudSwatchSheet>
          </DCArtboard>
        </DCSection>

        {/* ═══════════ Settings variations ═══════════ */}
        <DCSection id="settings" title="Settings · main app" subtitle="Pending-changes queue is the core anti-cheat mechanism — this is the key surface of the app.">
          <DCArtboard id="settings-sidebar-light" label="A · sidebar queue · light" width={900} height={620}>
            <SettingsApp t={tLight} variant="sidebar" width={900} height={620} />
          </DCArtboard>
          <DCArtboard id="settings-sidebar-dark" label="B · sidebar queue · dark" width={900} height={620}>
            <SettingsApp t={tDark} variant="sidebar" width={900} height={620} />
          </DCArtboard>
          <DCArtboard id="settings-banner" label="C · banner + tab list" width={900} height={620}>
            <SettingsApp t={tLight} variant="split" width={900} height={620} />
          </DCArtboard>
          <DCArtboard id="settings-unified" label="D · inline pending" width={900} height={620}>
            <SettingsApp t={tLight} variant="unified" width={900} height={620} />
          </DCArtboard>
        </DCSection>

        {/* ═══════════ Warning popups ═══════════ */}
        <DCSection id="warnings" title="Warning popups" subtitle="Fire at 30/10/5/1 minutes. Stern tone, no cancel action — only acknowledgment.">
          <DCArtboard id="warn-30" label="30 min · toast" width={420} height={240}>
            <Center t={tLight}><WarningPopup t={tLight} minsLeft={30} /></Center>
          </DCArtboard>
          <DCArtboard id="warn-10" label="10 min · toast" width={420} height={240}>
            <Center t={tLight}><WarningPopup t={tLight} minsLeft={10} /></Center>
          </DCArtboard>
          <DCArtboard id="warn-5-dark" label="5 min · dark" width={420} height={240}>
            <Center t={tDark}><WarningPopup t={tDark} minsLeft={5} /></Center>
          </DCArtboard>
          <DCArtboard id="warn-1-banner" label="1 min · banner" width={620} height={200}>
            <Center t={tLight}><WarningPopup t={tLight} minsLeft={1} variant="banner" /></Center>
          </DCArtboard>
        </DCSection>

        {/* ═══════════ Fullscreen shutdown takeover ═══════════ */}
        <DCSection id="shutdown" title="Shutdown takeover" subtitle="Medium drama — full red, large countdown, impossible to miss. Three variants.">
          <DCArtboard id="shutdown-classic" label="A · classic red" width={960} height={540}>
            <ShutdownTakeover variant="classic" secs={43} width={960} height={540} />
          </DCArtboard>
          <DCArtboard id="shutdown-minimal" label="B · minimal black + red" width={960} height={540}>
            <ShutdownTakeover variant="minimal" secs={43} width={960} height={540} />
          </DCArtboard>
          <DCArtboard id="shutdown-terminal" label="C · terminal log" width={960} height={540}>
            <ShutdownTakeover variant="terminal" secs={43} width={960} height={540} />
          </DCArtboard>
        </DCSection>

        {/* ═══════════ Cooldown confirm ═══════════ */}
        <DCSection id="cooldown" title="Cooldown confirm" subtitle="Appears when you try to weaken a lock — raise cap, push cutoff later, or enable dry-run.">
          <DCArtboard id="cooldown-light" label="Light" width={520} height={480}>
            <Center t={tLight}><CooldownConfirm t={tLight} /></Center>
          </DCArtboard>
          <DCArtboard id="cooldown-dark" label="Dark" width={520} height={480}>
            <Center t={tDark}><CooldownConfirm t={tDark} /></Center>
          </DCArtboard>
        </DCSection>

        {/* ═══════════ Tray menu ═══════════ */}
        <DCSection id="tray" title="System tray menu" subtitle="Right-click the taskbar icon. Note: 'Quit' and 'Pause' are disabled — you can't escape your own lock.">
          <DCArtboard id="tray-light" label="Light" width={340} height={500}>
            <Center t={tLight}><TrayMenu t={tLight} /></Center>
          </DCArtboard>
          <DCArtboard id="tray-dark" label="Dark" width={340} height={500}>
            <Center t={tDark}><TrayMenu t={tDark} /></Center>
          </DCArtboard>
          <DCArtboard id="tray-in-context" label="In context · dark taskbar" width={640} height={500}>
            <DesktopCanvas t={tDark} wallpaper="dusk">
              <div style={{ position: 'absolute', bottom: 56, right: 16 }}>
                <TrayMenu t={tDark} />
              </div>
            </DesktopCanvas>
          </DCArtboard>
        </DCSection>

        {/* ═══════════ History ═══════════ */}
        <DCSection id="history" title="History & stats" subtitle="Streaks, cap hits, and a clear record of when shutdowns happened. The receipts.">
          <DCArtboard id="history-light" label="Light" width={900} height={620}>
            <HistoryView t={tLight} />
          </DCArtboard>
          <DCArtboard id="history-dark" label="Dark" width={900} height={620}>
            <HistoryView t={tDark} />
          </DCArtboard>
        </DCSection>

        {/* ═══════════ Onboarding ═══════════ */}
        <DCSection id="onboarding" title="First-run onboarding" subtitle="The moment rested-you makes the decision that tired-you has to live with.">
          <DCArtboard id="ob-light" label="Set limits · light" width={760} height={540}>
            <Onboarding t={tLight} step={2} />
          </DCArtboard>
          <DCArtboard id="ob-dark" label="Set limits · dark" width={760} height={540}>
            <Onboarding t={tDark} step={2} />
          </DCArtboard>
        </DCSection>
      </DesignCanvas>

      {tweaksOpen && (
        <TweaksPanel
          tweaks={tweaks}
          setKey={setKey}
          onClose={() => {
            setTweaksOpen(false);
            window.parent.postMessage({ type: '__edit_mode_deactivated' }, '*');
          }}
        />
      )}
    </>
  );
}

// ─────────── Sheet helpers ───────────
function HudSwatchSheet({ t, children, center }) {
  return (
    <div style={{
      width: '100%', height: '100%',
      background: t.bg,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      flexDirection: 'column', gap: 14,
      padding: 20,
    }}>
      {React.Children.map(children, (c, i) => (
        <div key={i} style={{ display: 'flex', justifyContent: 'center', width: center ? 'auto' : 'auto' }}>
          {c}
        </div>
      ))}
    </div>
  );
}

function Center({ t, children }) {
  return (
    <div style={{
      width: '100%', height: '100%',
      background: t.bg,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 20,
    }}>
      {children}
    </div>
  );
}

// ─────────── Overview hero ───────────
function OverviewHero({ t }) {
  return (
    <div style={{
      width: '100%', height: '100%',
      background: t.mica,
      fontFamily: HL_FONT, color: t.text,
      padding: '44px 56px',
      display: 'flex', flexDirection: 'column',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 18 }}>
        <div style={{
          width: 44, height: 44, borderRadius: 10,
          background: t.red, color: '#fff',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 4px 16px rgba(196,43,28,0.3)',
        }}>
          <svg width="22" height="22" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4"><rect x="3" y="7" width="10" height="7" rx="1.5"/><path d="M5 7V5a3 3 0 016 0v2"/></svg>
        </div>
        <div>
          <div style={{ fontSize: 10, color: t.textTertiary, letterSpacing: 2, textTransform: 'uppercase', fontWeight: 600 }}>Hard Lock · v1.3.0 · Windows</div>
          <div style={{ fontSize: 28, fontWeight: 600, letterSpacing: -0.4, lineHeight: 1.1, marginTop: 2 }}>
            A commitment device for your computer time.
          </div>
        </div>
      </div>
      <div style={{ fontSize: 14, color: t.textSecondary, maxWidth: 760, lineHeight: 1.55, marginBottom: 24 }}>
        Two limits — a daily active-use cap and a hard wall-clock cutoff. Whichever hits first forces a shutdown. The app distinguishes tightening the lock (applies instantly) from weakening it (deferred 24 hours), so tired-you-at-11pm can't override rested-you's decisions.
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, flex: 1 }}>
        <Pillar t={t} n="01" title="Track" body="Active input time. Idle past a threshold pauses the counter." color={t.accent} icon={HLIcons.clock} />
        <Pillar t={t} n="02" title="Warn" body="Popups at 30/10/5/1 min. Fullscreen red takeover at zero." color={t.amber} icon={HLIcons.warning} />
        <Pillar t={t} n="03" title="Shut down" body="60-second grace, no cancel. Windows powers off. You set this." color={t.red} icon={HLIcons.power} />
      </div>

      <div style={{
        marginTop: 20, padding: '14px 18px',
        background: t.surface, border: `1px solid ${t.border}`, borderRadius: 8,
        display: 'flex', alignItems: 'center', gap: 14,
      }}>
        <div style={{ color: t.green }}>{HLIcons.shield}</div>
        <div style={{ fontSize: 12, color: t.textSecondary, lineHeight: 1.5 }}>
          <strong style={{ color: t.text }}>Anti-cheat design:</strong> every setting screen is asymmetric. The path to a stricter lock is one click. The path to a weaker one is a 24-hour wait in a pending-changes queue.
        </div>
      </div>
    </div>
  );
}

function Pillar({ t, n, title, body, color, icon }) {
  return (
    <div style={{
      padding: '18px 20px', background: t.surface,
      border: `1px solid ${t.border}`, borderRadius: 10,
      display: 'flex', flexDirection: 'column',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <div style={{ fontSize: 11, color: t.textTertiary, fontFamily: HL_FONT_MONO, letterSpacing: 1 }}>{n}</div>
        <div style={{ width: 30, height: 30, borderRadius: 6, background: color + '18', color, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{icon}</div>
      </div>
      <div style={{ fontSize: 18, fontWeight: 600, letterSpacing: -0.2, marginBottom: 6 }}>{title}</div>
      <div style={{ fontSize: 12, color: t.textSecondary, lineHeight: 1.55 }}>{body}</div>
    </div>
  );
}

// ─────────── Tweaks panel ───────────
function TweaksPanel({ tweaks, setKey, onClose }) {
  const t = HL_THEMES.light; // panel always in light for clarity
  return (
    <div style={{
      position: 'fixed', bottom: 24, right: 24,
      width: 280, zIndex: 1000,
      background: '#fff',
      borderRadius: 10,
      boxShadow: '0 12px 40px rgba(0,0,0,0.18), 0 0 0 1px rgba(0,0,0,0.08)',
      fontFamily: HL_FONT, overflow: 'hidden',
    }}>
      <div style={{
        padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 8,
        borderBottom: '1px solid rgba(0,0,0,0.06)',
      }}>
        <div style={{ fontSize: 13, fontWeight: 600 }}>Tweaks</div>
        <div style={{ flex: 1 }} />
        <div onClick={onClose} style={{ fontSize: 11, color: 'rgba(0,0,0,0.4)', cursor: 'pointer' }}>close</div>
      </div>
      <div style={{ padding: 14 }}>
        <TweakRow label="Theme">
          <PickOne value={tweaks.theme} onChange={(v) => setKey('theme', v)} options={[['light','Light'],['dark','Dark']]} />
        </TweakRow>
        <TweakRow label="HUD preset" subtitle="applies to variation row">
          <PickOne value={tweaks.hudPreset} onChange={(v) => setKey('hudPreset', v)}
            options={[['pill-dot','Status dot'],['pill-progress','Progress fill'],['pill-minimal','Minimal']]} />
        </TweakRow>
      </div>
    </div>
  );
}

function TweakRow({ label, subtitle, children }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#333', marginBottom: 2, letterSpacing: 0.3, textTransform: 'uppercase' }}>{label}</div>
      {subtitle && <div style={{ fontSize: 10, color: '#888', marginBottom: 6 }}>{subtitle}</div>}
      {!subtitle && <div style={{ height: 6 }}/>}
      {children}
    </div>
  );
}

function PickOne({ value, onChange, options }) {
  return (
    <div style={{
      display: 'flex', background: '#f3f3f3',
      border: '1px solid rgba(0,0,0,0.06)', borderRadius: 6, padding: 2, gap: 2,
    }}>
      {options.map(([v, l]) => (
        <div key={v} onClick={() => onChange(v)} style={{
          flex: 1, padding: '6px 8px', fontSize: 11, borderRadius: 4,
          textAlign: 'center', cursor: 'pointer',
          background: value === v ? '#fff' : 'transparent',
          color: value === v ? '#000' : 'rgba(0,0,0,0.6)',
          boxShadow: value === v ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
          fontWeight: value === v ? 500 : 400,
        }}>{l}</div>
      ))}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
