import gi
gi.require_version('Gtk', '3.0')
gi.require_version('PangoCairo', '1.0')

from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Gdk
class SideBar(Gtk.Revealer):
    __gsignals__ = {

        ## Signal that is emitted by the drawing area when a node is clicked.
        'highlight': (GObject.SIGNAL_RUN_FIRST, None, (int, object))
    }

    def __init__(self, nodes=None, edges=None, widget=None):
        Gtk.Revealer.__init__(self)

        notebook = Gtk.Notebook.new()
        # self.set_expanded(True)
        # consts for columns
        self.TEXT_COL=0
        self.ID_COL=1

        ## set in treeModelSetup
        self.store = None
        # self.nodes is dict from node.id (int) to node
        self.nodes = nodes if nodes is not None else {}

        # self.childNodes is dict from nodeId to list of nodeId
        # {int: list(int)}
        self.childNodes = edges if edges is not None else {}
        self.dotwidget = widget

        self.connect("highlight", self.on_highlighted)

        # child nodes
        self.childTreeview = Gtk.TreeView.new()
        self.childTreeview.connect("row-activated", self.on_row_activated)

        self.treeViewSetup(self.childTreeview)
        self.treeModelSetup(self.childTreeview, edges=self.childNodes)

        childViewWindow = Gtk.ScrolledWindow.new()
        childViewWindow.add(self.childTreeview)
        notebook.append_page(childViewWindow, Gtk.Label(label="Adjacent nodes"))

        # conflict nodes
        self.conflictTreeview = Gtk.TreeView.new()
        self.conflictTreeview.connect("row-activated", self.on_row_activated)

        self.treeViewSetup(self.conflictTreeview)
        self.treeModelSetup(self.conflictTreeview, edges={})

        conflictViewWindow = Gtk.ScrolledWindow.new()
        conflictViewWindow.add(self.conflictTreeview)
        notebook.append_page(conflictViewWindow, Gtk.Label(label="Conflict nodes"))

        self.set_vexpand(True)
        self.set_border_width(5)
        self.add(notebook)
        self.set_reveal_child(True)

        self.set_hexpand(True)
        self.show_all()
    
    def toggleVisibility(self):
        if self.get_child_revealed():
            self.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
            self.set_reveal_child(False)
        else:
            self.set_transition_type(Gtk.RevealerTransitionType.SLIDE_RIGHT)
            self.set_reveal_child(True)


    def on_highlighted(self, event, nodeId, conflictNodes=None):
        """
        When a node is clicked in the dotwidget area, this method scrolls to the corresponding
        node in the sidebar, and selects it.
        TODO: Also highlight conflictNodes?
        """

        treeview = self.get_nth_page(self.get_current_page()).get_child()
        store = treeview.get_model()
        nodeIter = store.get_iter_first()
        while nodeIter is not False and nodeIter is not None:
            curNodeId = store.get(nodeIter, self.ID_COL)[0]
            if (curNodeId == nodeId):
                treeview.get_selection().select_iter(nodeIter)
                path = store.get_path(nodeIter)
                treeview.scroll_to_cell(path=path)
                break

            nextNodeIter = store.iter_next(nodeIter)
            nodeIter = nextNodeIter

    def set_nodes_and_edges(self, graph):
        nodes = graph.nodes
        childEdges = graph.edges

        # reset both the stores
        self.childTreeview.get_model().clear()
        self.conflictTreeview.get_model().clear()


        self.nodes.clear()
        self.childNodes.clear()
        for node in nodes:
            label = node.label[:node.label.index('\n')]
            self.nodes[int(node.id)] = label

        conflictEdges =  dict(filter(lambda el: el[0] in self.nodes, graph.conflictingNodes.items()))

        for edge in childEdges:
            (srcId, dstId) = int(edge.src.id), int(edge.dst.id)
            srcList = []
            if srcId not in self.childNodes:
                self.childNodes[srcId] = []
            srcList = self.childNodes[srcId]
            srcList.append(dstId)
        
        self.populateTreeModel(edges=self.childNodes, treeview=self.childTreeview)
        self.populateTreeModel(edges=conflictEdges, treeview=self.conflictTreeview)

    def treeViewSetup(self, treeview):
        renderer = Gtk.CellRendererText.new()
        column = Gtk.TreeViewColumn("Nodes", renderer, text=self.TEXT_COL)
        treeview.append_column(column)

    def treeModelSetup(self, treeview, edges):
        # first column is display text, last is the node id
        store = Gtk.TreeStore(GObject.TYPE_STRING, GObject.TYPE_INT)
        treeview.set_model(store)
        self.populateTreeModel(edges=edges, treeview=treeview)

    def populateTreeModel(self, edges, treeview, rootIter=None):

        ## simple closure to set a node
        def setNode(nodeId, pos):
            store.set(pos, self.TEXT_COL, self.nodes[nodeId]) # set the text
            store.set(pos, self.ID_COL, nodeId) # set id

        store = treeview.get_model()
        nodeList = []
        if rootIter is None:
            nodeList = self.nodes.keys()
        else:
            nodeId = store.get(rootIter, self.ID_COL)[0]
            nodeList = edges[nodeId]
    
        if rootIter is not None and store.iter_has_child(rootIter):
            childIter = store.iter_children(rootIter)
            while childIter is not False and childIter is not None:
                nextChildIter = store.iter_next(childIter)
                store.remove(childIter)
                childIter = nextChildIter

        for node in nodeList:
            pos = store.append(rootIter)

            setNode(node, pos)
            # append children as well
            if node in edges:
                for child in edges[node]:
                    pos2 = store.append(pos)
                    setNode(child, pos2)
    
    def on_row_activated(self, treeview, node, column):
        # Signal the dotwidget
        store = treeview.get_model() 
        pos = store.get_iter(node)
        self.dotwidget.emit("node-highlighted", store.get(pos, self.ID_COL)[0])

        # We only need to expand the row in case we are in adjacent child mode
        if (treeview == self.childTreeview):
            if pos is None:
            # Don't know how this should be possible
                return
            
            edges = self.childNodes
            self.populateTreeModel(edges=edges, treeview=treeview, rootIter=pos)

