export type BackendTaskStatus = "queued" | "processing" | "success" | "error";
export type BackendFileStatus = "uploaded" | "processing" | "ready" | "error";

export type FileUploadAcceptedResponse = {
  file_id: string;
  task_id: string;
  status: "uploaded";
};

export type TaskResult = {
  file_id?: string | null;
  paper_id?: string | null;
  metadata: Record<string, unknown>;
  sections_count: number;
  section_titles: string[];
};

export type TaskResponse = {
  id: string;
  task_type: string;
  status: BackendTaskStatus;
  file_id?: string | null;
  created_by: string;
  result: TaskResult;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
};

export type FileStatusResponse = {
  file_id: string;
  file_status: BackendFileStatus;
  latest_task?: TaskResponse | null;
  linked_paper_id?: string | null;
  knowledge_status: KnowledgeStatusSummary;
};

export type KnowledgeStatusSummary = {
  uploaded: boolean;
  parsing: boolean;
  parse_success: boolean;
  parse_error: boolean;
  paper_generated: boolean;
  researcher_context_bound: boolean;
  in_researcher_knowledge_base: boolean;
  awaiting_knowledge_base_entry: boolean;
  agent_ready: boolean;
  summary_text: string;
};

export type FileHistoryItem = {
  file_id: string;
  original_name: string;
  content_type?: string | null;
  size_bytes: number;
  file_status: BackendFileStatus;
  researcher_id?: string | null;
  linked_paper_id?: string | null;
  created_at: string;
  updated_at: string;
  latest_task?: TaskResponse | null;
  knowledge_status: KnowledgeStatusSummary;
};
