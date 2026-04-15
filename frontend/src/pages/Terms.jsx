export default function Terms() {
  return (
    <div className="ca-page ca-fade-in" style={{ maxWidth: 760 }}>
      <div className="ca-h1">Terms of Service</div>
      <p className="ca-subtitle">Last updated: 2026-04-15</p>

      <div className="ca-card" style={{ fontSize: 13, lineHeight: 1.7 }}>
        <p>
          CostAdvisor is an early-stage product provided by Stamina Chemical Inc. By
          signing in you agree to the terms below. They are written in plain language
          because we'd rather you actually read them.
        </p>

        <h3 style={{ marginTop: 20 }}>The service</h3>
        <p>
          CostAdvisor lets you model the should-cost of chemical products using commodity
          index data, supplier prices, and volumes you provide. The index data we ship with
          is aggregated from publicly available sources. Output is advisory — use it to
          inform negotiations, not as a substitute for your own judgment.
        </p>

        <h3 style={{ marginTop: 20 }}>Your data</h3>
        <p>
          You own everything you upload. You grant us a limited license to store and process
          it solely to operate the service for you and your team. We do not sell or share
          your team's data with third parties. See the <a href="/privacy">Privacy Policy</a>
          {' '}for details.
        </p>

        <h3 style={{ marginTop: 20 }}>Acceptable use</h3>
        <p>
          Don't upload data that isn't yours to share. Don't try to access other teams'
          data, reverse-engineer the service, or use it to build a competing product. Don't
          abuse the API beyond reasonable use — we apply rate limits and may suspend
          accounts that ignore them.
        </p>

        <h3 style={{ marginTop: 20 }}>No warranty</h3>
        <p>
          The service is provided "as is" without any warranty. Stamina Chemical Inc. is not
          liable for business decisions made on the basis of CostAdvisor output, for data
          loss, or for service interruptions. We take backups and test restores, but you
          should keep independent copies of anything critical.
        </p>

        <h3 style={{ marginTop: 20 }}>Changes + termination</h3>
        <p>
          We may change these terms with reasonable notice via email. You may delete your
          account at any time from Settings. We may suspend or terminate accounts that
          violate these terms.
        </p>

        <h3 style={{ marginTop: 20 }}>Contact</h3>
        <p>
          <a href="mailto:alexis@staminachem.com">alexis@staminachem.com</a>.
        </p>
      </div>
    </div>
  );
}
