# Evander's Repo — iOS 越狱源

源地址：**https://evandersun.github.io/**

在 Sileo / Zebra / Cydia / Installer 里添加上面的地址，搜索 `ScreenTimeSpoofer` 安装。

## 收录的包

| 包 | 版本 | 架构 | 适用越狱 |
|---|---|---|---|
| `com.evander.screentimespoofer` | 0.6.3 | `iphoneos-arm64e` | **roothide**（Dopamine RootHide 等隐根） |
| `com.evander.screentimespoofer` | 0.6.3 | `iphoneos-arm64` | **rootless**（Dopamine / palera1n） |

两个包同名不同架构，包管理器会按设备架构自动选对那个。

## 目录结构（flat APT repo）

```
├── Packages / Packages.gz / Packages.bz2 / Packages.xz   包索引（四种格式）
├── Release                                              索引校验和（MD5/SHA1/SHA256/SHA512）
├── CydiaIcon.png                                         源图标
├── sileo-featured.json                                   Sileo 精选横幅
├── index.html                                            源首页（浏览器访问）
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

## 源码与 Release

插件源码、构建脚本与历史版本在 [github.com/evandersun/ScreenTimeSpoofer](https://github.com/evandersun/ScreenTimeSpoofer)。
