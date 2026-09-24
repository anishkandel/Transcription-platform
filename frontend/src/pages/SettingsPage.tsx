import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth";
import {
  ZoomAuthStatus,
  disconnectZoom,
  getZoomAuthStatus,
  startZoomOAuth,
} from "../api";

export default function SettingsPage() {
  const { user, refresh } = useAuth();
  const [zoom, setZoom] = useState<ZoomAuthStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function loadZoom() {
    try {
      setZoom(await getZoomAuthStatus());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Zoom status");
    }
  }

  useEffect(() => {
    void loadZoom();
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
      await loadZoom();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to disconnect Zoom");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="settings-page">
      <div className="page-header">
        <div>
          <h1>Settings</h1>
          <p>Account, Zoom binding, and prototype configuration.</p>
        </div>
      </div>

      <section className="settings-section">
        <div className="settings-section-header">
          <div className="settings-section-icon">ME</div>
          <div>
            <h2>Account</h2>
            <p>Your Kaituhi Korero login (separate from Zoom).</p>
          </div>
        </div>
        <div className="settings-form">
          <div className="settings-field">
            <label>Name</label>
            <div className="settings-input">
              <input value={user?.name || ""} readOnly />
            </div>
          </div>
          <div className="settings-field">
            <label>Email</label>
            <div className="settings-input">
              <input value={user?.email || ""} readOnly />
            </div>
          </div>
        </div>
      </section>

      <section className="settings-section">
        <div className="settings-section-header">
          <div className="settings-section-icon">ZM</div>
          <div>
            <h2>Zoom binding</h2>
            <p>
              Optional. After Connect Zoom, Scheduled Meetings loads real upcoming meetings from
              the Zoom API.
            </p>
          </div>
        </div>
        <div className="settings-form">
          <div className="settings-field">
            <label>Status</label>
            <div className="settings-input">
              <input
                value={
                  zoom?.connected
                    ? `Connected · ${zoom.user?.display_name || zoom.user?.email || zoom.user?.zoom_user_id}`
                    : "Not connected"
                }
                readOnly
              />
            </div>
          </div>
          <div className="settings-field">
            <label>App credentials</label>
            <div className="settings-input">
              <input
                value={zoom?.zoom_client_configured ? "ZOOM_CLIENT_ID configured" : "Missing in .env"}
                readOnly
              />
            </div>
          </div>
          <div className="button-row">
            <button
              className="primary-button"
              type="button"
              disabled={busy}
              onClick={() => void onConnectZoom()}
            >
              {zoom?.connected ? "Reconnect Zoom" : "Connect Zoom"}
            </button>
            {zoom?.connected ? (
              <button
                className="secondary-button"
                type="button"
                disabled={busy}
                onClick={() => void onDisconnect()}
              >
                Disconnect
              </button>
            ) : null}
            <Link to="/scheduled" className="secondary-button">
              Open Scheduled Meetings
            </Link>
          </div>
          {error ? <p className="error">{error}</p> : null}
        </div>
      </section>

      <section className="settings-section">
        <div className="settings-section-header">
          <div className="settings-section-icon">PR</div>
          <div>
            <h2>Papa Reo</h2>
            <p>Standard chunked transcription is the current default mode.</p>
          </div>
        </div>
        <div className="settings-form">
          <div className="settings-field">
            <label>Mode</label>
            <div className="settings-input">
              <input value="standard (chunked progressive)" readOnly />
            </div>
          </div>
          <div className="settings-field">
            <label>Endpoint</label>
            <div className="settings-input">
              <input value="/tuhi/transcribe" readOnly />
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
