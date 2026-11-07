# Evander's Repo — iOS 越狱源

源地址：**https://evandersun.github.io/**

在 Sileo / Zebra / Cydia / Installer 里添加上面的地址即可。

## 目录结构（flat APT repo）

```
├── Packages / Packages.gz / Packages.bz2 / Packages.xz   包索引（四种格式）
├── Release                                              索引校验和（MD5/SHA1/SHA256/SHA512）
├── CydiaIcon.png                                         源图标（猫图，全套 6 个文件名）
├── sileo-featured.json                                   Sileo / Zebra 精选页配置
├── index.html                                            源首页（浏览器访问）
├── debs/                                                 .deb 文件
├── assets/                                               源头像原图
├── .nojekyll                                             让 GitHub Pages 原样发布
└── tools/build_repo.py                                   重新生成索引与图标
```

## 更新源（加新版本 / 加新包）

1. 把新的 `.deb` 放进 `debs/`，删掉要下架的旧 `.deb`。
2. 在仓库根目录运行：

   ```sh
   python3 tools/build_repo.py
   ```

   脚本会扫描 `debs/*.deb`，重新生成 `Packages`（含 `Filename`/`Size`/`MD5sum`/`SHA1`/`SHA256`/`SHA512`）、四种压缩格式、`Release` 校验和，以及源图标。`debs/` 为空时会写出一份空索引。只依赖 `dpkg-deb`、Python 3 标准库和 Pillow，无需 iOS SDK。
3. 提交并推送；GitHub Pages 自动发布。用户在包管理器里刷新源即可。

> 换域名时改 `tools/build_repo.py` 顶部的 `BASE_URL`，以及 `index.html` 里的绝对 URL。

## 源图标

源图标由 `tools/build_repo.py` 生成，取自 `assets/repo-avatar-source.jpg`（猫图），并同时输出各客户端会读取的全部文件名：

| 文件 | 尺寸 | 谁读 |
|---|---|---|
| `CydiaIcon.png` | 256×256 | Cydia / Sileo / Zebra 主图标 |
| `CydiaIcon@1x.png` | 64×64 | Cydia 传统密度 |
| `CydiaIcon@2x.png` | 128×128 | **Sileo 优先读这个**、Zebra 高密度 |
| `CydiaIcon@3x.png` | 192×192 | 高分屏 |
| `RepoIcon.png` / `icon.png` | 192×192 | Installer / 部分网页端 |

- 换源头像：把图片存成 **`assets/repo-avatar-source.jpg`**，重跑脚本即可。
- 删掉 `assets/repo-avatar-source.jpg` 则回退到内置的几何时钟图标。
- 运行脚本会重刷全套图标、`Packages` 与 `Release` 校验和。

> `Release` 里记录了各图标的 MD5/SHA1/SHA256/SHA512，只替换图片不刷新索引会导致校验和不匹配。
>
> **客户端会长期缓存源图标**。脚本顶部的 `ASSET_VER`（当前 `v=3`）是图片 URL 版本戳，换头像时递增这个值可穿透缓存。若包管理器里仍显示旧图标，最彻底的办法是**删除该源后重新添加** —— 新加的 `@2x` 等文件名没有历史缓存，会直接拉到新图。

## 精选页

`sileo-featured.json` 采用官方 `FeaturedBannersView` 结构（`itemSize` / `itemCornerRadius` / `banners`）。往 `banners` 里加条目即可在 Sileo / Zebra 精选页顶部展示卡片，每条用 `url` 指定 16:9 图片、`package` 指定点击后跳转的包。
