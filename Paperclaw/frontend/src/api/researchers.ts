import { apiRequest } from "./client";
import type {
  CreateRelationshipPayload,
  CreateResearcherPayload,
  Researcher,
  ResearcherAdvisorLink,
  UpdateRelationshipPayload,
  UpdateResearchStagePayload,
} from "../types/researcher";

export const researchersApi = {
  list: () => apiRequest<Researcher[]>("/researchers/"),
  create: (payload: CreateResearcherPayload) =>
    apiRequest<Researcher>("/researchers/", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getDetail: (researcherId: string) =>
    apiRequest<Researcher>(`/researchers/${researcherId}`),
  updateStage: (researcherId: string, payload: UpdateResearchStagePayload) =>
    apiRequest<Researcher>(`/researchers/${researcherId}/stage`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  listRelationships: (researcherId: string) =>
    apiRequest<ResearcherAdvisorLink[]>(`/researchers/${researcherId}/advisors`),
  createRelationship: (researcherId: string, payload: CreateRelationshipPayload) =>
    apiRequest<ResearcherAdvisorLink>(`/researchers/${researcherId}/advisors`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getRelationship: (researcherId: string, advisorId: string) =>
    apiRequest<ResearcherAdvisorLink>(`/researchers/${researcherId}/advisors/${advisorId}`),
  updateRelationship: (researcherId: string, advisorId: string, payload: UpdateRelationshipPayload) =>
    apiRequest<ResearcherAdvisorLink>(`/researchers/${researcherId}/advisors/${advisorId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  deleteRelationship: (researcherId: string, advisorId: string) =>
    apiRequest<void>(`/researchers/${researcherId}/advisors/${advisorId}`, {
      method: "DELETE",
    }),
};
