import unittest
from unittest.mock import patch

from app import create_app, db
from app.models.user import User
from app.services.location_service import (
    extract_reliable_ward,
    normalize_city_name,
    normalize_district_name,
    normalize_state_name,
    reverse_geocode_coordinates,
)


class LocationReverseGeocodeTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.citizen = User(
            role='citizen',
            full_name='Loc Citizen',
            email='loc.citizen@civic.gov',
            mobile_number='9866611100',
            is_active=True,
        )
        self.citizen.set_password('Citizen@123')
        db.session.add(self.citizen)
        db.session.commit()

        with self.client.session_transaction() as sess:
            sess['user_id'] = self.citizen.id
            sess['role'] = 'citizen'
            sess['user_role'] = 'citizen'

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_english_and_tamil_normalization_and_taluk_inference(self):
        self.assertEqual(normalize_state_name('தமிழ்நாடு'), 'Tamil Nadu')
        self.assertEqual(normalize_state_name('Tamil Nadu'), 'Tamil Nadu')
        self.assertEqual(normalize_district_name('Coimbatore District'), 'Coimbatore')
        self.assertEqual(normalize_district_name('கோயம்புத்தூர் மாவட்டம்'), 'Coimbatore')
        self.assertEqual(normalize_district_name('Kancheepuram District'), 'Kanchipuram')
        self.assertEqual(normalize_district_name('Tiruchirappalli District'), 'Tiruchirappalli')
        self.assertEqual(normalize_district_name('', 'Pollachi'), 'Coimbatore')
        self.assertEqual(normalize_district_name('Tambaram Taluk'), 'Chengalpattu')
        self.assertEqual(normalize_district_name('Bengaluru Urban District'), 'Bengaluru Urban')
        self.assertEqual(normalize_city_name('பொள்ளாச்சி'), 'Pollachi')
        self.assertEqual(normalize_city_name('Chennai'), 'Greater Chennai Corporation')

    def test_strict_ward_extraction_never_guesses(self):
        self.assertEqual(extract_reliable_ward('Ward 42, Zone IV'), 'Ward 42')
        self.assertEqual(extract_reliable_ward('Division No. 18'), 'Ward 18')
        self.assertIsNone(extract_reliable_ward('Coimbatore Corporation, Gandhipuram'))
        self.assertIsNone(extract_reliable_ward(''))

    def test_pollachi_and_other_indian_states_reverse_geocode(self):
        def fake_pollachi(url, timeout=4.5):
            if 'nominatim' in url:
                return {
                    'name': 'Pollachi Bus Stand',
                    'address': {
                        'state': 'Tamil Nadu',
                        'state_district': 'Coimbatore District',
                        'town': 'Pollachi',
                        'suburb': 'Mahalingapuram',
                        'road': 'Udumalpet Road',
                        'house_number': '18',
                        'amenity': 'Pollachi Municipal Office',
                        'postcode': '642001',
                    },
                }
            return {}

        res = reverse_geocode_coordinates(10.6589, 77.0087, fetcher=fake_pollachi)
        self.assertTrue(res['success'])
        self.assertEqual(res['state'], 'Tamil Nadu')
        self.assertEqual(res['district'], 'Coimbatore')
        self.assertEqual(res['city'], 'Pollachi')
        self.assertEqual(res['pincode'], '642001')
        self.assertEqual(res['locality'], 'Mahalingapuram')
        self.assertEqual(res['street_name'], '18 Udumalpet Road')
        self.assertEqual(res['landmark'], 'Pollachi Municipal Office')
        self.assertIsNone(res['ward_number'])

        def fake_bengaluru_with_ward(url, timeout=4.5):
            if 'nominatim' in url:
                return {
                    'address': {
                        'state': 'Karnataka',
                        'state_district': 'Bengaluru Urban District',
                        'city': 'Bengaluru',
                        'suburb': 'Indiranagar',
                        'road': '100 Feet Road',
                        'postcode': '560038',
                    },
                    'extratags': {'ward': '80'},
                }
            return {}

        res_blr = reverse_geocode_coordinates(12.9784, 77.6408, fetcher=fake_bengaluru_with_ward)
        self.assertTrue(res_blr['success'])
        self.assertEqual(res_blr['state'], 'Karnataka')
        self.assertEqual(res_blr['district'], 'Bengaluru Urban')
        self.assertEqual(res_blr['city'], 'BBMP (Bengaluru)')
        self.assertEqual(res_blr['ward_number'], 'Ward 80')
        self.assertEqual(res_blr['pincode'], '560038')

        def fake_chennai_neighbourhood_ward(url, timeout=4.5):
            if 'nominatim' in url:
                return {
                    'address': {
                        'state': 'Tamil Nadu',
                        'state_district': 'Chennai District',
                        'city': 'Chennai',
                        'neighbourhood': 'Ward 136',
                        'suburb': 'Zone 10 Kodambakkam',
                        'road': 'Gopathi Narayanaswami Road',
                        'postcode': '600017',
                    }
                }
            return {}

        res_chn = reverse_geocode_coordinates(13.0418, 80.2341, fetcher=fake_chennai_neighbourhood_ward)
        self.assertTrue(res_chn['success'])
        self.assertEqual(res_chn['state'], 'Tamil Nadu')
        self.assertEqual(res_chn['district'], 'Chennai')
        self.assertEqual(res_chn['city'], 'Greater Chennai Corporation')
        self.assertEqual(res_chn['ward_number'], 'Ward 136')
        self.assertEqual(res_chn['locality'], 'Zone 10 Kodambakkam')
        self.assertEqual(res_chn['pincode'], '600017')

    @patch('app.routes.api.reverse_geocode_coordinates')
    def test_api_reverse_geocode_endpoint_and_new_complaint_page(self, mock_rg):
        mock_rg.return_value = {
            'success': True,
            'latitude': '10.658900',
            'longitude': '77.008700',
            'state': 'Tamil Nadu',
            'district': 'Coimbatore',
            'city': 'Pollachi',
            'ward_number': None,
            'street_name': 'Udumalpet Road',
            'locality': 'Mahalingapuram',
            'landmark': '',
            'pincode': '642001',
        }
        bad = self.client.get('/api/reverse-geocode?lat=abc&lng=77')
        self.assertEqual(bad.status_code, 400)

        oob = self.client.get('/api/reverse-geocode?lat=120&lng=77')
        self.assertEqual(oob.status_code, 400)

        ok = self.client.get('/api/reverse-geocode?lat=10.6589&lng=77.0087')
        self.assertEqual(ok.status_code, 200)
        payload = ok.get_json()
        self.assertTrue(payload['success'])
        self.assertEqual(payload['district'], 'Coimbatore')
        self.assertEqual(payload['pincode'], '642001')

        page = self.client.get('/citizen/complaints/new')
        self.assertEqual(page.status_code, 200)
        html = page.get_data(as_text=True)
        self.assertIn('js/location.js', html)
        self.assertIn('initCivicLocationSelector', html)
        self.assertIn('id="wardInput" value=""', html)
        self.assertNotIn('id="wardSelect"', html)


if __name__ == '__main__':
    unittest.main()
