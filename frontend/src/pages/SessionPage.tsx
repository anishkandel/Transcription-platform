import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  CalendarDays,
  Download,
  Mic,
  Upload,
  Video,
} from "lucide-react";

import {
  Session,
  exportUrl,
  getSession,
  getTranscript,
  bindZoomRtmsSession,
  startMockRtms,
  startZoomRtms,
  transcribeAudio,
  wsUrl,
} from "../api";

import FileDropzone from "../components/FileDropzone";
import TranscriptChat from "../components/TranscriptChat";

type ChatLine = {
  id: string;
  fullText: string;
};

function linesFromTranscript(text: string): ChatLine[] {
  return text
    .split(/\n+/)
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part, index) => ({
      id: `loaded-${index}-${part.slice(0, 12)}`,
      fullText: part,
    }));
}

export default function SessionPage() {
  const { sessionId = "" } = useParams();

  const [session, setSession] = useState<Session | null>(null);
  const [transcript, setTranscript] = useState("");
  const [lines, setLines] = useState<ChatLine[]>([]);
  const [provider, setProvider] = useState("none");

  const [file, setFile] = useState<File | null>(null);
  const [mockFile, setMockFile] = useState<File | null>(null);

  const [status, setStatus] = useState<string>("idle");
  const [error, setError] = useState<string | null>(null);

  const [liveNote, setLiveNote] = useState(
    "Connecting websocket..."
  );

  const [isLive, setIsLive] = useState(false);

  const seenSegments = useRef<Set<string>>(new Set());

  const canExport = useMemo(
    () => transcript.trim().length > 0,
    [transcript]
  );

  useEffect(() => {
    if (!sessionId) return;

    async function load() {
      try {
        const [sessionData, transcriptData] = await Promise.all([
          getSession(sessionId),
          getTranscript(sessionId),
        ]);

        setSession(sessionData);
        setTranscript(transcriptData.text || "");
        setProvider(transcriptData.provider || "none");

        if (transcriptData.text) {
          setLines(linesFromTranscript(transcriptData.text));
        }

        if (sessionData.meeting_id) {
          try {
            await bindZoomRtmsSession(
              sessionData.meeting_id,
              sessionId
            );

            setLiveNote(
              "Session linked to Zoom. Keep this page open, then start/join the meeting. Transcripts appear automatically."
            );
          } catch (bindErr) {
            setLiveNote(
              "Keep this page open, then start/join the Zoom meeting. Transcripts appear automatically when RTMS starts."
            );

            console.warn("RTMS bind failed", bindErr);
          }
        }
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load session"
        );
      }
    }

    void load();
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId) return;

    let closedByEffect = false;
    let socket: WebSocket | null = null;
    let retryTimer: number | undefined;

    const connect = () => {
      socket = new WebSocket(wsUrl(sessionId));

      socket.onopen = () => {
        setLiveNote("WebSocket connected");
      };

      socket.onclose = () => {
        setLiveNote("WebSocket disconnected");

        if (!closedByEffect) {
          retryTimer = window.setTimeout(connect, 1500);
        }
      };

      socket.onerror = () => {
        setLiveNote("WebSocket connection error");
      };

      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);

          if (message.type) {
            setLiveNote(`Event: ${message.type}`);
          }

          if (message.provider) {
            setProvider(message.provider);
          }

          if (
            message.type === "zoom.rtms_start_requested" ||
            message.type === "zoom.rtms_started" ||
            message.type === "zoom.rtms_connecting" ||
            message.type === "zoom.rtms_media_connected" ||
            message.type === "zoom.rtms_ready"
          ) {
            setIsLive(true);

            if (typeof message.message === "string") {
              setLiveNote(message.message);
            }
          }

          if (message.type === "zoom.rtms_error") {
            setIsLive(false);

            setError(
              typeof message.message === "string"
                ? message.message
                : "Live RTMS error"
            );
          }

          if (message.type === "zoom.rtms_stopped") {
            setIsLive(false);
          }

          if (
            message.type === "transcript.partial" ||
            message.type === "transcript.final" ||
            message.type === "transcript.final_segment" ||
            message.type === "transcript.started"
          ) {
            setIsLive(
              message.type !== "transcript.final"
            );
          }

          if (
            typeof message.segment === "string" &&
            message.segment.trim()
          ) {
            const segment = message.segment.trim();

            const segmentId =
              message.segment_id !== undefined &&
              message.segment_id !== null
                ? String(message.segment_id)
                : null;

            if (segmentId) {
              const lineId = `stream-${segmentId}`;

              setLines((prev) => {
                const existingIndex = prev.findIndex(
                  (line) => line.id === lineId
                );

                if (existingIndex >= 0) {
                  const next = [...prev];

                  next[existingIndex] = {
                    ...next[existingIndex],
                    fullText: segment,
                  };

                  return next;
                }

                return [
                  ...prev,
                  {
                    id: lineId,
                    fullText: segment,
                  },
                ];
              });
            } else {
              const key = `${
                message.chunk_index ?? "x"
              }:${segment}`;

              if (!seenSegments.current.has(key)) {
                seenSegments.current.add(key);

                setLines((prev) => [
                  ...prev,
                  {
                    id: `${Date.now()}-${prev.length}`,
                    fullText: segment,
                  },
                ]);
              }
            }
          }

          if (typeof message.text === "string") {
            setTranscript(message.text);

            if (
              !message.segment &&
              message.text.trim()
            ) {
              const nextLines =
                linesFromTranscript(message.text);

              setLines((prev) =>
                nextLines.length >= prev.length
                  ? nextLines
                  : prev
              );
            }
          }

          if (message.type === "transcript.final") {
            setIsLive(false);

            if (
              typeof message.text === "string" &&
              message.text.trim()
            ) {
              setLines(
                linesFromTranscript(message.text)
              );
            }
          }
        } catch {
          setLiveNote(
            "Received non-JSON websocket message"
          );
        }
      };
    };

    connect();

    return () => {
      closedByEffect = true;

      if (retryTimer) {
        window.clearTimeout(retryTimer);
      }

      if (!socket) return;

      socket.onmessage = null;
      socket.onerror = null;
      socket.onclose = null;

      const current = socket;

      if (current.readyState === WebSocket.OPEN) {
        current.close();
      } else if (
        current.readyState === WebSocket.CONNECTING
      ) {
        current.onopen = () => current.close();
      }
    };
  }, [sessionId]);

  async function onTranscribe() {
    if (!file || !sessionId) return;

    setStatus("transcribing");
    setError(null);
    setIsLive(true);
    setLines([]);
    setTranscript("");

    seenSegments.current = new Set();

    try {
      const result = await transcribeAudio(
        sessionId,
        file,
        false
      );

      setTranscript(result.transcription || "");

      if (result.transcription) {
        setLines(
          linesFromTranscript(result.transcription)
        );
      }

      if (result.provider) {
        setProvider(result.provider);
      }

      setStatus(
        result.success ? "completed" : "error"
      );

      setIsLive(false);

      if (result.detail) {
        setLiveNote(result.detail);

        if (!result.success) {
          setError(result.detail);
        }
      }

      setSession(await getSession(sessionId));
    } catch (err) {
      setStatus("error");
      setIsLive(false);

      setError(
        err instanceof Error
          ? err.message
          : "Progressive transcription failed"
      );
    }
  }

  async function onMockRtms() {
    if (!mockFile || !sessionId) return;

    setStatus("mock_streaming");
    setError(null);
    setIsLive(true);
    setLines([]);
    setTranscript("");

    seenSegments.current = new Set();

    try {
      await startMockRtms(sessionId, mockFile);

      setLiveNote(
        "Mock RTMS started. Watch live transcript updates..."
      );

      setSession(await getSession(sessionId));
    } catch (err) {
      setStatus("error");
      setIsLive(false);

      setError(
        err instanceof Error
          ? err.message
          : "Mock RTMS failed"
      );
    }
  }

  async function onLiveRtms() {
    if (!session?.meeting_id) {
      setError(
        "This session has no Zoom meeting ID"
      );
      return;
    }

    setError(null);
    setIsLive(true);
    setStatus("live_rtms_starting");

    setLiveNote(
      "Manually requesting Zoom RTMS..."
    );

    try {
      await startZoomRtms(
        session.meeting_id,
        sessionId
      );

      setLiveNote(
        "RTMS start requested. Wait for live transcript events."
      );

      setSession(await getSession(sessionId));
    } catch (err) {
      setStatus("error");
      setIsLive(false);

      setError(
        err instanceof Error
          ? err.message
          : "Failed to start live RTMS"
      );
    }
  }

  if (!session) {
    return (
      <div>
        <p>{error || "Loading session..."}</p>

        <Link to="/">Back</Link>
      </div>
    );
  }

  function formatProvider(value: string) {
    if (
      value === "papa_reo_streaming_live_rtms"
    ) {
      return "Papa Reo Streaming";
    }

    if (value === "papa_reo_streaming") {
      return "Papa Reo Streaming";
    }

    if (value === "papa_reo_standard") {
      return "Papa Reo Standard";
    }

    if (!value || value === "none") {
      return "Not available";
    }

    return value.replace(/_/g, " ");
  }

function formatMeetingDate(value?: string | null) {
  if (!value) return "Not available";

  const date = new Date(value);

  return date.toLocaleString("en-NZ", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

  function formatMeetingDuration(minutes?: number | null) {
    if (!minutes) return "Not available";
  
    if (minutes < 60) {
      return `${minutes} min`;
    }
  
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
  
    if (remainingMinutes === 0) {
      return `${hours} hr`;
    }
  
    return `${hours} hr ${remainingMinutes} min`;
  }

  
  function formatPlatform(value: string) {
    if (value === "zoom") {
      return "Zoom";
    }

    return value
      ? value.charAt(0).toUpperCase() +
          value.slice(1)
      : "Unknown";
  }

  const isCompleted =
    session.status === "completed";

  return (
    <div>
      <div className="page-header">
        <div style={{ width: "100%" }}>
          <p className="crumb">
            <Link to="/">Sessions</Link>
            {" / "}
            {session.title}
          </p>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 16,
              flexWrap: "wrap",
            }}
          >
            <h1 style={{ marginBottom: 4 }}>
              {session.title}
            </h1>

            <span
              className={`status ${session.status}`}
              style={{
                textTransform: "capitalize",
              }}
            >
              {session.status}
            </span>
          </div>

         <p className="muted" style={{ marginTop: 4, marginBottom: 2 }}>
            {session.scheduled_start
              ? formatMeetingDate(session.scheduled_start)
              : "Date not available"}
          
            {session.duration_minutes
              ? ` · ${formatMeetingDuration(session.duration_minutes)}`
              : ""}
          </p>
          
          <p
            className="muted"
            style={{ marginTop: 2, marginBottom: 2 }}
          >
            {formatPlatform(session.platform)}
            {" · "}
            {formatProvider(provider)}
          </p>

{session.participants && session.participants.length > 0 ? (
  <p
    className="muted"
    style={{ marginTop: 2 }}
  >
    Participants: {session.participants.join(", ")}
  </p>
) : null}
        </div>
      </div>

      {!isCompleted ? (
        isLive ? (
          <div className="recording-banner">
            <span className="recording-dot" />

            Live transcription in progress ·{" "}
            {liveNote}
          </div>
        ) : (
          <p
            className="muted"
            style={{ marginBottom: 16 }}
          >
            {liveNote}
          </p>
        )
      ) : (
        <div
          className="success-note"
          style={{
            marginBottom: 20,
            padding: "14px 18px",
          }}
        >
          <strong>Meeting completed</strong>

          <div
            style={{
              marginTop: 4,
              fontSize: 14,
            }}
          >
            Your transcript is ready to review
            and export.
          </div>
        </div>
      )}

      {!isCompleted ? (
        <div className="transcription-options">
          <div className="transcription-option">
            <div className="transcription-option-icon upload-icon">
              <Upload size={22} />
            </div>

            <div className="transcription-option-content">
              <h3>Progressive transcription</h3>

              <p>
                Upload meeting audio to create a
                transcript using Papa Reo.
              </p>

              <div className="stack">
                <FileDropzone
                  file={file}
                  onChange={setFile}
                  disabled={
                    status === "transcribing"
                  }
                  label="Drop meeting audio here"
                />

                <button
                  className="primary-button"
                  type="button"
                  onClick={onTranscribe}
                  disabled={
                    !file ||
                    status === "transcribing"
                  }
                >
                  <Mic size={15} />

                  {status === "transcribing"
                    ? "Transcribing..."
                    : "Start transcription"}
                </button>
              </div>
            </div>
          </div>

          <div className="transcription-option">
            <div className="transcription-option-icon zoom-icon">
              <Video size={22} />
            </div>

            <div className="transcription-option-content">
              <h3>Live Zoom transcription</h3>

              {session.meeting_id ? (
                <>
                  <p>
                    Start or join the linked Zoom
                    meeting. Live transcription
                    begins automatically when the
                    meeting audio becomes available.
                  </p>

                  <button
                    className="secondary-button"
                    type="button"
                    onClick={() =>
                      void onLiveRtms()
                    }
                  >
                    Retry live connection
                  </button>
                </>
              ) : (
                <p>
                  This session is not linked to a
                  Zoom meeting.
                </p>
              )}

              <h3
                style={{
                  marginTop: 20,
                }}
              >
                Test with recording
              </h3>

              <p>
                Use a recording to test the live
                transcription flow.
              </p>

              <div className="stack">
                <FileDropzone
                  file={mockFile}
                  onChange={setMockFile}
                  disabled={
                    status === "mock_streaming"
                  }
                  label="Drop recording here"
                />

                <button
                  className="primary-button"
                  type="button"
                  onClick={onMockRtms}
                  disabled={
                    !mockFile ||
                    status === "mock_streaming"
                  }
                >
                  Start test transcription
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {error ? (
        <p className="error">{error}</p>
      ) : null}

      <div className="transcript-layout">
        <div style={{ minWidth: 0 }}>
          {isCompleted ? (
            <div
              className="section-title"
              style={{
                marginBottom: 10,
              }}
            >
              <h2>Transcript</h2>
            </div>
          ) : null}

          <TranscriptChat
            lines={lines}
            isLive={
              isCompleted ? false : isLive
            }
          />
        </div>

        <aside className="transcript-sidebar">
          <h3>Meeting details</h3>
          <div className="detail">
          <span>Date & time</span>
          <strong>
            {formatMeetingDate(session.scheduled_start)}
          </strong>
        </div>
        
        <div className="detail">
          <span>Duration</span>
          <strong>
            {formatMeetingDuration(session.duration_minutes)}
          </strong>
        </div>
        
        <div className="detail">
          <span>Participants</span>
          <strong>
            {session.participants && session.participants.length > 0
              ? session.participants.join(", ")
              : "Not available"}
          </strong>
        </div>
          <div className="detail">
            <span>
              <CalendarDays size={12} />
              Status
            </span>

            <strong
              style={{
                textTransform: "capitalize",
              }}
            >
              {session.status}
            </strong>
          </div>

          <div className="detail">
            <span>
              <Video size={12} />
              Platform
            </span>

            <strong>
              {formatPlatform(
                session.platform
              )}
            </strong>
          </div>

          <div className="detail">
            <span>
              <Mic size={12} />
              Transcription
            </span>

            <strong>
              {formatProvider(provider)}
            </strong>
          </div>

          <div
            className="stack"
            style={{ marginTop: 18 }}
          >
            <h3
              style={{
                margin: 0,
                fontSize: 14,
              }}
            >
              Export transcript
            </h3>

            <div className="button-row">
              <a
                className={`secondary-button ${
                  !canExport
                    ? "disabled"
                    : ""
                }`}
                href={exportUrl(
                  sessionId,
                  "txt"
                )}
              >
                <Download size={14} />
                TXT
              </a>

              <a
                className={`secondary-button ${
                  !canExport
                    ? "disabled"
                    : ""
                }`}
                href={exportUrl(
                  sessionId,
                  "json"
                )}
              >
                JSON
              </a>

              <a
                className={`secondary-button ${
                  !canExport
                    ? "disabled"
                    : ""
                }`}
                href={exportUrl(
                  sessionId,
                  "docx"
                )}
              >
                DOCX
              </a>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
