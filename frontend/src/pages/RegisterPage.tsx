import { FormEvent, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  CheckCircle2,
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  Mic,
  UserRound,
} from "lucide-react";
import { useAuth } from "../auth";

export default function RegisterPage() {
  const { user, loading, register } = useAuth();
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  if (!loading && user) {
    return <Navigate to="/dashboard" replace />;
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);

    try {
      await register(email.trim(), password, name.trim());
      navigate("/dashboard");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Registration failed"
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-background-glow auth-glow-one" />
      <div className="auth-background-glow auth-glow-two" />

      <div className="auth-layout">
        {/* LEFT BRAND PANEL */}
        <section className="auth-showcase">
          <div className="auth-showcase-inner">
            <div className="auth-brand auth-brand-large">
              <div className="sidebar-logo-icon auth-logo">
                <Mic size={25} strokeWidth={2.3} />
              </div>

              <div>
                <strong>Kaituhi-Kōrero</strong>
                <span>Meeting Transcription</span>
              </div>
            </div>

            <div className="auth-showcase-content">
              <span className="auth-kicker">
                <span className="auth-kicker-dot" />
                YOUR KŌRERO, YOUR WORKSPACE
              </span>

              <h1>
                Turn every
                <br />
                kōrero into words.
              </h1>

              <p>
                Create your workspace and keep your meetings,
                conversations, and transcripts organised in one place.
              </p>

              <div className="auth-feature-list">
                <div className="auth-feature">
                  <div className="auth-feature-icon">
                    <Mic size={17} />
                  </div>

                  <div>
                    <strong>Live transcription</strong>
                    <span>
                      Follow your kōrero as it happens.
                    </span>
                  </div>
                </div>

                <div className="auth-feature">
                  <div className="auth-feature-icon">
                    <CheckCircle2 size={17} />
                  </div>

                  <div>
                    <strong>Simple workspace</strong>
                    <span>
                      Keep meetings and transcripts together.
                    </span>
                  </div>
                </div>

                <div className="auth-feature">
                  <div className="auth-feature-icon">
                    <LockKeyhole size={17} />
                  </div>

                  <div>
                    <strong>Secure access</strong>
                    <span>
                      Your workspace is protected with authentication.
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div className="auth-showcase-footer">
              © Kaituhi-Kōrero · Meeting transcription workspace
            </div>
          </div>
        </section>

        {/* RIGHT REGISTER PANEL */}
        <section className="auth-form-panel">
          <div className="auth-card auth-card-register">
            <div className="auth-mobile-brand">
              <div className="sidebar-logo-icon auth-logo">
                <Mic size={22} />
              </div>

              <div>
                <strong>Kaituhi-Kōrero</strong>
                <span>Meeting Transcription</span>
              </div>
            </div>

            <div className="auth-heading">
              <span className="auth-form-kicker">
                CREATE YOUR ACCOUNT
              </span>

              <h2>Create your workspace</h2>

              <p>
                Set up your account to start managing meetings and
                transcripts.
              </p>
            </div>

            <form className="auth-form" onSubmit={onSubmit}>
              {/* NAME */}
              <div className="form-group">
                <label htmlFor="register-name">
                  Name
                  <span className="optional-label">Optional</span>
                </label>

                <div className="input-with-icon">
                  <UserRound size={17} />

                  <input
                    id="register-name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Your name"
                    autoComplete="name"
                  />
                </div>
              </div>

              {/* EMAIL */}
              <div className="form-group">
                <label htmlFor="register-email">
                  Email address
                </label>

                <div className="input-with-icon">
                  <Mail size={17} />

                  <input
                    id="register-email"
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    required
                  />
                </div>
              </div>

              {/* PASSWORD */}
              <div className="form-group">
                <label htmlFor="register-password">
                  Password
                </label>

                <div className="input-with-icon password-input">
                  <LockKeyhole size={17} />

                  <input
                    id="register-password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="new-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Create a password"
                    minLength={8}
                    required
                  />

                  <button
                    type="button"
                    className="password-toggle"
                    onClick={() =>
                      setShowPassword((value) => !value)
                    }
                    aria-label={
                      showPassword
                        ? "Hide password"
                        : "Show password"
                    }
                  >
                    {showPassword ? (
                      <EyeOff size={17} />
                    ) : (
                      <Eye size={17} />
                    )}
                  </button>
                </div>

                <span className="field-hint">
                  Use at least 8 characters.
                </span>
              </div>

              {error ? (
                <div className="auth-error">
                  <span>{error}</span>
                </div>
              ) : null}

              <button
                className="primary-button auth-submit"
                type="submit"
                disabled={busy}
              >
                {busy ? (
                  "Creating your account..."
                ) : (
                  <>
                    Create account
                    <ArrowRight size={16} />
                  </>
                )}
              </button>
            </form>

            <div className="auth-divider">
              <span>Already have an account?</span>
            </div>

            <Link to="/login" className="auth-secondary-button">
              Sign in to your workspace
            </Link>

            <p className="auth-security-note">
              <LockKeyhole size={13} />
              Your account is protected with secure authentication.
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}