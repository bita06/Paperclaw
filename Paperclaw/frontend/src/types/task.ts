export type AsyncStatus = "idle" | "loading" | "success" | "error";

export type UploadPipelineStatus =
  | "idle"
  | "uploading"
  | "uploaded"
  | "parsing"
  | "ready"
  | "error";

export type AsyncState<T> = {
  status: AsyncStatus;
  data?: T;
  error?: string;
};

export type UploadQueueItem = {
  id: string;
  name: string;
  size: number;
  status: UploadPipelineStatus;
};
