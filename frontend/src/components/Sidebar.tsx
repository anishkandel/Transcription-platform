import {
  CalendarDays,
  CheckCircle2,
  Clock3,
  History,
  Home,
  LogOut,
  Mic,
  Settings,
  Sparkles,
} from "lucide-react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

export default function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const isActive = (path: string) => {
    if (path === "/dashboard") {
      return location.pathname === "/" || location.pathname === "/dashboard";
    }

    if (path === "/start-transcription") {
      return (
        location.pathname === path ||
        location.pathname.startsWith("/sessions/")
      );
    }

    return (
      location.pathname === path ||
      location.pathname.startsWith(`${path}/`)
    );
  };

  const initial = (
    user?.name ||
    user?.email ||
    "U"
  )
    .trim()
    .charAt(0)
    .toUpperCase();

  async function onLogout() {
    await logout();
    navigate("/login");
  }

  return (
    <aside className="sidebar">
      {/* Brand */}
      <div className="sidebar-brand">
        <Link to="/dashboard" className="brand-link">
          <div className="brand-mark">
            <Mic size={22} strokeWidth={2.4} />
          </div>

          <div className="brand-text">
            <strong>Kaituhi-Kōrero</strong>
            <span>Meeting Transcription</span>
          </div>
        </Link>
      </div>

      {/* Main navigation */}
      <nav className="sidebar-nav">
        <div className="nav-section">
          <p className="nav-label">MAIN</p>

          <Link
            to="/dashboard"
            className={`nav-item ${
              isActive("/dashboard") ? "active" : ""
            }`}
          >
            <span className="nav-icon">
              <Home size={18} />
            </span>
            <span className="nav-text">Dashboard</span>
          </Link>

          <Link
            to="/scheduled"
            className={`nav-item ${
              isActive("/scheduled") ? "active" : ""
            }`}
          >
            <span className="nav-icon">
              <CalendarDays size={18} />
            </span>
            <span className="nav-text">Scheduled Meetings</span>
          </Link>

          {/* Primary action */}
          <Link
            to="/start-transcription"
            className={`nav-item nav-primary ${
              isActive("/start-transcription") ? "active" : ""
            }`}
          >
            <span className="nav-icon">
              <Mic size={18} />
            </span>
            <span className="nav-text">Start Transcription</span>
            <Sparkles className="nav-sparkle" size={15} />
          </Link>
        </div>

        <div className="nav-section">
          <p className="nav-label">MEETINGS</p>

          <Link
            to="/completed"
            className={`nav-item ${
              isActive("/completed") ? "active" : ""
            }`}
          >
            <span className="nav-icon">
              <CheckCircle2 size={18} />
            </span>
            <span className="nav-text">Completed Meetings</span>
          </Link>

          <Link
            to="/history"
            className={`nav-item ${
              isActive("/history") ? "active" : ""
            }`}
          >
            <span className="nav-icon">
              <History size={18} />
            </span>
            <span className="nav-text">Meeting History</span>
          </Link>

          {/* <Link
            to="/completed"
            className="nav-item nav-subtle-link"
          >
            <span className="nav-icon">
              <Clock3 size={18} />
            </span>
            <span className="nav-text">Recent Activity</span>
          </Link> */}
        </div>

        <div className="nav-section">
          <p className="nav-label">ACCOUNT</p>

          <Link
            to="/settings"
            className={`nav-item ${
              isActive("/settings") ? "active" : ""
            }`}
          >
            <span className="nav-icon">
              <Settings size={18} />
            </span>
            <span className="nav-text">Settings</span>
          </Link>
        </div>
      </nav>

      {/* Bottom area */}
      <div className="sidebar-bottom">
        {/* User profile */}
        <div className="sidebar-user">
          <div className="user-avatar">
            {initial}
          </div>

          <div className="user-details">
            <strong>{user?.name || "User"}</strong>
            <span>{user?.email || "Signed in"}</span>
          </div>
        </div>

        {/* Sign out */}
        <button
          className="logout-button"
          type="button"
          onClick={() => void onLogout()}
        >
          <LogOut size={17} />
          <span>Sign out</span>
        </button>
      </div>
    </aside>
  );
}
