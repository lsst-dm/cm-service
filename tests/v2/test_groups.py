from itertools import pairwise
from unittest.mock import Mock, patch
from urllib.parse import urlparse
from uuid import UUID, uuid5

import numpy as np
import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from lsst.cmservice.db.campaigns_v2 import Node
from lsst.cmservice.machines.node import StepMachine

pytestmark = pytest.mark.asyncio(loop_scope="module")
"""All tests in this module will run in the same event loop."""


@patch("lsst.cmservice.common.splitter.QuerySplitter.butler_query", return_value=np.arange(3_932_128))
async def test_campaign_with_groups(
    MockSplitter: Mock, test_campaign_groups: str, session: AsyncSession
) -> None:
    campaign_id = urlparse(url=test_campaign_groups).path.split("/")[-2:][0]

    # Prepare a step with no grouping
    node_id = uuid5(UUID(campaign_id), "lambert.1")

    node = await session.get_one(Node, node_id)
    await session.commit()

    node_machine = StepMachine(o=node)
    await node_machine.trigger("prepare")

    # Prepare a step with values-based grouping
    node_id = uuid5(UUID(campaign_id), "ash.1")

    node = await session.get_one(Node, node_id)
    await session.commit()

    node_machine = StepMachine(o=node)
    await node_machine.trigger("prepare")

    # Prepare a step with query grouping
    node_id = uuid5(UUID(campaign_id), "ripley.1")

    node = await session.get_one(Node, node_id)
    await session.commit()

    node_machine = StepMachine(o=node)
    await node_machine.trigger("prepare")

    ...


def test_array_splitting() -> None:
    """Test demonstrates the partitioning of an arbitrarily large np array via
    partial sorting.
    """
    dimension = "field"
    d = np.arange(932_673)
    np.random.shuffle(d)

    group_size = min(100_000, d.size // 8)
    group_count = (d.size // group_size) + (d.size % group_size != 0)
    partition_indices = np.linspace(0, d.size, num=group_count, dtype=int, endpoint=False)

    d.partition(partition_indices)

    predicates = []
    for a, b in pairwise(partition_indices):
        predicates.append(f"{dimension} >= {d[a]} AND {dimension} < {d[b]}")
    predicates.append(f"{dimension} >= {d[partition_indices[-1]]}")
