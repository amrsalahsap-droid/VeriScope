import { auth } from "@/auth";
import { NextResponse } from "next/server";

export interface ProxyOptions {
  method: string;
  path: string;
  request: Request;
}

export async function proxyBackend({ method, path, request }: ProxyOptions) {
  const backendBaseUrl = process.env.NEXT_PUBLIC_API_URL || process.env.BACKEND_URL;
  if (!backendBaseUrl) {
    return NextResponse.json(
      { error: "Backend base URL environment variable (NEXT_PUBLIC_API_URL/BACKEND_URL) is missing" },
      { status: 500 }
    );
  }

  const session = await auth();
  if (!session?.backendToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const cleanBaseUrl = backendBaseUrl.replace(/\/+$/, "");
    const { search } = new URL(request.url);
    const backendUrl = `${cleanBaseUrl}${path}${search}`;
    console.log("PROXY_BACKEND_REQUEST", { path, search, backendUrl });

    const headers: HeadersInit = {
      Authorization: `Bearer ${session.backendToken}`,
    };

    // Forward Content-Type if present in original request
    const contentType = request.headers.get("content-type");
    if (contentType) {
      headers["Content-Type"] = contentType;
    }

    let body: any = undefined;
    if (method === "POST" || method === "PATCH" || method === "PUT") {
      try {
        const text = await request.text();
        if (text) {
          body = text;
        }
      } catch (e) {
        console.warn("Failed to read request body text:", e);
      }
    }

    const res = await fetch(backendUrl, {
      method,
      headers,
      body,
      cache: "no-store",
    });

    const responseContentType = res.headers.get("content-type") || "";
    const responseContentDisposition = res.headers.get("content-disposition");

    const responseHeaders: HeadersInit = {};
    if (responseContentType) {
      responseHeaders["Content-Type"] = responseContentType;
    }
    if (responseContentDisposition) {
      responseHeaders["Content-Disposition"] = responseContentDisposition;
    }

    if (responseContentType.includes("application/json")) {
      const jsonBody = await res.json().catch(() => ({}));
      return NextResponse.json(jsonBody, {
        status: res.status,
        headers: responseHeaders,
      });
    } else {
      const textBody = await res.text().catch(() => "");
      return new NextResponse(textBody, {
        status: res.status,
        headers: responseHeaders,
      });
    }
  } catch (err: any) {
    console.error("Proxy error:", err);
    return NextResponse.json(
      { error: err?.message || "Failed to reach backend" },
      { status: 502 }
    );
  }
}
