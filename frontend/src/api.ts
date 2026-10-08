const API_BASE = import.meta.env.VITE_API_BASE_URL || "";
const TOKEN_KEY = "kk_access_token";

export function getAccessToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setAccessToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Ignore storage failures.
  }
}

async function request(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers || {});

  if (
    init.body &&
    !(init.body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }

  const token = getAccessToken();

  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  return fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
}

async function parseError(response: Response): Promise<string> {
  try {
    const data = await response.json();

    if (typeof data?.detail === "string") return data.detail;

    return JSON.stringify(data);
  } catch {
    return response.statusText;
  }
}

export type AuthUser = {
  id: string;
  email: string;
  name: string;
  zoom_connected: boolean;
  created_at?: string | null;
};

export type Session = {
  id: string;
  user_id?: string | null;
  title: string;
  status: string;
  platform: string;
  meeting_id?: string | null;
  source?: string;
  scheduled_start?: string | null;
  duration_minutes?: number | null;
  actual_duration_seconds?: number | null;
  participants?: string[];
  created_at: string;
  updated_at: string;
};

export type Transcript = {
  session_id: string;
  text: string;
  provider: string;
  is_final: boolean;
  duration_seconds?: number | null;
};

export type ZoomAuthStatus = {
  connected: boolean;
  zoom_client_configured: boolean;
  user: null | {
    zoom_user_id: string;
    email?: string | null;
    display_name?: string | null;
    expires_at: string;
    scope?: string | null;
  };
};

export type ZoomMeeting = {
  id: number | string;
  topic: string;
  start_time?: string;
  duration?: number;
  join_url?: string;
  timezone?: string;
  source?: "hosted" | "invited" | string;
  is_host?: boolean;
};

export async function registerAccount(payload: {
  email: string;
  password: string;
  name?: string;
}): Promise<AuthUser> {
  const response = await request("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });

  if (!response.ok) throw new Error(await parseError(response));

  const data = await response.json();

  if (typeof data.access_token === "string") {
    setAccessToken(data.access_token);
  }

  return data.user;
}

export async function loginAccount(payload: {
  email: string;
  password: string;
}): Promise<AuthUser> {
  const response = await request("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });

  if (!response.ok) throw new Error(await parseError(response));

  const data = await response.json();

  if (typeof data.access_token === "string") {
    setAccessToken(data.access_token);
  }

  return data.user;
}

export async function logoutAccount(): Promise<void> {
  const response = await request("/api/auth/logout", {
    method: "POST",
  });

  setAccessToken(null);

  if (!response.ok) throw new Error(await parseError(response));
}

export async function getMe(): Promise<AuthUser | null> {
  const response = await request("/api/auth/me");

  if (response.status === 401) return null;
  if (!response.ok) throw new Error(await parseError(response));

  const data = await response.json();

  return data.user;
}

export async function createSession(
  title: string,
  platform = "file",
  meetingId?: string,
  source: "manual" | "zoom" | "mock_rtms" = "manual",
  scheduledStart?: string,
  durationMinutes?: number,
  participants: string[] = []
): Promise<Session> {
  const response = await request("/api/sessions", {
    method: "POST",
    body: JSON.stringify({
      title,
      platform,
      meeting_id: meetingId || null,
      source,
      scheduled_start: scheduledStart || null,
      duration_minutes: durationMinutes ?? null,
      participants,
    }),
  });

  if (!response.ok) throw new Error(await parseError(response));

  return response.json();
}

export async function listSessions(): Promise<Session[]> {
  const response = await request("/api/sessions");

  if (!response.ok) throw new Error(await parseError(response));

  return response.json();
}

export async function listSessionsWithAudioDurations(): Promise<Session[]> {
  const sessions = await listSessions();

  return Promise.all(
    sessions.map(async (session) => {
      if (session.platform !== "file") return session;

      try {
        const transcript = await getTranscript(session.id);
        return {
          ...session,
          audio_duration_seconds: transcript.duration_seconds ?? null,
        };
      } catch {
        return { ...session, audio_duration_seconds: null };
      }
    })
  );
}

export async function getSession(
  sessionId: string
): Promise<Session> {
  const response = await request(`/api/sessions/${sessionId}`);

  if (!response.ok) throw new Error(await parseError(response));

  return response.json();
}

export async function getTranscript(
  sessionId: string
): Promise<Transcript> {
  const response = await request(
    `/api/sessions/${sessionId}/transcript`
  );

  if (!response.ok) throw new Error(await parseError(response));

  return response.json();
}

export async function transcribeAudio(
  sessionId: string,
  file: File,
  withMetadata = false
): Promise<{
  transcription: string;
  success: boolean;
  detail?: string;
  provider?: string;
}> {
  const form = new FormData();

  form.append("audio_file", file);
  form.append("with_metadata", String(withMetadata));

  const response = await request(
    `/api/sessions/${sessionId}/transcribe`,
    {
      method: "POST",
      body: form,
    }
  );

  if (!response.ok) throw new Error(await parseError(response));

  return response.json();
}

export async function startMockRtms(
  sessionId: string,
  file: File
) {
  const form = new FormData();

  form.append("audio_file", file);

  const response = await request(
    `/api/sessions/${sessionId}/mock-rtms/start`,
    {
      method: "POST",
      body: form,
    }
  );

  if (!response.ok) throw new Error(await parseError(response));

  return response.json();
}

export async function downloadTranscript(
  sessionId: string,
  format: "txt" | "json" | "docx"
): Promise<void> {
  const response = await request(
    `/api/sessions/${sessionId}/export?format=${format}`
  );

  if (!response.ok) {
    throw new Error(await parseError(response));
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = `transcript-${sessionId}.${format}`;
  document.body.appendChild(link);

  try {
    link.click();
  } finally {
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}

export function wsUrl(sessionId: string) {
  const configured =
    import.meta.env.VITE_WS_BASE_URL ||
    import.meta.env.VITE_API_BASE_URL ||
    "http://127.0.0.1:8000";

  if (
    configured.startsWith("http://") ||
    configured.startsWith("https://")
  ) {
    const base = configured
      .replace(/^http/, "ws")
      .replace(/\/$/, "");

    return `${base}/ws/sessions/${sessionId}`;
  }

  const protocol =
    window.location.protocol === "https:" ? "wss" : "ws";

  return `${protocol}://${window.location.host}/ws/sessions/${sessionId}`;
}

export function zoomLoginUrl() {
  return `${API_BASE}/api/zoom/oauth/login`;
}

export async function startZoomOAuth(): Promise<string> {
  const response = await request("/api/zoom/oauth/start");

  if (!response.ok) throw new Error(await parseError(response));

  const data = await response.json();

  if (!data?.authorize_url) {
    throw new Error(
      "Zoom authorize URL missing from server response"
    );
  }

  return data.authorize_url as string;
}

export async function getZoomAuthStatus(): Promise<ZoomAuthStatus> {
  const response = await request("/api/zoom/oauth/status");

  if (!response.ok) throw new Error(await parseError(response));

  return response.json();
}

export async function disconnectZoom(): Promise<void> {
  const response = await request("/api/zoom/oauth/disconnect", {
    method: "POST",
  });

  if (!response.ok) throw new Error(await parseError(response));
}

export async function listZoomMeetings(
  meetingType = "upcoming"
): Promise<{
  meetings: ZoomMeeting[];
  warning?: string;
  hosted_count?: number;
  invited_count?: number;
}> {
  const response = await request(
    `/api/zoom/meetings?meeting_type=${meetingType}&include_invited=true`
  );

  if (!response.ok) throw new Error(await parseError(response));

  const data = await response.json();

  return {
    meetings: data.meetings || [],
    warning: data.warning,
    hosted_count: data.hosted_count,
    invited_count: data.invited_count,
  };
}

export async function createZoomMeeting(payload: {
  topic: string;
  start_time?: string;
  duration: number;
  timezone: string;
  attendees?: string[];
}) {
  const response = await request("/api/zoom/meetings", {
    method: "POST",
    body: JSON.stringify(payload),
  });

  if (!response.ok) throw new Error(await parseError(response));

  return response.json();
}

export async function deleteZoomMeeting(
  meetingId: string | number
) {
  const response = await request(
    `/api/zoom/meetings/${meetingId}`,
    {
      method: "DELETE",
    }
  );

  if (!response.ok) throw new Error(await parseError(response));

  return response.json();
}

export async function bindZoomRtmsSession(
  meetingId: string | number,
  sessionId: string
) {
  const response = await request(
    `/api/zoom/meetings/${meetingId}/rtms/bind`,
    {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId }),
    }
  );

  if (!response.ok) throw new Error(await parseError(response));

  return response.json();
}

export async function startZoomRtms(
  meetingId: string | number,
  sessionId?: string
) {
  const response = await request(
    `/api/zoom/meetings/${meetingId}/rtms/start`,
    {
      method: "POST",
      body: JSON.stringify({
        session_id: sessionId || null,
      }),
    }
  );

  if (!response.ok) throw new Error(await parseError(response));

  return response.json();
}
