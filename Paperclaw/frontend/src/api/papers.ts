import { apiRequest } from "./client";
import type { PaperUploadResponse } from "../types/paper";

export type UploadPaperPayload = {
  file: File;
  title?: string;
  authors: string[];
  year?: string;
  venue?: string;
  doi?: string;
  abstract?: string;
  keywords: string[];
  advisorIds: string[];
  subFieldIds: string[];
  libraryTags: string[];
  notes?: string;
  researcherId?: string;
};

export const papersApi = {
  upload: async (payload: UploadPaperPayload) => {
    const formData = new FormData();
    formData.append("file", payload.file);
    if (payload.title) formData.append("title", payload.title);
    if (payload.year) formData.append("year", payload.year);
    if (payload.venue) formData.append("venue", payload.venue);
    if (payload.doi) formData.append("doi", payload.doi);
    if (payload.abstract) formData.append("abstract", payload.abstract);
    if (payload.notes) formData.append("notes", payload.notes);
    if (payload.researcherId) formData.append("researcher_id", payload.researcherId);
    if (payload.authors.length) formData.append("authors", JSON.stringify(payload.authors));
    if (payload.keywords.length) formData.append("keywords", JSON.stringify(payload.keywords));
    if (payload.advisorIds.length) formData.append("advisor_ids", JSON.stringify(payload.advisorIds));
    if (payload.subFieldIds.length) formData.append("sub_field_ids", JSON.stringify(payload.subFieldIds));
    if (payload.libraryTags.length) formData.append("library_tags", JSON.stringify(payload.libraryTags));

    return apiRequest<PaperUploadResponse>("/papers/upload", {
      method: "POST",
      body: formData,
    });
  },
};
