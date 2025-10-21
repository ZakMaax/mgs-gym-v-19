from odoo import models, api, fields  # type: ignore


class GymUser(models.Model):
    _inherit = "res.users"

    branch_ids = fields.Many2many("mgs_gym.branch", string="Branchs", required=True)
    default_branch_id = fields.Many2one(
        "mgs_gym.branch",
        string="Default Branch",
    )

    @api.onchange("branch_ids")
    def _onchange_branch_ids(self):
        """Limit default_branch_id to selected branches."""
        if self.branch_ids:
            if (
                not self.default_branch_id
                or self.default_branch_id not in self.branch_ids
            ):
                self.default_branch_id = self.branch_ids[0]
            return {
                "domain": {"default_branch_id": [("id", "in", self.branch_ids.ids)]}
            }
        self.default_branch_id = False
        return {"domain": {"default_branch_id": []}}
