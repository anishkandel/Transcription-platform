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

/** Default: ~1 hour from now, as datetime-local value (YYYY-MM-DDTHH:mm). */
// function defaultLocalStart(): string {
//   const d = new Date(Date.now() + 60 * 60 * 1000);
//   const pad = (n: number) => String(n).padStart(2, "0");
//   return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
// }

/** datetime-local → Zoom start_time (wall time + seconds). */
// function toZoomStartTime(localValue: string): string | undefined {
//   if (!localValue) return undefined;
//   return localValue.length === 16 ? `${localValue}:00` : localValue;
// }

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
  const defaultStart = new Date(Date.now() + 60 * 60 * 1000);
  
  const [topic, setTopic] = useState("");
  
  const [startDate, setStartDate] = useState(
    `${defaultStart.getFullYear()}-${String(defaultStart.getMonth() + 1).padStart(2, "0")}-${String(
      defaultStart.getDate()
    ).padStart(2, "0")}`
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
  
  const [attendees, setAttendees] = useState("");
  const [busy, setBusy] = useState(false);

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
            `Hosted: ${result.hosted_count ?? 0} · Invited (next ~24h): ${result.invited_count ?? 0}`,
          );
        }
      } else {
        setMeetings([]);
      }
      await refreshAuth();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Zoom status");
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
      setError(err instanceof Error ? err.message : "Failed to start Zoom connect");
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
      setError(err instanceof Error ? err.message : "Failed to disconnect Zoom");
    } finally {
      setBusy(false);
    }
  }

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
  
  async function onCreateMeeting(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    const emails = parseAttendeeEmails(attendees);
    try {
      const created = await createZoomMeeting({
        topic,
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
      const inviteNote =
        emails.length > 0
          ? ` · invited ${emails.length} participant${emails.length === 1 ? "" : "s"}`
          : "";
      setNotice(`Meeting created (ID ${created.id})${inviteNote}. Refreshing list…`);
      // Zoom list can lag briefly after create
      await new Promise((r) => setTimeout(r, 800));
      await refresh();
      setStartTime(defaultLocalStart());
      setAttendees("");
      setNotice(`Meeting created (ID ${created.id})${inviteNote}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create meeting");
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(meetingId: string | number, meetingTopic: string) {
    const ok = window.confirm(
      `Permanently delete this Zoom meeting?\n\n"${meetingTopic}" (ID ${meetingId})\n\nThis calls Zoom DELETE /meetings/{id} and cannot be undone.`,
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
      setError(err instanceof Error ? err.message : "Failed to delete meeting");
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
      "zoom"
    );

    navigate(`/sessions/${session.id}`);
  } catch (err) {
    setError(err instanceof Error ? err.message : "Failed to open session");
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
            Open a session first, then start/join the Zoom meeting. Live transcription starts
            automatically when Zoom RTMS begins (no extra Start RTMS click). Invited meetings cover
            roughly the next 24 hours.
          </p>
        </div>
        <div className="button-row">
          <button className="primary-button" type="button" onClick={() => void onConnectZoom()} disabled={busy}>
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
          <button className="secondary-button" type="button" onClick={() => void refresh()} disabled={busy}>
            Refresh
          </button>
        </div>
      </div>

      <section className="settings-section" style={{ marginBottom: 18 }}>
        <p className="muted" style={{ margin: 0 }}>
          App configured: <strong>{auth?.zoom_client_configured ? "yes" : "no"}</strong> · Zoom
          linked: <strong>{auth?.connected ? "yes" : "no"}</strong>
          {auth?.user
            ? ` · ${auth.user.display_name || auth.user.email || auth.user.zoom_user_id}`
            : ""}
        </p>
      </section>

      <section className="settings-section" style={{ marginBottom: 24 }}>
        <div className="section-title">
          <div>
            <h2>Create meeting</h2>
            <p>Creates a real Zoom meeting on the linked account via Meetings API.</p>
          </div>
        </div>
        <form className="settings-form" onSubmit={onCreateMeeting}>
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
              {Array.from({ length: 12 }, (_, index) => index + 1).map((hour) => (
                <option key={hour} value={String(hour).padStart(2, "0")}>
                  {hour}
                </option>
              ))}
            </select>
        
            <span>:</span>
        
            <select
              value={startMinute}
              onChange={(e) => setStartMinute(e.target.value)}
            >
              <option value="00">00</option>
              <option value="15">15</option>
              <option value="30">30</option>
              <option value="45">45</option>
            </select>
        
            <select
              value={startPeriod}
              onChange={(e) =>
                setStartPeriod(e.target.value as "AM" | "PM")
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
              onChange={(e) => setDurationHours(Number(e.target.value))}
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
              onChange={(e) => setDurationMinutes(Number(e.target.value))}
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
              Participants <span className="required-mark">*</span>
            </label>
          
            <textarea
              value={attendees}
              onChange={(e) => setAttendees(e.target.value)}
              placeholder="Enter participant email addresses"
              rows={2}
              required
            />
          
            <span className="muted" style={{ fontSize: 13 }}>
              Add one or more email addresses separated by commas or spaces.
              Zoom will send the meeting invitation.
            </span>
          </div>
          <div className="form-group" style={{ justifyContent: "end" }}>
            <button className="primary-button" type="submit" disabled={busy || !auth?.connected}>
              Create upcoming meeting
            </button>
          </div>
        </form>
      </section>

      {listNote ? (
        <p className="muted" style={{ marginTop: -8, marginBottom: 16 }}>
          {listNote}
        </p>
      ) : null}

      {notice ? <p className="success-note">{notice}</p> : null}
      {error ? <p className="error">{error}</p> : null}

      <section>
        <div className="section-title">
          <h2>Upcoming meetings</h2>
        </div>

        {meetings.length === 0 ? (
          <div className="empty-meetings">
            <CalendarDays size={28} color="#0f766e" />
            <h3>No upcoming meetings loaded</h3>
            <p>
              {auth?.connected
                ? "No hosted upcoming meetings and no invited meetings in the next ~24 hours. Ask your friend for the meeting ID/join link, or create a meeting you host below."
                : "Sign in is done — click Connect Zoom, approve access, then refresh."}
            </p>
            <Link to="/settings" className="secondary-button">
              Account settings
            </Link>
          </div>
        ) : (
          <div className="scheduled-list">
            {meetings.map((meeting) => (
              <div key={String(meeting.id)} className="scheduled-card">
                <div className="file-icon">
                  <Video size={18} />
                </div>
                <div className="meeting-information">
                  <span className="status scheduled">
                    {meeting.source === "invited" || meeting.is_host === false ? "INVITED" : "HOSTED"}
                  </span>
                  <h3>{meeting.topic}</h3>
                  <div className="meeting-details">
                    <span>ID {meeting.id}</span>
                    {meeting.start_time ? <span>{meeting.start_time}</span> : null}
                    {meeting.duration ? <span>{meeting.duration} min</span> : null}
                  </div>
                </div>
                <div className="button-row">
                  <button
                    className="primary-button"
                    type="button"
                    onClick={() => void onOpenSession(meeting)}
                    disabled={busy}
                  >
                    Open session
                  </button>
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={() => void onDelete(meeting.id, meeting.topic)}
                    disabled={busy}
                    title="Permanently delete this meeting on Zoom"
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
