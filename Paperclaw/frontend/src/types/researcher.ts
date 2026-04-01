export type Researcher = {
  id: string;
  name: string;
  email: string;
  research_group?: string | null;
  academic_level?: string | null;
  bio?: string | null;
  is_active: boolean;
  current_stage?: string | null;
  current_research_question?: string | null;
  created_at: string;
  updated_at: string;
};

export type ResearcherAdvisorLink = {
  advisor_id: string;
  advisor_name: string;
  relationship_type: string;
  access_level: string;
  sub_fields_access: string[];
  joined_at: string;
};

export type CreateResearcherPayload = {
  name: string;
  email: string;
  password: string;
  primary_advisor_id?: string | null;
  research_group?: string;
  academic_level?: string;
  bio?: string;
};

export type UpdateResearchStagePayload = {
  current_stage: string;
  current_research_question?: string;
};

export type CreateRelationshipPayload = {
  advisor_id: string;
  relationship_type: string;
  access_level: string;
  sub_fields_access: string[];
};

export type UpdateRelationshipPayload = {
  relationship_type?: string;
  access_level?: string;
  sub_fields_access?: string[];
};
