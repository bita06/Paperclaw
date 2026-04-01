import { apiRequest, buildQueryString } from "./client";
import type {
  Advisor,
  AdvisorDetail,
  AdvisorSubField,
  CreateAdvisorPayload,
  CreateAdvisorSubFieldPayload,
  UpdateAdvisorSubFieldPayload,
} from "../types/advisor";
import type { AdvisorLibraryPaper } from "../types/paper";

export const advisorsApi = {
  list: () => apiRequest<Advisor[]>("/advisors"),
  create: (payload: CreateAdvisorPayload) =>
    apiRequest<Advisor>("/advisors", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  remove: (advisorId: string) =>
    apiRequest<void>(`/advisors/${advisorId}`, {
      method: "DELETE",
    }),
  getDetail: (advisorId: string) => apiRequest<AdvisorDetail>(`/advisors/${advisorId}`),
  createSubField: (advisorId: string, payload: CreateAdvisorSubFieldPayload) =>
    apiRequest<AdvisorSubField>(`/advisors/${advisorId}/sub-fields`, {
      method: "POST",
      body: JSON.stringify({ advisor_id: advisorId, ...payload }),
    }),
  updateSubField: (subFieldId: string, payload: UpdateAdvisorSubFieldPayload) =>
    apiRequest<AdvisorSubField>(`/advisors/sub-fields/${subFieldId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  removeSubField: (subFieldId: string) =>
    apiRequest<void>(`/advisors/sub-fields/${subFieldId}`, {
      method: "DELETE",
    }),
  listSubFields: (advisorId: string) => apiRequest<AdvisorSubField[]>(`/advisors/${advisorId}/sub-fields`),
  listPapers: (advisorId: string, params?: { subFieldId?: string; tag?: string; researcherId?: string }) => {
    const suffix = buildQueryString({
      sub_field_id: params?.subFieldId,
      tag: params?.tag,
      researcher_id: params?.researcherId,
    });
    return apiRequest<AdvisorLibraryPaper[]>(`/advisors/${advisorId}/papers${suffix}`);
  },
};
