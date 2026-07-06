"""
================================================================================
Power BI Documentation Extractor
================================================================================
Author: Ryan Benac (USACE Rock Island District)
Date: July 1, 2026
Version: 1.6

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
    - Model_Diagram.md: Mermaid diagram of table relationships (Markdown format)
    - Query_Dependencies.md: Mermaid diagram of query dependencies (Markdown format)
    - Live_Connection_Info.json: For live connection reports only

Usage:
    1. Set pbix_path to a single .pbix file or a folder path
    2. Run the script
    3. Documentation will be saved to the output_dir location
    4. Open .md files in VS Code and use preview (Ctrl+K V)

Requirements:
    - pbixray library
    - pandas
    - Python 3.7+
    - VS Code with "Markdown Preview Mermaid Support" extension (for viewing)
================================================================================
"""

import json
import os
import re
import time
from pathlib import Path
from datetime import datetime
from pbixray import PBIXRay

# ============================================================================
# CONFIGURATION
# ============================================================================

# Set this to either:
# 1. A single .pbix file path
# 2. A folder path (will recursively scan for all .pbix files)
pbix_path = r"\\mvrdfs.mvr.ds.usace.army.mil\EGIS\Work\Office\EC\EC\General Power BI Dashboards"

# Output directory where documentation will be saved
output_base_dir = Path(r"C:\Workspace\GIT\PBIX-Documentation-Generator\DashboardDocs")

# ============================================================================
# FUNCTIONS
# ============================================================================

def extract_source_info_from_expression(expression):
    """Extract data source information from M expression"""
    if not expression:
        return None
    
    expression = str(expression)
    lines = expression.split('\n')
    
    for line in lines:
        line = line.strip()
        
        # Pattern 1: Source = FunctionName.Method("endpoint")
        match = re.search(r'Source\s*=\s*([A-Za-z0-9_]+\.[A-Za-z0-9_]+)\s*\(\s*"([\^"]+)"', line)
        if match:
            return {
                "type": "data_source",
                "source_function": match.group(1),
                "endpoint": match.group(2),
                "display_name": f"{match.group(1)}"
            }
        
        # Pattern 2: Source = FunctionName.Method(parameter, "endpoint")
        match = re.search(r'Source\s*=\s*([A-Za-z0-9_]+\.[A-Za-z0-9_]+)\s*\([\^,]+,\s*"([\^"]+)"', line)
        if match:
            return {
                "type": "data_source",
                "source_function": match.group(1),
                "endpoint": match.group(2),
                "display_name": f"{match.group(1)}"
            }
        
        # Pattern 3: Source = Excel.Workbook or similar without quotes
        match = re.search(r'Source\s*=\s*([A-Za-z0-9_]+\.[A-Za-z0-9_]+)\s*\(', line)
        if match:
            return {
                "type": "data_source",
                "source_function": match.group(1),
                "endpoint": "",
                "display_name": f"{match.group(1)}"
            }
        
        # Pattern 4: Web.Contents or similar
        if 'Web.Contents' in line or 'Web.Page' in line:
            return {
                "type": "data_source",
                "source_function": "Web.Contents",
                "endpoint": "",
                "display_name": "Web Source"
            }
        
        # Pattern 5: SharePoint
        if 'SharePoint.' in line:
            return {
                "type": "data_source",
                "source_function": "SharePoint",
                "endpoint": "",
                "display_name": "SharePoint"
            }
    
    return None

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
        "%%{init: {'theme':'base', 'themeVariables': { 'primaryColor':'#fff','primaryTextColor':'#000','primaryBorderColor':'#000','lineColor':'#000','secondaryColor':'#f4f4f4','tertiaryColor':'#fff','background':'#ffffff','mainBkg':'#ffffff','secondaryBkg':'#ffffff','tertiaryBkg':'#ffffff','textColor':'#000000','labelTextColor':'#000000','lineColor':'#333333','borderColor':'#333333'}}}%%",
        "erDiagram",
        "    %%{init: {'theme':'base'}}%%"
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
        
        # Add active/inactive indicator and storage mode to label
        active_indicator = "" if rel.get('is_active', True) else " [INACTIVE]"
        
        # Get storage modes for both tables
        from_storage = ""
        to_storage = ""
        if from_table in table_details:
            from_storage = table_details[from_table]['storage_mode']
        if to_table in table_details:
            to_storage = table_details[to_table]['storage_mode']
        
        # Sanitize table names for Mermaid
        from_id = sanitize_mermaid_id(from_table)
        to_id = sanitize_mermaid_id(to_table)
        
        # Create descriptive label with storage modes
        label = f"{rel['from_column']} to {rel['to_column']}{active_indicator}"
        if from_storage or to_storage:
            label += f" ({from_storage} to {to_storage})"
        label = label.replace('"', '&quot;')
        
        # Add relationship with label
        mermaid_lines.append(f'    {from_id} {symbol} {to_id} : "{label}"')
    
    # Write as Markdown file with mermaid code block
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Power BI Data Model - Table Relationships\n\n")
        f.write("```mermaid\n")
        f.write('\n'.join(mermaid_lines))
        f.write("\n```\n\n")
        f.write("## Legend\n\n")
        f.write("### Relationship Symbols\n")
        f.write("- `||--||` : One-to-One\n")
        f.write("- `||--o{` : One-to-Many\n")
        f.write("- `}o--o{` : Many-to-Many\n\n")
        f.write("### Storage Modes\n")
        f.write("- **Import**: Data cached in memory\n")
        f.write("- **DirectQuery**: Live connection to source\n")
        f.write("- **Dual**: Can use Import or DirectQuery\n\n")
        f.write("### Relationship Status\n")
        f.write("- **[INACTIVE]**: Relationship exists but not active\n")

def create_query_dependencies_diagram(m_queries_data, output_path):
    """Create a Mermaid diagram showing query dependencies including data sources"""
    
    mermaid_lines = [
        "---",
        "title: Power BI Query Dependencies - Data Sources to Queries",
        "---",
        "%%{init: {'theme':'base', 'themeVariables': { 'primaryColor':'#fff','primaryTextColor':'#000','primaryBorderColor':'#000','lineColor':'#000','secondaryColor':'#f4f4f4','tertiaryColor':'#fff','background':'#ffffff','mainBkg':'#ffffff','textColor':'#000000','labelTextColor':'#000000','edgeLabelBackground':'#ffffff'}}}%%",
        "graph LR",
        ""
    ]
    
    # Track dependencies and data sources
    dependencies = {}
    all_queries = set()
    data_sources = {}  # Maps query to its data source
    
    # First, collect all query names
    for query_name in m_queries_data.keys():
        all_queries.add(query_name)
    
    # Analyze each query for references to other queries AND data sources
    for query_name, query_info in m_queries_data.items():
        expression = query_info.get('expression', '')
        
        # Convert to string and check if valid
        if expression is None:
            expression = ''
        else:
            expression = str(expression)
        
        if not expression or len(expression) < 10:
            continue
        
        # Extract data source information
        source_info = extract_source_info_from_expression(expression)
        if source_info:
            data_sources[query_name] = source_info
        
        # Find all references using the comprehensive function
        referenced_queries = find_query_references(expression, all_queries)
        
        # Remove self-references
        valid_references = [ref for ref in referenced_queries if ref != query_name and ref in all_queries]
        
        if valid_references:
            dependencies[query_name] = valid_references
    
    # Create unique data source nodes
    unique_sources = {}
    for query_name, source_info in data_sources.items():
        source_key = source_info['source_function']
        if source_key not in unique_sources:
            unique_sources[source_key] = {
                'display_name': source_info['display_name'],
                'queries': []
            }
        unique_sources[source_key]['queries'].append(query_name)
    
    # Add data source nodes with darker colors for better contrast
    mermaid_lines.append("    %% Data Sources")
    for source_key, source_data in unique_sources.items():
        source_id = sanitize_mermaid_id(source_key)
        display_name = source_data['display_name'].replace('"', '&quot;')
        mermaid_lines.append(f'    {source_id}[("🗄️ {display_name}")]')
        mermaid_lines.append(f'    style {source_id} fill:#e1bee7,stroke:#6a1b9a,stroke-width:3px,color:#000')
    
    mermaid_lines.append("")
    
    # Add query nodes with improved styling and dark text
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
        
        # Determine node style with improved colors and dark text
        if query_type == 'parameter':
            mermaid_lines.append(f'    {query_id}[["⚙️ {display_name}<br/>Parameter"]]')
            mermaid_lines.append(f'    style {query_id} fill:#bbdefb,stroke:#0d47a1,stroke-width:2px,color:#000')
        elif not enable_load:
            mermaid_lines.append(f'    {query_id}["{display_name}<br/>Not Loaded"]')
            mermaid_lines.append(f'    style {query_id} fill:#ffe0b2,stroke:#e65100,stroke-width:2px,stroke-dasharray: 5 5,color:#000')
        else:
            # Check if this is a final table (has dependencies but is not referenced by others)
            is_referenced = any(query_name in deps for deps in dependencies.values())
            if is_referenced:
                # Intermediate query
                mermaid_lines.append(f'    {query_id}["{display_name}"]')
                mermaid_lines.append(f'    style {query_id} fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px,color:#000')
            else:
                # Final table (loaded to model)
                mermaid_lines.append(f'    {query_id}["{display_name}<br/>📊 Final Table"]')
                mermaid_lines.append(f'    style {query_id} fill:#a5d6a7,stroke:#1b5e20,stroke-width:3px,color:#000')
    
    mermaid_lines.append("")
    
    # Add connections from data sources to queries
    mermaid_lines.append("    %% Data Source Connections")
    for query_name, source_info in data_sources.items():
        source_id = sanitize_mermaid_id(source_info['source_function'])
        query_id = sanitize_mermaid_id(query_name)
        mermaid_lines.append(f'    {source_id} ==>|extracts| {query_id}')
    
    # Add dependencies between queries
    if dependencies:
        mermaid_lines.append("")
        mermaid_lines.append("    %% Query Dependencies")
        
        for query_name, referenced in dependencies.items():
            query_id = sanitize_mermaid_id(query_name)
            
            for ref_query in referenced:
                if ref_query in all_queries:
                    ref_id = sanitize_mermaid_id(ref_query)
                    mermaid_lines.append(f'    {ref_id} -->|transforms| {query_id}')
    
    # Add visible legend as actual nodes in a subgraph
    mermaid_lines.append("")
    mermaid_lines.append("    %% Legend")
    mermaid_lines.append("    subgraph Legend[\" \"]")
    mermaid_lines.append('        direction TB')
    mermaid_lines.append('        L1[("🗄️ Data Source")]')
    mermaid_lines.append('        L2[["⚙️ Parameter"]]')
    mermaid_lines.append('        L3["Intermediate Query"]')
    mermaid_lines.append('        L4["📊 Final Table"]')
    mermaid_lines.append('        L5["Not Loaded"]')
    mermaid_lines.append('        style L1 fill:#e1bee7,stroke:#6a1b9a,stroke-width:3px,color:#000')
    mermaid_lines.append('        style L2 fill:#bbdefb,stroke:#0d47a1,stroke-width:2px,color:#000')
    mermaid_lines.append('        style L3 fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px,color:#000')
    mermaid_lines.append('        style L4 fill:#a5d6a7,stroke:#1b5e20,stroke-width:3px,color:#000')
    mermaid_lines.append('        style L5 fill:#ffe0b2,stroke:#e65100,stroke-width:2px,stroke-dasharray: 5 5,color:#000')
    mermaid_lines.append('    end')
    
    # Write as Markdown file with mermaid code block
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Power BI Query Dependencies - Data Sources to Queries\n\n")
        f.write("```mermaid\n")
        f.write('\n'.join(mermaid_lines))
        f.write("\n```\n\n")
        f.write("## Legend\n\n")
        f.write("### Node Types\n")
        f.write("- 🗄️ **Purple Box (Data Source)**: External data source (SharePoint, SQL, etc.)\n")
        f.write("- ⚙️ **Blue Box (Parameter)**: M Parameter used in queries\n")
        f.write("- **Light Green Box (Intermediate Query)**: Query that transforms data and is referenced by other queries\n")
        f.write("- 📊 **Dark Green Box (Final Table)**: Query loaded into the data model\n")
        f.write("- **Orange Dashed Box (Not Loaded)**: Query that exists but is not loaded to the model\n\n")
        f.write("### Arrow Types\n")
        f.write("- `==> extracts`: Data extracted from source\n")
        f.write("- `--> transforms`: Query transforms another query\n\n")
        f.write("### Flow Direction\n")
        f.write("Data flows from **left to right**: Data Source → Query → Final Table\n")

def format_time(seconds):
    """Format seconds into human-readable time"""
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    else:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.1f}s"

def process_pbix_file(pbix_file_path, output_base_dir, default_author="Unknown"):
    """Process a single PBIX file and extract documentation"""
    
    pbix_file_path = Path(pbix_file_path)
    pbix_filename = pbix_file_path.stem
    file_size_mb = round(pbix_file_path.stat().st_size / (1024 * 1024), 2) if pbix_file_path.exists() else 0
    
    print(f"\nProcessing: {pbix_filename} ({file_size_mb} MB)")
    
    start_time = time.time()
    
    # Try to extract author from PBIX metadata
    author_name = default_author
    try:
        import zipfile
        with zipfile.ZipFile(pbix_file_path, 'r') as zip_ref:
            # Try to read Metadata file
            if 'Metadata' in zip_ref.namelist():
                try:
                    metadata_data = zip_ref.read('Metadata')
                    metadata_text = metadata_data.decode('utf-8', errors='ignore')
                    
                    # Try to parse as JSON
                    try:
                        metadata_json = json.loads(metadata_text)
                        # Look for author in various possible locations
                        if 'createdBy' in metadata_json:
                            author_name = metadata_json['createdBy']
                        elif 'author' in metadata_json:
                            author_name = metadata_json['author']
                        elif 'creator' in metadata_json:
                            author_name = metadata_json['creator']
                    except:
                        # If not JSON, try to find author with regex
                        import re
                        author_match = re.search(r'"(?:createdBy|author|creator)"\s*:\s*"([\^"]+)"', metadata_text)
                        if author_match:
                            author_name = author_match.group(1)
                except Exception as meta_error:
                    pass  # Keep default author
    except Exception as zip_error:
        pass  # Keep default author
    
    # Check if this is a live connection report
    is_live_connection = False
    connection_info = {}
    model = None
    
    try:
        # parse the PBIX file - this might fail for live connections
        model = PBIXRay(str(pbix_file_path))
    except Exception as e:
        error_msg = str(e).lower()
        if 'live-connection' in error_msg or 'pbiservicelive' in error_msg or 'live connection' in error_msg:
            is_live_connection = True
            print(f"  ⚠ Live Connection Report detected")
            
            # Extract connection information from the exception
            connection_info = {
                "connection_type": "Live Connection",
                "error_message": str(e)
            }
            
            # Try to extract the connections attribute from the exception
            if hasattr(e, 'connections'):
                try:
                    connections_detail = e.connections
                    if connections_detail:
                        connection_info["connections_detail"] = str(connections_detail)
                        # Try to parse if it's a dict or list
                        if isinstance(connections_detail, (dict, list)):
                            connection_info["connections_parsed"] = connections_detail
                except Exception as conn_error:
                    connection_info["connections_extraction_error"] = str(conn_error)
            
            # Try to extract ConnectionType if available
            if 'ConnectionType=' in str(e):
                import re
                match = re.search(r"ConnectionType='([\^']+)'", str(e))
                if match:
                    connection_info["connection_type_detail"] = match.group(1)
        else:
            # Re-raise if it's a different error
            raise
    
    try:
        # Create the output directory structure
        output_dir = output_base_dir / pbix_filename
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if is_live_connection:
            # For live connections, extract what we can using direct ZIP access
            live_connection_data = {
                "report_info": {
                    "report_name": pbix_filename,
                    "file_path": str(pbix_file_path),
                    "file_size_mb": file_size_mb,
                    "documentation_generated": datetime.now().isoformat(),
                    "connection_type": "Live Connection",
                    "author": author_name
                },
                "connection_details": connection_info,
                "report_level_measures": [],
                "parameters": [],
                "m_queries": {},
                "connections": {},
                "data_sources": [],
                "note": "This is a live connection report. The data model exists in an external source (Power BI Service or Analysis Services). Only report-level measures, M queries, and calculations are documented here."
            }
            
            # Try to extract data directly from the PBIX file (it's a ZIP file)
            import zipfile
            try:
                with zipfile.ZipFile(pbix_file_path, 'r') as zip_ref:
                    # List all files in the PBIX
                    file_list = zip_ref.namelist()
                    print(f"  ℹ Files in PBIX: {', '.join(file_list)}")
                    
                    # Try to read DataModelSchema (contains measures)
                    if 'DataModelSchema' in file_list:
                        print(f"  ✓ Found DataModelSchema - extracting measures")
                        try:
                            schema_data = zip_ref.read('DataModelSchema')
                            schema_text = schema_data.decode('utf-16-le')
                            
                            # Parse the schema as JSON
                            schema_json = json.loads(schema_text)
                            
                            # Extract measures from the schema
                            if 'model' in schema_json and 'tables' in schema_json['model']:
                                for table in schema_json['model']['tables']:
                                    table_name = table.get('name', 'Unknown')
                                    
                                    # Check for measures in this table
                                    if 'measures' in table:
                                        for measure in table['measures']:
                                            measure_info = {
                                                "name": measure.get('name', ''),
                                                "table": table_name,
                                                "expression": measure.get('expression', ''),
                                                "description": measure.get('description', ''),
                                                "display_folder": measure.get('displayFolder', ''),
                                                "is_hidden": measure.get('isHidden', False)
                                            }
                                            live_connection_data["report_level_measures"].append(measure_info)
                                
                                print(f"  ✓ Extracted {len(live_connection_data['report_level_measures'])} measure(s) from schema")
                        except Exception as schema_error:
                            print(f"  ⚠ Error parsing DataModelSchema: {str(schema_error)}")
                    
                    # Try to extract from Report/Layout (for live connection reports)
                    if 'Report/Layout' in file_list:
                        print(f"  ✓ Found Report/Layout - extracting measures")
                        try:
                            layout_data = zip_ref.read('Report/Layout')
                            
                            # Try UTF-16 LE first (most common for Power BI)
                            try:
                                layout_text = layout_data.decode('utf-16-le')
                            except:
                                try:
                                    layout_text = layout_data.decode('utf-8')
                                except:
                                    layout_text = layout_data.decode('utf-8', errors='ignore')
                            
                            # Try to parse as JSON
                            try:
                                layout_json = json.loads(layout_text)
                                
                                # Function to recursively search for measures
                                def extract_measures_from_json(obj, path=""):
                                    found_measures = []
                                    
                                    if isinstance(obj, dict):
                                        # Check for measure-like structures
                                        if 'Name' in obj and 'Expression' in obj:
                                            # This looks like a measure
                                            expr = obj.get('Expression', '')
                                            # Verify it's actually a DAX expression
                                            if expr and any(keyword in str(expr).upper() for keyword in ['CALCULATE', 'SUM', 'COUNT', 'AVERAGE', 'MAX', 'MIN', 'DISTINCTCOUNT', 'SUMX', 'FILTER']):
                                                measure_info = {
                                                    "name": obj.get('Name', ''),
                                                    "table": obj.get('TableName', 'Report Level'),
                                                    "expression": str(expr),
                                                    "description": obj.get('Description', ''),
                                                    "display_folder": obj.get('DisplayFolder', ''),
                                                    "is_hidden": obj.get('IsHidden', False)
                                                }
                                                found_measures.append(measure_info)
                                        
                                        # Recursively search all dict values
                                        for key, value in obj.items():
                                            found_measures.extend(extract_measures_from_json(value, f"{path}.{key}"))
                                    
                                    elif isinstance(obj, list):
                                        # Recursively search all list items
                                        for i, item in enumerate(obj):
                                            found_measures.extend(extract_measures_from_json(item, f"{path}[{i}]"))
                                    
                                    return found_measures
                                
                                # Extract measures
                                found_measures = extract_measures_from_json(layout_json)
                                
                                # Add unique measures (avoid duplicates)
                                for measure in found_measures:
                                    if not any(m['name'] == measure['name'] and m['expression'] == measure['expression'] 
                                            for m in live_connection_data["report_level_measures"]):
                                        live_connection_data["report_level_measures"].append(measure)
                                
                                if found_measures:
                                    print(f"  ✓ Extracted {len(found_measures)} measure(s) from Report/Layout")
                                
                            except json.JSONDecodeError:
                                # If JSON parsing fails, try regex
                                print(f"  ℹ Report/Layout is not valid JSON, trying regex extraction")
                                import re
                                
                                # More comprehensive regex patterns
                                patterns = [
                                    # Pattern 1: Standard measure format
                                    r'"Name"\s*:\s*"([\^"]+)"[\^}]*?"Expression"\s*:\s*"([\^"]+)"',
                                    # Pattern 2: With escaped quotes
                                    r'"Name"\s*:\s*"([\^"]+)"[\^}]*?"Expression"\s*:\s*"((?:[\^"\\]|\\.)+)"',
                                    # Pattern 3: Multiline with any characters
                                    r'"Name"\s*:\s*"([\^"]+)"[\s\S]*?"Expression"\s*:\s*"([\s\S]+?)"(?=\s*,\s*")',
                                ]
                                
                                for pattern in patterns:
                                    matches = re.findall(pattern, layout_text, re.DOTALL)
                                    
                                    for match in matches:
                                        name, expression = match[0], match[1]
                                        
                                        # Filter: must look like a DAX expression
                                        if len(expression) > 10 and any(keyword in expression.upper() for keyword in 
                                            ['CALCULATE', 'SUM', 'COUNT', 'AVERAGE', 'MAX', 'MIN', 'DISTINCTCOUNT', 'SUMX', 'FILTER', 'RELATED', 'VALUES']):
                                            
                                            measure_info = {
                                                "name": name,
                                                "table": "Report Level",
                                                "expression": expression.replace('\\n', '\n').replace('\\"', '"'),
                                                "description": "",
                                                "display_folder": "",
                                                "is_hidden": False
                                            }
                                            
                                            # Avoid duplicates
                                            if not any(m['name'] == measure_info['name'] for m in live_connection_data["report_level_measures"]):
                                                live_connection_data["report_level_measures"].append(measure_info)
                                
                                if live_connection_data["report_level_measures"]:
                                    print(f"  ✓ Extracted {len(live_connection_data['report_level_measures'])} measure(s) via regex")
                        
                        except Exception as layout_error:
                            print(f"  ⚠ Error reading Report/Layout: {str(layout_error)}")
                    
                    # Try to read Connections file
                    if 'Connections' in file_list:
                        print(f"  ✓ Found Connections file")
                        try:
                            conn_data = zip_ref.read('Connections')
                            
                            # Try different encodings
                            conn_text = None
                            for encoding in ['utf-8', 'utf-16-le', 'utf-16-be']:
                                try:
                                    conn_text = conn_data.decode(encoding)
                                    break
                                except:
                                    continue
                            
                            if not conn_text:
                                conn_text = conn_data.decode('utf-8', errors='ignore')
                            
                            # Try to parse as JSON
                            try:
                                conn_json = json.loads(conn_text)
                                
                                # Handle different connection formats
                                connections_list = []
                                if isinstance(conn_json, dict):
                                    if 'Connections' in conn_json:
                                        connections_list = conn_json['Connections']
                                    elif 'RemoteArtifacts' in conn_json:
                                        connections_list = conn_json['RemoteArtifacts']
                                elif isinstance(conn_json, list):
                                    connections_list = conn_json
                                
                                for conn in connections_list:
                                    conn_info = {
                                        "name": conn.get('Name', conn.get('name', 'Unknown')),
                                        "connection_string": conn.get('ConnectionString', conn.get('connectionString', '')),
                                        "type": conn.get('ConnectionType', conn.get('type', 'Unknown'))
                                    }
                                    live_connection_data["data_sources"].append(conn_info)
                                
                                if connections_list:
                                    print(f"  ✓ Extracted {len(connections_list)} connection(s)")
                            
                            except json.JSONDecodeError:
                                print(f"  ⚠ Connections file is not valid JSON")
                        
                        except Exception as conn_error:
                            print(f"  ⚠ Error reading Connections: {str(conn_error)}")
            
            except Exception as zip_error:
                print(f"  ⚠ Error reading PBIX as ZIP: {str(zip_error)}")
            
            # Final status
            if not live_connection_data["report_level_measures"]:
                print(f"  ℹ No report-level measures found")
            
            # ... rest of the live connection code (writing files, etc.) ...
            
            # Write Live Connection documentation files
            
            # 1. Live_Connection_Info.json
            live_connection_path = output_dir / "Live_Connection_Info.json"
            with open(live_connection_path, 'w', encoding='utf-8') as f:
                json.dump(live_connection_data, f, indent=2, ensure_ascii=False)
            
            # 2. M_Queries.json (if any were found)
            if live_connection_data["m_queries"]:
                m_queries_json_path = output_dir / "M_Queries.json"
                with open(m_queries_json_path, 'w', encoding='utf-8') as f:
                    json.dump(live_connection_data["m_queries"], f, indent=2, ensure_ascii=False)
            
            # 3. Connections.json (if any were found)
            if live_connection_data["connections"]:
                connections_json_path = output_dir / "Connections.json"
                with open(connections_json_path, 'w', encoding='utf-8') as f:
                    json.dump(live_connection_data["connections"], f, indent=2, ensure_ascii=False)
            
            # 4. Measures.json (if any were found)
            if live_connection_data["report_level_measures"]:
                measures_json_path = output_dir / "Measures.json"
                measures_by_table = {}
                for measure in live_connection_data["report_level_measures"]:
                    table = measure["table"]
                    if table not in measures_by_table:
                        measures_by_table[table] = []
                    measures_by_table[table].append(measure)
                
                with open(measures_json_path, 'w', encoding='utf-8') as f:
                    json.dump(measures_by_table, f, indent=2, ensure_ascii=False)
            
            # Create a comprehensive README
            readme_path = output_dir / "README.md"
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(f"# {pbix_filename}\n\n")
                f.write("## Live Connection Report\n\n")
                f.write("This Power BI report uses a **live connection** to an external data source ")
                
                # Add specific connection type if available
                conn_type_detail = connection_info.get("connection_type_detail", "")
                if conn_type_detail:
                    if conn_type_detail == "pbiServiceLive":
                        f.write("(**Power BI Service Dataset**). ")
                    elif "AnalysisServices" in conn_type_detail:
                        f.write("(**Analysis Services**). ")
                    else:
                        f.write(f"(**{conn_type_detail}**). ")
                else:
                    f.write("(Power BI Service or Analysis Services). ")
                
                f.write("The data model is not embedded in this file.\n\n")
                
                # Add connection details if available
                if connection_info.get("connections_parsed"):
                    f.write("### Connection Information\n\n")
                    f.write("```json\n")
                    f.write(json.dumps(connection_info["connections_parsed"], indent=2))
                    f.write("\n```\n\n")
                
                f.write("### What's Documented\n\n")
                documented_items = []
                if live_connection_data.get("report_level_measures"):
                    documented_items.append(f"- **Report-level measures** ({len(live_connection_data['report_level_measures'])}): Measures defined in this report file")
                if live_connection_data.get("parameters"):
                    documented_items.append(f"- **Parameters** ({len(live_connection_data['parameters'])}): M parameters used in the report")
                if live_connection_data.get("m_queries"):
                    documented_items.append(f"- **M Queries** ({len(live_connection_data['m_queries'])}): Power Query transformations")
                if live_connection_data.get("connections"):
                    documented_items.append(f"- **Connections** ({len(live_connection_data['connections'])}): Data source connections")
                if live_connection_data.get("data_sources"):
                    documented_items.append(f"- **Data Sources** ({len(live_connection_data['data_sources'])}): External data sources")
                
                if documented_items:
                    f.write("\n".join(documented_items))
                else:
                    f.write("- No extractable content found (pure live connection with no report-level customizations)")
                
                f.write("\n\n### What's NOT Documented\n\n")
                f.write("- **Tables**: Defined in the external source\n")
                f.write("- **Columns**: Defined in the external source\n")
                f.write("- **Model measures**: Defined in the external source\n")
                f.write("- **Relationships**: Defined in the external source\n\n")
                
                f.write("### Files Generated\n\n")
                f.write("- `Live_Connection_Info.json`: All available information about this report\n")
                if live_connection_data.get("m_queries"):
                    f.write("- `M_Queries.json`: M queries and parameters\n")
                if live_connection_data.get("connections"):
                    f.write("- `Connections.json`: Data source connections\n")
                if live_connection_data.get("report_level_measures"):
                    f.write("- `Measures.json`: Report-level measures organized by table\n")
                
                # Add measures documentation
                if live_connection_data.get("report_level_measures"):
                    f.write(f"\n## Report-Level Measures ({len(live_connection_data['report_level_measures'])})\n\n")
                    
                    # Group by table
                    measures_by_table = {}
                    for measure in live_connection_data["report_level_measures"]:
                        table = measure["table"]
                        if table not in measures_by_table:
                            measures_by_table[table] = []
                        measures_by_table[table].append(measure)
                    
                    for table, measures in sorted(measures_by_table.items()):
                        f.write(f"### Table: {table}\n\n")
                        for measure in measures:
                            f.write(f"#### {measure['name']}")
                            if measure.get('is_hidden'):
                                f.write(" 🔒 *Hidden*")
                            f.write("\n\n")
                            
                            if measure['description']:
                                f.write(f"*{measure['description']}*\n\n")
                            if measure['display_folder']:
                                f.write(f"**Display Folder:** `{measure['display_folder']}`\n\n")
                            
                            f.write("```dax\n")
                            f.write(f"{measure['expression']}\n")
                            f.write("```\n\n")
                
                # Add data sources documentation
                if live_connection_data.get("data_sources"):
                    f.write(f"\n## Data Sources ({len(live_connection_data['data_sources'])})\n\n")
                    for ds in live_connection_data["data_sources"]:
                        f.write(f"### {ds.get('name', 'Unknown')}\n\n")
                        if ds.get('type'):
                            f.write(f"- **Type:** `{ds['type']}`\n")
                        if ds.get('provider'):
                            f.write(f"- **Provider:** `{ds['provider']}`\n")
                        if ds.get('connection_string'):
                            f.write(f"- **Connection String:** `{ds['connection_string']}`\n")
                        f.write("\n")
                
                # Add connections documentation
                if live_connection_data.get("connections"):
                    f.write(f"\n## Data Connections ({len(live_connection_data['connections'])})\n\n")
                    for conn_key, conn_info_item in live_connection_data["connections"].items():
                        if isinstance(conn_info_item, dict):
                            if 'source_function' in conn_info_item:
                                f.write(f"### {conn_info_item.get('display_name', conn_info_item['source_function'])}\n\n")
                                f.write(f"- **Type:** `{conn_info_item['source_function']}`\n")
                                if conn_info_item.get('endpoint'):
                                    f.write(f"- **Endpoint:** `{conn_info_item['endpoint']}`\n")
                                if conn_info_item.get('tables_using'):
                                    f.write(f"- **Used by:** {', '.join(conn_info_item['tables_using'])}\n")
                            else:
                                f.write(f"### {conn_info_item.get('name', 'Unknown')}\n\n")
                                if conn_info_item.get('type'):
                                    f.write(f"- **Type:** `{conn_info_item['type']}`\n")
                                if conn_info_item.get('connection_string'):
                                    f.write(f"- **Connection String:** `{conn_info_item['connection_string']}`\n")
                            f.write("\n")
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            print(f"✓ SUCCESS - Live connection documentation extracted")
            print(f"  Processing time: {format_time(processing_time)}")
            print(f"  Output: {output_dir}")
            print(f"\n  Summary:")
            print(f"  ├─ Connection Type: {connection_info.get('connection_type_detail', 'Live Connection')}")
            print(f"  ├─ Report-Level Measures: {len(live_connection_data.get('report_level_measures', []))}")
            print(f"  ├─ M Queries: {len(live_connection_data.get('m_queries', {}))}")
            print(f"  ├─ Parameters: {len(live_connection_data.get('parameters', []))}")
            print(f"  ├─ Data Sources: {len(live_connection_data.get('data_sources', []))}")
            print(f"  └─ Connections: {len(live_connection_data.get('connections', {}))}")
            
            return True, {
                "report_name": pbix_filename,
                "file_size_mb": file_size_mb,
                "processing_time_seconds": round(processing_time, 2),
                "connection_type": connection_info.get('connection_type_detail', 'Live Connection'),
                "report_level_measures": len(live_connection_data.get('report_level_measures', [])),
                "m_queries": len(live_connection_data.get('m_queries', {})),
                "parameters": len(live_connection_data.get('parameters', [])),
                "data_sources": len(live_connection_data.get('data_sources', [])),
                "connections": len(live_connection_data.get('connections', {}))
            }
        
        # If not a live connection, continue with normal processing
        loaded_tables = list(model.tables)
        
        # Get M queries using power_query (it's a DataFrame)
        m_queries_df = model.power_query
        
        # Get M parameters to add to M queries
        m_params_df = model.m_parameters
        
        # Create M_Queries.json - include both queries and parameters
        m_queries_data = {}
        
        # Add regular M queries
        for index, row in m_queries_df.iterrows():
            table_name = row['TableName']
            m_code = row['Expression']
            
            m_queries_data[table_name] = {
                "type": "query",
                "expression": str(m_code) if m_code is not None else "",
                "enable_load": table_name in loaded_tables
            }
        
        # Add M parameters
        if not m_params_df.empty:
            for index, param_row in m_params_df.iterrows():
                param_name = str(param_row.get('ParameterName', ''))
                expression = str(param_row.get('Expression', '')) if param_row.get('Expression') is not None else ''
                
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
        end_time = time.time()
        processing_time = end_time - start_time
        
        summary_data = {
            "report_info": {
                "report_name": pbix_filename,
                "file_path": str(pbix_file_path),
                "file_size_mb": file_size_mb,
                "processing_time_seconds": round(processing_time, 2),
                "documentation_generated": datetime.now().isoformat(),
                "author": author_name,
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
        
        # Create Mermaid diagrams (now as .md files)
        
        # Model diagram (relationships)
        model_diagram_path = output_dir / "Model_Diagram.md"
        create_model_diagram(model_data["relationships"], table_details, model_diagram_path)
        
        # Query dependencies diagram
        query_diagram_path = output_dir / "Query_Dependencies.md"
        create_query_dependencies_diagram(m_queries_data, query_diagram_path)
        
        # Print summary
        print(f"✓ SUCCESS - Documentation extracted")
        print(f"  Processing time: {format_time(processing_time)}")
        print(f"  Output: {output_dir}")
        print(f"\n  Summary Statistics:")
        print(f"  ├─ Tables: {summary_data['tables']['total_tables']} ({summary_data['tables']['user_generated_tables']} user-generated)")
        print(f"  ├─ Columns: {summary_data['columns']['total_columns']}")
        print(f"  ├─ Measures: {summary_data['measures']['total_measures']}")
        print(f"  ├─ Relationships: {summary_data['relationships']['total_relationships']}")
        print(f"  └─ Connections: {summary_data['connections']['total_unique_connections']}")
        
        return True, summary_data
        
    except Exception as e:
        end_time = time.time()
        processing_time = end_time - start_time
        print(f"✗ FAILED - Error: {str(e)}")
        print(f"  Processing time: {format_time(processing_time)}")
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
    
    overall_start_time = time.time()
    
    pbix_path = Path(pbix_path)
    
    # Determine if path is a file or directory
    if pbix_path.is_file() and pbix_path.suffix.lower() == '.pbix':
        # Single file processing
        print(f"\nMode: Single File")
        
        success, summary = process_pbix_file(pbix_path, output_base_dir, "Unknown")
        
        overall_end_time = time.time()
        total_time = overall_end_time - overall_start_time
        
        if success:
            print(f"\n{'='*80}")
            print("✓ Processing Complete")
            print(f"Total time: {format_time(total_time)}")
            print(f"{'='*80}\n")
        else:
            print(f"\n{'='*80}")
            print("✗ Processing Failed")
            print(f"Total time: {format_time(total_time)}")
            print(f"{'='*80}\n")
    
    elif pbix_path.is_dir():
        # Directory processing - recursive scan
        print(f"\nMode: Recursive Directory Scan")
        
        # Find all .pbix files recursively
        pbix_files = list(pbix_path.rglob("*.pbix"))
        
        if not pbix_files:
            print(f"\n✗ No .pbix files found in {pbix_path}")
        else:
            print(f"\nFound {len(pbix_files)} .pbix file(s)\n")
            
            successful = 0
            failed = 0
            processing_stats = []
            
            for pbix_file in pbix_files:
                success, summary = process_pbix_file(pbix_file, output_base_dir)
                
                if success:
                    successful += 1
                    if summary:
                        processing_stats.append({
                            "name": summary.get("report_info", {}).get("report_name", "Unknown"),
                            "size_mb": summary.get("report_info", {}).get("file_size_mb", 0),
                            "time_seconds": summary.get("report_info", {}).get("processing_time_seconds", 0)
                        })
                else:
                    failed += 1
            
            overall_end_time = time.time()
            total_time = overall_end_time - overall_start_time
            
            # Final summary
            print(f"\n{'='*80}")
            print("Processing Complete")
            print(f"{'='*80}")
            print(f"Total Files: {len(pbix_files)}")
            print(f"✓ Successful: {successful}")
            print(f"✗ Failed: {failed}")
            print(f"Total time: {format_time(total_time)}")
            
            # Processing time analysis
            if processing_stats:
                print(f"\n{'='*80}")
                print("Processing Time Analysis")
                print(f"{'='*80}")
                
                # Sort by file size
                processing_stats.sort(key=lambda x: x['size_mb'])
                
                print(f"\n{'File Name':<40} {'Size (MB)':<12} {'Time':<10}")
                print("-" * 80)
                for stat in processing_stats:
                    print(f"{stat['name']:<40} {stat['size_mb']:<12.2f} {format_time(stat['time_seconds']):<10}")
                
                # Calculate averages
                avg_time = sum(s['time_seconds'] for s in processing_stats) / len(processing_stats)
                avg_size = sum(s['size_mb'] for s in processing_stats) / len(processing_stats)
                
                print(f"\n{'='*80}")
                print(f"Average file size: {avg_size:.2f} MB")
                print(f"Average processing time: {format_time(avg_time)}")
                
                # Estimate time per MB
                if avg_size > 0:
                    time_per_mb = avg_time / avg_size
                    print(f"Estimated time per MB: {format_time(time_per_mb)}")
                
            print(f"{'='*80}\n")
    
    else:
        print(f"\n✗ ERROR: Invalid path - must be a .pbix file or directory")
        print(f"Path provided: {pbix_path}\n")