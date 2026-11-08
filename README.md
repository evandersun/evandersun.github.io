# Evander's Repo — iOS 越狱源

源地址：**https://evandersun.github.io/**

在 Sileo / Zebra / Cydia / Installer 里添加上面的地址即可。

## 目录结构（flat APT repo）

```
├── Packages / Packages.gz                               包索引（明文 + gzip 两种格式）
├── Release                                              索引校验和（MD5/SHA1/SHA256/SHA512）
├── CydiaIcon.png                                         源图标（猫图，全套 6 个文件名）
├── sileo-featured.json                                   Sileo / Zebra 精选页配置
├── index.html                                            源首页（浏览器访问，含已上传插件列表）
├── admin.html                                            管理页（本页输入密码 → 上传文件 / 上传插件）
├── debs/                                                 .deb 文件
├── zips/                                                 管理页上传的插件原始 zip
├── js/                                                   浏览器端 JS 库（fflate / fzstd / repo-pack / repo-list）
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

   脚本会扫描 `debs/*.deb`，重新生成 `Packages`（含 `Filename`/`Size`/`MD5sum`/`SHA1`/`SHA256`/`SHA512`）、`Packages.gz`、`Release` 校验和，以及源图标。`debs/` 为空时会写出一份空索引。只依赖 `dpkg-deb`、Python 3 标准库和 Pillow，无需 iOS SDK。
3. 提交并推送；GitHub Pages 自动发布。用户在包管理器里刷新源即可。

> 索引压缩格式是「明文 + gzip 两种」。管理页 `admin.html` 在浏览器里重建索引时无法生成 bzip2 / xz，因此脚本也不生成 `.bz2` / `.xz`，两边保持完全一致的 `Release` 结构，客户端不会读到过期索引。

## 管理页上传插件

点击首页底部的 **admin登录** 会先跳转到 `admin.html`，在该页输入管理员密码后才会显示管理功能；然后在「上传插件」卡片里选一个 **zip**：

- zip 的**文件名即插件名**，例如 `MyTweak.zip`
- zip 内固定两个文件：`arm64.deb`（rootless 包）和 `arm64e.deb`（roothide 包）；放在一层子目录里也能识别，`__MACOSX` 等垃圾文件会自动忽略
- 管理页在浏览器本地解压、读取两个 deb 的 control，然后把 deb 放进 `debs/`、原 zip 存进 `zips/`，并**自动重建** `Packages` / `Packages.gz` / `Release`，所有文件一次原子提交到仓库

提交后约 10–60 秒 GitHub Pages 发布完成，包管理器刷新源即可看到新插件。上传同名 zip 会覆盖该插件的两个 deb（用于更新版本）；下方「已收录插件」列表可查看或删除已上传的插件，删除后索引同样自动重建。整个过程不需要服务器，也不需要 `workflow` 权限的令牌。

> `js/repo-pack.js` 在浏览器里同时挂载 `window.RepoPack` 与别名 `window.RP`（管理页统一用 `RP.*` 调用），Node 下走 `module.exports` 便于跑测试；三个浏览器库都不依赖 CDN。

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

## 首页「已上传插件」列表

首页会同源读取 `Packages` 索引，把每个插件的 arm64 / arm64e 两条记录合并成一行，展示插件名、版本、包名、简介与支持的架构。列表不需要令牌，也不调用 GitHub API；上传插件后约 10–60 秒 Pages 发布新索引，点列表右上角「刷新」即可看到。索引为空时显示「暂无插件」。解析逻辑在 `js/repo-list.js`，是浏览器 / Node 双用的纯函数，无网络请求与 DOM 依赖。

> 管理员密码只在 `admin.html` 内校验；首页的 admin登录 按钮只是一个跳转链接，页面里不含任何密码。

## 精选页

`sileo-featured.json` 采用官方 `FeaturedBannersView` 结构（`itemSize` / `itemCornerRadius` / `banners`）。往 `banners` 里加条目即可在 Sileo / Zebra 精选页顶部展示卡片，每条用 `url` 指定 16:9 图片、`package` 指定点击后跳转的包。
