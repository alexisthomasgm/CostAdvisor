export default function Privacy() {
  return (
    <div className="ca-page ca-fade-in" style={{ maxWidth: 760 }}>
      <div className="ca-h1">Privacy Policy</div>
      <p className="ca-subtitle">Last updated: 2026-04-15</p>

      <div className="ca-card" style={{ fontSize: 13, lineHeight: 1.7 }}>
        <p>
          CostAdvisor is operated by Stamina Chemical Inc. This page explains what we
          collect, where it goes, and how you can get it removed. We are a small team
          running a proof-of-concept, so this is short and literal — not a template.
        </p>

        <h3 style={{ marginTop: 20 }}>What we collect</h3>
        <ul>
          <li><strong>Google account basics</strong>: your email, Google-assigned user ID, display name, and profile picture. Collected through Google OAuth when you sign in.</li>
          <li><strong>What you put in</strong>: products, suppliers, cost models, prices, volumes, index overrides, and team data you or your teammates enter.</li>
          <li><strong>Operational logs</strong>: HTTP request logs (route, status code, timestamp) and an internal audit trail of actions you take on your team's data.</li>
        </ul>

        <h3 style={{ marginTop: 20 }}>Where it lives</h3>
        <p>
          Application and database hosted on Railway (US-East). Cached computations on
          Redis (same Railway project). The LLM that powers the "AI analysis" features runs
          on a private Hetzner server in Germany, reachable only from our application over
          a private network. Encrypted nightly database backups are stored on Backblaze B2.
          No third-party analytics or advertising trackers.
        </p>

        <h3 style={{ marginTop: 20 }}>Who else sees it</h3>
        <p>
          Other members of your team inside CostAdvisor see your team's data. Nobody outside
          your team does — this is enforced at the application layer and also at the database
          layer via row-level security policies. Stamina Chemical staff may access production
          data only to diagnose a specific issue you've reported.
        </p>

        <h3 style={{ marginTop: 20 }}>Deleting your account</h3>
        <p>
          You can delete your account from Settings. If you are the sole member of a team,
          the team and all its data are deleted. If you share the team with others, only your
          membership is removed. Backups are retained for 30 days then permanently deleted.
        </p>

        <h3 style={{ marginTop: 20 }}>Questions</h3>
        <p>
          Email <a href="mailto:alexis@staminachem.com">alexis@staminachem.com</a>.
        </p>
      </div>
    </div>
  );
}
