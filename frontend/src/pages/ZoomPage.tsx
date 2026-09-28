import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CalendarDays, Trash2, Video } from "lucide-react";
import { useAuth } from "../auth";
import {
  ZoomAuthStatus,
  ZoomMeeting,
  createSession,
  createZoomMeeting,
  deleteZoomMeeting,
  disconnectZoom,
  getZoomAuthStatus,
  listSessions,
  listZoomMeetings,
  startZoomOAuth,
} from "../api";

const TIMEZONE = "Pacific/Auckland";

function parseAttendeeEmails(raw: string): string[] {
  return raw
    .split(/[\s,;]+/)
    .map((s) => s.trim())
    .filter((s) => s.includes("@"));
}

function buildZoomStartTime(
  date: string,
  hour: string,
  minute: string,
  period: "AM" | "PM"
): string | undefined {
  if (!date || !hour || !minute) return undefined;

  let hour24 = Number(hour);

  if (period === "AM" && hour24 === 12) {
    hour24 = 0;
  }

  if (period === "PM" && hour24 !== 12) {
    hour24 += 12;
  }

  return `${date}T${String(hour24).padStart(2, "0")}:${minute}:00`;
}

export default function ZoomPage() {
  const navigate = useNavigate();
  const { refresh: refreshAuth } = useAuth();

  const [auth, setAuth] = useState<ZoomAuthStatus | null>(null);
  const [meetings, setMeetings] = useState<ZoomMeeting[]>([]);
  const [listNote, setListNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const defaultStart = new Date(Date.now() + 60 * 60 * 1000);

  const [topic, setTopic] = useState("");

  const [startDate, setStartDate] = useState(
    `${defaultStart.getFullYear()}-${String(
      defaultStart.getMonth() + 1
    ).padStart(2, "0")}-${String(defaultStart.getDate()).padStart(2, "0")}`
  );

  const initialHour = defaultStart.getHours();

  const [startHour, setStartHour] = useState(
    String(initialHour % 12 || 12).padStart(2, "0")
  );

  const [startMinute, setStartMinute] = useState("00");

  const [startPeriod, setStartPeriod] = useState<"AM" | "PM">(
    initialHour >= 12 ? "PM" : "AM"
  );

  const [durationHours, setDurationHours] = useState(0);
  const [durationMinutes, setDurationMinutes] = useState(30);
  const [meetingParticipants, setMeetingParticipants] = useState<
  Record<string, string[]>
>({});
  const [attendees, setAttendees] = useState("");


  async function refresh() {
    setError(null);
    setListNote(null);

    try {
      const status = await getZoomAuthStatus();
      setAuth(status);

      if (status.connected) {
        const result = await listZoomMeetings("upcoming");

        setMeetings(result.meetings);

        if (result.warning) {
          setListNote(result.warning);
        } else {
          setListNote(
            `Hosted: ${result.hosted_count ?? 0} · Invited (next ~24h): ${
              result.invited_count ?? 0
            }`
          );
        }
      } else {
        setMeetings([]);
      }

      await refreshAuth();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load Zoom status"
      );
    }
  }

  useEffect(() => {
    void refresh();

    const params = new URLSearchParams(window.location.search);
    const zoomError = params.get("zoom_error");
    const connected = params.get("connected");

    if (zoomError) {
      setError(zoomError);
    } else if (connected === "1") {
      setError(null);
    }
  }, []);

  async function onConnectZoom() {
    setBusy(true);
    setError(null);

    try {
      const url = await startZoomOAuth();
      window.location.href = url;
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to start Zoom connect"
      );
      setBusy(false);
    }
  }

  async function onDisconnect() {
    setBusy(true);
    setError(null);

    try {
      await disconnectZoom();
      await refresh();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to disconnect Zoom"
      );
    } finally {
      setBusy(false);
    }
  }

  async function onCreateMeeting(event: FormEvent) {
    event.preventDefault();

    setBusy(true);
    setError(null);
    setNotice(null);

    const emails = parseAttendeeEmails(attendees);
    const duration = durationHours * 60 + durationMinutes;

    if (!topic.trim()) {
      setError("Please enter a meeting topic.");
      setBusy(false);
      return;
    }

    if (emails.length === 0) {
      setError("Please add at least one participant email.");
      setBusy(false);
      return;
    }

    if (duration <= 0) {
      setError("Please select a meeting duration.");
      setBusy(false);
      return;
    }

    try {
      const created = await createZoomMeeting({
        topic: topic.trim(),
        start_time: buildZoomStartTime(
          startDate,
          startHour,
          startMinute,
          startPeriod
        ),
        duration,
        timezone: TIMEZONE,
        attendees: emails,
      });
      setMeetingParticipants((prev) => ({
       ...prev,
       [String(created.id)]: emails,
    }));

      const inviteNote =
        emails.length > 0
          ? ` · invited ${emails.length} participant${
              emails.length === 1 ? "" : "s"
            }`
          : "";

      setNotice(
        `Meeting created (ID ${created.id})${inviteNote}. Refreshing list…`
      );

      await new Promise((resolve) => setTimeout(resolve, 800));

      await refresh();

      setTopic("");
      setAttendees("");
      setDurationHours(0);
      setDurationMinutes(30);

      setNotice(`Meeting created (ID ${created.id})${inviteNote}.`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create meeting"
      );
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(
    meetingId: string | number,
    meetingTopic: string
  ) {
    const ok = window.confirm(
      `Permanently delete this Zoom meeting?\n\n"${meetingTopic}" (ID ${meetingId})\n\nThis cannot be undone.`
    );

    if (!ok) return;

    setBusy(true);
    setError(null);
    setNotice(null);

    try {
      await deleteZoomMeeting(meetingId);

      setNotice(`Meeting ${meetingId} deleted from Zoom.`);

      await refresh();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to delete meeting"
      );
    } finally {
      setBusy(false);
    }
  }

  async function onOpenSession(meeting: ZoomMeeting) {
    setBusy(true);
    setError(null);

    try {
      const sessions = await listSessions();

      const existingSession = sessions.find(
        (session) =>
          session.platform === "zoom" &&
          String(session.meeting_id) === String(meeting.id)
      );

      if (existingSession) {
        navigate(`/sessions/${existingSession.id}`);
        return;
      }

      const session = await createSession(
        meeting.topic,
        "zoom",
        String(meeting.id),
        "zoom",
        meeting.start_time,
        meeting.duration,
        meetingParticipants[String(meeting.id)] || []
      );

      navigate(`/sessions/${session.id}`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to open session"
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Scheduled Meetings</h1>

          <p>
            Schedule a Zoom meeting, invite participants, and open the meeting
            session when you are ready to begin transcription.
          </p>
        </div>

        <div className="button-row">
          <button
            className="primary-button"
            type="button"
            onClick={() => void onConnectZoom()}
            disabled={busy}
          >
            {auth?.connected ? "Reconnect Zoom" : "Connect Zoom"}
          </button>

          {auth?.connected ? (
            <button
              className="secondary-button"
              type="button"
              onClick={() => void onDisconnect()}
              disabled={busy}
            >
              Disconnect
            </button>
          ) : null}

          <button
            className="secondary-button"
            type="button"
            onClick={() => void refresh()}
            disabled={busy}
          >
            Refresh
          </button>
        </div>
      </div>

      <section
        className="settings-section"
        style={{ marginBottom: 18 }}
      >
        <p className="muted" style={{ margin: 0 }}>
          Zoom connection:{" "}
          <strong>{auth?.connected ? "Connected" : "Not connected"}</strong>

          {auth?.user
            ? ` · ${
                auth.user.display_name ||
                auth.user.email ||
                auth.user.zoom_user_id
              }`
            : ""}
        </p>
      </section>

      <section
        className="settings-section"
        style={{ marginBottom: 24 }}
      >
        <div className="section-title">
          <div>
            <h2>Schedule meeting</h2>
            <p>
              Create a Zoom meeting and invite participants.
            </p>
          </div>
        </div>

        <form
          className="settings-form"
          onSubmit={onCreateMeeting}
        >
          <div className="form-group">
            <label>Topic</label>

            <input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="Enter meeting topic"
              required
            />
          </div>

          <div className="form-group">
            <label>When</label>

            <div className="meeting-when-row">
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                required
              />

              <select
                value={startHour}
                onChange={(e) => setStartHour(e.target.value)}
              >
                {Array.from(
                  { length: 12 },
                  (_, index) => index + 1
                ).map((hour) => (
                  <option
                    key={hour}
                    value={String(hour).padStart(2, "0")}
                  >
                    {hour}
                  </option>
                ))}
              </select>

              <span>:</span>

              <input
              className="meeting-minute-input"
              type="number"
              min="0"
              max="59"
              value={startMinute}
              onChange={(e) => {
                const value = Number(e.target.value);
            
                if (value >= 0 && value <= 59) {
                  setStartMinute(e.target.value);
                }
              }}
              onBlur={() => {
                const minute = Math.min(
                  59,
                  Math.max(0, Number(startMinute) || 0)
                );
            
                setStartMinute(String(minute).padStart(2, "0"));
              }}
            />

              <select
                value={startPeriod}
                onChange={(e) =>
                  setStartPeriod(
                    e.target.value as "AM" | "PM"
                  )
                }
              >
                <option value="AM">AM</option>
                <option value="PM">PM</option>
              </select>
            </div>
          </div>

          <div className="form-group">
            <label>Duration</label>

            <div className="duration-row">
              <select
                value={durationHours}
                onChange={(e) =>
                  setDurationHours(Number(e.target.value))
                }
              >
                <option value={0}>0</option>
                <option value={1}>1</option>
                <option value={2}>2</option>
                <option value={3}>3</option>
                <option value={4}>4</option>
              </select>

              <span>hr</span>

              <select
                value={durationMinutes}
                onChange={(e) =>
                  setDurationMinutes(Number(e.target.value))
                }
              >
                <option value={0}>0</option>
                <option value={15}>15</option>
                <option value={30}>30</option>
                <option value={45}>45</option>
              </select>

              <span>min</span>
            </div>
          </div>

          <div className="form-group">
            <label>
              Participants{" "}
              <span className="required-mark">*</span>
            </label>

            <textarea
              value={attendees}
              onChange={(e) => setAttendees(e.target.value)}
              placeholder="Enter participant email addresses"
              rows={2}
              required
            />

            <span
              className="muted"
              style={{ fontSize: 13 }}
            >
              Add one or more email addresses separated by commas
              or spaces. Zoom will send the meeting invitation.
            </span>
          </div>

          <div
            className="form-group"
            style={{ justifyContent: "end" }}
          >
            <button
              className="primary-button"
              type="submit"
              disabled={busy || !auth?.connected}
            >
              Schedule meeting
            </button>
          </div>
        </form>
      </section>

      {listNote ? (
        <p
          className="muted"
          style={{ marginTop: -8, marginBottom: 16 }}
        >
          {listNote}
        </p>
      ) : null}

      {notice ? (
        <p className="success-note">{notice}</p>
      ) : null}

      {error ? <p className="error">{error}</p> : null}

      <section>
        <div className="section-title">
          <h2>Upcoming meetings</h2>
        </div>

        {meetings.length === 0 ? (
          <div className="empty-meetings">
            <CalendarDays
              size={28}
              color="#0f766e"
            />

            <h3>No upcoming meetings</h3>

            <p>
              {auth?.connected
                ? "You do not currently have any upcoming meetings."
                : "Connect your Zoom account to view or schedule meetings."}
            </p>

            <Link
              to="/settings"
              className="secondary-button"
            >
              Account settings
            </Link>
          </div>
        ) : (
          <div className="scheduled-list">
            {meetings.map((meeting) => (
              <div
                key={String(meeting.id)}
                className="scheduled-card"
              >
                <div className="file-icon">
                  <Video size={18} />
                </div>

                <div className="meeting-information">
                  <span className="status scheduled">
                    {meeting.source === "invited" ||
                    meeting.is_host === false
                      ? "INVITED"
                      : "HOSTED"}
                  </span>

                  <h3>{meeting.topic}</h3>

                  <div className="meeting-details">
                    {meeting.start_time ? (
                      <span>{meeting.start_time}</span>
                    ) : null}

                    {meeting.duration ? (
                      <span>
                        {meeting.duration} min
                      </span>
                    ) : null}
                  </div>
                </div>

                <div className="button-row">
                  <button
                    className="primary-button"
                    type="button"
                    onClick={() =>
                      void onOpenSession(meeting)
                    }
                    disabled={busy}
                  >
                    Open session
                  </button>

                  <button
                    className="secondary-button"
                    type="button"
                    onClick={() =>
                      void onDelete(
                        meeting.id,
                        meeting.topic
                      )
                    }
                    disabled={busy}
                    title="Delete this meeting"
                  >
                    <Trash2 size={14} />
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
