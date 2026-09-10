// Local, offline authentication client. Talks to the local backend's /auth
// endpoints and keeps the issued JWT in localStorage. Replaces Firebase Auth.
const API_BASE =
  (typeof window !== "undefined" && window.desktop?.apiBase) ||
  import.meta.env.VITE_API_BASE ||
  "/api";
const TOKEN_KEY = "auth_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

async function detail(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
  } catch {
    /* ignore */
  }
  return fallback;
}

export async function login(email: string, password: string): Promise<void> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(await detail(res, "login failed"));
  const data = (await res.json()) as { token: string };
  setToken(data.token);
}

export function logout(): void {
  clearToken();
}

export async function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<void> {
  const res = await fetch(`${API_BASE}/auth/change-password`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getToken() ?? ""}`,
    },
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
  if (!res.ok) throw new Error(await detail(res, "could not change password"));
}
