export type UserRole = "researcher" | "admin" | "developer_admin";

export type CurrentUser = {
  id: string;
  name: string;
  student_id?: string | null;
  email: string;
  role: UserRole;
  department?: string | null;
  auth_provider: string;
  is_active: boolean;
  researcher_id?: string | null;
  researcher_name?: string | null;
  created_at: string;
  updated_at: string;
};

export type LoginPayload = {
  identifier: string;
  password: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: CurrentUser;
};
