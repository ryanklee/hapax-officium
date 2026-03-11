// Types matching cockpit/data/ Python dataclasses

export interface Nudge {
  category: string;
  priority_score: number;
  priority_label: "critical" | "high" | "medium" | "low";
  title: string;
  detail: string;
  suggested_action: string;
  command_hint: string;
  source_id: string;
}

export interface BriefingData {
  headline: string;
  generated_at: string;
  body: string;
  action_items: ActionItem[];
}

export interface ActionItem {
  priority: string;
  action: string;
  reason: string;
  command: string;
}

export interface GoalSnapshot {
  goals: GoalStatus[];
  active_count: number;
  stale_count: number;
  primary_stale: string[];
}

export interface GoalStatus {
  id: string;
  name: string;
  status: string;
  category: string;
  last_activity_h: number | null;
  stale: boolean;
  progress_summary: string;
  description: string;
}

export interface AgentInfo {
  name: string;
  uses_llm: boolean;
  description: string;
  command: string;
  module: string;
  flags: AgentFlag[];
}

export interface AgentFlag {
  flag: string;
  description: string;
  flag_type: string;
  default: string | null;
  choices: string[] | null;
  metavar: string | null;
}

// --- Management ---

export interface PersonState {
  name: string;
  team: string;
  role: string;
  cadence: string;
  status: string;
  cognitive_load: number | null;
  growth_vector: string;
  feedback_style: string;
  last_1on1: string;
  coaching_active: boolean;
  stale_1on1: boolean;
  days_since_1on1: number | null;
}

export interface CoachingState {
  title: string;
  person: string;
  status: string;
  check_in_by: string;
  overdue: boolean;
  days_overdue: number;
}

export interface FeedbackState {
  title: string;
  person: string;
  direction: string;
  category: string;
  follow_up_by: string;
  followed_up: boolean;
  overdue: boolean;
  days_overdue: number;
}

export interface ManagementSnapshot {
  people: PersonState[];
  coaching: CoachingState[];
  feedback: FeedbackState[];
}

// --- Agent Run ---

export interface AgentRunStatus {
  running: boolean;
  agent_name?: string;
  pid?: number;
  elapsed_s?: number;
}

export interface NudgeActionResponse {
  status: string;
  source_id: string;
  action: string;
}

// --- Cycle Mode ---

export interface CycleModeResponse {
  mode: "dev" | "prod";
  switched_at: string | null;
}

// --- Scout Decisions ---

export interface ScoutDecision {
  component: string;
  decision: "adopted" | "deferred" | "dismissed";
  notes: string;
  timestamp: string;
}

export interface ScoutDecisionsResponse {
  decisions: ScoutDecision[];
}

// --- Demos ---

export interface Demo {
  id: string;
  title: string;
  audience: string;
  scope: string;
  scenes: number;
  format: string;
  duration: number;
  timestamp: string;
  primary_file: string;
  files: string[];
  dir: string;
  has_video?: boolean;
  has_audio?: boolean;
}

// --- Tier 1 Expansion ---

export interface KeyResultState {
  id: string;
  description: string;
  target: number;
  current: number;
  unit: string;
  direction: string;
  confidence: number | null;
  last_updated: string;
  stale: boolean;
}

export interface OKRState {
  objective: string;
  scope: string;
  team: string;
  person: string;
  quarter: string;
  status: string;
  key_results: KeyResultState[];
  score: number | null;
  scored_at: string;
  at_risk_count: number;
  stale_kr_count: number;
}

export interface OKRSnapshot {
  okrs: OKRState[];
  active_count: number;
  at_risk_count: number;
  stale_kr_count: number;
}

export interface SmartGoalState {
  person: string;
  specific: string;
  status: string;
  framework: string;
  category: string;
  created: string;
  target_date: string;
  last_reviewed: string;
  review_cadence: string;
  linked_okr: string;
  measurable: string;
  achievable: string;
  relevant: string;
  time_bound: string;
  days_until_due: number | null;
  overdue: boolean;
  review_overdue: boolean;
  days_since_review: number | null;
}

export interface SmartGoalSnapshot {
  goals: SmartGoalState[];
  active_count: number;
  overdue_count: number;
  review_overdue_count: number;
}

export interface IncidentState {
  title: string;
  severity: string;
  status: string;
  detected: string;
  mitigated: string;
  duration_minutes: number | null;
  impact: string;
  root_cause: string;
  owner: string;
  teams_affected: string[];
  open: boolean;
  has_postmortem: boolean;
}

export interface IncidentSnapshot {
  incidents: IncidentState[];
  open_count: number;
  missing_postmortem_count: number;
}

export interface PostmortemActionState {
  title: string;
  incident_ref: string;
  owner: string;
  status: string;
  priority: string;
  due_date: string;
  completed_date: string;
  overdue: boolean;
  days_overdue: number;
}

export interface PostmortemActionSnapshot {
  actions: PostmortemActionState[];
  open_count: number;
  overdue_count: number;
}

export interface ReviewCycleState {
  person: string;
  cycle: string;
  status: string;
  self_assessment_due: string;
  self_assessment_received: boolean;
  peer_feedback_requested: number;
  peer_feedback_received: number;
  review_due: string;
  calibration_date: string;
  delivered: boolean;
  days_until_review_due: number | null;
  peer_feedback_gap: number;
  overdue: boolean;
}

export interface ReviewCycleSnapshot {
  cycles: ReviewCycleState[];
  active_count: number;
  overdue_count: number;
  peer_feedback_gap_total: number;
}

export interface StatusReportState {
  date: string;
  cadence: string;
  direction: string;
  generated: boolean;
  edited: boolean;
  days_since: number | null;
  stale: boolean;
}

export interface StatusReportSnapshot {
  reports: StatusReportState[];
  latest_date: string;
  stale: boolean;
}
