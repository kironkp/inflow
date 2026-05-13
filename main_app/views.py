import json

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Max, Q
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView
from django.views.generic.edit import CreateView, DeleteView, UpdateView

from .forms import FlowchartForm, NodeForm
from .layout import NODE_HEIGHT, NODE_WIDTH, V_GAP, auto_layout_flowchart
from .models import Flowchart, FlowchartShare, Node, NodeLog, NODE_SHAPES, SHAPE_COLORS, Tag

VALID_SHAPES = {s for s, _ in NODE_SHAPES}


def _chart_access(user, pk, require_edit=False):
    """Return (chart, is_owner, can_edit) if `user` can access the flowchart.

    Owners always have full access. Otherwise, an active FlowchartShare row
    must exist; can_edit on that row determines whether writes are allowed.
    Raises Http404 if the user has no access, or if require_edit=True and the
    user only has view access.
    """
    chart = get_object_or_404(Flowchart, pk=pk)
    if chart.user_id == user.id:
        return chart, True, True
    share = chart.shares.filter(user=user).first()
    if share is None:
        raise Http404('Flowchart not found')
    if require_edit and not share.can_edit:
        raise Http404('Flowchart not found')
    return chart, False, share.can_edit


def _node_access(user, pk, require_edit=False):
    """Same shape as _chart_access but starting from a node id."""
    node = get_object_or_404(Node, pk=pk)
    chart = node.flowchart
    if chart.user_id == user.id:
        return node, chart, True, True
    share = chart.shares.filter(user=user).first()
    if share is None:
        raise Http404('Node not found')
    if require_edit and not share.can_edit:
        raise Http404('Node not found')
    return node, chart, False, share.can_edit


def _build_preview(nodes):
    """Render-ready dict for the home page SVG snapshot. None if no nodes."""
    nodes = list(nodes)
    if not nodes:
        return None
    serialized = _serialize_nodes(nodes)
    NODE_W, NODE_H = 200, 96
    min_x = min(n['x'] for n in serialized)
    min_y = min(n['y'] for n in serialized)
    max_x = max(n['x'] + NODE_W for n in serialized)
    max_y = max(n['y'] + NODE_H for n in serialized)
    pad = 40
    by_id = {n['id']: n for n in serialized}
    nodes_render = []
    for n in serialized:
        nodes_render.append({
            **n,
            'w': NODE_W,
            'h': NODE_H,
            'text_x': n['x'] + 14,
            'shape_text_y': n['y'] + 22,
            'label_text_y': n['y'] + 48,
            'subtitle_text_y': n['y'] + 70,
        })
    edges = []
    for n in serialized:
        if not n['parent_id'] or n['parent_id'] not in by_id:
            continue
        p = by_id[n['parent_id']]
        sx = p['x'] + NODE_W / 2
        sy = p['y'] + NODE_H
        tx = n['x'] + NODE_W / 2
        ty = n['y']
        dy = max(40, (ty - sy) * 0.6)
        edges.append({
            'd': f'M {sx} {sy} C {sx} {sy + dy}, {tx} {ty - dy}, {tx} {ty}',
            'branch_label': n['branch_label'],
            'mx': (sx + tx) / 2,
            'my': (sy + ty) / 2 - 4,
        })
    return {
        'view_x': min_x - pad,
        'view_y': min_y - pad,
        'view_w': max_x - min_x + pad * 2,
        'view_h': max_y - min_y + pad * 2,
        'nodes': nodes_render,
        'edges': edges,
    }


def _serialize_nodes(nodes):
    """Shape every node into the dict the canvas JS expects."""
    return [
        {
            'id': n.id,
            'parent_id': n.parent_id,
            'label': n.label,
            'subtitle': n.subtitle,
            'shape': n.shape,
            'shape_display': n.get_shape_display(),
            'branch_label': n.branch_label,
            'color': n.color or SHAPE_COLORS.get(n.shape, '#1B4D5A'),
            'x': n.x_pos,
            'y': n.y_pos,
            'detail_url': reverse('node-detail', kwargs={'pk': n.id}),
        }
        for n in nodes
    ]


def _initial_position(chart, parent):
    """Pick a sensible starting (x, y) for a freshly created node."""
    if parent is None:
        roots = Node.objects.filter(flowchart=chart, parent__isnull=True)
        max_x = roots.aggregate(m=Max('x_pos'))['m']
        if max_x is None:
            return 0.0, 0.0
        return max_x + NODE_WIDTH + 80, 0.0
    siblings = Node.objects.filter(flowchart=chart, parent=parent)
    child_y = parent.y_pos + NODE_HEIGHT + V_GAP
    max_x = siblings.aggregate(m=Max('x_pos'))['m']
    if max_x is None:
        return parent.x_pos, child_y
    return max_x + NODE_WIDTH + 36, child_y


@ensure_csrf_cookie
def home(request):
    if request.user.is_authenticated:
        charts = list(
            Flowchart.objects.filter(user=request.user, archived=False)
            .annotate(n_nodes=Count('nodes'))
            .order_by('-updated_at')[:6]
        )
        most_recent = charts[0] if charts else None
        preview = _build_preview(most_recent.nodes.all()) if most_recent else None

        recent_changes = (
            NodeLog.objects
            .filter(node__flowchart__user=request.user)
            .select_related('node', 'node__flowchart')[:6]
        )

        context = {
            'charts': charts,
            'most_recent': most_recent,
            'preview': preview,
            'recent_changes': recent_changes,
            'flowchart_count': Flowchart.objects.filter(user=request.user, archived=False).count(),
            'node_count': Node.objects.filter(flowchart__user=request.user).count(),
        }
        return render(request, 'home.html', context)
    return render(request, 'home.html')


def about(request):
    return render(request, 'about.html')


def signup(request):
    error_message = ''
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            chart = Flowchart.objects.create(
                user=user,
                title='My First Flow',
                description='A starter flowchart — drag nodes to rearrange, scroll to zoom, shift+drag to box-select.',
            )
            start = Node.objects.create(
                flowchart=chart, label='Start', shape='start', sort_order=0,
                subtitle='where the flow begins',
            )
            step = Node.objects.create(
                flowchart=chart, label='Do the thing', shape='process',
                parent=start, sort_order=1, subtitle='the actual work',
            )
            decision = Node.objects.create(
                flowchart=chart, label='Worked?', shape='decision',
                parent=step, sort_order=2, subtitle='yes / no branch',
            )
            Node.objects.create(
                flowchart=chart, label='Done', shape='start', parent=decision,
                branch_label='Yes', sort_order=3, subtitle='wrap up',
            )
            Node.objects.create(
                flowchart=chart, label='Try again', shape='process', parent=decision,
                branch_label='No', sort_order=4, subtitle='loop back to the step',
            )
            auto_layout_flowchart(chart)
            login(request, user)
            return redirect('flowchart-index')
        error_message = 'Invalid sign up - try again'
    form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form, 'error': error_message})


# ---------- Flowcharts ----------

@login_required
def flowchart_index(request):
    charts = (
        Flowchart.objects.filter(user=request.user)
        .annotate(n_nodes=Count('nodes'))
    )
    show_archived = request.GET.get('archived') == '1'
    if not show_archived:
        charts = charts.filter(archived=False)
    query = request.GET.get('q', '').strip()
    if query:
        charts = charts.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )
    shared_charts = (
        Flowchart.objects
        .filter(shares__user=request.user, archived=False)
        .select_related('user')
        .annotate(n_nodes=Count('nodes', distinct=True))
        .distinct()
        .order_by('-updated_at')
    )
    # Attach the share row (for can_edit / shared-by display) onto each shared chart.
    share_by_chart = {
        s.flowchart_id: s
        for s in FlowchartShare.objects.filter(user=request.user)
        .select_related('flowchart')
    }
    for c in shared_charts:
        s = share_by_chart.get(c.id)
        c.share_can_edit = s.can_edit if s else False
        c.shared_by = c.user.username
    return render(request, 'flowcharts/index.html', {
        'charts': charts,
        'shared_charts': shared_charts,
        'query': query,
        'show_archived': show_archived,
        'no_match_query': query if query and not charts.exists() else '',
    })


class FlowchartCreate(LoginRequiredMixin, CreateView):
    model = Flowchart
    form_class = FlowchartForm

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class FlowchartUpdate(LoginRequiredMixin, UpdateView):
    model = Flowchart
    form_class = FlowchartForm

    def get_queryset(self):
        return Flowchart.objects.filter(user=self.request.user)


class FlowchartDelete(LoginRequiredMixin, DeleteView):
    model = Flowchart
    success_url = reverse_lazy('flowchart-index')

    def get_queryset(self):
        return Flowchart.objects.filter(user=self.request.user)


@login_required
@ensure_csrf_cookie
def flowchart_detail(request, pk):
    chart, is_owner, can_edit = _chart_access(request.user, pk)
    nodes = list(chart.nodes.all())
    nodes_json = json.dumps(_serialize_nodes(nodes))
    recent_logs = (
        NodeLog.objects.filter(node__flowchart=chart)
        .select_related('node')[:8]
    )
    return render(request, 'flowcharts/detail.html', {
        'chart': chart,
        'nodes_json': nodes_json,
        'node_count': len(nodes),
        'recent_logs': recent_logs,
        'is_owner': is_owner,
        'can_edit': can_edit,
    })


@login_required
def flowchart_archive(request, pk):
    chart = get_object_or_404(Flowchart, pk=pk, user=request.user)
    if request.method == 'POST':
        chart.archived = not chart.archived
        chart.save(update_fields=['archived', 'updated_at'])
    return redirect('flowchart-index')


@login_required
@require_POST
def flowchart_auto_layout(request, pk):
    """Retidy every node's position with the tree algorithm."""
    chart, _, _ = _chart_access(request.user, pk, require_edit=True)
    auto_layout_flowchart(chart)
    chart.save(update_fields=['updated_at'])
    return JsonResponse({'ok': True})


@login_required
@require_POST
def flowchart_batch_positions(request, pk):
    """Persist drag results. Body: {"positions": [{"id": 1, "x": 100, "y": 200}, ...]}"""
    chart, _, _ = _chart_access(request.user, pk, require_edit=True)
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    rows = payload.get('positions')
    if not isinstance(rows, list):
        return JsonResponse({'error': 'positions must be a list'}, status=400)
    # Build map of valid (id -> (x, y)) limited to this chart's nodes.
    requested = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            nid = int(row.get('id'))
            x = float(row.get('x'))
            y = float(row.get('y'))
        except (TypeError, ValueError):
            continue
        requested[nid] = (x, y)
    if not requested:
        return JsonResponse({'ok': True, 'updated': 0})
    nodes = list(Node.objects.filter(flowchart=chart, id__in=requested.keys()))
    for n in nodes:
        n.x_pos, n.y_pos = requested[n.id]
    with transaction.atomic():
        Node.objects.bulk_update(nodes, ['x_pos', 'y_pos'])
        chart.save(update_fields=['updated_at'])
    return JsonResponse({'ok': True, 'updated': len(nodes)})


# ---------- Nodes ----------

@login_required
def node_create(request, flowchart_pk):
    chart, _, _ = _chart_access(request.user, flowchart_pk, require_edit=True)
    if request.method == 'POST':
        form = NodeForm(request.POST, flowchart=chart)
        if form.is_valid():
            node = form.save(commit=False)
            node.flowchart = chart
            siblings = Node.objects.filter(flowchart=chart, parent=node.parent)
            node.sort_order = (siblings.aggregate(m=Max('sort_order'))['m'] or 0) + 1
            node.x_pos, node.y_pos = _initial_position(chart, node.parent)
            node.save()
            form.save_m2m()
            NodeLog.objects.create(node=node, action='created', note='Node created')
            chart.save(update_fields=['updated_at'])
            return redirect('flowchart-detail', pk=chart.pk)
    else:
        initial = {}
        parent_id = request.GET.get('parent')
        if parent_id and parent_id.isdigit():
            if Node.objects.filter(pk=parent_id, flowchart=chart).exists():
                initial['parent'] = parent_id
        form = NodeForm(flowchart=chart, initial=initial)
    return render(request, 'main_app/node_form.html', {
        'form': form,
        'chart': chart,
    })


class NodeDetail(LoginRequiredMixin, DetailView):
    model = Node
    context_object_name = 'node'
    template_name = 'main_app/node_detail.html'

    def get_queryset(self):
        u = self.request.user
        return Node.objects.filter(
            Q(flowchart__user=u) | Q(flowchart__shares__user=u)
        ).distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['children'] = self.object.children.all()
        ctx['logs'] = self.object.logs.all()[:10]
        ctx['available_tags'] = Tag.objects.exclude(id__in=self.object.tags.values_list('id'))
        return ctx


class NodeUpdate(LoginRequiredMixin, UpdateView):
    model = Node
    form_class = NodeForm

    def get_queryset(self):
        u = self.request.user
        return Node.objects.filter(
            Q(flowchart__user=u) |
            Q(flowchart__shares__user=u, flowchart__shares__can_edit=True)
        ).distinct()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['flowchart'] = self.object.flowchart
        return kwargs

    def form_valid(self, form):
        old_parent_id = Node.objects.filter(pk=self.object.pk).values_list('parent_id', flat=True).first()
        response = super().form_valid(form)
        if old_parent_id != self.object.parent_id:
            NodeLog.objects.create(node=self.object, action='moved', note='Parent changed')
        else:
            NodeLog.objects.create(node=self.object, action='edited', note='Edited')
        self.object.flowchart.save(update_fields=['updated_at'])
        return response

    def get_success_url(self):
        return reverse('flowchart-detail', kwargs={'pk': self.object.flowchart_id})


class NodeDelete(LoginRequiredMixin, DeleteView):
    model = Node
    template_name = 'main_app/node_confirm_delete.html'

    def get_queryset(self):
        u = self.request.user
        return Node.objects.filter(
            Q(flowchart__user=u) |
            Q(flowchart__shares__user=u, flowchart__shares__can_edit=True)
        ).distinct()

    def get_success_url(self):
        return reverse('flowchart-detail', kwargs={'pk': self.object.flowchart_id})


@login_required
@require_POST
def node_reparent(request, pk):
    """Change a node's parent without auto-relayout (canvas keeps positions)."""
    node, _, _, _ = _node_access(request.user, pk, require_edit=True)
    parent_id_raw = request.POST.get('parent_id')
    new_parent = None
    if parent_id_raw and parent_id_raw not in ('', 'null', 'none'):
        try:
            new_parent = Node.objects.get(
                pk=int(parent_id_raw),
                flowchart=node.flowchart,
            )
        except (Node.DoesNotExist, ValueError, TypeError):
            return JsonResponse({'error': 'Parent not found'}, status=404)
        if new_parent.id == node.id:
            return JsonResponse({'error': "Can't be its own parent"}, status=400)
        cur = new_parent
        seen = set()
        while cur:
            if cur.id == node.id:
                return JsonResponse({'error': "Can't move a node into its own descendant"}, status=400)
            if cur.id in seen:
                break
            seen.add(cur.id)
            cur = cur.parent
    node.parent = new_parent
    node.save(update_fields=['parent'])
    NodeLog.objects.create(node=node, action='moved', note='Reparented')
    node.flowchart.save(update_fields=['updated_at'])
    return JsonResponse({'ok': True})


@login_required
@require_POST
def node_quick_add(request, flowchart_pk):
    """Add a child node inline from the canvas (used by the in-canvas + button)."""
    chart, _, _ = _chart_access(request.user, flowchart_pk, require_edit=True)
    label = (request.POST.get('label') or '').strip()[:120]
    if not label:
        return JsonResponse({'error': 'Label is required'}, status=400)
    parent_id_raw = request.POST.get('parent_id')
    parent = None
    if parent_id_raw and parent_id_raw not in ('', 'null', 'none'):
        try:
            parent = Node.objects.get(pk=int(parent_id_raw), flowchart=chart)
        except (Node.DoesNotExist, ValueError, TypeError):
            return JsonResponse({'error': 'Parent not found'}, status=404)
    shape = request.POST.get('shape', 'process')
    if shape not in VALID_SHAPES:
        shape = 'process'
    branch_label = (request.POST.get('branch_label') or '').strip()[:40]
    subtitle = (request.POST.get('subtitle') or '').strip()[:160]
    siblings = Node.objects.filter(flowchart=chart, parent=parent)
    new_order = (siblings.aggregate(m=Max('sort_order'))['m'] or 0) + 1
    x_pos, y_pos = _initial_position(chart, parent)
    node = Node.objects.create(
        flowchart=chart,
        parent=parent,
        label=label,
        subtitle=subtitle,
        shape=shape,
        branch_label=branch_label,
        sort_order=new_order,
        x_pos=x_pos,
        y_pos=y_pos,
    )
    NodeLog.objects.create(node=node, action='created', note='Quick add')
    chart.save(update_fields=['updated_at'])
    return JsonResponse({
        'ok': True,
        'node': _serialize_nodes([node])[0],
    })


@login_required
@require_POST
def node_quick_delete(request, pk):
    """Delete a node + every descendant in one hit (used by canvas keybind)."""
    node, chart, _, _ = _node_access(request.user, pk, require_edit=True)
    node.delete()
    chart.save(update_fields=['updated_at'])
    return JsonResponse({'ok': True})


@login_required
@require_POST
def node_add_tag(request, pk, tag_id):
    node, _, _, _ = _node_access(request.user, pk, require_edit=True)
    tag = get_object_or_404(Tag, pk=tag_id)
    node.tags.add(tag)
    return redirect('node-detail', pk=node.pk)


@login_required
@require_POST
def node_remove_tag(request, pk, tag_id):
    node, _, _, _ = _node_access(request.user, pk, require_edit=True)
    tag = get_object_or_404(Tag, pk=tag_id)
    node.tags.remove(tag)
    return redirect('node-detail', pk=node.pk)


# ---------- Share ----------

@login_required
def flowchart_share(request, pk):
    """List + manage who a flowchart is shared with. Owner only."""
    chart = get_object_or_404(Flowchart, pk=pk, user=request.user)
    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        can_edit = request.POST.get('can_edit') == '1'
        if not username:
            messages.error(request, 'Enter a username.')
        elif username.lower() == request.user.username.lower():
            messages.error(request, "You can't share with yourself.")
        else:
            try:
                target = User.objects.get(username__iexact=username)
                _, created = FlowchartShare.objects.update_or_create(
                    flowchart=chart, user=target,
                    defaults={'can_edit': can_edit},
                )
                kind = 'edit' if can_edit else 'view-only'
                if created:
                    messages.success(request, f'Shared with {target.username} ({kind}).')
                else:
                    messages.success(request, f'Updated {target.username} to {kind}.')
            except User.DoesNotExist:
                messages.error(request, f'No user named "{username}".')
        return redirect('flowchart-share', pk=chart.pk)
    shares = chart.shares.select_related('user').order_by('-created_at')
    return render(request, 'flowcharts/share.html', {
        'chart': chart,
        'shares': shares,
    })


@login_required
@require_POST
def flowchart_share_remove(request, pk, share_id):
    chart = get_object_or_404(Flowchart, pk=pk, user=request.user)
    share = chart.shares.filter(pk=share_id).first()
    if share:
        username = share.user.username
        share.delete()
        messages.success(request, f'Removed {username}.')
    return redirect('flowchart-share', pk=chart.pk)


# ---------- Tags (shared catalog) ----------

class TagList(LoginRequiredMixin, ListView):
    model = Tag
    context_object_name = 'tags'
    template_name = 'main_app/tag_list.html'


class TagDetail(LoginRequiredMixin, DetailView):
    model = Tag
    context_object_name = 'tag'
    template_name = 'main_app/tag_detail.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['nodes'] = self.object.nodes.filter(flowchart__user=self.request.user)
        return ctx


class TagCreate(LoginRequiredMixin, CreateView):
    model = Tag
    fields = ['name', 'color']
    success_url = reverse_lazy('tag-index')
    template_name = 'main_app/tag_form.html'


class TagUpdate(LoginRequiredMixin, UpdateView):
    model = Tag
    fields = ['name', 'color']
    success_url = reverse_lazy('tag-index')
    template_name = 'main_app/tag_form.html'


class TagDelete(LoginRequiredMixin, DeleteView):
    model = Tag
    success_url = reverse_lazy('tag-index')
    template_name = 'main_app/tag_confirm_delete.html'
