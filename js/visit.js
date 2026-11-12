/*
 * 站点访问计数（Vercount）：跟随当前部署域名，CF Pages / 自定义域名都能用。
 * 数字回填不出来就整块隐藏，页脚不留 Loading。
 * 注意：Vercount 按 hostname 计数，换域名后是独立的新计数，不继承 github.io 的旧数字。
 */
(function(){
  var box = document.getElementById('visitBox');
  if(!box) return;

  var proto = location.protocol;
  if(proto !== 'http:' && proto !== 'https:') return;

  /* 任意正式部署域名都统计；本地预览要加 ?visit=test，免得把调试访问也算进去 */
  var official = (window.Site && Site.official) ||
                 /(^|\.)evandersun\.github\.io$/i.test(location.hostname);
  var forced   = /(^|[?&])visit=test(&|$)/.test(location.search);
  if(!official && !forced) return;

  var SRC = ['https://cn.vercount.one/js', 'https://events.vercount.one/js'];
  var n = 0;

  function load(){
    var s = document.createElement('script');
    s.src = SRC[n];
    s.async = true;
    s.onerror = function(){
      n += 1;
      if(n < SRC.length) load();      /* 国内节点不通就换全球节点，只换一次，不会重复计数 */
    };
    document.head.appendChild(s);
  }

  /* 两个数字都变成纯数字之后才显示，否则一直隐藏 */
  var tick = setInterval(function(){
    var uv = document.getElementById('vercount_value_site_uv');
    var pv = document.getElementById('vercount_value_site_pv');
    if(!uv || !pv) return;
    if(/^\d+$/.test(uv.textContent.trim()) && /^\d+$/.test(pv.textContent.trim())){
      box.classList.add('on');
      clearInterval(tick);
    }
  }, 250);
  setTimeout(function(){ clearInterval(tick); }, 9000);

  load();
})();
