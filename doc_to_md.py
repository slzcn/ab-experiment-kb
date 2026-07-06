#!/usr/bin/env python3
# 文档 → Markdown 转码器（带图）。
# 把 PPT/Word/PDF 等常见文档抽成 markdown 文章：正文文字 + 内嵌图片。
# 图片模型沿用本项目最新那篇文章的做法：
#   - 抽出的图片写到 assets/<slug>-<n>.<ext>
#   - md 里用 raw.githubusercontent.com 的 URL 引用（线上/妙搭/本地都能显示）
#
# 用法：
#   python3 doc_to_md.py <文件路径> [--slug 前缀] [--title 标题] [--json]
#   默认输出 markdown 到 stdout；--json 输出 {title, md, images:[存好的文件名]}
#
# 依赖（本机已装）：python-pptx / python-docx / PyMuPDF(fitz) / Pillow
# 被 serve.py 的批量上传接口调用，也可命令行单独跑。

import sys, os, re, json, zipfile, hashlib, io
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
# 图片线上引用前缀（与最新文章一致：raw.githubusercontent 指向仓库 assets/）
RAW_BASE = "https://raw.githubusercontent.com/slzcn/ab-experiment-kb/main/assets/"

MIN_IMG_BYTES = 3000      # 小于此的多半是图标/装饰，跳过
MIN_IMG_WH    = 80        # 任一边小于此像素跳过（去掉小logo/项目符号）


def _slugify(s, fallback="doc"):
    s = re.sub(r'[\\/:*?"<>|\s]+', "-", (s or "").strip()).strip("-").lower()
    s = re.sub(r'[^a-z0-9一-鿿\-]', "", s)
    return s[:32] or fallback


def _img_ok(data):
    """过滤太小或纯图标的图片，返回 (ok, ext)。"""
    if not data or len(data) < MIN_IMG_BYTES:
        return False, None
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data))
        w, h = im.size
        if w < MIN_IMG_WH or h < MIN_IMG_WH:
            return False, None
        fmt = (im.format or "PNG").lower()
        ext = {"jpeg": "jpg"}.get(fmt, fmt)
        if ext not in ("jpg", "png", "gif", "webp"):
            ext = "png"
        return True, ext
    except Exception:
        return False, None


def _save_img(data, slug, seen):
    """存图到 assets/，去重（按内容 hash），返回线上 md 引用 URL 或 None。"""
    ok, ext = _img_ok(data)
    if not ok:
        return None
    h = hashlib.md5(data).hexdigest()[:8]
    if h in seen:
        return seen[h]                       # 同一张图复用已存文件
    os.makedirs(ASSETS, exist_ok=True)
    name = f"{slug}-{h}.{ext}"
    with open(os.path.join(ASSETS, name), "wb") as f:
        f.write(data)
    url = RAW_BASE + name
    seen[h] = url
    return url


# ---------------- PPTX：按幻灯片顺序，文字 + 该页图片 ----------------
def _pptx(path, slug):
    from pptx import Presentation
    from pptx.util import Emu
    prs = Presentation(path)
    seen = {}
    imgs = []
    md_parts = []
    for i, slide in enumerate(prs.slides, 1):
        texts = []
        pics = []
        for shp in slide.shapes:
            if shp.has_text_frame:
                t = "\n".join(p.text for p in shp.text_frame.paragraphs if p.text.strip())
                if t.strip():
                    texts.append(t.strip())
            if shp.shape_type == 13 or getattr(shp, "image", None):  # PICTURE
                try:
                    blob = shp.image.blob
                    url = _save_img(blob, slug, seen)
                    if url:
                        pics.append(url)
                except Exception:
                    pass
        block = []
        if texts:
            # 第一行当小标题，其余作正文
            head = texts[0].split("\n")[0].strip()
            if head:
                block.append(f"## {head}")
            body = "\n\n".join(texts)
            # 去掉重复的标题行
            body = "\n".join(ln for ln in body.split("\n") if ln.strip() != head)
            if body.strip():
                block.append(body.strip())
        for u in pics:
            block.append(f"![]({u})")
            imgs.append(u)
        if block:
            md_parts.append("\n\n".join(block))
    return "\n\n".join(md_parts), imgs


# ---------------- DOCX：按文档流顺序穿插段落与图片 ----------------
def _docx(path, slug):
    import docx
    from docx.document import Document as _Doc
    d = docx.Document(path)
    seen = {}
    imgs = []
    # rId -> 图片二进制
    rels = {}
    for rid, rel in d.part.rels.items():
        if "image" in rel.reltype:
            try:
                rels[rid] = rel.target_part.blob
            except Exception:
                pass
    ns = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    }
    md_parts = []
    for p in d.paragraphs:
        # 段落文字
        txt = p.text.strip()
        if txt:
            style = (p.style.name or "").lower()
            if "heading 1" in style or style == "title":
                md_parts.append(f"## {txt}")
            elif "heading" in style:
                md_parts.append(f"### {txt}")
            else:
                md_parts.append(txt)
        # 段落里的内嵌图
        blips = p._p.findall(".//a:blip", ns)
        for b in blips:
            rid = b.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
            if rid and rid in rels:
                url = _save_img(rels[rid], slug, seen)
                if url:
                    md_parts.append(f"![]({url})")
                    imgs.append(url)
    # 表格
    for tb in d.tables:
        rows = []
        for r in tb.rows:
            cells = [c.text.strip().replace("\n", " ") for c in r.cells]
            if any(cells):
                rows.append("| " + " | ".join(cells) + " |")
        if rows:
            # 加表头分隔
            if len(rows) >= 1:
                ncol = rows[0].count("|") - 1
                rows.insert(1, "|" + "---|" * ncol)
            md_parts.append("\n".join(rows))
    return "\n\n".join(md_parts), imgs


# ---------------- PDF：按页抽文字 + 内嵌图 ----------------
def _pdf(path, slug):
    import fitz
    doc = fitz.open(path)
    seen = {}
    imgs = []
    md_parts = []
    for pno in range(len(doc)):
        page = doc[pno]
        txt = page.get_text().strip()
        if txt:
            md_parts.append(txt)
        for img in page.get_images(full=True):
            xref = img[0]
            try:
                pix = fitz.Pixmap(doc, xref)
                if pix.n - pix.alpha >= 4:          # CMYK → RGB
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                data = pix.tobytes("png")
                url = _save_img(data, slug, seen)
                if url:
                    md_parts.append(f"![]({url})")
                    imgs.append(url)
            except Exception:
                pass
    return "\n\n".join(md_parts), imgs


def convert(path, slug=None, title=None):
    ext = os.path.splitext(path)[1].lower()
    base = os.path.splitext(os.path.basename(path))[0]
    title = title or base
    slug = _slugify(slug or base)
    if ext == ".pptx":
        md, imgs = _pptx(path, slug)
    elif ext == ".docx":
        md, imgs = _docx(path, slug)
    elif ext == ".pdf":
        md, imgs = _pdf(path, slug)
    else:
        # 老格式/纯文本：退回 read_doc.py 只抽文字（无图）
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "feishu-claude-bot", "scripts"))
        try:
            import read_doc
            secs = read_doc.read(path)
            md = "\n\n".join(
                (f"## {s['section']}\n\n{s['text']}" if s.get("section") not in ("正文", None) else s["text"])
                for s in secs if s.get("text")
            )
            imgs = []
        except Exception as e:
            raise RuntimeError(f"不支持的格式且文本兜底失败：{ext}（{e}）")
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    return {"title": title, "md": md, "images": imgs}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 doc_to_md.py <文件> [--slug 前缀] [--title 标题] [--json]")
        sys.exit(1)
    path = sys.argv[1]
    as_json = "--json" in sys.argv

    def _opt(flag):
        if flag in sys.argv:
            i = sys.argv.index(flag)
            if i + 1 < len(sys.argv):
                return sys.argv[i + 1]
        return None

    if not os.path.exists(path):
        print("文件不存在:", path); sys.exit(1)
    try:
        r = convert(path, slug=_opt("--slug"), title=_opt("--title"))
    except Exception as e:
        print(f"转码失败({type(e).__name__}): {e}"); sys.exit(2)
    if as_json:
        print(json.dumps(r, ensure_ascii=False))
    else:
        print(f"# {r['title']}\n")
        print(r["md"])
        print(f"\n\n[抽出图片 {len(r['images'])} 张 → assets/]", file=sys.stderr)
