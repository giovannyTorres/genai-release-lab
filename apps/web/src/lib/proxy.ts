/** Same-origin backend gateway. API_URL is operator configuration read at request time. */
const REQUEST_LIMIT = 2_100_000;
const forwardedHeaders = [
  "accept",
  "content-type",
  "cookie",
  "origin",
  "referer",
  "sec-fetch-site",
  "x-correlation-id",
];
const removedResponseHeaders = [
  "connection",
  "content-length",
  "content-encoding",
  "transfer-encoding",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "upgrade",
];

export async function proxyToApi(
  request: Request,
  segments: string[],
): Promise<Response> {
  // The destination authority is never derived from request data or forwarded host headers.
  const configured = process.env.API_URL || "http://127.0.0.1:8103";
  let destination: URL;
  try {
    const base = new URL(configured);
    if (
      !["http:", "https:"].includes(base.protocol) ||
      base.username ||
      base.password
    )
      throw new Error("Invalid backend configuration");
    if (segments.some((segment) => [".", ".."].includes(segment)))
      return Response.json({ detail: "Invalid API path" }, { status: 400 });
    destination = new URL(
      `/api/${segments.map(encodeURIComponent).join("/")}`,
      base,
    );
    destination.search = new URL(request.url).search;
  } catch {
    return Response.json(
      { detail: "The application backend is not configured correctly." },
      { status: 503 },
    );
  }
  const headers = new Headers();
  for (const name of forwardedHeaders) {
    const value = request.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  let body: Uint8Array | undefined;
  if (request.method !== "GET" && request.method !== "HEAD" && request.body) {
    const reader = request.body.getReader();
    const chunks: Uint8Array[] = [];
    let length = 0;
    try {
      while (true) {
        const next = await reader.read();
        if (next.done) break;
        length += next.value.byteLength;
        if (length > REQUEST_LIMIT) {
          await reader.cancel();
          return Response.json(
            { detail: "Import is too large. Maximum request size is 2.1 MB." },
            { status: 413 },
          );
        }
        chunks.push(next.value);
      }
    } catch {
      return Response.json(
        { detail: "The request could not be read. Please retry." },
        { status: 400 },
      );
    } finally {
      reader.releaseLock();
    }
    body = new Uint8Array(length);
    let offset = 0;
    for (const chunk of chunks) {
      body.set(chunk, offset);
      offset += chunk.byteLength;
    }
  }
  const timeout = AbortSignal.timeout(30_000);
  try {
    const upstream = await fetch(destination, {
      method: request.method,
      headers,
      body: body as BodyInit | undefined,
      redirect: "manual",
      cache: "no-store",
      signal: AbortSignal.any([request.signal, timeout]),
    });
    const responseHeaders = new Headers(upstream.headers);
    for (const name of removedResponseHeaders) responseHeaders.delete(name);
    responseHeaders.set("cache-control", "no-store");
    return new Response(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch {
    return Response.json(
      {
        detail: timeout.aborted
          ? "The backend took too long to respond. Please retry."
          : "The backend is temporarily unavailable. Please retry.",
      },
      { status: timeout.aborted ? 504 : 502 },
    );
  }
}
