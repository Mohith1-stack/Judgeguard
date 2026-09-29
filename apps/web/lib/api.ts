const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export function apiUrl(path: string): string {
  return `${base}${path}`;
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const response = await fetch(apiUrl(path), {
    ...options,
    headers,
    credentials: "include",
    cache: "no-store",
  });
  const text = await response.text();
  if (!response.ok) throw new Error(text || `Request failed with ${response.status}`);
  return text ? (JSON.parse(text) as T) : (undefined as T);
}

export type User = { id: string; email: string; display_name: string; role: string; is_active: boolean; email_verified: boolean; created_at: string };
export async function getMe() { return apiFetch<User>("/auth/me"); }
