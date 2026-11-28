"""
Multilingual translation engine backed directly by src/locales/{en,ta,hi}/translation.json.
Preserves technical identifiers, emails, references, and user-entered values unchanged.
"""
import json
import os
import re

SUPPORTED_LANGUAGES = ('en', 'ta', 'hi')
LANGUAGE_META = [
    {'code': 'en', 'name': 'English', 'native': 'English'},
    {'code': 'ta', 'name': 'Tamil', 'native': 'தமிழ்'},
    {'code': 'hi', 'name': 'Hindi', 'native': 'हिन्दी'},
]

_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
_LOCALES_DIR = os.path.join(_BASE_DIR, 'src', 'locales')


def _load_locale_file(lang):
    path = os.path.join(_LOCALES_DIR, lang, 'translation.json')
    if not os.path.isfile(path):
        return {'keys': {}, 'phrases': {}}
    with open(path, 'r', encoding='utf-8') as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        return {'keys': {}, 'phrases': {}}
    return {
        'keys': data.get('keys') if isinstance(data.get('keys'), dict) else {},
        'phrases': data.get('phrases') if isinstance(data.get('phrases'), dict) else {},
    }


LOCALE_BUNDLES = {lang: _load_locale_file(lang) for lang in SUPPORTED_LANGUAGES}

# Backward-compatible TRANSLATIONS dict keyed by structured keys
TRANSLATIONS = {}
for _k in LOCALE_BUNDLES['en']['keys']:
    TRANSLATIONS[_k] = {
        lang: LOCALE_BUNDLES[lang]['keys'].get(_k, LOCALE_BUNDLES['en']['keys'].get(_k, _k))
        for lang in SUPPORTED_LANGUAGES
    }

_PHRASES_EXACT = {lang: dict(LOCALE_BUNDLES[lang]['phrases']) for lang in SUPPORTED_LANGUAGES}
_PHRASES_NORM = {}
_EN_PHRASES_BY_NORM = {}

for _en_phrase in _PHRASES_EXACT['en']:
    _norm = ' '.join(_en_phrase.split()).lower()
    _EN_PHRASES_BY_NORM[_norm] = _en_phrase
    for _lang in SUPPORTED_LANGUAGES:
        _PHRASES_NORM.setdefault(_lang, {})[_norm] = _PHRASES_EXACT[_lang].get(_en_phrase, _en_phrase)


def normalize_lang(lang, default='en'):
    if not lang:
        return default
    code = str(lang).strip().lower().split('-')[0].split('_')[0]
    return code if code in SUPPORTED_LANGUAGES else default


def get_translation(key, lang='en', default=None):
    """Retrieve translated string by key with safe fallback to English."""
    lang = normalize_lang(lang)
    val = LOCALE_BUNDLES[lang]['keys'].get(key)
    if val:
        return val
    en_val = LOCALE_BUNDLES['en']['keys'].get(key)
    if en_val:
        return en_val
    return default if default is not None else key


def _translate_dynamic_sentence(text_str, lang):
    """Translate parameterized runtime strings cleanly while preserving IDs and names."""
    exact = _PHRASES_EXACT.get(lang, {}).get(text_str)
    if exact:
        return exact
    norm_key = ' '.join(text_str.split()).lower()
    norm_hit = _PHRASES_NORM.get(lang, {}).get(norm_key)
    if norm_hit:
        return norm_hit

    if text_str.endswith((':', '.', '!', '?', '...')):
        for punct in ('...', ':', '.', '!', '?'):
            if text_str.endswith(punct):
                stem = text_str[:-len(punct)].strip()
                stem_hit = _PHRASES_NORM.get(lang, {}).get(' '.join(stem.split()).lower())
                if stem_hit:
                    return stem_hit + punct

    patterns = (
        (
            r'^Ward\s+([A-Za-z0-9-]+)$',
            {'ta': lambda m: "வார்டு {}".format(m.group(1)), 'hi': lambda m: "वार्ड {}".format(m.group(1))},
        ),
        (
            r'^Complaint registered successfully!\s*Your tracking Reference ID is\s+([A-Z0-9-]+)\.?$',
            {
                'ta': lambda m: "புகார் வெற்றிகரமாகப் பதிவு செய்யப்பட்டது! உங்கள் கண்காணிப்பு எண்: {}.".format(m.group(1)),
                'hi': lambda m: "शिकायत सफलतापूर्वक दर्ज हो गई! आपकी ट्रैकिंग संदर्भ आईडी {} है।".format(m.group(1)),
            },
        ),
        (
            r'^Complaint #(\d+) could not be located or has been archived\.$',
            {
                'ta': lambda m: "புகார் #{} கிடைக்கவில்லை அல்லது காப்பகப்படுத்தப்பட்டுள்ளது.".format(m.group(1)),
                'hi': lambda m: "शिकायत #{} नहीं मिली या संग्रहीत कर दी गई है।".format(m.group(1)),
            },
        ),
        (
            r'^Complaint #(\d+) was not found in your authorized department schedule\.$',
            {
                'ta': lambda m: "உங்கள் அதிகார எல்லைக்குட்பட்ட துறை அட்டவணையில் புகார் #{} கிடைக்கவில்லை.".format(m.group(1)),
                'hi': lambda m: "आपके अधिकृत विभाग शेड्यूल में शिकायत #{} नहीं मिली।".format(m.group(1)),
            },
        ),
        (
            r'^Complaint #(\d+) was not found or is not accessible\.$',
            {
                'ta': lambda m: "புகார் #{} கிடைக்கவில்லை அல்லது அணுக முடியவில்லை.".format(m.group(1)),
                'hi': lambda m: "शिकायत #{} नहीं मिली या सुलभ नहीं है।".format(m.group(1)),
            },
        ),
        (
            r'^Task #(\d+) was not found in your assignments queue\.$',
            {
                'ta': lambda m: "உங்கள் பணி ஒதுக்கீடு வரிசையில் பணி #{} கிடைக்கவில்லை.".format(m.group(1)),
                'hi': lambda m: "आपकी आवंटन कतार में कार्य #{} नहीं मिला।".format(m.group(1)),
            },
        ),
        (
            r"^Task is already in status '([^']+)'\.$",
            {
                'ta': lambda m: "பணி ஏற்கனவே '{}' நிலையில் உள்ளது.".format(translate_text(m.group(1), 'ta')),
                'hi': lambda m: "कार्य पहले से '{}' स्थिति में है।".format(translate_text(m.group(1), 'hi')),
            },
        ),
        (
            r'^Task ([A-Z0-9-]+) accepted and moved to In Progress\.$',
            {
                'ta': lambda m: "பணி {} ஏற்றுக்கொள்ளப்பட்டு 'நடைபெறுகிறது' நிலைக்கு மாற்றப்பட்டது.".format(m.group(1)),
                'hi': lambda m: "कार्य {} स्वीकार कर 'प्रगति में' ले जाया गया।".format(m.group(1)),
            },
        ),
        (
            r'^Priority updated to ([A-Za-z]+)\.$',
            {
                'ta': lambda m: "முன்னுரிமை {} எனப் புதுப்பிக்கப்பட்டது.".format(translate_text(m.group(1).title(), 'ta')),
                'hi': lambda m: "प्राथमिकता {} में अपडेट की गई।".format(translate_text(m.group(1).title(), 'hi')),
            },
        ),
        (
            r'^User (.+) created successfully\.$',
            {
                'ta': lambda m: "பயனர் {} வெற்றிகரமாக உருவாக்கப்பட்டார்.".format(m.group(1)),
                'hi': lambda m: "उपयोगकर्ता {} सफलतापूर्वक बनाया गया।".format(m.group(1)),
            },
        ),
        (
            r"^Field worker '([^']+)' \(([^)]+)\) created in (.+)\.$",
            {
                'ta': lambda m: "களப் பணியாளர் '{}' ({}) {} துறையில் உருவாக்கப்பட்டார்.".format(m.group(1), m.group(2), translate_text(m.group(3), 'ta')),
                'hi': lambda m: "फील्ड कार्यकर्ता '{}' ({}) {} में बनाया गया।".format(m.group(1), m.group(2), translate_text(m.group(3), 'hi')),
            },
        ),
        (
            r'^Unauthorized access\.\s*You have been redirected to your ([A-Za-z]+) dashboard\.$',
            {
                'ta': lambda m: "அங்கீகரிக்கப்படாத அணுகல். உங்கள் {} பலகைக்குத் திருப்பி விடப்பட்டுள்ளீர்கள்.".format(translate_text(m.group(1).lower(), 'ta')),
                'hi': lambda m: "अनधिकृत पहुंच। आपको आपके {} डैशबोर्ड पर पुनर्निर्देशित किया गया है।".format(translate_text(m.group(1).lower(), 'hi')),
            },
        ),
        (
            r'^(Action failed|Dispatch failed|Update failed|Escalation failed|Assignment failed|Verification action failed|Worker operation failed|Error registering complaint|Failed to reopen complaint|Error purging test data):\s*(.+)$',
            {
                'ta': lambda m: "{}: {}".format(translate_text(m.group(1), 'ta'), m.group(2)),
                'hi': lambda m: "{}: {}".format(translate_text(m.group(1), 'hi'), m.group(2)),
            },
        ),
        (
            r'^Assigned to (.+?)\. Assigned Officer: (.+?)\.$',
            {
                'ta': lambda m: "{} துறைக்கு ஒதுக்கப்பட்டது. ஒதுக்கப்பட்ட அதிகாரி: {}.".format(translate_text(m.group(1), 'ta'), m.group(2)),
                'hi': lambda m: "{} को आवंटित। आवंटित अधिकारी: {}।".format(translate_text(m.group(1), 'hi'), m.group(2)),
            },
        ),
        (
            r'^Administrator assigned to (.+?) \(Officer: (.+?)\)\. Remarks: (.+)$',
            {
                'ta': lambda m: "நிர்வாகி {} துறைக்கு ஒதுக்கினார் (அதிகாரி: {}). குறிப்பு: {}".format(translate_text(m.group(1), 'ta'), m.group(2), m.group(3)),
                'hi': lambda m: "प्रशासक ने {} को आवंटित किया (अधिकारी: {})। टिप्पणी: {}".format(translate_text(m.group(1), 'hi'), m.group(2), m.group(3)),
            },
        ),
        (
            r'^Assigned to Field Technician (.+?)\. Instructions: (.+)$',
            {
                'ta': lambda m: "களப் பணியாளர் {}-க்கு ஒதுக்கப்பட்டது. அறிவுறுத்தல்கள்: {}".format(m.group(1), m.group(2)),
                'hi': lambda m: "फील्ड तकनीशियन {} को आवंटित। निर्देश: {}".format(m.group(1), m.group(2)),
            },
        ),
        (
            r'^Verified and approved by Officer (.+?)\. Remarks: (.+)$',
            {
                'ta': lambda m: "அதிகாரி {} சரிபார்த்து அங்கீகரித்தார். குறிப்பு: {}".format(m.group(1), m.group(2)),
                'hi': lambda m: "अधिकारी {} द्वारा सत्यापित और अनुमोदित। टिप्पणी: {}".format(m.group(1), m.group(2)),
            },
        ),
        (
            r'^Returned for rework by Officer (.+?)\. Reason: (.+)$',
            {
                'ta': lambda m: "அதிகாரி {} மறுபணிக்குத் திருப்பி அனுப்பினார். காரணம்: {}".format(m.group(1), m.group(2)),
                'hi': lambda m: "अधिकारी {} द्वारा पुनर्कार्य हेतु लौटाया गया। कारण: {}".format(m.group(1), m.group(2)),
            },
        ),
        (
            r'^Officer requested rework:\s*(.+)$',
            {
                'ta': lambda m: "அதிகாரி மறுபணி கோரினார்: {}".format(m.group(1)),
                'hi': lambda m: "अधिकारी ने पुनर्कार्य का अनुरोध किया: {}".format(m.group(1)),
            },
        ),
        (
            r'^Are you sure you want to (disable|activate) ([a-z ]+?) account (.+)\?$',
            {
                'ta': lambda m: "{} கணக்கை {} விரும்புகிறீர்களா?".format(m.group(3), 'முடக்க' if m.group(1).lower() == 'disable' else 'செயல்படுத்த'),
                'hi': lambda m: "क्या आप वाकई खाता {} को {} करना चाहते हैं?".format(m.group(3), 'अक्षम' if m.group(1).lower() == 'disable' else 'सक्रिय'),
            },
        ),
        (
            r'^Permanently delete ([a-z ]+?) account (.+?)\? All associated records will be removed\. This cannot be undone\.$',
            {
                'ta': lambda m: "{} கணக்கை நிரந்தரமாக நீக்கவா? தொடர்புடைய அனைத்துப் பதிவுகளும் நீக்கப்படும். இதைத் திரும்பப் பெற முடியாது.".format(m.group(2)),
                'hi': lambda m: "क्या खाता {} को स्थायी रूप से हटाएं? सभी संबंधित रिकॉर्ड हटा दिए जाएंगे। इसे पूर्ववत नहीं किया जा सकता।".format(m.group(2)),
            },
        ),
        (
            r'^(Complaint Submitted|New Complaint|Status Update|New Complaint Assigned|New Field Task Assigned|Worker Assigned|Complaint Resolved|Rework Required|Rework Requested|Work Accepted|In Progress|Site Evidence Added|Completion Evidence Submitted|New Contact Inquiry):\s*(.+)$',
            {
                'ta': lambda m: "{}: {}".format(translate_text(m.group(1), 'ta'), m.group(2)),
                'hi': lambda m: "{}: {}".format(translate_text(m.group(1), 'hi'), m.group(2)),
            },
        ),
    )

    for regex, handlers in patterns:
        match = re.match(regex, text_str, flags=re.IGNORECASE)
        if match and lang in handlers:
            return handlers[lang](match)

    return text_str


def translate_text(text, lang='en'):
    """Translate literal UI/dynamic text via src/locales/{lang}/translation.json, preserving text when unmapped."""
    if text is None:
        return ''
    text_str = str(text)
    lang = normalize_lang(lang)
    if lang == 'en' or not text_str.strip():
        return text_str
    return _translate_dynamic_sentence(text_str, lang)


def translate_json_payload(payload, lang='en'):
    """Translate user-facing message/error/title fields in JSON payloads cleanly."""
    lang = normalize_lang(lang)
    if lang == 'en' or not isinstance(payload, dict):
        return payload

    out = dict(payload)
    for key in ('message', 'error', 'title'):
        if isinstance(out.get(key), str) and out[key].strip():
            out[key] = translate_text(out[key], lang)

    if isinstance(out.get('notifications'), list):
        translated_notifs = []
        for item in out['notifications']:
            if isinstance(item, dict):
                n = dict(item)
                if isinstance(n.get('title'), str):
                    n['title'] = translate_text(n['title'], lang)
                if isinstance(n.get('message'), str):
                    n['message'] = translate_text(n['message'], lang)
                translated_notifs.append(n)
            else:
                translated_notifs.append(item)
        out['notifications'] = translated_notifs

    return out
