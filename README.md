# Power System Word Report Builder

This app builds a Word report from one or more CSV files, with optional graphs and an optional Word template. It is designed to help assemble power-system analysis tables and plots into a document that resembles engineering report formats.

## Setup (uv)

```bash
uv sync
```

## Run

```bash
uv run python main.py
```

## Workflow

1. Add one or more CSV files.
2. (Optional) choose a Word template (`.docx`) to append the tables/graphs into.
3. Choose the output Word document path.
4. Select a graph type or disable graphs.
5. Generate the report.

Graphs are created from numeric columns only. Line and bar charts plot all numeric columns; scatter uses the first two numeric columns. If a CSV has no numeric data, the app skips the graph for that dataset.
