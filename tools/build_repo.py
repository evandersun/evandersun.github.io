#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_repo.py —— 生成/刷新 iOS 越狱源（flat APT repo）的 Packages / Release / 源图标。

用法（在本文件所在仓库的根目录执行）：
    python3 tools/build_repo.py

流程：
  1. 扫描 debs/*.deb，读每个包的 control 字段
  2. 追加 Filename / Size / MD5sum / SHA1 / SHA256 / SHA512
  3. 写出 Packages 及 .gz / .bz2 / .xz 四种格式（debs/ 为空时写出空索引）
  4. 计算各索引文件与图标的校验和，写出 Release
  5. 由 assets/repo-avatar-source.jpg 生成全套源图标（仅需 Pillow）

新增或更新 deb 时：把新 deb 丢进 debs/，删掉旧 deb，重跑本脚本即可。
control 里自带的 Depiction / Icon / Tag 等字段会原样保留，本脚本不硬编码
任何包专属 URL，因此对任意包都通用。
只依赖：dpkg-deb、Python 3 标准库、Pillow。无 iOS SDK 也能在任意 Linux 上跑。
"""
import sys
import io
import gzip
import bz2
import lzma
import hashlib
import subprocess
import email.utils
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:          # 没装 Pillow 时跳过图标生成，不影响源可用性
    Image = ImageDraw = ImageFont = None

# 源对外 URL；换域名/换托管时只改这一处
BASE_URL = "https://evandersun.github.io"
ASSET_VER = "v=3"   # 图片 URL 版本戳；换图标/头像时递增，穿透包管理器/CDN 缓存
REPO_NAME = "Evander's Repo"
REPO_LABEL = "Evander's Repo"
REPO_DESC = "Evander's Repo — iOS 越狱源"

ROOT = Path(__file__).resolve().parent.parent
DEBS = ROOT / "debs"
ASSETS = ROOT / "assets"


def sh(*args):
    return subprocess.check_output(args, stderr=subprocess.STDOUT).decode("utf-8", "replace")


def control_of(deb):
    """返回 deb 的完整 control 文本（dpkg-deb -f 不带字段名即输出全部）。"""
    return sh("dpkg-deb", "-f", str(deb)).rstrip("\n")


def field(control, name):
    for line in control.splitlines():
        if line.startswith(name + ":"):
            return line.split(":", 1)[1].strip()
    return ""


def digest(data, algo):
    h = hashlib.new(algo)
    h.update(data)
    return h.hexdigest()


def make_stanza(deb, relname):
    raw = control_of(deb)
    data = deb.read_bytes()
    # control 原文完整保留（含包自己声明的 Depiction / Icon / Tag 等字段），
    # 只追加 flat repo 必需的定位与校验字段。
    lines = list(raw.splitlines())
    lines += [
        "Filename: debs/" + relname,
        "Size: %d" % len(data),
        "MD5sum: " + digest(data, "md5"),
        "SHA1: " + digest(data, "sha1"),
        "SHA256: " + digest(data, "sha256"),
        "SHA512: " + digest(data, "sha512"),
    ]
    return "\n".join(lines) + "\n"


def write_packages():
    debs = sorted(DEBS.glob("*.deb"))
    if not debs:
        print("  ! debs/ 为空，写出空索引")
    stanzas = []
    for d in debs:
        stanzas.append(make_stanza(d, d.name))
        print("  + %-62s %7d bytes  [%s]" % (
            d.name, d.stat().st_size, field(control_of(d), "Architecture")))
    pkg = "\n".join(stanzas).encode("utf-8")

    (ROOT / "Packages").write_bytes(pkg)
    with (ROOT / "Packages.gz").open("wb") as f:
        with gzip.GzipFile(fileobj=f, mode="wb", mtime=0) as g:
            g.write(pkg)
    (ROOT / "Packages.bz2").write_bytes(bz2.compress(pkg, 9))
    (ROOT / "Packages.xz").write_bytes(lzma.compress(pkg, format=lzma.FORMAT_XZ, preset=9))
    print("  -> Packages / .gz / .bz2 / .xz  (%d bytes 明文)" % len(pkg))
    return debs


def write_release(debs):
    # 只记录实际存在的文件；增删页面/图标后无需改这里
    candidates = ["Packages", "Packages.gz", "Packages.bz2", "Packages.xz",
                  "CydiaIcon.png", "CydiaIcon@1x.png", "CydiaIcon@2x.png",
                  "CydiaIcon@3x.png", "RepoIcon.png", "icon.png",
                  "sileo-featured.json"]
    index_files = [n for n in candidates if (ROOT / n).exists()]
    sums = {}
    for algo in ("md5", "sha1", "sha256", "sha512"):
        sums[algo] = []
        for name in index_files:
            b = (ROOT / name).read_bytes()
            sums[algo].append(" %s %16d %s" % (digest(b, algo), len(b), name))

    archs = sorted({field(control_of(d), "Architecture") for d in debs})
    if not archs:
        archs = ["iphoneos-arm"]
    if "iphoneos-arm" not in archs:
        archs.insert(0, "iphoneos-arm")

    out = [
        "Origin: " + REPO_NAME,
        "Label: " + REPO_LABEL,
        "Suite: stable",
        "Version: 1.0",
        "Codename: stable",
        "Architectures: " + " ".join(archs),
        "Components: main",
        "Description: " + REPO_DESC,
        "Icon: file://CydiaIcon.png",
        "Date: " + email.utils.formatdate(usegmt=True),
    ]
    for key, algo in (("MD5Sum", "md5"), ("SHA1", "sha1"),
                      ("SHA256", "sha256"), ("SHA512", "sha512")):
        out.append(key + ":")
        out.extend(sums[algo])
    (ROOT / "Release").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("  -> Release  (%d 个文件 × 4 种校验和, architectures: %s)" %
          (len(index_files), ", ".join(archs)))


def load_avatar_square():
    """把 assets/repo-avatar-source.jpg 裁成聚焦猫脸+帽子的正方形。

    原图是 1440x1832 竖图：帽子顶约在 12% 处、猫脸在 35%~65% 处，
    下方全是毛衣。取宽度的 76% 作边长、垂直起点 9.5%，正好把帽子和
    整张脸装进方形，避免头像里猫脸太小。
    返回 RGB Image；没有自定义头像时返回 None（回退到几何时钟图标）。
    """
    src = ASSETS / "repo-avatar-source.jpg"
    if not src.exists():
        return None
    im = Image.open(src).convert("RGB")
    w, h = im.size
    side = min(int(w * 0.76), h)
    x0 = (w - side) // 2
    y0 = int(h * 0.095)
    y0 = max(0, min(y0, h - side))
    return im.crop((x0, y0, x0 + side, y0 + side))


def make_assets():
    """生成全套源图标。

    各客户端读的图标文件名并不相同：Cydia 用 CydiaIcon.png / @1x，
    Sileo 优先 @2x，Zebra 自适应，Installer 用 RepoIcon.png / icon.png。
    全部由同一张头像生成；图标都不加圆角（客户端自己渲染）。
    """
    if Image is None:
        print("  ! 未装 Pillow，跳过图标生成（不影响源可用性）")
        return

    import math

    def clock(size, radius_ratio=0.34):
        """无自定义头像时的回退图标：几何时钟。"""
        im = Image.new("RGB", (size, size), (0, 0, 0))
        d = ImageDraw.Draw(im)
        for y in range(size):
            t = y / max(1, size - 1)
            d.line([(0, y), (size, y)],
                   fill=(int(18 + 12 * t), int(30 + 22 * t), int(58 + 40 * t)))
        cx = cy = size // 2
        r = int(size * radius_ratio)
        d.ellipse([cx - r, cy - r, cx + r, cy + r],
                  outline=(235, 242, 255), width=max(2, int(size * 0.035)))
        for i in range(12):
            a = math.pi * 2 * i / 12 - math.pi / 2
            r1, r2 = int(r * 0.78), int(r * 0.92)
            d.line([(cx + r1 * math.cos(a), cy + r1 * math.sin(a)),
                    (cx + r2 * math.cos(a), cy + r2 * math.sin(a))],
                   fill=(150, 180, 235), width=max(1, int(size * 0.012)))
        d.line([(cx, cy), (cx + int(r * 0.50 * math.cos(-math.pi / 3)),
                           cy + int(r * 0.50 * math.sin(-math.pi / 3)))],
               fill=(255, 255, 255), width=max(2, int(size * 0.030)))
        d.line([(cx, cy), (cx + int(r * 0.72 * math.cos(math.pi / 6)),
                           cy + int(r * 0.72 * math.sin(math.pi / 6)))],
               fill=(105, 200, 255), width=max(2, int(size * 0.024)))
        d.ellipse([cx - int(size * 0.02), cy - int(size * 0.02),
                   cx + int(size * 0.02), cy + int(size * 0.02)],
                  fill=(255, 255, 255))
        return im

    ICON_SET = [("CydiaIcon.png", 256), ("CydiaIcon@1x.png", 64),
                ("CydiaIcon@2x.png", 128), ("CydiaIcon@3x.png", 192),
                ("RepoIcon.png", 192), ("icon.png", 192)]

    avatar = load_avatar_square()
    if avatar is not None:
        for name, sz in ICON_SET:
            avatar.resize((sz, sz), Image.LANCZOS).save(ROOT / name, "PNG", optimize=True)
        print("  -> 源图标：assets/repo-avatar-source.jpg 猫图（全套 6 个文件名）")
    else:
        for name, sz in ICON_SET:
            clock(sz).save(ROOT / name, "PNG", optimize=True)
        print("  -> 未找到自定义头像，源图标回退几何时钟")


def main():
    print("== 扫描 debs/ ==")
    debs = write_packages()
    print("== 生成源图标 ==")
    make_assets()
    print("== 生成 Release ==")
    write_release(debs)
    print("完成。源地址：%s/" % BASE_URL)


if __name__ == "__main__":
    main()
