/* 访客统计：读取仓库根目录 analytics.json 里的百度统计站点 ID，有值才加载 hm.js。
 * 没配置时完全静默，不产生任何请求；本地预览（file: / localhost）不上报，避免污染数据。
 * 想换统计账号只需要改 analytics.json，或者在 admin 页里填。 */
(function () {
  var h = location.hostname;
  if (location.protocol === 'file:') return;
  if (/^(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])$/i.test(h)) return;

  function inject(id) {
    if (window.__hm_loaded) return;
    window.__hm_loaded = true;
    var _hmt = window._hmt = window._hmt || [];
    var hm = document.createElement('script');
    hm.src = 'https://hm.baidu.com/hm.js?' + id;
    hm.async = true;
    var s = document.getElementsByTagName('script')[0];
    if (s && s.parentNode) s.parentNode.insertBefore(hm, s);
    else document.head.appendChild(hm);
    // 顺带把设备类型记进自定义变量（1=设备 2=系统 3=屏幕），报表里更好分组
    var ua = navigator.userAgent || '';
    var dev = /iPad|Tablet/i.test(ua) ? '平板' : (/Mobile|iPhone|Android/i.test(ua) ? '手机' : '桌面');
    var os = '其他';
    if (/iPhone|iPad|iPod/i.test(ua)) os = 'iOS';
    else if (/Android/i.test(ua)) os = 'Android';
    else if (/CrOS/i.test(ua)) os = 'ChromeOS';
    else if (/Mac OS X/i.test(ua)) os = 'macOS';
    else if (/Windows/i.test(ua)) os = 'Windows';
    else if (/Linux/i.test(ua)) os = 'Linux';
    var scr = (screen.width || 0) + 'x' + (screen.height || 0);
    try {
      _hmt.push(['_setCustomVar', 1, '设备', dev, 3]);
      _hmt.push(['_setCustomVar', 2, '系统', os, 3]);
      _hmt.push(['_setCustomVar', 3, '屏幕', scr, 3]);
    } catch (e) {}
  }

  try {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', '/analytics.json?t=' + Date.now(), true);
    xhr.timeout = 6000;
    xhr.onload = function () {
      if (xhr.status !== 200) return;
      var d;
      try { d = JSON.parse(xhr.responseText); } catch (e) { return; }
      var id = String((d && d.baidu) || '').trim();
      if (!/^[0-9a-f]{16,40}$/i.test(id)) return;
      inject(id);
    };
    xhr.send();
  } catch (e) {}
})();
