import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import { excavate } from "./api";
import type { ClaimState, InvestigationReport } from "./api";

const STATE_ORDER: ClaimState[] = [
  "VERIFIED",
  "SUPPORTED",
  "CONTRADICTED",
  "UNVERIFIED",
  "NOT_DETERMINABLE",
];

function downloadJson(report: InvestigationReport) {
  const blob = new Blob([JSON.stringify(report, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "necromancer-report.json";
  anchor.click();
  URL.revokeObjectURL(url);
}

export default function App() {
  const [path, setPath] = useState("");
  const [report, setReport] = useState<InvestigationReport | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const counts = useMemo(() => {
    const map = new Map<string, number>();
    report?.claims.forEach((claim) =>
      map.set(claim.state, (map.get(claim.state) ?? 0) + 1),
    );
    return map;
  }, [report]);

  const hypothesisGroups = useMemo(() => {
    const groups = new Map<string, InvestigationReport["hypotheses_not_facts"]>();
    report?.hypotheses_not_facts.forEach((hyp) => {
      const list = groups.get(hyp.group) ?? [];
      list.push(hyp);
      groups.set(hyp.group, list);
    });
    return [...groups.entries()];
  }, [report]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      setReport(await excavate(path.trim()));
    } catch (err) {
      setReport(null);
      setError(err instanceof Error ? err.message : "Excavation failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <header className="masthead">
        <h1>NECROMANCER</h1>
        <p className="tagline">Resurrect the investigation. Not the assumptions.</p>
      </header>

      <form className="excavate-bar" onSubmit={onSubmit}>
        <label htmlFor="repo-path">Local repository path</label>
        <div className="excavate-row">
          <input
            id="repo-path"
            value={path}
            onChange={(event) => setPath(event.target.value)}
            placeholder="/path/to/abandoned-repo"
            required
          />
          <button type="submit" disabled={loading}>
            {loading ? "Excavating..." : "Excavate"}
          </button>
        </div>
        <p className="hint">
          Read-only. The target code is never executed. Start the API first:
          uvicorn necromancer.api:app --port 8000
        </p>
      </form>

      {error ? (
        <section className="notice notice-error" role="alert">
          <strong>WARN — excavation did not complete.</strong> {error}
        </section>
      ) : null}

      {!report && !error ? (
        <section className="notice">
          No investigation loaded yet. Counts, when shown, are always broken
          down by epistemic level; they are never collapsed into one number.
        </section>
      ) : null}

      {report ? (
        <main>
          <section className="summary">
            <div>
              <h2>Investigation</h2>
              <p className="mono">{report.repo_path}</p>
              <p className="mono">HEAD {report.head.slice(0, 12)}</p>
              <p className="mono">Seal {report.seal.slice(0, 16)}...</p>
            </div>
            <ul className="level-counts">
              {STATE_ORDER.map((state) => (
                <li key={state}>
                  <span className={`badge badge-${state.toLowerCase()}`}>{state}</span>
                  <strong>{counts.get(state) ?? 0}</strong>
                </li>
              ))}
            </ul>
            <button type="button" onClick={() => downloadJson(report)}>
              Download JSON report
            </button>
          </section>

          {report.warnings.map((warning) => (
            <p key={warning} className="notice">WARN: {warning}</p>
          ))}

          <section>
            <h2>Timeline</h2>
            <ol className="timeline">
              {report.events.map((event) => (
                <li key={event.id}>
                  <span className="mono">{event.ts || "undated"}</span>
                  <span className="event-kind">{event.kind}</span>
                  <span>{event.title}</span>
                  <span className="mono refs">{event.refs.slice(0, 3).join(" · ")}</span>
                </li>
              ))}
            </ol>
          </section>

          <section>
            <h2>Claims</h2>
            <div className="claim-list">
              {report.claims.map((claim) => (
                <article key={claim.id} className="claim-card">
                  <span className={`badge badge-${claim.state.toLowerCase()}`}>
                    {claim.state}
                  </span>
                  <blockquote>{claim.text}</blockquote>
                  <dl>
                    <div><dt>Origin</dt><dd className="mono">{claim.origin}</dd></div>
                    <div><dt>Why</dt><dd>{claim.rationale}</dd></div>
                    <div><dt>Scope</dt><dd>{claim.scope}</dd></div>
                    <div><dt>Would reopen</dt><dd>{claim.falsifier}</dd></div>
                  </dl>
                </article>
              ))}
            </div>
          </section>

          <section>
            <h2>Contradictions</h2>
            {report.contradictions.length === 0 ? (
              <p>
                None detected by the deterministic rules. This is not proof
                that none exist.
              </p>
            ) : (
              <ul className="edges">
                {report.contradictions.map((item) => (
                  <li key={item.id}>
                    <span className="mono">claim {item.claim_id}</span>
                    <span aria-hidden="true"> --[{item.kind}]--&gt; </span>
                    <span className="mono">{item.evidence_ref}</span>
                    <p>{item.detail}</p>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <h2>Hypotheses — not facts</h2>
            <p>
              Competing explanations only. They never upgrade the evidence
              above.
            </p>
            {hypothesisGroups.map(([group, items]) => (
              <div key={group} className="hyp-group">
                <h3>{items[0]?.question}</h3>
                <ul>
                  {items.map((hyp) => (
                    <li key={hyp.id}>
                      <strong>({hyp.confidence})</strong> {hyp.statement}
                      <br />
                      <span className="discriminate">
                        Discriminate by: {hyp.discriminators.join("; ")}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </section>

          <section>
            <h2>Resurrection plan</h2>
            <ol className="plan">
              {report.resurrection_plan.map((action) => (
                <li key={action.id}>
                  <span className="priority">P{action.priority}</span>
                  <strong>{action.title}</strong>
                  <p>{action.rationale}</p>
                  <p className="mono">{action.suggested_check}</p>
                </li>
              ))}
            </ol>
          </section>
        </main>
      ) : null}
    </div>
  );
}
