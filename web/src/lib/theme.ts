import { create } from "zustand";

export type Theme = "dark" | "light";

const KEY = "artistaboard-theme";

function stored(): Theme {
  return (localStorage.getItem(KEY) as Theme | null) === "light" ? "light" : "dark";
}

// Toggle the `.light` class on <html>; the CSS var overrides in index.css do the
// rest. Applied on load (main.tsx) before first paint to avoid a flash.
export function applyTheme(theme: Theme): void {
  document.documentElement.classList.toggle("light", theme === "light");
  localStorage.setItem(KEY, theme);
}

export const useTheme = create<{ theme: Theme; toggle: () => void }>((set, get) => ({
  theme: stored(),
  toggle: () => {
    const next: Theme = get().theme === "dark" ? "light" : "dark";
    applyTheme(next);
    set({ theme: next });
  },
}));
