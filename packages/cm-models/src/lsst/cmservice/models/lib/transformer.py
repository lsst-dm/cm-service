"""Module for functions that bridge between the REST API and the internal
logic of the service, e.g., transforming REST API inputs into ORM-ready objects
that can be used by the service layer."""

from uuid import UUID, uuid5

from ..api.manifests import CampaignManifest, EdgeManifest, Manifest, ManifestModel, NodeManifest
from ..db.campaigns import Campaign, CampaignElement, Edge, Node
from ..db.campaigns import Manifest as OrmManifest


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
