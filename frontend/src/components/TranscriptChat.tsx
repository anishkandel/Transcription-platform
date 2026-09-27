import { useEffect, useRef, useState } from "react";
import {
  Maximize2,
  Minimize2,
  User,
  Radio,
  ChevronDown,
} from "lucide-react";

type ChatLine = {
  id: string;
  fullText: string;
};

type Props = {
  lines: ChatLine[];
  isLive: boolean;
  emptyText?: string;
};

export default function TranscriptChat({
  lines,
  isLive,
  emptyText = "Waiting for live transcript...",
}: Props) {
  const scrollerRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const stickToBottomRef = useRef(true);

  const [fullscreen, setFullscreen] = useState(false);
  const [showJump, setShowJump] = useState(false);

  const scrollToLatest = (behavior: ScrollBehavior = "auto") => {
    const node = scrollerRef.current;

    if (!node) return;

    node.scrollTo({
      top: node.scrollHeight,
      behavior,
    });

    endRef.current?.scrollIntoView({
      behavior,
      block: "end",
    });
  };

  /*
   * Automatically follow new transcript lines
   * while the user is already near the bottom.
   */
  useEffect(() => {
    if (!stickToBottomRef.current) {
      setShowJump(true);
      return;
    }

    requestAnimationFrame(() => {
      scrollToLatest(lines.length <= 1 ? "auto" : "smooth");
    });
  }, [lines]);

  /*
   * Fullscreen handling.
   */
  useEffect(() => {
    if (!fullscreen) return;

    const previousOverflow = document.body.style.overflow;

    document.body.style.overflow = "hidden";

    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setFullscreen(false);
      }
    };

    window.addEventListener("keydown", onKey);

    requestAnimationFrame(() => {
      scrollToLatest("auto");
    });

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKey);
    };
  }, [fullscreen]);

  /*
   * Detect whether the user is near the latest transcript.
   */
  function onScroll() {
    const node = scrollerRef.current;

    if (!node) return;

    const distance =
      node.scrollHeight - node.scrollTop - node.clientHeight;

    const nearBottom = distance < 72;

    stickToBottomRef.current = nearBottom;

    setShowJump(!nearBottom && lines.length > 0);
  }

  const latestLineId = lines.length > 0 ? lines[lines.length - 1].id : null;

  return (
    <div
      className={`transcript-main ${
        fullscreen ? "is-fullscreen" : ""
      }`}
    >
      {/* =====================================================
          HEADER
      ====================================================== */}

      <div className="transcript-toolbar">
        <div className="transcript-heading">
          <div className="transcript-heading-icon">
            <Radio size={16} />
          </div>

          <div>
            <strong>
              {fullscreen ? "Fullscreen transcript" : "Live transcript"}
            </strong>

            <p className="muted">
              {fullscreen
                ? "Press Esc or Exit to leave fullscreen preview"
                : isLive
                ? "Listening and processing speech in real time"
                : "Transcript updates appear as speech is processed"}
            </p>
          </div>
        </div>

        <div className="transcript-toolbar-actions">
          <div className={`live-pill ${isLive ? "on" : ""}`}>
            <span className="dot" />

            <span>
              {isLive ? "Live" : "Idle"}
            </span>
          </div>

          <button
            type="button"
            className="icon-button"
            onClick={() => setFullscreen((value) => !value)}
            aria-label={
              fullscreen
                ? "Exit fullscreen"
                : "Enter fullscreen"
            }
            title={
              fullscreen
                ? "Exit fullscreen"
                : "Fullscreen preview"
            }
          >
            {fullscreen ? (
              <Minimize2 size={15} />
            ) : (
              <Maximize2 size={15} />
            )}

            <span>
              {fullscreen ? "Exit" : "Fullscreen"}
            </span>
          </button>
        </div>
      </div>

      {/* =====================================================
          TRANSCRIPT AREA
      ====================================================== */}

      <div
        className="transcript-scroll"
        ref={scrollerRef}
        onScroll={onScroll}
      >
        {lines.length === 0 ? (
          <div className="chat-empty">
            <div className="transcript-empty-state">
              <div className="transcript-empty-icon">
                <MicIcon />
              </div>

              <h3>
                {isLive
                  ? "Listening for speech..."
                  : "No transcript yet"}
              </h3>

              <p>
                {isLive
                  ? "Your transcript will appear here as speech is detected."
                  : emptyText}
              </p>

              {isLive ? (
                <div className="transcript-listening">
                  <span />
                  <span />
                  <span />
                </div>
              ) : null}
            </div>
          </div>
        ) : (
          <div className="transcript-content">
            {lines.map((line, index) => {
              const isLatest = line.id === latestLineId;

              return (
                <article
                  key={line.id}
                  className={`transcript-item ${
                    isLatest && isLive
                      ? "is-current"
                      : ""
                  }`}
                >
                  {/* Speaker icon */}

                  <div className="speaker-avatar">
                    <User size={16} />
                  </div>

                  {/* Transcript content */}

                  <div className="transcript-message">
                    <div className="speaker-header">
                      <div className="speaker-name">
                        <strong>
                          Segment {index + 1}
                        </strong>
                      </div>

                      <span className="provider-label">
                        Papa Reo
                      </span>
                    </div>

                    <p className="transcript-line">
                      {line.fullText}
                      {isLatest && isLive ? (
                        <span className="typing-cursor">
                          <span className="typing-cursor-bar" />
                        </span>
                      ) : null}
                    </p>
                  </div>
                </article>
              );
            })}
          </div>
        )}

        <div
          className="transcript-end-spacer"
          ref={endRef}
          aria-hidden="true"
        />
      </div>

      {/* =====================================================
          JUMP TO LATEST
      ====================================================== */}

      {showJump ? (
        <button
          type="button"
          className="jump-latest"
          onClick={() => {
            stickToBottomRef.current = true;
            setShowJump(false);
            scrollToLatest("smooth");
          }}
        >
          <ChevronDown size={15} />
          Jump to latest
        </button>
      ) : null}

      {/* =====================================================
          TRANSCRIPT COUNT
      ====================================================== */}

           {lines.length > 0 ? (
        <div className="transcript-footer">
          <span>
            {lines.length} {lines.length === 1 ? "segment" : "segments"}
            {" · "}
            {isLive ? "Receiving transcript" : "Transcript ready"}
          </span>
        </div>
      ) : null}
    </div>
  );
}

/*
 * Small microphone icon component.
 * Kept local so we don't need to change any other file.
 */
function MicIcon() {
  return (
    <svg
      width="25"
      height="25"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <rect
        x="9"
        y="2"
        width="6"
        height="12"
        rx="3"
      />
      <path d="M5 11a7 7 0 0 0 14 0" />
      <path d="M12 18v4" />
      <path d="M8 22h8" />
    </svg>
  );
}
