export type ClaimState =
  | "VERIFIED"
  | "SUPPORTED"
  | "CONTRADICTED"
  | "UNVERIFIED"
  | "NOT_DETERMINABLE";

export interface ReportEvent {
  id: string;
  ts: string;
  kind: string;
  title: string;
  detail: string;
  refs: string[];
  provenance: string;
}

export interface Claim {
  id: string;
  text: string;
  verb: string;
  state: ClaimState;
  source_kind: string;
  source_ref: string;
  origin: string;
  scope: string;
  falsifier: string;
  rationale: string;
}

export interface Contradiction {
  id: string;
  claim_id: string;
  evidence_ref: string;
  kind: string;
  detail: string;
}

export interface Hypothesis {
  id: string;
  group: string;
  question: string;
  statement: string;
  discriminators: string[];
  confidence: string;
  provenance: string;
}

export interface PlanAction {
  id: string;
  priority: number;
  title: string;
  rationale: string;
  claim_ids: string[];
  reversible: boolean;
  suggested_check: string;
}

export interface InvestigationReport {
  repo_path: string;
  head: string;
  seal: string;
  warnings: string[];
  events: ReportEvent[];
  claims: Claim[];
  contradictions: Contradiction[];
  hypotheses_not_facts: Hypothesis[];
  resurrection_plan: PlanAction[];
  abandoned_branches: { name: string; tip: string; merged_into_head: boolean }[];
}

const API_BASE = "http://127.0.0.1:8000";

export async function excavate(path: string): Promise<InvestigationReport> {
  const response = await fetch(`${API_BASE}/excavate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Excavation failed with HTTP ${response.status}`);
  }
  return (await response.json()) as InvestigationReport;
}
