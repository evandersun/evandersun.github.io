/*
 * js/site.js — 站点地址统一模块（Cloudflare Pages / GitHub Pages / 自定义域名通用）
 *
 * 同一个仓库同时部署在多个平台时，页面里的源地址、包管理器深链、
 * 详情页绝对 URL 不能写死。这里把它们分成两类：
 *
 *   Site.root        读取本站资源用：始终跟随当前访问的域名（同源，不会跨域）
 *   Site.publicRoot  对外展示 / 让用户添加源用：默认等于 Site.root；
 *                    有自有域名并做了优选 IP 后，在 <head> 里提前写一行
 *                    window.PUBLIC_ORIGIN = 'https://你的域名/'; 即可全局切换。
 *
 * 注意：后台写入目标永远是 GitHub 仓库（admin.html 的 REPO / API / CDN_LIST），
 * 跟页面托管在哪无关；只要 CF Pages 用 Git 集成连这个仓库，写入会自动触发重新部署。
 */
(function (global) {
  'use strict';

  var REPO_ROOT = 'https://evandersun.github.io/';   // 数据写入 / CDN 回源的根
  var FALLBACK  = REPO_ROOT;                          // file:// 本地预览时的兜底
  var loc       = global.location;

  var root = FALLBACK;
  if (loc && loc.protocol !== 'file:') {
    root = loc.origin + '/';
  }
  if (global.SITE_ROOT_OVERRIDE) root = global.SITE_ROOT_OVERRIDE;   // 部署在子路径时用

  var publicRoot = global.PUBLIC_ORIGIN || root;
  if (!/\/$/.test(publicRoot)) publicRoot += '/';

  function fill(text, base, trailingSlash) {
    var v = trailingSlash === false ? base.replace(/\/$/, '') : base;
    return String(text).replace(/https:\/\/evandersun\.github\.io\//g, v)
                       .replace(/https:\/\/evandersun\.github\.io(?=[^\/]|$)/g,
                                v.replace(/\/$/, ''));
  }

  var host = (function () {
    try { return new URL(root).hostname; } catch (e) { return 'evandersun.github.io'; }
  })();
  var LOCAL = /^(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]|)$/i;

  var Site = {
    root: root,
    publicRoot: publicRoot,
    repoRoot: REPO_ROOT,
    host: host,
    /* 本地预览不算正式访问（访问计数器据此判断） */
    official: !LOCAL.test(host) && !!loc && loc.protocol !== 'file:',
    /* 把文本 / 属性里写死的旧域名换成对外域名 */
    fill: function (t) { return fill(t, publicRoot); },
    /* 详情页地址可能来自任一已发布过的站点根，全部尝试转成站内相对路径 */
    knownRoots: function () {
      var a = [root, publicRoot];
      if (a.indexOf(REPO_ROOT) < 0) a.push(REPO_ROOT);
      return a;
    },
    /* DOM 就绪后统一替换标记了 data-site 的元素 */
    apply: function () {
      var nodes = document.querySelectorAll('[data-site]');
      Array.prototype.forEach.call(nodes, function (n) {
        var key = n.getAttribute('data-site') || 'text';
        if (key === 'text' || key === 'both') {
          if (n.firstChild && n.firstChild.nodeType === 3) {
            n.firstChild.nodeValue = fill(n.firstChild.nodeValue, publicRoot);
          } else {
            n.textContent = fill(n.textContent, publicRoot);
          }
        }
        if ((key === 'href' || key === 'both') && n.hasAttribute('href')) {
          n.setAttribute('href', fill(n.getAttribute('href'), publicRoot));
        }
      });
    }
  };

  global.Site = Site;
  global.SITE_ROOT = publicRoot;        // 兼容旧代码
  global.siteFill = Site.fill;

  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', function () { Site.apply(); });
    } else {
      Site.apply();
    }
  }
})(typeof window !== 'undefined' ? window : this);
