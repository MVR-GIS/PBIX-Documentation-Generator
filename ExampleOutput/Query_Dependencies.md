# Power BI Query Dependencies - Data Sources to Queries

```mermaid
---
title: Power BI Query Dependencies - Data Sources to Queries
---
%%{init: {'theme':'base', 'themeVariables': { 'primaryColor':'#fff','primaryTextColor':'#000','primaryBorderColor':'#000','lineColor':'#000','secondaryColor':'#f4f4f4','tertiaryColor':'#fff','background':'#ffffff','mainBkg':'#ffffff','textColor':'#000000','labelTextColor':'#000000','edgeLabelBackground':'#ffffff'}}}%%
graph LR

    %% Data Sources
    Table_Combine[("🗄️ Table.Combine")]
    style Table_Combine fill:#e1bee7,stroke:#6a1b9a,stroke-width:3px,color:#000
    SharePoint_Tables[("🗄️ SharePoint.Tables")]
    style SharePoint_Tables fill:#e1bee7,stroke:#6a1b9a,stroke-width:3px,color:#000
    DateTime_LocalNow[("🗄️ DateTime.LocalNow")]
    style DateTime_LocalNow fill:#e1bee7,stroke:#6a1b9a,stroke-width:3px,color:#000
    SharePoint_Files[("🗄️ SharePoint.Files")]
    style SharePoint_Files fill:#e1bee7,stroke:#6a1b9a,stroke-width:3px,color:#000
    Odbc_DataSource[("🗄️ Odbc.DataSource")]
    style Odbc_DataSource fill:#e1bee7,stroke:#6a1b9a,stroke-width:3px,color:#000

    %% Query Nodes
    All_Tickets["All Tickets<br/>📊 Final Table"]
    style All_Tickets fill:#a5d6a7,stroke:#1b5e20,stroke-width:3px,color:#000
    CAD_Tickets["CAD Tickets"]
    style CAD_Tickets fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px,color:#000
    EMS_Tickets["EMS Tickets"]
    style EMS_Tickets fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px,color:#000
    EMS_EMPLOYEES[["⚙️ EMS_EMPLOYEES<br/>Parameter"]]
    style EMS_EMPLOYEES fill:#bbdefb,stroke:#0d47a1,stroke-width:2px,color:#000
    EXT["EXT<br/>📊 Final Table"]
    style EXT fill:#a5d6a7,stroke:#1b5e20,stroke-width:3px,color:#000
    KM_Tickets["KM Tickets"]
    style KM_Tickets fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px,color:#000
    LastRefresh["LastRefresh<br/>📊 Final Table"]
    style LastRefresh fill:#a5d6a7,stroke:#1b5e20,stroke-width:3px,color:#000
    PW_Tickets["PW Tickets"]
    style PW_Tickets fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px,color:#000
    ParameterMTest[["⚙️ ParameterMTest<br/>Parameter"]]
    style ParameterMTest fill:#bbdefb,stroke:#0d47a1,stroke-width:2px,color:#000
    TYPE["TYPE<br/>📊 Final Table"]
    style TYPE fill:#a5d6a7,stroke:#1b5e20,stroke-width:3px,color:#000

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
    EMS_Tickets -->|transforms| All_Tickets
    KM_Tickets -->|transforms| All_Tickets
    CAD_Tickets -->|transforms| All_Tickets
    PW_Tickets -->|transforms| All_Tickets
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
        style L1 fill:#e1bee7,stroke:#6a1b9a,stroke-width:3px,color:#000
        style L2 fill:#bbdefb,stroke:#0d47a1,stroke-width:2px,color:#000
        style L3 fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px,color:#000
        style L4 fill:#a5d6a7,stroke:#1b5e20,stroke-width:3px,color:#000
        style L5 fill:#ffe0b2,stroke:#e65100,stroke-width:2px,stroke-dasharray: 5 5,color:#000
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
