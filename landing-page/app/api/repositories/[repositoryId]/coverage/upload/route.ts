import { auth } from "@/auth";
import { NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ repositoryId: string }> }
) {
  const session = await auth();
  const { repositoryId } = await params;

  if (!session?.backendToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const formData = await request.formData();
    const file = formData.get("file") as File;
    const format = formData.get("format") as string || "LCOV";
    const commitSha = formData.get("commit_sha") as string | null;
    const branch = formData.get("branch") as string | null;
    const source = formData.get("source") as string || "MANUAL_UPLOAD";
    const pullRequestId = formData.get("pull_request_id") as string | null;
    const headSha = formData.get("head_sha") as string | null;
    const sourceContext = formData.get("source_context") as string | null;

    if (!file) {
      return NextResponse.json({ error: "No file provided" }, { status: 400 });
    }

    // Create new FormData for backend
    const backendFormData = new FormData();
    backendFormData.append("file", file);
    backendFormData.append("format", format);
    if (commitSha) backendFormData.append("commit_sha", commitSha);
    if (branch) backendFormData.append("branch", branch);
    backendFormData.append("source", source);
    if (pullRequestId) backendFormData.append("pull_request_id", pullRequestId);
    if (headSha) backendFormData.append("head_sha", headSha);
    if (sourceContext) backendFormData.append("source_context", sourceContext);

    const res = await fetch(
      `${BACKEND}/github/repositories/${repositoryId}/coverage/upload`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.backendToken}`,
        },
        body: backendFormData,
      }
    );

    const body = await res.json().catch(() => ({}));

    if (!res.ok) {
      return NextResponse.json(
        { error: body?.detail || `Backend error ${res.status}` },
        { status: res.status }
      );
    }

    return NextResponse.json(body);
  } catch (err: any) {
    return NextResponse.json(
      { error: err?.message || "Failed to reach backend" },
      { status: 502 }
    );
  }
}
