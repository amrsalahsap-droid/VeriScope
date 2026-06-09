"use server";

import { cookies } from "next/headers";
import { auth } from "@/auth";

export async function setReposSelectedCookie() {
  const cookieStore = await cookies();
  cookieStore.set("veriscope_repos_selected", "true", {
    maxAge: 60 * 60 * 24 * 365,
    path: "/",
  });
}

export async function getRepositoriesFromBackend() {
  const session = await auth();
  if (!session?.backendToken) {
    return [];
  }
  
  try {
    const res = await fetch("http://localhost:8000/github/repositories?selected_only=false", {
      headers: {
        Authorization: `Bearer ${session.backendToken}`,
      },
      cache: "no-store",
    });
    if (!res.ok) {
      console.error("Failed to fetch repositories:", res.status, res.statusText);
      return [];
    }
    const data = await res.json();
    return data.repositories || [];
  } catch (error) {
    console.error("Failed to fetch repositories:", error);
    return [];
  }
}

export async function updateRepositorySelectionServer(repositoryIds: string[]) {
  const session = await auth();
  if (!session?.backendToken) {
    throw new Error("Not authenticated");
  }
  
  try {
    const res = await fetch("http://localhost:8000/github/repositories/select", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session.backendToken}`,
      },
      body: JSON.stringify({ repository_ids: repositoryIds }),
    });
    if (!res.ok) {
      const body = await res.json();
      console.error("Selection failed:", body);
      throw new Error("Failed to update selection");
    }
    const data = await res.json();
    return data;
  } catch (error) {
    console.error("Failed to update repository selection:", error);
    throw error;
  }
}
