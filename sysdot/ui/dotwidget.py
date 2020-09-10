
import os
import subprocess
import sys
import time
import math
from enum import Enum

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Gdk

from ..dot.lexer import ParseError
from ..dot.parser import XDotParser
from . import animation
from . import actions

from .elements import Graph
from .elements import Node

from ..conflicts import mapper
from ..conflicts import dotCreater 

class ConflictMode(Enum):
    CONFLICT_MODE_OFF = 1
    CONFLICT_SELECTION = 2
    CONFLICT_MODE_ON = 3

class DotWidget(Gtk.DrawingArea):
    """GTK widget that draws dot graphs."""

    __gsignals__ = {
        # 'clicked': (GObject.SIGNAL_RUN_LAST, None, (str, object)), 
        'error': (GObject.SIGNAL_RUN_LAST, None, (str,)),
        'history': (GObject.SIGNAL_RUN_LAST, None, (bool, bool)),
        'node-highlighted': (GObject.SIGNAL_RUN_LAST, None, (int,)),
        'conflict-button-pressed': (GObject.SIGNAL_RUN_FIRST, None, ())
    }

    filter = 'dot'

    def set_conflict_graph(self, conflictGraph):
        self.conflict_nodes = conflictGraph
        self.graph.set_conflicting_nodes(conflictGraph)

        # Initialize the sidebar as well.
        self.sidebar.set_nodes_and_edges(self.graph)

    def __init__(self):
        Gtk.DrawingArea.__init__(self)

        self.sidebar = None
        self.set_hexpand(True)
        self.graph = Graph()
        self.graph.hideConflictNodes = True
        self.openfilename = None
        self.set_can_focus(True)
        ## conflict_nodes is {int: list(int)}; id to list of ids
        self.conflict_nodes = {}
        self.conflictMode = ConflictMode.CONFLICT_MODE_OFF

        self.connect("draw", self.on_draw)
        self.connect("node-highlighted", self.on_node_highlighted)
        self.connect("conflict-button-pressed", self.on_conflict_button_pressed)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                        Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.connect("button-press-event", self.on_area_button_press)
        self.connect("button-release-event", self.on_area_button_release)
        self.add_events(Gdk.EventMask.POINTER_MOTION_MASK |
                        Gdk.EventMask.POINTER_MOTION_HINT_MASK |
                        Gdk.EventMask.BUTTON_RELEASE_MASK |
                        Gdk.EventMask.SCROLL_MASK)
        self.connect("motion-notify-event", self.on_area_motion_notify)
        self.connect("scroll-event", self.on_area_scroll_event)
        self.connect("size-allocate", self.on_area_size_allocate)

        self.connect('key-press-event', self.on_key_press_event)
        self.last_mtime = None

        GLib.timeout_add(1000, self.update)

        self.x, self.y = 0.0, 0.0
        self.zoom_ratio = 1.0
        self.zoom_to_fit_on_resize = False
        self.animation = animation.NoAnimation(self)
        self.drag_action = actions.NullAction(self)
        self.presstime = None
        self.highlight = None
        self.highlight_search = False
        self.history_back = []
        self.history_forward = []

    def error_dialog(self, message):
        self.emit('error', message)

    def set_filter(self, filter):
        self.filter = filter

    def on_conflict_button_pressed(self, event):
        """
        Returns the button text, and
        """
        pass

    def turnOffConflictMode(self):
        self.conflictMode = ConflictMode.CONFLICT_MODE_OFF
        self.graph = self.original_graph
        self.graph.selectedNodes = set()
        self.graph.hideConflictNodes = True

        ## reset sidebar as well
        # self.sidebar.set_nodes_and_edges(self.graph)

    def turnOnConflictMode(self):
        self.conflictMode = ConflictMode.CONFLICT_SELECTION
        self.graph.hideConflictNodes = False
    
    def run_filter(self, dotcode):
        if not self.filter:
            return dotcode
        try:
            p = subprocess.Popen(
                [self.filter, '-Txdot'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                universal_newlines=False
            )
        except OSError as exc:
            error = '%s: %s' % (self.filter, exc.strerror)
            p = subprocess.CalledProcessError(exc.errno, self.filter, exc.strerror)
        else:
            xdotcode, error = p.communicate(dotcode)
            error = error.decode()
        error = error.rstrip()
        if error:
            sys.stderr.write(error + '\n')
        if p.returncode != 0:
            self.error_dialog(error)
            return None
        return xdotcode

    def _set_dotcode(self, dotcode, center=True):
        # By default DOT language is UTF-8, but it accepts other encodings
        assert isinstance(dotcode, bytes)
        xdotcode = self.run_filter(dotcode)
        if xdotcode is None:
            return False
        try:
            self.set_xdotcode(xdotcode, center=center)
        except ParseError as ex:
            self.error_dialog(str(ex))
            return False
        else:
            return True

    def set_dotcode(self, dotcode, filename=None, center=True):
        self.openfilename = None
        if self._set_dotcode(dotcode, center=center):
            if filename is None:
                self.last_mtime = None
            else:
                self.last_mtime = os.stat(filename).st_mtime
            self.openfilename = filename
            return True

    def create_new_graph(self):
        dotCreater.bfs(self.graph)
        selectiveDotcode = dotCreater.truncatedGraphList(self.graph, self.graph.selectedNodes)
        self.graph = self.parse_graph_from_dotcode(selectiveDotcode)
        self.graph.set_conflicting_nodes(self.conflict_nodes)
        self.zoom_image(self.zoom_ratio, center=True)

        ## also set sidebar things ?
        # self.sidebar.set_nodes_and_edges(self.graph)


    def parse_graph_from_dotcode(self, dotcode: bytes):
        xdotcode = self.run_filter(dotcode)
        parser = XDotParser(xdotcode)
        return parser.parse()
        
    def set_xdotcode(self, xdotcode, center=True):
        assert isinstance(xdotcode, bytes)
        parser = XDotParser(xdotcode)
        self.graph = parser.parse()
        self.graph.set_conflicting_nodes(self.conflict_nodes)
        self.original_graph = self.graph
        self.zoom_image(self.zoom_ratio, center=center)

    def reload(self):
        if self.openfilename is not None:
            try:
                fp = open(self.openfilename, 'rb')
                self._set_dotcode(fp.read(), False)
                fp.close()
            except IOError:
                pass
            else:
                del self.history_back[:], self.history_forward[:]

    def update(self):
        if self.openfilename is not None:
            current_mtime = os.stat(self.openfilename).st_mtime
            if current_mtime != self.last_mtime:
                self.last_mtime = current_mtime
                self.reload()
        return True

    def _draw_graph(self, cr, rect):
        w, h = float(rect.width), float(rect.height)
        cx, cy = 0.5 * w, 0.5 * h
        x, y, ratio = self.x, self.y, self.zoom_ratio
        x0, y0 = x - cx / ratio, y - cy / ratio
        x1, y1 = x0 + w / ratio, y0 + h / ratio
        bounding = (x0, y0, x1, y1)

        cr.translate(cx, cy)
        cr.scale(ratio, ratio)
        cr.translate(-x, -y)
        self.graph.draw(cr, highlight_items=self.highlight, bounding=bounding)

    def on_draw(self, widget, cr):
        rect = self.get_allocation()
        Gtk.render_background(self.get_style_context(), cr, 0, 0,
                              rect.width, rect.height)

        cr.save()
        self._draw_graph(cr, rect)
        cr.restore()

        self.drag_action.draw(cr)

        return False

    def get_current_pos(self):
        return self.x, self.y

    def set_current_pos(self, x, y):
        self.x = x
        self.y = y
        self.queue_draw()

    def set_highlight(self, items, search=False):
        # Enable or disable search highlight
        if search:
            self.highlight_search = items is not None
        # Ignore cursor highlight while searching
        if self.highlight_search and not search:
            return
        if self.highlight != items:
            self.highlight = items
            self.queue_draw()

    def zoom_image(self, zoom_ratio, center=False, pos=None):
        # Constrain zoom ratio to a sane range to prevent numeric instability.
        zoom_ratio = min(zoom_ratio, 1E4)
        zoom_ratio = max(zoom_ratio, 1E-6)

        if center:
            self.x = self.graph.width/2
            self.y = self.graph.height/2
        elif pos is not None:
            rect = self.get_allocation()
            x, y = pos
            x -= 0.5*rect.width
            y -= 0.5*rect.height
            self.x += x / self.zoom_ratio - x / zoom_ratio
            self.y += y / self.zoom_ratio - y / zoom_ratio
        self.zoom_ratio = zoom_ratio
        self.zoom_to_fit_on_resize = False
        self.queue_draw()

    def zoom_to_area(self, x1, y1, x2, y2):
        rect = self.get_allocation()
        width = abs(x1 - x2)
        height = abs(y1 - y2)
        if width == 0 and height == 0:
            self.zoom_ratio *= self.ZOOM_INCREMENT
        else:
            self.zoom_ratio = min(
                float(rect.width)/float(width),
                float(rect.height)/float(height)
            )
        self.zoom_to_fit_on_resize = False
        self.x = (x1 + x2) / 2
        self.y = (y1 + y2) / 2
        self.queue_draw()

    def zoom_to_fit(self):
        rect = self.get_allocation()
        rect.x += self.ZOOM_TO_FIT_MARGIN
        rect.y += self.ZOOM_TO_FIT_MARGIN
        rect.width -= 2 * self.ZOOM_TO_FIT_MARGIN
        rect.height -= 2 * self.ZOOM_TO_FIT_MARGIN
        zoom_ratio = min(
            float(rect.width)/float(self.graph.width),
            float(rect.height)/float(self.graph.height)
        )
        self.zoom_image(zoom_ratio, center=True)
        self.zoom_to_fit_on_resize = True

    ZOOM_INCREMENT = 1.25
    ZOOM_TO_FIT_MARGIN = 12

    def on_zoom_in(self, action):
        self.zoom_image(self.zoom_ratio * self.ZOOM_INCREMENT)

    def on_zoom_out(self, action):
        self.zoom_image(self.zoom_ratio / self.ZOOM_INCREMENT)

    def on_zoom_fit(self, action):
        self.zoom_to_fit()

    def on_zoom_100(self, action):
        self.zoom_image(1.0)

    POS_INCREMENT = 100

    def on_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Left:
            self.x -= self.POS_INCREMENT/self.zoom_ratio
            self.queue_draw()
            return True
        if event.keyval == Gdk.KEY_Right:
            self.x += self.POS_INCREMENT/self.zoom_ratio
            self.queue_draw()
            return True
        if event.keyval == Gdk.KEY_Up:
            self.y -= self.POS_INCREMENT/self.zoom_ratio
            self.queue_draw()
            return True
        if event.keyval == Gdk.KEY_Down:
            self.y += self.POS_INCREMENT/self.zoom_ratio
            self.queue_draw()
            return True
        if event.keyval in (Gdk.KEY_Page_Up,
                            Gdk.KEY_plus,
                            Gdk.KEY_equal,
                            Gdk.KEY_KP_Add):
            self.zoom_image(self.zoom_ratio * self.ZOOM_INCREMENT)
            self.queue_draw()
            return True
        if event.keyval in (Gdk.KEY_Page_Down,
                            Gdk.KEY_minus,
                            Gdk.KEY_KP_Subtract):
            self.zoom_image(self.zoom_ratio / self.ZOOM_INCREMENT)
            self.queue_draw()
            return True
        if event.keyval == Gdk.KEY_Escape:
            self.drag_action.abort()
            self.drag_action = actions.NullAction(self)
            return True
        if event.keyval == Gdk.KEY_r:
            self.reload()
            return True
        if event.keyval == Gdk.KEY_f:
            win = widget.get_toplevel()
            find_toolitem = win.uimanager.get_widget('/ToolBar/Find')
            textentry = find_toolitem.get_children()
            win.set_focus(textentry[0])
            return True
        if event.keyval == Gdk.KEY_q:
            Gtk.main_quit()
            return True
        if event.keyval == Gdk.KEY_p:
            self.on_print()
            return True
        return False

    print_settings = None

    def on_print(self, action=None):
        print_op = Gtk.PrintOperation()

        if self.print_settings is not None:
            print_op.set_print_settings(self.print_settings)

        print_op.connect("begin_print", self.begin_print)
        print_op.connect("draw_page", self.draw_page)

        res = print_op.run(Gtk.PrintOperationAction.PRINT_DIALOG, self.get_toplevel())
        if res == Gtk.PrintOperationResult.APPLY:
            self.print_settings = print_op.get_print_settings()

    def begin_print(self, operation, context):
        operation.set_n_pages(1)
        return True

    def draw_page(self, operation, context, page_nr):
        cr = context.get_cairo_context()
        rect = self.get_allocation()
        self._draw_graph(cr, rect)

    def get_drag_action(self, event):
        state = event.state
        if event.button in (1, 2):  # left or middle button
            modifiers = Gtk.accelerator_get_default_mod_mask()
            if state & modifiers == Gdk.ModifierType.CONTROL_MASK:
                return actions.ZoomAction
            elif state & modifiers == Gdk.ModifierType.SHIFT_MASK:
                return actions.ZoomAreaAction
            else:
                return actions.PanAction
        return actions.NullAction

    def on_area_button_press(self, area, event):
        self.animation.stop()
        self.drag_action.abort()
        action_type = self.get_drag_action(event)
        self.drag_action = action_type(self)
        self.drag_action.on_button_press(event)
        self.presstime = time.time()
        self.pressx = event.x
        self.pressy = event.y
        return False

    def is_click(self, event, click_fuzz=4, click_timeout=1.0):
        assert event.type == Gdk.EventType.BUTTON_RELEASE
        if self.presstime is None:
            # got a button release without seeing the press?
            return False
        # XXX instead of doing this complicated logic, shouldn't we listen
        # for gtk's clicked event instead?
        deltax = self.pressx - event.x
        deltay = self.pressy - event.y
        return (time.time() < self.presstime + click_timeout and
                math.hypot(deltax, deltay) < click_fuzz)

    def on_area_button_release(self, area, event):
        """
        This part is responsible for what happens when a node is clicked
        """
        self.drag_action.on_button_release(event)
        self.drag_action = actions.NullAction(self)
        x, y = int(event.x), int(event.y)
        if self.is_click(event):
            el = self.get_element(x, y)

            if self.conflictMode == ConflictMode.CONFLICT_MODE_OFF:
                if isinstance(el, Node):
                    # pass on the nodeId and conflictNodes
                    nodeId = int(el.id)
                    self.sidebar.emit("highlight", nodeId, self.conflict_nodes[nodeId])

                if event.button == 1: # left click
                    jump = self.get_jump(x, y)
                    if jump is not None:
                        self.animate_to(jump.x, jump.y)

                    return True
            elif self.conflictMode == ConflictMode.CONFLICT_SELECTION:
                if isinstance(el, Node):
                    self.graph.selectedNodes.add(el.id)
            elif self.conflictMode == ConflictMode.CONFLICT_MODE_ON:
                pass
                # do nothing

        if event.button == 1 or event.button == 2:
            return True
        return False

    def on_area_scroll_event(self, area, event):
        if event.direction == Gdk.ScrollDirection.UP:
            self.zoom_image(self.zoom_ratio * self.ZOOM_INCREMENT,
                            pos=(event.x, event.y))
            return True
        if event.direction == Gdk.ScrollDirection.DOWN:
            self.zoom_image(self.zoom_ratio / self.ZOOM_INCREMENT,
                            pos=(event.x, event.y))
            return True
        return False

    def on_area_motion_notify(self, area, event):
        self.drag_action.on_motion_notify(event)
        return True

    def on_area_size_allocate(self, area, allocation):
        if self.zoom_to_fit_on_resize:
            self.zoom_to_fit()

    def animate_to(self, x, y):
        del self.history_forward[:]
        self.history_back.append(self.get_current_pos())
        self.history_changed()
        self._animate_to(x, y)

    def _animate_to(self, x, y):
        self.animation = animation.ZoomToAnimation(self, x, y)
        self.animation.start()

    def history_changed(self):
        self.emit(
            'history',
            bool(self.history_back),
            bool(self.history_forward))

    def on_go_back(self, action=None):
        try:
            item = self.history_back.pop()
        except LookupError:
            return
        self.history_forward.append(self.get_current_pos())
        self.history_changed()
        self._animate_to(*item)

    def on_go_forward(self, action=None):
        try:
            item = self.history_forward.pop()
        except LookupError:
            return
        self.history_back.append(self.get_current_pos())
        self.history_changed()
        self._animate_to(*item)

    def window2graph(self, x, y):
        rect = self.get_allocation()
        x -= 0.5*rect.width
        y -= 0.5*rect.height
        x /= self.zoom_ratio
        y /= self.zoom_ratio
        x += self.x
        y += self.y
        return x, y

    def get_element(self, x, y):
        x, y = self.window2graph(x, y)
        return self.graph.get_element(x, y)


    def get_jump(self, x, y):
        x, y = self.window2graph(x, y)
        return self.graph.get_jump(x, y)
    

    def on_node_highlighted(self, event, nodeId):
        # TODO: Add logic here
        print("This node was highlighted: ", nodeId)
        pass
