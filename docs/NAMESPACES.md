# Campaign Namespaces

## Prototype (v0.x)

To support namespaced campaigns and spec blocks in CM Service prototype, a `DEFAULT` namespace is establishe as UUID5 value in the `common.enums` module. This is the name "io.lsst.cmservice" in the DNS namespace.

The loading and creation of spec-blocks, and specifications are provided a namespace in which to manipulate the short names of these objects. The functions related to these operations now include a `namespace` argument to which the namespace UUID of a campaign should be provided.

A campaign's namespace is the UUID5 of the campaign's short name in the application's `DEFAULT` namespace.

For each "spec block" a Campaign declares, a record ID and a name uniquely identify it within the database. Although the name column does not have a unique constraint, there is heavy use of a "locate by name" operation and spec blocks are referenced by name throughout a Campaign's spec/manifest file.

To apply a namespaced name to these spec blocks, the stored name of the spec block is modified to include the campaign namespace component. All references to the spec block may be made by short name as long as the campaign namespace is known during the lookup so the unique name can be generated on-demand.

* Scripts, Steps, and Groups are already effectively namespaced, with a "fullname" that expresses the owning campaign. The short names given to these objects do not need to be manipulated to include a namespace.
