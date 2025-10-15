from odoo import models, fields  # type: ignore


class GymPartner(models.Model):
    _inherit = "res.partner"

    gender = fields.Selection(
        [("male", "Male"), ("female", "Female")], string="Gender", required=True
    )
    is_gym_member = fields.Boolean(default=False, string="Is GYM Client", required=True)
    branch_id = fields.Many2one("mgs_gym.branch", string="Branch", required=True)
