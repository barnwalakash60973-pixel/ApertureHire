import { FiMoon, FiSun } from "react-icons/fi";
import { useTheme } from "@/context/ThemeContext";

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  return (
    <button
      onClick={toggleTheme}
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      className="flex h-9 w-9 items-center justify-center rounded-lg border border-base-border bg-base-surface text-ink-muted transition-colors hover:text-ink"
    >
      {theme === "dark" ? <FiSun size={16} /> : <FiMoon size={16} />}
    </button>
  );
}
