# Copyright 2008-2015 Jose Fonseca
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import math
import os
import re
import subprocess
import sys
import time
from enum import Enum


import gi
gi.require_version('Gtk', '3.0')
gi.require_version('PangoCairo', '1.0')

from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Gdk

# See http://www.graphviz.org/pub/scm/graphviz-cairo/plugin/cairo/gvrender_cairo.c

# For pygtk inspiration and guidance see:
# - http://mirageiv.berlios.de/
# - http://comix.sourceforge.net/

from . import actions
from ..dot.lexer import ParseError
from ..dot.parser import XDotParser
from . import animation
from . import actions
from .elements import Graph
from .elements import Node

from .sidebar import SideBar
from .dotwidget import DotWidget

from ..conflicts import mapper
from ..conflicts import dotCreater 


class FindMenuToolAction(Gtk.Action):
    __gtype_name__ = "FindMenuToolAction"

    def do_create_tool_item(self):
        return Gtk.ToolItem()

class DotWindow(Gtk.ApplicationWindow):
    """
    This is the main application window. Here, the elements for toolbar, sidebar and the dotwidget
    are created, and wired together.

    Any new top-level widget should be created here.
    """
    base_title = 'Dot Viewer'

    def __init__(self, widget=None, width=512, height=512):
        Gtk.Window.__init__(self)

        self.set_title(self.base_title)
        self.set_default_size(width, height)

        self.dotwidget = widget or DotWidget()
        self.dotwidget.connect("error", lambda e, m: self.error_dialog(m))
        self.dotwidget.connect("history", self.on_history)

        # Create sidebar
        self.sidebar = SideBar(widget=self.dotwidget)
        self.dotwidget.sidebar = self.sidebar


        box = Gtk.VBox()
        box.set_homogeneous(False) # Allows toolbars to be of different sizes

        # Header
        header = self.createHeader()
        box.pack_start(header, False, True, 0)

        # Container for sidebar
        pane = Gtk.HPaned(wide_handle=True) # makes for a better separator
        pane.pack1(self.sidebar, False, True)
        pane.pack2(self.dotwidget, True, False)
        box.add(pane)

        self.add(box)

        self.last_open_dir = "."
        self.set_focus(self.dotwidget)

        self.show_all()

    def createHeader(self):

        def addButton(iconName, callback, tooltipText=None, **kwargs):
            button = Gtk.ToolButton(icon_widget=Gtk.Image.new_from_icon_name(iconName, Gtk.IconSize.SMALL_TOOLBAR))
            button.set_tooltip_text(tooltipText)
            button.connect("clicked", callback)
            for propName, propVal in kwargs.items():
                button.set_property(propName, propVal)
                
            header.pack_start(button)
            return button
        
        def addSeparator():
            header.pack_start(Gtk.VSeparator())


        header = Gtk.HeaderBar.new()  

        # Look at https://developer.gnome.org/icon-naming-spec/ for different icon names
        addButton("applications-accessories", self.hideSidebar, tooltipText="Toggle sidebar")
        addSeparator()

        # File operations
        addButton("document-open", self.on_open, tooltipText="Load a new grph (.dot file)")
        addButton('view-refresh', self.on_reload, "Reloads the graph"),
        addButton("document-print", self.dotwidget.on_print, "Prints the currently visible part of the graph")
        addSeparator()

        # Zoom buttons
        addButton("zoom-in", self.dotwidget.on_zoom_in, "Zoom in")
        addButton("zoom-out", self.dotwidget.on_zoom_out, "Zoom out")
        addButton("zoom-fit-best", lambda x: self.dotwidget.zoom_to_fit(), "Zoom to fit")
        addButton("zoom-original", lambda x: self.dotwidget.zoom_image(1.0), "Zoom to 100%")
        addSeparator()

        # Forward/Back - Keeping track of buttons so we can disable/enable them in on_history method.
        self.back_action = addButton("go-previous", self.dotwidget.on_go_back, "Go back", sensitive=False)
        self.forward_action = addButton("go-next", self.dotwidget.on_go_forward, "Go forward", sensitive=False)

        # Conflict file operations
        addButton("image-loading", self.on_open_conflict_file, "Load a conflict file")
        conflictButton = Gtk.ToolButton(label="Select nodes")
        conflictButton.set_tooltip_text("Click here to start selecting nodes.\nSelected nodes will be in blue.")
        conflictButton.connect("clicked", self.dotwidget.on_conflict_button_pressed)
        header.pack_start(conflictButton)

        # Add Find text search
        # find_toolitem = Gtk.ToolItem()
        # self.textentry = Gtk.Entry(max_length=20)
        # self.textentry.set_icon_from_stock(0, Gtk.STOCK_FIND)
        # find_toolitem.add(self.textentry)
        # self.textentry.set_activates_default(True)
        # self.textentry.connect("activate", self.textentry_activate, self.textentry)
        # self.textentry.connect("changed", self.textentry_changed, self.textentry)
        # header.pack_start(find_toolitem)

        # show the standard 3 mnimize, maximize and close buttons
        # header.set_show_close_button(True)

        return header
    
    def hideSidebar(self, widget):
        self.sidebar.toggleVisibility()

    def find_text(self, entry_text):
        found_items = []
        dot_widget = self.dotwidget
        regexp = re.compile(entry_text)
        for element in dot_widget.graph.nodes:
            if element.search_text(regexp):
                found_items.append(element)
        return found_items

    def textentry_changed(self, widget, entry):
        entry_text = entry.get_text()
        dot_widget = self.dotwidget
        if not entry_text:
            dot_widget.set_highlight(None, search=True)
            return

        found_items = self.find_text(entry_text)
        dot_widget.set_highlight(found_items, search=True)

    def textentry_activate(self, widget, entry):
        entry_text = entry.get_text()
        dot_widget = self.dotwidget
        if not entry_text:
            dot_widget.set_highlight(None, search=True)
            return

        found_items = self.find_text(entry_text)
        dot_widget.set_highlight(found_items, search=True)
        if(len(found_items) == 1):
            dot_widget.animate_to(found_items[0].x, found_items[0].y)

    def set_filter(self, filter):
        self.dotwidget.set_filter(filter)

    def set_dotcode(self, dotcode, filename=None):
        if self.dotwidget.set_dotcode(dotcode, filename):
            self.update_title(filename)
            self.dotwidget.zoom_to_fit()
        
        self.sidebar.set_nodes_and_edges(self.dotwidget.graph)

    def set_xdotcode(self, xdotcode, filename=None):
        if self.dotwidget.set_xdotcode(xdotcode):
            self.update_title(filename)
            self.dotwidget.zoom_to_fit()

    def update_title(self, filename=None):
        if filename is None:
            self.set_title(self.base_title)
        else:
            self.set_title(os.path.basename(filename) + ' - ' + self.base_title)

    def open_file(self, filename):
        try:
            fp = open(filename, 'rb')
            self.set_dotcode(fp.read(), filename)
            fp.close()
        except IOError as ex:
            self.error_dialog(str(ex))


    def on_open_conflict_file(self, action):
        chooser = Gtk.FileChooserDialog(parent=self,
                                        title="Open html conflict File",
                                        action=Gtk.FileChooserAction.OPEN,
                                        buttons=(Gtk.STOCK_CANCEL,
                                                 Gtk.ResponseType.CANCEL,
                                                 Gtk.STOCK_OPEN,
                                                 Gtk.ResponseType.OK))
        chooser.set_default_response(Gtk.ResponseType.OK)
        chooser.set_current_folder(self.last_open_dir)
        filter = Gtk.FileFilter()
        filter.set_name("Html conflict files")
        filter.add_pattern("*.html")
        chooser.add_filter(filter)
        filter = Gtk.FileFilter()
        filter.set_name("All files")
        filter.add_pattern("*")
        chooser.add_filter(filter)
        if chooser.run() == Gtk.ResponseType.OK:
            filename = chooser.get_filename()
            self.last_open_dir = chooser.get_current_folder()
            chooser.destroy()
            self.load_conflict_file(filename)
        else:
            chooser.destroy()
    
    def load_conflict_file(self, fileName: str):
        conflictGraph = mapper.generateMap(fileName)
        self.dotwidget.set_conflict_graph(conflictGraph)


    def on_open(self, action):
        chooser = Gtk.FileChooserDialog(parent=self,
                                        title="Open dot File",
                                        action=Gtk.FileChooserAction.OPEN,
                                        buttons=(Gtk.STOCK_CANCEL,
                                                 Gtk.ResponseType.CANCEL,
                                                 Gtk.STOCK_OPEN,
                                                 Gtk.ResponseType.OK))
        chooser.set_default_response(Gtk.ResponseType.OK)
        chooser.set_current_folder(self.last_open_dir)
        filter = Gtk.FileFilter()
        filter.set_name("Graphviz dot files")
        filter.add_pattern("*.dot")
        chooser.add_filter(filter)
        filter = Gtk.FileFilter()
        filter.set_name("All files")
        filter.add_pattern("*")
        chooser.add_filter(filter)
        if chooser.run() == Gtk.ResponseType.OK:
            filename = chooser.get_filename()
            self.last_open_dir = chooser.get_current_folder()
            chooser.destroy()
            self.open_file(filename)
        else:
            chooser.destroy()

    def on_reload(self, action):
        self.dotwidget.reload()

    def error_dialog(self, message):
        dlg = Gtk.MessageDialog(parent=self,
                                type=Gtk.MessageType.ERROR,
                                message_format=message,
                                buttons=Gtk.ButtonsType.OK)
        dlg.set_title(self.base_title)
        dlg.run()
        dlg.destroy()
    
    def on_history(self, action, has_back, has_forward):
        self.back_action.set_sensitive(has_back)
        self.forward_action.set_sensitive(has_forward)
