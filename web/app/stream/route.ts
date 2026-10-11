export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET() {
  const api = process.env.API_INTERNAL_URL || "http://127.0.0.1:18080";
  try {
    const upstream = await fetch(`${api}/api/alerts/stream`, {
      headers: { Accept: "text/event-stream" },
      cache: "no-store",
    });
    if (!upstream.ok || !upstream.body) {
      return new Response("告警通道暂时不可用", { status: 502 });
    }
    return new Response(upstream.body, {
      headers: {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  } catch {
    return new Response("告警通道暂时不可用", { status: 502 });
  }
}
