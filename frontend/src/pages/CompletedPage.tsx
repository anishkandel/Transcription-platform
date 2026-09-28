import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  CheckCircle2,
  Clock3,
  FileText,
  Sparkles,
} from "lucide-react";
import { Session, listSessions } from "../api";

export default function CompletedPage() {
  const [sessions, setSessions] = useState<Session[]>([]);

  useEffect(() => {
    void listSessions().then((items) =>
      setSessions(items.filter((item) => item.status === "completed"))
    );
  }, []);

  return (
    <div className="completed-page">
      {/* HERO */}
      <section className="completed-hero">
        <div className="completed-hero-content">
          <div className="completed-eyebrow">
            <CheckCircle2 size={14} />
            MEETING LIBRARY
          </div>

          <h1>Completed Meetings</h1>

          <p>
            Review your finished transcription sessions and quickly open
            transcripts from your meeting history.
          </p>

          <div className="completed-hero-meta">
            <div className="completed-count-pill">
              <CheckCircle2 size={15} />
              <strong>{sessions.length}</strong>
              <span>
                {sessions.length === 1 ? "completed meeting" : "completed meetings"}
              </span>
            </div>
          </div>
        </div>

        <div className="completed-hero-art">
          <div className="completed-glow completed-glow-one" />
          <div className="completed-glow completed-glow-two" />

          <div className="completed-check-card">
            <div className="completed-check-icon">
              <CheckCircle2 size={30} />
            </div>

            <div>
              <strong>All caught up</strong>
              <span>Your finished kōrero lives here</span>
            </div>

            <Sparkles size={17} />
          </div>
        </div>
      </section>

      {/* SECTION HEADER */}
      <section className="completed-section">
        <div className="completed-section-heading">
          <div>
            <div className="completed-section-label">
              <FileText size={13} />
              TRANSCRIPT LIBRARY
            </div>

            <h2>Your completed sessions</h2>

            <p>
              Open any completed meeting to review the full transcript.
            </p>
          </div>

          <div className="completed-total">
            <span>Total</span>
            <strong>{sessions.length}</strong>
          </div>
        </div>

        {/* EMPTY STATE */}
        {sessions.length === 0 ? (
          <div className="completed-empty-state">
            <div className="completed-empty-icon">
              <CheckCircle2 size={28} />
            </div>

            <div className="completed-empty-content">
              <span className="completed-empty-label">
                NO COMPLETED MEETINGS
              </span>

              <h3>No completed meetings yet</h3>

              <p>
                Run a transcription session to create your first completed
                meeting. Once finished, it will appear here.
              </p>

              <Link
                to="/start-transcription"
                className="completed-primary-button"
              >
                <FileText size={15} />
                Start transcription
                <ArrowRight size={14} />
              </Link>
            </div>
          </div>
        ) : (
          <div className="completed-list">
            {sessions.map((session, index) => (
              <article
                key={session.id}
                className="completed-session-card"
              >
                {/* Number / Icon */}
                <div className="completed-session-number">
                  <span>{String(index + 1).padStart(2, "0")}</span>
                </div>

                {/* Main information */}
                <div className="completed-session-main">
                  <div className="completed-session-topline">
                    <span className="completed-status-badge">
                      <CheckCircle2 size={12} />
                      COMPLETED
                    </span>

                    <span className="completed-session-source">
                      {session.source || "manual"}
                    </span>
                  </div>

                  <h3>{session.title}</h3>

                  <div className="completed-session-details">
                    <span>
                      <Clock3 size={14} />
                      {session.scheduled_start
                          ? new Date(session.scheduled_start).toLocaleString()
                          : new Date(session.updated_at).toLocaleString()}
                    </span>

                    <span>
                      <FileText size={14} />
                      {session.platform}
                    </span>
                  </div>
                </div>

                {/* Action */}
                <div className="completed-session-action">
                  <Link
                    to={`/sessions/${session.id}`}
                    className="completed-open-button"
                  >
                    <FileText size={15} />
                    Open transcript
                    <ArrowRight size={15} />
                  </Link>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
