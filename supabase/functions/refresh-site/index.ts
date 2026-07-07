// Supabase Edge Function：refresh-site
// 后台「立即刷新公开站」按钮调它 → 用服务端保存的 GitHub token 触发 refresh-cache Action，
// 让公开站（GitHub Pages）立刻重建静态文件、同步最新的上下线/编辑/删除。
//
// 为什么要它：admin.html 部署在公开的 GitHub Pages 上，不能把 GitHub token 写进前端
// （谁都能看源码）。token 只存在这个 Edge Function 的环境变量里，前端碰不到。
//
// 部署（详见 README「立即刷新」一节）：
//   supabase functions deploy refresh-site --no-verify-jwt
//   supabase secrets set GH_TOKEN=<细粒度token> GH_REPO=slzcn/ab-experiment-kb
//
// 触发的事件类型是 article-published——refresh-cache.yml 已在监听它。

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });

  const token = Deno.env.get("GH_TOKEN");
  const repo = Deno.env.get("GH_REPO") || "slzcn/ab-experiment-kb";
  if (!token) {
    return json({ ok: false, error: "服务器未配置 GH_TOKEN" }, 500);
  }

  try {
    const r = await fetch(`https://api.github.com/repos/${repo}/dispatches`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "ab-kb-refresh-site",
      },
      body: JSON.stringify({ event_type: "article-published" }),
    });
    // GitHub dispatch 成功返回 204 No Content
    if (r.status === 204) return json({ ok: true, msg: "已触发公开站刷新" });
    const detail = await r.text();
    return json({ ok: false, error: `GitHub ${r.status}: ${detail.slice(0, 200)}` }, 502);
  } catch (e) {
    return json({ ok: false, error: String(e) }, 500);
  }
});

function json(obj: unknown, status = 200): Response {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { ...CORS, "Content-Type": "application/json" },
  });
}
