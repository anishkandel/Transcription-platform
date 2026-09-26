import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  Clock3,
  FileText,
  History,
  Search,
  Sparkles,
} from "lucide-react";
import { Session, listSessions } from "../api";

export default function HistoryPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [filter, setFilter] = useState<"all" | "completed" | "active">("all");
  const [query, setQuery] = useState("");

  useEffect(() => {
    void listSessions().then(setSessions);
  }, []);

  const filtered = useMemo(() => {
    return sessions.filter((session) => {
      const matchesQuery = session.title
        .toLowerCase()
        .includes(query.toLowerCase());

      if (!matchesQuery) return false;

      if (filter === "completed") {
        return session.status === "completed";
      }

      if (filter === "active") {
        return session.status !== "completed";
      }

      return true;
    });
  }, [sessions, filter, query]);

  const completedCount = sessions.filter(
    (session) => session.status === "completed"
  ).length;

  const activeCount = sessions.filter(
    (session) => session.status !== "completed"
  ).length;

  return (
    <div className="history-page-redesign">
      {/* =====================================================
          HEADER
      ===================================================== */}

      <section className="history-hero">
        <div className="history-hero-content">
          <div className="history-eyebrow">
            <History size={14} />
            YOUR WORKSPACE
          </div>

          <h1>Meeting History</h1>

          <p>
            Browse your transcription sessions, review previous kōrero, and
            quickly return to a transcript.
          </p>
        </div>

        <div className="history-hero-card">
          <div className="history-hero-icon">
            <FileText size={22} />
          </div>

          <div>
            <span>Total sessions</span>
            <strong>{sessions.length}</strong>
          </div>
        </div>
      </section>

      {/* =====================================================
          SUMMARY CARDS
      ===================================================== */}

      <section className="history-summary-grid">
        <div className="history-summary-card history-summary-all">
          <div className="history-summary-icon">
            <History size={18} />
          </div>

          <div>
            <span>All sessions</span>
            <strong>{sessions.length}</strong>
            <small>Across your workspace</small>
          </div>
        </div>

        <div className="history-summary-card history-summary-completed">
          <div className="history-summary-icon">
            <CheckCircle2 size={18} />
          </div>

          <div>
            <span>Completed</span>
            <strong>{completedCount}</strong>
            <small>Finished transcripts</small>
          </div>
        </div>

        <div className="history-summary-card history-summary-active">
          <div className="history-summary-icon">
            <Activity size={18} />
          </div>

          <div>
            <span>Active</span>
            <strong>{activeCount}</strong>
            <small>Sessions in progress</small>
          </div>
        </div>
      </section>

      {/* =====================================================
          SEARCH + FILTERS
      ===================================================== */}

      <section className="history-controls">
        <div className="history-search-redesign">
          <Search size={18} />

          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search your meetings..."
            aria-label="Search meeting history"
          />

          {query ? (
            <button
              type="button"
              className="history-clear-search"
              onClick={() => setQuery("")}
              aria-label="Clear search"
            >
              ×
            </button>
          ) : null}
        </div>

        <div className="history-filter-group">
          <span className="history-filter-label">Show</span>

          {(["all", "completed", "active"] as const).map((item) => (
            <button
              key={item}
              type="button"
              className={`history-filter ${
                filter === item ? "active" : ""
              }`}
              onClick={() => setFilter(item)}
            >
              {item === "all" && <History size={14} />}
              {item === "completed" && <CheckCircle2 size={14} />}
              {item === "active" && <Clock3 size={14} />}

              <span>
                {item.charAt(0).toUpperCase() + item.slice(1)}
              </span>
            </button>
          ))}
        </div>
      </section>

      {/* =====================================================
          RESULTS HEADER
      ===================================================== */}

      <section className="history-results-header">
        <div>
          <div className="history-results-eyebrow">
            <Sparkles size={13} />
            TRANSCRIPT LIBRARY
          </div>

          <h2>
            {query
              ? `Search results`
              : filter === "all"
              ? "All meetings"
              : filter === "completed"
              ? "Completed meetings"
              : "Active meetings"}
          </h2>

          <p>
            {filtered.length}{" "}
            {filtered.length === 1 ? "session" : "sessions"} available
          </p>
        </div>
      </section>

      {/* =====================================================
          EMPTY STATE
      ===================================================== */}

      {filtered.length === 0 ? (
        <div className="empty-history-redesign">
          <div className="empty-history-icon">
            <History size={28} />
          </div>

          <div>
            <h3>No history found</h3>

            <p>
              {query
                ? "We couldn't find a session matching your search."
                : "There are no sessions in this category yet."}
            </p>

            {query ? (
              <button
                type="button"
                className="secondary-button"
                onClick={() => setQuery("")}
              >
                Clear search
              </button>
            ) : (
              <Link to="/start-transcription" className="primary-button">
                Start transcription
                <ArrowRight size={14} />
              </Link>
            )}
          </div>
        </div>
      ) : (
        /* =====================================================
           HISTORY LIST
        ===================================================== */

        <div className="history-list-redesign">
          {filtered.map((session) => {
            const completed = session.status === "completed";

            return (
              <article key={session.id} className="history-card-redesign">
                <div
                  className={`history-card-icon ${
                    completed ? "completed" : "active"
                  }`}
                >
                  {completed ? (
                    <CheckCircle2 size={20} />
                  ) : (
                    <FileText size={20} />
                  )}
                </div>

                <div className="history-card-main">
                  <div className="history-card-top">
                    <span
                      className={`history-status-badge ${
                        completed ? "completed" : "active"
                      }`}
                    >
                      {completed ? (
                        <>
                          <CheckCircle2 size={12} />
                          COMPLETED
                        </>
                      ) : (
                        <>
                          <Activity size={12} />
                          {session.status
                            .split("_")
                            .join(" ")
                            .toUpperCase()}
                        </>
                      )}
                    </span>
                  </div>

                  <h3>{session.title}</h3>

                  <div className="history-card-details">
                    <span>
                      <Clock3 size={13} />
                      {new Date(session.updated_at).toLocaleString()}
                    </span>

                    <span>
                      <FileText size={13} />
                      {session.platform}
                    </span>
                  </div>

                  <div className="history-card-meta">
                    <span className="history-source">
                      {session.source || "manual"}
                    </span>

                    <span className="history-session-id">
                      ID {session.id.slice(0, 8)}
                    </span>
                  </div>
                </div>

                <div className="history-card-action">
                  <Link
                    to={`/sessions/${session.id}`}
                    className="history-open-button"
                  >
                    <FileText size={15} />
                    <span>Open transcript</span>
                    <ArrowRight size={15} />
                  </Link>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}