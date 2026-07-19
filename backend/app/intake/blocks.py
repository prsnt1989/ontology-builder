from __future__ import annotations

QUESTIONNAIRE_BLOCKS = [
    {
        "block_number": 1,
        "title": "Company Profile",
        "description": "Understanding your organization",
        "questions": [
            {
                "id": "company_name",
                "text": "What is your company name?",
                "options": [],
                "impact": "Used to label and identify this ontology",
            },
            {
                "id": "industry",
                "text": "What industry is your company in?",
                "options": ["Healthcare", "Manufacturing", "Financial Services", "Retail & E-commerce", "Logistics & Supply Chain"],
                "impact": "Determines industry-specific object types and compliance requirements",
            },
            {
                "id": "company_size",
                "text": "What is your company size?",
                "options": ["Startup (1-50)", "SMB (51-500)", "Mid-market (501-5000)", "Enterprise (5000+)"],
                "impact": "Influences permission complexity and scale requirements",
            },
            {
                "id": "tech_stack",
                "text": "What are your primary technology platforms?",
                "options": ["SAP/Oracle ERP", "Salesforce", "Microsoft Dynamics", "Custom/In-house", "Multiple SaaS tools"],
                "impact": "Determines data source integrations and entity mappings",
            },
            {
                "id": "palantir_experience",
                "text": "Have you used Palantir Foundry or similar ontology platforms before?",
                "options": ["Yes, actively using Foundry", "Some experience", "No, this is new to us"],
                "impact": "Adjusts complexity of generated ontology",
            },
        ],
    },
    {
        "block_number": 2,
        "title": "Business Domain",
        "description": "Your department and key processes",
        "questions": [
            {
                "id": "department",
                "text": "Which department or function is this ontology primarily for?",
                "options": ["Operations", "Finance", "Sales & Marketing", "Supply Chain", "Human Resources"],
                "impact": "Determines primary object types and workflows",
            },
            {
                "id": "key_processes",
                "text": "What are the key business processes you want to model?",
                "options": ["Order-to-Cash", "Procure-to-Pay", "Plan-to-Produce", "Hire-to-Retire", "Issue-to-Resolution"],
                "impact": "Drives lifecycle states and action definitions",
            },
            {
                "id": "key_entities",
                "text": "What are the primary business entities you work with?",
                "options": ["Customers & Orders", "Products & Inventory", "Employees & Teams", "Assets & Equipment", "Cases & Tickets"],
                "impact": "Core object types in the ontology",
            },
            {
                "id": "domain_terms",
                "text": "Are there domain-specific terms unique to your business?",
                "options": ["Yes, many specialized terms", "A few industry-standard terms", "We use standard business terminology"],
                "impact": "Influences property naming and descriptions",
            },
        ],
    },
    {
        "block_number": 3,
        "title": "Problem Statement",
        "description": "What you're trying to solve",
        "questions": [
            {
                "id": "primary_goal",
                "text": "What is the primary goal for building this ontology?",
                "options": ["Operational visibility & reporting", "Process automation", "Data integration across systems", "Predictive analytics & ML"],
                "impact": "Shapes the depth of relationships and computed properties",
            },
            {
                "id": "pain_points",
                "text": "What are your biggest data/process pain points?",
                "options": ["Data silos between systems", "No single source of truth", "Manual processes that should be automated", "Can't answer business questions quickly"],
                "impact": "Prioritizes which object types get the most detail",
            },
            {
                "id": "success_criteria",
                "text": "How will you measure success of this ontology?",
                "options": ["Faster decision making", "Reduced manual work", "Better cross-team collaboration", "Improved data quality"],
                "impact": "Influences validation rules and action definitions",
            },
        ],
    },
    {
        "block_number": 4,
        "title": "Data Sources",
        "description": "Your existing systems and data",
        "questions": [
            {
                "id": "primary_source",
                "text": "What is your primary data source?",
                "options": ["ERP system (SAP/Oracle/Dynamics)", "CRM (Salesforce/HubSpot)", "Database (PostgreSQL/SQL Server)", "Data warehouse (Snowflake/BigQuery)", "APIs & microservices"],
                "impact": "Determines backing table structure and column types",
            },
            {
                "id": "data_volume",
                "text": "What is the approximate data volume?",
                "options": ["Small (<100K records)", "Medium (100K-10M records)", "Large (10M-1B records)", "Very large (1B+ records)"],
                "impact": "Influences indexing strategy and partition design",
            },
            {
                "id": "data_freshness",
                "text": "How fresh does the data need to be?",
                "options": ["Real-time (seconds)", "Near real-time (minutes)", "Batch (hourly/daily)", "Historical only"],
                "impact": "Affects timestamp properties and lifecycle transitions",
            },
            {
                "id": "data_quality",
                "text": "What are your known data quality issues?",
                "options": ["Missing/null values", "Inconsistent formats", "Duplicates across systems", "No major issues"],
                "impact": "Drives validation rules and data cleansing actions",
            },
        ],
    },
    {
        "block_number": 5,
        "title": "Users & Permissions",
        "description": "Who uses the system and their access levels",
        "questions": [
            {
                "id": "user_roles",
                "text": "What are the primary user roles?",
                "options": ["Executives & Managers", "Analysts & Data Scientists", "Operational Staff", "External Partners/Customers", "System Administrators"],
                "impact": "Defines permission roles and row-level filters",
            },
            {
                "id": "permission_model",
                "text": "What permission model do you need?",
                "options": ["Simple (view/edit/admin)", "Role-based (department-scoped)", "Attribute-based (row-level security)", "Hierarchical (org-tree based)"],
                "impact": "Complexity of permission rules",
            },
            {
                "id": "sensitive_data",
                "text": "Do you have sensitive data that needs restricted access?",
                "options": ["PII/PHI (personal/health data)", "Financial data (SOX compliance)", "Proprietary/trade secrets", "No special restrictions"],
                "impact": "Property-level restrictions and audit actions",
            },
        ],
    },
    {
        "block_number": 6,
        "title": "Workflows",
        "description": "Business processes and entity lifecycles",
        "questions": [
            {
                "id": "workflow_complexity",
                "text": "How complex are your primary workflows?",
                "options": ["Linear (step-by-step)", "Branching (if/then paths)", "Parallel (multiple tracks)", "Cyclic (loops/iterations)"],
                "impact": "Complexity of lifecycle state machines",
            },
            {
                "id": "approval_processes",
                "text": "Do your workflows involve approvals?",
                "options": ["Multi-level approvals", "Single approver", "Auto-approved with rules", "No approvals needed"],
                "impact": "Adds approval states and guard conditions",
            },
            {
                "id": "notifications",
                "text": "What triggers notifications in your workflows?",
                "options": ["State changes", "SLA breaches", "Assignment changes", "All of the above"],
                "impact": "Side effects in lifecycle transitions",
            },
            {
                "id": "automation_level",
                "text": "How much automation do you want?",
                "options": ["Fully automated where possible", "Human-in-the-loop for critical steps", "Manual with system suggestions", "Minimal automation"],
                "impact": "Determines action preconditions and auto-triggers",
            },
        ],
    },
    {
        "block_number": 7,
        "title": "Constraints & Requirements",
        "description": "Compliance, scale, and integration needs",
        "questions": [
            {
                "id": "compliance",
                "text": "What compliance requirements apply?",
                "options": ["HIPAA (healthcare)", "SOX (financial)", "GDPR (data privacy)", "Industry-specific (FDA/FAA/etc)", "No specific compliance"],
                "impact": "Adds audit trails, retention rules, and access controls",
            },
            {
                "id": "integration_needs",
                "text": "What systems need to integrate with this ontology?",
                "options": ["BI tools (PowerBI/Tableau)", "ML/AI platforms", "Workflow engines (Airflow/Prefect)", "External APIs", "All of the above"],
                "impact": "Influences action definitions and export formats",
            },
            {
                "id": "scalability",
                "text": "What are your scalability expectations?",
                "options": ["Single team pilot", "Department-wide", "Company-wide", "Multi-org/partner ecosystem"],
                "impact": "Namespace strategy and permission granularity",
            },
        ],
    },
]


def get_block(block_number: int) -> dict | None:
    for block in QUESTIONNAIRE_BLOCKS:
        if block["block_number"] == block_number:
            return block
    return None


TOTAL_BLOCKS = len(QUESTIONNAIRE_BLOCKS)
