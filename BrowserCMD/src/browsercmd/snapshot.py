"""Bounded JavaScript expression for visible DOM text and style snapshots."""

SNAPSHOT_SCRIPT = r"""(() => {
  const MAX_NODES = 5000;
  const MAX_RUNS = 5000;
  const MAX_TEXT = 1000000;
  const walker = document.createTreeWalker(document.body || document.documentElement,
    NodeFilter.SHOW_TEXT);
  const runs = [];
  let nodes = 0;
  let textBytes = 0;
  let node;
  while (nodes < MAX_NODES && runs.length < MAX_RUNS && (node = walker.nextNode())) {
    nodes += 1;
    const text = (node.nodeValue || '').replace(/\s+/g, ' ').trim();
    if (!text) continue;
    const remaining = MAX_TEXT - textBytes;
    if (remaining <= 0) break;
    const boundedText = text.slice(0, remaining);
    const parent = node.parentElement;
    if (!parent) continue;
    const style = getComputedStyle(parent);
    if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0) continue;
    const range = document.createRange();
    range.selectNodeContents(node);
    const rects = Array.from(range.getClientRects()).slice(0, 32);
    if (!rects.length) continue;
    const anchor = parent.closest('a[href]');
    for (const rect of rects) {
      if (runs.length >= MAX_RUNS) break;
      if (rect.width <= 0 || rect.height <= 0) continue;
      if (textBytes + boundedText.length > MAX_TEXT) break;
      runs.push({
        text: boundedText,
        x: rect.x,
        y: rect.y,
        width: rect.width,
        height: rect.height,
        color: style.color,
        background: style.backgroundColor,
        bold: Number.parseInt(style.fontWeight, 10) >= 600,
        italic: style.fontStyle !== 'normal',
        underline: style.textDecorationLine.includes('underline'),
        link: Boolean(anchor),
        href: anchor ? anchor.href.slice(0, 8192) : ''
      });
      textBytes += boundedText.length;
    }
  }
  return {
    url: location.href.slice(0, 8192),
    title: document.title.slice(0, 4096),
    viewport: { width: innerWidth, height: innerHeight, scrollX, scrollY },
    nodeCount: nodes,
    runs
  };
})()"""