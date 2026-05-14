"""Tidy-tree layout for flowchart nodes.

Each node has an absolute (x_pos, y_pos) on the canvas. Auto-layout computes
those positions so the tree reads top-down, parents centered above their
children. Manual drags overwrite the positions; users can call auto-layout
again to retidy.

OneZoom-style importance baked into geometry: depth 0 (root) and depth 1
(sections) reserve much more space in the layout than deeper nodes. The CSS
renders nodes at the SAME pre-baked size at every zoom, so the camera
transform alone produces the "tree of life" effect — big colored trunks
visible at far zoom, smaller branches/leaves at close zoom. No CSS-only
inflation at zoom transitions (that was the wave bug).
"""
from collections import defaultdict

from .models import Node


# Depth -> (width, height) in canvas pixels.
# Matches the per-depth sizes declared in base.css.
NODE_SIZES = {
    0: (900, 320),    # root (trunk) — always visible as a landmark
    1: (600, 240),    # depth-1 sections — visible at moderate zoom
    2: (240, 110),    # depth-2 sub-landmarks — small but distinct
}
DEFAULT_W = 200
DEFAULT_H = 96

H_GAP = 36       # horizontal gap between sibling subtrees
V_GAP = 90       # vertical gap between a parent and its children
FOREST_GAP = 100  # extra horizontal gap between separate root trees


def _size(depth):
    return NODE_SIZES.get(depth, (DEFAULT_W, DEFAULT_H))


def auto_layout_flowchart(flowchart):
    """Compute and persist tidy positions for every node in a flowchart."""
    nodes = list(flowchart.nodes.all())
    if not nodes:
        return

    children_of = defaultdict(list)
    by_id = {n.id: n for n in nodes}
    roots = []
    for n in nodes:
        if n.parent_id and n.parent_id in by_id:
            children_of[n.parent_id].append(n)
        else:
            roots.append(n)
    for kids in children_of.values():
        kids.sort(key=lambda c: (c.sort_order, c.created_at or 0))
    roots.sort(key=lambda r: (r.sort_order, r.created_at or 0))

    depth_of = {}

    def assign_depth(node, d):
        depth_of[node.id] = d
        for c in children_of[node.id]:
            assign_depth(c, d + 1)

    for r in roots:
        assign_depth(r, 0)

    width_cache = {}

    def subtree_width(node):
        if node.id in width_cache:
            return width_cache[node.id]
        own_w, _ = _size(depth_of[node.id])
        kids = children_of[node.id]
        if not kids:
            w = own_w
        else:
            children_total = sum(subtree_width(k) for k in kids) + H_GAP * (len(kids) - 1)
            w = max(own_w, children_total)
        width_cache[node.id] = w
        return w

    def place(node, x_left, y_top):
        own_w, own_h = _size(depth_of[node.id])
        w = subtree_width(node)
        node.x_pos = x_left + (w - own_w) / 2
        node.y_pos = y_top
        child_y = y_top + own_h + V_GAP
        cx = x_left
        for child in children_of[node.id]:
            cw = subtree_width(child)
            place(child, cx, child_y)
            cx += cw + H_GAP

    x_offset = 0
    for root in roots:
        rw = subtree_width(root)
        place(root, x_offset, 0)
        x_offset += rw + FOREST_GAP

    Node.objects.bulk_update(nodes, ['x_pos', 'y_pos'])
