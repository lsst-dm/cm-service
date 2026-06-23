#!/usr/bin/env python3
import os
import sys
from datetime import UTC, datetime, timedelta

from astropy.time import Time

from lsst.daf.butler import Butler, CollectionType, Config, DatasetType, Timespan  # type: ignore
from lsst.daf.butler.registry import ConflictingDefinitionError
from lsst.daf.butler.registry.interfaces import SchemaAlreadyDefinedError

TODAY = datetime.now(UTC)
YESTERDAY = TODAY - timedelta(days=1)
CHECK = "\u2713"
SKIP = "\u2192"
REPO_ROOT = "/opt/shared"
NUM_DETECTOR = 189
NUM_EXPOSURE = 1_000
SKYMAP = "lsst_cells_v2"


def create_test_repo():
    """Creates a butler repo and registry."""
    config = Config(
        {
            "root": REPO_ROOT,
            "registry": {"db": os.getenv("DB__URL")},
        }
    )
    try:
        Butler.makeRepo(REPO_ROOT, config=config, overwrite=True)
        sys.stdout.write(f"{CHECK} Created Butler Schema Registry\n")
    except SchemaAlreadyDefinedError:
        sys.stdout.write(f"{SKIP} Butler Schema Registry Already Exists\n")

    butler = Butler(config, without_datastore=True, writeable=True)  # type: ignore
    return butler


def register_collections_and_types(butler: Butler):
    """Creates some collections and dataset types."""
    for collection_, type_ in [
        ("LSSTCam/defaults", CollectionType.TAGGED),
        ("LSSTCam/templates", CollectionType.TAGGED),
        (f"LSSTCam/runs/prompt-{TODAY:%Y%m%d}", CollectionType.RUN),
        (f"LSSTCam/runs/prompt-{YESTERDAY:%Y%m%d}", CollectionType.RUN),
    ]:
        butler.registry.registerCollection(collection_, type_)
        sys.stdout.write(f"{CHECK} Created collection {collection_}\n")

    for dataset_, dimensions_, storage_ in [
        ("raw", ["detector", "exposure", "instrument"], "Exposure"),
        ("calexp", ["detector", "visit", "instrument"], "ExposureF"),
        ("post_isr_image", ["detector", "exposure"], "Exposure"),
    ]:
        butler.registry.registerDatasetType(
            DatasetType(
                name=dataset_,
                dimensions=dimensions_,
                storageClass=storage_,
                universe=butler.registry.dimensions,
            )
        )
        sys.stdout.write(f"{CHECK} Created dataset type {dataset_}\n")


def create_dimension_data(butler: Butler):
    butler.registry.insertDimensionData(
        "instrument",
        {
            "name": "LSSTCam",
            "class_name": "lsst.obs.base.Instrument",
            "visit_max": 10_000_000,
            "exposure_max": 10_000_000,
            "detector_max": 200,
        },
        skip_existing=True,
    )
    sys.stdout.write(f"{CHECK} Created LSSTCam Instrument\n")

    for detector in range(189):
        butler.registry.insertDimensionData(
            "detector",
            {
                "instrument": "LSSTCam",
                "id": detector,
                "full_name": f"R00_DET{detector:03d}",
                "name_in_raft": f"DET{detector:03d}",
                "raft": "R00",
                "purpose": "SCIENCE",
            },
            skip_existing=True,
        )
    sys.stdout.write(f"{CHECK} Created LSSTCam Detectors\n")

    for band_name in "grizy":
        butler.registry.insertDimensionData(
            "physical_filter",
            {
                "instrument": "LSSTCam",
                "name": f"{band_name}_01",
                "band": band_name,
            },
            skip_existing=True,
        )
    sys.stdout.write(f"{CHECK} Created LSSTCam Bands\n")

    butler.registry.insertDimensionData(
        "skymap", {"name": SKYMAP, "hash": SKYMAP.encode()}, skip_existing=True
    )
    sys.stdout.write(f"{CHECK} Created LSST Skymap\n")

    for tract_id in range(10_000):
        butler.registry.insertDimensionData(
            "tract",
            {
                "skymap": SKYMAP,
                "id": tract_id,
                "region": None,
            },
            skip_existing=True,
        )
    sys.stdout.write(f"{CHECK} Created LSST Tracts\n")

    butler.registry.insertDimensionData(
        "day_obs", {"instrument": "LSSTCam", "id": int(f"{YESTERDAY:%Y%m%d}")}, skip_existing=True
    )
    butler.registry.insertDimensionData(
        "day_obs", {"instrument": "LSSTCam", "id": int(f"{TODAY:%Y%m%d}")}, skip_existing=True
    )
    sys.stdout.write(f"{CHECK} Created day obs\n")


def create_exposures_and_visits(day_obs: datetime, butler: Butler):
    cadence = timedelta(seconds=35)
    start = day_obs.replace(hour=22, minute=0, second=0)

    for exposure in range(NUM_EXPOSURE):
        group = f"day_obs_{day_obs:%Y%m%d}_seqnum_{exposure:05d}"

        butler.registry.insertDimensionData(
            "group", {"instrument": "LSSTCam", "name": group}, skip_existing=True
        )

        butler.registry.insertDimensionData(
            "exposure",
            {
                "instrument": "LSSTCam",
                "id": int(f"{day_obs:%Y%m%d}{exposure:05d}"),
                "timespan": Timespan(Time(start), Time(start + cadence)),
                "obs_id": f"LR_O_{start:%Y%m%d}_{exposure:05d}",
                "physical_filter": "g_01",
                "day_obs": int(f"{day_obs:%Y%m%d}"),
                "group": group,
            },
            skip_existing=True,
        )

        butler.registry.insertDimensionData(
            "visit",
            {
                "instrument": "LSSTCam",
                "id": int(f"{day_obs:%Y%m%d}{exposure:05d}"),
                "name": f"visit_{day_obs:%Y%m%d}{exposure:05d}",
                "physical_filter": "g_01",
                "day_obs": int(f"{day_obs:%Y%m%d}"),
                "timespan": Timespan(Time(start), Time(start + cadence)),
            },
            skip_existing=True,
        )

        butler.registry.insertDimensionData(
            "visit_definition",
            {
                "instrument": "LSSTCam",
                "visit": int(f"{day_obs:%Y%m%d}{exposure:05d}"),
                "exposure": int(f"{day_obs:%Y%m%d}{exposure:05d}"),
            },
            skip_existing=True,
        )
        start += cadence
    sys.stdout.write(f"{CHECK} Created exposures and visits for {day_obs:%Y%m%d}\n")


def create_raws(day_obs: datetime, butler: Butler):
    datums = [
        {"instrument": "LSSTCam", "detector": detector, "exposure": int(f"{day_obs:%Y%m%d}{exposure:05d}")}
        for detector in range(NUM_DETECTOR)
        for exposure in range(NUM_EXPOSURE)
    ]
    try:
        butler.registry.insertDatasets("raw", dataIds=datums, run=f"LSSTCam/runs/prompt-{day_obs:%Y%m%d}")
        sys.stdout.write(f"{CHECK} Created raws for {day_obs:%Y%m%d}\n")
    except ConflictingDefinitionError:
        sys.stdout.write(f"{SKIP} Raws already exist for {day_obs:%Y%m%d}\n")


def main():
    butler = create_test_repo()
    create_dimension_data(butler)
    register_collections_and_types(butler)
    create_exposures_and_visits(YESTERDAY, butler)
    create_exposures_and_visits(TODAY, butler)
    create_raws(YESTERDAY, butler)
    create_raws(TODAY, butler)


if __name__ == "__main__":
    main()
