import { Injectable, signal } from '@angular/core';
export type ThemeMode = 'light' | 'dark' | 'system';
const KEY = 'talentrank-ui-theme'; // Only a display preference: never store CVs or tokens.
@Injectable({providedIn:'root'})
export class PreferencesService {
  readonly theme = signal<ThemeMode>(this.restore());
  readonly isDark = signal(false);
  constructor() {
    this.apply();
    // Keep the system option aligned with OS appearance changes without persisting personal data.
    if (typeof window !== 'undefined' && typeof matchMedia !== 'undefined') {
      matchMedia('(prefers-color-scheme: dark)').addEventListener?.('change', () => {
        if (this.theme() === 'system') this.apply();
      });
    }
  }
  private restore(): ThemeMode {
    try { const value=localStorage.getItem(KEY); return value==='light'||value==='dark'||value==='system'?value:'system'; }
    catch { return 'system'; }
  }
  setTheme(mode:ThemeMode) {
    this.theme.set(mode);
    try { localStorage.setItem(KEY,mode); } catch { /* Browsers may block storage. */ }
    this.apply();
  }
  apply() {
    if (typeof document==='undefined') return;
    const dark=this.theme()==='dark' || (this.theme()==='system' && typeof matchMedia!=='undefined' && matchMedia('(prefers-color-scheme: dark)').matches);
    this.isDark.set(dark);
    document.documentElement.classList.toggle('dark',dark);
    document.documentElement.style.colorScheme=dark?'dark':'light';
  }
}
