from bs4 import BeautifulSoup as bs
from typing import List, Set, Dict, Tuple, Optional

def generateMap(fileName: str) -> Dict[int, List[int]]:
    """
    returns a dictionary of nodeId to list of nodeId which the key node is in conflict in
    """
    import re    
    def getTags(taggedString: str) -> (int, int):
        p = re.compile(r"\((\d*),\d\)")
        m = p.findall(taggedString)
        return int(m[0]), int(m[1])

    with open(fileName, 'r') as f:
        soup = bs(f, 'html.parser')
        tds = soup.findAll('td')
        result = {}
        for td in tds:
            if td.has_attr('title') and td.has_attr('class') and td.get('class') == ["tg-red2"]:
                key, value = getTags(td.get('title'))
                if key == value:
                    continue

                if key in result:
                    x = result[key]
                    if value not in x:
                        x.append(value)
                else:
                    result[key] = [value]
        return result

def generateFullMap(fileName: str) -> Dict[int, List[int]]:
    import re    
    def getTags(taggedString: str) -> (int, int):
        p = re.compile(r"\((\d*),\d\)")
        m = p.findall(taggedString)
        return int(m[0]), int(m[1])

    def getStatements(td):
        return list(map(lambda i: i.contents[0], td.findAll('pre')))

    with open(fileName, 'r') as f:
        soup = bs(f, 'html.parser')
        tds = soup.findAll('td')
        result = {}
        for td in tds:
            if td.has_attr('title') and td.has_attr('class') and td.get('class') == ["tg-red2"]:
                key, value = getTags(td.get('title'))
                statements = getStatements(td)
                if key == value:
                    continue
                
                c = ConflictNode(value, statements)
                if key in result:
                    x = result[key]
                    x.add(c)
                else:
                    result[key] = {c}
        return result


class ConflictNode:
    def __init__(self, nodeId, statements):
        self.nodeId = nodeId
        self.statements = statements

    def __eq__(self, other):
        if isinstance(other, ConflictNode):
            return other.nodeId == self.nodeId
        return False
 
    def __hash__(self):
        return hash(self.nodeId)

 
