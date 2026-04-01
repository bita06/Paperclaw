export type Paper = {
  id: string;
  title: string;
  authors: string[];
  year?: number | null;
  venue?: string | null;
  doi?: string | null;
  abstract?: string | null;
  keywords: string[];
  source: string;
  source_url?: string | null;
  indexed: boolean;
  visibility: string;
  created_at: string;
  updated_at: string;
};

export type AdvisorLibraryPaper = {
  id: string;
  advisor_id: string;
  paper_id: string;
  sub_field_id?: string | null;
  sub_field_name?: string | null;
  library_tags: string[];
  notes?: string | null;
  added_at: string;
  paper: Paper;
};

export type PaperUploadResponse = {
  paper: Paper;
  advisor_links: Array<{
    id: string;
    advisor_id: string;
    paper_id: string;
    sub_field_id?: string | null;
    sub_field_name?: string | null;
    library_tags: string[];
    notes?: string | null;
    added_at: string;
    added_by: string;
  }>;
};
