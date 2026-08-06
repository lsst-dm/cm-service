# Composable Configurations

Every node in a CM campaign assembles a configuration at the time it transitions from "waiting" to "ready," except for a Group node, which is created by its parent Step with its configuration fully in place.
The Step node composes the Group configuration as part of its "running" transition.

The composable configuration is made up of multiple Chain Mappings, one for each of the five kinds of high-level configuration (`lsst`, `bps`, `butler`, `wms`, and `site`).
In each of these chain mappings, the hierarchy is:

1. Direct node configuration
1. Campaign manifest (one of)
    1. Selected manifest (selectors matching labels)
    1. Campaign-default manifest
    1. Best-effort manifest
    1. None
1. Library manifest
1. Application Fallback/Manifest Defaults

## Manifest Contents
Every manifest is an object mapping parameters to values.
What parameters are available on which manifest is available via model definitions and through help pages in the Web GUI.

When a manifest configuration is composed, each manifest is added to a `ChainMap` where each parameter lookup is coalesced down the chain (or stack, if you prefer) of available manifests until a definition is found.

This is intuitive for *scalar* values (`k=v`) but less so for *complex* values (`k=[x, y, z]`).
Complex values are not *merged*; manifests expressing a complex value are authoritative for that value.

Exceptions or caveats to the above are:

- `include_files`. Every manifest supports an `include_files` list. While these values are not merged within a single chain, these values *are* merged across all manifests. In other words, the contents of a `butler.include_files` and a `site.include_files` are used as a merged set, but `butler.0.include_files` and `butler.1.include_files` are *not*, and only the contents of the highest-priority `butler` value are used at runtime.

## Configuration Chain
A node's configuration chain is composed of a stack of available manifests for each kind in the order expressed above.
In order of ascending priority, these potential manifest sources are detailed next.

### Manifest Defaults
If no other manifest provides a value for a configuration attribute elsewhere in the chain map, the manifest default value is used.
This value is defined in the object model for the manifest.
If no default value is defined for the value a runtime default may be read from application configuration.
If no runtime default is available for a value, that value remains undefined.

Some values are not meant for user configuration and are set by contract at runtime.
These parameters should be described as such in the model field description.

### Library Manifest
A library manifest is a manifest of version 0 in the default namespace.
This is a baseline manifest for the given type with general-purpose defaults, generally provided and seeded at application deployment. When a new campaign is created, it is the library manifest that is copied into the campaign as the initial set of campaign-default manifests, where they can be edited, replaced, or deleted before the campaign is saved.

> [!NOTE]
> The copy-on-create behavior will be deprecated.

### Campaign Manifest
A manifest from the campaign namespace is added to the chain.
A campaign may have more than one candidate manifest, but one and only one is added to the chain.
In descending priority, a *selected*, *default*, or *best-effort* manifest is picked.
If the manifest selection is still ambiguous, *no campaign manifest is added at all*.

### Selected Manifest
Any versioned manifest in the campaign namespace can be *selected* by a node by matching selectors with labels.
If a manifest's labels completely fulfill a node's selectors, that manifest is selected by the node, even if the manifest has additional labels that the node did not request.

Manifest version is used a tie-breaker when multiple manifests match the selection.
If the manifest selection is ambiguous or undefined, no manifest will be selected.
In other words, a manifest is selected if and only if it uniquely satisfies the node's selectors.

### Campaign Default Manifest
A versioned manifest in the campaign namespace which has the "default" flag set on it.
There can be only one "default" manifest of each kind in a campaign.
The default flag is set by the user and is not necessarily the "latest" version of a manifest, nor do new manifests automatically inherit a default flag from a previous version.

> [!NOTE]
> The *first* manifest of a kind added to a campaign may be assigned a default status automatically, which can later be reassigned to a different manifest as needed.

### Best Effort Manifest
If there is no campaign default manifest for a given type, the highest version available manifest is chosen.
If there is still ambiguity (e.g., multiple manifests with the same version are found), no manifest is added to the chain.

## Direct Node Configuration
Any configuration applied directly to the Node takes precedence over any other manifest in the chain mapping.
Group nodes in particular will have a direct configuration applied to them by their parent Step during creation, so they are "born" with a fully composed configuration applied to them directly.

Any parameter that can be added to a manifest can be added to a Node's configuration, and like other manifests in the chain,
