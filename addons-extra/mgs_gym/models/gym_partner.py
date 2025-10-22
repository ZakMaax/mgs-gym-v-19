from odoo import models, api, fields  # type: ignore


class GymPartner(models.Model):
    _inherit = "res.partner"

    is_gym_member = fields.Boolean(default=True, string="Is GYM Client")
    branch_id = fields.Many2one(
        "mgs_gym.branch",
        string="Branch",
        domain=lambda self: [("id", "in", self.env.user.branch_ids.ids)],
        default=lambda self: self.env.user.default_branch_id,
    )
    gender = fields.Selection(related="branch_id.gender", store=True, readonly=True)
    company_id = fields.Many2one(
        "res.company", compute="_compute_company_id", store=True, readonly=True
    )

    @api.depends("branch_id")
    def _compute_company_id(self):
        for partner in self:
            partner.company_id = partner.branch_id.company_id or self.env.company
