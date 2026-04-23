"""Module for functions that bridge between the REST API and the internal
logic of the service, e.g., transforming REST API inputs into ORM-ready objects
that can be used by the service layer."""

from collections import defaultdict
from uuid import UUID, uuid5

from ..api.manifests import CampaignManifest, EdgeManifest, Manifest, ManifestModel, NodeManifest
from ..db.campaigns import Campaign, CampaignElement, Edge, Node
from ..db.campaigns import Manifest as OrmManifest


async def prepare_orm_from_manifest(manifest: dict, namespace: UUID | None = None) -> CampaignElement:
    """Given a dictionary representation of a campaign element manifest,
    create and return an ORM object for that manifest.

    This function implements some of the same business logic as found in the
    creation REST API for a given manifest kind, but always in the context of
    creating objects for a new campaign -- so versions are always 1, there are
    no pre-checks for existing objects, etc.

    After the business logic is applied to the manifest request, we get an ORM
    from a transformer

    Parameters
    ----------
    manifest: Mapping
        A campaign element manifest as a python dict, as one loaded from YAML
        or JSON.

    namespace: UUID | None
        The namespace in which the element should exist. If not None, the UUID
        is added to the ORM object's metadata.

    Returns
    -------
    CampaignElement
        An ORM object representing a CM Campaign element, one of a `Campaign`,
        `Node`, `Edge`, or `Manifest`.

    Raises
    ------
    RuntimeError
        If an ORM object can't be prepared from the given inputs, e.g., an
        edge manifest without a namespace.
    """
    # One assumption this function can make is that it is only ever preparing
    # VERSION 1 objects for a NEW CAMPAIGN, which simplifies the service-layer
    # logic of generating Node and Edge ORM objects.

    api_request_mapping: defaultdict[str, type[Manifest]] = defaultdict(
        lambda: ManifestModel,
        campaign=CampaignManifest,
        node=NodeManifest,
        edge=EdgeManifest,
    )

    # Using the dict manifest, apply business logic to it and build a request
    # model object from it. This is notably similar to what FastAPI is doing
    # with request bodies in our POST routes.
    if namespace is not None:
        manifest["metadata"] |= {"namespace": str(namespace)}

    match manifest["kind"]:
        case "edge":
            if namespace is None:
                raise RuntimeError("Can't create an edge without a namespace")

            # in an edge, the adjacencies may be specified as a uuid string,
            # an unversioned name, or a versioned name.
            for key in ["source", "target"]:
                node = manifest["spec"][key]
                try:
                    _ = UUID(node)
                    # this is fine, do nothing else
                except ValueError:
                    # make sure the node is always version 1
                    node_name = node.split(".")[0]
                    adjacency = uuid5(namespace, f"{node_name}.1")
                    manifest["spec"][key] = str(adjacency)

        case _:
            manifest["metadata"]["version"] = 1

    manifest_request = api_request_mapping[manifest["kind"]].model_validate(manifest)
    orm = manifest_to_orm(manifest_request)
    return orm


def manifest_to_orm(manifest: Manifest) -> CampaignElement:
    """Transform a manifest dictionary into an ORM-ready object.

    This function implements the logic used by the REST API to transform a
    request body Manifest into an ORM object that can be added to the database.

    This function assumes that any business logic specific to the request has
    already been performed and applied.

    Parameters
    ----------
    manifest: Manifest
        A fully populated request manifest for the ORM kind being transformed.
        Any business logic concerning names, namespaces, and other dynamic
        values should be precomputed and applied to the manifest request before
        calling this function.
    """
    match manifest:
        case CampaignManifest():
            return Campaign.model_validate(
                dict(
                    name=manifest.metadata_.name,
                    metadata_=manifest.metadata_.model_dump(),
                    configuration=manifest.spec.model_dump(),
                )
            )
        case NodeManifest():
            # TODO migrate these assignments to the model validator
            node_name = manifest.metadata_.name
            node_kind = manifest.metadata_.kind
            node_namespace_uuid = UUID(manifest.metadata_.namespace)
            node_version = manifest.metadata_.version

            return Node(
                id=uuid5(node_namespace_uuid, f"{node_name}.{node_version}"),
                name=node_name,
                namespace=node_namespace_uuid,
                kind=node_kind,
                version=node_version,
                configuration=manifest.spec.model_dump(exclude_none=True),
                metadata_=manifest.metadata_.model_dump(exclude_none=True),
            )

        case EdgeManifest():
            edge_name = manifest.metadata_.name
            edge_namespace_uuid = UUID(manifest.metadata_.namespace)
            edge_id = uuid5(edge_namespace_uuid, edge_name)
            source_node_uuid = UUID(manifest.spec.source)
            target_node_uuid = UUID(manifest.spec.target)

            return Edge(
                id=edge_id,
                name=edge_name,
                namespace=edge_namespace_uuid,
                source=source_node_uuid,
                target=target_node_uuid,
                metadata_=manifest.metadata_.model_dump(exclude_none=True),
                configuration=manifest.spec.model_dump(exclude_none=True),
            )

        case ManifestModel():
            manifest_name = manifest.metadata_.name
            manifest_version = manifest.metadata_.version
            manifest_namespace_uuid = UUID(manifest.metadata_.namespace)
            manifest_id = uuid5(manifest_namespace_uuid, f"{manifest.kind}")
            manifest_id = uuid5(manifest_id, f"{manifest_name}.{manifest_version}")

            return OrmManifest(
                id=manifest_id,
                name=manifest_name,
                namespace=manifest_namespace_uuid,
                kind=manifest.kind,
                version=manifest_version,
                metadata_=manifest.metadata_.model_dump(exclude_none=True),
                spec=manifest.spec.model_dump(exclude_none=True),
            )
        case _:
            error_str = f"Unsupported manifest kind: {manifest.kind}"
            raise ValueError(error_str)
