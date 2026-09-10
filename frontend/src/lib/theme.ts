// Light/dark theme handling. The design tokens (.dark in index.css) and
// tailwind darkMode:["class"] are already in place — this just toggles the
// `dark` class on <html> and remembers the choice.
export type Theme = "light" | "dark";

const KEY = "theme";

export function getTheme(): Theme {
  const saved = localStorage.getItem(KEY);
  if (saved === "light" || saved === "dark") return saved;
  // Default to the OS preference on first run.
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function applyTheme(theme: Theme): void {
  document.documentElement.classList.toggle("dark", theme === "dark");
  localStorage.setItem(KEY, theme);
}

export function initTheme(): void {
  applyTheme(getTheme());
}

export function toggleTheme(): Theme {
  const next: Theme = getTheme() === "dark" ? "light" : "dark";
  applyTheme(next);
  return next;
}
