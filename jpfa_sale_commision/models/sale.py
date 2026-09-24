from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # =========================================================================
    # FIELDS KOMISI & LATIHAN
    # =========================================================================
    commision_percent = fields.Float(string='Commission (%)', default=0.0)
    commision_nominal = fields.Float(string='Commission Nominal', compute='compute_nominal', store=True)

    # 1. FIELD UNTUK LATIHAN DOMAIN BASED ON MANY2MANY
    # partner_tag_ids: Many2many ke tags partner (res.partner.category)
    partner_tag_ids = fields.Many2many(
        'res.partner.category',
        string='Filter Partner Tags (M2M)',
        help='Pilih tag untuk memfilter partner di bawah'
    )
    # partner_custom_id: Many2one yang difilter oleh Many2many partner_tag_ids!
    # Pada res.partner, field tag bernama 'category_id' (Many2many)
    partner_custom_id = fields.Many2one(
        'res.partner',
        string='Partner Custom (Filtered by M2M)',
        domain="[('category_id', 'in', partner_tag_ids)]",
        help='Dropdown ini hanya menampilkan partner yang memiliki category_id yang ada di partner_tag_ids'
    )

    # =========================================================================
    # 2. @api.depends — COMPUTE FIELD (Slide 21)
    # =========================================================================
    @api.depends('commision_percent', 'amount_total')
    def compute_nominal(self):
        for rec in self:
            rec.commision_nominal = rec.amount_total * rec.commision_percent / 100

    def calculate_nominal(self):
        self.commision_nominal = self.amount_total * self.commision_percent / 100

    # =========================================================================
    # 3. @api.onchange — DYNAMIC UI UPDATES & WARNINGS (Slide 22)
    # =========================================================================
    @api.onchange('partner_id')
    def _onchange_partner_id_custom(self):
        """
        @api.onchange berjalan di sisi klien (in-memory sebelum save).
        Mengeset default komisi dan menampilkan popup warning jika partner tidak punya email.
        """
        print("=== [ONCHANGE] _onchange_partner_id_custom dipanggil ===")
        if self.partner_id:
            # Contoh: jika customer dari Indonesia (ID), beri default komisi 10%
            if self.partner_id.country_id.code == 'ID':
                self.commision_percent = 10.0

            # Warning dialog jika email kosong (sesuai Slide 22)
            if not self.partner_id.email:
                return {
                    'warning': {
                        'title': _("Missing Email"),
                        'message': _("Customer '%s' tidak memiliki alamat email yang tercatat!", self.partner_id.name)
                    }
                }

    @api.onchange('partner_custom_id')
    def _onchange_partner_custom_id(self):
        if self.partner_custom_id and not self.partner_id:
            self.partner_id = self.partner_custom_id

    # =========================================================================
    # 4. @api.constrains — SERVER-SIDE INTEGRITY VALIDATION (Slide 24)
    # =========================================================================
    @api.constrains('commision_percent')
    def _check_commision_percent(self):
        """
        @api.constrains dieksekusi di server saat create() dan write().
        Jika aturan dilanggar, lemparkan ValidationError untuk me-rollback database.
        """
        for rec in self:
            # Komisi tidak boleh > 50% (sesuai Slide 24 contoh discount limit)
            if rec.commision_percent > 50.0:
                raise ValidationError(_(
                    "Komisi tidak boleh melebihi 50%%! (Nilai saat ini: %.2f%%)",
                    rec.commision_percent
                ))
            if rec.commision_percent < 0.0:
                raise ValidationError(_("Komisi tidak boleh bernilai negatif!"))

    # =========================================================================
    # 5. CRUD OVERRIDE: create() with @api.model_create_multi (Slide 25)
    # =========================================================================
    @api.model_create_multi
    def create(self, vals_list):
        """
        create(vals_list):
        - Menerima list of dicts (batch creation modern Odoo 17/18).
        - Injeksi nilai default sebelum memanggil super().create(vals_list).
        """
        print("=== [CREATE OVERRIDE] Eksekusi create untuk %d record ===" % len(vals_list))
        # Jangan timpa jika dipanggil dari proses copy/duplicate
        if not self.env.context.get('is_copy'):
            for vals in vals_list:
                # Cek apakah field tidak diisi user (tidak mengecek falsy agar 0.0 tidak tertimpa)
                if 'commision_percent' not in vals:
                    vals['commision_percent'] = 2.5
        
        # Panggil super() untuk menjalankan proses insert standar Odoo
        records = super().create(vals_list)
        print("=== [CREATE OVERRIDE] Berhasil membuat SO: %s ===" % records.mapped('name'))
        return records

    # =========================================================================
    # 6. CRUD OVERRIDE: write() — Protection & Intercept (Slide 3 & 4)
    # =========================================================================
    def write(self, vals):
        """
        write(vals):
        - Dieksekusi setiap kali ada perubahan data (update).
        - Proteksi: Jika Sale Order sudah 'sale' (Confirmed), komisi tidak boleh diubah!
        """
        print("=== [WRITE OVERRIDE] Field yang diubah:", vals)
        for rec in self:
            if rec.state == 'sale' and 'commision_percent' in vals:
                raise UserError(_(
                    "Perubahan Ditolak! Komisi tidak boleh diubah pada Sale Order '%s' yang sudah Confirmed!",
                    rec.name
                ))
        return super().write(vals)

    # =========================================================================
    # 7. CRUD OVERRIDE: unlink() — Delete Protection (Slide 3)
    # =========================================================================
    def unlink(self):
        """
        unlink():
        - Dieksekusi saat record akan dihapus.
        - Proteksi: Hanya status 'draft' dan 'cancel' yang boleh dihapus.
        """
        print("=== [UNLINK OVERRIDE] Menghapus record ID:", self.ids)
        for rec in self:
            if rec.state not in ('draft', 'cancel'):
                raise UserError(_(
                    "Hanya Sale Order dengan status 'Quotation (Draft)' atau 'Cancelled' yang boleh dihapus!\n"
                    "Order '%s' saat ini berstatus '%s'.",
                    rec.name, rec.state
                ))
        return super().unlink()

    # =========================================================================
    # 8. CRUD OVERRIDE: copy() — Duplicate Customization (Slide 26)
    # =========================================================================
    def copy(self, default=None):
        """
        copy(default):
        - Dieksekusi saat menekan Action -> Duplicate.
        - Reset persentase komisi menjadi 0 pada dokumen hasil duplikasi.
        """
        self.ensure_one()
        print("=== [COPY OVERRIDE] Menduplikasi record ID:", self.id)
        default = dict(default or {})
        default['commision_percent'] = 0.0
        return super(SaleOrder, self.with_context(is_copy=True)).copy(default)

    # =========================================================================
    # 9. @api.model — RECORD-INDEPENDENT METHOD (Slide 23)
    # =========================================================================
    @api.model
    def get_default_commission_rate(self):
        """Method level model (independen tanpa record ID)."""
        return 5.0

    # =========================================================================
    # 10. METHOD LATIHAN ORM & NATIVE SQL (Slide 6, 7, 8, 9)
    # =========================================================================
    def coba_orm(self):
        # 1. Search dengan domain
        movie = self.env['movie.movie'].search([('rating', '=', '5')]) if 'movie.movie' in self.env else []
        so = self.env['sale.order'].search([('state', '=', 'sale')])
        print("=== COBA ORM SEARCH ===")
        print("SO Confirmed count:", len(so))
        for r in so[:3]:
            print("  •", r.name, "| Partner:", r.partner_id.name, "| Amount:", r.amount_total)

        # 2. Browse dengan list ID (Slide 7)
        if so:
            get_ids = so[:2].ids
            so_browse = self.env['sale.order'].browse(get_ids)
            print("Browse IDs:", get_ids, "->", so_browse)

    def coba_query(self):
        # Parameterized SQL query (Slide 8)
        self.env.cr.execute("SELECT id, name FROM res_partner WHERE is_company = %s LIMIT 3", (True,))
        rows = self.env.cr.fetchall()
        print("=== COBA SQL FETCHALL ===")
        print(rows)

        self.env.cr.execute("SELECT COUNT(*) FROM sale_order WHERE state = %s", ('sale',))
        count = self.env.cr.fetchone()[0]
        print("Total Confirmed SO (via SQL count):", count)
        # raise ValidationError(rows)

    # =========================================================================
    # 11. METODE BISNIS DENGAN UNSUR ORM (Slide 6, 7, 15, 16)
    # =========================================================================
    def action_apply_loyalty_commission(self):
        """
        Unsur ORM yang digunakan:
        1. self.env['sale.order'].search(domain) -> Memfilter recordset database
        2. .mapped('amount_total') -> Mengambil list nilai field dari recordset
        3. sum() agregasi Python
        4. self.env['res.partner'].browse(id) -> Mengakses objek partner
        """
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("Silakan pilih Customer terlebih dahulu sebelum menghitung komisi!"))

        # ORM Search: Cari semua order confirmed milik customer ini sebelumnya
        domain = [
            ('partner_id', '=', self.partner_id.id),
            ('state', '=', 'sale'),
            ('id', '!=', self.id)
        ]
        past_orders = self.env['sale.order'].search(domain)
        
        # Agregasi ORM menggunakan mapped()
        total_spent = sum(past_orders.mapped('amount_total'))
        order_count = len(past_orders)

        print(f"=== [ORM LOGIC] Customer: {self.partner_id.name} ===")
        print(f"Total Histori Order Confirmed: {order_count} order(s), Nominal: Rp {total_spent:,.2f}")

        # Aturan bisnis: Jika total belanja >= 10 juta ATAU sudah >= 3 order, beri komisi 15%
        if total_spent >= 10000000 or order_count >= 3:
            self.commision_percent = 15.0
            msg = _("🎉 Customer Loyal! Histori: %d order (Total: Rp %s). Komisi otomatis dinaikkan ke 15%%.", 
                    order_count, f"{total_spent:,.2f}")
        else:
            self.commision_percent = 5.0
            msg = _("ℹ️ Customer Reguler. Histori: %d order (Total: Rp %s). Komisi diset ke 5%%.", 
                    order_count, f"{total_spent:,.2f}")

        # Catat ke chatter SO
        self.message_post(body=msg)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Perhitungan Komisi Loyalitas (ORM)"),
                'message': msg,
                'sticky': False,
                'type': 'success',
            }
        }

    def action_find_similar_orders(self):
        """
        Unsur ORM yang digunakan:
        1. expression.OR & expression.AND (Slide 16: Dynamic Domain Builder)
        2. self.env['sale.order'].search(final_domain, limit=10)
        3. Menampilkan view action dinamis berdasarkan domain hasil kalkulasi
        """
        self.ensure_one()
        from odoo.osv import expression

        # Kondisi A: Customer yang sama
        dom_a = [('partner_id', '=', self.partner_id.id)]
        
        # Kondisi B: Rentang nominal yang mirip (+/- 30%)
        min_amount = self.amount_total * 0.7
        max_amount = self.amount_total * 1.3
        dom_b = [('amount_total', '>=', min_amount), ('amount_total', '<=', max_amount)]

        # Gabungkan secara dinamis: (A OR B) AND state == 'sale'
        combined_dom = expression.OR([dom_a, dom_b])
        final_domain = expression.AND([combined_dom, [('state', '=', 'sale')]])

        print("=== [DYNAMIC DOMAIN ORM] Generated Domain:", final_domain)
        similar_orders = self.env['sale.order'].search(final_domain, limit=10)
        print("Ditemukan %d order serupa:" % len(similar_orders))

        return {
            'name': _("Similar Orders (Dynamic Domain ORM)"),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': final_domain,
            'target': 'current',
        }

