// Smart Civic Flow - Reusable Administrative Location & GPS Auto-Population Engine
// Normalizes English + Tamil location names and cascades State -> District -> City/Municipality -> Ward cleanly.

(function() {
  const LOCATION_DATA = {
    'Tamil Nadu': {
      'Ariyalur': ['Ariyalur Municipality', 'Jayankondam', 'Sendurai'],
      'Chengalpattu': ['Tambaram Corporation', 'Chengalpattu Municipality', 'Pallavaram', 'Maraimalai Nagar', 'Madurantakam'],
      'Chennai': ['Greater Chennai Corporation', 'City Centre', 'Ambattur', 'Avadi', 'Sholinganallur', 'Tiruvottiyur'],
      'Coimbatore': ['Coimbatore Corporation', 'Pollachi', 'Mettupalayam', 'Valparai', 'Sulur'],
      'Cuddalore': ['Cuddalore Corporation', 'Chidambaram', 'Neyveli', 'Panruti', 'Vriddhachalam'],
      'Dharmapuri': ['Dharmapuri Municipality', 'Harur', 'Palacode'],
      'Dindigul': ['Dindigul Corporation', 'Palani', 'Kodaikanal', 'Oddanchatram'],
      'Erode': ['Erode Corporation', 'Gobichettipalayam', 'Bhavani', 'Sathyamangalam'],
      'Kallakurichi': ['Kallakurichi Municipality', 'Tirukoilur', 'Ulundurpet'],
      'Kanchipuram': ['Kanchipuram Corporation', 'Sriperumbudur', 'Kundrathur', 'Walajabad'],
      'Kanyakumari': ['Nagercoil Corporation', 'Padmanabhapuram', 'Colachel', 'Kuzhithurai'],
      'Karur': ['Karur Corporation', 'Kulithalai', 'Pallapatti'],
      'Krishnagiri': ['Hosur Corporation', 'Krishnagiri Municipality', 'Denkanikottai'],
      'Madurai': ['Madurai Corporation', 'Melur', 'Thirumangalam', 'Usilampatti'],
      'Mayiladuthurai': ['Mayiladuthurai Municipality', 'Sirkazhi', 'Kuthalam'],
      'Nagapattinam': ['Nagapattinam Municipality', 'Vedaranyam', 'Kilvelur'],
      'Namakkal': ['Namakkal Corporation', 'Tiruchengode', 'Rasipuram', 'Komarapalayam'],
      'Nilgiris': ['Udhagamandalam (Ooty)', 'Coonoor', 'Gudalur', 'Kotagiri'],
      'Perambalur': ['Perambalur Municipality', 'Kunnam'],
      'Pudukkottai': ['Pudukkottai Corporation', 'Aranthangi', 'Ponnamaravathi'],
      'Ramanathapuram': ['Ramanathapuram Municipality', 'Paramakudi', 'Rameswaram'],
      'Ranipet': ['Ranipet Municipality', 'Arcot', 'Walajapet', 'Arakkonam'],
      'Salem': ['Salem Corporation', 'Attur', 'Mettur', 'Edappadi'],
      'Sivaganga': ['Karaikudi Corporation', 'Sivaganga Municipality', 'Devakottai'],
      'Tenkasi': ['Tenkasi Municipality', 'Sankarankovil', 'Shenkottai', 'Kadayanallur'],
      'Thanjavur': ['Thanjavur Corporation', 'Kumbakonam', 'Pattukkottai'],
      'Theni': ['Theni-Allinagaram Municipality', 'Periyakulam', 'Bodinayakanur', 'Cumbum'],
      'Thoothukudi': ['Thoothukudi Corporation', 'Kovilpatti', 'Tiruchendur', 'Kayalpattinam'],
      'Tiruchirappalli': ['Tiruchirappalli Corporation', 'Srirangam', 'Thiruverumbur', 'Manapparai'],
      'Tirunelveli': ['Tirunelveli Corporation', 'Ambasamudram', 'Vikramasingapuram'],
      'Tirupathur': ['Tirupathur Municipality', 'Vaniyambadi', 'Ambur'],
      'Tiruppur': ['Tiruppur Corporation', 'Avinashi', 'Udumalaipettai', 'Dharapuram', 'Palladam'],
      'Tiruvallur': ['Avadi Corporation', 'Tiruvallur Municipality', 'Poonamallee', 'Tiruttani', 'Ponneri'],
      'Tiruvannamalai': ['Tiruvannamalai Corporation', 'Arni', 'Cheyyar', 'Polur'],
      'Tiruvarur': ['Tiruvarur Municipality', 'Mannargudi', 'Thiruthuraipoondi'],
      'Vellore': ['Vellore Corporation', 'Gudiyatham', 'Katpadi', 'Pernambut'],
      'Villupuram': ['Villupuram Municipality', 'Tindivanam', 'Gingee'],
      'Virudhunagar': ['Sivakasi Corporation', 'Virudhunagar Municipality', 'Rajapalayam', 'Aruppukkottai', 'Srivilliputhur']
    },
    'Puducherry': {
      'Puducherry': ['Puducherry Municipality', 'Oulgaret Municipality'],
      'Karaikal': ['Karaikal Municipality']
    },
    'Karnataka': {
      'Bengaluru Urban': ['BBMP (Bengaluru)', 'Yelahanka', 'Bommanahalli', 'Mahadevapura'],
      'Bengaluru Rural': ['Doddaballapura', 'Devanahalli', 'Hoskote'],
      'Mysuru': ['Mysuru City Corporation', 'Nanjangud'],
      'Mangaluru': ['Mangaluru City Corporation', 'Ullal']
    },
    'Kerala': {
      'Thiruvananthapuram': ['Thiruvananthapuram Corporation', 'Neyyattinkara'],
      'Ernakulam': ['Kochi Corporation', 'Aluva', 'Kakkanad'],
      'Kozhikode': ['Kozhikode Corporation', 'Vadakara'],
      'Thrissur': ['Thrissur Corporation', 'Chalakudy']
    },
    'Andhra Pradesh': {
      'Visakhapatnam': ['GVMC Visakhapatnam', 'Anakapalle'],
      'NTR': ['Vijayawada Municipal Corporation'],
      'Guntur': ['Guntur Municipal Corporation'],
      'Tirupati': ['Tirupati Municipal Corporation']
    },
    'Telangana': {
      'Hyderabad': ['GHMC Hyderabad', 'Secunderabad'],
      'Rangareddy': ['LB Nagar', 'Shamshabad'],
      'Medchal-Malkajgiri': ['Malkajgiri', 'Kukatpally']
    },
    'Maharashtra': {
      'Mumbai': ['BMC (Greater Mumbai)', 'Bandra', 'Andheri'],
      'Pune': ['Pune Municipal Corporation', 'Pimpri-Chinchwad'],
      'Thane': ['Thane Municipal Corporation', 'Kalyan-Dombivli'],
      'Nagpur': ['Nagpur Municipal Corporation']
    },
    'Delhi': {
      'New Delhi': ['NDMC New Delhi', 'MCD Central', 'MCD South'],
      'Central Delhi': ['MCD Central'],
      'South Delhi': ['MCD South']
    },
    'Gujarat': {
      'Ahmedabad': ['Ahmedabad Municipal Corporation'],
      'Surat': ['Surat Municipal Corporation'],
      'Vadodara': ['Vadodara Municipal Corporation']
    },
    'Rajasthan': {
      'Jaipur': ['Jaipur Municipal Corporation'],
      'Jodhpur': ['Jodhpur Municipal Corporation']
    },
    'Uttar Pradesh': {
      'Lucknow': ['Lucknow Municipal Corporation'],
      'Kanpur Nagar': ['Kanpur Municipal Corporation'],
      'Varanasi': ['Varanasi Municipal Corporation']
    },
    'West Bengal': {
      'Kolkata': ['Kolkata Municipal Corporation'],
      'Howrah': ['Howrah Municipal Corporation']
    }
  };

  const CITY_LOCALITIES = {
    'Greater Chennai Corporation': ['T. Nagar', 'Mylapore', 'Adyar', 'Anna Nagar', 'Velachery', 'Guindy', 'Kodambakkam', 'Triplicane', 'Perambur', 'Nungambakkam', 'Royapettah', 'Besant Nagar'],
    'City Centre': ['Central Square', 'Park Avenue', 'Anna Salai', 'Egmore', 'Nungambakkam'],
    'Tambaram Corporation': ['Tambaram East', 'Tambaram West', 'Chromepet', 'Pallavaram', 'Selaiyur'],
    'Coimbatore Corporation': ['RS Puram', 'Gandhipuram', 'Peelamedu', 'Saibaba Colony', 'Race Course', 'Singanallur'],
    'Pollachi': ['Mahalingapuram', 'Pollachi Town', 'Zamin Uthukuli', 'Suleeswaranpatti', 'Makkinampatti'],
    'Madurai Corporation': ['Anna Nagar', 'KK Nagar', 'Simmakkal', 'Goripalayam', 'Tallakulam'],
    'Tiruchirappalli Corporation': ['Thillai Nagar', 'Cantonment', 'Srirangam', 'Woraiyur'],
    'Salem Corporation': ['Fairlands', 'Hasthampatti', 'Gugai', 'Ammapet']
  };

  const STATE_ALIASES = {
    'tamil nadu': 'Tamil Nadu',
    'tamilnadu': 'Tamil Nadu',
    'tn': 'Tamil Nadu',
    'தமிழ்நாடு': 'Tamil Nadu',
    'தமிழ் நாடு': 'Tamil Nadu',
    'puducherry': 'Puducherry',
    'pondicherry': 'Puducherry',
    'புதுச்சேரி': 'Puducherry',
    'karnataka': 'Karnataka',
    'கர்நாடகா': 'Karnataka',
    'கர்நாடகம்': 'Karnataka',
    'kerala': 'Kerala',
    'கேரளா': 'Kerala',
    'கேரளம்': 'Kerala',
    'andhra pradesh': 'Andhra Pradesh',
    'ஆந்திரப் பிரதேசம்': 'Andhra Pradesh',
    'telangana': 'Telangana',
    'தெலுங்கானா': 'Telangana',
    'தெலங்கானா': 'Telangana',
    'maharashtra': 'Maharashtra',
    'delhi': 'Delhi',
    'nct of delhi': 'Delhi',
    'national capital territory of delhi': 'Delhi',
    'new delhi': 'Delhi',
    'gujarat': 'Gujarat',
    'rajasthan': 'Rajasthan',
    'uttar pradesh': 'Uttar Pradesh',
    'west bengal': 'West Bengal'
  };

  const DISTRICT_ALIASES = {
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
    // Taluk / Town to District mappings
    'pollachi': 'Coimbatore',
    'பொள்ளாச்சி': 'Coimbatore',
    'mettupalayam': 'Coimbatore',
    'valparai': 'Coimbatore',
    'sulur': 'Coimbatore',
    'tambaram': 'Chengalpattu',
    'தாம்பரம்': 'Chengalpattu',
    'pallavaram': 'Chengalpattu',
    'hosur': 'Krishnagiri',
    'ஓசூர்': 'Krishnagiri',
    'kumbakonam': 'Thanjavur',
    'கும்பகோணம்': 'Thanjavur',
    'sivakasi': 'Virudhunagar',
    'karaikudi': 'Sivaganga',
    'bengaluru urban': 'Bengaluru Urban',
    'bangalore urban': 'Bengaluru Urban',
    'bengaluru': 'Bengaluru Urban',
    'bangalore': 'Bengaluru Urban',
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
    'visakhapatnam': 'Visakhapatnam',
    'hyderabad': 'Hyderabad',
    'rangareddy': 'Rangareddy',
    'ranga reddy': 'Rangareddy',
    'puducherry': 'Puducherry',
    'pondicherry': 'Puducherry',
    'mumbai': 'Mumbai',
    'mumbai city': 'Mumbai',
    'mumbai suburban': 'Mumbai',
    'pune': 'Pune',
    'new delhi': 'New Delhi'
  };

  const CITY_ALIASES = {
    'chennai': 'Greater Chennai Corporation',
    'greater chennai': 'Greater Chennai Corporation',
    'greater chennai corporation': 'Greater Chennai Corporation',
    'சென்னை': 'Greater Chennai Corporation',
    'coimbatore': 'Coimbatore Corporation',
    'coimbatore corporation': 'Coimbatore Corporation',
    'கோயம்புத்தூர்': 'Coimbatore Corporation',
    'pollachi': 'Pollachi',
    'பொள்ளாச்சி': 'Pollachi',
    'tambaram': 'Tambaram Corporation',
    'tambaram corporation': 'Tambaram Corporation',
    'madurai': 'Madurai Corporation',
    'மதுரை': 'Madurai Corporation',
    'tiruchirappalli': 'Tiruchirappalli Corporation',
    'trichy': 'Tiruchirappalli Corporation',
    'salem': 'Salem Corporation',
    'சேலம்': 'Salem Corporation',
    'tirunelveli': 'Tirunelveli Corporation',
    'vellore': 'Vellore Corporation',
    'erode': 'Erode Corporation',
    'thanjavur': 'Thanjavur Corporation',
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
    'new delhi': 'NDMC New Delhi'
  };

  function cleanAdminSuffix(value) {
    if (!value) return '';
    return String(value)
      .trim()
      .replace(/\s+/g, ' ')
      .replace(/\s*\b(?:district|dist\.?|dt\.?|taluk|tk\.?|metropolitan region)\b\s*$/i, '')
      .replace(/\s*(?:மாவட்டம்|மாவட்ட|வட்டம்|மாநகராட்சி|நகராட்சி)\s*$/u, '')
      .replace(/\s+/g, ' ')
      .replace(/^[\s,.-]+|[\s,.-]+$/g, '');
  }

  function normalizeStateName(rawState) {
    const cleaned = cleanAdminSuffix(rawState);
    if (!cleaned) return '';
    return STATE_ALIASES[cleaned.toLowerCase()] || cleaned;
  }

  function normalizeDistrictName(rawDistrict, fallbackCity) {
    const candidates = [rawDistrict, fallbackCity];
    const dirRe = /\s*\b(?:north|south|east|west|central|rural|urban|city|municipal|corporation)\b\s*$/i;
    for (const raw of candidates) {
      const cleaned = cleanAdminSuffix(raw);
      if (!cleaned) continue;
      const low = cleaned.toLowerCase();
      if (DISTRICT_ALIASES[low]) return DISTRICT_ALIASES[low];
      const compact = low.replace(dirRe, '').trim();
      if (DISTRICT_ALIASES[compact]) return DISTRICT_ALIASES[compact];
      const compact2 = compact.replace(dirRe, '').trim();
      if (DISTRICT_ALIASES[compact2]) return DISTRICT_ALIASES[compact2];
    }
    return cleanAdminSuffix(rawDistrict) || cleanAdminSuffix(fallbackCity) || '';
  }

  function normalizeCityName(rawCity) {
    const cleaned = cleanAdminSuffix(rawCity);
    if (!cleaned) return '';
    const low = cleaned.toLowerCase();
    if (CITY_ALIASES[low]) return CITY_ALIASES[low];
    const compact = low.replace(/\s*\b(?:city|municipal corporation|corporation|municipality)\b\s*$/i, '').trim();
    if (CITY_ALIASES[compact]) return CITY_ALIASES[compact];
    return cleaned;
  }

  function extractWardFromText(text) {
    if (!text) return '';
    const str = String(text).trim();
    if (/^\d{1,3}$/.test(str)) {
      const n = parseInt(str, 10);
      return (n >= 1 && n <= 300) ? `Ward ${n}` : '';
    }
    const m = str.match(/(?:ward|division)\s*(?:no\.?|number|#|:|-)?\s*(\d{1,3})\b/i)
      || str.match(/வார்டு\s*(?:எண்\.?)?\s*(\d{1,3})\b/u);
    if (m) {
      const n = parseInt(m[1], 10);
      return (n >= 1 && n <= 300) ? `Ward ${n}` : '';
    }
    return '';
  }

  window.CivicLocation = {
    LOCATION_DATA,
    CITY_LOCALITIES,
    cleanAdminSuffix,
    normalizeStateName,
    normalizeDistrictName,
    normalizeCityName,
    extractWardFromText
  };

  window.initCivicLocationSelector = function(opts) {
    const cfg = opts || {};
    const stateSelect = document.getElementById(cfg.stateSelectId || 'stateSelect');
    const stateCustom = document.getElementById(cfg.stateCustomId || 'stateCustom');
    const stateHidden = document.getElementById(cfg.stateHiddenId || 'stateHidden');
    const districtSelect = document.getElementById(cfg.districtSelectId || 'districtSelect');
    const districtCustom = document.getElementById(cfg.districtCustomId || 'districtCustom');
    const districtHidden = document.getElementById(cfg.districtHiddenId || 'districtHidden');
    const citySelect = document.getElementById(cfg.citySelectId || 'citySelect');
    const cityCustom = document.getElementById(cfg.cityCustomId || 'cityCustom');
    const cityHidden = document.getElementById(cfg.cityHiddenId || 'cityHidden');
    const wardSelect = document.getElementById(cfg.wardSelectId || 'wardSelect');
    const wardCustom = document.getElementById(cfg.wardCustomId || 'wardCustom');
    const wardInput = document.getElementById(cfg.wardHiddenId || 'wardInput');
    const streetInput = document.getElementById(cfg.streetInputId || 'streetInput');
    const localityInput = document.getElementById(cfg.localityInputId || 'localityInput');
    const localityOptions = document.getElementById(cfg.localityOptionsId || 'localityOptions');
    const landmarkInput = document.getElementById(cfg.landmarkInputId || 'landmarkInput');
    const pincodeInput = document.getElementById(cfg.pincodeInputId || 'pincodeInput');
    const latInput = document.getElementById(cfg.latInputId || 'latitudeInput');
    const lngInput = document.getElementById(cfg.lngInputId || 'longitudeInput');
    const detectBtn = document.getElementById(cfg.detectBtnId || 'detectLocationBtn');
    const gpsStatusText = document.getElementById(cfg.gpsStatusId || 'gpsStatusText');
    const onLocationUpdated = typeof cfg.onLocationUpdated === 'function' ? cfg.onLocationUpdated : null;

    if (!stateSelect || !districtSelect || !citySelect) return;

    function populateSelect(selectEl, baseItems, preferredVal, otherLabel, options) {
      const settings = options || {};
      const items = baseItems.slice();
      const allowEmptyPlaceholder = Boolean(settings.placeholder);
      const injectMissing = Boolean(settings.injectMissing);

      let matched = null;
      if (preferredVal && String(preferredVal).trim() !== '') {
        const cleanPref = String(preferredVal).trim();
        matched = items.find(i => i.toLowerCase() === cleanPref.toLowerCase()) || null;
        if (!matched && settings.normalizeFn) {
          const normPref = settings.normalizeFn(cleanPref);
          if (normPref) {
            matched = items.find(i => i.toLowerCase() === normPref.toLowerCase()) || null;
            if (!matched) {
              matched = items.find(i => {
                const nItem = settings.normalizeFn(i);
                return nItem && nItem.toLowerCase() === normPref.toLowerCase();
              }) || null;
            }
          }
        }
        if (!matched && injectMissing) {
          const resolvedName = settings.normalizeFn ? (settings.normalizeFn(cleanPref) || cleanPref) : cleanPref;
          if (!items.some(i => i.toLowerCase() === resolvedName.toLowerCase())) {
            items.unshift(resolvedName);
          }
          matched = items.find(i => i.toLowerCase() === resolvedName.toLowerCase()) || resolvedName;
        }
      }

      const tr = (s) => (window.scfT ? window.scfT(s) : s);
      selectEl.innerHTML = '';
      if (allowEmptyPlaceholder) {
        const ph = document.createElement('option');
        ph.value = '';
        ph.textContent = tr(settings.placeholder);
        selectEl.appendChild(ph);
      }

      items.forEach(item => {
        const opt = document.createElement('option');
        opt.value = item;
        opt.textContent = item;
        selectEl.appendChild(opt);
      });

      const otherOpt = document.createElement('option');
      otherOpt.value = '__other__';
      otherOpt.textContent = tr(otherLabel || 'Other (Enter manually)...');
      selectEl.appendChild(otherOpt);

      if (matched) {
        selectEl.value = matched;
        return false;
      }
      if (preferredVal && String(preferredVal).trim() !== '') {
        selectEl.value = '__other__';
        return true;
      }
      if (allowEmptyPlaceholder) {
        selectEl.value = '';
        return false;
      }
      if (items.length > 0) {
        selectEl.value = items[0];
        return false;
      }
      return false;
    }

    function bindFieldSync(selectEl, customEl, hiddenEl, onChangeCallback) {
      function syncValue() {
        if (!selectEl || !customEl || !hiddenEl) return;
        if (selectEl.value === '__other__') {
          customEl.style.display = 'block';
          customEl.required = true;
          hiddenEl.value = customEl.value.trim();
        } else {
          customEl.style.display = 'none';
          customEl.required = false;
          hiddenEl.value = selectEl.value;
        }
      }
      if (selectEl) {
        selectEl.addEventListener('change', () => {
          syncValue();
          if (onChangeCallback) onChangeCallback();
        });
      }
      if (customEl && selectEl) {
        customEl.addEventListener('input', () => {
          if (selectEl.value === '__other__' && hiddenEl) {
            hiddenEl.value = customEl.value.trim();
          }
        });
      }
      return syncValue;
    }

    function updateLocalities(cityName) {
      if (!localityOptions) return;
      const list = CITY_LOCALITIES[cityName] || CITY_LOCALITIES['Greater Chennai Corporation'] || [];
      localityOptions.innerHTML = list.map(loc => `<option value="${loc}">`).join('');
    }

    function ensureStateCatalog(stateName) {
      if (stateName && !LOCATION_DATA[stateName]) {
        LOCATION_DATA[stateName] = {};
      }
    }

    function refreshDistricts(preferredDistrict, preferredCity, injectMissing) {
      const st = stateSelect.value;
      const districts = (LOCATION_DATA[st] && Object.keys(LOCATION_DATA[st])) || [];
      const resolvedPref = preferredDistrict ? normalizeDistrictName(preferredDistrict, preferredCity) : null;
      const useCustomDist = populateSelect(districtSelect, districts, resolvedPref, 'Other District...', {
        injectMissing: Boolean(injectMissing && resolvedPref),
        normalizeFn: (v) => normalizeDistrictName(v, preferredCity)
      });
      if (useCustomDist && districtCustom && resolvedPref) {
        districtCustom.value = resolvedPref;
      }
      syncDistrict();
      refreshCities(preferredCity, injectMissing);
    }

    function refreshCities(preferredCity, injectMissing) {
      const st = stateSelect.value;
      const dist = districtSelect.value;
      const cities = (LOCATION_DATA[st] && LOCATION_DATA[st][dist]) || [];
      const resolvedCity = preferredCity ? normalizeCityName(preferredCity) : null;
      const useCustomCity = populateSelect(citySelect, cities, resolvedCity, 'Other City / Municipality...', {
        injectMissing: Boolean(injectMissing && resolvedCity),
        normalizeFn: normalizeCityName
      });
      if (useCustomCity && cityCustom && resolvedCity) {
        cityCustom.value = resolvedCity;
      }
      syncCity();
      if (cityHidden) updateLocalities(cityHidden.value);
    }

    function refreshWards(preferredWard, clearIfUnavailable) {
      let targetWard = preferredWard ? String(preferredWard).trim() : '';
      if (!targetWard && !clearIfUnavailable && wardInput) {
        targetWard = (wardInput.value || '').trim();
      }
      const normalizedWard = targetWard ? (extractWardFromText(targetWard) || targetWard) : '';
      if (!wardSelect) {
        if (wardInput) wardInput.value = normalizedWard;
        return;
      }
      const wards = Array.from({ length: 200 }, (_, i) => `Ward ${i + 1}`);
      const useCustomWard = populateSelect(wardSelect, wards, normalizedWard, 'Other Ward / Zone...', {
        placeholder: '-- Select Ward Number --',
        injectMissing: Boolean(normalizedWard)
      });
      if (useCustomWard && wardCustom && normalizedWard) {
        wardCustom.value = normalizedWard;
      } else if (!normalizedWard && wardCustom) {
        wardCustom.value = '';
      }
      syncWard();
    }

    const syncState = bindFieldSync(stateSelect, stateCustom, stateHidden, () => {
      refreshDistricts(null, null, false);
    });
    const syncDistrict = bindFieldSync(districtSelect, districtCustom, districtHidden, () => {
      refreshCities(null, false);
    });
    const syncCity = bindFieldSync(citySelect, cityCustom, cityHidden, () => {
      if (cityHidden) updateLocalities(cityHidden.value);
    });
    const syncWard = bindFieldSync(wardSelect, wardCustom, wardInput, () => {
      if (onLocationUpdated) onLocationUpdated();
    });
    if (wardCustom && onLocationUpdated) {
      wardCustom.addEventListener('blur', onLocationUpdated);
    }

    // Initial cascading dropdown setup (preserve pre-populated user values if valid)
    const initState = normalizeStateName(stateHidden ? stateHidden.value : '') || 'Tamil Nadu';
    const initDistrict = normalizeDistrictName(districtHidden ? districtHidden.value : '', cityHidden ? cityHidden.value : '') || 'Chennai';
    const initCity = (cityHidden && cityHidden.value) ? cityHidden.value : 'Greater Chennai Corporation';
    const statesList = Object.keys(LOCATION_DATA);
    const useCustomInitSt = populateSelect(stateSelect, statesList, initState, 'Other State...', {
      injectMissing: true,
      normalizeFn: normalizeStateName
    });
    if (useCustomInitSt && stateCustom) stateCustom.value = initState;
    syncState();
    refreshDistricts(initDistrict, initCity, true);
    refreshWards(wardInput ? wardInput.value : '', false);

    function applyDetectedLocation(geo) {
      if (!geo) return;

      const detState = normalizeStateName(geo.state || '');
      const detCity = normalizeCityName(geo.city || '');
      const detDist = normalizeDistrictName(geo.district || '', detCity || geo.locality || '');
      const detWard = geo.ward_number ? (extractWardFromText(geo.ward_number) || String(geo.ward_number).trim()) : '';

      // 1. State -> 2. District -> 3. City/Municipality -> 4. Ward (Strict order)
      if (detState) {
        ensureStateCatalog(detState);
        const states = Object.keys(LOCATION_DATA);
        const customSt = populateSelect(stateSelect, states, detState, 'Other State...', {
          injectMissing: true,
          normalizeFn: normalizeStateName
        });
        if (customSt && stateCustom) stateCustom.value = detState;
        syncState();
      }

      if (detDist || detCity) {
        refreshDistricts(detDist || null, detCity || null, true);
      }

      if (detWard) {
        refreshWards(detWard, true);
      } else {
        // Leave Ward unselected for manual choice when reliable ward boundary data is absent
        refreshWards('', true);
      }

      // 5. Street, Locality, Landmark, PIN Code (never overwrite with empty/undefined)
      const detStreet = (geo.street_name || '').trim();
      const detLocality = (geo.locality || '').trim();
      const detLandmark = (geo.landmark || '').trim();
      const detPin = (geo.pincode || '').replace(/\D/g, '').slice(0, 6);

      if (detStreet && streetInput) streetInput.value = detStreet;
      if (detLocality && localityInput) localityInput.value = detLocality;
      if (detLandmark && landmarkInput) landmarkInput.value = detLandmark;
      if (detPin.length === 6 && pincodeInput) pincodeInput.value = detPin;
    }

    async function fallbackBrowserReverseGeocode(lat, lng) {
      let result = null;
      try {
        const nomUrl = `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lng)}&zoom=18&addressdetails=1&extratags=1&accept-language=en`;
        const resp = await fetch(nomUrl, { headers: { 'Accept-Language': 'en' } });
        if (resp.ok) {
          const geo = await resp.json();
          const addr = geo.address || {};
          const extra = geo.extratags || {};
          const rawCity = addr.city || addr.town || addr.municipality || addr.village || '';
          const rawDist = addr.state_district || addr.county || addr.district || '';
          result = {
            success: true,
            state: normalizeStateName(addr.state || ''),
            city: normalizeCityName(rawCity),
            district: normalizeDistrictName(rawDist, rawCity),
            ward_number: extractWardFromText(
              [addr.ward, extra.ward, extra['ref:ward'], addr.neighbourhood, addr.quarter, addr.suburb, addr.city_district].filter(Boolean).join(' ')
            ) || null,
            street_name: [addr.house_number, addr.road].filter(Boolean).join(' '),
            locality: ([addr.quarter, addr.neighbourhood, addr.suburb, addr.residential, addr.village]
              .find(v => v && !/^ward\s*\d+$/i.test(String(v).trim())) || addr.suburb || addr.neighbourhood || '').trim(),
            landmark: (addr.amenity || addr.building || addr.shop || addr.tourism || '').trim(),
            pincode: addr.postcode ? String(addr.postcode).replace(/\D/g, '').slice(0, 6) : ''
          };
        }
      } catch (_) {}

      if (!result || !result.district || !result.state) {
        try {
          const bdcUrl = `https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${encodeURIComponent(lat)}&longitude=${encodeURIComponent(lng)}&localityLanguage=en`;
          const resp2 = await fetch(bdcUrl);
          if (resp2.ok) {
            const bdc = await resp2.json();
            const admins = (bdc.localityInfo && bdc.localityInfo.administrative) || [];
            const lvl5 = admins.find(a => a.adminLevel === 5);
            const lvl6 = admins.find(a => a.adminLevel === 6);
            const wardEntry = admins.find(a => /ward/i.test((a.description || '') + ' ' + (a.name || '')));
            const st = normalizeStateName(bdc.principalSubdivision || '');
            const cty = normalizeCityName(bdc.city || (lvl6 && lvl6.name) || '');
            const dst = normalizeDistrictName((lvl5 && lvl5.name) || (lvl6 && lvl6.name) || bdc.city || '', cty);
            result = Object.assign({}, result || {}, {
              success: true,
              state: (result && result.state) || st,
              district: (result && result.district) || dst,
              city: (result && result.city) || cty,
              locality: (result && result.locality) || (bdc.locality || '').trim(),
              pincode: (result && result.pincode) || (bdc.postcode ? String(bdc.postcode).replace(/\D/g, '').slice(0, 6) : ''),
              ward_number: (result && result.ward_number) || (wardEntry ? extractWardFromText(wardEntry.name || wardEntry.description) : null)
            });
          }
        } catch (_) {}
      }
      return result;
    }

    if (detectBtn) {
      const tr = (s) => (window.scfT ? window.scfT(s) : s);
      detectBtn.addEventListener('click', () => {
        if (!navigator.geolocation) {
          if (gpsStatusText) {
            gpsStatusText.textContent = tr('Geolocation is not supported by your browser. Please fill the address manually.');
            gpsStatusText.style.display = 'block';
            gpsStatusText.style.color = '#d97706';
          }
          if (window.showToast) {
            window.showToast(tr('Geolocation is not supported by your browser. Please select address options manually.'), 'warning', tr('Location Unavailable'));
          }
          return;
        }

        const origHtml = detectBtn.innerHTML;
        detectBtn.disabled = true;
        detectBtn.innerHTML = tr('Detecting location...');

        navigator.geolocation.getCurrentPosition(
          async (pos) => {
            const lat = pos.coords.latitude.toFixed(6);
            const lng = pos.coords.longitude.toFixed(6);
            if (latInput) latInput.value = lat;
            if (lngInput) lngInput.value = lng;

            if (gpsStatusText) {
              gpsStatusText.textContent = tr(`GPS Coordinates Captured: ${lat}, ${lng} — resolving administrative details...`);
              gpsStatusText.style.display = 'block';
              gpsStatusText.style.color = '#2563eb';
            }

            let geo = null;
            let reverseFailed = false;
            try {
              const apiUrl = window.getApiUrl
                ? window.getApiUrl(`/api/reverse-geocode?lat=${encodeURIComponent(lat)}&lng=${encodeURIComponent(lng)}`)
                : `/api/reverse-geocode?lat=${encodeURIComponent(lat)}&lng=${encodeURIComponent(lng)}`;
              const resp = await fetch(apiUrl, {
                credentials: 'include',
                headers: { 'Accept': 'application/json' }
              });
              if (resp.ok) {
                const payload = await resp.json();
                if (payload && payload.success) {
                  geo = payload;
                }
              }
            } catch (_) {}

            if (!geo || (!geo.district && !geo.state)) {
              const browserGeo = await fallbackBrowserReverseGeocode(lat, lng);
              if (browserGeo && browserGeo.success) {
                geo = Object.assign({}, geo || {}, browserGeo);
              }
            }

            if (geo && (geo.state || geo.district || geo.city || geo.pincode || geo.locality || geo.street_name)) {
              applyDetectedLocation(geo);

              const hasWard = Boolean(geo.ward_number && wardInput && wardInput.value);
              const missingCritical = !geo.district || !geo.pincode;

              if (gpsStatusText) {
                const summary = [districtHidden && districtHidden.value, cityHidden && cityHidden.value, pincodeInput && pincodeInput.value].filter(Boolean).join(' • ');
                gpsStatusText.textContent = (hasWard && wardSelect)
                  ? `GPS (${lat}, ${lng}) — ${summary} • ${wardInput.value}`
                  : `GPS (${lat}, ${lng}) — ${summary}`;
                gpsStatusText.style.display = 'block';
                gpsStatusText.style.color = missingCritical ? '#d97706' : '#16a34a';
              }

              if (window.showToast) {
                if (missingCritical || (wardSelect && !hasWard)) {
                  window.showToast(
                    wardSelect && !hasWard
                      ? tr('GPS coordinates and address details detected. Please select any unavailable fields manually.')
                      : tr('GPS coordinates captured. Please verify any missing address details.'),
                    'info',
                    tr('Location Detected')
                  );
                } else {
                  window.showToast(tr('All location details and GPS coordinates populated automatically.'), 'success', tr('Location Detected'));
                }
              }
            } else {
              reverseFailed = true;
              if (gpsStatusText) {
                gpsStatusText.textContent = tr(`GPS Coordinates Captured (${lat}, ${lng}), but address details could not be resolved automatically.`);
                gpsStatusText.style.display = 'block';
                gpsStatusText.style.color = '#d97706';
              }
              if (window.showToast) {
                window.showToast(tr('GPS coordinates captured, but reverse geocoding failed. Please select State, District, and City manually.'), 'warning', tr('Partial Location Data'));
              }
            }

            detectBtn.disabled = false;
            detectBtn.innerHTML = origHtml;
            if (window.lucide) lucide.createIcons();
            if (!reverseFailed && onLocationUpdated) onLocationUpdated();
          },
          (err) => {
            detectBtn.disabled = false;
            detectBtn.innerHTML = origHtml;
            if (window.lucide) lucide.createIcons();

            let msg = tr('Could not retrieve GPS coordinates. Please check location settings or enter address manually.');
            let title = tr('Location Unavailable');
            if (err && err.code === 1) {
              title = tr('Location Permission Denied');
              msg = tr('GPS location access was denied. Please enable location permission in browser settings or enter the address manually.');
            } else if (err && err.code === 2) {
              title = tr('Location Services Unavailable');
              msg = tr('Your device location services appear disabled or unavailable. Enable GPS or select the address manually.');
            } else if (err && err.code === 3) {
              title = tr('Location Request Timed Out');
              msg = tr('GPS signal took too long to respond. Please retry or fill in the address manually.');
            }

            if (gpsStatusText) {
              gpsStatusText.textContent = msg;
              gpsStatusText.style.display = 'block';
              gpsStatusText.style.color = '#d97706';
            }
            if (window.showToast) {
              window.showToast(msg, 'warning', title);
            }
          },
          { enableHighAccuracy: true, timeout: 12000, maximumAge: 0 }
        );
      });
    }

    return {
      applyDetectedLocation,
      refreshDistricts,
      refreshCities,
      refreshWards
    };
  };
})();
