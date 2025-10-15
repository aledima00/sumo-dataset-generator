import importlib.util
import sys

def loadPyConfig(path:str)-> tuple[dict[str,set[str]],dict[str,set[str]],list[str]]:
    """Load a Python configuration file containing raw nodes and edges for the graph.
    Args:
        path (str): Path to the Python file containing the configuration.
    Returns:
        tuple: A tuple containing:
            - nodes_raw (dict): Dictionary of raw nodes.
            - edges_raw (dict): Dictionary of raw edges.
            - sources (list): List of source node IDs.
    """
    spec = importlib.util.spec_from_file_location("data",path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["data"] = module
    spec.loader.exec_module(module)
    return module.nodes_raw, module.edges_raw, module.sources
