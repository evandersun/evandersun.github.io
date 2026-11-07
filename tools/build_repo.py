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
ASSET_VER = "v=3"   # 图片 URL 版本戳；换图标/头像时递增，穿透包管理器/CDN 缓存
# v=3：插件图标 assets/icon.png 由猫图改回几何时钟（源图标字节不变），
#       并新增精选置顶横幅；必须换戳，否则客户端一直显示缓存里的旧猫图。
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

    源图标（CydiaIcon 全套）用自定义头像猫图；插件图标 assets/icon.png
    恒为几何时钟，两者互不牵连。产物尺寸按客户端实际显示需求定：
      CydiaIcon.png  256x256  源列表头像（猫图，保持不变）
      assets/icon.png 240x240  插件图标（几何时钟，包列表/包详情页显示）
      assets/banner.png         depiction 头部横幅（左侧贴 240 圆角源头像）
      assets/featured*.png      Sileo / Zebra 精选页置顶横幅（1200x675, 16:9）
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

    # 几何时钟「原来那个时钟」：自本次改版起固定作为**插件图标**，与源头像
    # 彻底解耦。之前 clock() 只定义在 else 分支里（没有自定义头像时才存在），
    # 这里提到分支外，保证「源图标用猫图 + 插件图标用时钟」能同时成立。
    def clock(size, radius_ratio=0.34):
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
        banner_icon = avatar.resize((240, 240), Image.LANCZOS)
        print("  -> 源图标：保持 assets/repo-avatar-source.jpg 猫图（全套 6 个文件名，字节不变）")
    else:
        save_icon_set(clock)
        banner_icon = clock(240)
        print("  -> 未找到自定义头像，源图标回退几何时钟")

    # 插件图标恒为几何时钟，与源图标（猫图）互不牵连。
    # 内容由猫图变回时钟，ASSET_VER 已递增到 v=3，穿透客户端旧缓存。
    clock(240).save(ASSETS / "icon.png", "PNG", optimize=True)
    print("  -> 插件图标 assets/icon.png：几何时钟（源图标仍为猫图，字节不变）")

    # depiction 头部横幅（左侧仍贴源头像，保持源的视觉一致性）
    W, H = 960, 360
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / (H - 1)
        d.line([(0, y), (W, y)], fill=(int(20 + 16 * t), int(36 + 28 * t), int(70 + 48 * t)))
    im.paste(banner_icon, (44, (H - 240) // 2), round_mask(240, 0.18))
    d.text((330, 78), "ScreenTimeSpoofer", font=bold, fill=(255, 255, 255))
    d.text((332, 178), "Spoof your Screen Time", font=reg, fill=(160, 195, 255))
    d.text((332, 258), "roothide  /  rootless  ·  v0.6.4", font=small,
           fill=(120, 150, 200))
    im.save(ASSETS / "banner.png")
    print("  -> CydiaIcon.png + @1x/@2x/@3x / RepoIcon.png / icon.png / assets/icon.png / banner.png")



def make_featured():
    """生成 Sileo / Zebra 精选页顶部的置顶横幅卡片（16:9）。

    Sileo 官方要求 16:9（推荐 1920x1080），这里用 1200x675 兼顾 Pages 体积。
    卡片白色大标题由 sileo-featured.json 的 title 字段叠加渲染，所以图片里
    只放渐变背景 + 装饰图形 + 右下角小角标，不放主文字，避免与叠加标题重复。
    点击行为由 json 的 package 字段决定：直达 ScreenTimeSpoofer 包详情。
    """
    if Image is None:
        print("  ! 未装 Pillow，跳过精选横幅生成")
        return
    ASSETS.mkdir(exist_ok=True)
    import math

    def font(name, size):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            return ImageFont.load_default()

    small = font("DejaVuSans.ttf", 24)

    def gradient(top, bottom):
        W, H = 1200, 675
        im = Image.new("RGB", (W, H))
        d = ImageDraw.Draw(im)
        for y in range(H):
            t = y / (H - 1)
            d.line([(0, y), (W, y)],
                   fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
        return im, d

    def halo(d, cx, cy, r, col):
        # 同心圆光晕：纯几何装饰，放左侧留白区，不与右侧时钟抢视觉。
        # 刻意不用五角星——那容易被误读成旗帜，插件横幅只需要时钟主题。
        for k in (1.0, 0.78, 0.56, 0.34):
            rr = int(r * k)
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=col,
                      width=max(2, int(r * 0.016)))
        d.ellipse([cx - int(r * 0.05), cy - int(r * 0.05),
                   cx + int(r * 0.05), cy + int(r * 0.05)], fill=col)

    def clock_glyph(d, cx, cy, r, col, width):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=width)
        for i in range(12):
            a = math.pi * 2 * i / 12 - math.pi / 2
            r1, r2 = int(r * 0.80), int(r * 0.94)
            d.line([(cx + r1 * math.cos(a), cy + r1 * math.sin(a)),
                    (cx + r2 * math.cos(a), cy + r2 * math.sin(a))],
                   fill=col, width=max(2, width // 2))
        d.line([(cx, cy), (cx + int(r * 0.50 * math.cos(-math.pi / 3)),
                           cy + int(r * 0.50 * math.sin(-math.pi / 3)))],
               fill=col, width=width)
        d.line([(cx, cy), (cx + int(r * 0.74 * math.cos(math.pi / 6)),
                           cy + int(r * 0.74 * math.sin(math.pi / 6)))],
               fill=col, width=max(2, width // 2))
        d.ellipse([cx - width, cy - width, cx + width, cy + width], fill=col)

    # ① 主推卡片：红 → 深红渐变（呼应截图里的红色精选卡）+ 光晕 + 白色大时钟
    im, d = gradient((216, 52, 62), (118, 12, 28))
    halo(d, 300, 310, 220, (198, 96, 104))
    for (x, y, rr) in [(140, 130, 7), (486, 176, 5), (196, 500, 6), (528, 466, 4)]:
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(255, 196, 196))
    clock_glyph(d, 900, 320, 168, (255, 255, 255), 11)
    d.text((866, 618), "Evander's Repo  ·  v0.6.4", font=small,
           fill=(255, 214, 214))
    im.save(ASSETS / "featured.png", "PNG", optimize=True)

    # ② 次卡片：深蓝 → 紫渐变 + 蓝色时钟 + 星点，对应「QQ群 / 更新日志」标题
    im2, d2 = gradient((26, 58, 122), (12, 16, 48))
    for i in range(40):
        a = i * 2.39996
        rr = 60 + i * 22
        x = 600 + int(rr * math.cos(a) * 0.9)
        y = 330 + int(rr * math.sin(a) * 0.7)
        if 0 <= x < 1200 and 0 <= y < 675:
            d2.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(120, 170, 255))
    clock_glyph(d2, 900, 320, 168, (150, 200, 255), 11)
    d2.text((848, 618), "QQ 1135135953  ·  v0.6.4", font=small,
            fill=(150, 190, 255))
    im2.save(ASSETS / "featured-group.png", "PNG", optimize=True)
    print("  -> assets/featured.png / featured-group.png（1200x675, 16:9）")


def main():
    print("== 扫描 debs/ ==")
    debs = write_packages()
    print("== 生成图标 ==")
    make_assets()
    print("== 生成精选置顶横幅 ==")
    make_featured()
    print("== 生成 Release ==")
    write_release(debs)
    print("完成。源地址：%s/" % BASE_URL)


if __name__ == "__main__":
    main()
