# Evander's Repo — iOS 越狱源

源地址：**https://evandersun.github.io/**

在 Sileo / Zebra / Cydia / Installer 里添加上面的地址，搜索 `ScreenTimeSpoofer` 安装。

## 收录的包

| 包 | 版本 | 架构 | 适用越狱 |
|---|---|---|---|
| `com.evander.screentimespoofer` | 0.6.4 | `iphoneos-arm64e` | **roothide**（Dopamine RootHide 等隐根） |
| `com.evander.screentimespoofer` | 0.6.4 | `iphoneos-arm64` | **rootless**（Dopamine / palera1n） |

两个包同名不同架构，包管理器会按设备架构自动选对那个。

## 目录结构（flat APT repo）

```
├── Packages / Packages.gz / Packages.bz2 / Packages.xz   包索引（四种格式）
├── Release                                              索引校验和（MD5/SHA1/SHA256/SHA512）
├── CydiaIcon.png                                         源图标（猫图，全套 6 个文件名）
├── sileo-featured.json                                   Sileo / Zebra 精选置顶横幅
├── index.html                                            源首页（浏览器访问）
├── CHANGELOG.md / changelog.html                         更新日志（仓库文档 / 网页版）
├── debs/                                                 .deb 文件
├── assets/                                               图标与横幅
├── depiction/                                            包详情页（HTML + Sileo JSON）
├── .nojekyll                                             让 GitHub Pages 原样发布
└── tools/build_repo.py                                   重新生成索引与图标
```

## 更新源（加新版本 / 加新包）

1. 把新的 `.deb` 放进 `debs/`，删掉要下架的旧 `.deb`。
2. 在仓库根目录运行：

   ```sh
   python3 tools/build_repo.py
   ```

   脚本会扫描 `debs/*.deb`，重新生成 `Packages`（含 `Filename`/`Size`/`MD5sum`/`SHA1`/`SHA256`/`SHA512`）、四种压缩格式、`Release` 校验和，以及图标。只依赖 `dpkg-deb`、Python 3 标准库和 Pillow，无需 iOS SDK。
3. 提交并推送；GitHub Pages 自动发布。用户在包管理器里刷新源即可。

> 换域名时改 `tools/build_repo.py` 顶部的 `BASE_URL`，以及 `index.html` / `depiction/` 里的绝对 URL。

## 图标：源图标与插件图标是两套

两者由 `tools/build_repo.py` 生成，但**互不牵连**：

| 角色 | 文件 | 内容 | 谁读 |
|---|---|---|---|
| **源图标 / 源头像** | `CydiaIcon.png` 全套 6 个 + 根 `icon.png` | 自定义猫图 | 软件源列表、`Release` 的 `Icon`、源首页 |
| **插件图标** | `assets/icon.png`（240×240） | **几何时钟** | 包列表、`Packages` 的 `Icon`、包详情页 |
| 头部横幅 | `assets/banner.png` | 蓝色渐变 + 左侧源头像 | depiction headerImage |
| 精选置顶横幅 | `assets/featured.png` / `featured-group.png`（16:9） | 红 / 蓝渐变 + 时钟 | `sileo-featured.json` |

- 换源头像：把图片存成 **`assets/repo-avatar-source.jpg`**，重跑脚本即可；插件图标始终仍是几何时钟。
- 删掉 `assets/repo-avatar-source.jpg` 则源图标也回退到几何时钟。
- 运行 `python3 tools/build_repo.py` 会重刷全套图标、置顶横幅、`Packages` 与 `Release` 校验和。

各客户端读的图标文件名并不相同，所以必须全给：

| 文件 | 尺寸 | 谁读 |
|---|---|---|
| `CydiaIcon.png` | 256×256 | Cydia / Sileo / Zebra 主图标 |
| `CydiaIcon@1x.png` | 64×64 | Cydia 传统密度 |
| `CydiaIcon@2x.png` | 128×128 | **Sileo 优先读这个**、Zebra 高密度 |
| `CydiaIcon@3x.png` | 192×192 | 高分屏 |
| `RepoIcon.png` / `icon.png` | 192×192 | Installer / 部分网页端 |

> 换头像后**必须重跑脚本**：`Release` 里记录了各图标的 MD5/SHA1/SHA256/SHA512，只替换图片不刷新索引会导致校验和不匹配。
>
> **客户端会长期缓存源图标**。脚本顶部的 `ASSET_VER`（当前 `v=3`）是图片 URL 版本戳，`index.html` / `depiction/` / `sileo-featured.json` 里的图片 URL 都带它；换头像时递增这个值可穿透缓存。若包管理器里仍显示旧图标，最彻底的办法是**删除该源后重新添加** —— 新加的 `@2x` 等文件名没有历史缓存，会直接拉到新图。

## 精选置顶与更新日志

- `sileo-featured.json` 用官方 `FeaturedBannersView` 结构（`itemSize` / `itemCornerRadius` / `banners[url,title,package,hideShadow]`）。`package` 指向包名，点击卡片直达插件详情页；两张 16:9 卡片可横向滑动。此前 `class` 误写成 `FeaturedBannerView` 且缺 `itemSize`，卡片一直不显示。
- 版本历史写在 `CHANGELOG.md`，网页版 `changelog.html`，首页有「最近更新」摘要，包详情的「更新记录」tab 也同步。

## 源码与 Release

插件源码、构建脚本与历史版本在 [github.com/evandersun/ScreenTimeSpoofer](https://github.com/evandersun/ScreenTimeSpoofer)。
