import axios from "axios";
import { api } from "@/lib/api";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: string;
  created_at: string;
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("auth_token");
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem("auth_token", token);
  document.cookie = `auth_token=${token}; path=/; max-age=3600; SameSite=Lax`;
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem("auth_token");
  document.cookie = "auth_token=; path=/; max-age=0; SameSite=Lax";
}

export async function authLogin(email: string, password: string): Promise<{ access_token: string; token_type: string }> {
  const payload = new URLSearchParams();
  payload.append("username", email);
  payload.append("password", password);

  const res = await api.post<{ access_token: string; token_type: string }>("/auth/login", payload, {
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
  });
  return res.data;
}

export async function authSignup(email: string, fullName: string, password: string): Promise<User> {
  const res = await api.post<User>("/auth/signup", {
    email,
    full_name: fullName,
    password,
  });
  return res.data;
}

export async function authMe(): Promise<User> {
  const res = await api.get<User>("/auth/me");
  return res.data;
}

export function getErrorMessage(error: unknown, fallback = "Something went wrong"): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") {
      return detail;
    }
  }
  return fallback;
}
