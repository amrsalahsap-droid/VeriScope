/**
 * @jest-environment node
 */

import {
  GET,
  POST,
  PUT,
  PATCH,
  DELETE,
} from "@/app/api/ac-test-mappings/[...path]/route";
import { auth } from "@/auth";
import { NextRequest } from "next/server";

jest.mock("@/auth", () => ({
  auth: jest.fn(),
}));

const mockAuth = auth as jest.Mock;

function makeRequest(
  method: string,
  pathSegments: string[],
  body?: Record<string, unknown>,
  search?: string
) {
  const url = new URL(
    `http://localhost:3000/api/ac-test-mappings/${pathSegments.join("/")}${
      search || ""
    }`
  );
  return new NextRequest(url, {
    method,
    body: body ? JSON.stringify(body) : undefined,
    headers: {
      "content-type": "application/json",
      accept: "application/json",
    },
  });
}

function makeParams(pathSegments: string[]) {
  return Promise.resolve({ path: pathSegments });
}

function mockFetch(status: number, body: string, contentType: string) {
  return jest.fn().mockResolvedValue({
    status,
    text: jest.fn().mockResolvedValue(body),
    headers: new Headers({ "content-type": contentType }),
  } as unknown as Response);
}

describe("/api/ac-test-mappings/[...path] proxy", () => {
  beforeEach(() => {
    global.fetch = jest.fn();
    mockAuth.mockResolvedValue({ backendToken: "test-token" });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it("returns 401 when no backend token is present", async () => {
    mockAuth.mockResolvedValueOnce(null);
    const req = makeRequest("GET", ["candidates", "abc"]);
    const res = await GET(req, { params: makeParams(["candidates", "abc"]) });
    expect(res.status).toBe(401);
    await expect(res.json()).resolves.toEqual({ error: "Unauthorized" });
  });

  it("GET forwards query parameters to the backend", async () => {
    global.fetch = mockFetch(200, JSON.stringify({ rows: [] }), "application/json");
    const req = makeRequest("GET", ["summary"], undefined, "?repo=1&pr=2");
    const res = await GET(req, { params: makeParams(["summary"]) });

    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/ac-test-mappings/summary?repo=1&pr=2",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer test-token",
          Accept: "application/json",
        }),
      })
    );
    expect(res.status).toBe(200);
  });

  it("POST accept_semantic_match reaches backend with body", async () => {
    global.fetch = mockFetch(
      200,
      JSON.stringify({ message: "Accepted semantic match" }),
      "application/json"
    );
    const req = makeRequest("POST", ["candidates", "abc", "accept_semantic_match"], {
      repository_id: "repo-1",
      pull_request_id: "pr-1",
      comment: "Looks right",
    });
    const res = await POST(req, {
      params: makeParams(["candidates", "abc", "accept_semantic_match"]),
    });

    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/ac-test-mappings/candidates/abc/accept_semantic_match",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer test-token",
          "Content-Type": "application/json",
        }),
        body: JSON.stringify({
          repository_id: "repo-1",
          pull_request_id: "pr-1",
          comment: "Looks right",
        }),
      })
    );
    expect(res.status).toBe(200);
    await expect(res.json()).resolves.toEqual({ message: "Accepted semantic match" });
  });

  it.each([
    ["confirm_candidate", POST, { reason: "" }],
    ["reject_candidate", POST, { reason: "Wrong AC" }],
    ["keep_declared_ref_anyway", POST, { acknowledged_warning: true }],
    ["mark_unmapped", POST, { reason: "No test" }],
    ["add_review_comment", POST, { comment: "Note" }],
  ] as [string, any, Record<string, unknown>][])(
    "POST candidates/:id/%s reaches backend",
    async (action, method, body) => {
      global.fetch = mockFetch(200, JSON.stringify({ message: "ok" }), "application/json");
      const req = makeRequest("POST", ["candidates", "c1", action], body);
      const res = await method(req, { params: makeParams(["candidates", "c1", action]) });

      expect(global.fetch).toHaveBeenCalledWith(
        `http://localhost:8000/ac-test-mappings/candidates/c1/${action}`,
        expect.objectContaining({ method: "POST" })
      );
      expect(res.status).toBe(200);
    }
  );

  it("POST manually_link_to_ac reaches backend", async () => {
    global.fetch = mockFetch(200, JSON.stringify({ message: "Linked" }), "application/json");
    const req = makeRequest("POST", ["manually_link_to_ac"], {
      target_ac_id: "ac-1",
      test_case_id: "tc-1",
      repository_id: "repo-1",
      pull_request_id: "pr-1",
      reason: "Manual override",
    });
    const res = await POST(req, { params: makeParams(["manually_link_to_ac"]) });

    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/ac-test-mappings/manually_link_to_ac",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          target_ac_id: "ac-1",
          test_case_id: "tc-1",
          repository_id: "repo-1",
          pull_request_id: "pr-1",
          reason: "Manual override",
        }),
      })
    );
    expect(res.status).toBe(200);
  });

  it("PUT and PATCH are forwarded", async () => {
    global.fetch = mockFetch(200, JSON.stringify({ ok: true }), "application/json");
    const putReq = makeRequest("PUT", ["candidates", "c1"], { status: "x" });
    const putRes = await PUT(putReq, { params: makeParams(["candidates", "c1"]) });
    expect(putRes.status).toBe(200);

    const patchReq = makeRequest("PATCH", ["candidates", "c1"], { reason: "y" });
    const patchRes = await PATCH(patchReq, { params: makeParams(["candidates", "c1"]) });
    expect(patchRes.status).toBe(200);
  });

  it("DELETE is forwarded without body", async () => {
    global.fetch = mockFetch(200, JSON.stringify({ deleted: true }), "application/json");
    const req = makeRequest("DELETE", ["candidates", "c1"]);
    const res = await DELETE(req, { params: makeParams(["candidates", "c1"]) });

    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/ac-test-mappings/candidates/c1",
      expect.objectContaining({ method: "DELETE" })
    );
    const callOpts = (global.fetch as jest.Mock).mock.calls[0][1];
    expect(callOpts.body).toBeUndefined();
    expect(res.status).toBe(200);
  });

  it("returns JSON error instead of Next.js HTML when backend sends HTML 404", async () => {
    global.fetch = mockFetch(
      404,
      "<!doctype html><html><body>Not Found</body></html>",
      "text/html"
    );
    const req = makeRequest("POST", ["candidates", "abc", "accept_semantic_match"], {});
    const res = await POST(req, {
      params: makeParams(["candidates", "abc", "accept_semantic_match"]),
    });

    expect(res.status).toBe(404);
    const json = await res.json();
    expect(json).toEqual({
      detail: "<!doctype html><html><body>Not Found</body></html>",
    });
  });

  it("returns 502 JSON when backend is unreachable", async () => {
    global.fetch = jest.fn().mockRejectedValue({ message: "fetch failed", cause: { code: "ECONNREFUSED" } });
    const req = makeRequest("POST", ["candidates", "abc", "accept_semantic_match"], {});
    const res = await POST(req, {
      params: makeParams(["candidates", "abc", "accept_semantic_match"]),
    });

    expect(res.status).toBe(502);
    const json = await res.json();
    expect(json.error).toContain("Backend is not reachable");
  });
});
