from networkx import DiGraph

from ..lib import enum, logging

logger = logging.LOGGER.bind(module=__name__)


def nx_to_mermaid(graph: DiGraph) -> str:
    """Generates a minimally interactive mermaid flowchart diagram based on a
    campaign graph (in simple view mode as from the graph API).
    """
    nodes = graph.nodes.data()
    mmd = "graph LR; "
    for edge in graph.edges:
        mmd += f"{edge[0]} --> {edge[1]}; "
    for node in nodes:
        node_decoration = enum.StatusDecorators[node[1]["status"]]
        mmd += f"""{node[0]}[{node[1]["name"]} v{node[1]["version"]}]\n"""
        mmd += f"""style {node[0]} fill:{node_decoration.hex}\n"""
        mmd += f"""click {node[0]} call emitEvent("node_click", "{node[1]["uuid"]}")\n"""
    logger.debug(mmd)
    return mmd
