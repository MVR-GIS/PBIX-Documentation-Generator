# Power BI Data Model - Table Relationships

```mermaid
---
title: Power BI Data Model - Table Relationships
---
erDiagram
    KM_Tickets ||--|| All_Tickets : "TicketID to TicketID (Import to Import)"
    PW_Tickets ||--|| All_Tickets : "TicketID to TicketID (Import to Import)"
    EMS_Tickets ||--|| All_Tickets : "TicketID to TicketID (Import to Import)"
    CAD_Tickets ||--|| All_Tickets : "TicketID to TicketID (Import to Import)"
```

## Legend

### Relationship Symbols
- `||--||` : One-to-One
- `||--o{` : One-to-Many
- `}o--o{` : Many-to-Many

### Storage Modes
- **Import**: Data cached in memory
- **DirectQuery**: Live connection to source
- **Dual**: Can use Import or DirectQuery

### Relationship Status
- **[INACTIVE]**: Relationship exists but not active
