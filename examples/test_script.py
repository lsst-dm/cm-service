#!/usr/bin/env python

# import os

prod_dict = {
    "LSSTCam-imSim_DRP-test-med-1": "LSSTCam-imSim_DRP-test-med-1_test",  # httpcore.ReadTimeout: timed out
    "LSSTComCamSim_DRP": "LSSTComCamSim_DRP",  #  httpcore.ReadTimeout: timed out
    "LSSTComCamSim_nightly-validation": "LSSTComCamSim_nightly-validation",  # success
    "hsc_micro": "hsc_micro",  # success
    "HSC_DRP-RC2": "HSC_DRP-RC2",  # httpcore.ReadTimeout: timed out
    "HSC_DRP-RC2_subset": "HSC_DRP-RC2_subset",  # httpcore.ReadTimeout: timed out
    "HSC_DRP-Prod": "HSC_DRP-Prod",  # httpcore.ReadTimeout: timed out
    "LATISS_DRP": "LATISS_DRP",
}

prod_dict = {
    "LATISS_DRP": "LATISS_DRP",
}

weekly_name = "w_2024_21"

for wms in ["panda", "htcondor"]:
    for key, val in prod_dict.items():
        com1 = "cm-client load campaign "
        com1 += f"--yaml_file examples/example_{key}.yaml --parent_name {key} "
        com1 += f"--name {weekly_name}_{wms} --data lsst_version:{weekly_name} --spec_name {val}_{wms}"
        print(com1)
        # os.system(com1)

        com2 = f"cm-client action process --fullname {key}/{weekly_name}_{wms} --fake_status accepted"
        print(com2)
        # os.system(com2)

        # os.system("sleep 30")
