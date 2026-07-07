#!/usr/bin/env python3
# 上传任务处理器（在 GitHub Action 里跑，就是这套方案里的“服务器”）。
#
# 纯 web 上传链路的后半段：
#   浏览器把原始文档直传到 doc-uploads 桶 + 插一条 upload_jobs(status=queued)。
#   本脚本被 Action 定时/触发调用：
#     ① 拉所有 queued 任务
#     ② 逐个：从 Storage 下载原文件 → doc_to_md 转码抽图 → 写 ab_articles
#     ③ 回填 upload_jobs 状态（processing/done/error）
#   图片由 doc_to_md 写进 assets/，Action 侧统一 git 提交（本脚本不碰 git）。
#
# 退出码：有成功入库的文章时打印 HAS_NEW=1（Action 据此决定要不要触发重建缓存）。

import os, sys, datetime, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import doc_to_md
from kb_common import plain_text, slugify, Supabase

BUCKET = "doc-uploads"
SB = Supabase()

# 仅列 Action 环境（ubuntu + pip 依赖）真正能处理的格式；
# 老二进制 .doc/.ppt/.xls/.rtf 需 LibreOffice，不在此列，前端也不再放它们进来
ALLOWED_EXT = {".pptx", ".docx", ".pdf", ".xlsx", ".xlsm",
               ".csv", ".txt", ".md", ".markdown", ".html", ".htm"}


def _set(job_id, patch):
    patch["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    SB.update("upload_jobs", f"id=eq.{job_id}", patch)


def process_one(job):
    jid = job["id"]
    fn = job["filename"]
    cat = job.get("cat") or "misc"
    title = os.path.splitext(os.path.basename(fn))[0]
    ext = os.path.splitext(fn)[1].lower()
    _set(jid, {"status": "processing", "title": title})

    if ext not in ALLOWED_EXT:
        _set(jid, {"status": "error", "error": f"不支持的格式 {ext}"})
        return False

    # 下载原文件到临时路径
    fd, tmp = tempfile.mkstemp(prefix="abup_", suffix=ext)
    try:
        data = SB.storage_download(BUCKET, job["path"])
        with os.fdopen(fd, "wb") as w:
            w.write(data)
        conv = doc_to_md.convert(tmp, slug=slugify(f"{cat}-{title}"), title=title)
        md = conv["md"]
        if not md.strip():
            _set(jid, {"status": "error", "error": "未抽取到内容"})
            return False
        # doc_id 由任务表自增 id 派生（9 开头内部区间），天然唯一、绝不碰撞
        # doc_id 用 920000000+ 段，避开 add.py/publish.py 的 910000000+ 段防冲突
            doc_id = 920000000 + int(jid)
        SB.insert("ab_articles", {
            "doc_id": doc_id, "title": title, "cat": cat,
            "keywords": (title + " 上传文档").strip(),
            "md": md, "body_text": plain_text(md),
            "updated": datetime.date.today().isoformat(),
            "source_url": "", "is_internal": True,
        }, upsert_on="doc_id")
        _set(jid, {"status": "done", "doc_id": doc_id,
                   "images": len(conv["images"]), "chars": len(md)})
        # 转码成功后删掉桶里的原始文件，避免无限累积
        try: SB.storage_delete(BUCKET, job["path"])
        except Exception: pass
        return True
    except Exception as e:
        _set(jid, {"status": "error", "error": str(e)[:400]})
        return False
    finally:
        try: os.remove(tmp)
        except Exception: pass


def main():
    try:
        jobs = SB.get("upload_jobs?status=eq.queued&order=created_at&select=*")
    except Exception as e:
        # upload_jobs 表还没建（未跑 supabase_uploads.sql）等情况：干净退出，不让 Action 红叉
        print(f"读取任务表失败（可能尚未初始化 upload_jobs）：{e}")
        print("HAS_NEW=0")
        return
    if not jobs:
        print("没有待处理任务。")
        print("HAS_NEW=0")
        return
    print(f"待处理任务 {len(jobs)} 个。")
    ok = 0
    for job in jobs:
        try:
            if process_one(job):
                ok += 1
                print(f"  ✓ {job['filename']}")
            else:
                print(f"  ✗ {job['filename']}")
        except Exception as e:
            print(f"  ✗ {job['filename']}: {e}")
            try: _set(job["id"], {"status": "error", "error": str(e)[:400]})
            except Exception: pass
    print(f"完成：成功 {ok}/{len(jobs)} 篇入库。")
    print(f"HAS_NEW={1 if ok else 0}")


if __name__ == "__main__":
    main()
