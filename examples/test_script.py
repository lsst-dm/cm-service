#!/usr/bin/env python

import os

dry_run = True

prod_dict = {
    # "HSC_DRP-Prod": "HSC_DRP-Prod",
    "HSC_DRP-RC2": "HSC_DRP-RC2",
    # "HSC_DRP-RC2_subset": "HSC_DRP-RC2_subset",
    # "hsc_micro": "hsc_micro",
    # "LATISS_DRP": "LATISS_DRP",
    # "LSSTCam-imSim_DRP-test-med-1": "LSSTCam-imSim_DRP-test-med-1",
    # "LSSTComCamSim_DRP": "LSSTComCamSim_DRP",
    # "LSSTComCamSim_nightly-validation": "LSSTComCamSim_nightly-validation",
}


test_name = "test"
weekly_name = "w_2024_20"

for wms in ["panda", "htcondor"]:
    for key, val in prod_dict.items():
        com1 = "cm-client load campaign "
        com1 += f"--yaml_file examples/example_{key}.yaml "
        com1 += f"--campaign_yaml examples/start_{key}.yaml "
        # com1 += f"--parent_name {key} "
        com1 += f"--name {test_name}_{wms} "
        # com1 += f"--spec_name {key}_{wms} "
        com1 += f'--data "lsst_version:{weekly_name}; prod_area:output/archive;" '
        com1 += f"--collections out:{key}/{weekly_name}_test"
        print(com1)
        if not dry_run:
            os.system(com1)


for wms in ["panda", "htcondor"]:
    for key, val in prod_dict.items():
        com2 = f"cm-client action process --fullname {key}/{test_name}_{wms} --fake_status accepted"
        print(com2)
        if not dry_run:
            pass
            # os.system(com2)
            # os.system("sleep 30")
