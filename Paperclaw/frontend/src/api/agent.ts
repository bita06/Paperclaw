import { apiRequest } from "./client";
import type { AgentQueryPayload, AgentQueryResponse, BuiltinCollectionOption } from "../types/chat";

export const agentApi = {
  listBuiltinCollections: () => apiRequest<BuiltinCollectionOption[]>("/agent/builtin-collections"),
  query: (payload: AgentQueryPayload) =>
    apiRequest<AgentQueryResponse>("/agent/query", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
