import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import {
  compareSaved, getFixtures, getSaved, investigate, listSaved, runFixture,
} from "./api";
import type {
  ClaimState, FixtureInfo, InvestigationReport, SavedInvestigation,
} from "./api";

const STATE_ORDER: ClaimState[] = [
  "VERIFIED", "SUPPORTED", "CONTRADICTED", "UNVERIFIED", "NOT_DETERMINABLE",
];

type Mode = "local" | "github" | "demo";
type Section = "timeline" | "evidence" | "contradictions" | "hypotheses" | "plan" | "graph" | "health";

const SECTIONS: { key: Section; label: string }[] = [
  { key: "timeline", label: "Timeline" },
  { key: "evidence", label: "Evidence" },
  { key: "contradictions", label: "Contradictions" },
  { key: "hypotheses", label: "Hypotheses" },
  { key: "plan", label: "Resurrection" },
  { key: "graph", label: "Graph" },
  { key: "health", label: "Health" },
];

export default function App() {
  const [mode, setMode] = useState<Mode>("local");
  const [source, setSource] = useState("");
  const [snapshot, setSnapshot] = useState("head");
  const [report, setReport] = useState<InvestigationReport | null>(null);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [section, setSection] = useState<Section>("timeline");
  const [fixtures, setFixtures] = useState<FixtureInfo[]>([]);
  const [saved, setSaved] = useState<SavedInvestigation[]>([]);
  const [selectedClaim, setSelectedClaim] = useState<string>("");
  const [graphQuery, setGraphQuery] = useState("");
  const [graphRelation, setGraphRelation] = useState("");
  const [graphSubsystem, setGraphSubsystem] = useState("");
  const [graphState, setGraphState] = useState("");
  const [focusMode, setFocusMode] = useState(false);
  const [selectedNode, setSelectedNode] = useState<string>("");
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [compareResult, setCompareResult] = useState<string>("");

  const counts = useMemo(() => {
    const map = new Map<string, number>();
    report?.claims.forEach((claim) =>
      map.set(claim.state, (map.get(claim.state) ?? 0) + 1));
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

  async function refreshSaved() {
    try {
      setSaved((await listSaved()).investigations);
    } catch {
      setSaved([]);
    }
  }

  useEffect(() => {
    getFixtures().then((data) => setFixtures(data.fixtures)).catch(() => setFixtures([]));
    refreshSaved();
  }, []);

  function accept(next: InvestigationReport, note: string) {
    setReport(next);
    setStatus(note);
    setSelectedClaim(next.claims[0]?.id ?? "");
    setSection("timeline");
    refreshSaved();
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setStatus(mode === "github" ? "Acquiring bounded clone..." : "Excavating read-only...");
    try {
      const result = await investigate(source.trim(), snapshot);
      accept(result, `Investigation sealed: ${result.seal.slice(0, 12)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Investigation failed");
      setStatus("");
    } finally {
      setLoading(false);
    }
  }

  async function onFixture(key: string) {
    setLoading(true);
    setError("");
    try {
      accept(await runFixture(key), "Synthetic demonstration loaded. Evidence is labeled synthetic.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fixture failed");
    } finally {
      setLoading(false);
    }
  }

  async function onReopen(id: string) {
    setLoading(true);
    setError("");
    try {
      accept(await getSaved(id), "Stored investigation reopened without rewriting its evidence.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reopen failed");
    } finally {
      setLoading(false);
    }
  }

  async function onCompare() {
    if (compareIds.length !== 2) return;
    try {
      const diff = await compareSaved(compareIds[0], compareIds[1]);
      setCompareResult(
        `${diff.changed_claims.length} changed, ${diff.added_claims.length} added, ` +
        `${diff.removed_claims.length} removed claims`);
    } catch (err) {
      setCompareResult(err instanceof Error ? err.message : "Compare failed");
    }
  }

  const claim = report?.claims.find((item) => item.id === selectedClaim) ?? null;
  const claimLinks = report?.links.filter((link) => link.claim_id === selectedClaim) ?? [];
  const nodeById = new Map((report?.graph.nodes ?? []).map((node) => [node.id, node]));
  const focusNeighbours = useMemo(() => {
    const neighbours = new Set<string>();
    if (!report || !selectedNode) return neighbours;
    neighbours.add(selectedNode);
    (report.graph.focus[selectedNode] ?? []).forEach((id) => neighbours.add(id));
    report.graph.edges.forEach((edge) => {
      if (edge.source === selectedNode) neighbours.add(edge.target);
      if (edge.target === selectedNode) neighbours.add(edge.source);
    });
    return neighbours;
  }, [report, selectedNode]);
  const graphNodes = (report?.graph.nodes ?? []).filter((node) => {
    if (!node.label.toLowerCase().includes(graphQuery.toLowerCase())) return false;
    if (graphState && node.kind === "claim" && node.state !== graphState) return false;
    if (graphSubsystem && node.kind === "file"
      && !(report?.graph.clusters.files_by_subsystem[graphSubsystem] ?? []).includes(node.id)) {
      return false;
    }
    if (focusMode && selectedNode && !focusNeighbours.has(node.id)) return false;
    return true;
  });
  const visibleNodeIds = new Set(graphNodes.map((node) => node.id));
  const graphEdges = (report?.graph.edges ?? []).filter((edge) =>
    (!graphRelation || edge.relation === graphRelation)
    && visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target));
  const confirmedCount = report?.contradictions.filter(
    (item) => item.qualification === "CONFIRMED").length ?? 0;
  const potentialCount = report?.contradictions.filter(
    (item) => item.qualification === "POTENTIAL").length ?? 0;
  const planGroups = useMemo(() => {
    const groups = new Map<string, InvestigationReport["resurrection_plan"]>();
    report?.resurrection_plan.forEach((action) => {
      const list = groups.get(action.group) ?? [];
      list.push(action);
      groups.set(action.group, list);
    });
    return [...groups.entries()];
  }, [report]);

  function exportJson() {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `necromancer-${report.head.slice(0, 8)}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="page">
      <header className="masthead">
        <h1>NECROMANCER</h1>
        <p className="tagline">Resurrect the investigation. Not the assumptions.</p>
      </header>

      <section className="launcher" aria-label="Investigation launcher">
        <div className="mode-tabs" role="tablist" aria-label="Investigation source">
          <button type="button" role="tab" aria-selected={mode === "local"}
            onClick={() => setMode("local")}>Local repository</button>
          <button type="button" role="tab" aria-selected={mode === "github"}
            onClick={() => setMode("github")}>Public GitHub URL</button>
          <button type="button" role="tab" aria-selected={mode === "demo"}
            onClick={() => setMode("demo")}>Demonstration</button>
        </div>

        {mode !== "demo" ? (
          <form onSubmit={onSubmit}>
            <label htmlFor="source-input">
              {mode === "local" ? "Local repository path" : "GitHub repository URL (https only)"}
            </label>
            <div className="excavate-row">
              <input id="source-input" value={source}
                onChange={(event) => setSource(event.target.value)}
                placeholder={mode === "local" ? "/path/to/repository" : "https://github.com/owner/repo"}
                required />
              <select aria-label="Snapshot scope" value={snapshot}
                onChange={(event) => setSnapshot(event.target.value)}>
                <option value="head">Snapshot: HEAD</option>
                <option value="worktree">Snapshot: worktree</option>
              </select>
              <button type="submit" disabled={loading}>
                {loading ? "Working..." : "Investigate"}
              </button>
            </div>
            <p className="hint">
              Read-only excavation. GitHub acquisition is a bounded clone with no
              checkout, no submodules and no credentials.
            </p>
          </form>
        ) : (
          <div>
            <p>Reproducible synthetic histories. Always labeled synthetic.</p>
            <div className="fixture-row">
              {fixtures.map((fixture) => (
                <button key={fixture.key} type="button" disabled={loading}
                  onClick={() => onFixture(fixture.key)}>{fixture.label}</button>
              ))}
            </div>
          </div>
        )}
        {status ? <p className="status-line" role="status">{status}</p> : null}
        {error ? (
          <p className="notice notice-error" role="alert">
            <strong>WARN, investigation did not complete.</strong> {error}
          </p>
        ) : null}
      </section>

      <section className="saved" aria-label="Recent investigations">
        <h2>Recent investigations</h2>
        {saved.length === 0 ? <p>No stored investigations yet.</p> : (
          <>
            <ul>
              {saved.slice(0, 8).map((item) => (
                <li key={item.id}>
                  <input type="checkbox" aria-label={`Select ${item.repo_path} for comparison`}
                    checked={compareIds.includes(item.id)}
                    onChange={(event) => setCompareIds((prev) =>
                      event.target.checked ? [...prev, item.id].slice(-2)
                        : prev.filter((id) => id !== item.id))} />
                  <button type="button" onClick={() => onReopen(item.id)}>
                    {item.source_kind}: {item.repo_path} at {item.head.slice(0, 8)}
                  </button>
                  <span className="mono"> {item.created_at.slice(0, 19)}</span>
                </li>
              ))}
            </ul>
            <button type="button" onClick={onCompare} disabled={compareIds.length !== 2}>
              Compare selected snapshots
            </button>
            {compareResult ? <p role="status">{compareResult}</p> : null}
          </>
        )}
      </section>

      {!report ? (
        <section className="notice">
          Investigate a local repository, acquire a public GitHub URL, or open a
          synthetic demonstration. Findings always stay separated by epistemic
          level; nothing is collapsed into one confidence score.
        </section>
      ) : (
        <main>
          {report.source_kind === "synthetic" ? (
            <p className="notice" role="note">
              SYNTHETIC DEMONSTRATION. This evidence was generated on purpose and
              is not a real repository.
            </p>
          ) : null}
          <section className="summary" aria-label="Investigation overview">
            <div>
              <h2>Investigation overview</h2>
              <p className="mono">{report.repo_path}</p>
              <p className="mono">
                HEAD {report.head.slice(0, 12)} · snapshot {report.snapshot} ·
                source {report.source_kind}
                {report.workspace_status ? ` · workspace ${report.workspace_status}` : ""}
              </p>
              <p className="mono">Seal {report.seal.slice(0, 16)}...</p>
              <p>Health: {report.health.category}. {report.health.category_evidence.join(" ")}</p>
            </div>
            <ul className="level-counts">
              {STATE_ORDER.map((state) => (
                <li key={state}>
                  <span className={`badge badge-${state.toLowerCase()}`}>{state}</span>
                  <strong>{counts.get(state) ?? 0}</strong>
                </li>
              ))}
            </ul>
          </section>
          {report.warnings.map((warning) => (
            <p key={warning} className="notice">WARN: {warning}</p>
          ))}

          <ol className="workflow" aria-label="Analyst workflow">
            <li className="done"><strong>1. Discover</strong>
              <span>Sealed investigation at {report.head.slice(0, 8)}</span></li>
            <li className={potentialCount ? "attention" : "done"}>
              <strong>2. Qualify</strong>
              <span>{confirmedCount} confirmed, {potentialCount} potential conflicts need review</span></li>
            <li className={claim ? "done" : ""}><strong>3. Investigate</strong>
              <span>{claim ? "Claim selected in Evidence" : "Select a claim in Evidence"}</span></li>
            <li className={compareResult ? "done" : ""}><strong>4. Compare</strong>
              <span>{compareResult || "Select two saved investigations above"}</span></li>
            <li><strong>5. Decide</strong>
              <span>{report.resurrection_plan.length} grouped proposals, none executed</span></li>
            <li><strong>6. Export</strong>
              <span><button type="button" onClick={exportJson}>Download JSON</button>
                {" "}Markdown: <code>necromancer excavate</code></span></li>
          </ol>

          <nav className="section-nav" aria-label="Investigation sections">
            {SECTIONS.map((item) => (
              <button key={item.key} type="button"
                aria-current={section === item.key}
                onClick={() => setSection(item.key)}>{item.label}</button>
            ))}
          </nav>

          {section === "timeline" ? (
            <section><h2>Historical timeline</h2>
              <p>Times are recorded Git author dates, one clock domain. Order
                shows adjacency, never causation by itself. A silent interval
                means no event was recorded, not that nothing happened.</p>
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
          ) : null}

          {section === "evidence" ? (
            <section><h2>Evidence explorer</h2>
              <div className="explorer">
                <ul className="claim-index">
                  {report.claims.map((item) => (
                    <li key={item.id}>
                      <button type="button" onClick={() => setSelectedClaim(item.id)}>
                        <span className={`badge badge-${item.state.toLowerCase()}`}>{item.state}</span>
                        {" "}{item.text.slice(0, 90)}
                      </button>
                    </li>
                  ))}
                </ul>
                {claim ? (
                  <article className="claim-card">
                    <blockquote>{claim.text}</blockquote>
                    <dl>
                      <div><dt>Origin</dt><dd className="mono">{claim.origin}
                        {claim.line ? ` (line ${claim.line})` : ""}</dd></div>
                      <div><dt>Extraction</dt><dd className="mono">{claim.extraction}</dd></div>
                      <div><dt>Modality</dt><dd>{claim.modality}
                        {claim.subject_tokens.length
                          ? ` · subject: ${claim.subject_tokens.join(", ")}` : ""}</dd></div>
                      <div><dt>Why</dt><dd>{claim.rationale}</dd></div>
                      <div><dt>Scope</dt><dd>{claim.scope}</dd></div>
                      <div><dt>Would reopen</dt><dd>{claim.falsifier}</dd></div>
                    </dl>
                    <h3>Linked evidence</h3>
                    <ul>{claimLinks.map((link) => (
                      <li key={`${link.evidence_ref}-${link.relation}`} className="mono">
                        {link.relation} -&gt; {link.evidence_ref}: {link.rationale}
                        {" "}[binding {link.binding_score} via {link.match_basis || "tokens"};{" "}
                        {link.binding_meaning}]
                      </li>))}
                    </ul>
                  </article>
                ) : <p>Select a claim to inspect its source.</p>}
              </div>
            </section>
          ) : null}

          {section === "contradictions" ? (
            <section><h2>Contradiction explorer</h2>
              <p>CONFIRMED means a defensible incompatibility in the same subject,
                scope and time. POTENTIAL is a conflict requiring human review; it
                changes no claim state. Absence from this list is not proof that
                no contradiction exists.</p>
              {report.contradictions.length === 0 ? (
                <p>None detected by the deterministic rules. This is not proof that none exist.</p>
              ) : (["CONFIRMED", "POTENTIAL"] as const).map((qualification) => {
                const items = report.contradictions.filter(
                  (item) => item.qualification === qualification);
                if (!items.length) return null;
                return (
                  <div key={qualification}>
                    <h3>{qualification} ({items.length})</h3>
                    {items.map((item) => {
                      const linked = report.claims.find((entry) => entry.id === item.claim_id);
                      return (
                        <div key={item.id} className="versus">
                          <div><h4>Claim</h4><p>{linked?.text ?? item.claim_id}</p>
                            <p className="mono">{linked?.origin}
                              {linked ? ` · modality ${linked.modality} · state ${linked.state}` : ""}</p></div>
                          <div><h4>Contradicting evidence</h4><p>{item.detail}</p>
                            <p className="mono">{item.evidence_ref} [{item.kind} · {item.qualification}]</p></div>
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </section>
          ) : null}

          {section === "hypotheses" ? (
            <section><h2>Hypothesis laboratory, not findings</h2>
              {hypothesisGroups.map(([group, items]) => (
                <div key={group} className="hyp-group">
                  <h3>{items[0]?.question}</h3>
                  <ul>{items.map((hyp) => (
                    <li key={hyp.id}><strong>({hyp.confidence})</strong> {hyp.statement}
                      <br /><span className="discriminate">
                        Discriminate by: {hyp.discriminators.join("; ")}</span></li>
                  ))}</ul>
                </div>
              ))}
              <div className="hyp-group unknown">
                <h3>UNKNOWN</h3>
                <p>The available evidence does not discriminate between the
                  explanations above. That is a finding about the evidence,
                  not a failure to pick a story.</p>
              </div>
            </section>
          ) : null}

          {section === "plan" ? (
            <section><h2>Resurrection planner</h2>
              <p>Proposals only, grouped by root cause and shared evidence.
                Nothing here executes against the repository.</p>
              {planGroups.map(([group, actions]) => (
                <div key={group} className="plan-group">
                  <h3 className="mono">{group} ({actions.length})</h3>
                  <ol className="plan">
                    {actions.map((action) => (
                      <li key={action.id}>
                        <span className="priority">P{action.priority}</span>
                        <strong>{action.title}</strong>
                        <p>{action.rationale}</p>
                        <p>Claims: <span className="mono">{action.claim_ids.join(", ") || "none"}</span></p>
                        <p>Prerequisites: {action.prerequisites}</p>
                        <p>Risk: {action.risk}</p>
                        <p>Expected effect: {action.expected_effect}</p>
                        <p className="mono">{action.suggested_check}</p>
                      </li>
                    ))}
                  </ol>
                </div>
              ))}
            </section>
          ) : null}

          {section === "graph" ? (
            <section><h2>Evidence graph</h2>
              <p>{report.graph.note}</p>
              <div className="graph-tools">
                <input aria-label="Search graph nodes" value={graphQuery}
                  onChange={(event) => setGraphQuery(event.target.value)}
                  placeholder="Search nodes" />
                <select aria-label="Filter by relationship" value={graphRelation}
                  onChange={(event) => setGraphRelation(event.target.value)}>
                  <option value="">All relationships</option>
                  {report.graph.relationships.map((rel) => (
                    <option key={rel} value={rel}>{rel}</option>))}
                </select>
                <select aria-label="Filter files by subsystem" value={graphSubsystem}
                  onChange={(event) => setGraphSubsystem(event.target.value)}>
                  <option value="">All subsystems</option>
                  {Object.keys(report.graph.clusters.files_by_subsystem).map((name) => (
                    <option key={name} value={name}>{name}</option>))}
                </select>
                <select aria-label="Filter claims by state" value={graphState}
                  onChange={(event) => setGraphState(event.target.value)}>
                  <option value="">All claim states</option>
                  {STATE_ORDER.map((state) => (
                    <option key={state} value={state}>{state}</option>))}
                </select>
                <label>
                  <input type="checkbox" checked={focusMode}
                    onChange={(event) => setFocusMode(event.target.checked)} />
                  {" "}Focus on selected node
                </label>
              </div>
              <p>
                Showing {graphNodes.length} of {report.graph.nodes.length} nodes
                and {graphEdges.length} of {report.graph.edges.length} edges.
                Clusters: {Object.entries(report.graph.clusters.by_kind)
                  .map(([kind, ids]) => `${kind} ${ids.length}`).join(" · ")}.
              </p>
              {report.graph.fanout.length ? (
                <div className="notice" role="note">
                  <strong>Shared-evidence fan-out.</strong>
                  <ul>{report.graph.fanout.slice(0, 5).map((entry) => (
                    <li key={entry.node} className="mono">
                      {entry.node} (degree {entry.degree}): {entry.warning}</li>
                  ))}</ul>
                </div>
              ) : null}
              <svg className="graph-svg" viewBox="0 0 960 420" role="img"
                aria-label="Evidence graph projection">
                {graphEdges.slice(0, 120).map((edge, index) => {
                  const kinds = ["claim", "commit", "file", "evidence", "hypothesis", "action", "branch", "tag", "event", "contradiction"];
                  const pos = (id: string) => {
                    const node = nodeById.get(id);
                    const siblings = graphNodes.filter((n) => n.kind === node?.kind);
                    const at = Math.max(0, siblings.findIndex((n) => n.id === id));
                    return {
                      x: 70 + kinds.indexOf(node?.kind ?? "file") * 95,
                      y: 30 + at * 26,
                    };
                  };
                  const a = pos(edge.source);
                  const b = pos(edge.target);
                  return <line key={index} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                    className={edge.speculative ? "edge-spec" : "edge"} />;
                })}
                {graphNodes.slice(0, 90).map((node) => {
                  const kinds = ["claim", "commit", "file", "evidence", "hypothesis", "action", "branch", "tag", "event", "contradiction"];
                  const siblings = graphNodes.filter((n) => n.kind === node.kind);
                  const at = siblings.findIndex((n) => n.id === node.id);
                  const x = 70 + kinds.indexOf(node.kind) * 95;
                  const y = 30 + at * 26;
                  return (
                    <g key={node.id} onClick={() => setSelectedNode(node.id)}
                      className="graph-node" tabIndex={0} role="button"
                      aria-label={`${node.kind}: ${node.label}`}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") setSelectedNode(node.id);
                      }}>
                      <circle cx={x} cy={y} r={5} />
                      <text x={x + 8} y={y + 4}>{node.label.slice(0, 22)}</text>
                    </g>
                  );
                })}
              </svg>
              {selectedNode && nodeById.get(selectedNode) ? (
                <p className="mono" role="status">
                  {nodeById.get(selectedNode)?.kind}: {nodeById.get(selectedNode)?.label}
                  {" · "}{selectedNode}
                </p>
              ) : null}
              <h3>Readable alternative (edge list)</h3>
              <ul className="edges">
                {graphEdges.slice(0, 80).map((edge, index) => (
                  <li key={index} className="mono">
                    {edge.source} --[{edge.relation}{edge.speculative ? ", speculative" : ""}]--&gt; {edge.target}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {section === "health" ? (
            <section><h2>Repository health indicators</h2>
              <dl className="health-grid">
                <div><dt>Category</dt><dd>{report.health.category}</dd></div>
                <div><dt>Last commit</dt><dd>{report.health.last_commit || "unknown"}</dd></div>
                <div><dt>Commits</dt><dd>{report.health.commit_count}</dd></div>
                <div><dt>Unmerged branches</dt>
                  <dd>{report.health.unmerged_branches.join(", ") || "none"}</dd></div>
                <div><dt>TODO/FIXME</dt><dd>{report.health.todo_fixme_references}</dd></div>
                <div><dt>Test files</dt><dd>{report.health.test_files}</dd></div>
                <div><dt>CI config</dt><dd>{report.health.ci_config_present ? "present" : "not found"}</dd></div>
                <div><dt>Tags</dt><dd>{report.health.tags.join(", ") || "none"}</dd></div>
              </dl>
              <p>{report.health.note}</p>
            </section>
          ) : null}
        </main>
      )}
    </div>
  );
}

