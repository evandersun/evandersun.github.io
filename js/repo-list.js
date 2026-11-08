/*
 * js/repo-list.js — 从 APT Packages 索引解析出「已上传插件」列表。
 * 纯函数、无网络请求、无 DOM 依赖：浏览器挂 window.RepoList，Node 走 module.exports。
 *
 * 管理页上传一个插件会往 Packages 写两条 stanza（arm64 / arm64e），
 * Filename 形如 debs/<插件名>_arm64.deb 与 debs/<插件名>_arm64e.deb。
 * 这里按插件名把两条合并成一条记录，供首页展示。
 */
(function (global) {
  'use strict';

  // Debian control 字段解析：续行（以空格/制表符开头）并入上一字段
  function fields(block) {
    var out = {}, last = null;
    String(block || '').replace(/\r\n/g, '\n').split('\n').forEach(function (line) {
      if (/^[ \t]/.test(line)) {
        if (last) out[last] += '\n' + line.replace(/^[ \t]+/, '');
        return;
      }
      var m = line.match(/^([A-Za-z0-9][A-Za-z0-9-]*):[ \t]*(.*)$/);
      if (m) { last = m[1]; out[last] = m[2]; }
      else last = null;
    });
    return out;
  }

  function splitBlocks(text) {
    return String(text || '').replace(/\r\n/g, '\n')
      .split(/\n[ \t]*\n+/)
      .map(function (s) { return s.trim(); })
      .filter(function (s) { return s.length > 0; });
  }

  // 从 Filename 反推插件名；没有 Filename 时回退到 Package / Name
  function pluginKey(f) {
    var base = String(f.Filename || '').split('/').pop();
    var m = base.match(/^(.*?)_(?:arm64e|arm64)\.deb$/i);
    if (m && m[1]) return m[1];
    var m2 = base.match(/^(.*?)\.deb$/i);
    if (m2 && m2[1]) return m2[1].replace(/_(?:iphoneos-)?(?:arm64e|arm64)$/i, '');
    return f.Package || f.Name || base || '';
  }

  function archLabel(arch) {
    var a = String(arch || '');
    if (a.toLowerCase() === 'iphoneos-arm64e') return 'roothide · arm64e';
    if (a.toLowerCase() === 'iphoneos-arm64') return 'rootless · arm64';
    return a || '未知架构';
  }

  function parsePackages(text) {
    var map = {}, order = [];
    splitBlocks(text).forEach(function (block) {
      var f = fields(block);
      if (!f.Package && !f.Filename) return;
      var key = pluginKey(f);
      if (!key) return;
      if (!map[key]) {
        map[key] = {
          key: key,
          name: f.Name || f.Package || key,
          packageId: f.Package || '',
          version: f.Version || '',
          description: String(f.Description || '').split('\n')[0].trim(),
          section: f.Section || '',
          depiction: String(f.Depiction || '').trim(),
          sileoDepiction: String(f.SileoDepiction || '').trim(),
          archs: [],
          files: []
        };
        order.push(key);
      }
      var p = map[key];
      if (!p.version && f.Version) p.version = f.Version;
      if (!p.description && f.Description) p.description = String(f.Description).split('\n')[0].trim();
      if (!p.depiction && f.Depiction) p.depiction = String(f.Depiction).trim();
      if (!p.sileoDepiction && f.SileoDepiction) p.sileoDepiction = String(f.SileoDepiction).trim();
      var a = String(f.Architecture || '');
      if (a && p.archs.indexOf(a) < 0) p.archs.push(a);
      if (f.Filename && p.files.indexOf(f.Filename) < 0) p.files.push(f.Filename);
    });
    return order.map(function (k) { return map[k]; });
  }

  var api = {
    parsePackages: parsePackages,
    fields: fields,
    splitBlocks: splitBlocks,
    pluginKey: pluginKey,
    archLabel: archLabel
  };
  if (typeof module === 'object' && module.exports) module.exports = api;
  else global.RepoList = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
