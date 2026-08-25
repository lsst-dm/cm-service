"""Module for custom table creation functions"""

from collections.abc import Mapping

from nicegui import ui


def provenance_report_table(provenance: Mapping) -> None:
    """Create a table from a provenance report"""
    for task in provenance["tasks"].keys():
        caveats_tree = (
            [
                {
                    "id": "caveats",
                    "label": "Caveats",
                    "children": [
                        {
                            "id": caveat["code"],
                            "label": f"Count: {caveat['count']}",
                            "token_description": (
                                f"{caveat['token']}: {provenance['legend'][caveat['token']]}"
                            ),
                            "code_description": (f"{caveat['code']}: {provenance['legend'][caveat['code']]}"),
                        }
                        for caveat in provenance["tasks"][task]["caveats"]
                    ],
                }
            ]
            if provenance["tasks"][task]["caveats"]
            else []
        )

        exceptions_tree = (
            [
                {
                    "id": "exceptions",
                    "label": "Exceptions",
                    "children": [
                        {
                            "id": exception["Exception"],
                            "label": exception["Exception"],
                            "description": (
                                f"Successes: {exception.get('Successes', 0)} | "
                                f"Failures: {exception.get('Failures', 0)}"
                            ),
                        }
                        for exception in provenance["tasks"][task]["exceptions"]
                    ],
                }
            ]
            if provenance["tasks"][task]["exceptions"]
            else []
        )

        provenance["tasks"][task]["caveats"] = caveats_tree
        provenance["tasks"][task]["exceptions"] = exceptions_tree

    rows = []
    columns = [
        {"name": "task", "label": "task", "field": "task", "sortOrder": "ad"},
        {"name": "caveats", "label": "caveats", "field": "caveats"},
        {"name": "exceptions", "label": "exceptions", "field": "exceptions"},
    ]

    column_names = [c["name"] for c in columns]
    status_names = set()
    for task, statuses in provenance["tasks"].items():
        rows.append({"task": task, **statuses})
        status_names.update({status for status in statuses.keys() if status not in column_names})

    columns.extend(
        [
            {
                "name": status,
                "label": status,
                "field": status,
                ":format": "(val) => val == null ? 0 : new Intl.NumberFormat().format(val)",
            }
            for status in status_names
        ]
    )

    rows = [{"task": k, **v} for k, v in provenance["tasks"].items()]
    table = ui.table(
        columns=columns,
        rows=rows,
        row_key="task",
        column_defaults={"sortable": True, "headerClasses": "uppercase text-primary"},
        pagination={"sortBy": "caveats", "descending": True, "rowsPerPage": 10},
    ).props("column-sort-order='da'")

    table.add_slot(
        "body-cell-caveats",
        r"""
        <q-td :props="props">
            <q-tree
                :nodes="props.value"
                node-key="id"
                label-key="label"
                no-nodes-label="No Caveats"
                dense
            >
            <template v-slot:default-body="treeProps">
                <div :props="treeProps" style="text-align: left">
                    <div>{{ treeProps.node.token_description }}</div>
                    <div>{{ treeProps.node.code_description }}</div>
                </div>
            </template>
            </q-tree>
        </q-td>
    """,
    )

    table.add_slot(
        "body-cell-exceptions",
        r"""
        <q-td :props="props">
            <q-tree
                :nodes="props.value"
                node-key="id"
                label-key="label"
                no-nodes-label="No Exceptions"
                dense
            >
            <template v-slot:default-body="treeProps">
                <div :props="treeProps" style="text-align: left">
                    <div>{{ treeProps.node.description }}</div>
                </div>
            </template>
            </q-tree>
        </q-td>
    """,
    )
