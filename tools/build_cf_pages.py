#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_cf_pages.py —— 生成可直接上传到 Cloudflare Pages 的部署包（zip）。

用法（仓库根目录执行）：
    python3 tools/build_cf_pages.py                          # 自适应域名，直接上传即可
    python3 tools/build_cf_pages.py --origin https://域名/  # 绑定自定义域名后，固定对外源地址

做了什么：
  1. 复制全站静态文件（排除 .git / 缓存 / 本工具自身）
  2. 若给了 --origin：
     - 在各页面 <head> 注入 window.PUBLIC_ORIGIN，让源地址、深链统一显示该域名
     - 把 Packages / depiction JSON / README 里的绝对 URL 换成该域名
     - 重建 Packages.gz，并重算 Release 的 4 组校验和（索引内容变了必须重算）
  3. 打包成 cf-pages-upload.zip，根目录含 _headers（CF Pages 缓存/类型配置）

为什么需要 --origin：
  优选 IP / 分线路 DNS 最终会用一个自有域名访问站点，但 CF Pages 项目本身
  仍叫 xxx.pages.dev。若不固定，页面会显示 pages.dev 作为源地址，用户添加后
  走的还是没被优选的默认线路。
"""
import argparse
import gzip
import hashlib
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT.parent / "cloudflare" / "cf-pages-upload.zip"
OLD = "https://evandersun.github.io/"

SKIP_DIRS = {".git", "__pycache__", "tools", "node_modules"}
SKIP_FILES = {".DS_Store", ".gitignore", ".nojekyll"}
SKIP_SUFFIX = {".pyc", ".zip"}

# 页面 <head> 注入 PUBLIC_ORIGIN 的位置（</head> 前）
PAGES = ["index.html", "repo.html", "post.html", "egg2.html", "admin.html",
         "depiction/screentimespoofer.html"]
# 含绝对 URL 需替换的静态文件
URL_FILES = ["Packages", "README.md", "depiction/screentimespoofer.json",
             "admin.html", "repo.html", "depiction/screentimespoofer.html"]
RELEASE_FILES = ["Packages", "Packages.gz", "CydiaIcon.png", "CydiaIcon@1x.png",
                 "CydiaIcon@2x.png", "CydiaIcon@3x.png", "RepoIcon.png",
                 "icon.png", "sileo-featured.json"]
ALGOS = [("MD5Sum", "md5"), ("SHA1", "sha1"), ("SHA256", "sha256"), ("SHA512", "sha512")]


def digest(b, algo):
    return hashlib.new(algo, b).hexdigest()


def rebuild_index(stage):
    """Packages 改过之后：重建 Packages.gz + 重写 Release 全部校验和。"""
    pkg = (stage / "Packages").read_bytes()
    with (stage / "Packages.gz").open("wb") as f:
        with gzip.GzipFile(fileobj=f, mode="wb", mtime=0) as g:
            g.write(pkg)

    rel = (stage / "Release").read_text(encoding="utf-8")
    files = [n for n in RELEASE_FILES if (stage / n).exists()]
    blocks = []
    for key, algo in ALGOS:
        lines = [key + ":"]
        for n in files:
            b = (stage / n).read_bytes()
            lines.append(" %s %16d %s" % (digest(b, algo), len(b), n))
        blocks.append("\n".join(lines))

    head = rel.split("MD5Sum:")[0].rstrip("\n")
    head = re.sub(r"^Date:.*$",
                  "Date: " + __import__("email.utils", fromlist=["formatdate"]).formatdate(usegmt=True),
                  head, flags=re.M)
    (stage / "Release").write_text(head + "\n" + "\n".join(blocks) + "\n", encoding="utf-8")
    return len(pkg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origin", default="", help="对外规范域名，如 https://repo.example.com/")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    origin = args.origin.strip()
    if origin and not re.match(r"^https://[A-Za-z0-9.\-]+/$", origin):
        raise SystemExit("--origin 必须是 https://域名/ 形式（结尾要有斜杠）")

    tmp = Path(tempfile.mkdtemp(prefix="cfpages-"))
    stage = tmp / "site"
    stage.mkdir()

    for p in ROOT.rglob("*"):
        if p.is_dir():
            continue
        rel = p.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if p.name in SKIP_FILES or p.suffix in SKIP_SUFFIX:
            continue
        dst = stage / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst)

    if origin:
        # 1) 页面固定对外域名
        for name in PAGES:
            f = stage / name
            s = f.read_text(encoding="utf-8")
            if "PUBLIC_ORIGIN" not in s:
                prefix = "../" if "/" in name else ""
                inject = ('  <script>window.PUBLIC_ORIGIN = %r;</script>\n'
                          % origin)
                # 必须放在 site.js 之前
                marker = '  <script src="%sjs/site.js"></script>\n' % prefix
                if marker in s:
                    s = s.replace(marker, inject + marker, 1)
                else:
                    s = s.replace("</head>", inject + "</head>", 1)
                f.write_text(s, encoding="utf-8")

        # 2) 静态文件里的绝对 URL
        for name in URL_FILES:
            f = stage / name
            if not f.exists():
                continue
            s = f.read_text(encoding="utf-8")
            f.write_text(s.replace(OLD, origin).replace(OLD.rstrip("/"), origin.rstrip("/")),
                         encoding="utf-8")

        n = rebuild_index(stage)
        print("  已固定域名 %s，Packages 重建 %d 字节，Release 校验和已重算" % (origin, n))
    else:
        print("  自适应域名模式（未指定 --origin）")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(stage.rglob("*")):
            if f.is_dir():
                continue
            z.write(f, f.relative_to(stage).as_posix())
            count += 1
    shutil.rmtree(tmp)

    print("  已生成 %s（%d 个文件，%.1f KB）" % (out, count, out.stat().st_size / 1024))
    print("  上传到 CF Pages：Workers & Pages → 创建 → Pages → 直接上传 → 拖入此 zip")


if __name__ == "__main__":
    main()
