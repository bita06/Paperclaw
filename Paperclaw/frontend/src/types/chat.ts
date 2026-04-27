export type ResearchQaMode =
  | "concept_positioning"
  | "literature_review"
  | "mechanism_analysis"
  | "research_design";

export type AgentEvidenceSource = "builtin_library" | "user_upload" | "web_of_science" | "web_search";

export type BuiltinCollectionOption = {
  collection_slug: string;
  label: string;
};

export type AgentLocalEvidenceItem = {
  paper_id: string;
  title: string;
  authors: string[];
  year?: number | null;
  section_title?: string | null;
  quote_or_summary: string;
  source: "builtin_library" | "user_upload";
  source_label: string;
  collection_slug?: string | null;
};

export type AgentExternalEvidenceItem = {
  title: string;
  authors: string[];
  year?: number | null;
  published_date?: string | null;
  source: AgentEvidenceSource;
  source_label: string;
  source_name?: string | null;
  doi?: string | null;
  times_cited?: number | null;
  external_url?: string | null;
  quote_or_summary: string;
};

export type AgentSourceStatus = {
  local: string;
  wos: string;
  web: string;
  messages: string[];
};

export type AgentQueryPayload = {
  question: string;
  mode: ResearchQaMode;
  researcher_id?: string;
  advisor_id?: string;
  include_builtin_library?: boolean;
  include_web?: boolean;
  include_wos?: boolean;
  collection_slug?: string;
  top_k?: number;
};

export type AgentQueryResponse = {
  mode: ResearchQaMode;
  answer_title: string;
  direct_answer: string;
  concept_lineage: string[];
  local_evidence: AgentLocalEvidenceItem[];
  wos_evidence: AgentExternalEvidenceItem[];
  web_evidence: AgentExternalEvidenceItem[];
  source_status: AgentSourceStatus;
  next_steps: string[];
  limitations: string[];
};
