from typing import Set
from graphviz import Digraph
import queue

def parseNodes(nodes: str) -> Set[int]:
    """
    Given a node list in following format: "1,2,5-10,6",
    it returns the following list: [1,2,5,6,7,8,9,10]
    """
    uniqueNodes = set()
    for item in nodes.split(","):
        if '-' in item:
            firstAndLast = item.split("-")
            if len(firstAndLast) != 2:
                print("Parse error on item", item)
                return []
            first = int(firstAndLast[0])
            last = int(firstAndLast[1])
            if last < first:
                first, last = last, first
            for i in range(first, last+1):
                uniqueNodes.add(i)
        else:
            uniqueNodes.add(int(item))
    return uniqueNodes



def truncatedGraphListOld(graph, nodes):
    """
    Takes a graph, and returns a corresponding dot source for it
    Only the nodes in nodes are included in the graph
    """
    dot = Digraph(comment='New graph')
    for n in graph.nodes:
        if n.id in nodes:
            dot.node(name = n.id.decode("utf-8"), label=n.label)
    s = dot.source
    return bytes(s, "utf-8")

def bfs(graph):
    nodes = graph.selectedNodes
    exploredNodes = set()
    for n in nodes:
        q = queue.Queue()
        q.put(n)
        while q.empty() is False:
            node = q.get()
            exploredNodes.add(node)
            edges = [edge for edge in graph.edges if edge.src.id is node]
            for edge in edges:
                dest = edge.dst.id
                if dest not in exploredNodes:
                    q.put(dest)
    
    graph.selectedNodes = exploredNodes





def truncatedGraphList(graph, nodes):
    """
    Takes a graph, and returns a corresponding dot source for it
    Only the nodes in nodes are included in the graph
    """
    dot = """
    digraph G {
	    node [style=rounded];

    """
    for n in graph.nodes:
        if n.id in nodes:
            nodeString = n.id.decode("utf-8") + "[shape=record,label=\"{" + n.label.replace('\n', "\l|") + "\l}\"];\n"
            dot += nodeString
    dot = dot.replace('>', "&gt;").replace('<', "&lt;").replace('||', " &#124;&#124;")

    for edge in graph.edges:
        if edge.src.id in nodes and edge.dst.id in nodes:
            dot += edge.src.id.decode("utf-8") + "->" + edge.dst.id.decode("utf-8") + " ;\n"

    dot += "}\n"
    return bytes(dot, "utf-8")



