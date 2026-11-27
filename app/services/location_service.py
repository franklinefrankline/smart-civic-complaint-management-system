import json
import re
import urllib.parse
import urllib.request

# Canonical State mapping (English variants + Tamil script -> canonical English name)
STATE_ALIASES = {
    'tamil nadu': 'Tamil Nadu',
    'tamilnadu': 'Tamil Nadu',
    'tn': 'Tamil Nadu',
    'தமிழ்நாடு': 'Tamil Nadu',
    'தமிழ் நாடு': 'Tamil Nadu',
    'karnataka': 'Karnataka',
    'கர்நாடகா': 'Karnataka',
    'கர்நாடகம்': 'Karnataka',
    'kerala': 'Kerala',
    'கேரளா': 'Kerala',
    'கேரளம்': 'Kerala',
    'andhra pradesh': 'Andhra Pradesh',
    'ஆந்திரப் பிரதேசம்': 'Andhra Pradesh',
    'ஆந்திர பிரதேசம்': 'Andhra Pradesh',
    'telangana': 'Telangana',
    'தெலுங்கானா': 'Telangana',
    'தெலங்கானா': 'Telangana',
    'puducherry': 'Puducherry',
    'pondicherry': 'Puducherry',
    'புதுச்சேரி': 'Puducherry',
    'பாண்டிச்சேரி': 'Puducherry',
    'maharashtra': 'Maharashtra',
    'delhi': 'Delhi',
    'nct of delhi': 'Delhi',
    'national capital territory of delhi': 'Delhi',
    'new delhi': 'Delhi',
    'gujarat': 'Gujarat',
    'rajasthan': 'Rajasthan',
    'uttar pradesh': 'Uttar Pradesh',
    'west bengal': 'West Bengal',
    'madhya pradesh': 'Madhya Pradesh',
    'bihar': 'Bihar',
    'odisha': 'Odisha',
    'orissa': 'Odisha',
    'punjab': 'Punjab',
    'haryana': 'Haryana',
    'assam': 'Assam',
    'jharkhand': 'Jharkhand',
    'chhattisgarh': 'Chhattisgarh',
    'goa': 'Goa',
    'uttarakhand': 'Uttarakhand',
    'himachal pradesh': 'Himachal Pradesh',
    'jammu and kashmir': 'Jammu and Kashmir',
    'chandigarh': 'Chandigarh',
}

# Canonical District aliases (English spellings + Tamil script + subdistrict/taluk -> District)
DISTRICT_ALIASES = {
    # All 38 Tamil Nadu Districts (English + Tamil + common spelling variants)
    'chennai': 'Chennai',
    'madras': 'Chennai',
    'சென்னை': 'Chennai',
    'chengalpattu': 'Chengalpattu',
    'chengalpet': 'Chengalpattu',
    'செங்கல்பட்டு': 'Chengalpattu',
    'kanchipuram': 'Kanchipuram',
    'kancheepuram': 'Kanchipuram',
    'காஞ்சிபுரம்': 'Kanchipuram',
    'tiruvallur': 'Tiruvallur',
    'thiruvallur': 'Tiruvallur',
    'திருவள்ளூர்': 'Tiruvallur',
    'coimbatore': 'Coimbatore',
    'kovai': 'Coimbatore',
    'கோயம்புத்தூர்': 'Coimbatore',
    'கோவை': 'Coimbatore',
    'madurai': 'Madurai',
    'மதுரை': 'Madurai',
    'tiruchirappalli': 'Tiruchirappalli',
    'thiruchirappalli': 'Tiruchirappalli',
    'tiruchirapalli': 'Tiruchirappalli',
    'trichy': 'Tiruchirappalli',
    'trichinopoly': 'Tiruchirappalli',
    'திருச்சிராப்பள்ளி': 'Tiruchirappalli',
    'திருச்சி': 'Tiruchirappalli',
    'salem': 'Salem',
    'சேலம்': 'Salem',
    'tirunelveli': 'Tirunelveli',
    'thirunelveli': 'Tirunelveli',
    'nellai': 'Tirunelveli',
    'திருநெல்வேலி': 'Tirunelveli',
    'vellore': 'Vellore',
    'வேலூர்': 'Vellore',
    'erode': 'Erode',
    'ஈரோடு': 'Erode',
    'thanjavur': 'Thanjavur',
    'tanjore': 'Thanjavur',
    'தஞ்சாவூர்': 'Thanjavur',
    'tiruppur': 'Tiruppur',
    'tirupur': 'Tiruppur',
    'திருப்பூர்': 'Tiruppur',
    'dindigul': 'Dindigul',
    'திண்டுக்கல்': 'Dindigul',
    'thoothukudi': 'Thoothukudi',
    'tuticorin': 'Thoothukudi',
    'தூத்துக்குடி': 'Thoothukudi',
    'kanyakumari': 'Kanyakumari',
    'kanniyakumari': 'Kanyakumari',
    'nagercoil': 'Kanyakumari',
    'கன்னியாகுமரி': 'Kanyakumari',
    'நாகர்கோவில்': 'Kanyakumari',
    'cuddalore': 'Cuddalore',
    'கடலூர்': 'Cuddalore',
    'villupuram': 'Villupuram',
    'viluppuram': 'Villupuram',
    'விழுப்புரம்': 'Villupuram',
    'tiruvannamalai': 'Tiruvannamalai',
    'thiruvannamalai': 'Tiruvannamalai',
    'திருவண்ணாமலை': 'Tiruvannamalai',
    'namakkal': 'Namakkal',
    'நாமக்கல்': 'Namakkal',
    'karur': 'Karur',
    'கரூர்': 'Karur',
    'nagapattinam': 'Nagapattinam',
    'நாகப்பட்டினம்': 'Nagapattinam',
    'sivaganga': 'Sivaganga',
    'sivagangai': 'Sivaganga',
    'சிவகங்கை': 'Sivaganga',
    'virudhunagar': 'Virudhunagar',
    'விருதுநகர்': 'Virudhunagar',
    'ramanathapuram': 'Ramanathapuram',
    'ramnad': 'Ramanathapuram',
    'ராமநாதபுரம்': 'Ramanathapuram',
    'இராமநாதபுரம்': 'Ramanathapuram',
    'krishnagiri': 'Krishnagiri',
    'கிருஷ்ணகிரி': 'Krishnagiri',
    'dharmapuri': 'Dharmapuri',
    'தர்மபுரி': 'Dharmapuri',
    'தருமபுரி': 'Dharmapuri',
    'pudukkottai': 'Pudukkottai',
    'pudukottai': 'Pudukkottai',
    'புதுக்கோட்டை': 'Pudukkottai',
    'theni': 'Theni',
    'தேனி': 'Theni',
    'nilgiris': 'Nilgiris',
    'the nilgiris': 'Nilgiris',
    'nilgiri': 'Nilgiris',
    'நீலகிரி': 'Nilgiris',
    'udhagamandalam': 'Nilgiris',
    'ooty': 'Nilgiris',
    'perambalur': 'Perambalur',
    'பெரம்பலூர்': 'Perambalur',
    'ariyalur': 'Ariyalur',
    'அரியலூர்': 'Ariyalur',
    'tiruvarur': 'Tiruvarur',
    'thiruvarur': 'Tiruvarur',
    'திருவாரூர்': 'Tiruvarur',
    'ranipet': 'Ranipet',
    'ராணிப்பேட்டை': 'Ranipet',
    'tirupathur': 'Tirupathur',
    'tirupattur': 'Tirupathur',
    'திருப்பத்தூர்': 'Tirupathur',
    'kallakurichi': 'Kallakurichi',
    'கள்ளக்குறிச்சி': 'Kallakurichi',
    'tenkasi': 'Tenkasi',
    'தென்காசி': 'Tenkasi',
    'mayiladuthurai': 'Mayiladuthurai',
    'மயிலாடுதுறை': 'Mayiladuthurai',
    # Major Taluk / Municipal Sub-units -> Parent Tamil Nadu District
    'pollachi': 'Coimbatore',
    'பொள்ளாச்சி': 'Coimbatore',
    'mettupalayam': 'Coimbatore',
    'valparai': 'Coimbatore',
    'sulur': 'Coimbatore',
    'kinathukadavu': 'Coimbatore',
    'tambaram': 'Chengalpattu',
    'தாம்பரம்': 'Chengalpattu',
    'pallavaram': 'Chengalpattu',
    'maraimalai nagar': 'Chengalpattu',
    'sriperumbudur': 'Kanchipuram',
    'kundrathur': 'Kanchipuram',
    'avadi': 'Tiruvallur',
    'ஆவடி': 'Tiruvallur',
    'poonamallee': 'Tiruvallur',
    'tiruttani': 'Tiruvallur',
    'ambattur': 'Chennai',
    'sholinganallur': 'Chennai',
    'kumbakonam': 'Thanjavur',
    'கும்பகோணம்': 'Thanjavur',
    'hosur': 'Krishnagiri',
    'ஓசூர்': 'Krishnagiri',
    'gobichettipalayam': 'Erode',
    'bhavani': 'Erode',
    'attur': 'Salem',
    'mettur': 'Salem',
    'srirangam': 'Tiruchirappalli',
    'sivakasi': 'Virudhunagar',
    'karaikudi': 'Sivaganga',
    'palani': 'Dindigul',
    'kodaikanal': 'Dindigul',
    'ambasamudram': 'Tirunelveli',
    'gudiyatham': 'Vellore',
    'katpadi': 'Vellore',
    'neyveli': 'Cuddalore',
    'chidambaram': 'Cuddalore',
    # Other Major Indian States / Districts
    'bengaluru urban': 'Bengaluru Urban',
    'bangalore urban': 'Bengaluru Urban',
    'bangalore': 'Bengaluru Urban',
    'bengaluru': 'Bengaluru Urban',
    'bengaluru rural': 'Bengaluru Rural',
    'mysuru': 'Mysuru',
    'mysore': 'Mysuru',
    'dakshina kannada': 'Mangaluru',
    'mangaluru': 'Mangaluru',
    'mangalore': 'Mangaluru',
    'thiruvananthapuram': 'Thiruvananthapuram',
    'trivandrum': 'Thiruvananthapuram',
    'ernakulam': 'Ernakulam',
    'kochi': 'Ernakulam',
    'cochin': 'Ernakulam',
    'kozhikode': 'Kozhikode',
    'calicut': 'Kozhikode',
    'thrissur': 'Thrissur',
    'visakhapatnam': 'Visakhapatnam',
    'vizag': 'Visakhapatnam',
    'vijayawada': 'NTR',
    'krishna': 'Krishna',
    'ntr': 'NTR',
    'guntur': 'Guntur',
    'tirupati': 'Tirupati',
    'hyderabad': 'Hyderabad',
    'rangareddy': 'Rangareddy',
    'ranga reddy': 'Rangareddy',
    'medchal malkajgiri': 'Medchal-Malkajgiri',
    'medchal-malkajgiri': 'Medchal-Malkajgiri',
    'puducherry': 'Puducherry',
    'pondicherry': 'Puducherry',
    'karaikal': 'Karaikal',
    'mumbai': 'Mumbai',
    'mumbai city': 'Mumbai',
    'mumbai suburban': 'Mumbai',
    'pune': 'Pune',
    'thane': 'Thane',
    'nagpur': 'Nagpur',
    'new delhi': 'New Delhi',
    'central delhi': 'Central Delhi',
    'south delhi': 'South Delhi',
    'north delhi': 'North Delhi',
    'ahmedabad': 'Ahmedabad',
    'surat': 'Surat',
    'vadodara': 'Vadodara',
    'jaipur': 'Jaipur',
    'lucknow': 'Lucknow',
    'kanpur nagar': 'Kanpur Nagar',
    'varanasi': 'Varanasi',
    'kolkata': 'Kolkata',
    'howrah': 'Howrah',
    'indore': 'Indore',
    'bhopal': 'Bhopal',
    'patna': 'Patna',
    'khordha': 'Khordha',
    'bhubaneswar': 'Khordha',
    'chandigarh': 'Chandigarh',
}

CITY_ALIASES = {
    'chennai': 'Greater Chennai Corporation',
    'greater chennai': 'Greater Chennai Corporation',
    'greater chennai corporation': 'Greater Chennai Corporation',
    'சென்னை': 'Greater Chennai Corporation',
    'பெருநகர சென்னை மாநகராட்சி': 'Greater Chennai Corporation',
    'coimbatore': 'Coimbatore Corporation',
    'coimbatore corporation': 'Coimbatore Corporation',
    'கோயம்புத்தூர்': 'Coimbatore Corporation',
    'pollachi': 'Pollachi',
    'பொள்ளாச்சி': 'Pollachi',
    'mettupalayam': 'Mettupalayam',
    'valparai': 'Valparai',
    'tambaram': 'Tambaram Corporation',
    'tambaram corporation': 'Tambaram Corporation',
    'தாம்பரம்': 'Tambaram Corporation',
    'chengalpattu': 'Chengalpattu Municipality',
    'pallavaram': 'Pallavaram',
    'kanchipuram': 'Kanchipuram Corporation',
    'avadi': 'Avadi Corporation',
    'madurai': 'Madurai Corporation',
    'மதுரை': 'Madurai Corporation',
    'tiruchirappalli': 'Tiruchirappalli Corporation',
    'trichy': 'Tiruchirappalli Corporation',
    'salem': 'Salem Corporation',
    'சேலம்': 'Salem Corporation',
    'tirunelveli': 'Tirunelveli Corporation',
    'vellore': 'Vellore Corporation',
    'erode': 'Erode Corporation',
    'ஈரோடு': 'Erode Corporation',
    'thanjavur': 'Thanjavur Corporation',
    'தஞ்சாவூர்': 'Thanjavur Corporation',
    'kumbakonam': 'Kumbakonam',
    'tiruppur': 'Tiruppur Corporation',
    'tirupur': 'Tiruppur Corporation',
    'dindigul': 'Dindigul Corporation',
    'thoothukudi': 'Thoothukudi Corporation',
    'tuticorin': 'Thoothukudi Corporation',
    'nagercoil': 'Nagercoil Corporation',
    'hosur': 'Hosur Corporation',
    'cuddalore': 'Cuddalore Corporation',
    'karur': 'Karur Corporation',
    'sivakasi': 'Sivakasi Corporation',
    'bengaluru': 'BBMP (Bengaluru)',
    'bangalore': 'BBMP (Bengaluru)',
    'mysuru': 'Mysuru City Corporation',
    'mysore': 'Mysuru City Corporation',
    'kochi': 'Kochi Corporation',
    'thiruvananthapuram': 'Thiruvananthapuram Corporation',
    'hyderabad': 'GHMC Hyderabad',
    'mumbai': 'BMC (Greater Mumbai)',
    'pune': 'Pune Municipal Corporation',
    'new delhi': 'NDMC New Delhi',
}


def clean_admin_suffix(value):
    """Strip common administrative suffixes (English & Tamil) and normalize whitespace."""
    if not value:
        return ''
    text = str(value).strip()
    text = re.sub(r'\s+', ' ', text)
    # Remove trailing "District", "Dist.", "Dt.", "Taluk", "Tk", Tamil "மாவட்டம்", "வட்டம்"
    text = re.sub(r'\s*\b(?:district|dist\.?|dt\.?|taluk|tk\.?|metropolitan region)\b\s*$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*(?:மாவட்டம்|மாவட்ட|வட்டம்|மாநகராட்சி|நகராட்சி)\s*$', '', text)
    text = re.sub(r'\s+', ' ', text).strip(' ,.-')
    return text


def normalize_state_name(raw_state):
    cleaned = clean_admin_suffix(raw_state)
    if not cleaned:
        return ''
    low = cleaned.lower()
    if low in STATE_ALIASES:
        return STATE_ALIASES[low]
    return cleaned


def normalize_district_name(*candidates):
    """Resolve canonical district name from one or more raw candidates (English/Tamil)."""
    dir_re = re.compile(r'\s*\b(?:north|south|east|west|central|rural|urban|city|municipal|corporation)\b\s*$', re.IGNORECASE)
    for raw in candidates:
        cleaned = clean_admin_suffix(raw)
        if not cleaned:
            continue
        low = cleaned.lower()
        if low in DISTRICT_ALIASES:
            return DISTRICT_ALIASES[low]
        compact = dir_re.sub('', low).strip()
        if compact in DISTRICT_ALIASES:
            return DISTRICT_ALIASES[compact]
        compact2 = dir_re.sub('', compact).strip()
        if compact2 in DISTRICT_ALIASES:
            return DISTRICT_ALIASES[compact2]

    for raw in candidates:
        cleaned = clean_admin_suffix(raw)
        if cleaned:
            return cleaned
    return ''


def normalize_city_name(*candidates):
    for raw in candidates:
        cleaned = clean_admin_suffix(raw)
        if not cleaned:
            continue
        low = cleaned.lower()
        if low in CITY_ALIASES:
            return CITY_ALIASES[low]
        compact = re.sub(r'\s*\b(?:city|municipal corporation|corporation|municipality)\b\s*$', '', low, flags=re.IGNORECASE).strip()
        if compact in CITY_ALIASES:
            return CITY_ALIASES[compact]
        return cleaned
    return ''


def extract_reliable_ward(*texts):
    """
    Extract ward number ONLY when explicit municipal ward boundary data is present.
    Never guesses or defaults to an arbitrary number.
    """
    patterns = [
        re.compile(r'\bward\s*(?:no\.?|number|#|:|-)?\s*(\d{1,3})\b', re.IGNORECASE),
        re.compile(r'வார்டு\s*(?:எண்\.?)?\s*(\d{1,3})\b'),
        re.compile(r'\bdivision\s*(?:no\.?|#)?\s*(\d{1,3})\b', re.IGNORECASE),
    ]
    for candidate in texts:
        if not candidate:
            continue
        txt = str(candidate).strip()
        if re.fullmatch(r'\d{1,3}', txt):
            num = int(txt)
            if 1 <= num <= 300:
                return f"Ward {num}"
        for pat in patterns:
            m = pat.search(txt)
            if m:
                num = int(m.group(1))
                if 1 <= num <= 300:
                    return f"Ward {num}"
    return None


def _http_get_json(url, timeout=4.5):
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'SmartCivicFlow/1.0 (civic-complaint-portal; contact@smartcivic.gov)',
            'Accept': 'application/json',
            'Accept-Language': 'en',
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8', errors='replace'))


def _parse_nominatim(geo):
    if not isinstance(geo, dict):
        return {}
    addr = geo.get('address') or {}
    extratags = geo.get('extratags') or {}
    namedetails = geo.get('namedetails') or {}

    state = normalize_state_name(addr.get('state') or addr.get('state_code'))
    city = normalize_city_name(
        addr.get('city'),
        addr.get('town'),
        addr.get('municipality'),
        addr.get('village') if not addr.get('city') and not addr.get('town') else '',
    )
    district = normalize_district_name(
        addr.get('state_district'),
        addr.get('county'),
        addr.get('district'),
        addr.get('city_district'),
        city,
    )
    is_ward_only = re.compile(r'^(?:ward|division)\s*(?:no\.?|number|#|:|-)?\s*\d{1,3}$', re.IGNORECASE)
    loc_candidates = [
        addr.get('quarter'),
        addr.get('neighbourhood'),
        addr.get('suburb'),
        addr.get('residential'),
        addr.get('city_district'),
        addr.get('village'),
        addr.get('hamlet'),
    ]
    locality = ''
    for cand in loc_candidates:
        cval = (cand or '').strip()
        if cval and not is_ward_only.match(cval):
            locality = cval
            break
    if not locality:
        locality = (addr.get('suburb') or addr.get('neighbourhood') or addr.get('town') or '').strip()

    street_parts = [addr.get('house_number'), addr.get('road') or addr.get('pedestrian') or addr.get('footway')]
    street_name = ' '.join(p.strip() for p in street_parts if p and str(p).strip())

    landmark = ''
    for lk in ('amenity', 'building', 'shop', 'tourism', 'leisure', 'historic', 'office', 'healthcare', 'railway', 'bus_stop', 'place_of_worship'):
        val = addr.get(lk)
        if val and str(val).strip().lower() not in (street_name.lower(), locality.lower()):
            landmark = str(val).strip()
            break
    if not landmark and geo.get('name'):
        gname = str(geo.get('name')).strip()
        if gname and not is_ward_only.match(gname) and gname.lower() not in (street_name.lower(), locality.lower(), (city or '').lower()):
            landmark = gname
    if not landmark and namedetails.get('name:en'):
        en_name = str(namedetails.get('name:en')).strip()
        if en_name and not is_ward_only.match(en_name) and en_name.lower() not in (street_name.lower(), locality.lower(), (city or '').lower()):
            landmark = en_name

    raw_pin = str(addr.get('postcode') or '')
    pin_digits = re.sub(r'\D', '', raw_pin)
    pincode = pin_digits[:6] if len(pin_digits) >= 6 else ''

    ward_number = extract_reliable_ward(
        addr.get('ward'),
        extratags.get('ward'),
        extratags.get('ward_no'),
        extratags.get('ref:ward'),
        addr.get('neighbourhood'),
        addr.get('quarter'),
        addr.get('residential'),
        addr.get('borough'),
        addr.get('suburb'),
        addr.get('city_district'),
        geo.get('name'),
        geo.get('display_name'),
    )

    return {
        'state': state,
        'district': district,
        'city': city,
        'ward_number': ward_number,
        'street_name': street_name,
        'locality': locality,
        'landmark': landmark,
        'pincode': pincode,
        'display_name': geo.get('display_name') or '',
    }


def _parse_bigdatacloud(bdc):
    if not isinstance(bdc, dict):
        return {}
    admin_list = ((bdc.get('localityInfo') or {}).get('administrative')) or []
    admin_by_level = {}
    ward_candidates = []
    for entry in admin_list:
        name = (entry.get('name') or '').strip()
        desc = (entry.get('description') or '').strip()
        level = entry.get('adminLevel')
        if level is not None and name:
            admin_by_level.setdefault(level, []).append(name)
        if 'ward' in desc.lower() or re.search(r'\bward\b', name, re.IGNORECASE):
            ward_candidates.append(name)
            ward_candidates.append(desc)

    state = normalize_state_name(bdc.get('principalSubdivision') or (admin_by_level.get(4) or [''])[0])
    district_raw_candidates = []
    # Level 5 in India is normally District; Level 6 is Sub-district / Taluk
    district_raw_candidates.extend(admin_by_level.get(5, []))
    district_raw_candidates.extend(admin_by_level.get(6, []))
    if bdc.get('city'):
        district_raw_candidates.append(bdc.get('city'))
    district = normalize_district_name(*district_raw_candidates)
    city = normalize_city_name(bdc.get('city'), *(admin_by_level.get(6, [])), bdc.get('locality'))
    locality = (bdc.get('locality') or '').strip()
    raw_pin = str(bdc.get('postcode') or '')
    pin_digits = re.sub(r'\D', '', raw_pin)
    pincode = pin_digits[:6] if len(pin_digits) >= 6 else ''
    ward_number = extract_reliable_ward(*ward_candidates)

    return {
        'state': state,
        'district': district,
        'city': city,
        'ward_number': ward_number,
        'street_name': '',
        'locality': locality,
        'landmark': '',
        'pincode': pincode,
        'display_name': '',
    }


def reverse_geocode_coordinates(lat, lng, fetcher=None):
    """
    Resolve coordinates to structured civic address components using Nominatim + BigDataCloud
    with English + Tamil normalization and strict municipal ward boundary extraction.
    """
    fetch_fn = fetcher or _http_get_json
    lat_str = f"{float(lat):.6f}"
    lng_str = f"{float(lng):.6f}"

    nom_data = {}
    nom_z15_data = {}
    bdc_data = {}
    photon_ward = None
    photon_loc = ''
    errors = []

    nom_url = (
        f"https://nominatim.openstreetmap.org/reverse?format=jsonv2"
        f"&lat={urllib.parse.quote(lat_str)}&lon={urllib.parse.quote(lng_str)}"
        f"&zoom=18&addressdetails=1&extratags=1&namedetails=1&accept-language=en"
    )
    try:
        nom_raw = fetch_fn(nom_url, timeout=4.5)
        nom_data = _parse_nominatim(nom_raw)
    except Exception as exc:
        errors.append(f"nominatim:{type(exc).__name__}")

    # Secondary zoom=15 lookup when zoom=18 road/building misses suburban ward boundary
    if not nom_data.get('ward_number'):
        nom_z15_url = (
            f"https://nominatim.openstreetmap.org/reverse?format=jsonv2"
            f"&lat={urllib.parse.quote(lat_str)}&lon={urllib.parse.quote(lng_str)}"
            f"&zoom=15&addressdetails=1&extratags=1&accept-language=en"
        )
        try:
            nom_z15_raw = fetch_fn(nom_z15_url, timeout=3.5)
            nom_z15_data = _parse_nominatim(nom_z15_raw)
        except Exception:
            pass

    # Query Photon reverse geocoder for ward/locality enrichment when ward is still undetected
    if not nom_data.get('ward_number') and not nom_z15_data.get('ward_number'):
        photon_url = f"https://photon.komoot.io/reverse?lat={urllib.parse.quote(lat_str)}&lon={urllib.parse.quote(lng_str)}"
        try:
            ph_raw = fetch_fn(photon_url, timeout=3.0)
            for feat in (ph_raw or {}).get('features', [])[:3]:
                props = feat.get('properties') or {}
                photon_ward = extract_reliable_ward(
                    props.get('district'),
                    props.get('locality'),
                    props.get('name'),
                    props.get('county'),
                )
                if not photon_loc:
                    photon_loc = (props.get('locality') or props.get('district') or '').strip()
                if photon_ward:
                    break
        except Exception:
            pass

    # Query BigDataCloud when Nominatim misses key admin fields or failed completely
    needs_bdc = (
        not nom_data
        or not nom_data.get('district')
        or not nom_data.get('state')
        or not (nom_data.get('ward_number') or nom_z15_data.get('ward_number') or photon_ward)
    )
    if needs_bdc:
        bdc_url = (
            f"https://api.bigdatacloud.net/data/reverse-geocode-client"
            f"?latitude={urllib.parse.quote(lat_str)}&longitude={urllib.parse.quote(lng_str)}&localityLanguage=en"
        )
        try:
            bdc_raw = fetch_fn(bdc_url, timeout=4.0)
            bdc_data = _parse_bigdatacloud(bdc_raw)
        except Exception as exc:
            errors.append(f"bigdatacloud:{type(exc).__name__}")

    if not nom_data and not nom_z15_data and not bdc_data:
        return {
            'success': False,
            'latitude': lat_str,
            'longitude': lng_str,
            'error': 'Reverse geocoding service unavailable.',
            'errors': errors,
        }

    state = normalize_state_name(nom_data.get('state') or nom_z15_data.get('state') or bdc_data.get('state'))
    district = normalize_district_name(
        nom_data.get('district'),
        nom_z15_data.get('district'),
        bdc_data.get('district'),
        nom_data.get('city'),
        bdc_data.get('city'),
    )
    city = normalize_city_name(nom_data.get('city') or nom_z15_data.get('city') or bdc_data.get('city'))
    ward_number = (
        nom_data.get('ward_number')
        or nom_z15_data.get('ward_number')
        or photon_ward
        or bdc_data.get('ward_number')
        or None
    )
    street_name = (nom_data.get('street_name') or '').strip()
    locality = (nom_data.get('locality') or nom_z15_data.get('locality') or photon_loc or bdc_data.get('locality') or '').strip()
    landmark = (nom_data.get('landmark') or '').strip()
    pincode = nom_data.get('pincode') or nom_z15_data.get('pincode') or bdc_data.get('pincode') or ''

    return {
        'success': True,
        'latitude': lat_str,
        'longitude': lng_str,
        'state': state,
        'district': district,
        'city': city,
        'ward_number': ward_number,
        'street_name': street_name,
        'locality': locality,
        'landmark': landmark,
        'pincode': pincode,
        'display_name': nom_data.get('display_name') or '',
    }
