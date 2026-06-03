"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api, Tokens } from "./api";

type User = { id: string; email: string; username: string; roles: string[]; display_name?: string } | null;

interface AuthCtx {
  user: User;
  loading: boolean;
  login: (id: string, pw: string) => Promise<void>;
  register: (email: string, username: string, password: string, publisher: boolean) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
}

const Ctx = createContext<AuthCtx | null>(null);

function store(t: Tokens) {
  localStorage.setItem("access_token", t.access_token);
  localStorage.setItem("refresh_token", t.refresh_token);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User>(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    try {
      if (typeof window !== "undefined" && localStorage.getItem("access_token")) {
        setUser(await api.me());
      }
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function login(id: string, pw: string) {
    store(await api.login(id, pw));
    setUser(await api.me());
  }

  async function register(email: string, username: string, password: string, publisher: boolean) {
    const roles = publisher ? ["app_developer", "model_developer"] : ["app_developer"];
    store(await api.register({ email, username, password, roles }));
    setUser(await api.me());
  }

  function logout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setUser(null);
  }

  return <Ctx.Provider value={{ user, loading, login, register, logout, refresh }}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth must be used within AuthProvider");
  return c;
}
