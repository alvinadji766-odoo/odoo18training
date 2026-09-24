import base64
import requests
import logging
from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class Pokemon(models.Model):
    _name = 'pokemon.pokemon'
    _description = 'Pokemon Monster Record'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'pokedex_id asc, name asc'

    name = fields.Char(string='Pokemon Name', required=True, tracking=True)
    pokedex_id = fields.Integer(string='Pokédex #', tracking=True, help='Nomor index Pokédex Nasional')
    
    # Dimensi Fisik (PokeAPI menyediakan decimeter & hectogram -> dikonversi ke m & kg)
    height = fields.Float(string='Height (m)', digits=(6, 2), help='Tinggi dalam meter')
    weight = fields.Float(string='Weight (kg)', digits=(6, 2), help='Berat dalam kilogram')
    base_experience = fields.Integer(string='Base Experience', help='Base XP saat dikalahkan/ditangkap')
    
    # Kategori & Karakteristik
    types = fields.Char(string='Type(s)', help='Elemen tipe Pokemon (misal: Grass / Poison)')
    abilities = fields.Char(string='Abilities', help='Kemampuan spesial Pokemon')
    
    # Base Stats Pokemon
    hp = fields.Integer(string='HP (Hit Points)')
    attack = fields.Integer(string='Attack')
    defense = fields.Integer(string='Defense')
    speed = fields.Integer(string='Speed')
    
    # Sprite Gambar (disimpan dalam bentuk binary base64 agar tampil di Odoo)
    image = fields.Image(string='Pokemon Image', max_width=512, max_height=512)
    image_url = fields.Char(string='Sprite URL')
    
    notes = fields.Text(string='Catatan Tambahan')

    def action_refetch_api(self):
        """
        Tombol untuk menyinkronkan ulang data Pokemon ini langsung dari PokeAPI.
        """
        self.ensure_one()
        query = str(self.pokedex_id or self.name).strip().lower()
        if not query:
            raise UserError("Nama atau Pokédex # tidak boleh kosong untuk melakukan sinkronisasi.")

        url = f"https://pokeapi.co/api/v2/pokemon/{query}"
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                self._update_from_api_data(data)
                self.message_post(body=f"🔄 <b>Sinkronisasi Sukses:</b> Data diperbarui dari PokeAPI ({url}).")
            else:
                raise UserError(f"Gagal mengambil data dari PokeAPI (HTTP Status: {res.status_code})")
        except requests.exceptions.RequestException as e:
            raise UserError(f"Terjadi kesalahan koneksi ke PokeAPI: {e}")

    def _update_from_api_data(self, data):
        """Helper untuk mem-parsing JSON PokeAPI dan memperbarui record"""
        # Parsing types (misal: "Grass, Poison")
        type_names = [t['type']['name'].capitalize() for t in data.get('types', []) if 'type' in t]
        
        # Parsing abilities (misal: "Overgrow, Chlorophyll")
        ability_names = [a['ability']['name'].replace('-', ' ').title() for a in data.get('abilities', []) if 'ability' in a]

        # Parsing base stats
        stats = {}
        for s in data.get('stats', []):
            stat_name = s.get('stat', {}).get('name', '')
            base_val = s.get('base_stat', 0)
            if stat_name == 'hp':
                stats['hp'] = base_val
            elif stat_name == 'attack':
                stats['attack'] = base_val
            elif stat_name == 'defense':
                stats['defense'] = base_val
            elif stat_name == 'speed':
                stats['speed'] = base_val

        # Ambil gambar sprite (default front sprite atau official artwork)
        sprites = data.get('sprites', {})
        other_artwork = sprites.get('other', {}).get('official-artwork', {})
        img_url = other_artwork.get('front_default') or sprites.get('front_default')

        vals = {
            'name': data.get('name', '').title(),
            'pokedex_id': data.get('id', 0),
            'height': (data.get('height', 0) * 0.1),  # decimeters to meters
            'weight': (data.get('weight', 0) * 0.1),  # hectograms to kg
            'base_experience': data.get('base_experience', 0),
            'types': " / ".join(type_names),
            'abilities': ", ".join(ability_names),
            'hp': stats.get('hp', 0),
            'attack': stats.get('attack', 0),
            'defense': stats.get('defense', 0),
            'speed': stats.get('speed', 0),
            'image_url': img_url or False,
        }

        # Download gambar jika ada URL
        if img_url:
            try:
                img_res = requests.get(img_url, timeout=10)
                if img_res.status_code == 200:
                    vals['image'] = base64.b64encode(img_res.content)
            except Exception as err:
                _logger.warning("Gagal mengunduh sprite Pokemon: %s", err)

        self.write(vals)
