- create sumocfg if not exists
- make default Params too (yml, ...)
- add possibility to specify source edges/nodes
- modify route random growth by restricting choice by allowance
- update route generation for pedestrians to allowed ones:
    ```python
    import sumolib

    # Carica la rete
    net = sumolib.net.readNet("rete.net.xml")

    # Ottieni l'edge corrente (dove si trova il pedone)
    current_edge = net.getEdge("edge_id_corrente")

    # Trova tutte le connessioni in uscita
    outgoing_connections = current_edge.getOutgoing()

    # Filtra solo quelle percorribili dai pedoni
    pedestrian_edges = [
        conn.getTo() for conn in outgoing_connections
        if "pedestrian" in conn.getTo().getAllowed() or "walk" in conn.getTo().getAllowed()
    ]

    # Stampa gli edge raggiungibili a piedi
    for e in pedestrian_edges:
        print(e.getID())
    ``` 