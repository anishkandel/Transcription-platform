import { FormEvent, useEffect, useRef, useState } from "react";
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

import { Session, createSession, listSessions, transcribeAudio } from "../api";

import FileDropzone from "../components/FileDropzone";

export default function HomePage() {
  const navigate = useNavigate();

  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const pendingSession = useRef<Session | null>(null);
  const submitting = useRef(false);
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

    if (!file || file.size === 0 || submitting.current) return;
    submitting.current = true;
    setLoading(true);
    setError(null);

    try {
      const session = pendingSession.current || await createSession(
        title.trim() || file.name.replace(/\.[^.]+$/, ""),
        "file"
      );
      pendingSession.current = session;
      const result = await transcribeAudio(session.id, file);
      if (!result.success) {
        throw new Error(result.detail || "Transcription failed. You can retry using the same session.");
      }
      pendingSession.current = null;

      navigate(`/sessions/${session.id}`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to transcribe recording"
      );
    } finally {
      submitting.current = false;
      setLoading(false);
    }
  }

  return (
    <div className="start-page-redesign">

      {/* =====================================================
          PAGE HEADER
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
              Upload a recording or transcribe a live Zoom meeting.
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
                AUDIO RECORDING
              </div>

              <h3>Upload a recording</h3>

              <p>
                Select your recording, then start transcription.
              </p>

              <div className="start-input-group">
                <label htmlFor="session-title">
                  Session title
                </label>

                <input
                  id="session-title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Optional recording title"
                  disabled={loading || !!pendingSession.current}
                />
              </div>

              <FileDropzone
                file={file}
                onChange={setFile}
                disabled={loading}
              />
              <button
                className="start-card-button start-card-button-primary"
                type="submit"
                disabled={loading || !file || file.size === 0}
              >
                <Mic size={16} />

                {loading ? "Transcribing..." : "Start transcription"}

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
                Upload a recording or open a Zoom meeting above to begin.
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
                Upload a recording
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
