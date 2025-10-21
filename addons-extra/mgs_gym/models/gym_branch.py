from odoo import models, api, fields  # type: ignore
from odoo.exceptions import UserError  # type: ignore


class GymBranch(models.Model):
    _name = "mgs_gym.branch"
    _description = "GYM Branch"

    name = fields.Char(string="Name", required=True)
    manager_id = fields.Many2one("res.users", string="Manager", required=True)
    gender = fields.Selection(
        [("male", "Male"), ("female", "Female")], string="Gender", required=True
    )
    is_active = fields.Boolean(default=True, string="Is Active")
    active = fields.Boolean(default=True)
    address = fields.Char(string="Address", required=True)
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Analytic Account",
        help="Used to track this branch’s revenue and expenses.",
    )
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, readonly=True
    )
    reminder_days = fields.Integer(
        default=3,
        string="Reminder Days",
        help="Number of days before membership expiration when we should remind the user",
    )

    @api.model
    def create(self, vals):
        # Automatically create an analytic account for each branch
        branch = super().create(vals)
        if not branch.analytic_account_id:
            analytic = self.env["account.analytic.account"].create(
                {
                    "name": f"Branch - {branch.name}",
                    "company_id": self.env.company.id,
                }
            )
            branch.analytic_account_id = analytic.id
        return branch

    def unlink(self):
        # 1. Check for associated memberships
        for branch in self:
            membership_count = self.env["mgs_gym.membership"].search_count(
                [("branch_id", "=", branch.id)]
            )

            # 2. Raise an error if memberships exist
            if membership_count > 0:
                raise UserError(
                    (
                        "You cannot delete the branch '%s' because it has %d membership(s) attached to it."
                    )
                    % (branch.name, membership_count)
                )

        return super(GymBranch, self).unlink()
