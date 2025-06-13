# Templates
CM Services uses [jinja](https://jinja.palletsprojects.com/en/stable/templates/) templates when writing BPS submit YAML files and submit scripts for various operations. These templates enforce a common structure for these files while allowing some flexibility at the campaign or step level. Generally, the `data` object associated with a campaign element is used to populate the environment used to render these templates.

The template files used by CM Service are in the `src/lsst/cmservice/templates` directory and are part of the CM Service Python package namespace.

## WMS Submit Script
The template `wms_submit_sh.j2` is used to render the shell script used, among other things, to call a BPS submit command along with a rendered BPS submit YAML. When the campaign's `script_method` is "htcondor", the execution environment of this script is expected to be an HTCondor interactive node.

This template is structured as follows with a number of named phases. Those phases indicated by square brackets (`[...]`) are "baked into" the template and will always be present. Those phases indicated by angle bracket (`<...>`) are available for campaign designers to insert or override values as appropriate by including an object with a matching name in a `data` object mapping at a step or campaign level.

```
[shebang]
<prepend>
[LSST setup]
<custom_lsst_setup>
[WMS setup]
<custom_wms_setup>
[command]
<append>
[EOF]
```

Designers are free to add any directives to the override blocks that are appropriate to their placement in the script (always executed top-to-bottom). Examples of directives that could be added to these phases include the following.

- `prepend`. Setting extra environment variables or calling commands prior to the setup of the LSST stack.
- `custom_lsst_setup`. Extra `setup -j ...` commands or environment variable manipulation following the Conda environment activation and EUPS setup.
- `custom_wms_setup`. Setting or changing WMS-specific environment variables.
- `append`. Calling commands after the primary work of the script is complete.

## BPS Submit YAML
The template `bps_submit_yaml.j2` is used to render the YAML file used with `bps submit` for a Step in a Campaign.

This template is structured with some general headings and has the potential to be quite complex. In most cases, the template assumes that the complete `data` dictionary for each Step is complete and correct.

The template sections are divided thusly:

```
[Header]
[LSST Setup]
[BPS Variables]
[Pipeline Configuration]
[Submission Environment Variables]
[BPS Payload Options]
[Clustering Configuration]
[Site WMS Configuration]
```

### Header
The header section includes metadata values such as the description and Jira link for the campaign.

### LSST Setup
The LSST Setup section includes top-level BPS configuration related to the LSST Stack, notably the stack version used for the workflow.

### BPS Variables
This section defines key-value pairs for BPS variable definitions, i.e., `{var_name}` that may be used throughout the workflow file.

### Pipeline Configuration
This section defines the `pipelineYaml` used for the workflow and any `includeConfigs` consumed by the workflow.

This section may also include arbitrary top-level bps configuration parameters that don't otherwise fit in another section. Steps may declare these parameters with a `data.bps_literals` object.

### Submission Environment Variables
This section populates a top-level `environments` object with key-value pairs from a `data.bps_environment` object. If no such object is defined, this section is not included.

### BPS Payload Options
This section populates a top-level `payload` object with key-value pairs from a `data.payload` object, and defines values for BPS pass-through arguments using `extra*Options` parameters.

### Clustering Configuration
This section includes any inline `clustering` directives based on the literal contents of a `data.cluster` object. If no such object is defined, this section is not included.

### Site WMS Configuration
This section includes configuration specific to a WMS and a Compute Site. This includes inline resource and memory management configurations. A `data.compute_site` object is used as a literal in this section.
