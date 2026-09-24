import json
import logging
from odoo import http
from odoo.http import request, Response
from odoo.exceptions import AccessDenied, AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)


class MovieSessionApiController(http.Controller):
    """
    Controller REST API untuk JPFA Movie menggunakan Autentikasi Bawaan Odoo (Session-Based).
    
    Fitur Utama:
    1. Login & Logout via Odoo Session (request.session.authenticate).
    2. Endpoint berjalan dengan hak akses User Odoo (ACL, Groups, dan Record Rules aktif).
    3. Tidak menggunakan .sudo(), sehingga keamanan mengikuti user yang sedang login.
    4. Mengembalikan response berstandar JSON murni (status 401 JSON jika session kadaluarsa/belum login).
    """

    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    def _json_response(self, data, status=200):
        """Helper untuk menghasilkan respon HTTP JSON berstandar REST API"""
        return Response(
            json.dumps(data, indent=2, default=str),
            status=status,
            mimetype='application/json'
        )

    def _check_auth(self):
        """
        Validasi apakah client memiliki session Odoo aktif (bukan anonymous / public user).
        Jika belum login, kembalikan HTTP 401 JSON agar ramah untuk Frontend / Mobile Client.
        """
        user = request.env.user
        if not request.session.uid or (hasattr(user, '_is_public') and user._is_public()):
            return False, self._json_response({
                'status': 'error',
                'code': 401,
                'message': 'Autentikasi dibutuhkan. Harap login terlebih dahulu via POST /api/v2/auth/login'
            }, status=401)
        return True, None

    # =========================================================================
    # 1. AUTHENTICATION ENDPOINTS (LOGIN, LOGOUT, ME)
    # =========================================================================

    @http.route('/api/v2/auth/login', type='http', auth='none', methods=['POST'], csrf=False)
    def api_login(self, **kwargs):
        """
        POST /api/v2/auth/login
        Login menggunakan kredensial user Odoo (Database, Login/Email, Password).
        Odoo akan secara otomatis menyertakan Cookie 'session_id' di header respon (Set-Cookie).

        Payload JSON:
        {
            "db": "odoo18training",
            "login": "admin",
            "password": "1"
        }
        """
        try:
            payload = json.loads(request.httprequest.data or '{}')
        except Exception:
            return self._json_response({
                'status': 'error',
                'code': 400,
                'message': 'Format payload tidak valid. Harap kirimkan format JSON valid.'
            }, status=400)

        # Jika database tidak dikirim di body, gunakan db default dari request
        db = payload.get('db') or (request.env.cr.dbname if hasattr(request.env, 'cr') and request.env.cr else None)
        login = payload.get('login')
        password = payload.get('password')

        if not login or not password:
            return self._json_response({
                'status': 'error',
                'code': 400,
                'message': "Field 'login' dan 'password' wajib diisi."
            }, status=400)

        try:
            # Autentikasi native Odoo 18
            # Di Odoo 18, Session.authenticate menerima 2 parameter: db dan credential dict
            credential = {
                'login': login,
                'password': password,
                'type': 'password',
            }
            try:
                auth_res = request.session.authenticate(db, credential)
            except TypeError:
                # Fallback untuk versi lama (db, login, password)
                auth_res = request.session.authenticate(db, login, password)

            # Di Odoo 18, authenticate() mengembalikan dictionary: {'uid': <id>, 'auth_method': ..., 'mfa': ...}
            if isinstance(auth_res, dict):
                uid = auth_res.get('uid')
            elif isinstance(auth_res, int):
                uid = auth_res
            else:
                uid = request.session.uid

            uid = uid or request.session.uid
            if not uid:
                return self._json_response({
                    'status': 'error',
                    'code': 401,
                    'message': 'Login gagal: Kredensial tidak valid.'
                }, status=401)

            # Pastikan uid berupa integer agar browse() menghasilkan singleton record
            uid = int(uid)

            # Ambil data profil user yang berhasil login
            user = request.env['res.users'].sudo().browse(uid)
            return self._json_response({
                'status': 'success',
                'code': 200,
                'message': f"Selamat datang, {user.name}! Login berhasil.",
                'data': {
                    'uid': uid,
                    'name': user.name,
                    'login': user.login,
                    'email': user.email or '',
                    'company_id': user.company_id.id,
                    'company_name': user.company_id.name,
                    'session_id': request.session.sid, # Disimpan juga otomatis via Set-Cookie header
                }
            })
        except AccessDenied:
            return self._json_response({
                'status': 'error',
                'code': 401,
                'message': 'Username atau password salah.'
            }, status=401)
        except Exception as e:
            _logger.exception("Error saat login API:")
            return self._json_response({
                'status': 'error',
                'code': 500,
                'message': f"Terjadi kesalahan di server: {str(e)}"
            }, status=500)

    @http.route('/api/v2/auth/logout', type='http', auth='public', methods=['POST'], csrf=False)
    def api_logout(self, **kwargs):
        """
        POST /api/v2/auth/logout
        Logout dan menghancurkan session Odoo yang aktif.
        """
        try:
            request.session.logout(keep_db=True)
            return self._json_response({
                'status': 'success',
                'code': 200,
                'message': 'Logout berhasil. Sesi telah diakhiri.'
            })
        except Exception as e:
            return self._json_response({
                'status': 'error',
                'code': 500,
                'message': f"Gagal logout: {str(e)}"
            }, status=500)

    @http.route('/api/v2/auth/me', type='http', auth='public', methods=['GET'], csrf=False)
    def api_me(self, **kwargs):
        """
        GET /api/v2/auth/me
        Mengecek identitas user yang sedang aktif dalam session.
        """
        is_auth, err_resp = self._check_auth()
        if not is_auth:
            return err_resp

        user = request.env.user
        return self._json_response({
            'status': 'success',
            'code': 200,
            'data': {
                'uid': user.id,
                'name': user.name,
                'login': user.login,
                'email': user.email or '',
                'partner_id': user.partner_id.id,
                'is_system_admin': user.has_group('base.group_system'),
                'groups': [g.name for g in user.groups_id],
            }
        })

    # =========================================================================
    # 2. MOVIE ENDPOINTS (SESSION & USER PERMISSIONS BASED)
    # =========================================================================

    @http.route('/api/v2/movies', type='http', auth='public', methods=['GET'], csrf=False)
    def get_movies_list(self, **kwargs):
        """
        GET /api/v2/movies
        Menampilkan daftar film.
        Catatan: Query dijalankan langsung dengan hak akses user (tanpa sudo!).
        """
        is_auth, err_resp = self._check_auth()
        if not is_auth:
            return err_resp

        domain = [('active', '=', True)]

        search_query = kwargs.get('search')
        if search_query:
            domain.append(('name', 'ilike', search_query))

        state_filter = kwargs.get('state')
        if state_filter in ['draft', 'released']:
            domain.append(('state', '=', state_filter))

        limit = int(kwargs.get('limit', 20))
        offset = int(kwargs.get('offset', 0))

        try:
            movie_model = request.env['movie.movie']
            movies = movie_model.search(domain, limit=limit, offset=offset, order='id asc')
            total_count = movie_model.search_count(domain)

            data = []
            for m in movies:
                data.append({
                    'id': m.id,
                    'name': m.name,
                    'state': m.state,
                    'release_date': m.release_date,
                    'duration': m.duration,
                    'rating_star': m.rating,
                    'avg_rating': m.avg_rating,
                    'review_count': m.review_count,
                    'studio': m.studio_id.name if m.studio_id else None,
                    'genres': m.genre_ids.mapped('name'),
                })

            return self._json_response({
                'status': 'success',
                'code': 200,
                'user': request.env.user.name,
                'meta': {
                    'total': total_count,
                    'limit': limit,
                    'offset': offset,
                    'returned': len(data),
                },
                'data': data
            })
        except AccessError as e:
            return self._json_response({
                'status': 'error',
                'code': 403,
                'message': f"Akses ditolak oleh Odoo Security Rules: {str(e)}"
            }, status=403)
        except Exception as e:
            return self._json_response({
                'status': 'error',
                'code': 500,
                'message': f"Kesalahan server: {str(e)}"
            }, status=500)

    @http.route('/api/v2/movies/<int:movie_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_movie_detail(self, movie_id, **kwargs):
        """
        GET /api/v2/movies/<id>
        Mengambil detail satu film berdasarkan ID.
        """
        is_auth, err_resp = self._check_auth()
        if not is_auth:
            return err_resp

        try:
            movie = request.env['movie.movie'].browse(movie_id)
            if not movie.exists():
                return self._json_response({
                    'status': 'error',
                    'code': 404,
                    'message': f"Film ID {movie_id} tidak ditemukan."
                }, status=404)

            reviews = [{
                'id': rev.id,
                'author': rev.name,
                'score': rev.score,
                'comment': rev.comment,
            } for rev in movie.review_ids]

            artists = [{
                'id': art.id,
                'name': art.name,
                'role': getattr(art, 'role', 'artist'),
            } for art in movie.artist_ids]

            data = {
                'id': movie.id,
                'name': movie.name,
                'state': movie.state,
                'release_date': movie.release_date,
                'duration': movie.duration,
                'synopsis': movie.synopsis,
                'rating_star': movie.rating,
                'avg_rating': movie.avg_rating,
                'review_count': movie.review_count,
                'studio': {
                    'id': movie.studio_id.id if movie.studio_id else None,
                    'name': movie.studio_id.name if movie.studio_id else None,
                },
                'genres': movie.genre_ids.mapped('name'),
                'cast_and_crew': artists,
                'reviews': reviews,
            }

            return self._json_response({'status': 'success', 'code': 200, 'data': data})
        except AccessError as e:
            return self._json_response({
                'status': 'error',
                'code': 403,
                'message': f"Akses ditolak: {str(e)}"
            }, status=403)

    @http.route('/api/v2/movies', type='http', auth='public', methods=['POST'], csrf=False)
    def create_movie(self, **kwargs):
        """
        POST /api/v2/movies
        Membuat record film baru dengan identitas user yang sedang login.
        """
        is_auth, err_resp = self._check_auth()
        if not is_auth:
            return err_resp

        try:
            payload = json.loads(request.httprequest.data or '{}')
        except Exception:
            return self._json_response({
                'status': 'error',
                'code': 400,
                'message': 'Format JSON tidak valid.'
            }, status=400)

        name = payload.get('name')
        if not name:
            return self._json_response({
                'status': 'error',
                'code': 400,
                'message': "Field 'name' wajib diisi."
            }, status=400)

        vals = {
            'name': name,
            'duration': payload.get('duration', 90),
            'release_date': payload.get('release_date') or False,
            'synopsis': payload.get('synopsis', ''),
            'rating': str(payload.get('rating', '0')),
            'state': 'draft',
        }

        try:
            # Create dieksekusi dengan user env aktif
            new_movie = request.env['movie.movie'].create(vals)
            new_movie.message_post(
                body=f"🎬 <b>Film dibuat via Session API</b> oleh user: <i>{request.env.user.name}</i>."
            )
            return self._json_response({
                'status': 'success',
                'code': 201,
                'message': f"Film '{new_movie.name}' berhasil dibuat.",
                'data': {
                    'id': new_movie.id,
                    'name': new_movie.name,
                    'duration': new_movie.duration,
                    'state': new_movie.state,
                }
            }, status=201)
        except AccessError as e:
            return self._json_response({
                'status': 'error',
                'code': 403,
                'message': f"User Anda tidak memiliki hak membuat record film: {str(e)}"
            }, status=403)
        except (UserError, ValidationError) as e:
            return self._json_response({'status': 'error', 'code': 400, 'message': str(e)}, status=400)
        except Exception as e:
            return self._json_response({'status': 'error', 'code': 500, 'message': str(e)}, status=500)

    @http.route('/api/v2/movies/<int:movie_id>', type='http', auth='public', methods=['PUT'], csrf=False)
    def update_movie(self, movie_id, **kwargs):
        """
        PUT /api/v2/movies/<id>
        Mengubah data film.
        """
        is_auth, err_resp = self._check_auth()
        if not is_auth:
            return err_resp

        try:
            payload = json.loads(request.httprequest.data or '{}')
        except Exception:
            return self._json_response({'status': 'error', 'code': 400, 'message': 'Format JSON tidak valid.'}, status=400)

        try:
            movie = request.env['movie.movie'].browse(movie_id)
            if not movie.exists():
                return self._json_response({'status': 'error', 'code': 404, 'message': f'Film ID {movie_id} tidak ditemukan.'}, status=404)

            # Filter field yang boleh diupdate via API
            allowed_fields = ['name', 'duration', 'release_date', 'synopsis', 'rating', 'state']
            vals = {k: v for k, v in payload.items() if k in allowed_fields}

            if not vals:
                return self._json_response({'status': 'error', 'code': 400, 'message': 'Tidak ada field valid untuk diupdate.'}, status=400)

            movie.write(vals)
            return self._json_response({
                'status': 'success',
                'code': 200,
                'message': f"Film '{movie.name}' berhasil diperbarui.",
                'data': {'id': movie.id, 'name': movie.name, 'state': movie.state}
            })
        except AccessError as e:
            return self._json_response({'status': 'error', 'code': 403, 'message': f"Akses ditolak: {str(e)}"}, status=403)
        except Exception as e:
            return self._json_response({'status': 'error', 'code': 500, 'message': str(e)}, status=500)

    @http.route('/api/v2/movies/<int:movie_id>/reviews', type='http', auth='public', methods=['POST'], csrf=False)
    def add_movie_review(self, movie_id, **kwargs):
        """
        POST /api/v2/movies/<id>/reviews
        Menambahkan review ke sebuah film sebagai user yang sedang login.
        """
        is_auth, err_resp = self._check_auth()
        if not is_auth:
            return err_resp

        try:
            payload = json.loads(request.httprequest.data or '{}')
        except Exception:
            return self._json_response({'status': 'error', 'code': 400, 'message': 'Format JSON tidak valid.'}, status=400)

        score = payload.get('score')
        comment = payload.get('comment', '')

        if score is None:
            return self._json_response({'status': 'error', 'code': 400, 'message': "Field 'score' wajib diisi (1-10)."}, status=400)

        try:
            movie = request.env['movie.movie'].browse(movie_id)
            if not movie.exists():
                return self._json_response({'status': 'error', 'code': 404, 'message': f'Film ID {movie_id} tidak ditemukan.'}, status=404)

            # Review dibuat atas nama user yang sedang login
            reviewer_name = request.env.user.name
            review = request.env['movie.review'].create({
                'movie_id': movie.id,
                'score': float(score),
                'comment': comment,
            })

            movie.message_post(body=f"⭐ <b>Review Baru</b> ditambahkan oleh user <i>{reviewer_name}</i> (Skor: {score}).")

            return self._json_response({
                'status': 'success',
                'code': 201,
                'message': 'Review berhasil ditambahkan.',
                'data': {
                    'review_id': review.id,
                    'author': reviewer_name,
                    'score': review.score,
                    'comment': review.comment,
                    'movie_avg_rating': movie.avg_rating,
                }
            }, status=201)
        except AccessError as e:
            return self._json_response({'status': 'error', 'code': 403, 'message': f"Akses ditolak: {str(e)}"}, status=403)
        except Exception as e:
            return self._json_response({'status': 'error', 'code': 500, 'message': str(e)}, status=500)

