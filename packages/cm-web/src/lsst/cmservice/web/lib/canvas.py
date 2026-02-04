import networkx as nx

from lsst.cmservice.common.graph import contract_simple_step_nodes


async def nx_to_flow(g: nx.DiGraph, *, contract: bool = True) -> dict[str, list]:
    """Converts a networkx graph to a collection of nodes and edges that can be
    used with a Svelte Flow canvas.

    This function requires that the graph be built using the "simple" data
    view.

    Parameters
    ----------
    g: nx.DiGraph
        A networkx directed graph, created by the `graph_from_edge_list_v2`
        function. The node view must be "simple".

    contract : bool
        If true, the graph will be "contracted" -- meaning any dynamic nodes
        like groups will be merged into their parents. This is done without
        concern for the status of any node, and no configuration is preserved.
        Contracting the graph in this way is useful when the graph is being
        cloned or copied such that only first-tier nodes are kept.
    """
    # make sure the graph is in simple view
    # TODO contract dynamic nodes from the graph
    contracted_graph = await contract_simple_step_nodes(g)

    # Every node is placed at (0, 0) but the canvas component calls auto-layout
    # in its onMount lifecycle callback so this isn't a problem.
    # In the simple node view the `id` of each node is its `name.version`
    # string; we do not preserve its uuid here.
    return {
        "nodes": [
            {
                "id": id,
                "position": {"x": 0, "y": 0},
                "data": {"name": node["name"]},
                "type": node["kind"],
            }
            for id, node in contracted_graph.nodes(data=True)
        ],
        "edges": [
            {
                "id": f"{source}--{target}",
                "source": source,
                "target": target,
            }
            for source, target in contracted_graph.edges
        ],
    }
