#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_repo.py —— 生成/刷新 iOS 越狱源（flat APT repo）的 Packages / Release / 图标。

用法（在本文件所在仓库的根目录执行）：
    python3 tools/build_repo.py

流程：
  1. 扫描 debs/*.deb，读每个包的 control 字段
  2. 追加 Filename / Size / MD5sum / SHA1 / SHA256 / SHA512 / Depiction 等字段
  3. 写出 Packages 及 .gz / .bz2 / .xz 四种格式
  4. 计算各索引文件的校验和，写出 Release
  5. 生成源图标、包图标、Sileo 横幅（仅需 Pillow）

新增或更新 deb 时：把新 deb 丢进 debs/，删掉旧 deb，重跑本脚本即可。
只依赖：dpkg-deb、Python 3 标准库、Pillow。无 iOS SDK 也能在任意 Linux 上跑。
"""
import os
import io
import sys
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
ASSET_VER = "v=2"   # 图片 URL 版本戳；换头像时递增，穿透包管理器/CDN 缓存
REPO_NAME = "Evander's Repo"
REPO_LABEL = "Evander's Repo"
REPO_DESC = "ScreenTimeSpoofer —— 修改「屏幕使用时间」显示的时长"

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
    size = len(data)
    arch = field(raw, "Architecture")
    # 让用户在包详情里能一眼看出该装哪个变体
    flavor = "roothide（隐根 / Dopamine RootHide）" if arch.endswith("arm64e") \
        else "rootless（Dopamine / palera1n）"
    desc = field(raw, "Description")
    if flavor not in desc:
        desc = "%s · %s" % (desc, flavor)

    lines = []
    for line in raw.splitlines():
        if line.startswith("Description:"):
            lines.append("Description: " + desc)
        else:
            lines.append(line)

    lines += [
        "Filename: debs/" + relname,
        "Size: %d" % size,
        "MD5sum: " + digest(data, "md5"),
        "SHA1: " + digest(data, "sha1"),
        "SHA256: " + digest(data, "sha256"),
        "SHA512: " + digest(data, "sha512"),
        "Depiction: %s/depiction/screentimespoofer.html" % BASE_URL,
        "SileoDepiction: %s/depiction/screentimespoofer.json" % BASE_URL,
        "Icon: %s/assets/icon.png?%s" % (BASE_URL, ASSET_VER),
        "Tag: role::hacker, compatible::ios15+",
    ]
    return "\n".join(lines) + "\n"


def write_packages():
    debs = sorted(DEBS.glob("*.deb"))
    if not debs:
        sys.exit("错误：debs/ 下没有 .deb")
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
    index_files = ["Packages", "Packages.gz", "Packages.bz2", "Packages.xz",
                   "CydiaIcon.png", "CydiaIcon@1x.png", "CydiaIcon@2x.png",
                   "CydiaIcon@3x.png", "RepoIcon.png", "icon.png",
                   "sileo-featured.json", "depiction/screentimespoofer.json"]
    sums = {}
    for algo in ("md5", "sha1", "sha256", "sha512"):
        sums[algo] = []
        for name in index_files:
            p = ROOT / name
            if not p.exists():
                continue
            b = p.read_bytes()
            sums[algo].append(" %s %16d %s" % (digest(b, algo), len(b), name))

    archs = sorted({field(control_of(d), "Architecture") for d in debs})
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
    print("  -> Release  (architectures: %s)" % ", ".join(archs))


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


def round_mask(size, ratio=0.18):
    """生成 L 模式圆角遮罩，用于把方形头像贴到横幅上。"""
    k = 4
    big = size * k
    m = Image.new("L", (big, big), 0)
    d = ImageDraw.Draw(m)
    r = int(big * ratio)
    try:
        d.rounded_rectangle([0, 0, big - 1, big - 1], radius=r, fill=255)
    except (AttributeError, TypeError):
        r0 = int(big * ratio)
        d.rectangle([r0, 0, big - r0, big], fill=255)
        d.rectangle([0, r0, big, big - r0], fill=255)
        d.ellipse([0, 0, r0 * 2, r0 * 2], fill=255)
        d.ellipse([big - r0 * 2, 0, big, r0 * 2], fill=255)
        d.ellipse([0, big - r0 * 2, r0 * 2, big], fill=255)
        d.ellipse([big - r0 * 2, big - r0 * 2, big, big], fill=255)
    return m.resize((size, size), Image.LANCZOS)


def make_assets():
    """生成源图标 / 包图标 / Sileo 横幅。

    有 assets/repo-avatar-source.jpg 时用自定义头像（猫图）；
    否则回退到原来的几何时钟图标。三种产物尺寸都按客户端实际显示需求定：
      CydiaIcon.png  256x256  Cydia / Sileo / Zebra 的源列表头像
      assets/icon.png 240x240  首页、包详情页
      assets/banner.png         Sileo 精选横幅（左侧贴 240 圆角头像）
    """
    if Image is None:
        print("  ! 未装 Pillow，跳过图标生成（不影响源可用性）")
        return

    ASSETS.mkdir(exist_ok=True)
    import math

    def font(name, size):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            return ImageFont.load_default()

    bold = font("DejaVuSans-Bold.ttf", 58)
    reg = font("DejaVuSans.ttf", 40)
    small = font("DejaVuSans.ttf", 26)

    avatar = load_avatar_square()

    # 各客户端读的图标文件名并不相同：Cydia 用 CydiaIcon.png / @1x，
    # Sileo 优先 @2x，Zebra 自适应，Installer 用 RepoIcon.png / icon.png。
    # 全部用同一张猫图生成；这些新文件名此前不存在，客户端没有历史缓存，
    # 能直接穿透「换图标不生效」的缓存问题。图标都不加圆角（客户端自己渲染）。
    ICON_SET = [("CydiaIcon.png", 256), ("CydiaIcon@1x.png", 64),
                ("CydiaIcon@2x.png", 128), ("CydiaIcon@3x.png", 192),
                ("RepoIcon.png", 192), ("icon.png", 192)]

    def save_icon_set(render):
        for name, sz in ICON_SET:
            render(sz).save(ROOT / name, "PNG", optimize=True)

    if avatar is not None:
        save_icon_set(lambda sz: avatar.resize((sz, sz), Image.LANCZOS))
        avatar.resize((240, 240), Image.LANCZOS).save(ASSETS / "icon.png",
                                                      "PNG", optimize=True)
        banner_icon = avatar.resize((240, 240), Image.LANCZOS)
        print("  -> 使用 assets/repo-avatar-source.jpg 自定义头像（全套 6 个图标文件名）")
    else:
        def clock(size, radius_ratio=0.34):
            im = Image.new("RGB", (size, size), (0, 0, 0))
            d = ImageDraw.Draw(im)
            for y in range(size):
                t = y / max(1, size - 1)
                d.line([(0, y), (size, y)],
                       fill=(int(18 + 12 * t), int(30 + 22 * t), int(58 + 40 * t)))
            m = int(size * 0.10)
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

        save_icon_set(clock)
        clock(120).save(ASSETS / "icon.png")
        banner_icon = clock(240)
        print("  -> 未找到自定义头像，使用内置几何图标")

    # Sileo 精选横幅 / 包详情 header
    W, H = 960, 360
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / (H - 1)
        d.line([(0, y), (W, y)], fill=(int(20 + 16 * t), int(36 + 28 * t), int(70 + 48 * t)))
    im.paste(banner_icon, (44, (H - 240) // 2), round_mask(240, 0.18))
    d.text((330, 78), "ScreenTimeSpoofer", font=bold, fill=(255, 255, 255))
    d.text((332, 178), "Spoof your Screen Time", font=reg, fill=(160, 195, 255))
    d.text((332, 258), "roothide  /  rootless  ·  v0.6.3", font=small,
           fill=(120, 150, 200))
    im.save(ASSETS / "banner.png")
    print("  -> CydiaIcon.png + @1x/@2x/@3x / RepoIcon.png / icon.png / assets/icon.png / banner.png")


def main():
    print("== 扫描 debs/ ==")
    debs = write_packages()
    print("== 生成图标 ==")
    make_assets()
    print("== 生成 Release ==")
    write_release(debs)
    print("完成。源地址：%s/" % BASE_URL)


if __name__ == "__main__":
    main()
