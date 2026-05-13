// InFlow flowchart canvas.
// Renders positioned nodes + SVG edges and handles every interaction
// (pan, zoom, drag-subtree, box-select, group-move, inline add, delete).
(function () {
  'use strict';

  // ---------- Constants ----------
  const NODE_W = 200;
  const NODE_H = 96;       // matches CSS min-height + padding
  const MIN_ZOOM = 0.15;
  const MAX_ZOOM = 2.5;
  const PADDING = 240;     // canvas extends past nodes so panning past edges feels OK

  const cfg = window.INFLOW_CHART || {};
  const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';
  const SVG_NS = 'http://www.w3.org/2000/svg';
  const READONLY = !!cfg.readonly;

  // ---------- DOM refs ----------
  const viewport = document.getElementById('fc-viewport');
  const canvas   = document.getElementById('fc-canvas');
  const edgesSvg = document.getElementById('fc-edges');
  const marquee  = document.getElementById('fc-marquee');
  const popover  = document.getElementById('fc-add-popover');
  const zoomReadout = document.getElementById('zoom-readout');
  if (!viewport || !canvas) return;

  // ---------- State ----------
  const state = {
    nodes: new Map(),         // id -> node data { id, parent_id, label, ..., x, y, el }
    selection: new Set(),     // ids of selected nodes
    pan: { x: 80, y: 80 },
    zoom: 1,
    // gestures
    isPanning: false,
    isMarquee: false,
    isDraggingNodes: false,
    panStart: null,           // { mx, my, panX, panY }
    marqueeStart: null,       // { vx, vy }
    dragStart: null,          // { mx, my, originals: [{id, x, y}], movingIds: [] }
    // canvas bounds (px in canvas-coords, refreshed after position changes)
    bounds: { minX: 0, minY: 0, maxX: 1000, maxY: 800 },
    // batch save scheduling
    pendingSave: new Set(),   // ids that need persisting
    saveTimer: null,
    activeAddParent: null,
  };

  // ---------- Init from server JSON ----------
  (function loadInitial() {
    const tag = document.getElementById('initial-nodes');
    if (!tag) return;
    let rows = [];
    try { rows = JSON.parse(tag.textContent || '[]'); } catch (_) { rows = []; }
    rows.forEach(r => {
      state.nodes.set(r.id, {
        id: r.id,
        parent_id: r.parent_id,
        label: r.label || '',
        subtitle: r.subtitle || '',
        shape: r.shape || 'process',
        shape_display: r.shape_display || '',
        branch_label: r.branch_label || '',
        color: r.color || '#1B4D5A',
        x: Number(r.x) || 0,
        y: Number(r.y) || 0,
        detail_url: r.detail_url || (cfg.nodeBaseUrl + r.id + '/'),
        el: null,
      });
    });
  })();

  // ---------- Coord helpers ----------
  function screenToCanvas(sx, sy) {
    const r = viewport.getBoundingClientRect();
    return {
      x: (sx - r.left - state.pan.x) / state.zoom,
      y: (sy - r.top - state.pan.y) / state.zoom,
    };
  }
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

  function recomputeBounds() {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    state.nodes.forEach(n => {
      if (n.x < minX) minX = n.x;
      if (n.y < minY) minY = n.y;
      if (n.x + NODE_W > maxX) maxX = n.x + NODE_W;
      if (n.y + NODE_H > maxY) maxY = n.y + NODE_H;
    });
    if (!isFinite(minX)) { minX = 0; minY = 0; maxX = 800; maxY = 600; }
    state.bounds = {
      minX: minX - PADDING,
      minY: minY - PADDING,
      maxX: maxX + PADDING,
      maxY: maxY + PADDING,
    };
    const w = state.bounds.maxX - state.bounds.minX;
    const h = state.bounds.maxY - state.bounds.minY;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    edgesSvg.setAttribute('width', w);
    edgesSvg.setAttribute('height', h);
    // offset canvas so node coords map cleanly: a node at (x, y) sits at translate(x - minX, y - minY)
    canvas.dataset.offsetX = String(state.bounds.minX);
    canvas.dataset.offsetY = String(state.bounds.minY);
  }

  // ---------- Render ----------
  function applyTransform() {
    canvas.style.transform = 'translate(' + state.pan.x + 'px, ' + state.pan.y + 'px) scale(' + state.zoom + ')';
    zoomReadout.textContent = Math.round(state.zoom * 100) + '%';
  }

  function buildNodeEl(n) {
    const el = document.createElement('div');
    el.className = 'fc-node';
    el.dataset.nodeId = String(n.id);
    el.dataset.shape = n.shape;
    el.style.setProperty('--node-color', n.color);
    el.innerHTML = ''
      + '<div class="node-shape">' + escapeHtml(n.shape_display) + '</div>'
      + '<div class="node-label"></div>'
      + (n.subtitle ? '<div class="node-subtitle"></div>' : '')
      + '<div class="node-actions">'
      +   '<button type="button" class="node-action" data-action="add" title="Add child">+</button>'
      +   '<a class="node-action" data-action="open" href="' + n.detail_url + '" title="Open detail">↗</a>'
      + '</div>';
    el.querySelector('.node-label').textContent = n.label;
    if (n.subtitle) el.querySelector('.node-subtitle').textContent = n.subtitle;
    n.el = el;
    positionNodeEl(n);
    return el;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }

  function positionNodeEl(n) {
    const ox = parseFloat(canvas.dataset.offsetX) || 0;
    const oy = parseFloat(canvas.dataset.offsetY) || 0;
    n.el.style.left = (n.x - ox) + 'px';
    n.el.style.top  = (n.y - oy) + 'px';
  }

  function renderAllNodes() {
    // Clear existing nodes (keep SVG)
    canvas.querySelectorAll('.fc-node').forEach(el => el.remove());
    state.nodes.forEach(n => {
      const el = buildNodeEl(n);
      canvas.appendChild(el);
    });
    refreshSelectionClasses();
  }

  function renderAllEdges() {
    // Wipe and rebuild — simpler than diffing for the node counts we expect.
    while (edgesSvg.firstChild) edgesSvg.removeChild(edgesSvg.firstChild);
    const ox = parseFloat(canvas.dataset.offsetX) || 0;
    const oy = parseFloat(canvas.dataset.offsetY) || 0;
    state.nodes.forEach(n => {
      if (!n.parent_id) return;
      const p = state.nodes.get(n.parent_id);
      if (!p) return;
      const sx = (p.x - ox) + NODE_W / 2;
      const sy = (p.y - oy) + NODE_H;
      const tx = (n.x - ox) + NODE_W / 2;
      const ty = (n.y - oy);
      // Smooth cubic with vertical tangents — reads as parent-down-to-child
      const dy = Math.max(40, (ty - sy) * 0.6);
      const d = 'M ' + sx + ' ' + sy
              + ' C ' + sx + ' ' + (sy + dy) + ', '
              +       tx + ' ' + (ty - dy) + ', '
              +       tx + ' ' + ty;
      const path = document.createElementNS(SVG_NS, 'path');
      path.setAttribute('class', 'edge-line');
      path.setAttribute('d', d);
      path.dataset.parentId = String(p.id);
      path.dataset.childId = String(n.id);
      edgesSvg.appendChild(path);

      if (n.branch_label) {
        // Place label slightly above the midpoint of the curve's vertical run.
        const mx = (sx + tx) / 2;
        const my = (sy + ty) / 2 - 4;
        const text = document.createElementNS(SVG_NS, 'text');
        text.setAttribute('class', 'edge-label');
        text.setAttribute('x', mx);
        text.setAttribute('y', my);
        text.setAttribute('text-anchor', 'middle');
        text.textContent = n.branch_label;
        edgesSvg.appendChild(text);
      }
    });
  }

  function refreshSelectionClasses() {
    state.nodes.forEach(n => {
      if (!n.el) return;
      if (state.selection.has(n.id)) n.el.classList.add('is-selected');
      else n.el.classList.remove('is-selected');
    });
  }

  function fullRender() {
    recomputeBounds();
    renderAllNodes();
    renderAllEdges();
    applyTransform();
  }

  // ---------- Descendants helper (drag-subtree) ----------
  const childrenByParent = new Map();
  function rebuildChildrenIndex() {
    childrenByParent.clear();
    state.nodes.forEach(n => {
      if (n.parent_id == null) return;
      if (!childrenByParent.has(n.parent_id)) childrenByParent.set(n.parent_id, []);
      childrenByParent.get(n.parent_id).push(n.id);
    });
  }
  function descendantIds(rootId, includeSelf) {
    const out = [];
    const stack = [rootId];
    const seen = new Set();
    while (stack.length) {
      const id = stack.pop();
      if (seen.has(id)) continue;
      seen.add(id);
      if (includeSelf || id !== rootId) out.push(id);
      const kids = childrenByParent.get(id) || [];
      for (const k of kids) stack.push(k);
    }
    return out;
  }

  // ---------- Selection ----------
  function clearSelection() {
    state.selection.clear();
    refreshSelectionClasses();
  }
  function setSelection(ids) {
    state.selection = new Set(ids);
    refreshSelectionClasses();
  }
  function toggleSelection(id) {
    if (state.selection.has(id)) state.selection.delete(id);
    else state.selection.add(id);
    refreshSelectionClasses();
  }

  // ---------- Pan & Zoom ----------
  viewport.addEventListener('wheel', (e) => {
    e.preventDefault();
    const r = viewport.getBoundingClientRect();
    const mx = e.clientX - r.left;
    const my = e.clientY - r.top;
    const factor = Math.exp(-e.deltaY * 0.0015);
    const newZoom = clamp(state.zoom * factor, MIN_ZOOM, MAX_ZOOM);
    // anchor zoom under cursor
    state.pan.x = mx - (mx - state.pan.x) * (newZoom / state.zoom);
    state.pan.y = my - (my - state.pan.y) * (newZoom / state.zoom);
    state.zoom = newZoom;
    applyTransform();
  }, { passive: false });

  function startPan(e) {
    state.isPanning = true;
    state.panStart = { mx: e.clientX, my: e.clientY, panX: state.pan.x, panY: state.pan.y };
    viewport.classList.add('is-panning');
  }
  function continuePan(e) {
    if (!state.isPanning) return;
    state.pan.x = state.panStart.panX + (e.clientX - state.panStart.mx);
    state.pan.y = state.panStart.panY + (e.clientY - state.panStart.my);
    applyTransform();
  }
  function endPan() {
    state.isPanning = false;
    viewport.classList.remove('is-panning');
  }

  // ---------- Marquee (shift-drag) ----------
  function startMarquee(e) {
    state.isMarquee = true;
    const r = viewport.getBoundingClientRect();
    state.marqueeStart = { vx: e.clientX - r.left, vy: e.clientY - r.top };
    marquee.style.left = state.marqueeStart.vx + 'px';
    marquee.style.top  = state.marqueeStart.vy + 'px';
    marquee.style.width = '0px';
    marquee.style.height = '0px';
    marquee.classList.add('active');
    viewport.classList.add('is-marquee');
  }
  function continueMarquee(e) {
    if (!state.isMarquee) return;
    const r = viewport.getBoundingClientRect();
    const x = e.clientX - r.left, y = e.clientY - r.top;
    const left = Math.min(x, state.marqueeStart.vx);
    const top  = Math.min(y, state.marqueeStart.vy);
    const w    = Math.abs(x - state.marqueeStart.vx);
    const h    = Math.abs(y - state.marqueeStart.vy);
    marquee.style.left = left + 'px';
    marquee.style.top  = top  + 'px';
    marquee.style.width  = w + 'px';
    marquee.style.height = h + 'px';
  }
  function endMarquee(e) {
    if (!state.isMarquee) return;
    state.isMarquee = false;
    marquee.classList.remove('active');
    viewport.classList.remove('is-marquee');
    // Compute selection in canvas coordinates.
    const r = viewport.getBoundingClientRect();
    const x1 = e.clientX - r.left, y1 = e.clientY - r.top;
    const vLeft = Math.min(x1, state.marqueeStart.vx);
    const vTop  = Math.min(y1, state.marqueeStart.vy);
    const vRight = Math.max(x1, state.marqueeStart.vx);
    const vBot   = Math.max(y1, state.marqueeStart.vy);
    const a = screenToCanvas(vLeft + r.left, vTop + r.top);
    const b = screenToCanvas(vRight + r.left, vBot + r.top);
    const ids = [];
    state.nodes.forEach(n => {
      const nl = n.x, nt = n.y, nr = n.x + NODE_W, nb = n.y + NODE_H;
      if (nr >= a.x && nl <= b.x && nb >= a.y && nt <= b.y) ids.push(n.id);
    });
    setSelection(ids);
  }

  // ---------- Node drag (with subtree or selection) ----------
  function startNodeDrag(e, nodeEl) {
    const id = parseInt(nodeEl.dataset.nodeId, 10);
    if (Number.isNaN(id)) return;

    // Figure out which nodes are moving:
    // - If the clicked node is in a multi-selection, move all selected.
    // - Otherwise, move this node + its subtree (and select it).
    let movingIds;
    if (state.selection.has(id) && state.selection.size > 1) {
      movingIds = Array.from(state.selection);
    } else {
      movingIds = descendantIds(id, true);
      setSelection([id]);
    }

    const originals = movingIds.map(mid => {
      const n = state.nodes.get(mid);
      return { id: mid, x: n.x, y: n.y };
    });
    state.isDraggingNodes = true;
    state.dragStart = {
      mx: e.clientX,
      my: e.clientY,
      originals,
      movingIds,
    };
    movingIds.forEach(mid => {
      const n = state.nodes.get(mid);
      if (n && n.el) n.el.classList.add('is-dragging');
    });
  }
  function continueNodeDrag(e) {
    if (!state.isDraggingNodes) return;
    const dxScreen = e.clientX - state.dragStart.mx;
    const dyScreen = e.clientY - state.dragStart.my;
    const dx = dxScreen / state.zoom;
    const dy = dyScreen / state.zoom;
    state.dragStart.originals.forEach(orig => {
      const n = state.nodes.get(orig.id);
      if (!n) return;
      n.x = orig.x + dx;
      n.y = orig.y + dy;
      positionNodeEl(n);
    });
    renderAllEdges();
  }
  function endNodeDrag() {
    if (!state.isDraggingNodes) return;
    state.dragStart.movingIds.forEach(id => {
      const n = state.nodes.get(id);
      if (n && n.el) n.el.classList.remove('is-dragging');
      state.pendingSave.add(id);
    });
    state.isDraggingNodes = false;
    state.dragStart = null;
    schedulePositionSave();
  }

  function schedulePositionSave() {
    if (state.saveTimer) clearTimeout(state.saveTimer);
    state.saveTimer = setTimeout(flushPositions, 350);
  }
  async function flushPositions() {
    if (!state.pendingSave.size) return;
    const positions = [];
    state.pendingSave.forEach(id => {
      const n = state.nodes.get(id);
      if (!n) return;
      positions.push({ id: n.id, x: n.x, y: n.y });
    });
    state.pendingSave.clear();
    try {
      const resp = await fetch(cfg.positionsUrl, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrf,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ positions }),
      });
      if (!resp.ok) console.warn('position save failed', resp.status);
    } catch (err) {
      console.warn('position save error', err);
    }
  }

  // ---------- Inline add child ----------
  function openAddPopover(parentId) {
    const p = state.nodes.get(parentId);
    if (!p) return;
    state.activeAddParent = parentId;
    document.getElementById('add-parent-label').textContent = p.label;
    document.getElementById('add-label').value = '';
    document.getElementById('add-subtitle').value = '';
    document.getElementById('add-branch').value = '';
    document.getElementById('add-shape').value = 'process';
    // Position popover near the node, in viewport (screen) coords
    const r = viewport.getBoundingClientRect();
    const ox = parseFloat(canvas.dataset.offsetX) || 0;
    const oy = parseFloat(canvas.dataset.offsetY) || 0;
    const screenX = (p.x - ox) * state.zoom + state.pan.x + NODE_W * state.zoom + 12;
    const screenY = (p.y - oy) * state.zoom + state.pan.y;
    popover.style.left = clamp(screenX, 8, r.width - 260) + 'px';
    popover.style.top  = clamp(screenY, 8, r.height - 240) + 'px';
    popover.classList.add('open');
    setTimeout(() => document.getElementById('add-label').focus(), 30);
  }
  function closeAddPopover() {
    state.activeAddParent = null;
    popover.classList.remove('open');
  }
  async function submitAddPopover() {
    if (state.activeAddParent == null) return;
    const label = document.getElementById('add-label').value.trim();
    if (!label) return;
    const body = new URLSearchParams();
    body.set('label', label);
    body.set('subtitle', document.getElementById('add-subtitle').value);
    body.set('shape', document.getElementById('add-shape').value);
    body.set('branch_label', document.getElementById('add-branch').value);
    body.set('parent_id', String(state.activeAddParent));
    try {
      const resp = await fetch(cfg.quickAddUrl, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrf,
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: body.toString(),
      });
      const data = await resp.json();
      if (!resp.ok || !data.ok) {
        alert(data.error || 'Add failed');
        return;
      }
      const n = data.node;
      state.nodes.set(n.id, {
        id: n.id,
        parent_id: n.parent_id,
        label: n.label || '',
        subtitle: n.subtitle || '',
        shape: n.shape || 'process',
        shape_display: n.shape_display || '',
        branch_label: n.branch_label || '',
        color: n.color || '#1B4D5A',
        x: Number(n.x) || 0,
        y: Number(n.y) || 0,
        detail_url: n.detail_url,
        el: null,
      });
      rebuildChildrenIndex();
      fullRender();
      closeAddPopover();
    } catch (err) {
      alert('Add failed: ' + err.message);
    }
  }

  // ---------- Delete selected ----------
  async function deleteSelected() {
    if (state.selection.size === 0) return;
    const ids = Array.from(state.selection);
    const noun = ids.length === 1 ? 'node' : (ids.length + ' nodes');
    if (!confirm('Delete ' + noun + ' (and any descendants)? This can\'t be undone.')) return;
    for (const id of ids) {
      try {
        const resp = await fetch(cfg.nodeBaseUrl + id + '/quick-delete/', {
          method: 'POST',
          headers: {
            'X-CSRFToken': csrf,
            'Content-Type': 'application/x-www-form-urlencoded',
          },
        });
        if (!resp.ok) continue;
      } catch (_) { /* swallow */ }
    }
    // Walk the local index and prune.
    const toRemove = new Set();
    for (const id of ids) {
      descendantIds(id, true).forEach(d => toRemove.add(d));
    }
    toRemove.forEach(id => state.nodes.delete(id));
    state.selection.clear();
    rebuildChildrenIndex();
    fullRender();
  }

  // ---------- Auto-layout ----------
  async function runAutoLayout() {
    try {
      const resp = await fetch(cfg.autoLayoutUrl, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrf,
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });
      if (!resp.ok) { alert('Auto-layout failed'); return; }
      // Easiest reliable refresh: reload the page.
      window.location.reload();
    } catch (err) { alert('Auto-layout failed: ' + err.message); }
  }

  // ---------- Fit-to-view ----------
  function fitToView() {
    if (state.nodes.size === 0) {
      state.zoom = 1; state.pan.x = 80; state.pan.y = 80; applyTransform(); return;
    }
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    state.nodes.forEach(n => {
      if (n.x < minX) minX = n.x;
      if (n.y < minY) minY = n.y;
      if (n.x + NODE_W > maxX) maxX = n.x + NODE_W;
      if (n.y + NODE_H > maxY) maxY = n.y + NODE_H;
    });
    const r = viewport.getBoundingClientRect();
    const pad = 60;
    const w = maxX - minX, h = maxY - minY;
    const zx = (r.width  - pad * 2) / w;
    const zy = (r.height - pad * 2) / h;
    state.zoom = clamp(Math.min(zx, zy), MIN_ZOOM, MAX_ZOOM);
    const ox = parseFloat(canvas.dataset.offsetX) || 0;
    const oy = parseFloat(canvas.dataset.offsetY) || 0;
    state.pan.x = (r.width  - w * state.zoom) / 2 - (minX - ox) * state.zoom;
    state.pan.y = (r.height - h * state.zoom) / 2 - (minY - oy) * state.zoom;
    applyTransform();
  }

  // ---------- Event wiring ----------
  viewport.addEventListener('mousedown', (e) => {
    if (e.button !== 0) return;
    if (!READONLY && popover.classList.contains('open') && popover.contains(e.target)) return;
    if (!READONLY) closeAddPopover();
    const nodeEl = e.target.closest('.fc-node');
    if (nodeEl) {
      const actionBtn = e.target.closest('.node-action');
      if (actionBtn) {
        e.stopPropagation();
        if (READONLY) {
          // Only the 'open' (link) action is meaningful in readonly mode; let the link navigate.
          if (actionBtn.dataset.action !== 'open') e.preventDefault();
          return;
        }
        const id = parseInt(nodeEl.dataset.nodeId, 10);
        if (actionBtn.dataset.action === 'add') {
          openAddPopover(id);
        } else if (actionBtn.dataset.action === 'open') {
          return;
        }
        return;
      }
      if (READONLY) {
        // Click on a node body in readonly: start a pan instead, so the page still feels alive.
        startPan(e);
        e.preventDefault();
        return;
      }
      const id = parseInt(nodeEl.dataset.nodeId, 10);
      if (e.shiftKey) {
        toggleSelection(id);
      }
      startNodeDrag(e, nodeEl);
      e.preventDefault();
      return;
    }
    // Empty space click
    if (!READONLY && e.shiftKey) {
      startMarquee(e);
    } else {
      clearSelection();
      startPan(e);
    }
  });

  window.addEventListener('mousemove', (e) => {
    if (state.isDraggingNodes) continueNodeDrag(e);
    else if (state.isPanning) continuePan(e);
    else if (state.isMarquee) continueMarquee(e);
  });
  window.addEventListener('mouseup', (e) => {
    if (state.isDraggingNodes) endNodeDrag();
    if (state.isPanning) endPan();
    if (state.isMarquee) endMarquee(e);
  });

  // Keyboard
  viewport.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    if ((e.key === 'Delete' || e.key === 'Backspace') && !READONLY) {
      e.preventDefault();
      deleteSelected();
    } else if (e.key === 'Escape') {
      if (!READONLY) closeAddPopover();
      clearSelection();
    } else if (e.key === 'f' || e.key === 'F') {
      fitToView();
    }
  });

  // Make sure clicks on the viewport focus it for keyboard.
  viewport.addEventListener('mousedown', () => viewport.focus(), { capture: true });

  // Toolbar
  document.getElementById('zoom-in').addEventListener('click', () => zoomBy(1.2));
  document.getElementById('zoom-out').addEventListener('click', () => zoomBy(1 / 1.2));
  document.getElementById('fit-view').addEventListener('click', fitToView);
  const autoLayoutBtn = document.getElementById('auto-layout-btn');
  if (autoLayoutBtn) {
    autoLayoutBtn.addEventListener('click', () => {
      if (!confirm('Replace all node positions with the auto-layout tree? Your manual placement will be overwritten.')) return;
      runAutoLayout();
    });
  }

  function zoomBy(f) {
    const r = viewport.getBoundingClientRect();
    const mx = r.width / 2, my = r.height / 2;
    const newZoom = clamp(state.zoom * f, MIN_ZOOM, MAX_ZOOM);
    state.pan.x = mx - (mx - state.pan.x) * (newZoom / state.zoom);
    state.pan.y = my - (my - state.pan.y) * (newZoom / state.zoom);
    state.zoom = newZoom;
    applyTransform();
  }

  // Popover buttons
  document.getElementById('add-cancel').addEventListener('click', closeAddPopover);
  document.getElementById('add-submit').addEventListener('click', submitAddPopover);
  document.getElementById('add-label').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); submitAddPopover(); }
    else if (e.key === 'Escape') { closeAddPopover(); }
  });

  // ---------- Boot ----------
  rebuildChildrenIndex();
  fullRender();
  // Initial fit if there are nodes
  if (state.nodes.size > 0) fitToView();
  viewport.focus();
})();
