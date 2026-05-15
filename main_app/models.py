import uuid

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
    image = models.ImageField(
        upload_to='node_images/%Y/%m/',
        blank=True,
        null=True,
        help_text='Optional attached image — useful for screenshots of sub-flows, wireframes, or reference diagrams.',
    )
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


class FlowchartInvitation(models.Model):
    """A pending share for an email that doesn't yet have an InFlow account.

    When the owner shares with a non-existent email, we save it here instead
    of erroring. When someone signs up with that email, the matching invites
    are converted to live FlowchartShare rows automatically.
    """
    flowchart = models.ForeignKey(Flowchart, on_delete=models.CASCADE, related_name='invitations')
    email = models.EmailField()
    can_edit = models.BooleanField(default=False)
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    claimed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('flowchart', 'email')
        ordering = ['-created_at']

    def __str__(self):
        kind = 'edit' if self.can_edit else 'view'
        return f'{self.flowchart.title} → {self.email} ({kind}, pending)'

    @property
    def is_pending(self):
        return self.claimed_at is None


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


# ---------- Documents & signatures (NDA flow) ----------

class Document(models.Model):
    """A signable document — typically an NDA tied to a flowchart/project.

    Owner-managed. Shareable via an unguessable share_token; anyone with the
    link can read the body and sign without an InFlow account.
    """
    STATUS_DRAFT = 'draft'
    STATUS_OPEN = 'open'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft — not shareable yet'),
        (STATUS_OPEN, 'Open for signing'),
        (STATUS_CLOSED, 'Closed — no further signatures'),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    flowchart = models.ForeignKey(
        Flowchart, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='documents',
        help_text='Optional: link this document to a flowchart so collaborators see it in context.',
    )
    title = models.CharField(max_length=160)
    body = models.TextField(
        help_text='The full document text. Paste your NDA / agreement here. Line breaks preserved.',
    )
    disclosing_party_name = models.CharField(
        max_length=160,
        blank=True,
        help_text=(
            'Your full legal name as the Disclosing Party. Auto-populates '
            'the signature block on the generated PDF. Leave blank to use '
            'your account email.'
        ),
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    share_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('document-detail', kwargs={'pk': self.id})

    @property
    def sign_url_path(self):
        return reverse('document-public-sign', kwargs={'token': str(self.share_token)})

    @property
    def signature_count(self):
        return self.signatures.count()


class Signature(models.Model):
    """One signing event on a document. No InFlow account required."""
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='signatures')
    signer_name = models.CharField(
        max_length=160,
        help_text='The full legal name the signer typed.',
    )
    signer_email = models.EmailField(blank=True)
    signed_at = models.DateTimeField(default=timezone.now)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=320, blank=True)
    # The exact text the signer typed in the signature field — usually the
    # same as signer_name, but kept separate in case the cursive rendering
    # is later changed and we want to re-render historical signatures.
    typed_signature = models.CharField(max_length=160)

    class Meta:
        ordering = ['signed_at']

    def __str__(self):
        return f'{self.signer_name} → {self.document.title} ({self.signed_at:%Y-%m-%d})'
