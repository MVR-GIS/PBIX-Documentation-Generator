# Power BI Query Dependencies - Data Sources to Queries

```mermaid
---
title: Power BI Query Dependencies - Data Sources to Queries
---
graph LR

    %% Data Sources
    Table_Combine[("🗄️ Table.Combine")]
    style Table_Combine fill:#f3e5f5,stroke:#7b1fa2,stroke-width:3px
    SharePoint_Tables[("🗄️ SharePoint.Tables")]
    style SharePoint_Tables fill:#f3e5f5,stroke:#7b1fa2,stroke-width:3px
    DateTime_LocalNow[("🗄️ DateTime.LocalNow")]
    style DateTime_LocalNow fill:#f3e5f5,stroke:#7b1fa2,stroke-width:3px
    SharePoint_Files[("🗄️ SharePoint.Files")]
    style SharePoint_Files fill:#f3e5f5,stroke:#7b1fa2,stroke-width:3px
    Odbc_DataSource[("🗄️ Odbc.DataSource")]
    style Odbc_DataSource fill:#f3e5f5,stroke:#7b1fa2,stroke-width:3px

    %% Query Nodes
    All_Tickets["All Tickets<br/>📊 Final Table"]
    style All_Tickets fill:#c8e6c9,stroke:#2e7d32,stroke-width:3px
    CAD_Tickets["CAD Tickets"]
    style CAD_Tickets fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
    EMS_Tickets["EMS Tickets"]
    style EMS_Tickets fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
    EMS_EMPLOYEES[["⚙️ EMS_EMPLOYEES<br/>Parameter"]]
    style EMS_EMPLOYEES fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    EXT["EXT<br/>📊 Final Table"]
    style EXT fill:#c8e6c9,stroke:#2e7d32,stroke-width:3px
    KM_Tickets["KM Tickets"]
    style KM_Tickets fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
    LastRefresh["LastRefresh<br/>📊 Final Table"]
    style LastRefresh fill:#c8e6c9,stroke:#2e7d32,stroke-width:3px
    PW_Tickets["PW Tickets"]
    style PW_Tickets fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
    ParameterMTest[["⚙️ ParameterMTest<br/>Parameter"]]
    style ParameterMTest fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    TYPE["TYPE<br/>📊 Final Table"]
    style TYPE fill:#c8e6c9,stroke:#2e7d32,stroke-width:3px

    %% Data Source Connections
    Table_Combine ==>|extracts| All_Tickets
    SharePoint_Tables ==>|extracts| KM_Tickets
    SharePoint_Tables ==>|extracts| PW_Tickets
    DateTime_LocalNow ==>|extracts| LastRefresh
    SharePoint_Tables ==>|extracts| EMS_Tickets
    SharePoint_Tables ==>|extracts| CAD_Tickets
    SharePoint_Files ==>|extracts| TYPE
    SharePoint_Files ==>|extracts| EXT
    Odbc_DataSource ==>|extracts| EMS_EMPLOYEES

    %% Query Dependencies
    KM_Tickets -->|transforms| All_Tickets
    CAD_Tickets -->|transforms| All_Tickets
    PW_Tickets -->|transforms| All_Tickets
    EMS_Tickets -->|transforms| All_Tickets
    EMS_EMPLOYEES -->|transforms| PW_Tickets
    EMS_EMPLOYEES -->|transforms| EMS_Tickets
    EMS_EMPLOYEES -->|transforms| CAD_Tickets

    %% Legend
    subgraph Legend[" "]
        direction TB
        L1[("🗄️ Data Source")]
        L2[["⚙️ Parameter"]]
        L3["Intermediate Query"]
        L4["📊 Final Table"]
        L5["Not Loaded"]
        style L1 fill:#f3e5f5,stroke:#7b1fa2,stroke-width:3px
        style L2 fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
        style L3 fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
        style L4 fill:#c8e6c9,stroke:#2e7d32,stroke-width:3px
        style L5 fill:#fff3e0,stroke:#f57c00,stroke-width:2px,stroke-dasharray: 5 5
    end
```

## Legend

### Node Types
- 🗄️ **Purple Box (Data Source)**: External data source (SharePoint, SQL, etc.)
- ⚙️ **Blue Box (Parameter)**: M Parameter used in queries
- **Light Green Box (Intermediate Query)**: Query that transforms data and is referenced by other queries
- 📊 **Dark Green Box (Final Table)**: Query loaded into the data model
- **Orange Dashed Box (Not Loaded)**: Query that exists but is not loaded to the model

### Arrow Types
- `==> extracts`: Data extracted from source
- `--> transforms`: Query transforms another query

### Flow Direction
Data flows from **left to right**: Data Source → Query → Final Table
