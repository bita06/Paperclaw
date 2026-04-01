const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
const TOKEN_KEY = "paperclaw_access_token";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  const body = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const detail =
      typeof body === "string"
        ? body
        : body?.detail
          ? typeof body.detail === "string"
            ? body.detail
            : JSON.stringify(body.detail)
          : "Request failed";
    if (response.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("paperclaw:auth-expired"));
    }
    throw new ApiError(response.status, detail);
  }

  return body as T;
}

export function buildQueryString(
  params: Record<string, string | number | boolean | null | undefined>,
): string {
  const query = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }
    query.set(key, String(value));
  });

  const serialized = query.toString();
  return serialized ? `?${serialized}` : "";
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  try {
    const token = window.localStorage.getItem(TOKEN_KEY);
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...(init?.headers ?? {}),
      },
    });

    return parseResponse<T>(response);
  } catch (cause) {
    if (cause instanceof ApiError) {
      throw cause;
    }

    throw new ApiError(
      0,
      "当前无法连接后端服务或请求已中断，请确认 FastAPI 服务已启动，并稍后重试。",
    );
  }
}
