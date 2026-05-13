from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse
from django.utils import timezone


NODE_SHAPES = [
    ('process', 'Process'),
    ('start', 'Start / End'),
    ('decision', 'Decision'),
    ('io', 'Input / Output'),
    ('data', 'Data'),
    ('note', 'Note'),
]

SHAPE_COLORS = {
    'process': '#14383F',
    'start': '#2A6B45',
    'decision': '#B5821A',
    'io': '#4A6FA5',
    'data': '#5B4B8A',
    'note': '#8C7A55',
}


class Tag(models.Model):
    """Shared catalog of labels usable across any user's nodes.

    Mirrors FindIt's Tag — a flat, cross-user catalog so multiple people can
    converge on the same vocabulary (e.g. "Approval", "Manual step", "Risk").
    """
    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=20, default='#14383F')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('tag-index')


class Flowchart(models.Model):
    """A single flowchart owned by a user. Acts as a namespace for nodes."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='flowcharts')
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('flowchart-detail', kwargs={'pk': self.id})

    @property
    def node_count(self):
        return self.nodes.count()


class Node(models.Model):
    """A single shape in a flowchart. Linked to a parent for tree structure."""
    flowchart = models.ForeignKey(Flowchart, on_delete=models.CASCADE, related_name='nodes')
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
    )
    label = models.CharField(max_length=120)
    subtitle = models.CharField(
        max_length=160,
        blank=True,
        help_text='Optional second line rendered as small italic text under the label.',
    )
    shape = models.CharField(max_length=20, choices=NODE_SHAPES, default='process')
    branch_label = models.CharField(
        max_length=40,
        blank=True,
        help_text='Optional label shown on the line from the parent (e.g. "Yes", "No").',
    )
    description = models.TextField(blank=True)
    color = models.CharField(
        max_length=20,
        blank=True,
        help_text='Optional override. Leave blank to use the shape default color.',
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name='nodes')
    sort_order = models.PositiveIntegerField(default=0)
    x_pos = models.FloatField(default=0)
    y_pos = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'created_at']

    def __str__(self):
        return self.label

    def get_absolute_url(self):
        return reverse('node-detail', kwargs={'pk': self.id})

    @property
    def display_color(self):
        return self.color or SHAPE_COLORS.get(self.shape, '#14383F')

    def breadcrumb(self):
        parts = [self.label]
        node = self.parent
        seen = {self.id}
        while node and node.id not in seen:
            seen.add(node.id)
            parts.append(node.label)
            node = node.parent
        return ' › '.join(reversed(parts))


class FlowchartShare(models.Model):
    """Grants another user access to a flowchart.

    The owning user retains full control. A share row gives the recipient
    read-only access by default, or read-write if can_edit is True.
    """
    flowchart = models.ForeignKey(Flowchart, on_delete=models.CASCADE, related_name='shares')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shared_flowcharts')
    can_edit = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('flowchart', 'user')
        ordering = ['-created_at']

    def __str__(self):
        kind = 'edit' if self.can_edit else 'view'
        return f'{self.flowchart.title} → {self.user.username} ({kind})'


class NodeLog(models.Model):
    """Audit trail of edits to a node (rename, reparent, shape change)."""
    node = models.ForeignKey(Node, on_delete=models.CASCADE, related_name='logs')
    action = models.CharField(max_length=40)
    note = models.CharField(max_length=240, blank=True)
    changed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-changed_at']

    def __str__(self):
        return f'{self.node.label} · {self.action} · {self.changed_at:%Y-%m-%d}'
