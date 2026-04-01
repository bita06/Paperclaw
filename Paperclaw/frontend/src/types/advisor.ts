export type Advisor = {
  id: string;
  name: string;
  email: string;
  affiliation?: string | null;
  research_areas: string[];
  bio?: string | null;
  created_at: string;
  updated_at: string;
};

export type AdvisorSubField = {
  id: string;
  advisor_id: string;
  field_name: string;
  description?: string | null;
  display_order: number;
  created_at: string;
  updated_at: string;
};

export type AdvisorDetail = Advisor & {
  sub_fields: AdvisorSubField[];
};

export type CreateAdvisorPayload = {
  name: string;
  email: string;
  affiliation?: string;
  research_areas: string[];
  bio?: string;
};

export type CreateAdvisorSubFieldPayload = {
  field_name: string;
  description?: string;
  display_order?: number;
};

export type UpdateAdvisorSubFieldPayload = {
  field_name?: string;
  description?: string;
  display_order?: number;
};
