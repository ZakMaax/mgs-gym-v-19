{
    "name": "MGS SMS Gateway - (Telesom Integration)",
    "version": "1.0",
    "author": "Meisour Global Solutions",
    "category": "Extra Tools",
    "summary": "Secure implementation of the Telesom API for Odoo SMS framework.",
    "depends": [
        "base",
        "sms",
        "mgs_gym",  # Depends on mgs_gym because configuration parameters are defined there
    ],
    "data": ["security/ir.model.access.csv", "views/views.xml"],
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
}  # type: ignore
