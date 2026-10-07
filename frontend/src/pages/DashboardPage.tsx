import {
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  Link,
  useNavigate,
} from "react-router-dom";

import {
  ArrowRight,
  CalendarDays,
  CheckCircle2,
  Clock3,
  FileAudio,
  FileText,
  Mic,
  Plus,
  Radio,
  Sparkles,
  Upload,
  Video,
  Wifi,
  WifiOff,
} from "lucide-react";

import {
  Session,
  ZoomMeeting,
  createSession,
  getZoomAuthStatus,
  listSessions,
  listZoomMeetings,
} from "../api";

export default function DashboardPage() {
  const navigate = useNavigate();

  const [sessions, setSessions] =
    useState<Session[]>([]);

  const [meetings, setMeetings] =
    useState<ZoomMeeting[]>([]);

  const [zoomConnected, setZoomConnected] =
    useState(false);

  const [creating, setCreating] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  /* =========================================================
     LOAD DASHBOARD
     ========================================================= */

  useEffect(() => {
    let cancelled = false;

    const timer = window.setTimeout(() => {
      async function load() {
        try {
          const [
            sessionRows,
            zoomStatus,
          ] = await Promise.all([
            listSessions(),
            getZoomAuthStatus(),
          ]);

          if (cancelled) return;

          setSessions(sessionRows);
          setZoomConnected(
            zoomStatus.connected
          );

          if (zoomStatus.connected) {
            const result =
              await listZoomMeetings(
                "upcoming"
              );

            if (cancelled) return;

            const activeUpcomingMeetings =
            result.meetings.filter((meeting) => {
              const relatedSession =
                sessionRows.find(
                  (session) =>
                    session.platform === "zoom" &&
                    String(session.meeting_id) ===
                      String(meeting.id)
                );
          
              if (
                relatedSession?.status ===
                "completed"
              ) {
                return false;
              }
          
              if (meeting.start_time) {
                const startTime =
                  new Date(
                    meeting.start_time
                  ).getTime();
          
                const durationMs =
                  (meeting.duration || 0) *
                  60 *
                  1000;
          
                const meetingEnd =
                  startTime + durationMs;
          
                if (
                  meetingEnd <
                  Date.now()
                ) {
                  return false;
                }
              }
          
              return true;
            });
          
          setMeetings(
            activeUpcomingMeetings.slice(0, 6)
          );
          } else {
            setMeetings([]);
          }
        } catch (err) {
          if (!cancelled) {
            setError(
              err instanceof Error
                ? err.message
                : "Failed to load dashboard"
            );
          }
        }
      }

      void load();
    }, 400);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, []);

  /* =========================================================
     STATS
     ========================================================= */

  const stats = useMemo(() => {
    const completed = sessions.filter(
      (session) =>
        session.status === "completed"
    ).length;

    const live = sessions.filter(
      (session) =>
        [
          "transcribing",
          "mock_streaming",
        ].includes(session.status)
    ).length;

    return {
      scheduled: meetings.length,
      live,
      completed,
      total: sessions.length,
    };
  }, [sessions, meetings]);

  const recent = sessions.slice(0, 5);

  /* =========================================================
     OPEN ZOOM MEETING
     ========================================================= */

  async function openMeeting(
    meeting: ZoomMeeting
  ) {
    setCreating(true);
    setError(null);

    try {
      const existingSession =
        sessions.find(
          (session) =>
            session.platform === "zoom" &&
            String(session.meeting_id) ===
              String(meeting.id)
        );

      /*
       * If a transcription session already exists
       * for this Zoom meeting, simply open it.
       */
      if (existingSession) {
        navigate(
          `/sessions/${existingSession.id}`
        );

        return;
      }

      /*
       * Otherwise create a transcription session
       * for this Zoom meeting.
       */
      const session =
        await createSession(
          meeting.topic,
          "zoom",
          String(meeting.id),
          "zoom",
          meeting.start_time,
          meeting.duration,
          []
        );

      navigate(
        `/sessions/${session.id}`
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to open meeting"
      );
    } finally {
      setCreating(false);
    }
  }

  /* =========================================================
     UPLOAD SESSION
     ========================================================= */

  async function startUploadSession() {
    setCreating(true);
    setError(null);

    try {
      const session =
        await createSession(
          "Uploaded recording session",
          "file",
          undefined,
          "manual"
        );

      navigate(
        `/sessions/${session.id}`
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to create session"
      );
    } finally {
      setCreating(false);
    }
  }

  /* =========================================================
     PAGE
     ========================================================= */

  return (
    <div className="dashboard-page">

      {/* =====================================================
          HERO
      ===================================================== */}

      <section className="dashboard-hero">
        <div className="dashboard-hero-content">
          <div className="welcome-label">
            <span className="welcome-dot" />

            Kaituhi-Kōrero workspace
          </div>

          <h1>
            Kia ora, welcome back 👋
          </h1>

          <p>
            Manage your meetings, start
            transcription, and review your
            kōrero from one simple workspace.
          </p>

          <div className="hero-actions">
            <Link
              to="/scheduled"
              className="primary-button hero-primary"
            >
              <Plus size={17} />

              Schedule meeting
            </Link>

            <Link
              to="/history"
              className="hero-secondary"
            >
              View transcript history

              <ArrowRight size={15} />
            </Link>
          </div>
        </div>

        <div className="dashboard-hero-decoration">
          <div className="hero-circle hero-circle-one" />
          <div className="hero-circle hero-circle-two" />

          <div className="hero-mic-card">
            <div className="hero-mic-icon">
              <Mic size={26} />
            </div>

            <div>
              <strong>
                Ready to kōrero
              </strong>

              <span>
                Live transcription workspace
              </span>
            </div>

            <Sparkles
              size={17}
              className="hero-sparkle"
            />
          </div>
        </div>
      </section>

      {/* =====================================================
          STATS
      ===================================================== */}

      <section className="dashboard-stats">

        <StatCard
          icon={
            <CalendarDays size={19} />
          }
          title="Upcoming meetings"
          value={String(
            stats.scheduled
          )}
          description="From Zoom"
          accent="teal"
          to="/scheduled"
        />

        <StatCard
          icon={<Radio size={19} />}
          title="Live transcription"
          value={String(stats.live)}
          description={
            stats.live > 0
              ? "Currently active"
              : "Nothing live"
          }
          accent="orange"
          live={stats.live > 0}
        />

        <StatCard
          icon={
            <CheckCircle2 size={19} />
          }
          title="Completed meetings"
          value={String(
            stats.completed
          )}
          description="Successfully completed"
          accent="green"
        />

        <StatCard
          icon={
            <FileText size={19} />
          }
          title="Total transcripts"
          value={String(stats.total)}
          description="Your transcript library"
          accent="purple"
          to="/history"
        />

      </section>

      {/* =====================================================
          QUICK START
      ===================================================== */}

      <section className="quick-start-section">
        <div className="section-heading-large">
          <div>
            <div className="section-eyebrow">
              <Sparkles size={13} />

              QUICK START
            </div>

            <h2>
              Start a transcription
            </h2>

            <p>
              Choose how you want to capture
              your kōrero today.
            </p>
          </div>
        </div>

        <div className="transcription-options">

          {/* ZOOM */}

          <div className="transcription-option zoom-option">
            <div className="option-top">

              <div className="transcription-option-icon zoom-icon">
                <Video size={23} />
              </div>

              {zoomConnected ? (
                <span className="connection-badge connected">
                  <Wifi size={12} />

                  Connected
                </span>
              ) : (
                <span className="connection-badge disconnected">
                  <WifiOff size={12} />

                  Not connected
                </span>
              )}

            </div>

            <div className="transcription-option-content">
              <h3>
                Start Zoom Meeting
              </h3>

              <p>
                Connect to your Zoom meetings
                and begin live transcription
                while your meeting is
                happening.
              </p>

              <Link
                to="/scheduled"
                className="option-action primary-button"
              >
                <Mic size={15} />

                Start transcription

                <ArrowRight size={14} />
              </Link>
            </div>
          </div>

          {/* UPLOAD */}

          <div className="transcription-option upload-option">
            <div className="option-top">

              <div className="transcription-option-icon upload-icon">
                <Upload size={23} />
              </div>

              <span className="connection-badge recording-badge">
                <FileAudio size={12} />

                Audio file
              </span>
            </div>

            <div className="transcription-option-content">
              <h3>
                Upload Audio
              </h3>

              <p>
                Upload a recorded meeting and
                process it with progressive
                chunked transcription.
              </p>

              <button
                className="option-action secondary-button"
                type="button"
                onClick={() =>
                  void startUploadSession()
                }
                disabled={creating}
              >
                <Upload size={15} />

                {creating
                  ? "Creating session..."
                  : "Upload recording"}

                {!creating && (
                  <ArrowRight size={14} />
                )}
              </button>
            </div>
          </div>

        </div>
      </section>

      {/* =====================================================
          ERROR
      ===================================================== */}

      {error ? (
        <div className="dashboard-error">
          <strong>
            Something went wrong
          </strong>

          <span>{error}</span>
        </div>
      ) : null}

      {/* =====================================================
          UPCOMING MEETINGS
      ===================================================== */}

      <section className="dashboard-section">

        <div className="section-title">
          <div>
            <h2>
              Upcoming meetings
            </h2>

            <p>
              Your next meetings available
              through Zoom.
            </p>
          </div>

          <Link
            to="/scheduled"
            className="view-all-link"
          >
            View all

            <ArrowRight size={15} />
          </Link>
        </div>

        {!zoomConnected ? (

          <div className="empty-meetings enhanced-empty">
            <div className="empty-icon">
              <Video size={22} />
            </div>

            <div>
              <h3>
                Connect your Zoom account
              </h3>

              <p>
                Connect Zoom to automatically
                load your hosted and invited
                meetings here.
              </p>

              <Link
                to="/scheduled"
                className="primary-button"
              >
                Connect Zoom

                <ArrowRight size={14} />
              </Link>
            </div>
          </div>

        ) : meetings.length === 0 ? (

          <div className="empty-meetings enhanced-empty">
            <div className="empty-icon">
              <CalendarDays size={22} />
            </div>

            <div>
              <h3>
                No upcoming Zoom meetings
              </h3>

              <p>
                Your upcoming hosted and
                invited meetings will appear
                here.
              </p>

              <Link
                to="/scheduled"
                className="secondary-button"
              >
                Open Scheduled Meetings
              </Link>
            </div>
          </div>

        ) : (

          <div className="meeting-grid">

            {meetings.map(
              (meeting) => (
                <MeetingCard
                  key={String(
                    meeting.id
                  )}

                  title={
                    meeting.topic
                  }

                  date={
                    meeting.start_time
                      ? new Date(
                          meeting.start_time
                        ).toLocaleDateString(
                          undefined,
                          {
                            weekday:
                              "short",
                            day: "numeric",
                            month: "short",
                          }
                        )
                      : "Date TBD"
                  }

                  time={
                    meeting.start_time
                      ? new Date(
                          meeting.start_time
                        ).toLocaleTimeString(
                          undefined,
                          {
                            hour:
                              "numeric",
                            minute:
                              "2-digit",
                          }
                        )
                      : "Time TBD"
                  }

                  duration={
                    meeting.duration
                      ? `${meeting.duration} min`
                      : "—"
                  }

                  participants={
                    meeting.source ===
                      "invited" ||
                    meeting.is_host ===
                      false
                      ? "Invited meeting"
                      : "You host"
                  }
                  actionLabel={
                    sessions.some(
                      (session) =>
                        session.platform === "zoom" &&
                        String(session.meeting_id) === String(meeting.id)
                    )
                      ? "Open session"
                      : "Create session"
                  }

                  disabled={creating}

                  onOpen={() =>
                    void openMeeting(
                      meeting
                    )
                  }
                />
              )
            )}

          </div>

        )}
      </section>

      {/* =====================================================
          RECENT TRANSCRIPTS
      ===================================================== */}

      <section className="dashboard-section recent-section">

        <div className="section-title">
          <div>
            <h2>
              Recent sessions
            </h2>

            <p>
              Quick access to your latest
              transcription sessions.
            </p>
          </div>

          <Link
            to="/history"
            className="view-all-link"
          >
            View history

            <ArrowRight size={15} />
          </Link>
        </div>

        {recent.length === 0 ? (

          <div className="empty-meetings enhanced-empty">
            <div className="empty-icon">
              <FileText size={22} />
            </div>

            <div>
              <h3>
                No sessions yet
              </h3>

              <p>
                Start a meeting or upload a
                recording to create your
                first transcript.
              </p>
            </div>
          </div>

        ) : (

          <div className="transcript-list">

            {recent.map(
              (session) => (
                <Link
                  key={session.id}
                  to={`/sessions/${session.id}`}
                  className="transcript-row"
                >
                  <div className="file-icon">
                    <FileText
                      size={18}
                    />
                  </div>

                  <div className="transcript-row-content">
                    <strong>
                      {session.title}
                    </strong>

                    <span>
                      {new Date(
                        session.updated_at
                      ).toLocaleString()}
                    </span>
                  </div>

                  <span
                    className={`transcript-status ${session.status.toLowerCase()}`}
                  >
                    {session.status
                      .split("_")
                      .join(" ")}
                  </span>

                  <div className="transcript-arrow">
                    <ArrowRight
                      size={16}
                    />
                  </div>
                </Link>
              )
            )}

          </div>

        )}

      </section>
    </div>
  );
}

/* =========================================================
   STAT CARD
   ========================================================= */

function StatCard({
  icon,
  title,
  value,
  description,
  accent,
  live,
  to,
}: {
  icon: ReactNode;
  title: string;
  value: string;
  description: string;
  accent:
    | "teal"
    | "orange"
    | "green"
    | "purple";
  live?: boolean;
  to?: string;
}) {
  const content = (
    <>
     <div className="stat-card-top">
        <div className="stat-icon">
          {icon}
        </div>
      
        {live && (
          <span className="stat-live">
            <span />
            LIVE
          </span>
        )}
      </div>

      <div className="stat-card-info">
        <span>{title}</span>

        <strong>{value}</strong>

        <small>
          {description}
        </small>
      </div>
    </>
  );

  if (to) {
    return (
      <Link
        to={to}
        className={`stat-card stat-${accent}`}
        style={{
          textDecoration: "none",
          color: "inherit",
        }}
      >
        {content}
      </Link>
    );
  }

  return (
    <div
      className={`stat-card stat-${accent}`}
    >
      {content}
    </div>
  );
}

/* =========================================================
   MEETING CARD
   ========================================================= */

function MeetingCard({
  title,
  date,
  time,
  duration,
  participants,
  actionLabel,
  onOpen,
  disabled,
}: {
  title: string;
  date: string;
  time: string;
  duration: string;
  participants: string;
  actionLabel: string;
  onOpen: () => void;
  disabled?: boolean;
}) {
  return (
    <div className="meeting-card">

      <div className="meeting-card-header">

        <span className="meeting-type">
          <Video size={12} />

          Zoom
        </span>

        <span className="meeting-host-status">
          {participants === "You host"
            ? "HOST"
            : "INVITED"}
        </span>

      </div>

      <h3>{title}</h3>

      <div className="meeting-info">

        <div>
          <CalendarDays size={14} />

          <span>{date}</span>
        </div>

        <div>
          <Clock3 size={14} />

          <span>
            {time} · {duration}
          </span>
        </div>

      </div>

      <div className="meeting-card-footer">

        <span className="meeting-participant">
          {participants}
        </span>

        <button
          type="button"
          className="meeting-open"
          onClick={onOpen}
          disabled={disabled}
        >
          {disabled ? "Opening..." : actionLabel}

          {!disabled && (
            <ArrowRight size={13} />
          )}
        </button>

      </div>

    </div>
  );
}
