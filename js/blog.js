/* 极简 Markdown 渲染：够博客用，不做完整解析。
 * 支持：空行分段、# ## ### 标题、> 引用、- / 1. 列表、``` 代码块、--- 分隔线、
 *       **粗体**、*斜体*、`行内代码`、[文字](链接)、裸网址自动转链接。
 * 结构在原始文本上判断，输出前才转义，正文里的标签不会被当成结构执行。 */
(function (global) {
  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function inline(s) {
    // 行内代码先占位，避免里面的符号被后续规则改写
    var codes = [];
    s = s.replace(/`([^`]+)`/g, function (_, c) {
      codes.push(c);
      return '\u0000' + (codes.length - 1) + '\u0000';
    });
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>');
    s = s.replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    s = s.replace(/(^|[\s(（])(https?:\/\/[^\s<)）]+)/g, function (_, pre, url) {
      return pre + '<a href="' + url + '" target="_blank" rel="noopener noreferrer">' + url + '</a>';
    });
    s = s.replace(/\u0000(\d+)\u0000/g, function (_, i) {
      return '<code>' + codes[+i] + '</code>';
    });
    return s;
  }

  function md2html(text) { return inline(esc(text)); }

  function render(md) {
    var lines = String(md || '').replace(/\r\n?/g, '\n').split('\n');
    var out = [];
    var i = 0, list = null;

    function closeList() {
      if (list) { out.push('</' + list + '>'); list = null; }
    }

    while (i < lines.length) {
      var line = lines[i];

      // 代码块
      if (/^```/.test(line.trim())) {
        closeList();
        var buf = [];
        i++;
        while (i < lines.length && !/^```/.test(lines[i].trim())) { buf.push(lines[i]); i++; }
        i++;
        out.push('<pre><code>' + esc(buf.join('\n')) + '</code></pre>');
        continue;
      }

      if (!line.trim()) { closeList(); i++; continue; }

      if (/^(-{3,}|\*{3,}|_{3,})$/.test(line.trim())) {
        closeList(); out.push('<hr>'); i++; continue;
      }

      var h = /^(#{1,4})\s+(.*)$/.exec(line);
      if (h) {
        closeList();
        var lv = Math.min(4, Math.max(2, h[1].length));   // h1 留给文章标题，# 与 ## 都算 h2
        out.push('<h' + lv + '>' + md2html(h[2].trim()) + '</h' + lv + '>');
        i++; continue;
      }

      if (/^>\s?/.test(line)) {
        closeList();
        var quote = [];
        while (i < lines.length && /^>\s?/.test(lines[i])) {
          quote.push(lines[i].replace(/^>\s?/, ''));
          i++;
        }
        out.push('<blockquote>' + md2html(quote.join('\n')).replace(/\n/g, '<br>') + '</blockquote>');
        continue;
      }

      if (/^[-*+]\s+/.test(line)) {
        if (list !== 'ul') { closeList(); out.push('<ul>'); list = 'ul'; }
        out.push('<li>' + md2html(line.replace(/^[-*+]\s+/, '')) + '</li>');
        i++; continue;
      }

      if (/^\d+[.)]\s+/.test(line)) {
        if (list !== 'ol') { closeList(); out.push('<ol>'); list = 'ol'; }
        out.push('<li>' + md2html(line.replace(/^\d+[.)]\s+/, '')) + '</li>');
        i++; continue;
      }

      closeList();
      var para = [line];
      i++;
      while (i < lines.length && lines[i].trim() &&
             !/^(#{1,4}\s|>|[-*+]\s|\d+[.)]\s|```)/.test(lines[i]) &&
             !/^(-{3,}|\*{3,}|_{3,})$/.test(lines[i].trim())) {
        para.push(lines[i]);
        i++;
      }
      out.push('<p>' + md2html(para.join('\n')).replace(/\n/g, '<br>') + '</p>');
    }
    closeList();
    return out.join('\n');
  }

  global.Blog = {
    esc: esc,
    render: render,
    plain: function (md) {
      return String(md || '')
        .replace(/```[\s\S]*?```/g, ' ')
        .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
        .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
        .replace(/[#>*_`~-]+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
    }
  };
})(window);
