from collections.abc import AsyncGenerator, Mapping, Sequence
from functools import partial
from itertools import pairwise

import numpy as np
from anyio import to_thread

from lsst.daf.butler import DimensionNameError, MissingDatasetTypeError

from ...config import config
from ..butler import BUTLER_FACTORY
from ..enums import SplitterEnum
from ..errors import CMInvalidGroupingError, CMNoButlerError
from .abc import Splitter


class QuerySplitter(Splitter):
    """Class implementing a group splitter based on Query split rules.

    Parameters
    ----------
    dataset : str
        The name of a Butler dataset type from which data IDs are determined
        and against which split operations occur.

    dimension : str
        The dimension found in the dataset along which the values are split.

    butler_label : str
        The name of a Butler known to this application's Butler Factory, as a
        "label". This generally should mean the name of the Butler as used with
        the ``DAF_BUTLER_REPOSITORIES`` environment variable, e.g.,
        "/repo/main".

    min_groups : int
        The minimum number of groups into which the Splitter must split data ID
        ranges into groups. Data IDs are generally equally distributed among
        groups, but the ultimate group may be short. If there are not enough
        data IDs to satisfy this parameter, an exception is raised.

    max_size : int
        The maximum number of Data IDs per group. Setting this to a small value
        results in more groups with fewer members. Groups may have fewer
        members than this parameter implies if smaller groups are necessary to
        satisfy the `min_groups` parameter.

    Raises
    ------
    CMNoButlerError
        If no Butler matching `butler_label` is known to the application's
        Butler Factory.

    CMInvalidGroupingError
        If the requested dataset type does not exist; the requested dimension
        is not present in the dataset type; or there are not enough Data ID
        members to satisfy the `min_groups` parameter.
    """

    __kind__ = SplitterEnum.QUERY

    def __init__(
        self,
        *args: Sequence,
        dataset: str,
        dimension: str,
        butler_label: str,
        min_groups: int = 1,
        max_size: int = 1_000_000,
        collections: list[str] = [],
        predicates: list[str] = [],
        **kwargs: Mapping,
    ):
        self.dataset = dataset
        self.dimension = dimension
        self.min_groups = min_groups
        self.max_size = max_size
        self.butler_label = butler_label
        self.collection_constraint = collections
        self.where = " AND ".join(predicates)

    async def butler_query(self) -> np.ndarray:
        """Get a butler and query its registry for the collection of data IDs
        associated with the subject dataset.

        The butler represented by `butler_label` is queried for dataset types
        where the supplied predicates are true. The query is constrained to
        either a step input collection or the campaign input collection
        list.

        Returns
        -------
        `numpy.ndarray`
            A potentially unsorted array of `dimension` values for each data ID
            discovered in the `dataset` as a Numpy array.
        """
        butler = await BUTLER_FACTORY.aget_butler(self.butler_label)

        if butler is None:
            raise CMNoButlerError

        # Sanity checks before running a potentially expensive query.
        try:
            dataset_type = butler.get_dataset_type(self.dataset)
            if self.dimension not in dataset_type.dimensions:
                msg = f"Dimension {self.dimension} not found in dataset {self.dataset}"
                raise DimensionNameError(msg)
        except MissingDatasetTypeError as e:
            msg = f"Dataset {self.dataset} not found in Butler registry"
            raise CMInvalidGroupingError(msg) from e
        except DimensionNameError as e:
            raise CMInvalidGroupingError from e

        # FIXME include campaign+step predicate constraints
        # NOTE the default behavior of the limit parameter is to log a warning
        # if the limit is exceeded and still cap the resultset. We are unlikely
        # to notice this warning, but we don't really want unbounded queries.
        # However, we don't want silently truncated results, either.
        refs_f = partial(
            butler.query_datasets,
            dataset_type,
            collections=self.collection_constraint,
            where=self.where,
            find_first=True,
            with_dimension_records=False,
            limit=config.butler.max_query_limit,
        )
        refs = await to_thread.run_sync(refs_f)
        # TODO could we just as well return an N-dimensional array and pull out
        # the specific target dimension later?
        dimension_dtype: np.dtypes.StringDType | type
        if (
            dimension_dtype := butler.dimensions.dimensions[self.dimension].primaryKey.getPythonType()
        ) is str:
            dimension_dtype = np.dtypes.StringDType()
        return np.fromiter({ref.dataId[self.dimension] for ref in refs}, dtype=dimension_dtype)

    async def split(self) -> AsyncGenerator[str]:
        """Produces group predicates by first querying a Butler for a set of
        relevant data ids, then organizing them into groups according to the
        node configuration.

        Yields
        ------
        str
            A string predicate for a Butler query describing the group range.
        """
        dataset_ref_values = await self.butler_query()

        if dataset_ref_values.size < self.min_groups:
            raise CMInvalidGroupingError("Not enough dataset elements to support minimum group count")

        group_size = min(self.max_size, dataset_ref_values.size // self.min_groups)
        group_count = (dataset_ref_values.size // group_size) + (dataset_ref_values.size % group_size != 0)

        # Given an unsorted array of known size, partition around a set of more
        # or less equally-spaced indices
        partition_indices = np.linspace(
            0, dataset_ref_values.size, num=group_count, dtype=int, endpoint=False
        )
        dataset_ref_values.partition(partition_indices)
        for a, b in pairwise(partition_indices):
            yield (
                f"{self.dimension} >= {dataset_ref_values[a]} AND {self.dimension} < {dataset_ref_values[b]}"
            )
        yield f"{self.dimension} >= {dataset_ref_values[partition_indices[-1]]}"
