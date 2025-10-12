{
    "name": "MGS SALE",
    "version": "1.0",
    "author": "Meisour Global Solutions",
    "description": "Sales module with additional reporting",
    "category": "Accounting",
    "depends": ["base", "sale_management", "crm", "hr", "contacts", "account"],
    "license": "GPL-2",
    "data": [
        "security/ir.model.access.csv",
        "reports/mgs_sale_detailed_report.xml",
        "reports/mgs_sale_summary_report.xml",
        "reports/report_actions.xml",
        "views/mgs_sale_report_views.xml",
        "views/actions.xml",
        "views/menus.xml",
    ],
}  # type: ignore
