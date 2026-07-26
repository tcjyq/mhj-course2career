const UPSTREAM_ORIGIN = "https://mhj-course2career.streamlit.app";

export default {
  async fetch(request) {
    const incomingUrl = new URL(request.url);
    const upstreamUrl = new URL(request.url);
    upstreamUrl.protocol = "https:";
    upstreamUrl.hostname = "mhj-course2career.streamlit.app";
    upstreamUrl.port = "";

    const requestHeaders = new Headers(request.headers);
    requestHeaders.delete("host");

    if (requestHeaders.has("origin")) {
      requestHeaders.set("origin", UPSTREAM_ORIGIN);
    }
    if (requestHeaders.has("referer")) {
      requestHeaders.set(
        "referer",
        `${UPSTREAM_ORIGIN}${incomingUrl.pathname}${incomingUrl.search}`,
      );
    }

    const upstreamRequest = new Request(upstreamUrl, {
      method: request.method,
      headers: requestHeaders,
      body:
        request.method === "GET" || request.method === "HEAD"
          ? undefined
          : request.body,
      redirect: "manual",
    });
    const upstreamResponse = await fetch(upstreamRequest);

    // Preserve the WebSocket response used by Streamlit.
    if (upstreamResponse.status === 101) {
      return upstreamResponse;
    }

    const responseHeaders = new Headers(upstreamResponse.headers);
    const location = responseHeaders.get("location");
    if (location?.startsWith(UPSTREAM_ORIGIN)) {
      responseHeaders.set(
        "location",
        `${incomingUrl.origin}${location.slice(UPSTREAM_ORIGIN.length)}`,
      );
    }
    responseHeaders.set("x-course2career-edge", "cloudflare-worker");

    return new Response(upstreamResponse.body, {
      status: upstreamResponse.status,
      statusText: upstreamResponse.statusText,
      headers: responseHeaders,
    });
  },
};
