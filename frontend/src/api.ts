export type ClaimState =
  | "VERIFIED"
  | "SUPPORTED"
  | "CONTRADICTED"
  | "UNVERIFIED"
  | "NOT_DETERMINABLE";

export interface ReportEvent {
  id: string; ts: string; kind: string; title: string; detail: string;
  refs: string[]; provenance: string;
}

export interface Claim {
  id: string; text: string; verb: string; state: ClaimState;
  source_kind: string; source_ref: string; origin: string;
  line: number | null; extraction: string;
  modality: string; subject_tokens: string[];
  scope: string; falsifier: string; rationale: string;
}

export interface EvidenceLink {
  claim_id: string; evidence_ref: string; relation: string; rationale: string;
  binding_score: number; match_basis: string; binding_meaning: string;
}

export interface Contradiction {
  id: string; claim_id: string; evidence_ref: string; kind: string; detail: string;
  qualification: "CONFIRMED" | "POTENTIAL";
}

export interface Hypothesis {
  id: string; group: string; question: string; statement: string;
  discriminators: string[]; confidence: string; provenance: string;
}

export interface PlanAction {
  id: string; priority: number; title: string; rationale: string;
  claim_ids: string[]; reversible: boolean; suggested_check: string;
  risk: string; prerequisites: string; expected_effect: string; group: string;
}

export interface Health {
  category: string; category_evidence: string[]; last_commit: string;
  days_since_last_commit: number | null; commit_count: number;
  unmerged_branches: string[]; todo_fixme_references: number;
  test_files: number; code_files: number; ci_config_present: boolean;
  tags: string[]; note: string;
}

export interface GraphNode {
  id: string; kind: string; label: string;
  state?: string; origin?: string; line?: number | null; provenance?: string;
  [key: string]: unknown;
}

export interface GraphEdge {
  source: string; target: string; relation: string; speculative: boolean;
}

export interface EvidenceGraph {
  nodes: GraphNode[]; edges: GraphEdge[]; relationships: string[]; note: string;
  clusters: {
    by_kind: Record<string, string[]>;
    files_by_subsystem: Record<string, string[]>;
    claims_by_state: Record<string, string[]>;
  };
  fanout: { node: string; degree: number; warning: string }[];
  focus: Record<string, string[]>;
}

export interface InvestigationReport {
  repo_path: string; head: string; snapshot: string;
  source_kind: string; source_ref: string;
  health: Health; graph: EvidenceGraph;
  seal: string; warnings: string[];
  events: ReportEvent[]; claims: Claim[]; links: EvidenceLink[];
  contradictions: Contradiction[];
  hypotheses_not_facts: Hypothesis[];
  resurrection_plan: PlanAction[];
  abandoned_branches: { name: string; tip: string; merged_into_head: boolean }[];
  investigation_id?: string; workspace_status?: string;
}

export interface SavedInvestigation {
  id: string; created_at: string; repo_path: string;
  source_kind: string; head: string; snapshot: string; seal: string;
}

export interface FixtureInfo { key: string; label: string; synthetic: boolean }

const API_BASE =
  (import.meta as { env?: Record<string, string> }).env?.VITE_API_BASE ??
  "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Request failed with HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export function investigate(source: string, snapshot: string): Promise<InvestigationReport> {
  return request<InvestigationReport>("/investigations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source, snapshot, save: true }),
  });
}

export function getFixtures(): Promise<{ fixtures: FixtureInfo[]; note: string }> {
  return request("/fixtures");
}

export function runFixture(key: string): Promise<InvestigationReport> {
  return request(`/fixtures/${key}`, { method: "POST" });
}

export function listSaved(): Promise<{ investigations: SavedInvestigation[] }> {
  return request("/investigations");
}

export function getSaved(id: string): Promise<InvestigationReport> {
  return request(`/investigations/${id}`);
}

export function compareSaved(olderId: string, newerId: string): Promise<{
  changed_claims: { claim_id: string; from: string; to: string; text: string }[];
  added_claims: string[]; removed_claims: string[];
}> {
  return request("/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ older_id: olderId, newer_id: newerId }),
  });
}
