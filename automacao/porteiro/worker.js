// Porteiro da postagem automática (Cloudflare Worker, plano grátis).
// POST /telegram  -> o Telegram avisa aqui na hora; o porteiro acorda o GitHub Actions (repository_dispatch).
// GET  /m/<chave> -> entrega a mídia guardada no KV pro Instagram baixar (link secreto, apagado depois de postar).
// Vídeo maior que 20 MB fica em partes (<chave>, <chave>.1, ...): o KV aceita no máximo 25 MB por valor.
// Segredos do Worker: TG_SEGREDO, GH_PAT. Variável: REPO (dono/repositório). KV ligado como MIDIA.
export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    if (req.method === "POST" && url.pathname === "/telegram") {
      if (req.headers.get("X-Telegram-Bot-Api-Secret-Token") !== env.TG_SEGREDO) return new Response("não", { status: 403 });
      const r = await fetch(`https://api.github.com/repos/${env.REPO}/dispatches`, {
        method: "POST",
        headers: { Authorization: `Bearer ${env.GH_PAT}`, Accept: "application/vnd.github+json", "User-Agent": "moda-estampa-porteiro" },
        body: JSON.stringify({ event_type: "telegram", client_payload: { update: await req.json() } }),
      });
      return new Response(null, { status: r.ok ? 200 : 502 }); // 502: o Telegram tenta de novo
    }
    const m = url.pathname.match(/^\/m\/([0-9a-f]{16}\.(jpg|mp4))$/);
    if (!m || !["GET", "HEAD"].includes(req.method)) return new Response("ok");
    const { value, metadata } = await env.MIDIA.getWithMetadata(m[1], "arrayBuffer");
    if (!value) return new Response("não achei", { status: 404 });
    const partes = metadata?.partes ?? 1, tamanho = metadata?.tamanho ?? value.byteLength;
    const headers = { "Content-Type": m[2] === "jpg" ? "image/jpeg" : "video/mp4", "Content-Length": String(tamanho) };
    if (req.method === "HEAD") return new Response(null, { headers });
    if (partes === 1) return new Response(value, { headers });
    const { readable, writable } = new FixedLengthStream(tamanho);
    ctx.waitUntil((async () => {
      const w = writable.getWriter();
      await w.write(new Uint8Array(value));
      for (let i = 1; i < partes; i++) await w.write(new Uint8Array(await env.MIDIA.get(`${m[1]}.${i}`, "arrayBuffer")));
      await w.close();
    })());
    return new Response(readable, { headers });
  },
};
