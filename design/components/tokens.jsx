// Hard Lock — Windows 11 Fluent-inspired tokens
// Two themes (light + dark), traffic-light states.

const HL_FONT = '"Segoe UI Variable", "Segoe UI", -apple-system, BlinkMacSystemFont, system-ui, sans-serif';
const HL_FONT_MONO = '"Cascadia Code", "JetBrains Mono", "Segoe UI Mono", Consolas, monospace';

const HL_THEMES = {
  light: {
    // Mica-ish warm gray base
    bg: '#f3f3f3',
    mica: 'linear-gradient(180deg, #f6f4f1 0%, #efedea 100%)',
    surface: '#ffffff',
    surfaceAlt: '#fafaf9',
    surfaceSunken: '#eeecea',
    border: 'rgba(0,0,0,0.06)',
    borderStrong: 'rgba(0,0,0,0.12)',
    divider: 'rgba(0,0,0,0.055)',
    text: '#1a1a1a',
    textSecondary: 'rgba(0,0,0,0.6)',
    textTertiary: 'rgba(0,0,0,0.45)',
    textDisabled: 'rgba(0,0,0,0.3)',
    // Fluent-ish accent (Windows blue, tweaked slightly desaturated)
    accent: '#0067c0',
    accentHover: '#005ba1',
    accentSubtle: 'rgba(0,103,192,0.08)',
    // Traffic lights
    green: '#107c41',
    greenBg: 'rgba(16,124,65,0.10)',
    amber: '#b8860b',
    amberBg: 'rgba(184,134,11,0.12)',
    red: '#c42b1c',
    redBg: 'rgba(196,43,28,0.10)',
    // Shadow
    shadow: '0 2px 6px rgba(0,0,0,0.06), 0 0 1px rgba(0,0,0,0.1)',
    shadowLg: '0 8px 24px rgba(0,0,0,0.12), 0 0 1px rgba(0,0,0,0.14)',
    titlebar: '#f9f7f5',
  },
  dark: {
    bg: '#202020',
    mica: 'linear-gradient(180deg, #2a2826 0%, #1f1d1b 100%)',
    surface: '#2b2b2b',
    surfaceAlt: '#323232',
    surfaceSunken: '#1d1d1d',
    border: 'rgba(255,255,255,0.07)',
    borderStrong: 'rgba(255,255,255,0.14)',
    divider: 'rgba(255,255,255,0.06)',
    text: '#ffffff',
    textSecondary: 'rgba(255,255,255,0.72)',
    textTertiary: 'rgba(255,255,255,0.5)',
    textDisabled: 'rgba(255,255,255,0.36)',
    accent: '#4cc2ff',
    accentHover: '#47b1e8',
    accentSubtle: 'rgba(76,194,255,0.12)',
    green: '#6ccb5f',
    greenBg: 'rgba(108,203,95,0.14)',
    amber: '#fce100',
    amberBg: 'rgba(252,225,0,0.12)',
    red: '#ff99a4',
    redBg: 'rgba(255,153,164,0.14)',
    shadow: '0 2px 6px rgba(0,0,0,0.3), 0 0 1px rgba(0,0,0,0.4)',
    shadowLg: '0 8px 32px rgba(0,0,0,0.5), 0 0 1px rgba(0,0,0,0.6)',
    titlebar: '#1f1f1f',
  },
};

Object.assign(window, { HL_FONT, HL_FONT_MONO, HL_THEMES });
