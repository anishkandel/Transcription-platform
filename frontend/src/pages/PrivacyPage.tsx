export default function PrivacyPage() {
  return (
    <main className="legal-page">
      <div className="legal-container">
        <h1>Privacy Policy</h1>

        <p>
          Kaituhi Kōrero is a meeting transcription platform that supports
          live Zoom meeting transcription and uploaded audio transcription.
        </p>

        <h2>Information we collect</h2>
        <p>
          The application may process account information, Zoom account
          information, meeting metadata, participant information, audio,
          transcripts, and Zoom OAuth authorization tokens where required
          to provide the service.
        </p>

        <h2>How information is used</h2>
        <p>
          Information is used only to authenticate users, connect Zoom
          accounts, manage meeting sessions, process audio for transcription,
          display transcripts, and provide transcript export functionality.
        </p>

        <h2>Zoom data</h2>
        <p>
          When a user connects their Zoom account, Kaituhi Kōrero uses Zoom
          OAuth to access only the permissions required for the application's
          meeting and transcription functionality.
        </p>

        <p>
          Zoom OAuth access and refresh tokens are encrypted before being
          stored and are used only by the backend application to communicate
          with Zoom on behalf of the authorized user.
        </p>

        <h2>Audio and transcripts</h2>
        <p>
          Meeting audio or uploaded audio may be processed by transcription
          services in order to generate transcripts. Session information and
          generated transcripts may be stored so users can review and export
          their transcription results.
        </p>

        <h2>Third-party services</h2>
        <p>
          The application may use services including Zoom, Papa Reo, Render,
          and Vercel to provide authentication, transcription, hosting,
          database, and application functionality.
        </p>

        <h2>Data security</h2>
        <p>
          Reasonable technical measures are used to protect application data.
          Sensitive credentials are stored as protected environment variables,
          Zoom OAuth tokens are encrypted before database storage, and deployed
          application traffic uses HTTPS.
        </p>

        <h2>Data access and deletion</h2>
        <p>
          Users may disconnect their Zoom account from the application.
          Requests relating to access, correction, or deletion of personal
          information can be submitted through the support contact provided
          on the Support page.
        </p>

        <h2>Changes to this policy</h2>
        <p>
          This Privacy Policy may be updated as the application and its
          functionality develop.
        </p>

        <p>
          <strong>Last updated:</strong> October 2026
        </p>
      </div>
    </main>
  );
}
