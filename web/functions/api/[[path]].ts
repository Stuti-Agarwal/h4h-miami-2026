// Cloudflare Pages Function: proxy /api/* to the Flask API at env.FLASK_URL.
interface Env {
  FLASK_URL: string;
}

export const onRequest = async ({ request, env }: { request: Request; env: Env }) => {
  if (!env.FLASK_URL) return new Response("FLASK_URL not configured", { status: 500 });
  const url = new URL(request.url);
  const target = new URL(url.pathname + url.search, env.FLASK_URL);
  return fetch(new Request(target, request));
};
