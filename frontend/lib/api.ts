// Typed client for the Metal Marketplace backend (FastAPI on Modal).
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  "https://hashaamdogar--metal-marketplace-api-api.modal.run";

export type Tokens = { access_token: string; refresh_token: string; token_type: string };

export interface ModelListItem {
  id: string;
  slug: string;
  name: string;
  publisher_id: string;
  architecture: string;
  quantization?: string | null;
  param_count_b?: number | null;
  tags: string[];
  license_type: string;
  status: string;
  metrics: { tokens_per_sec_m2?: number | null; downloads: number; rating_avg: number; rating_count: number };
}

export interface ModelDetail extends ModelListItem {
  description: string;
  file_format: string;
  context_length?: number | null;
  min_ram_gb?: number | null;
  use_cases: string[];
  artifact: { storage_key?: string | null; size_bytes?: number | null; sha256?: string | null; version?: string };
  cloud_inference: { enabled: boolean; modal_app: string; modal_function: string; served_model_ref?: string | null };
}

export interface Page<T> { items: T[]; total: number; page: number; page_size: number }

export interface License {
  license_key: string;
  model_id: string;
  status: string;
  issued_at: string;
  max_devices: number;
  bound_device_count: number;
  devices: { device_id: string; device_name?: string; platform?: string; bound_at: string; last_seen_at: string; status: string }[];
}

export class ApiError extends Error {
  code: string;
  status: number;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

function token(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

async function request<T>(path: string, opts: RequestInit & { auth?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = { ...(opts.headers as Record<string, string>) };
  if (opts.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
  if (opts.auth) {
    const t = token();
    if (t) headers["Authorization"] = `Bearer ${t}`;
  }
  const res = await fetch(`${API_URL}${path}`, { ...opts, headers });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const e = data?.error || {};
    throw new ApiError(res.status, e.code || "error", e.message || res.statusText);
  }
  return data as T;
}

export const api = {
  // auth
  async register(body: { email: string; username: string; password: string; roles?: string[] }) {
    return request<Tokens>("/v1/auth/register", { method: "POST", body: JSON.stringify(body) });
  },
  async login(username: string, password: string) {
    const form = new URLSearchParams({ username, password });
    const res = await fetch(`${API_URL}/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form.toString(),
    });
    const data = await res.json();
    if (!res.ok) throw new ApiError(res.status, data?.error?.code || "error", data?.error?.message || "Login failed");
    return data as Tokens;
  },
  me() {
    return request<any>("/v1/users/me", { auth: true });
  },
  becomePublisher(body: { org_name?: string }) {
    return request<any>("/v1/users/me/become-publisher", { method: "POST", body: JSON.stringify(body), auth: true });
  },

  // catalog
  listModels(params: Record<string, string> = {}) {
    const q = new URLSearchParams(params).toString();
    return request<Page<ModelListItem>>(`/v1/models${q ? `?${q}` : ""}`);
  },
  getModel(slug: string) {
    return request<ModelDetail>(`/v1/models/${slug}`);
  },
  listReviews(slug: string) {
    return request<Page<any>>(`/v1/models/${slug}/reviews`);
  },

  // licensing
  acquire(modelId: string) {
    return request<License>(`/v1/models/${modelId}/acquire`, { method: "POST", auth: true });
  },
  myLicenses() {
    return request<License[]>("/v1/licenses", { auth: true });
  },
  bindDevice(key: string, body: { device_id: string; device_name?: string; platform?: string }) {
    return request<License>(`/v1/licenses/${key}/devices`, { method: "POST", body: JSON.stringify(body), auth: true });
  },
  unbindDevice(key: string, deviceId: string) {
    return request<License>(`/v1/licenses/${key}/devices/${deviceId}`, { method: "DELETE", auth: true });
  },
  verify(key: string, deviceId: string, autoBind = false) {
    return request<any>(`/v1/licenses/${key}/verify`, {
      method: "POST",
      body: JSON.stringify({ device_id: deviceId, auto_bind: autoBind }),
      auth: true,
    });
  },
  download(modelId: string, deviceId?: string) {
    const q = deviceId ? `?device_id=${encodeURIComponent(deviceId)}` : "";
    return request<{ download_url: string; sha256?: string; size_bytes?: number; expires_in: number }>(
      `/v1/models/${modelId}/download${q}`,
      { auth: true },
    );
  },

  // inference (cloud fallback)
  inference(body: { model_id: string; prompt: string; max_tokens?: number; temperature?: number; device_id?: string; reason: string }) {
    return request<{ output: string; tokens_generated: number; tokens_per_sec: number; path: string }>(
      "/v1/inference",
      { method: "POST", body: JSON.stringify(body), auth: true },
    );
  },

  readyz() {
    return request<{ ready: boolean; checks: Record<string, boolean> }>("/readyz");
  },
};
