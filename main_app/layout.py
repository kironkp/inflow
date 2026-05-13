"""Tidy-tree layout for flowchart nodes.

Each node has an absolute (x_pos, y_pos) on the canvas. Auto-layout computes
those positions so the tree reads top-down, parents centered above their
children. Manual drags overwrite the positions; users can call auto-layout
again to retidy.
"""
from collections import defaultdict

from .models import Node


NODE_WIDTH = 200
NODE_HEIGHT = 96
H_GAP = 36       # horizontal gap between sibling subtrees
V_GAP = 80       # vertical gap between a parent and its children
FOREST_GAP = 80  # extra horizontal gap between separate root trees


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

    width_cache = {}

    def subtree_width(node):
        if node.id in width_cache:
            return width_cache[node.id]
        kids = children_of[node.id]
        if not kids:
            w = NODE_WIDTH
        else:
            w = sum(subtree_width(k) for k in kids) + H_GAP * (len(kids) - 1)
            w = max(NODE_WIDTH, w)
        width_cache[node.id] = w
        return w

    def place(node, x_left, y_top):
        w = subtree_width(node)
        node.x_pos = x_left + (w - NODE_WIDTH) / 2
        node.y_pos = y_top
        child_y = y_top + NODE_HEIGHT + V_GAP
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
