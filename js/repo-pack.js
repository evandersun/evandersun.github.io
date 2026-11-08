/*!
 * repo-pack.js —— 把插件 zip 变成 flat APT repo 索引的浏览器端纯函数库。
 *
 * 依赖：fflate（js/fflate.min.js，zip / gzip）、fzstd（js/fzstd.min.js，
 *       新版 dpkg-deb 默认用 zstd 压 control.tar）、Web Crypto (crypto.subtle)。
 * 浏览器：window.RepoPack；Node（测试用）：module.exports。
 *
 * 不做任何网络请求，只负责：解压 zip -> 读 deb control -> 生成 stanza ->
 * 合并 Packages -> gzip -> 更新 Release。提交到仓库由 admin.html 负责。
 */
(function (global) {
  'use strict';

  var fflate = global.fflate;
  if (!fflate && typeof require === 'function') fflate = require('./fflate.min.js');
  if (!fflate) throw new Error('fflate 未加载');

  var fzstd = global.fzstd;
  if (!fzstd && typeof require === 'function') fzstd = require('./fzstd.min.js');
  if (!fzstd) throw new Error('fzstd 未加载');

  function utf8ToBytes(str) {
    if (typeof TextEncoder !== 'undefined') return new TextEncoder().encode(str);
    return fflate.strToU8(str);
  }
  function bytesToUtf8(u8) {
    if (typeof TextDecoder !== 'undefined') return new TextDecoder('utf-8').decode(u8);
    return fflate.strFromU8(u8);
  }
  function hex(u8) {
    var s = '', i, h;
    for (i = 0; i < u8.length; i++) {
      h = u8[i].toString(16);
      s += (h.length === 1 ? '0' : '') + h;
    }
    return s;
  }
  function rotl(x, s) { return (((x << s) | (x >>> (32 - s))) >>> 0); }

  /* ---------- MD5（Web Crypto 不提供 MD5，这里纯 JS 实现） ---------- */
  function md5(bytes) {
    var n = bytes.length;
    // 0x80 一字节 + 8 字节长度，再向上取整到 64 的倍数
    var total = ((n + 1 + 8 + 63) & ~63);
    var buf = new Uint8Array(total);
    buf.set(bytes, 0);
    buf[n] = 0x80;
    var dv = new DataView(buf.buffer);
    dv.setUint32(total - 8, (n * 8) >>> 0, true);
    dv.setUint32(total - 4, Math.floor(n * 8 / 0x100000000), true);

    var S = [7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22,
             5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20,
             4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23,
             6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21];
    var K = new Array(64), i;
    for (i = 0; i < 64; i++) {
      K[i] = Math.floor(Math.abs(Math.sin(i + 1)) * 0x100000000) >>> 0;
    }
    var a0 = 0x67452301, b0 = 0xefcdab89, c0 = 0x98badcfe, d0 = 0x10325476;
    var off = 0;
    for (; off < total; off += 64) {
      var M = new Array(16);
      for (i = 0; i < 16; i++) M[i] = dv.getUint32(off + i * 4, true);
      var A = a0, B = b0, C = c0, D = d0, F, g, j;
      for (j = 0; j < 64; j++) {
        if (j < 16) { F = (B & C) | (~B & D); g = j; }
        else if (j < 32) { F = (D & B) | (~D & C); g = (5 * j + 1) % 16; }
        else if (j < 48) { F = B ^ C ^ D; g = (3 * j + 5) % 16; }
        else { F = C ^ (B | ~D); g = (7 * j) % 16; }
        F = (F + A + K[j] + M[g]) >>> 0;
        A = D; D = C; C = B;
        B = (B + rotl(F, S[j])) >>> 0;
      }
      a0 = (a0 + A) >>> 0; b0 = (b0 + B) >>> 0;
      c0 = (c0 + C) >>> 0; d0 = (d0 + D) >>> 0;
    }
    var out = new Uint8Array(16);
    var odv = new DataView(out.buffer);
    odv.setUint32(0, a0, true); odv.setUint32(4, b0, true);
    odv.setUint32(8, c0, true); odv.setUint32(12, d0, true);
    return hex(out);
  }

  var cryptoObj = global.crypto || global.msCrypto;
  function shaHex(algo, bytes) {
    if (!cryptoObj || !cryptoObj.subtle) {
      return Promise.reject(new Error('Web Crypto 不可用，请使用较新的浏览器'));
    }
    return cryptoObj.subtle.digest(algo, bytes).then(function (d) {
      return hex(new Uint8Array(d));
    });
  }
  function hashes(bytes) {
    var b = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
    return Promise.all([shaHex('SHA-1', b), shaHex('SHA-256', b), shaHex('SHA-512', b)])
      .then(function (r) {
        return { md5: md5(b), sha1: r[0], sha256: r[1], sha512: r[2] };
      });
  }

  /* ---------- zip -> 两个 deb ---------- */
  function unzipDebs(zipBytes) {
    var files = fflate.unzipSync(new Uint8Array(zipBytes));
    var out = {}, path, base, low, key, magic;
    for (path in files) {
      if (!Object.prototype.hasOwnProperty.call(files, path)) continue;
      base = path.split('/').pop();
      if (!base || base.charAt(0) === '.' || path.indexOf('__MACOSX/') === 0) continue;
      low = base.toLowerCase();
      key = low === 'arm64.deb' ? 'arm64' : (low === 'arm64e.deb' ? 'arm64e' : null);
      if (key && !out[key]) out[key] = files[path];
    }
    if (!out.arm64 || !out.arm64e) {
      throw new Error('zip 内需同时包含 arm64.deb（rootless）和 arm64e.deb（roothide）');
    }
    for (key in out) {
      if (!Object.prototype.hasOwnProperty.call(out, key)) continue;
      magic = bytesToUtf8(out[key].subarray(0, 8));
      if (magic !== '!<arch>\n') throw new Error(key + '.deb 不是有效的 deb 文件（缺少 ar 魔数）');
    }
    return out;
  }

  /* ---------- deb -> control 文本 ---------- */
  function findTarFile(tar, want) {
    var pos = 0;
    while (pos + 512 <= tar.length) {
      var hdr = tar.subarray(pos, pos + 512);
      var name = bytesToUtf8(hdr.subarray(0, 100)).replace(/\0.*$/, '').replace(/^\.\//, '');
      var sz = bytesToUtf8(hdr.subarray(124, 136)).replace(/\0.*$/, '').replace(/\s+$/, '');
      var size = /^[0-7]+$/.test(sz) ? parseInt(sz, 8) : 0;
      // tar 里第一个条目常是 "./" 目录，名字去掉前缀后为空；跳过而不是当作结束
      if (name && want.indexOf(name) >= 0) {
        return bytesToUtf8(tar.subarray(pos + 512, pos + 512 + size));
      }
      pos += 512 + Math.ceil(size / 512) * 512;
    }
    throw new Error('control.tar 里找不到 control 文件');
  }

  function debControl(debBytes) {
    var u8 = debBytes instanceof Uint8Array ? debBytes : new Uint8Array(debBytes);
    if (bytesToUtf8(u8.subarray(0, 8)) !== '!<arch>\n') throw new Error('不是有效的 deb 文件');
    var pos = 8, controlTar = null, kind = '';
    while (pos + 60 <= u8.length) {
      var hdr = u8.subarray(pos, pos + 60);
      var name = bytesToUtf8(hdr.subarray(0, 16)).replace(/\s+$/, '').replace(/\/$/, '');
      var sizeStr = bytesToUtf8(hdr.subarray(48, 58)).replace(/\s+$/, '');
      var size = parseInt(sizeStr, 10);
      if (!isFinite(size) || size < 0) break;
      var data = u8.subarray(pos + 60, pos + 60 + size);
      if (/^control\.tar/.test(name)) { controlTar = data; kind = name; break; }
      pos += 60 + size + (size % 2);
    }
    if (!controlTar) throw new Error('deb 内找不到 control.tar.*');
    var tar;
    if (/\.gz$/.test(kind)) tar = fflate.gunzipSync(controlTar);
    else if (/\.zst$/.test(kind)) tar = fzstd.decompress(controlTar);
    else if (/\.xz$/.test(kind)) {
      throw new Error('暂不支持 control.tar.xz；请用 gzip 或 zstd 重新打包 deb');
    } else tar = controlTar;
    return findTarFile(tar, ['control']);
  }

  function controlFields(text) {
    var out = {}, last = null;
    String(text).replace(/\r\n/g, '\n').split('\n').forEach(function (line) {
      if (!line) return;
      if (/^[ \t]/.test(line)) { if (last) out[last] += '\n' + line; return; }
      var m = line.match(/^([A-Za-z0-9-]+):[ \t]*(.*)$/);
      if (m) { last = m[1]; out[last] = m[2]; }
    });
    return out;
  }

  /* ---------- Packages ---------- */
  function splitStanzas(text) {
    return String(text || '').replace(/\r\n/g, '\n').split(/\n\s*\n/)
      .map(function (s) { return s.trim(); }).filter(Boolean);
  }
  function stanzaFilename(s) {
    var m = s.match(/^Filename:[ \t]*(.+)$/mi);
    return m ? m[1].trim() : '';
  }
  function makeStanza(controlText, filename, bytes, h, pluginName) {
    var lines = String(controlText).replace(/\r\n/g, '\n').replace(/\n+$/, '').split('\n');
    var fields = controlFields(controlText);
    if (!fields.Name && pluginName) {
      var idx = -1;
      lines.forEach(function (l, i) { if (/^Package:/i.test(l)) idx = i; });
      if (idx >= 0) lines.splice(idx + 1, 0, 'Name: ' + pluginName);
      else lines.unshift('Name: ' + pluginName);
    }
    lines = lines.filter(function (l) {
      return !/^(Filename|Size|MD5sum|SHA1|SHA256|SHA512):/i.test(l);
    });
    return lines.join('\n') + '\n' +
      'Filename: ' + filename + '\n' +
      'Size: ' + bytes.length + '\n' +
      'MD5sum: ' + h.md5 + '\n' +
      'SHA1: ' + h.sha1 + '\n' +
      'SHA256: ' + h.sha256 + '\n' +
      'SHA512: ' + h.sha512 + '\n';
  }
  function mergePackages(existingText, newStanzas, removePrefix) {
    var keep = splitStanzas(existingText).filter(function (s) {
      var f = stanzaFilename(s);
      return !(removePrefix && f.indexOf(removePrefix) === 0);
    });
    var all = keep.concat(newStanzas.map(function (s) { return String(s).replace(/\n+$/, ''); }));
    return all.length ? all.join('\n\n') + '\n' : '';
  }
  // 架构只由当前 Packages 决定，与 tools/build_repo.py 一致：删掉插件后
  // Packages 为空时自动收缩回 iphoneos-arm，不会残留旧架构。
  function collectArchs(packagesText) {
    var archs = [];
    splitStanzas(packagesText).forEach(function (s) {
      var am = s.match(/^Architecture:[ \t]*(.+)$/mi);
      if (am && am[1].trim() && archs.indexOf(am[1].trim()) < 0) archs.push(am[1].trim());
    });
    archs.sort();
    if (archs.indexOf('iphoneos-arm') < 0) archs.unshift('iphoneos-arm');
    else { archs.splice(archs.indexOf('iphoneos-arm'), 1); archs.unshift('iphoneos-arm'); }
    return archs;
  }
  function gzipPackages(text) {
    return fflate.gzipSync(utf8ToBytes(text), { level: 9, mtime: 0 });
  }

  /* ---------- Release ---------- */
  function pad16(n) { return ('                ' + n).slice(-16); }
  function updateRelease(releaseText, pkgLen, pkgH, gzLen, gzH, archs) {
    var algoOf = { MD5Sum: 'md5', SHA1: 'sha1', SHA256: 'sha256', SHA512: 'sha512' };
    var section = '', out = [];
    String(releaseText).replace(/\r\n/g, '\n').split('\n').forEach(function (line) {
      var sm = line.match(/^(MD5Sum|SHA1|SHA256|SHA512):\s*$/);
      if (sm) { section = sm[1]; out.push(line); return; }
      if (line && /^\S/.test(line)) section = '';
      if (section && /^ /.test(line)) {
        var m = line.match(/^\s+([0-9a-fA-F]+)\s+(\d+)\s+(\S+)\s*$/);
        if (m) {
          if (m[3] === 'Packages' || m[3] === 'Packages.gz') {
            var isPkg = m[3] === 'Packages';
            var h = (isPkg ? pkgH : gzH)[algoOf[section]];
            out.push(' ' + h + ' ' + pad16(isPkg ? pkgLen : gzLen) + ' ' + m[3]);
            return;
          }
          if (m[3] === 'Packages.bz2' || m[3] === 'Packages.xz') return; // 已移除的旧格式
        }
      }
      if (/^Architectures:/i.test(line)) { out.push('Architectures: ' + archs.join(' ')); return; }
      if (/^Date:/i.test(line)) { out.push('Date: ' + new Date().toUTCString()); return; }
      out.push(line);
    });
    while (out.length && out[out.length - 1] === '') out.pop();
    return out.join('\n') + '\n';
  }

  /* ---------- 名称 ---------- */
  function pluginName(zipFileName) {
    return String(zipFileName || '').replace(/\.zip$/i, '').trim();
  }
  function safeName(name) {
    var s = String(name || '').trim()
      .replace(/[\\/:*?"<>|\r\n\t]/g, '_')
      .replace(/^\.+/, '_').replace(/\s+/g, '_');
    return s.slice(0, 120) || 'plugin';
  }

  var api = {
    utf8ToBytes: utf8ToBytes, bytesToUtf8: bytesToUtf8, hex: hex,
    md5: md5, hashes: hashes,
    unzipDebs: unzipDebs, debControl: debControl, controlFields: controlFields,
    splitStanzas: splitStanzas, stanzaFilename: stanzaFilename,
    makeStanza: makeStanza, mergePackages: mergePackages,
    collectArchs: collectArchs, gzipPackages: gzipPackages,
    updateRelease: updateRelease, pluginName: pluginName, safeName: safeName
  };
  if (typeof module === 'object' && module.exports) module.exports = api;
  else {
    // admin.html 里统一用 RP.* 调用；RepoPack 为完整名，RP 为兼容别名，两者指向同一对象
    global.RepoPack = api;
    global.RP = api;
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
