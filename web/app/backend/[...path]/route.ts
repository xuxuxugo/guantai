import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function apiBase() {
  return process.env.API_INTERNAL_URL || "http://127.0.0.1:18080";
}

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  if (path.some((segment) => segment.includes("..") || segment.includes("\\") || segment.includes(":"))) {
    return Response.json({ detail: "路径不正确" }, { status: 400 });
  }
  const incoming = new URL(request.url);
  const target = `${apiBase()}/${path.join("/")}${incoming.search}`;
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  const method = request.method;
  const body = method === "GET" || method === "HEAD" ? undefined : await request.text();
  try {
    const upstream = await fetch(target, { method, headers, body, cache: "no-store" });
    const text = await upstream.text();
    return new Response(text, {
      status: upstream.status,
      headers: {
        "content-type": upstream.headers.get("content-type") || "application/json; charset=utf-8",
        "cache-control": "no-store",
      },
    });
  } catch {
    return Response.json({ detail: "行情服务暂时没有回应" }, { status: 502 });
  }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
