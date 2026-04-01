import type { CurrentUser, LoginPayload, TokenResponse } from "../types/auth";
import { apiRequest } from "./client";

export const authApi = {
  login: (payload: LoginPayload) =>
    apiRequest<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  me: () => apiRequest<CurrentUser>("/auth/me"),
  logout: () =>
    apiRequest<{ message: string }>("/auth/logout", {
      method: "POST",
    }),
};
