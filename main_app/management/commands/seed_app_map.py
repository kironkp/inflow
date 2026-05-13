"""Seed the VR/AR DAW App Map flowchart for a user.

Usage:
    python manage.py seed_app_map --user kiron

Creates a new flowchart titled "VR/AR DAW · App Map" with ~120 nodes
mirroring Tab 1 of the source HTML. Nodes are colored by section, with
red highlighting on the "novel-candidate" interactions (the ones flagged
with ← in the original diagram). Auto-layout is applied at the end so the
chart opens cleanly tidy.
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from main_app.layout import auto_layout_flowchart
from main_app.models import Flowchart, Node


# Section colors mirror the original HTML's per-band tints.
SECTION_COLORS = {
    'root':    '#102026',  # ink — root node
    'channel': '#2F6A3B',  # green — channel strip
    'master':  '#6B7A45',  # olive — master strip (mixer-family but distinct)
    'aux':     '#45596B',  # slate blue — aux / send buses
    'inst':    '#A26A0F',  # orange — instrument wall
    'fx':      '#4C2D8E',  # purple — effects wall
    'active':  '#2D4F78',  # blue — active instrument
    'tutor':   '#5E4577',  # lavender — AI tutor
    'wrist':   '#7A5A00',  # tan — wrist + session
    'novel':   '#B85450',  # red — novel-candidate (overrides section)
}


# Tree definition. Each dict supports:
#   label     (required)
#   shape     (default 'process')
#   subtitle  (optional, rendered italic under the label)
#   section   (optional, sets/overrides the color band for the subtree)
#   novel     (optional, paints the node red regardless of section)
#   branch_label (optional, text on the connector from its parent)
#   children  (optional list)
TREE = {
    'label': 'USER IN SESSION',
    'shape': 'start',
    'subtitle': 'default state · all actions branch from here',
    'section': 'root',
    'children': [
        # ===================== CHANNEL STRIP =====================
        {
            'label': 'CHANNEL STRIP',
            'subtitle': 'always present · on table',
            'section': 'channel',
            'children': [
                {'label': 'Tap Options', 'subtitle': 'context menu', 'children': [
                    {'label': 'Duplicate'},
                    {'label': 'Delete'},
                    {'label': 'Freeze'},
                    {'label': 'Group'},
                ]},
                {'label': 'Tap Color', 'subtitle': 'open color picker'},
                {'label': 'Tap Name', 'subtitle': 'rename channel'},
                {'label': 'Input port', 'shape': 'io', 'novel': True,
                 'subtitle': 'spatial routing source',
                 'children': [
                    {'label': 'Drag to instr.', 'novel': True, 'subtitle': 'route input'},
                    {'label': 'Drag to FX', 'novel': True, 'subtitle': 'sidechain / process'},
                    {'label': 'Cancel'},
                ]},
                {'label': 'Tap Comp', 'subtitle': '1-knob compressor', 'children': [
                    {'label': 'Amount (tutor)', 'novel': True,
                     'subtitle': 'tutor suggests preset based on track'},
                    {'label': 'Bypass'},
                ]},
                {'label': 'Tap HI', 'subtitle': 'treble band'},
                {'label': 'Tap MID', 'subtitle': 'mid band'},
                {'label': 'Tap LO', 'subtitle': 'bass band'},
                {'label': 'Bypass EQ'},
                {'label': 'Tap Pan'},
                {'label': 'Tap Volume', 'subtitle': 'fader'},
                {'label': 'Tap Mute'},
                {'label': 'Tap Solo'},
                {'label': 'Output port', 'shape': 'io', 'novel': True,
                 'subtitle': 'spatial routing target',
                 'children': [
                    {'label': 'Drag to Send', 'novel': True},
                    {'label': 'Drag to Bus', 'novel': True},
                    {'label': 'Drag to Master', 'novel': True},
                    {'label': 'Drag to FX', 'novel': True},
                    {'label': 'Cancel'},
                ]},
                {'label': 'Drag — reorder', 'subtitle': 'shuffle strips'},
                {'label': 'Resize', 'novel': True, 'subtitle': 'change strip footprint', 'children': [
                    {'label': 'Drag corner', 'novel': True},
                    {'label': '+ button'},
                    {'label': '− button'},
                ]},
                {'label': 'Move', 'novel': True, 'subtitle': 'reposition in space', 'children': [
                    {'label': 'Snap to surface', 'novel': True, 'subtitle': 'snap to detected table'},
                    {'label': 'Free-float', 'subtitle': 'no surface? float'},
                ]},
            ],
        },
        # ===================== MASTER STRIP =====================
        {
            'label': 'MASTER STRIP',
            'subtitle': 'sum bus · transport hub · end of chain',
            'section': 'master',
            'children': [
                {'label': 'Transport', 'subtitle': 'global playback — lives on the master', 'children': [
                    {'label': 'Play / Stop', 'subtitle': 'tap or voice — global'},
                    {'label': 'Record', 'subtitle': 'captures armed channels'},
                    {'label': 'Loop toggle'},
                    {'label': 'Metronome'},
                    {'label': 'Time signature'},
                    {'label': 'BPM display', 'subtitle': 'tap to type a value'},
                    {'label': 'Tap-tempo (mid-air)', 'novel': True,
                     'subtitle': 'tap hand in space to set BPM'},
                ]},
                {'label': 'Tap HI', 'subtitle': 'master EQ · treble'},
                {'label': 'Tap MID'},
                {'label': 'Tap LO'},
                {'label': 'Bypass EQ'},
                {'label': 'Tap Comp', 'subtitle': 'master bus glue', 'children': [
                    {'label': 'Amount (tutor)', 'novel': True,
                     'subtitle': 'tutor-suggested master compression'},
                    {'label': 'Bypass'},
                ]},
                {'label': 'Tap Pan'},
                {'label': 'Tap Volume', 'subtitle': 'master fader'},
                {'label': 'Tap Mute', 'subtitle': 'panic — silence everything'},
                {'label': 'Master meter', 'subtitle': 'visual level / clipping indicator'},
                {'label': 'Output port', 'shape': 'io', 'novel': True,
                 'subtitle': 'where the mix goes', 'children': [
                    {'label': 'Drag to physical out', 'novel': True,
                     'subtitle': 'headphones / monitors'},
                    {'label': 'Drag to record bounce', 'novel': True,
                     'subtitle': 'capture as audio file'},
                ]},
                {'label': 'Tap Options', 'subtitle': 'context menu', 'children': [
                    {'label': 'Color'},
                    {'label': 'Rename'},
                ]},
                {'label': 'Resize', 'novel': True, 'children': [
                    {'label': 'Drag corner', 'novel': True},
                    {'label': '+ button'},
                    {'label': '− button'},
                ]},
                {'label': 'Move', 'novel': True, 'children': [
                    {'label': 'Snap to surface', 'novel': True},
                    {'label': 'Free-float'},
                ]},
                {'label': 'Show / Hide'},
            ],
        },
        # ===================== AUX STRIPS =====================
        {
            'label': 'AUX STRIPS',
            'subtitle': 'parallel routing · reverb bus, delay bus, stems',
            'section': 'aux',
            'children': [
                {'label': 'Create Aux', 'subtitle': 'spawn a new aux strip', 'children': [
                    {'label': 'Tap "+ Aux" on mixer'},
                    {'label': 'Drag send → empty space', 'novel': True,
                     'subtitle': 'creates aux from a channel send'},
                ]},
                {'label': 'Tap Name', 'subtitle': 'e.g. "Reverb Bus"'},
                {'label': 'Tap Color'},
                {'label': 'Tap Options', 'children': [
                    {'label': 'Duplicate'},
                    {'label': 'Delete'},
                    {'label': 'Rename'},
                    {'label': 'Color'},
                    {'label': 'Group'},
                ]},
                {'label': 'Input (sends only)', 'shape': 'io', 'novel': True,
                 'subtitle': 'no mic/line — dashed input port'},
                {'label': 'Tap HI', 'subtitle': 'treble'},
                {'label': 'Tap MID'},
                {'label': 'Tap LO'},
                {'label': 'Bypass EQ'},
                {'label': 'Tap Comp', 'children': [
                    {'label': 'Amount (tutor)', 'novel': True},
                    {'label': 'Bypass'},
                ]},
                {'label': 'Tap Pan'},
                {'label': 'Tap Volume'},
                {'label': 'Tap Mute'},
                {'label': 'Tap Solo', 'subtitle': 'isolate this bus'},
                {'label': 'Output port', 'shape': 'io', 'novel': True,
                 'subtitle': 'defaults to master', 'children': [
                    {'label': 'Drag to Master', 'novel': True, 'subtitle': 'default'},
                    {'label': 'Drag to another Bus', 'novel': True, 'subtitle': 'aux of an aux'},
                    {'label': 'Drag to FX', 'novel': True, 'subtitle': 'further parallel'},
                ]},
                {'label': 'Resize', 'novel': True, 'children': [
                    {'label': 'Drag corner', 'novel': True},
                    {'label': '+ button'},
                    {'label': '− button'},
                ]},
                {'label': 'Move', 'novel': True, 'children': [
                    {'label': 'Snap to surface', 'novel': True},
                    {'label': 'Free-float'},
                ]},
                {'label': 'Show / Hide'},
            ],
        },
        # ===================== INSTRUMENT WALL =====================
        {
            'label': 'INSTRUMENT WALL',
            'subtitle': 'summoned · wrist button',
            'section': 'inst',
            'children': [
                {'label': 'Tap instr. tile', 'novel': True,
                 'subtitle': 'spawn instrument into space', 'children': [
                    {'label': 'Drop on surface', 'novel': True, 'subtitle': 'snap to detected table'},
                    {'label': 'Drop in air', 'subtitle': 'float free'},
                    {'label': 'Cancel'},
                ]},
                {'label': 'Long-press tile', 'subtitle': 'tile context menu', 'children': [
                    {'label': 'Favorite / Unfav'},
                    {'label': 'Audition / preview'},
                    {'label': 'Info'},
                ]},
                {'label': 'Tap category btn', 'subtitle': 'filter the wall', 'children': [
                    {'label': 'Drums'},
                    {'label': 'Synths'},
                    {'label': 'Guitars'},
                    {'label': 'Bass'},
                    {'label': 'Orchestral'},
                    {'label': 'Strings'},
                    {'label': 'Pads'},
                    {'label': 'All'},
                    {'label': 'Favs only'},
                ]},
                {'label': 'Tap Dismiss', 'subtitle': 'hide the wall'},
            ],
        },
        # ===================== EFFECTS WALL =====================
        {
            'label': 'EFFECTS WALL',
            'subtitle': 'summoned · wrist button',
            'section': 'fx',
            'children': [
                {'label': 'Tap effect tile', 'novel': True,
                 'subtitle': 'drop FX onto signal path', 'children': [
                    {'label': 'Drag to chan strip', 'novel': True, 'subtitle': 'insert on channel'},
                    {'label': 'Drag to existing FX', 'novel': True, 'subtitle': 'chain after FX'},
                    {'label': 'Drag to Send/Aux', 'novel': True, 'subtitle': 'parallel routing'},
                    {'label': 'Cancel (in air)'},
                ]},
                {'label': 'Long-press tile', 'children': [
                    {'label': 'Favorite / Unfav'},
                    {'label': 'Audition / preview'},
                    {'label': 'Info'},
                ]},
                {'label': 'Tap category btn', 'children': [
                    {'label': 'Time'},
                    {'label': 'Dynamics'},
                    {'label': 'EQ / Filter'},
                    {'label': 'Modulation'},
                    {'label': 'Saturation'},
                    {'label': 'Creative / FX'},
                    {'label': 'All'},
                    {'label': 'Favs only'},
                ]},
                {'label': 'Tap Dismiss'},
            ],
        },
        # ===================== ACTIVE INSTRUMENT =====================
        {
            'label': 'ACTIVE INSTRUMENT',
            'subtitle': 'whatever the user is playing',
            'section': 'active',
            'children': [
                {'label': 'Tap key/pad', 'novel': True, 'subtitle': 'spatial keypress'},
                {'label': 'Tap knob', 'subtitle': 'grab & turn in 3D', 'children': [
                    {'label': 'Filter cutoff'},
                    {'label': 'Resonance'},
                    {'label': 'Envelope'},
                    {'label': 'LFO'},
                    {'label': 'Oscillator'},
                    {'label': 'Pad sensitivity'},
                ]},
                {'label': 'Tap button', 'children': [
                    {'label': 'Octave +'},
                    {'label': 'Octave −'},
                    {'label': 'Latch / hold'},
                    {'label': 'Arpeggiator'},
                    {'label': 'Sustain'},
                ]},
                {'label': 'MIDI view', 'novel': True, 'subtitle': 'spatial piano-roll'},
                {'label': 'Tap Preset', 'children': [
                    {'label': 'Next preset'},
                    {'label': 'Prev preset'},
                    {'label': 'Save preset'},
                    {'label': 'Browse list'},
                ]},
                {'label': 'Switch instr.', 'subtitle': 'replace with another'},
                {'label': 'Tap Options', 'children': [
                    {'label': 'Duplicate'},
                    {'label': 'Delete'},
                    {'label': 'Rename'},
                    {'label': 'Color'},
                    {'label': 'Group'},
                ]},
                {'label': 'Resize', 'novel': True, 'children': [
                    {'label': 'Drag corner', 'novel': True},
                    {'label': '+ button'},
                    {'label': '− button'},
                ]},
                {'label': 'Move', 'novel': True, 'children': [
                    {'label': 'Snap to surface', 'novel': True},
                    {'label': 'Free-float'},
                ]},
                {'label': 'Show / Hide', 'subtitle': 'toggle visibility'},
            ],
        },
        # ===================== AI TUTOR =====================
        {
            'label': 'AI TUTOR',
            'subtitle': 'ambient · gaze + voice',
            'section': 'tutor',
            'children': [
                {'label': 'Ask (gaze + voice)', 'novel': True,
                 'subtitle': 'point at thing, ask question', 'children': [
                    {'label': '"Show me X"',      'shape': 'note', 'novel': True},
                    {'label': '"What is this?"', 'shape': 'note', 'novel': True},
                    {'label': '"Help me with X"','shape': 'note', 'novel': True},
                    {'label': 'General Q&A',     'shape': 'note', 'novel': True},
                ]},
                {'label': 'Behavior-driven help', 'novel': True,
                 'subtitle': 'tutor notices struggle & offers'},
                {'label': 'Voice command', 'novel': True,
                 'subtitle': 'imperative changes', 'children': [
                    {'label': '"Quantize at X%"', 'shape': 'note', 'novel': True},
                    {'label': '"Set tempo to X"','shape': 'note', 'novel': True},
                    {'label': '"Set key to X"',  'shape': 'note', 'novel': True},
                    {'label': '"Add reverb"',    'shape': 'note', 'novel': True},
                ]},
                {'label': 'Tutor first-song', 'novel': True,
                 'subtitle': 'guided walkthrough'},
                {'label': 'Echo-back', 'subtitle': 'onboarding · confirms profile'},
                {'label': 'Theatrical UI', 'subtitle': 'onboarding · UI builds in narrated phases'},
            ],
        },
        # ===================== WRIST + SESSION =====================
        {
            'label': 'WRIST + SESSION',
            'subtitle': 'global controls',
            'section': 'wrist',
            'children': [
                {'label': 'Play / Stop (backup)',
                 'subtitle': 'safety net when master strip is hidden / out of reach'},
                {'label': 'Inst Wall toggle'},
                {'label': 'FX Wall toggle'},
                {'label': 'Simpler', 'subtitle': 'collapse to essentials'},
                {'label': 'Explore', 'subtitle': 'expand to advanced'},
                {'label': 'Undo'},
                {'label': 'Redo'},
                {'label': 'Settings', 'children': [
                    {'label': 'Audio I/O'},
                    {'label': 'MIDI devices'},
                    {'label': 'Hand calibration'},
                    {'label': 'Account'},
                ]},
                {'label': 'Session', 'children': [
                    {'label': 'Save'},
                    {'label': 'Pause'},
                    {'label': 'Exit'},
                ]},
            ],
        },
    ],
}


class Command(BaseCommand):
    help = 'Seed the VR/AR DAW App Map flowchart for a user'

    def add_arguments(self, parser):
        parser.add_argument('--user', required=True,
                            help='Username to seed the chart for')
        parser.add_argument('--title', default='VR/AR DAW · App Map',
                            help='Flowchart title')

    def handle(self, *args, **options):
        try:
            user = User.objects.get(username=options['user'])
        except User.DoesNotExist:
            raise CommandError('User "%s" not found' % options['user'])

        chart = Flowchart.objects.create(
            user=user,
            title=options['title'],
            description=(
                'VR/AR DAW interaction map. Red nodes are novel-candidate '
                'interactions; each section is colored by app surface. Drag '
                'nodes to rearrange, scroll to zoom, shift-drag empty space '
                'to box-select.'
            ),
        )

        created = [0]

        def resolve_color(node_data, parent_section):
            section = node_data.get('section', parent_section)
            if node_data.get('novel'):
                return SECTION_COLORS['novel'], section
            return SECTION_COLORS.get(section, ''), section

        def create_subtree(node_data, parent, parent_section):
            color, section = resolve_color(node_data, parent_section)
            subtitle = node_data.get('subtitle', '')
            if node_data.get('novel'):
                novel_tag = '✦ novel-candidate'
                subtitle = '%s · %s' % (subtitle, novel_tag) if subtitle else novel_tag
            node = Node.objects.create(
                flowchart=chart,
                parent=parent,
                label=node_data['label'][:120],
                subtitle=subtitle[:160],
                shape=node_data.get('shape', 'process'),
                branch_label=node_data.get('branch_label', ''),
                color=color or '',
                sort_order=created[0],
            )
            created[0] += 1
            for child in node_data.get('children', []):
                create_subtree(child, node, section)

        create_subtree(TREE, None, 'root')
        auto_layout_flowchart(chart)

        self.stdout.write(self.style.SUCCESS(
            'Created flowchart "%s" (id=%d) with %d nodes for %s'
            % (chart.title, chart.id, created[0], options['user'])
        ))
