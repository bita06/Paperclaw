import { apiRequest, buildQueryString } from "./client";
import type { FileHistoryItem, FileStatusResponse, FileUploadAcceptedResponse, TaskResponse } from "../types/fileTask";

export const filesApi = {
  upload: async (file: File, researcherId?: string) => {
    const formData = new FormData();
    formData.append("file", file);
    if (researcherId) {
      formData.append("researcher_id", researcherId);
    }

    return apiRequest<FileUploadAcceptedResponse>("/files/upload", {
      method: "POST",
      body: formData,
    });
  },
  listHistory: (options?: { researcherId?: string; limit?: number }) =>
    apiRequest<FileHistoryItem[]>(
      `/files/history${buildQueryString({
        researcher_id: options?.researcherId,
        limit: options?.limit,
      })}`,
    ),
  getFileStatus: (fileId: string) => apiRequest<FileStatusResponse>(`/files/${fileId}/status`),
  getTask: (taskId: string) => apiRequest<TaskResponse>(`/tasks/${taskId}`),
};
