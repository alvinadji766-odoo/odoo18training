import base64
import json
import logging
import requests
from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PokemonFetchWizard(models.TransientModel):
    _name = 'pokemon.fetch.wizard'
    _description = 'Wizard Fetch Data Pokemon dari REST API'

    pokemon_query = fields.Char(
        string='Pokemon Name or ID',
        required=True,
        default='pikachu',
        help='Masukkan nama Pokemon (misal: pikachu, charizard, bulbasaur) atau ID Pokédex (misal: 25, 6, 1)'
    )
    api_source = fields.Selection([
        ('live', '🌐 Live Public PokeAPI (pokeapi.co)'),
        ('mock', '💾 Mock / Offline Simulation'),
    ], string='Sumber API', default='live', required=True)

    def action_fetch_and_create(self):
        """
        Mengambil data dari PokeAPI (atau mock), lalu menyimpan hasilnya
        ke dalam model pokemon.pokemon dan langsung membuka form view-nya.
        """
        self.ensure_one()
        query = (self.pokemon_query or '').strip().lower()
        if not query:
            raise UserError("Silakan masukkan nama atau ID Pokemon terlebih dahulu.")

        # 1. Ambil data dari API atau simulasi Mock
        if self.api_source == 'live':
            data = self._fetch_from_pokeapi(query)
        else:
            data = self._get_mock_pokemon(query)

        # 2. Parsing dan susun field yang dibutuhkan
        pokemon_vals = self._parse_pokemon_payload(data)

        # 3. Buat atau update record di Odoo
        pokemon_model = self.env['pokemon.pokemon']
        existing = pokemon_model.search([
            '|',
            ('pokedex_id', '=', pokemon_vals.get('pokedex_id')),
            ('name', '=ilike', pokemon_vals.get('name'))
        ], limit=1)

        if existing:
            existing.write(pokemon_vals)
            pokemon_record = existing
            msg = f"🔄 Pokemon <b>{pokemon_record.name}</b> berhasil diperbarui dari REST API."
        else:
            pokemon_record = pokemon_model.create(pokemon_vals)
            msg = f"🎉 Pokemon baru <b>{pokemon_record.name}</b> (#{pokemon_record.pokedex_id}) berhasil ditambahkan dari REST API!"

        pokemon_record.message_post(body=msg)

        # 4. Tampilkan langsung form view Pokemon yang baru dibuat/diupdate
        return {
            'name': pokemon_record.name,
            'type': 'ir.actions.act_window',
            'res_model': 'pokemon.pokemon',
            'res_id': pokemon_record.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # =========================================================================
    # HELPER PEMANGGILAN API & PARSING DATA
    # =========================================================================
    def _fetch_from_pokeapi(self, query):
        """Memanggil REST API publik pokeapi.co"""
        endpoint = f"https://pokeapi.co/api/v2/pokemon/{query}"
        try:
            resp = requests.get(endpoint, timeout=10)
            if resp.status_code == 404:
                raise UserError(f"Pokemon '{query}' tidak ditemukan di PokeAPI (HTTP 404). Cek ejaan nama atau nomor ID.")
            if resp.status_code != 200:
                raise UserError(f"Gagal mengambil data dari PokeAPI. Kode Status: {resp.status_code}")
            return resp.json()
        except requests.exceptions.ConnectionError:
            raise UserError(
                "Tidak dapat terhubung ke internet untuk mengakses PokeAPI! "
                "Silakan pilih opsi '💾 Mock / Offline Simulation' untuk mencoba secara offline."
            )
        except requests.exceptions.Timeout:
            raise UserError("Koneksi ke PokeAPI timeout. Coba beberapa saat lagi.")

    def _parse_pokemon_payload(self, data):
        """Mengekstrak data JSON PokeAPI ke dalam dictionary Odoo vals"""
        # Parsing tipe (misal: "Electric" atau "Fire / Flying")
        types_list = [t['type']['name'].capitalize() for t in data.get('types', []) if 'type' in t]
        types_str = " / ".join(types_list) if types_list else "Unknown"

        # Parsing ability
        abilities_list = [a['ability']['name'].replace('-', ' ').title() for a in data.get('abilities', []) if 'ability' in a]
        abilities_str = ", ".join(abilities_list) if abilities_list else "-"

        # Parsing stats
        stats_dict = {}
        for s in data.get('stats', []):
            stat_name = s.get('stat', {}).get('name', '')
            val = s.get('base_stat', 0)
            if stat_name in ['hp', 'attack', 'defense', 'speed']:
                stats_dict[stat_name] = val

        # Sprite image
        sprites = data.get('sprites', {})
        other_art = sprites.get('other', {}).get('official-artwork', {})
        img_url = other_art.get('front_default') or sprites.get('front_default')

        image_base64 = False
        if img_url:
            try:
                img_res = requests.get(img_url, timeout=10)
                if img_res.status_code == 200:
                    image_base64 = base64.b64encode(img_res.content)
            except Exception as e:
                _logger.warning("Gagal mengunduh gambar Pokemon: %s", e)

        return {
            'name': data.get('name', '').title(),
            'pokedex_id': data.get('id', 0),
            'height': (data.get('height', 0) * 0.1),
            'weight': (data.get('weight', 0) * 0.1),
            'base_experience': data.get('base_experience', 0),
            'types': types_str,
            'abilities': abilities_str,
            'hp': stats_dict.get('hp', 0),
            'attack': stats_dict.get('attack', 0),
            'defense': stats_dict.get('defense', 0),
            'speed': stats_dict.get('speed', 0),
            'image_url': img_url or False,
            'image': image_base64,
        }

    def _get_mock_pokemon(self, query):
        """Simulasi data offline jika server tanpa internet"""
        mock_database = {
            'pikachu': {
                'id': 25,
                'name': 'pikachu',
                'height': 4,
                'weight': 60,
                'base_experience': 112,
                'types': [{'type': {'name': 'electric'}}],
                'abilities': [{'ability': {'name': 'static'}}, {'ability': {'name': 'lightning-rod'}}],
                'stats': [
                    {'stat': {'name': 'hp'}, 'base_stat': 35},
                    {'stat': {'name': 'attack'}, 'base_stat': 55},
                    {'stat': {'name': 'defense'}, 'base_stat': 40},
                    {'stat': {'name': 'speed'}, 'base_stat': 90},
                ],
                'sprites': {'front_default': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/25.png'}
            },
            'charizard': {
                'id': 6,
                'name': 'charizard',
                'height': 17,
                'weight': 905,
                'base_experience': 267,
                'types': [{'type': {'name': 'fire'}}, {'type': {'name': 'flying'}}],
                'abilities': [{'ability': {'name': 'blaze'}}, {'ability': {'name': 'solar-power'}}],
                'stats': [
                    {'stat': {'name': 'hp'}, 'base_stat': 78},
                    {'stat': {'name': 'attack'}, 'base_stat': 84},
                    {'stat': {'name': 'defense'}, 'base_stat': 78},
                    {'stat': {'name': 'speed'}, 'base_stat': 100},
                ],
                'sprites': {'front_default': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/6.png'}
            }
        }
        return mock_database.get(query, {
            'id': 1,
            'name': query or 'bulbasaur',
            'height': 7,
            'weight': 69,
            'base_experience': 64,
            'types': [{'type': {'name': 'grass'}}, {'type': {'name': 'poison'}}],
            'abilities': [{'ability': {'name': 'overgrow'}}],
            'stats': [
                {'stat': {'name': 'hp'}, 'base_stat': 45},
                {'stat': {'name': 'attack'}, 'base_stat': 49},
                {'stat': {'name': 'defense'}, 'base_stat': 49},
                {'stat': {'name': 'speed'}, 'base_stat': 45},
            ],
            'sprites': {'front_default': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/1.png'}
        })
