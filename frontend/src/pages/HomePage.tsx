import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  FileText,
  Mic,
  Plus,
  Radio,
  Sparkles,
  Video,
} from "lucide-react";

import { Session, createSession, listSessions } from "../api";

export default function HomePage() {
  const navigate = useNavigate();

  const [title, setTitle] = useState("Orahiri meeting transcription");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function refresh() {
    try {
      setSessions(await listSessions());
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load sessions"
      );
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function onCreate(event: FormEvent) {
    event.preventDefault();

    setLoading(true);
    setError(null);

    try {
      const session = await createSession(
        title.trim() || "Untitled session",
        "file"
      );

      navigate(`/sessions/${session.id}`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create session"
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="start-page-redesign">

      {/* =====================================================
          PAGE HEADER
      ===================================================== */}

      <section className="start-page-hero">
        <div className="start-hero-content">
          <div className="start-eyebrow">
            <span className="start-eyebrow-dot" />
            TRANSCRIPTION WORKSPACE
          </div>

          <h1>Start your transcription</h1>

          <p>
            Turn your meeting kōrero into clear, searchable transcripts.
            Choose a new recording session or continue with Zoom.
          </p>

          <div className="start-hero-actions">
            <button
              className="start-primary-action"
              type="button"
              onClick={() =>
                document
                  .getElementById("new-session-card")
                  ?.scrollIntoView({ behavior: "smooth" })
              }
            >
              <Mic size={17} />
              Start a new session
              <ArrowRight size={15} />
            </button>

            <Link to="/scheduled" className="start-secondary-action">
              <Video size={16} />
              Open Zoom
            </Link>
          </div>
        </div>

        <div className="start-hero-visual">
          <div className="start-glow start-glow-one" />
          <div className="start-glow start-glow-two" />

          <div className="start-floating-card">
            <div className="start-floating-icon">
              <Mic size={25} />
            </div>

            <div>
              <strong>Ready to kōrero</strong>
              <span>Live transcription workspace</span>
            </div>

            <div className="start-live-indicator">
              <span />
              READY
            </div>
          </div>

          <div className="start-wave">
            <span />
            <span />
            <span />
            <span />
            <span />
            <span />
            <span />
            <span />
            <span />
          </div>
        </div>
      </section>

      {/* =====================================================
          OPTIONS
      ===================================================== */}

      <section className="start-options-section">
        <div className="start-section-heading">
          <div>
            <div className="start-section-eyebrow">
              <Sparkles size={13} />
              GET STARTED
            </div>

            <h2>Choose how you want to transcribe</h2>

            <p>
              Start with a new session or connect to an upcoming Zoom meeting.
            </p>
          </div>
        </div>

        <div className="start-options-grid">

          {/* New session */}

          <form
            id="new-session-card"
            className="start-option-card start-new-card"
            onSubmit={onCreate}
          >
            <div className="start-card-top">
              <div className="start-option-icon start-file-icon">
                <FileText size={23} />
              </div>

              <span className="start-card-number">01</span>
            </div>

            <div className="start-option-content">
              <div className="start-card-label">
                <span className="start-status-dot" />
                NEW SESSION
              </div>

              <h3>Create a transcription session</h3>

              <p>
                Create a new workspace for progressive transcription,
                uploaded recordings, or testing.
              </p>

              <div className="start-input-group">
                <label htmlFor="session-title">
                  Session title
                </label>

                <input
                  id="session-title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Enter meeting title"
                />
              </div>

              <button
                className="start-card-button start-card-button-primary"
                type="submit"
                disabled={loading}
              >
                <Mic size={16} />

                {loading ? "Creating session..." : "Create session"}

                {!loading && <ArrowRight size={15} />}
              </button>
            </div>
          </form>

          {/* Zoom */}

          <div className="start-option-card start-zoom-card">
            <div className="start-card-top">
              <div className="start-option-icon start-zoom-icon">
                <Video size={23} />
              </div>

              <span className="start-card-number">02</span>
            </div>

            <div className="start-option-content">
              <div className="start-card-label zoom-label">
                <Radio size={13} />
                ZOOM WORKFLOW
              </div>

              <h3>Start from a Zoom meeting</h3>

              <p>
                Connect your Zoom account, manage scheduled meetings, and
                open a live transcription session.
              </p>

              <div className="start-feature-list">
                <div>
                  <CheckCircle2 size={15} />
                  <span>Manage upcoming meetings</span>
                </div>

                <div>
                  <CheckCircle2 size={15} />
                  <span>Open a live transcription session</span>
                </div>

                <div>
                  <CheckCircle2 size={15} />
                  <span>Follow your meeting kōrero</span>
                </div>
              </div>

              <Link
                to="/scheduled"
                className="start-card-button start-card-button-secondary"
              >
                <Video size={16} />
                Go to Zoom Meetings
                <ArrowRight size={15} />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* =====================================================
          ERROR
      ===================================================== */}

      {error ? (
        <div className="start-error">
          <div className="start-error-icon">
            !
          </div>

          <div>
            <strong>Something went wrong</strong>
            <span>{error}</span>
          </div>
        </div>
      ) : null}

      {/* =====================================================
          RECENT SESSIONS
      ===================================================== */}

      <section className="start-recent-section">
        <div className="start-section-heading start-recent-heading">
          <div>
            <div className="start-section-eyebrow">
              <FileText size={13} />
              YOUR WORKSPACE
            </div>

            <h2>Recent sessions</h2>

            <p>
              Open your latest transcription sessions and continue where you
              left off.
            </p>
          </div>

          {sessions.length > 0 ? (
            <span className="start-session-count">
              {sessions.length}{" "}
              {sessions.length === 1 ? "session" : "sessions"}
            </span>
          ) : null}
        </div>

        {sessions.length === 0 ? (
          <div className="start-empty-state">
            <div className="start-empty-icon">
              <FileText size={25} />
            </div>

            <div className="start-empty-content">
              <h3>No sessions yet</h3>

              <p>
                Create your first transcription session above to begin.
              </p>

              <button
                type="button"
                className="start-empty-button"
                onClick={() =>
                  document
                    .getElementById("new-session-card")
                    ?.scrollIntoView({ behavior: "smooth" })
                }
              >
                <Plus size={15} />
                Create first session
              </button>
            </div>
          </div>
        ) : (
          <div className="start-session-list">
            {sessions.map((session) => (
              <Link
                key={session.id}
                to={`/sessions/${session.id}`}
                className="start-session-row"
              >
                <div className="start-session-file-icon">
                  <FileText size={18} />
                </div>

                <div className="start-session-main">
                  <strong>{session.title}</strong>

                  <span>
                    {session.platform} ·{" "}
                    {session.source || "manual"}
                  </span>
                </div>

                <span
                  className={`start-session-status ${
                    session.status === "completed"
                      ? "completed"
                      : "active"
                  }`}
                >
                  {session.status.split("_").join(" ")}
                </span>

                <div className="start-session-arrow">
                  <ChevronRight size={17} />
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}