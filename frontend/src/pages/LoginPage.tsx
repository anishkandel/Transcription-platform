import { FormEvent, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  Mic,
  ShieldCheck,
} from "lucide-react";
import { useAuth } from "../auth";

export default function LoginPage() {
  const { user, loading, login } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!loading && user) {
    return <Navigate to="/dashboard" replace />;
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();

    setBusy(true);
    setError(null);

    try {
      await login(email.trim(), password);
      navigate("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      {/* Decorative background */}
      <div className="login-background">
        <div className="login-orb login-orb-one" />
        <div className="login-orb login-orb-two" />
        <div className="login-grid" />
      </div>

      <div className="login-container">
        {/* LEFT SIDE */}
        <section className="login-showcase">
          <div className="showcase-brand">
            <div className="showcase-brand-icon">
              <Mic size={23} strokeWidth={2.4} />
            </div>

            <div>
              <strong>Kaituhi-Kōrero</strong>
              <span>Meeting Transcription</span>
            </div>
          </div>

          

            <h1>
              Turn every
              <span> kōrero </span>
              into words.
            </h1>

            <p>
              Capture your meetings, follow live conversations, and keep your
              transcripts organised in one simple workspace.
            </p>

            <div className="showcase-features">
              <div className="showcase-feature">
                <div className="feature-icon">
                  <Mic size={17} />
                </div>

                <div>
                  <strong>Live transcription</strong>
                  <span>Follow your kōrero as it happens.</span>
                </div>
              </div>

              <div className="showcase-feature">
                <div className="feature-icon">
                  <ShieldCheck size={17} />
                </div>

                <div>
                  <strong>Simple workspace</strong>
                  <span>Keep meetings and transcripts together.</span>
                </div>
              </div>
            </div>

          <div className="showcase-footer">
            <span>© Kaituhi-Kōrero</span>
            <span>•</span>
            <span>Meeting transcription workspace</span>
          </div>
        </section>

        {/* RIGHT SIDE */}
        <section className="login-panel">
          <div className="login-card">
            <div className="login-card-header">
              <div className="login-mobile-brand">
                <div className="login-mobile-icon">
                  <Mic size={20} />
                </div>
              </div>

              <span className="login-welcome">WELCOME BACK</span>

              <h2>Sign in to your workspace</h2>

              <p>
                Enter your details below to continue to your meetings and
                transcripts.
              </p>
            </div>

            <form className="login-form" onSubmit={onSubmit}>
              {/* EMAIL */}
              <div className="login-form-group">
                <label htmlFor="login-email">Email address</label>

                <div className="login-input-wrapper">
                  <Mail size={18} />

                  <input
                    id="login-email"
                    type="email"
                    autoComplete="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>
              </div>

              {/* PASSWORD */}
              <div className="login-form-group">
                <div className="password-label-row">
                  <label htmlFor="login-password">Password</label>
                </div>

                <div className="login-input-wrapper">
                  <LockKeyhole size={18} />

                  <input
                    id="login-password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    placeholder="Enter your password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />

                  <button
                    type="button"
                    className="password-toggle"
                    onClick={() => setShowPassword((value) => !value)}
                    aria-label={
                      showPassword ? "Hide password" : "Show password"
                    }
                  >
                    {showPassword ? (
                      <EyeOff size={17} />
                    ) : (
                      <Eye size={17} />
                    )}
                  </button>
                </div>
              </div>

              {error ? (
                <div className="login-error">
                  <span className="login-error-dot" />
                  <p>{error}</p>
                </div>
              ) : null}

              <button
                className="login-submit"
                type="submit"
                disabled={busy}
              >
                <span>{busy ? "Signing in..." : "Sign in"}</span>

                {!busy ? <ArrowRight size={17} /> : null}
              </button>
            </form>

            <div className="login-divider">
              <span />
              <small>NEW TO KAITUHI-KŌRERO?</small>
              <span />
            </div>

            <Link to="/register" className="create-account-button">
              Create your account
              <ArrowRight size={15} />
            </Link>

            <div className="login-security">
              <ShieldCheck size={15} />

              <span>
                Your workspace is protected with secure authentication.
              </span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}