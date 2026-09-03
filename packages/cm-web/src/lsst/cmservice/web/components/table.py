"""Module for custom table creation functions"""

from collections.abc import Mapping

from nicegui import ui
from rich import box
from rich.console import Console
from rich.table import Table


def provenance_report_table(provenance: Mapping) -> ui.table:
    """Create a table from a provenance report"""
    hidden_columns = {"caveats_tree", "exceptions_tree"}
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

        provenance["tasks"][task]["caveats_tree"] = caveats_tree
        provenance["tasks"][task]["exceptions_tree"] = exceptions_tree

    rows = []
    columns = [
        {"name": "task", "label": "task", "field": "task", "sortOrder": "ad"},
        {"name": "caveats", "label": "caveats", "field": "caveats_tree"},
        {"name": "exceptions", "label": "exceptions", "field": "exceptions_tree"},
    ]
    columns.extend({"name": c, "label": c, "headerClasses": "", "classes": ""} for c in hidden_columns)

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

    return table


def provenance_report_plaintext(provenance: ui.table) -> None:
    """Render a table in plaintext format"""
    hidden_columns = {"caveats_tree", "exceptions_tree"}

    columns: list[str] = [c["label"] for c in provenance.columns if c["label"] not in hidden_columns]
    rows = [tuple(r.get(c, 0) for c in columns) for r in provenance.rows]
    plaintext_rows: list[list[str]] = []
    for row in rows:
        row_md: list[str] = []
        for field in row:
            _field = ""
            match field:
                case []:
                    _field += " "
                case [{"token": _, "code": _, "count": _}, *_]:
                    _field += ",".join(f"{c['token']}{c['code']}{c['count']}" for c in field)
                case [{"Exception": _, "Successes": _, "Failures": _}, *_]:
                    for exc in field:
                        _field += f"\u2022 {exc['Exception']}\n"
                        _field += f"  \u2022 Successes: {exc['Successes']}\n"
                        _field += f"  \u2022 Failures: {exc['Failures']}\n"
                case _:
                    _field += str(field)

            row_md.append(_field)
        plaintext_rows.append(row_md)

    table = Table(box=box.SQUARE, show_lines=True)
    for column in columns:
        table.add_column(column.title(), no_wrap=True)
    for plaintext_row in plaintext_rows:
        table.add_row(*plaintext_row)

    with (
        Console(force_terminal=True, color_system=None, width=10_000) as console,
        console.capture() as capture,
    ):
        console.print(table)

    plaintext = capture.get()
    ui.code(plaintext, language=None)


def provenance_report_markdown(provenance: ui.table, *, render_markdown: bool = True) -> None:
    """Render a table in markdown table format"""
    hidden_columns = {"caveats_tree", "exceptions_tree"}
    columns = [c["label"] for c in provenance.columns if c["label"] not in hidden_columns]
    rows = [tuple(r.get(c, 0) for c in columns) for r in provenance.rows]

    markdown_header = "".join([f"| {c.title()} " for c in columns]) + "|\n"
    markdown_separator = "|---" * len(columns) + "|\n"
    markdown_rows = ""
    for row in rows:
        markdown_rows += "|"
        row_md: list[str] = []
        for field in row:
            _field = ""
            match field:
                case []:
                    _field += ""
                case [{"token": _, "code": _, "count": _}, *_]:
                    _field += ",".join(f"{c['token']}{c['code']}{c['count']}" for c in field)
                case [{"Exception": _, "Successes": _, "Failures": _}, *_]:
                    _field = "<ul>"
                    for exc in field:
                        _field += "<li>"
                        _field += f"{exc['Exception']}<ul>"
                        _field += f"<li>Successes: {exc['Successes']}</li>"
                        _field += f"<li>Failures: {exc['Failures']}</li>"
                        _field += "</ul></li>"
                    _field += "</uv>"
                case _:
                    _field += str(field)

            row_md.append(_field)
        markdown_rows += "|".join(f"{f}" for f in row_md)
        markdown_rows += "|\n"

    if render_markdown:
        ui.markdown(
            markdown_header + markdown_separator + markdown_rows,
            extras=["tables"],
        )
    else:
        ui.code(markdown_header + markdown_separator + markdown_rows, language="markdown")
