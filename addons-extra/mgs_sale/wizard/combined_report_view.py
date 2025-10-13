from odoo import models, fields, tools  # type: ignore


class CombinedSaleReport(models.AbstractModel):
    _name = "mgs_sale.combined_report"
    _description = "Combined Sales and POS Lines Report (SQL View)"
    _auto = False
    _rec_name = "date_order"

    # Fields must match the columns selected in the SQL query
    date_order = fields.Datetime("Order Date", readonly=True)
    order_ref = fields.Char("Order Reference", readonly=True)
    price_subtotal = fields.Float("Subtotal", readonly=True)
    price_unit = fields.Float("Unit Price", readonly=True)
    margin = fields.Float("Margin", readonly=True)
    product_uom_qty = fields.Float("Ordered Qty", readonly=True)
    qty_delivered = fields.Float("Delivered Qty", readonly=True)
    qty_invoiced = fields.Float("Invoiced Qty", readonly=True)
    product_id = fields.Many2one("product.product", "Product", readonly=True)
    partner_id = fields.Many2one("res.partner", "Partner", readonly=True)
    user_id = fields.Many2one("res.users", "Salesperson", readonly=True)
    company_id = fields.Many2one("res.company", "Company", readonly=True)
    team_id = fields.Many2one("crm.team", "Sales Team", readonly=True)

    # NOTE: This 'source_type' field is purely internal for identifying the record source ('sale' or 'pos').
    source_type = fields.Selection(
        [("sale", "Sale"), ("pos", "PoS")], string="Source Type", readonly=True
    )

    def _select_sale(self):
        """SQL SELECT statement for Sale Order Lines."""
        return """
            SELECT
                -- Create a synthetic unique ID for the report view
                ('sale' || l.id) AS id,
                s.date_order AS date_order,
                l.price_subtotal AS price_subtotal,
                l.price_unit AS price_unit,
                l.margin AS margin,
                l.product_uom_qty AS product_uom_qty,
                l.qty_delivered AS qty_delivered,
                l.qty_invoiced AS qty_invoiced,
                l.product_id AS product_id,
                s.partner_id AS partner_id,
                s.user_id AS user_id,
                s.company_id AS company_id,
                s.team_id AS team_id,
                s.name AS order_ref,
                'sale' AS source_type
            FROM
                sale_order_line l
            INNER JOIN
                sale_order s ON (l.order_id = s.id)
            WHERE
                s.state IN ('sale', 'done')
        """

    def _select_pos(self):
        """SQL SELECT statement for POS Order Lines."""
        # PoS lines are simpler: qty is used for ordered, delivered, and invoiced qty concepts.
        return """
            SELECT
                ('pos' || l.id) AS id, -- Ensure unique ID 
                p.date_order AS date_order,
                l.price_subtotal AS price_subtotal,
                l.price_unit AS price_unit,
                (l.price_subtotal - (l.qty * pp.standard_price::numeric)) AS margin,
                l.qty AS product_uom_qty,
                l.qty AS qty_delivered,
                l.qty AS qty_invoiced,
                l.product_id AS product_id,
                p.partner_id AS partner_id,
                p.user_id AS user_id,
                p.company_id AS company_id,
                NULL::integer AS team_id, -- Using NULL::integer for type matching
                p.name AS order_ref,
                'pos' AS source_type
            FROM
                pos_order_line l
            INNER JOIN
                pos_order p ON (l.order_id = p.id)
            INNER JOIN
                product_product pp ON (l.product_id = pp.id)
            WHERE
                p.state IN ('paid', 'done', 'invoiced')
        """

    def _query(self):
        """The combined UNION ALL query."""
        return f"""
            {self._select_sale()}
            UNION ALL
            {self._select_pos()}
        """

    def init(self):
        """Create or replace the SQL view on module installation/update."""
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS
            (
                {self._query()}
            )
        """)
