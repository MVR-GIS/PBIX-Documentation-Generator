"""
================================================================================
Power BI Documentation Extractor
================================================================================
Author: Ryan Benac (USACE Rock Island District)
Date: July 1, 2026
Version: 1.2

Description:
    This script extracts comprehensive documentation from Power BI (.pbix) files
    and exports it to structured JSON files for easier review, auditing, and
    understanding of Power BI data models.

Output Files:
    - M_Queries.json: All M queries and parameters with their expressions
    - Tables.json: Table structures with columns, measures, and calculations
    - Model.json: Relationships, storage modes, and partition details
    - Connections.json: Data source connections and endpoints
    - Summary.json: Overall statistics and complexity metrics
    - Model_Diagram.mmd: Mermaid diagram of table relationships
    - Query_Dependencies.mmd: Mermaid diagram of query dependencies

Usage:
    1. Set pbix_path to a single .pbix file or a folder path
    2. Run the script
    3. Documentation will be saved to the output_dir location

Requirements:
    - pbixray library
    - pandas
    - Python 3.7+
================================================================================
"""

import json
import os
import re
from pathlib import Path
from datetime import datetime
from pbixray import PBIXRay

# ============================================================================
# CONFIGURATION
# ============================================================================

# Set this to either:
# 1. A single .pbix file path
# 2. A folder path (will recursively scan for all .pbix files)
pbix_path = r"\\mvrdfs.mvr.ds.usace.army.mil\EGIS\Work\Office\EC\EC\General Power BI Dashboards\MVR Systems and Knowledge Support.pbix"

# Output directory where documentation will be saved
output_base_dir = Path(r"C:\Workspace\GIT\PBIX-Documentation-Generator\DashboardDocs")

# ============================================================================
# FUNCTIONS
# ============================================================================

def extract_source_info_from_line(source_line):
    """Extract source information from a Source = line"""
    
    # Pattern: Source = FunctionName.Method("endpoint"
    # Using .+? for non-greedy match of any character
    match = re.search(r'Source\s*=\s*([A-Za-z0-9_]+\.[A-Za-z0-9_]+)\s*\(\s*"(.+?)"', source_line)
    
    if match:
        return {
            "source_function": match.group(1),
            "endpoint": match.group(2)
        }
    
    # Check for Table.Combine
    if 'Table.Combine' in source_line:
        return {
            "source_function": "Table.Combine",
            "endpoint": ""
        }
    
    # Check for DateTime functions
    if 'DateTime.' in source_line:
        return {
            "source_function": "DateTime (Calculated)",
            "endpoint": ""
        }
    
    return None

def sanitize_mermaid_id(name):
    """Sanitize a name to be used as a Mermaid node ID"""
    if not name:
        return 'EmptyNode'
    
    # Convert to string and strip whitespace
    name_str = str(name).strip()
    
    if not name_str:
        return 'EmptyNode'
    
    # Method: Simple character-by-character replacement
    result = []
    for char in name_str:
        if char.isalnum() or char == '_':
            result.append(char)
        else:
            result.append('_')
    
    sanitized = ''.join(result)
    
    # Remove consecutive underscores
    while '__' in sanitized:
        sanitized = sanitized.replace('__', '_')
    
    # Remove leading and trailing underscores
    sanitized = sanitized.strip('_')
    
    # Check if empty
    if not sanitized:
        return 'Node_' + str(abs(hash(name_str)))[:8]
    
    # Ensure doesn't start with number
    if sanitized[0].isdigit():
        sanitized = 'N_' + sanitized
    
    return sanitized

def find_query_references(expression, all_query_names):
    """Find all references to other queries in an M expression"""
    if not expression:
        return []
    
    # Convert to string if not already
    expression = str(expression)
    
    references = set()
    
    # Pattern 1: #"Query Name" - most common in Power Query
    refs = re.findall(r'#"([\^"]+)"', expression)
    references.update(refs)
    
    # Pattern 2: Source = QueryName (without quotes, for simple references)
    # This catches cases like: Source = SomeQuery
    source_refs = re.findall(r'Source\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\s*[,\n]', expression)
    references.update(source_refs)
    
    # Pattern 3: Table.NestedJoin or Table.Join references
    # Example: Table.NestedJoin(Query1, {"Col"}, Query2, {"Col"})
    nested_refs = re.findall(r'Table\.(?:NestedJoin|Join)\s*\([\^,]+,\s*[\^,]+,\s*#?"?([A-Za-z_][A-Za-z0-9_]*)"?', expression)
    references.update(nested_refs)
    
    # Pattern 4: Check if any query name appears as a whole word in the expression
    # This is more aggressive but catches edge cases
    for query_name in all_query_names:
        # Skip very short names to avoid false positives
        if len(query_name) < 3:
            continue
        
        # Escape special regex characters in query name
        escaped_name = re.escape(query_name)
        
        # Look for the query name as a whole word
        if re.search(r'\b' + escaped_name + r'\b', expression):
            references.add(query_name)
    
    return list(references)

def create_model_diagram(relationships, table_details, output_path):
    """Create a Mermaid diagram of the data model relationships"""
    
    mermaid_lines = [
        "---",
        "title: Power BI Data Model - Table Relationships",
        "---",
        "erDiagram",
        ""
    ]
    
    # Track which tables we've seen
    tables_in_relationships = set()
    
    # Add relationships
    for rel in relationships:
        from_table = rel['from_table']
        to_table = rel['to_table']
        
        # Skip system tables
        if from_table.startswith('LocalDateTable_') or to_table.startswith('LocalDateTable_'):
            continue
        if from_table.startswith('DateTableTemplate_') or to_table.startswith('DateTableTemplate_'):
            continue
        
        tables_in_relationships.add(from_table)
        tables_in_relationships.add(to_table)
        
        # Determine relationship symbol based on cardinality
        cardinality = rel.get('cardinality', '')
        if '1:1' in cardinality or cardinality == '1':
            symbol = '||--||'
        elif 'Many' in cardinality or '*' in cardinality:
            # Determine direction
            if cardinality.startswith('1') or cardinality.startswith('One'):
                symbol = '||--o{'  # One to many
            else:
                symbol = '}o--o{'  # Many to many
        else:
            symbol = '||--||'  # Default to one-to-one
        
        # Add active/inactive indicator
        active_indicator = "" if rel.get('is_active', True) else " (inactive)"
        
        # Sanitize table names for Mermaid
        from_id = sanitize_mermaid_id(from_table)
        to_id = sanitize_mermaid_id(to_table)
        
        # Escape special characters in label
        label = f"{rel['from_column']} to {rel['to_column']}{active_indicator}"
        label = label.replace('"', '&quot;')
        
        # Add relationship with label
        mermaid_lines.append(f'    {from_id} {symbol} {to_id} : "{label}"')
    
    # Add table attributes for tables in relationships
    if tables_in_relationships:
        mermaid_lines.append("")
        mermaid_lines.append("    %% Table Details")
        
        for table_name in sorted(tables_in_relationships):
            table_id = sanitize_mermaid_id(table_name)
            storage_mode = ""
            
            if table_name in table_details:
                storage_mode = f" [{table_details[table_name]['storage_mode']}]"
            
            # Escape special characters in display name
            display_name = str(table_name).replace('"', '&quot;')
            
            mermaid_lines.append(f'    {table_id}["{display_name}{storage_mode}"]')
    
    # Write to file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(mermaid_lines))

def create_query_dependencies_diagram(m_queries_data, output_path):
    """Create a Mermaid diagram showing query dependencies"""
    
    print("\n" + "="*80)
    print("Creating Query Dependencies Diagram")
    print("="*80)
    
    mermaid_lines = [
        "---",
        "title: Power BI Query Dependencies",
        "---",
        "graph TD",
        ""
    ]
    
    # Track dependencies
    dependencies = {}
    all_queries = set()
    
    # First, collect all query names
    for query_name in m_queries_data.keys():
        all_queries.add(query_name)
    
    print(f"\nTotal queries to analyze: {len(all_queries)}")
    print(f"Query names: {sorted(all_queries)}\n")
    
    # Analyze each query for references to other queries
    for query_name, query_info in m_queries_data.items():
        expression = query_info.get('expression', '')
        
        # Convert to string and check if valid
        if expression is None:
            expression = ''
        else:
            expression = str(expression)
        
        print(f"\n--- Analyzing: {query_name} ---")
        print(f"  Type: {query_info.get('type')}")
        print(f"  Expression length: {len(expression)}")
        
        if not expression or len(expression) < 10:
            print(f"  Skipping - expression too short or empty")
            continue
        
        # Show first 200 characters
        print(f"  Expression preview:\n  {expression[:200]}")
        
        # Find all references using the comprehensive function
        referenced_queries = find_query_references(expression, all_queries)
        
        # Remove self-references
        valid_references = [ref for ref in referenced_queries if ref != query_name and ref in all_queries]
        
        if valid_references:
            dependencies[query_name] = valid_references
            print(f"  ✓ Found dependencies: {valid_references}")
        else:
            print(f"  No dependencies found")
    
    print(f"\n{'='*80}")
    print(f"Dependency Analysis Complete")
    print(f"  Queries with dependencies: {len(dependencies)}")
    print(f"  Total dependency links: {sum(len(refs) for refs in dependencies.values())}")
    print(f"{'='*80}\n")
    
    # Add nodes with styling based on type
    mermaid_lines.append("    %% Query Nodes")
    
    for query_name in sorted(all_queries):
        if not query_name or not str(query_name).strip():
            continue
        
        query_id = sanitize_mermaid_id(query_name)
        
        if not query_id:
            query_id = 'Unknown_' + str(abs(hash(query_name)))[:8]
        
        query_info = m_queries_data.get(query_name, {})
        query_type = query_info.get('type', 'query')
        enable_load = query_info.get('enable_load', False)
        
        # Escape special characters in display name
        display_name = str(query_name).replace('"', '&quot;')
        
        # Determine node style
        if query_type == 'parameter':
            mermaid_lines.append(f'    {query_id}[("{display_name}<br/>[Parameter]")]')
            mermaid_lines.append(f'    style {query_id} fill:#e1f5ff,stroke:#01579b')
        elif not enable_load:
            mermaid_lines.append(f'    {query_id}["{display_name}<br/>(Load Disabled)"]')
            mermaid_lines.append(f'    style {query_id} fill:#fff3e0,stroke:#e65100')
        else:
            mermaid_lines.append(f'    {query_id}["{display_name}"]')
            mermaid_lines.append(f'    style {query_id} fill:#e8f5e9,stroke:#2e7d32')
    
    # Add dependencies
    if dependencies:
        mermaid_lines.append("")
        mermaid_lines.append("    %% Dependencies")
        
        for query_name, referenced in dependencies.items():
            query_id = sanitize_mermaid_id(query_name)
            
            for ref_query in referenced:
                if ref_query in all_queries:
                    ref_id = sanitize_mermaid_id(ref_query)
                    mermaid_lines.append(f'    {ref_id} --> {query_id}')
    else:
        mermaid_lines.append("")
        mermaid_lines.append("    %% No dependencies found")
        print("WARNING: No dependencies detected in any queries!")
    
    # Add legend
    mermaid_lines.append("")
    mermaid_lines.append("    %% Legend")
    mermaid_lines.append('    Legend["<b>Legend</b><br/>Green: Loaded Query<br/>Orange: Not Loaded<br/>Blue: Parameter"]')
    mermaid_lines.append('    style Legend fill:#f5f5f5,stroke:#666')
    
    # Write to file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(mermaid_lines))
    
    print(f"Query Dependencies diagram saved to: {output_path}\n")

def process_pbix_file(pbix_file_path, output_base_dir):
    """Process a single PBIX file and extract documentation"""
    
    pbix_file_path = Path(pbix_file_path)
    pbix_filename = pbix_file_path.stem
    
    print(f"\n{'='*80}")
    print(f"Processing: {pbix_filename}")
    print(f"{'='*80}")
    
    try:
        # parse the PBIX file
        model = PBIXRay(str(pbix_file_path))
        
        # Create the output directory structure
        output_dir = output_base_dir / pbix_filename
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Get M queries using power_query (it's a DataFrame)
        m_queries_df = model.power_query
        
        print(f"\n--- Power Query DataFrame Info ---")
        print(f"Number of queries: {len(m_queries_df)}")
        print(f"Columns: {list(m_queries_df.columns)}")
        
        # Get M parameters to add to M queries
        m_params_df = model.m_parameters
        
        # Get list of loaded tables to determine Enable Load status
        loaded_tables = list(model.tables)
        
        # Create M_Queries.json - include both queries and parameters
        m_queries_data = {}
        
        # Add regular M queries
        print(f"\n--- Capturing M Queries ---")
        for index, row in m_queries_df.iterrows():
            table_name = row['TableName']
            m_code = row['Expression']
            
            # Debug output
            print(f"\nQuery: {table_name}")
            print(f"  Expression type: {type(m_code)}")
            print(f"  Expression length: {len(str(m_code)) if m_code is not None else 0}")
            
            m_queries_data[table_name] = {
                "type": "query",
                "expression": str(m_code) if m_code is not None else "",
                "enable_load": table_name in loaded_tables
            }
        
        # Add M parameters
        if not m_params_df.empty:
            print(f"\n--- Capturing M Parameters ---")
            for index, param_row in m_params_df.iterrows():
                param_name = str(param_row.get('ParameterName', ''))
                expression = str(param_row.get('Expression', '')) if param_row.get('Expression') is not None else ''
                
                print(f"\nParameter: {param_name}")
                print(f"  Expression length: {len(expression)}")
                
                m_queries_data[param_name] = {
                    "type": "parameter",
                    "expression": expression,
                    "description": str(param_row.get('Description', '')) if param_row.get('Description') and str(param_row.get('Description')) != 'None' else '',
                    "modified_time": str(param_row.get('ModifiedTime', '')),
                    "enable_load": param_name in loaded_tables
                }
        
        # Write M_Queries.json
        m_queries_json_path = output_dir / "M_Queries.json"
        with open(m_queries_json_path, 'w', encoding='utf-8') as f:
            json.dump(m_queries_data, f, indent=2, ensure_ascii=False)
        
        # Now create the Tables.json file
        tables_data = {}
        
        # Get all table names from regular tables
        table_names = list(model.tables)
        
        # Add DAX calculated tables to the list
        dax_tables_df = model.dax_tables
        if not dax_tables_df.empty:
            for index, table_row in dax_tables_df.iterrows():
                table_name = table_row.get('TableName', '')
                if table_name and table_name not in table_names:
                    table_names.append(table_name)
        
        # Get hidden status from tmschema_tables
        tables_schema_df = model.tmschema_tables
        hidden_tables = {}
        if hasattr(tables_schema_df, 'columns') and 'Name' in tables_schema_df.columns and 'IsHidden' in tables_schema_df.columns:
            for index, row in tables_schema_df.iterrows():
                table_name = row['Name']
                hidden_tables[table_name] = bool(row['IsHidden'])
        
        # Initialize tables_data with all table names
        for table_name in table_names:
            # Check if it's a system-generated table (LocalDateTable or DateTableTemplate)
            is_system_table = table_name.startswith('LocalDateTable_') or table_name.startswith('DateTableTemplate_')
            
            tables_data[table_name] = {
                "is_calculated_table": False,
                "table_expression": "",
                "is_hidden": hidden_tables.get(table_name, False),
                "is_system_generated": is_system_table,
                "columns": [],
                "measures": []
            }
        
        # Mark calculated tables and add their expressions
        if not dax_tables_df.empty:
            for index, table_row in dax_tables_df.iterrows():
                table_name = table_row.get('TableName', '')
                expression = table_row.get('Expression', '')
                
                if table_name and table_name in tables_data:
                    if expression and str(expression).strip() and str(expression) != 'nan':
                        tables_data[table_name]["is_calculated_table"] = True
                        tables_data[table_name]["table_expression"] = str(expression)
        
        # Get ALL columns information from tmschema_columns
        all_columns_df = model.tmschema_columns
        
        for index, col_row in all_columns_df.iterrows():
            table_name = col_row['TableName']
            
            if table_name in tables_data:
                column_info = {
                    "name": col_row['Name'],
                    "data_type": str(col_row.get('DataType', '')),
                    "description": str(col_row.get('Description', '')) if col_row.get('Description') else '',
                    "is_hidden": bool(col_row.get('IsHidden', False)),
                    "calculation_type": "none"
                }
                
                # Check if it's a DAX calculated column
                expression = col_row.get('Expression')
                if expression and str(expression).strip() and str(expression) != 'nan':
                    column_info["dax_formula"] = str(expression)
                    column_info["calculation_type"] = "dax"
                
                tables_data[table_name]["columns"].append(column_info)
        
        # Get measures information
        measures_df = model.dax_measures
        
        if not measures_df.empty:
            for index, measure_row in measures_df.iterrows():
                table_name = measure_row['TableName']
                
                if table_name in tables_data:
                    measure_info = {
                        "name": measure_row['Name'],
                        "expression": str(measure_row['Expression']),
                        "description": str(measure_row.get('Description', '')) if measure_row.get('Description') and str(measure_row.get('Description')) != 'None' else '',
                        "display_folder": str(measure_row.get('DisplayFolder', '')) if measure_row.get('DisplayFolder') and str(measure_row.get('DisplayFolder')) != 'None' else ''
                    }
                    
                    tables_data[table_name]["measures"].append(measure_info)
        
        # Write Tables.json to the parent pbix folder
        tables_json_path = output_dir / "Tables.json"
        with open(tables_json_path, 'w', encoding='utf-8') as f:
            json.dump(tables_data, f, indent=2, ensure_ascii=False)
        
        # Create Model.json with relationships and storage modes
        model_data = {
            "relationships": []
        }
        
        # Get relationships
        relationships_df = model.relationships
        
        for index, rel_row in relationships_df.iterrows():
            relationship_info = {
                "from_table": str(rel_row.get('FromTableName', '')),
                "from_column": str(rel_row.get('FromColumnName', '')),
                "to_table": str(rel_row.get('ToTableName', '')),
                "to_column": str(rel_row.get('ToColumnName', '')),
                "is_active": bool(rel_row.get('IsActive', True)),
                "cross_filtering_behavior": str(rel_row.get('CrossFilteringBehavior', '')),
                "cardinality": str(rel_row.get('Cardinality', '')),
                "security_filtering_behavior": str(rel_row.get('SecurityFilteringBehavior', '')),
                "from_key_count": str(rel_row.get('FromKeyCount', '')),
                "to_key_count": str(rel_row.get('ToKeyCount', '')),
                "rely_on_referential_integrity": bool(int(rel_row.get('RelyOnReferentialIntegrity', 0)))
            }
            
            model_data["relationships"].append(relationship_info)
        
        # Add storage mode and partition information
        table_details = {}
        partitions_df = model.tmschema_partitions
        
        # Map mode values to readable names
        mode_mapping = {
            0: "Import",
            1: "DirectQuery", 
            2: "Dual"
        }
        
        # Map state values
        state_mapping = {
            0: "Ready",
            1: "Processing",
            2: "Error"
        }
        
        # Map type values
        type_mapping = {
            1: "Query",
            2: "Calculated",
            3: "None",
            4: "Entity"
        }
        
        for index, partition_row in partitions_df.iterrows():
            table_name = partition_row['TableName']
            
            # Skip system-generated tables
            if table_name.startswith('LocalDateTable_') or table_name.startswith('DateTableTemplate_'):
                continue
            
            # Skip hierarchies (they start with H$)
            if table_name.startswith('H$'):
                continue
            
            # Skip if already processed (only take first partition per table)
            if table_name in table_details:
                continue
            
            mode_value = partition_row.get('Mode', 0)
            state_value = partition_row.get('State', 0)
            type_value = partition_row.get('Type', 1)
            
            table_details[table_name] = {
                "storage_mode": mode_mapping.get(mode_value, f"Unknown ({mode_value})"),
                "partition_type": type_mapping.get(type_value, f"Unknown ({type_value})"),
                "state": state_mapping.get(state_value, f"Unknown ({state_value})"),
                "modified_time": str(partition_row.get('ModifiedTime', '')),
                "refreshed_time": str(partition_row.get('RefreshedTime', '')),
                "data_source_id": str(partition_row.get('DataSourceID', '')) if partition_row.get('DataSourceID') else None
            }
        
        model_data["table_details"] = table_details
        
        # Add storage mode summary
        storage_mode_summary = {}
        for details in table_details.values():
            mode = details["storage_mode"]
            storage_mode_summary[mode] = storage_mode_summary.get(mode, 0) + 1
        
        model_data["storage_mode_summary"] = storage_mode_summary
        
        # Write Model.json
        model_json_path = output_dir / "Model.json"
        with open(model_json_path, 'w', encoding='utf-8') as f:
            json.dump(model_data, f, indent=2, ensure_ascii=False)
        
        # Create Connections.json - Extract from Source = lines
        connections_data = {}
        
        # Use M queries for source detection
        for index, row in m_queries_df.iterrows():
            table_name = row['TableName']
            query_text = row['Expression']
            
            if query_text is None:
                continue
            
            query_text = str(query_text)
            
            # Find the Source = line
            lines = query_text.split('\n')
            for line in lines:
                if line.strip().startswith('Source') and '=' in line:
                    source_info = extract_source_info_from_line(line)
                    
                    if source_info and source_info["source_function"] not in ["Table.Combine", "DateTime (Calculated)"]:
                        conn_key = f"{source_info['source_function']}::{source_info['endpoint']}"
                        
                        if conn_key not in connections_data:
                            connections_data[conn_key] = {
                                "source_function": source_info["source_function"],
                                "endpoint": source_info["endpoint"],
                                "tables_using": []
                            }
                        
                        connections_data[conn_key]["tables_using"].append(table_name)
                    break  # Only process the first Source = line
        
        # Also check M parameters for connections
        if not m_params_df.empty:
            for index, param_row in m_params_df.iterrows():
                param_name = str(param_row.get('ParameterName', ''))
                query_text = str(param_row.get('Expression', ''))
                
                if not query_text:
                    continue
                
                lines = query_text.split('\n')
                for line in lines:
                    if line.strip().startswith('Source') and '=' in line:
                        source_info = extract_source_info_from_line(line)
                        
                        if source_info and source_info["source_function"] not in ["Table.Combine", "DateTime (Calculated)"]:
                            conn_key = f"{source_info['source_function']}::{source_info['endpoint']}"
                            
                            if conn_key not in connections_data:
                                connections_data[conn_key] = {
                                    "source_function": source_info["source_function"],
                                    "endpoint": source_info["endpoint"],
                                    "tables_using": []
                                }
                            
                            connections_data[conn_key]["tables_using"].append(f"[Parameter] {param_name}")
                        break
        
        # Write Connections.json
        connections_json_path = output_dir / "Connections.json"
        with open(connections_json_path, 'w', encoding='utf-8') as f:
            json.dump(connections_data, f, indent=2, ensure_ascii=False)
        
        # Create Summary.json with comprehensive statistics
        summary_data = {
            "report_info": {
                "report_name": pbix_filename,
                "file_path": str(pbix_file_path),
                "file_size_mb": round(pbix_file_path.stat().st_size / (1024 * 1024), 2) if pbix_file_path.exists() else 0,
                "documentation_generated": datetime.now().isoformat(),
                "author": "Ryan Benac (USACE Rock Island District)",
                "pbixray_version": "Latest"
            },
            "tables": {
                "total_tables": len(table_names),
                "user_generated_tables": len([t for t in tables_data.values() if not t["is_system_generated"]]),
                "system_generated_tables": len([t for t in tables_data.values() if t["is_system_generated"]]),
                "calculated_tables": len([t for t in tables_data.values() if t["is_calculated_table"]]),
                "hidden_tables": len([t for t in tables_data.values() if t["is_hidden"]]),
                "visible_tables": len([t for t in tables_data.values() if not t["is_hidden"]])
            },
            "columns": {
                "total_columns": sum(len(t["columns"]) for t in tables_data.values()),
                "calculated_columns": sum(len([c for c in t["columns"] if c["calculation_type"] == "dax"]) for t in tables_data.values()),
                "regular_columns": sum(len([c for c in t["columns"] if c["calculation_type"] == "none"]) for t in tables_data.values()),
                "hidden_columns": sum(len([c for c in t["columns"] if c["is_hidden"]]) for t in tables_data.values()),
                "columns_with_descriptions": sum(len([c for c in t["columns"] if c["description"]]) for t in tables_data.values())
            },
            "measures": {
                "total_measures": sum(len(t["measures"]) for t in tables_data.values()),
                "measures_with_descriptions": sum(len([m for m in t["measures"] if m["description"]]) for t in tables_data.values()),
                "measures_in_display_folders": sum(len([m for m in t["measures"] if m["display_folder"]]) for t in tables_data.values())
            },
            "relationships": {
                "total_relationships": len(model_data["relationships"]),
                "active_relationships": len([r for r in model_data["relationships"] if r["is_active"]]),
                "inactive_relationships": len([r for r in model_data["relationships"] if not r["is_active"]]),
                "bidirectional_relationships": len([r for r in model_data["relationships"] if r["cross_filtering_behavior"] == "Both"]),
                "single_direction_relationships": len([r for r in model_data["relationships"] if r["cross_filtering_behavior"] != "Both"])
            },
            "queries": {
                "total_m_queries": len(m_queries_df),
                "queries_with_load_enabled": len([q for q in m_queries_data.values() if q.get("enable_load", False) and q["type"] == "query"]),
                "queries_with_load_disabled": len([q for q in m_queries_data.values() if not q.get("enable_load", False) and q["type"] == "query"]),
                "m_parameters": len(m_params_df) if not m_params_df.empty else 0
            },
            "connections": {
                "total_unique_connections": len(connections_data),
                "connection_types": {}
            },
            "storage_modes": storage_mode_summary,
            "complexity_indicators": {
                "has_calculated_tables": any(t["is_calculated_table"] for t in tables_data.values()),
                "has_calculated_columns": sum(len([c for c in t["columns"] if c["calculation_type"] == "dax"]) for t in tables_data.values()) > 0,
                "has_bidirectional_relationships": any(r["cross_filtering_behavior"] == "Both" for r in model_data["relationships"]),
                "has_inactive_relationships": any(not r["is_active"] for r in model_data["relationships"]),
                "has_directquery_tables": "DirectQuery" in storage_mode_summary,
                "has_dual_tables": "Dual" in storage_mode_summary,
                "average_columns_per_table": round(sum(len(t["columns"]) for t in tables_data.values()) / len(table_names), 2) if len(table_names) > 0 else 0,
                "average_measures_per_table": round(sum(len(t["measures"]) for t in tables_data.values()) / len(table_names), 2) if len(table_names) > 0 else 0
            },
            "documentation_quality": {
                "tables_with_descriptions": 0,
                "columns_with_descriptions_percentage": round((sum(len([c for c in t["columns"] if c["description"]]) for t in tables_data.values()) / sum(len(t["columns"]) for t in tables_data.values()) * 100), 2) if sum(len(t["columns"]) for t in tables_data.values()) > 0 else 0,
                "measures_with_descriptions_percentage": round((sum(len([m for m in t["measures"] if m["description"]]) for t in tables_data.values()) / sum(len(t["measures"]) for t in tables_data.values()) * 100), 2) if sum(len(t["measures"]) for t in tables_data.values()) > 0 else 0
            }
        }
        
        # Count connection types
        for conn in connections_data.values():
            source_type = conn["source_function"].split('.')[0]
            if source_type in summary_data["connections"]["connection_types"]:
                summary_data["connections"]["connection_types"][source_type] += 1
            else:
                summary_data["connections"]["connection_types"][source_type] = 1
        
        # Write Summary.json
        summary_json_path = output_dir / "Summary.json"
        with open(summary_json_path, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, indent=2, ensure_ascii=False)
        
        # Create Mermaid diagrams
        print(f"\n  Generating Mermaid diagrams...")
        
        # Model diagram (relationships)
        model_diagram_path = output_dir / "Model_Diagram.mmd"
        create_model_diagram(model_data["relationships"], table_details, model_diagram_path)
        
        # Query dependencies diagram
        query_diagram_path = output_dir / "Query_Dependencies.mmd"
        create_query_dependencies_diagram(m_queries_data, query_diagram_path)
        
        # Print summary
        print(f"\n✓ SUCCESS - Documentation extracted to: {output_dir}")
        print(f"\n  Files Created:")
        print(f"  ├─ M_Queries.json")
        print(f"  ├─ Tables.json")
        print(f"  ├─ Model.json")
        print(f"  ├─ Connections.json")
        print(f"  ├─ Summary.json")
        print(f"  ├─ Model_Diagram.mmd")
        print(f"  └─ Query_Dependencies.mmd")
        print(f"\n  Summary Statistics:")
        print(f"  ├─ Tables: {summary_data['tables']['total_tables']} ({summary_data['tables']['user_generated_tables']} user-generated)")
        print(f"  ├─ Columns: {summary_data['columns']['total_columns']}")
        print(f"  ├─ Measures: {summary_data['measures']['total_measures']}")
        print(f"  ├─ Relationships: {summary_data['relationships']['total_relationships']}")
        print(f"  ├─ Connections: {summary_data['connections']['total_unique_connections']}")
        print(f"  └─ Storage Modes: {storage_mode_summary}")
        
        return True, summary_data
        
    except Exception as e:
        print(f"\n✗ FAILED - Error processing file: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, None

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*80)
    print("Power BI Documentation Extractor")
    print("Author: Ryan Benac (USACE Rock Island District)")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    pbix_path = Path(pbix_path)
    
    # Determine if path is a file or directory
    if pbix_path.is_file() and pbix_path.suffix.lower() == '.pbix':
        # Single file processing
        print(f"\nMode: Single File")
        print(f"File: {pbix_path.name}")
        
        success, summary = process_pbix_file(pbix_path, output_base_dir)
        
        if success:
            print(f"\n{'='*80}")
            print("✓ Processing Complete")
            print(f"{'='*80}\n")
        else:
            print(f"\n{'='*80}")
            print("✗ Processing Failed")
            print(f"{'='*80}\n")
    
    elif pbix_path.is_dir():
        # Directory processing - recursive scan
        print(f"\nMode: Recursive Directory Scan")
        print(f"Directory: {pbix_path}")
        
        # Find all .pbix files recursively
        pbix_files = list(pbix_path.rglob("*.pbix"))
        
        if not pbix_files:
            print(f"\n✗ No .pbix files found in {pbix_path}")
        else:
            print(f"\nFound {len(pbix_files)} .pbix file(s)")
            
            successful = 0
            failed = 0
            
            for pbix_file in pbix_files:
                success, summary = process_pbix_file(pbix_file, output_base_dir)
                
                if success:
                    successful += 1
                else:
                    failed += 1
            
            # Final summary
            print(f"\n{'='*80}")
            print("Processing Complete")
            print(f"{'='*80}")
            print(f"Total Files: {len(pbix_files)}")
            print(f"✓ Successful: {successful}")
            print(f"✗ Failed: {failed}")
            print(f"{'='*80}\n")
    
    else:
        print(f"\n✗ ERROR: Invalid path - must be a .pbix file or directory")
        print(f"Path provided: {pbix_path}\n")