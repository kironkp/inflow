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
    'root':     '#102026',  # ink — root node
    'channel':  '#2F6A3B',  # green — channel strip
    'master':   '#6B7A45',  # olive — master strip (mixer-family but distinct)
    'aux':      '#45596B',  # slate blue — aux / send buses
    'timeline': '#1F4A6B',  # deep ocean — Star Wars depth-axis timeline
    'clips':    '#7E3D5E',  # raspberry — audio + MIDI clips on the timeline
    'inst':     '#A26A0F',  # orange — instrument wall
    'fx':       '#4C2D8E',  # purple — effects wall
    'library':  '#3E6B5C',  # forest teal — samples / files / Splice
    'equipment': '#5C5C70', # steel — speakers / equipment wall (physical hardware)
    'active':   '#2D4F78',  # blue — active instrument
    'tutor':    '#5E4577',  # lavender — AI tutor
    'wrist':    '#7A5A00',  # tan — wrist + session
    'novel':    '#B85450',  # red — novel-candidate (overrides section)
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
                    {'label': 'Global Swing', 'subtitle': 'project-wide groove — next to BPM',
                     'children': [
                        {'label': 'Swing amount slider'},
                        {'label': 'Swing template', 'subtitle': 'hip-hop · jazz · triplet'},
                        {'label': 'Preview (audible)', 'subtitle': 'scrub-to-hear changes'},
                    ]},
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
        # ===================== TIMELINE =====================
        {
            'label': 'TIMELINE',
            'subtitle': 'Star Wars depth axis · clips travel toward you, Guitar Hero style',
            'section': 'timeline',
            'children': [
                {'label': 'Playhead', 'subtitle': 'where time "is" right now', 'children': [
                    {'label': 'Tap to move'},
                    {'label': 'Scrub by hand', 'novel': True,
                     'subtitle': 'grab the playhead like a phonograph needle'},
                    {'label': 'Snap to bar / beat / zero-crossing'},
                    {'label': 'Loop region', 'novel': True,
                     'subtitle': 'drag-paint a range of time to loop'},
                ]},
                {'label': 'Zoom timeline', 'subtitle': 'no walking required', 'children': [
                    {'label': 'Pinch in / out (mid-air)', 'novel': True,
                     'subtitle': 'two-hand pinch to scale time'},
                    {'label': 'Zoom presets', 'subtitle': '1 bar · 4 bar · full song'},
                    {'label': 'Reset zoom'},
                ]},
                {'label': 'Track lanes', 'subtitle': 'one lane per channel', 'children': [
                    {'label': 'Tap empty lane → create clip at playhead'},
                    {'label': 'Reorder lanes (drag vertically)'},
                    {'label': 'Lane height (drag divider)'},
                    {'label': 'Lane mute / solo (mirrors strip)'},
                ]},
                {'label': 'Markers', 'subtitle': 'jump points in the arrangement', 'children': [
                    {'label': 'Drop marker (tap)'},
                    {'label': 'Tap marker → jump'},
                    {'label': 'Rename'},
                    {'label': 'Color'},
                ]},
                {'label': 'Automation plane', 'novel': True,
                 'subtitle': 'z-axis wave rising from clip — volume / velocity / pan over time',
                 'children': [
                    {'label': 'Pull edge up / down', 'novel': True,
                     'subtitle': 'shapes the plane like a sheet'},
                    {'label': 'Tap to add anchor point'},
                    {'label': 'Choose target', 'subtitle': 'volume · pan · send · any parameter'},
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
        # ===================== CLIPS =====================
        {
            'label': 'CLIPS',
            'subtitle': 'audio + MIDI segments traveling toward you on the timeline',
            'section': 'clips',
            'children': [
                {'label': 'Tap clip → open editor', 'novel': True,
                 'subtitle': 'expands into MIDI editor or audio editor'},
                {'label': 'Drag clip', 'novel': True, 'children': [
                    {'label': 'Horizontal — move in time', 'novel': True},
                    {'label': 'Vertical — switch lane', 'novel': True},
                    {'label': 'Snap to grid', 'subtitle': 'on / off toggle'},
                ]},
                {'label': 'Trim', 'novel': True, 'children': [
                    {'label': 'Drag clip edge', 'novel': True},
                    {'label': 'Snap to zero-crossing (audio)'},
                ]},
                {'label': 'Fade', 'novel': True, 'children': [
                    {'label': 'Drag corner → fade in', 'novel': True},
                    {'label': 'Drag corner → fade out', 'novel': True},
                    {'label': 'Fade shape', 'subtitle': 'linear · exp · log'},
                ]},
                {'label': 'Splice', 'subtitle': 'cut a clip in two', 'children': [
                    {'label': 'Scissors gesture at playhead', 'novel': True,
                     'subtitle': 'cut-motion with hand'},
                    {'label': 'Tap at playhead → split'},
                    {'label': 'Re-glue (undo split)'},
                ]},
                {'label': 'Loop', 'children': [
                    {'label': 'Drag right edge past clip end → loop'},
                    {'label': 'Loop count'},
                ]},
                {'label': 'Time-stretch', 'novel': True,
                 'subtitle': 'grab handles + pull to stretch in time',
                 'children': [
                    {'label': 'Drag stretch handles', 'novel': True},
                    {'label': 'Preserve pitch (toggle)'},
                ]},
                {'label': 'Reverse', 'subtitle': 'audio only'},
                {'label': 'Volume automation plane', 'novel': True,
                 'subtitle': 'rising plane on top of clip = volume over time',
                 'children': [
                    {'label': 'Pull plane edge up / down', 'novel': True},
                    {'label': 'Reset to flat'},
                ]},
                {'label': 'Long-press → context menu', 'children': [
                    {'label': 'Duplicate'},
                    {'label': 'Delete'},
                    {'label': 'Rename'},
                    {'label': 'Color'},
                    {'label': 'Bounce to audio', 'subtitle': 'MIDI clip → render to audio file'},
                    {'label': 'Properties', 'subtitle': 'gain · offset · tempo'},
                ]},
                # ----- MIDI EDITOR sub-tree -----
                {
                    'label': 'MIDI EDITOR',
                    'subtitle': 'Guitar Hero for piano · opens when you tap a MIDI clip',
                    'children': [
                        {'label': 'Virtual keyboard (floor level)', 'novel': True,
                         'subtitle': 'real piano you stand at / hover hands over', 'children': [
                            {'label': 'Keys light up as notes hit', 'novel': True,
                             'subtitle': 'feedback during playback'},
                            {'label': 'Mirror to external MIDI controller'},
                        ]},
                        {'label': 'Note grid (above keyboard)', 'subtitle': 'time flows toward the keys'},
                        {'label': 'Place note (tap on grid)'},
                        {'label': 'Tap note → select'},
                        {'label': 'Drag note', 'children': [
                            {'label': 'Horizontal → time'},
                            {'label': 'Vertical → pitch'},
                            {'label': 'Drag end → length'},
                        ]},
                        {'label': 'Velocity via Z-axis', 'novel': True,
                         'subtitle': 'pull note toward you → louder · push away → quieter',
                         'children': [
                            {'label': 'Velocity plane rising over notes', 'novel': True,
                             'subtitle': 'wave/plane height = velocity, like volume automation'},
                            {'label': 'Velocity paint', 'novel': True,
                             'subtitle': 'sweep hand at depth across a run of notes'},
                        ]},
                        {'label': 'Scale lock (side button)', 'novel': True,
                         'subtitle': 'always-visible button on MIDI editor wall',
                         'children': [
                            {'label': 'Choose scale', 'subtitle': 'major / minor / blues / custom'},
                            {'label': 'Notes snap to scale on placement'},
                        ]},
                        {'label': 'Quantize (side button)', 'children': [
                            {'label': 'Physical knob → amount %', 'novel': True,
                             'subtitle': 'sliding scale, not just on/off'},
                            {'label': 'Snap value', 'subtitle': '1/4 · 1/8 · 1/16 · 1/32'},
                            {'label': 'AI suggests quantize', 'novel': True,
                             'subtitle': 'tutor offers when notes are off-grid'},
                            {'label': 'Apply / preview audible'},
                        ]},
                        {'label': 'Swing (per-clip)', 'subtitle': 'less central — global swing is on master',
                         'children': [
                            {'label': 'Amount slider'},
                            {'label': 'Bypass'},
                        ]},
                        {'label': 'Humanize', 'children': [
                            {'label': 'Timing jitter'},
                            {'label': 'Velocity variance'},
                        ]},
                        {'label': 'Multi-select', 'children': [
                            {'label': 'Box-select in air', 'novel': True},
                            {'label': 'Move group'},
                        ]},
                        {'label': 'Octave shift (entire clip)'},
                        {'label': 'Mute / Solo note'},
                        {'label': 'Exit / collapse to clip'},
                    ],
                },
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
        # ===================== LIBRARY (samples + files) =====================
        {
            'label': 'LIBRARY',
            'subtitle': '4th wall · summoned · wrist button · samples + sounds + files',
            'section': 'library',
            'children': [
                {'label': 'Tap tile → preview', 'subtitle': 'audition the sample'},
                {'label': 'Long-press tile', 'children': [
                    {'label': 'Favorite / Unfav'},
                    {'label': 'Info / metadata', 'subtitle': 'tempo · key · length'},
                    {'label': 'Reveal in source folder'},
                ]},
                {'label': 'Drag tile', 'novel': True, 'children': [
                    {'label': 'Drag to timeline', 'novel': True,
                     'subtitle': 'creates audio clip on nearest track'},
                    {'label': 'Drag to instrument', 'novel': True,
                     'subtitle': 'loads as sampler / replaces active instrument'},
                    {'label': 'Drag to channel strip', 'novel': True,
                     'subtitle': 'spins up new audio track with the sample'},
                    {'label': 'Cancel (drop in air)'},
                ]},
                {'label': 'Tap category btn', 'subtitle': 'filter the wall', 'children': [
                    {'label': 'My Files', 'subtitle': 'local / device'},
                    {'label': 'Drums'},
                    {'label': 'Loops'},
                    {'label': 'One-shots'},
                    {'label': 'Vocals'},
                    {'label': 'FX / impacts'},
                    {'label': 'Splice', 'novel': True,
                     'subtitle': '3rd-party cloud — placeholder for now'},
                    {'label': 'Favs only'},
                ]},
                {'label': 'Search'},
                {'label': 'Import from device', 'children': [
                    {'label': 'File picker'},
                    {'label': 'Drag-and-drop from desktop (passthrough)'},
                ]},
                {'label': 'Tap Dismiss'},
            ],
        },
        # ===================== EQUIPMENT WALL =====================
        {
            'label': 'EQUIPMENT WALL',
            'subtitle': '5th wall · speakers as physical objects · plug into master output',
            'section': 'equipment',
            'children': [
                {'label': 'Tap speaker tile', 'novel': True,
                 'subtitle': 'opens wall of speakers'},
                {'label': 'Speaker options', 'subtitle': 'consumer playback contexts as physical rigs',
                 'children': [
                    {'label': '60s tube cabinet', 'novel': True,
                     'subtitle': 'vintage warmth'},
                    {'label': 'Record-player horn rig', 'novel': True,
                     'subtitle': 'horn + base + needle · full emulator',
                     'children': [
                        {'label': 'Vintage horn'},
                        {'label': 'Record-player base'},
                        {'label': 'Needle'},
                        {'label': 'Optional noise profile (crackle · wow · flutter)', 'novel': True},
                    ]},
                    {'label': 'Phone-tier bass speaker', 'novel': True,
                     'subtitle': 'translation check · sounds bad on purpose'},
                    {'label': 'Laptop speakers', 'novel': True},
                    {'label': 'Car system mockup', 'novel': True,
                     'subtitle': 'subwoofer-heavy translation check'},
                    {'label': 'Studio monitors', 'novel': True,
                     'subtitle': 'flat reference'},
                ]},
                {'label': 'Plug speaker → master out', 'novel': True,
                 'subtitle': 'replaces default master output · ghost-wire connection'},
                {'label': 'Hot-swap mid-playback', 'novel': True,
                 'subtitle': 'yank + plug another · instant A/B'},
                {'label': 'Long-press tile', 'children': [
                    {'label': 'Favorite / Unfav'},
                    {'label': 'Info / specs'},
                    {'label': 'Audition'},
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
            'subtitle': 'robot mind · ghost-person body · never composes · silent ghost prompts',
            'section': 'tutor',
            'children': [
                # ----- Delivery model -----
                {'label': 'Tutor delivery model',
                 'subtitle': 'how the tutor shows up — never spoken unprompted',
                 'children': [
                    {'label': 'Robot presence',
                     'subtitle': 'the mind · speaks only when addressed'},
                    {'label': 'Ghost-person demonstrations', 'novel': True,
                     'subtitle': 'translucent figure mirrors gestures user should make',
                     'children': [
                        {'label': 'Stands next to user'},
                        {'label': 'Avoids uncanny humanoid robot moves'},
                    ]},
                    {'label': 'Spatial pointing', 'novel': True,
                     'subtitle': 'gestures at controls in 3D'},
                    {'label': 'Ghost-prompt (canonical UI pattern)', 'novel': True,
                     'subtitle': 'translucent prompt anchored to relevant object',
                     'children': [
                        {'label': '1-line description'},
                        {'label': '0-2 inline mini-buttons'},
                        {'label': 'Optional pre-armed knob inside prompt', 'novel': True},
                        {'label': 'Palm-flick to dismiss', 'novel': True},
                        {'label': 'Reused for ALL silent suggestions'},
                    ]},
                    {'label': 'Never speaks unprompted',
                     'subtitle': 'voice only when user addresses tutor'},
                ]},
                # ----- Translator -----
                {'label': 'Translator',
                 'subtitle': 'ideas → DAW · the translation gap',
                 'children': [
                    {'label': 'Hum → MIDI', 'novel': True,
                     'subtitle': 'sing/hum a melody · maps to scale · places notes'},
                    {'label': 'Tap-the-table drum mapping', 'novel': True,
                     'subtitle': 'tap surfaces → drum sounds', 'children': [
                        {'label': 'Surface detection (table / lap / wrist)', 'novel': True},
                        {'label': 'Drum-kit overlay on surface', 'novel': True,
                         'subtitle': 'faint zones: kick center · snare right · hat left'},
                        {'label': 'Mapping calibration (ghost-person demo)', 'novel': True},
                        {'label': 'Velocity from tap force', 'novel': True,
                         'subtitle': 'mic + accelerometer + IMU'},
                        {'label': 'Wrist-tap fallback', 'novel': True,
                         'subtitle': 'reduced kit when no surface available'},
                        {'label': 'Remap panel', 'subtitle': 'drag samples onto zones'},
                        {'label': 'Big red record button', 'novel': True,
                         'subtitle': 'captures performance as MIDI'},
                    ]},
                    {'label': '5-chord hover with record', 'novel': True,
                     'subtitle': 'non-pianist chord exploration', 'children': [
                        {'label': '5 chord cards float in front', 'novel': True},
                        {'label': 'Hover hand → live MIDI to existing instrument', 'novel': True,
                         'subtitle': 'no new audio generated'},
                        {'label': 'Crossfade between chords', 'novel': True},
                        {'label': 'Cards drawn from user\'s prior projects'},
                        {'label': 'Big red record button captures combo', 'novel': True},
                    ]},
                    {'label': 'Bar-by-bar bridge maker', 'novel': True,
                     'subtitle': 'hand-wave assembles bridge from existing material',
                     'children': [
                        {'label': 'N-bar loop as strip of cells', 'novel': True},
                        {'label': 'Hand-wave moves quantized playhead', 'novel': True,
                         'subtitle': 'snaps to bar under hand'},
                        {'label': 'Per-bar chord substitution', 'novel': True,
                         'subtitle': '5-chord hover available per bar'},
                        {'label': 'Record button captures combo', 'novel': True},
                    ]},
                    {'label': 'Learn-your-favorite-song', 'novel': True,
                     'subtitle': 'Spotify / Apple import · teaches the parts',
                     'children': [
                        {'label': 'Import from Spotify'},
                        {'label': 'Import from Apple Music'},
                        {'label': 'Import local audio file'},
                        {'label': 'Stem parser', 'novel': True},
                        {'label': 'Teach drum pattern', 'novel': True},
                        {'label': 'Teach bass line', 'novel': True},
                        {'label': 'Teach chord progression', 'novel': True},
                        {'label': 'Track-by-track walkthrough mode'},
                    ]},
                    {'label': 'Tempo / sound-swap walkthrough', 'novel': True,
                     'subtitle': 'teaches steps · tutor never auto-transforms',
                     'children': [
                        {'label': 'User asks "what if at 90 bpm?"'},
                        {'label': 'Tutor walks: adjust tempo'},
                        {'label': 'Tutor walks: swap bass patch'},
                        {'label': 'Tutor walks: adjust groove'},
                        {'label': 'User performs each step'},
                    ]},
                ]},
                # ----- Co-pilot -----
                {'label': 'Co-pilot',
                 'subtitle': 'silent help while you work',
                 'children': [
                    {'label': 'Personalized track suggestions', 'novel': True,
                     'subtitle': '3 choices · from YOUR past projects only · never AI-guessed'},
                    {'label': 'Behavioral autopilot', 'novel': True,
                     'subtitle': 'watches repeated actions · offers to automate',
                     'children': [
                        {'label': 'Detects pattern (e.g. kick → bass sidechain)'},
                        {'label': 'Surfaces ghost prompt with offer'},
                        {'label': 'User accepts / dismisses'},
                    ]},
                    {'label': 'Ghost-prompt examples', 'subtitle': 'all use the canonical pattern', 'children': [
                        {'label': 'Sidechain bass to kick', 'novel': True,
                         'subtitle': 'two buttons + pre-armed amount knob'},
                        {'label': 'EQ this vocal', 'novel': True},
                        {'label': 'Compress this kick', 'novel': True},
                        {'label': 'Swap snare for one you usually use', 'novel': True},
                        {'label': 'Humanize this clip', 'novel': True},
                        {'label': 'Match key with current project', 'novel': True},
                    ]},
                    {'label': 'Snooze nudges (palm-flick)', 'novel': True},
                ]},
                # ----- Coach -----
                {'label': 'Coach',
                 'subtitle': 'mixing + finishing',
                 'children': [
                    {'label': 'Why does this sound amateur?', 'novel': True,
                     'subtitle': 'audio analysis · ghost prompts for each deficit',
                     'children': [
                        {'label': 'Crowded midrange (with one-tap fix)'},
                        {'label': 'No stereo width (with one-tap fix)'},
                        {'label': 'Dry lead vocal (with one-tap fix)'},
                        {'label': 'Bass-kick masking (with one-tap fix)'},
                    ]},
                    {'label': 'Reference-matched mixing', 'novel': True,
                     'subtitle': 'teaches steps · never applies silently'},
                    {'label': 'Mixing tutorial mode'},
                    {'label': 'Polish detection', 'novel': True,
                     'subtitle': 'time-on-element > 30 min · ghost prompt for fresh ears'},
                    {'label': 'Ship-it preview', 'novel': True,
                     'subtitle': 'rendered mastered preview · breaks perfectionism loop'},
                    {'label': 'Anti-perfection framing',
                     'subtitle': 'real outcome statistics · not pep talk'},
                ]},
                # ----- Companion -----
                {'label': 'Companion',
                 'subtitle': 'encouragement · energy · growth',
                 'children': [
                    {'label': 'Affirmation button (sparkly heart)', 'novel': True,
                     'subtitle': 'real progress milestones from YOUR data',
                     'children': [
                        {'label': 'Tap → show user\'s own milestones', 'novel': True},
                        {'label': 'Tracks finished · mixes improved · etc.'},
                        {'label': 'Real data — never generic encouragement'},
                    ]},
                    {'label': 'Fatigue / posture awareness', 'novel': True,
                     'subtitle': 'detects heads-down · suggests stretch breaks',
                     'children': [
                        {'label': 'Headset telemetry'},
                        {'label': 'Controller pressure pattern'},
                        {'label': 'Threshold ~90 min default'},
                    ]},
                    {'label': 'No social signals',
                     'subtitle': 'no leaderboards · no follower counts · no public play counts'},
                ]},
                # ----- Templates & Lessons -----
                {'label': 'Templates & Lessons',
                 'subtitle': 'starting points and learning',
                 'children': [
                    {'label': 'Lesson button', 'novel': True,
                     'subtitle': 'tap anywhere · shy-mode friendly',
                     'children': [
                        {'label': 'Tutor decides what to teach', 'novel': True,
                         'subtitle': 'based on current context'},
                        {'label': 'User asks what to learn'},
                        {'label': 'Short hands-on lesson (not slide deck)'},
                        {'label': 'Uses ghost-person demonstration'},
                    ]},
                    {'label': 'Lesson catalog', 'subtitle': 'browse by topic'},
                    {'label': 'Genre-relationship templates', 'novel': True,
                     'subtitle': 'human-curated · how the parts interact',
                     'children': [
                        {'label': 'Lo-fi: kick · bass · Rhodes · tape hiss'},
                        {'label': 'Drum & bass: breaks · sub-bass · reese'},
                        {'label': 'Trap: 808 · hats · snare · vox chops'},
                        {'label': 'House: 4-on-floor · pluck · groove'},
                        {'label': '(more genres — curated)'},
                    ]},
                    {'label': 'Lucky template', 'novel': True,
                     'subtitle': 'template in YOUR style · not generation'},
                    {'label': 'Daily prompt', 'novel': True,
                     'subtitle': 'opt-in constraint of the day · defeats blank page'},
                ]},
                # ----- Onboarding mode -----
                {'label': 'Onboarding mode',
                 'subtitle': 'first-run experience only',
                 'children': [
                    {'label': 'Conversational onboarding'},
                    {'label': 'Echo-back', 'subtitle': 'tutor confirms your profile'},
                    {'label': 'Theatrical UI build', 'novel': True,
                     'subtitle': 'workspace materializes in narrated phases'},
                    {'label': 'Tutor first-song', 'novel': True,
                     'subtitle': 'guided walkthrough · first musical performance'},
                ]},
                # ----- Sensitivity -----
                {'label': 'Nudge sensitivity 1-10', 'novel': True,
                 'subtitle': 'user controls AI frequency · settings slider',
                 'children': [
                    {'label': '1 = only critical (polish · fatigue)'},
                    {'label': '5 = default (balanced)'},
                    {'label': '10 = chatty (all suggestions on)'},
                    {'label': 'Off entirely (no AI nudges at all)'},
                ]},
            ],
        },
        # ===================== WRIST + SESSION =====================
        {
            'label': 'WRIST + SESSION',
            'subtitle': 'global controls · always accessible',
            'section': 'wrist',
            'children': [
                {'label': 'Play / Stop (backup)',
                 'subtitle': 'safety net when master strip is hidden / out of reach'},
                {'label': 'Inst Wall toggle'},
                {'label': 'FX Wall toggle'},
                {'label': 'Library Wall toggle', 'subtitle': 'samples + files (4th wall)'},
                {'label': 'Equipment Wall toggle', 'novel': True,
                 'subtitle': 'speakers / hardware (5th wall)'},
                {'label': 'Splice quick-open', 'novel': True,
                 'subtitle': 'jumps straight to Splice tab in the library'},
                {'label': 'Lesson button', 'novel': True,
                 'subtitle': 'tap to start a contextual lesson · shy-mode friendly'},
                {'label': 'Affirmation button (sparkly heart)', 'novel': True,
                 'subtitle': 'tap → real progress milestones from YOUR data'},
                {'label': 'Bounce — "save" a version', 'novel': True,
                 'subtitle': 'no traditional save · everything is auto-saved · this BOUNCES',
                 'children': [
                    {'label': 'Tap → bounce V1, V2, V3 (next available)', 'novel': True},
                    {'label': 'Custom name (long-press)'},
                    {'label': 'Bounce settings', 'subtitle': 'format · quality · range'},
                ]},
                {'label': 'Bounces — scrollable list', 'novel': True,
                 'subtitle': 'past versions live on the wrist',
                 'children': [
                    {'label': 'Tap bounce → play', 'novel': True},
                    {'label': 'A/B against current', 'novel': True},
                    {'label': 'Long-press → rename / delete / export'},
                    {'label': 'Export to standard format', 'subtitle': 'wav · mp3 · stems'},
                ]},
                {'label': 'Simpler', 'subtitle': 'collapse to essentials'},
                {'label': 'Explore', 'subtitle': 'expand to advanced'},
                {'label': 'Undo'},
                {'label': 'Redo'},
                {'label': 'Settings', 'children': [
                    {'label': 'Audio I/O'},
                    {'label': 'MIDI devices'},
                    {'label': 'Hand calibration'},
                    {'label': 'Nudge sensitivity 1-10', 'novel': True,
                     'subtitle': 'how often AI nudges fire'},
                    {'label': 'Account'},
                ]},
                {'label': 'Session', 'children': [
                    {'label': 'Auto-save indicator',
                     'subtitle': 'everything saved continuously · no manual save'},
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
