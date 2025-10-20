from odoo import models  # type: ignore


class IrActionsActWindow(models.Model):
    _inherit = "ir.actions.act_window"

    def _get_action_dict(self):
        action = super()._get_action_dict()
        user = self.env.user

        member_action_id = self.env.ref("mgs_gym.action_gym_partner").id
        if action.get("id") == member_action_id:
            if user.has_group("base.group_system"):
                return action
            allowed_branch_ids = user.branch_ids.ids

            # Ensure domain is a list
            existing_domain = action.get("domain", [])
            if isinstance(existing_domain, str):
                # Convert string domain to list if needed
                existing_domain = eval(existing_domain)

            # Append branch restriction
            existing_domain.append(("branch_id", "in", allowed_branch_ids))
            action["domain"] = existing_domain

        return action
