import { Link, useNavigate } from "react-router-dom";
import { ThemeToggle } from "./ThemeToggle";
import { useAuth } from "@/context/AuthContext";

export function Navbar() {
  const { isAuthenticated, user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <header className="sticky top-0 z-40 border-b border-base-border/70 bg-base/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <Link to="/" className="flex items-center gap-2.5">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-signal">
            <span className="h-2.5 w-2.5 rounded-sm bg-white" />
          </span>
          <span className="font-semibold tracking-tight text-ink">Aperture</span>
        </Link>
        <nav className="flex items-center gap-3">
          <Link
            to="/campaigns"
            className="hidden sm:inline-block text-sm text-ink-muted transition-colors hover:text-ink"
          >
            Campaigns
          </Link>
          <Link
            to="/review"
            className="hidden sm:inline-block text-sm text-ink-muted transition-colors hover:text-ink"
          >
            New review
          </Link>
          {isAuthenticated ? (
            <>
              <span className="hidden sm:inline-block text-xs text-ink-faint">{user?.name}</span>
              <button
                onClick={handleLogout}
                className="text-sm text-ink-muted transition-colors hover:text-ink"
              >
                Log out
              </button>
            </>
          ) : (
            <Link to="/login" className="text-sm text-ink-muted transition-colors hover:text-ink">
              Sign in
            </Link>
          )}
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}
