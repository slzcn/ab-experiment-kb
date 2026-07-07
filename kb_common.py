#!/usr/bin/env python3
# 公共工具：正文纯文本提取 / slug 生成 / git 操作 / Supabase REST 客户端 / 配置读取。
# 之前这些逻辑在 publish.py / build_kb.py / add.py / admin_server.py / gen_cache.py /
# seed_supabase.py 里各写了一份（且行为略有出入），统一收敛到这里。

import os, re, json, subprocess
import urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------- 正文纯文本（检索用 body_text）----------------
def plain_text(md):
    """从 markdown 抽检索用纯文本：去图片/HTML/代码块/md 符号，压缩空白。"""
    t = md or ""
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)     # 图片
    t = re.sub(r"<[^>]+>", "", t)                   # HTML 标签
    t = re.sub(r"```[\s\S]*?```", "", t)            # 代码块
    t = re.sub(r"[#>*`|\-]{1,}", " ", t)            # md 符号
    return re.sub(r"\s+", " ", t).strip()


# ---------------- slug ----------------
def slugify(s, fallback="doc", maxlen=32):
    """把标题等转成文件/资源安全的 slug（保留中英文数字，其余转连字符）。"""
    s = re.sub(r'[\\/:*?"<>|\s]+', "-", (s or "").strip()).strip("-")
    s = re.sub(r"[^0-9A-Za-z一-鿿\-]", "", s)
    return s[:maxlen] or fallback


# ---------------- git ----------------
def git(*args, capture=True):
    """在仓库目录跑 git，默认禁用终端交互提示（sandbox 里会卡死）。"""
    return subprocess.run(
        ["git", "-C", HERE, *args],
        capture_output=capture, text=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )


# ---------------- 配置 ----------------
def load_sb_config():
    cfg = json.load(open(os.path.join(HERE, "sb_config.json"), encoding="utf-8"))
    return cfg["url"].rstrip("/"), cfg["key"]


# ---------------- Supabase REST ----------------
class Supabase:
    """极简 Supabase REST 客户端，统一 header/超时/错误处理。

    关键：urllib 对 4xx/5xx 会抛 HTTPError，本类会读出响应体里的错误详情
    再抛 RuntimeError（旧代码里 `if resp.status not in (...)` 永远走不到，
    错误详情被吞掉，无法排障）。
    """

    def __init__(self, url=None, key=None, timeout=60):
        if url is None or key is None:
            url, key = load_sb_config()
        self.url, self.key, self.timeout = url.rstrip("/"), key, timeout

    def _headers(self, extra=None):
        h = {"apikey": self.key, "Authorization": "Bearer " + self.key}
        if extra:
            h.update(extra)
        return h

    def _do(self, method, path, body=None, headers=None):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        req = urllib.request.Request(
            self.url + "/rest/v1/" + path, data=data, method=method,
            headers=self._headers({**({"Content-Type": "application/json"} if data else {}),
                                   **(headers or {})}))
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8") or ""
                return json.loads(raw) if raw.strip() else None
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8")[:300]
            except Exception:
                pass
            raise RuntimeError(f"Supabase {method} {path} HTTP {e.code}: {detail}") from None

    def get(self, path):
        return self._do("GET", path)

    def insert(self, table, row, upsert_on=None):
        """插入一行/多行；upsert_on 指定冲突列则走 merge 幂等 upsert。"""
        path = table
        headers = {"Prefer": "return=minimal"}
        if upsert_on:
            path = f"{table}?on_conflict={upsert_on}"
            headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
        return self._do("POST", path, body=row, headers=headers)

    def update(self, table, filt, patch):
        """PATCH：table 加 PostgREST 过滤（如 'id=eq.5'）后打补丁。"""
        return self._do("PATCH", f"{table}?{filt}", body=patch,
                         headers={"Prefer": "return=minimal"})

    def storage_download(self, bucket, path):
        """从 Storage 桶下载对象，返回 bytes（走公开路径，免密）。"""
        url = f"{self.url}/storage/v1/object/public/{bucket}/{path}"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Storage 下载失败 {bucket}/{path} HTTP {e.code}") from None

    def storage_delete(self, bucket, path):
        """删除 Storage 桶里的对象（处理完清理原始文件用）。对象已不存在视为成功。"""
        url = f"{self.url}/storage/v1/object/{bucket}/{path}"
        req = urllib.request.Request(url, method="DELETE", headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status in (200, 204)
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):   # 对象不存在——已达成"删除"的目的
                return True
            raise RuntimeError(f"Storage 删除失败 {bucket}/{path} HTTP {e.code}") from None
