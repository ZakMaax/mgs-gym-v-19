from odoo import models, fields  # type: ignore


class GymBranch(models.Model):
    _name = "mgs_gym.branch"
    _description = "GYM Branch"

    name = fields.Char(string="Name", required=True)
    manager_id = fields.Many2one("res.users", string="Manager", required=True)
    is_active = fields.Boolean(default=True, string="Is Active")
    address = fields.Char(string="Address", required=True)
