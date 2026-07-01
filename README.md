# PBIX Documentation Generator

A small Python utility to extract structured documentation from Power BI `.pbix` files for review, auditing, and developer onboarding.

## Purpose

This repository is designed to make Power BI model metadata easier to inspect and understand. It parses `.pbix` files and exports:

- Power Query (`M`) queries and parameters
- Table and column definitions
- DAX measures and calculated tables
- Model relationships and storage modes
- Data source connection metadata
- Summary metrics and documentation quality indicators
- Mermaid diagrams for model relationships and query dependencies

The output is intended to support reviews, audits, machine-readable analysis, and faster handoffs between developers.

## What the code does

The main script `ExtractFromPBIXMetadata.py` uses the `pbixray` library to read a Power BI file and export documentation into a folder structure.

It performs these key steps:

1. Loads a `.pbix` file or recursively scans a directory for `.pbix` files.
2. Extracts Power Query expressions and parameter definitions.
3. Extracts tables, columns, hidden state, calculated columns, and measures.
4. Extracts relationships, partition/storage mode details, and connection sources.
5. Builds a summary of counts and complexity indicators.
6. Generates Mermaid diagrams for table relationships and query dependencies.

## Notes

- The script currently uses hard-coded configuration values in `ExtractFromPBIXMetadata.py`.
- It supports both single-file and recursive directory processing.
- Mermaid output can be rendered with any Mermaid-compatible viewer.
- Connection extraction is based on `Source =` lines in M query text and may not capture every possible source expression.
- Processing takes on average 1 second/file size MB

## Getting started

1. Install Python 3.7 or newer.
2. Install repository dependencies.
3. Configure `pbix_path` and `output_base_dir` inside `ExtractFromPBIXMetadata.py`.
4. Run the script.

Example:

```powershell
& c:\Users\<you>\.venv\Scripts\python.exe ExtractFromPBIXMetadata.py
```

## Dependencies

The script depends on:

- Python 3.7+
- `pbixray`
- `pandas`

Install dependencies with pip:

```powershell
python -m pip install pbixray pandas
```

## Configuration

Open `ExtractFromPBIXMetadata.py` and set:

- `pbix_path` to a single `.pbix` file or a directory containing `.pbix` files
- `output_base_dir` to the folder where extracted documentation should be written

The script writes one output folder per processed PBIX file.

## Output files

For each processed report, the script generates:

- `M_Queries.json` — Power Query expressions and parameters
- `Tables.json` — table definitions, columns, measures, and hidden status
- `Model.json` — relationships, table storage modes, and partition details
- `Connections.json` — extracted data source connection endpoints
- `Summary.json` — metadata counts, complexity indicators, and documentation quality
- `Model_Diagram.md` — Mermaid ER diagram of table relationships
- `Query_Dependencies.md` — Mermaid dependency graph for Power Query queries
