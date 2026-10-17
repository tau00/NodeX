# NodeX keys

Shortcuts apply while the board has focus; text fields keep their normal editing keys.
The lead is the last selected node, shown in green. In Maya: Help > Keys shows the same tables.

Sections: [Navigation](#navigation) - [Selection](#selection) - [Wiring](#wiring) - [Bulk connect](#bulk-connect) - [Values](#values) - [Nodes](#nodes) - [Frames](#frames) - [Clipboard and presets](#clipboard-and-presets) - [Arrange and display](#arrange-and-display)

## Navigation

| Shortcut | Action |
| --- | --- |
| MMB drag / Alt+LMB drag | Pan |
| Wheel / Alt+RMB drag on empty canvas | Zoom |
| F / A | Frame selected / frame all |
| Toolbar bookmark buttons | Bookmark the view, previous / next bookmark |

## Selection

| Shortcut | Action |
| --- | --- |
| LMB on a node | Select it; Shift adds or makes it the lead, Ctrl toggles |
| LMB drag on empty canvas | Marquee select; Shift adds |
| LMB on empty canvas | Clear selection, isolation and the selected wire |
| Find field + Enter | Select and frame the nodes matching the text |
| Esc | Cancel a gesture, else leave isolation, else clear selection |

## Wiring

| Shortcut | Action |
| --- | --- |
| Drag port to port | Connect |
| Drag off a connected input | Move the wire to another input, or drop it to cut |
| Release a new wire on empty canvas | Search a node to create and connect |
| Alt+LMB drag from a socket | Sweep inputs: one source to every input crossed |
| Alt+RMB drag, node to node | Lazy connect to a compatible free input |
| Alt+Shift+RMB drag, node to node | Choose output and input sockets |
| Shift+RMB / Ctrl+RMB drag | Knife: cut every wire crossed |
| Del / Backspace | Disconnect the selected wire, else delete selected nodes |
| Double-click a wire | Isolate its two nodes; click the canvas to leave |
| RMB wire > Inbetween | Insert a utility node into the connection |
| RMB on a port or attribute name | Select connected nodes; copy attribute name, node.attr or full DAG path |
| W | Node links: one wire per node pair |

## Bulk connect

| Shortcut | Action |
| --- | --- |
| Wire between two selected nodes | Repeats for every selected pair with similar names |
| Wire into a selected node | Same input of every selected node of that type |
| K / Shift+K | Link the lead to the others by attribute name / replace inputs |
| Alt+L / Alt+Shift+L | Same as K / Shift+K |
| Alt+I / Alt+O / Alt+T | Transfer inputs / outputs / all connections from the lead |
| Alt+S | Swap the inputs of two selected nodes |

## Values

| Shortcut | Action |
| --- | --- |
| LMB / RMB drag a number field | Slide; Shift fine, Ctrl snap |
| Click a number field | Type a value |
| Drag down over number fields, release | Select them; type a number for all of them |
| Drag down, then sideways | Slide several fields together |
| Drag over bool fields | Toggle them all |
| Ctrl+Wheel over a field | Step a number, next enum item, toggle a bool |
| Esc while sliding | Restore the values |

## Nodes

| Shortcut | Action |
| --- | --- |
| Tab | Create a node at the cursor |
| F2 / double-click a node name | Rename |
| Drag a node's right edge | Width; double-click it for auto width |
| 1 / 2 / 3 / 4 | Simple / connected / full / custom display |
| RMB a node > Show all attributes | Every attribute of that node |
| RMB node > Delete inbetween | Bypass the node and delete it |
| Double-click a double chevron | Show the unit conversion node |

## Frames

| Shortcut | Action |
| --- | --- |
| Ctrl+J | Frame the selected nodes; nothing selected: a frame at the cursor |
| Drag a frame's title / corner | Move it with its nodes / resize |
| Double-click the title / body | Rename / write a comment |
| RMB on a frame | Colour, fit to nodes, select nodes, delete |

## Clipboard and presets

| Shortcut | Action |
| --- | --- |
| Ctrl+C / Ctrl+V | Copy / paste nodes with their internal connections |
| Shift+D | Maya Duplicate with shapes and hierarchy |
| Presets > Save selection as preset | Store the selection as a reusable fragment |
| Tab > Presets | Insert a saved preset |

## Arrange and display

| Shortcut | Action |
| --- | --- |
| Toolbar Rearrange arrow / Graph > Arrange | Layered, flow, straighten, grid, row, column |
| Display buttons | All shapes / except shading networks / no shapes |
| Two selected nodes > RMB > Find connections between | Highlight every chain joining them |

## Details

Copy captures node values, dynamic attributes, display settings, widths and relative positions.
Paste creates fresh nodes and selects the new group. Only connections whose endpoints are both
selected survive. Hidden unit-conversion chains between those endpoints keep their factors;
unselected upstream networks, DAG parents and child transforms are excluded. All shapes directly
owned by a selected transform are included, even if hidden on the board, with their geometry.
The snapshot remains usable
after changing or deleting the source nodes and can be pasted into another tab or scene.

Shift+D uses Maya's native `duplicate -rr` behavior, retaining the original DAG parent and copying
the child hierarchy and shapes. It does not use or overwrite the graph clipboard.

Paste and duplicate undo in one step. Maya's native import for paste is wrapped by the lazy-loaded
`fragment_command.py` plug-in so undo actually removes the imported nodes and redo restores their
identities. Copy leaves scene selection and undo history intact. A paste that exceeds the tab's
node limit is refused as a whole; raise `Options > Node limit` to continue.

Alt+LMB from a socket collects compatible inputs along the stroke and previews the branches.
Release to connect all collected ports in one undo step, even when releasing over empty canvas.
Existing input connections are replaced as with normal port dragging. Starting from a connected
input reuses its source and preserves the original connection. Escape cancels the gesture,
including while Alt remains held. Alt+LMB from empty canvas retains pan.

Right-click a wire and choose `Inbetween > Utility nodes` to insert a node into that connection.
The utility list is filtered against both ends of the wire. Choose the compatible input and
output attributes in the next dialog, then press `Insert`. Cancelling creates nothing. Insertion
keeps other branches intact and undoes in one step; existing hidden conversion factors are retained.

Right-click a port or an attribute name and choose `Select connected nodes` to replace the
selection with every node wired to that attribute, its children and its array elements. A port
follows its side (inputs or outputs); a name uses the inputs when the attribute has any, else the
outputs. Hidden unit conversions are looked through; an expanded one is selected itself. Nodes not
on the board are added first; a locked graph, or one that would pass `Options > Node limit`, is
left unchanged. Maya's default nodes such as `time1` are skipped.

Right-click any node and choose `Delete inbetween` to reconnect its active sources to its
receivers and delete that node. This works for ordinary nodes as well as inserted utilities.
One input/output pair can feed multiple receivers. Multiple pairs are matched by exact attribute
names, channel names (`X/Y/Z`, `R/G/B`) and array indices, with compatible data types required.
Compound connections can be paired with their individual channels. A unique mapping is required;
ambiguous or incomplete pairs, locked destinations and referenced nodes disable the action
with an explanatory tooltip. Child transforms must be removed separately. Hidden conversion
helpers and their factors remain. The entire operation undoes in one step.

Undo and Redo restore or remove tracked graph nodes visually along with the Maya scene,
preserving their board positions, widths and display settings, even with Auto-add disabled.

Select two nodes, right-click either selected node or the canvas, and choose
`Find connections between`. It shows every directed chain joining the pair, in either
direction, and adds missing intermediate nodes to the board. Existing node positions and
the pair selection are preserved. Found nodes and wires are highlighted; unrelated branches
are dimmed. Hidden conversion nodes are folded as usual. Click the canvas or press Escape
to leave the highlight. Locked graphs and node limits are respected.

Alt+RMB starting on empty canvas retains zoom. Lazy connect does not overwrite occupied inputs;
use the socket chooser when replacement is intended. This is a subset adapted to Maya DG nodes,
not Blender's shader-specific texture setup or mix-node creation.

**Fields.** An enum field opens a Blender-style list under the field (above it when there is no
room): hover highlights, click or Enter picks, typing filters, Escape closes. Number fields slide
under LMB or RMB drag; a plain RMB click still opens the node menu. Every slide or sweep is one
undo step; Maya shows the live value while dragging.

**Node search.** Tab, wire inbetween and link-drag share one ranked index: name, camel initials
(`dm` = decomposeMatrix), rigger aliases (`add`, `blend`, `space`), socket fit and how often a type
was used. Arnold / Redshift shading nodes sink unless asked for by name.
- RMB wire > Inbetween > `Search...`, or one of the eight best matches. Click inserts with the shown
  sockets; Shift+click (Shift+Enter in the search) opens the socket chooser.
- Drag a new wire from a socket and release it on empty canvas: choose a node and socket
  (`type.socket` narrows, e.g. `mult.matrixIn`); it is created there and connected (one undo).

**Bulk connect** (Options > Bulk connect from selection, on by default). Drag one wire:
- between two selected nodes: the pair teaches a rename (`skin_spine1 -> drv_spine1` = `skin` to
  `drv`); every other selected node connects to its renamed partner if that is selected too. When no
  name fits, selected nodes of the two types are paired in selection order;
- into a selected node from an unselected one: the same input of every selected node of that type.

**Arrange** (arrow on the Rearrange button, Graph > Arrange, canvas RMB > Arrange). Two or more
selected nodes arrange only themselves: Layered fit to view, Layered one flow, Straighten links,
Grid by category, Align in a row, Align in a column.

**Display shapes.** All shapes: a transform brings its shapes; except shading networks: the same,
and graphing stops at shading networks; no shapes: shapes are replaced by their transforms. The
buttons also apply to the open tab.

**Frames.** Ctrl+J or canvas RMB > Add frame. A node belongs to a frame while its centre is inside:
drop nodes in, drag them out. Drag the title to move the frame with its nodes, the corner to
resize; double-click the title to rename, the body to write a comment (Ctrl+Enter or a click
elsewhere keeps it, Escape cancels). RMB on a frame: colour, fit to nodes, select nodes, delete
(nodes stay). Frames are saved with the tab.

**Presets.** Presets > Save selection as preset writes the copied fragment (nodes, values, internal
connections, shapes, layout) to `Documents/maya/nodex_presets/<name>.json`. Presets are listed in
the Presets menu and in the Tab window; Load preset from file takes any such file.

**Move to new group.** RMB a wire > Move to new group: a new tab with just its two nodes.
