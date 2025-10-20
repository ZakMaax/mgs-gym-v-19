from odoo import models, fields  # type: ignore


class GymUser(models.Model):
    _inherit = "res.users"

    branch_ids = fields.Many2many("mgs_gym.branch", string="Branch", required=True)
