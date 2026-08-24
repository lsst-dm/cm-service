# Daemon Loop Iteration Sequence Diagram

The Daemon loop automates the evolution of Campaigns and their graphs.
Every Campaign is a graph of 2 or more Nodes, and each Node implements a Finite State Machine for which each state transition is associated with a business logic task and a check mechanism.
While Campaigns are not themselves state machines, they do have an associated status; `paused` for Campaigns that are not currently active, `running` for Campaigns that the Daemon should actively manage, and `accepted` for Campaigns that are complete with a positive outcome.

## Definitions
- `daemon`. One or more application service pods running an event loop dedicated to autonomous operations, including Campaign evolution, notification handling, and scheduled events.
- `database`. A PostgreSQL database supporting both the `daemon` and `api` service application pods for CRUD operations. Client utilities, such as web or cli tools, use the public API and not direct database access.
- `campaign`. A namespace containing a graph (nodes and edges), configuration manifests, and other assets specific to a campaign.
- `node`. A node in a campaign graph responsible for affecting a piece of business logic associated with the campaign. This is usually a Butler or BPS operation to manage data collections or Science Pipeline tasks/steps/stages.

##
```mermaid
sequenceDiagram
    actor Daemon
    participant Database
    actor Handler
    participant Node
    Note over Node: Node implements FSM
    participant Data

    Daemon ->> Database: Check Tasks
    Database -->> Daemon: Task Entry

    opt Daemon injects Node
    Daemon ->> Database: Get Node
    Database -->> Daemon: Node Entry
    end
    Daemon ->> Handler: Creates instance of
    activate Handler

    opt Handler fetches Node
    Handler ->> Database: Get Node
    Database -->> Handler: Node Entry
    end

    Handler ->> Node: Creates instance of
    activate Node
    Handler -->> Node: Hydration
    Note over Handler, Node: Dependency and/or Config Injection
    Handler -->> Node: State Machine
    Note over Handler, Node: Restore or set FSM state
    Handler -->> Daemon: Handler Ready
    Daemon ->> Handler: Calls activation/process method
    Handler ->> Node: Transition State
    alt Success
    Node -->> Data: Materialize Assets
    Note over Handler, Data: Data assets are a side-effect to Handler
    else Fail
    Note over Node: Failure semantics are Node/FSM-internals
    Node -->> Node:
    end
    deactivate Node
    opt Handler fetches Node
    Handler ->> Database: Update Node Entry
    end
    Handler -->> Daemon: Handler Finished
    deactivate Handler
    opt Daemon injects Node
    Daemon ->> Database: Update Node Entry
    end
    Daemon ->> Database: Update Queue Entry
```
