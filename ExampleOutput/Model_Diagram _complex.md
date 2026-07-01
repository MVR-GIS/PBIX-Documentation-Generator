# Power BI Data Model - Table Relationships

```mermaid
---
title: Power BI Data Model - Table Relationships
---
%%{init: {'theme':'base', 'themeVariables': { 'primaryColor':'#fff','primaryTextColor':'#000','primaryBorderColor':'#000','lineColor':'#000','secondaryColor':'#f4f4f4','tertiaryColor':'#fff','background':'#ffffff','mainBkg':'#ffffff','textColor':'#000000','labelTextColor':'#000000'}}}%%
erDiagram
    t_MVD_i ||--|| dms_doc : "CompositeKey to CompositeKey (Import to Import)"
    dms_doc ||--|| dms_proj : "o_projguid to o_projguid (Import to Import)"
    IPROJECTTEMPLATE ||--|| NewProjects : "PROJECT_Project_Code to ProjectCode (Import to Import)"
    dms_proj ||--|| dms_proj_wa_only : "WA_GUID to o_projguid (Import to Import)"
    dms_proj ||--|| dms_env : "o_envno to o_envno (Import to Import)"
    dms_proj ||--|| IPROJECTTEMPLATE : "KEY to KEY (Import to Import)"
    dms_proj ||--|| IPROGRAMTEMPLATE : "KEY to KEY (Import to Import)"
    dms_proj ||--|| I_LOCAL_SPONSOR : "KEY to KEY (Import to Import)"
    dms_proj ||--|| I_ADMIN_OFFICE_TEMPLATE : "KEY to key (Import to Import)"
    dms_proj ||--|| I_COPY_OF_PROJECT_TEMPLATE : "KEY to key (Import to Import)"
    dms_proj ||--|| I_FLIPL : "KEY to KEY (Import to Import)"
    dms_doc ||--|| dms_user : "o_creatorno to o_userno (Import to Import)"
    StdNaming ||--|| StdNaming_Discipline : "DisciplineName to DisciplineName (Import to Import)"
    LU_Levees ||--|| dms_proj : "o_projectno to o_projectno (Import to Import)"
    Unique_IDs ||--|| dms_proj : "o_projectno to o_projectno (Import to Import)"
    LU_Levees ||--|| dms_proj_wa_only : "o_projectno to o_projectno [INACTIVE] (Import to Import)"
    Unique_IDs ||--|| dms_proj_wa_only : "o_projectno to o_projectno [INACTIVE] (Import to Import)"
    StdNaming_Location ||--|| dms_proj : "MVR_DMS_Identifier to B5_Location_Code (Import to Import)"
    dms_ulsm ||--|| dms_ulst : "o_usrlstno to o_usrlstno (Import to Import)"
    dms_ulsm ||--|| dms_user : "o_memberno to o_userno (Import to Import)"
    dms_grpm ||--|| dms_grp : "o_groupno to o_groupno (Import to Import)"
    dms_ulsm_sql ||--|| dms_ulst : "o_usrlstno to o_usrlstno (Import to Import)"
    dms_grpm ||--|| dms_user : "o_userno to o_userno (Import to Import)"
    StdNaming ||--|| dms_doc : "CompositeKey to CompositeKey (Import to Import)"
    dms_doc ||--|| StdNamingNoFilter : "CompositeKey to CompositeKey (Import to Import)"
    keywords_normalized ||--|| t_MVD_i : "CompositeKey to CompositeKey (Import to Import)"
    StdNaming_With_Templates ||--|| StdNaming_With_Templates_Keywords : "ID to ID (Import to Import)"
    t_MVD_i ||--|| StdNaming_CriticalDocs_Normal : "A_MVR_Type-Subtype to Sort_TypeSubtype (Import to Import)"
    dms_doc ||--|| dms_thumb : "o_docguid to o_docguid (Import to Import)"
    dms_proj ||--|| dms_acce : "o_aclno to o_aclno (Import to Import)"
    EC_INDEXDOCINFO ||--|| dms_doc : "DOC_GUID to o_docguid (Import to Import)"
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
