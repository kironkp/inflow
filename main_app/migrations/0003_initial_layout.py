"""Run auto-layout on every existing flowchart so x_pos / y_pos are tidy
rather than all (0, 0). Safe to no-op on a fresh DB.
"""
from collections import defaultdict

from django.db import migrations


NODE_WIDTH = 200
NODE_HEIGHT = 96
H_GAP = 36
V_GAP = 80
FOREST_GAP = 80


def _layout_chart(Node, chart_id):
    nodes = list(Node.objects.filter(flowchart_id=chart_id))
    if not nodes:
        return
    by_id = {n.id: n for n in nodes}
    children_of = defaultdict(list)
    roots = []
    for n in nodes:
        if n.parent_id and n.parent_id in by_id:
            children_of[n.parent_id].append(n)
        else:
            roots.append(n)
    for kids in children_of.values():
        kids.sort(key=lambda c: (c.sort_order, c.created_at))
    roots.sort(key=lambda r: (r.sort_order, r.created_at))

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


def forwards(apps, schema_editor):
    Flowchart = apps.get_model('main_app', 'Flowchart')
    Node = apps.get_model('main_app', 'Node')
    for chart in Flowchart.objects.all():
        _layout_chart(Node, chart.id)


def backwards(apps, schema_editor):
    # No-op: dropping positions is meaningless and the column is removed by 0002 rollback anyway.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('main_app', '0002_node_subtitle_node_x_pos_node_y_pos'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
