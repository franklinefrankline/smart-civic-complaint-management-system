(function () {
  const SUPPORTED_LANGS = ['en', 'ta', 'hi'];
  const INTL_LOCALES = { en: 'en-IN', ta: 'ta-IN', hi: 'hi-IN' };
  const STORAGE_KEY = 'sccmt_lang';

  function getMeta(name) {
    const el = document.querySelector(`meta[name="${name}"]`);
    return el ? (el.getAttribute('content') || '').trim() : '';
  }

  function normalizeLang(lang) {
    if (!lang) return 'en';
    const short = String(lang).trim().toLowerCase().split(/[-_]/)[0];
    return SUPPORTED_LANGS.includes(short) ? short : 'en';
  }

  function getCookie(name) {
    try {
      const m = document.cookie.match(new RegExp('(?:^|;\\s*)' + name + '=([^;]*)'));
      return m ? decodeURIComponent(m[1]) : '';
    } catch (_) {
      return '';
    }
  }

  function setLangCookies(lang, isExplicit) {
    try {
      document.cookie = `${STORAGE_KEY}=${encodeURIComponent(lang)}; path=/; max-age=31536000; SameSite=Lax`;
      if (isExplicit !== undefined) {
        document.cookie = `sccmt_lang_explicit=${isExplicit ? '1' : '0'}; path=/; max-age=31536000; SameSite=Lax`;
      }
    } catch (_) {}
  }

  const serverLang = normalizeLang(getMeta('active-lang') || document.documentElement.getAttribute('lang') || 'en');
  const isUserLoggedIn = getMeta('user-authenticated') === '1';

  let initialLang = 'en';
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    const cookieLang = getCookie(STORAGE_KEY);
    if (isUserLoggedIn && serverLang !== 'en' && !stored) {
      // Cross-device login: restore account's saved preference from DB when browser has none
      initialLang = serverLang;
    } else if (stored && SUPPORTED_LANGS.includes(normalizeLang(stored))) {
      initialLang = normalizeLang(stored);
    } else if (cookieLang && SUPPORTED_LANGS.includes(normalizeLang(cookieLang))) {
      initialLang = normalizeLang(cookieLang);
    } else {
      initialLang = serverLang || 'en';
    }
    localStorage.setItem(STORAGE_KEY, initialLang);
    localStorage.setItem('i18nextLng', initialLang);
    setLangCookies(initialLang);
  } catch (_) {
    initialLang = serverLang || 'en';
  }

  // Canonical maps built dynamically from src/locales/{en,ta,hi}/translation.json
  const loadedBundles = {};
  const reverseToCanonicalEn = new Map();
  const normEnToKey = new Map();
  let observer = null;
  let applyingDom = false;
  let mutationTimer = null;
  const origTextMap = new WeakMap();

  function registerBundleMaps(lang, data) {
    if (!data || typeof data !== 'object') return;
    loadedBundles[lang] = data;
    const phrases = data.phrases || {};
    Object.keys(phrases).forEach((enPhrase) => {
      const normEn = enPhrase.replace(/\s+/g, ' ').trim().toLowerCase();
      if (normEn) normEnToKey.set(normEn, enPhrase);
      const val = phrases[enPhrase];
      if (typeof val === 'string' && val.trim()) {
        const normVal = val.replace(/\s+/g, ' ').trim().toLowerCase();
        if (!reverseToCanonicalEn.has(normVal)) {
          reverseToCanonicalEn.set(normVal, enPhrase);
        }
      }
    });
  }

  async function fetchLocaleJson(lang) {
    if (loadedBundles[lang]) return loadedBundles[lang];
    const urls = [
      `/static/locales/${lang}/translation.json?v=20261127a`,
      `/locales/${lang}/translation.json?v=20261127a`
    ];
    for (const url of urls) {
      try {
        const res = await fetch(url, { credentials: 'include' });
        if (res.ok) {
          const data = await res.json();
          registerBundleMaps(lang, data);
          if (window.i18next && typeof window.i18next.addResourceBundle === 'function') {
            window.i18next.addResourceBundle(lang, 'translation', data, true, true);
          }
          return data;
        }
      } catch (_) {}
    }
    return null;
  }

  function resolveCanonicalEnglish(rawText) {
    if (!rawText) return '';
    const trimmed = String(rawText).replace(/\s+/g, ' ').trim();
    if (!trimmed) return '';
    const norm = trimmed.toLowerCase();
    if (normEnToKey.has(norm)) return normEnToKey.get(norm);
    if (reverseToCanonicalEn.has(norm)) return reverseToCanonicalEn.get(norm);
    return trimmed;
  }

  function lookupExactPhrase(canonicalEn, targetLang) {
    if (!canonicalEn) return null;
    if (targetLang === 'en') {
      const norm = canonicalEn.replace(/\s+/g, ' ').trim().toLowerCase();
      return normEnToKey.get(norm) || (loadedBundles.en && loadedBundles.en.phrases && loadedBundles.en.phrases[canonicalEn]) || null;
    }
    if (window.i18next && window.i18next.isInitialized) {
      const direct = window.i18next.t(`phrases.${canonicalEn}`, { lng: targetLang, nsSeparator: false, keySeparator: false, defaultValue: '' });
      if (direct) return direct;
      // Use direct resource lookup cleanly (supports dots/special chars inside phrase keys)
      const resObj = window.i18next.getResourceBundle(targetLang, 'translation');
      if (resObj) {
        if (resObj.keys && Object.prototype.hasOwnProperty.call(resObj.keys, canonicalEn)) {
          return resObj.keys[canonicalEn];
        }
        if (resObj.phrases && Object.prototype.hasOwnProperty.call(resObj.phrases, canonicalEn)) {
          return resObj.phrases[canonicalEn];
        }
      }
    }
    const bundle = loadedBundles[targetLang];
    if (bundle) {
      if (bundle.keys && bundle.keys[canonicalEn]) return bundle.keys[canonicalEn];
      if (bundle.phrases && bundle.phrases[canonicalEn]) return bundle.phrases[canonicalEn];
      const normKey = normEnToKey.get(canonicalEn.replace(/\s+/g, ' ').trim().toLowerCase());
      if (normKey && bundle.phrases && bundle.phrases[normKey]) return bundle.phrases[normKey];
    }
    return null;
  }

  function translateDynamicPatterns(text, lang) {
    if (lang === 'en') return null;

    // 1. Field validation messages from main.js
    let m;
    if ((m = text.match(/^(.+?)\s+is required\.$/))) {
      const lbl = translateString(m[1], lang);
      return lang === 'ta' ? `${lbl} அவசியம்.` : `${lbl} आवश्यक है।`;
    }
    if ((m = text.match(/^(.+?)\s+must be at least\s+(\d+)\s+characters\.$/))) {
      const lbl = translateString(m[1], lang);
      return lang === 'ta' ? `${lbl} குறைந்தது ${m[2]} எழுத்துகள் இருக்க வேண்டும்.` : `${lbl} कम से कम ${m[2]} अक्षरों का होना चाहिए।`;
    }
    if ((m = text.match(/^(.+?)\s+must be no more than\s+(\d+)\s+characters\.$/))) {
      const lbl = translateString(m[1], lang);
      return lang === 'ta' ? `${lbl} அதிகபட்சம் ${m[2]} எழுத்துகளுக்குள் இருக்க வேண்டும்.` : `${lbl} अधिकतम ${m[2]} अक्षरों का होना चाहिए।`;
    }
    if ((m = text.match(/^Please enter a valid\s+(.+?)\s+format\.$/))) {
      const lbl = translateString(m[1], lang);
      return lang === 'ta' ? `சரியான ${lbl} வடிவத்தை உள்ளிடவும்.` : `कृपया मान्य ${lbl} प्रारूप दर्ज करें।`;
    }
    if ((m = text.match(/^(.+?)\s+must be at least\s+([0-9.]+)\.$/))) {
      const lbl = translateString(m[1], lang);
      return lang === 'ta' ? `${lbl} குறைந்தது ${m[2]} இருக்க வேண்டும்.` : `${lbl} कम से कम ${m[2]} होना चाहिए।`;
    }
    if ((m = text.match(/^(.+?)\s+must be at most\s+([0-9.]+)\.$/))) {
      const lbl = translateString(m[1], lang);
      return lang === 'ta' ? `${lbl} அதிகபட்சம் ${m[2]} இருக்க வேண்டும்.` : `${lbl} अधिकतम ${m[2]} होना चाहिए।`;
    }
    if ((m = text.match(/^Please check\s+(.+?)\.$/))) {
      const lbl = translateString(m[1], lang);
      return lang === 'ta' ? `${lbl} சரிபார்க்கவும்.` : `कृपया ${lbl} जांचें।`;
    }
    if ((m = text.match(/^Ward\s+([A-Za-z0-9-]+)$/i))) {
      return lang === 'ta' ? `வார்டு ${m[1]}` : `वार्ड ${m[1]}`;
    }
    if ((m = text.match(/^Are you sure you want to change the complaint status to "([^"]+)"\?$/))) {
      const st = translateString(m[1], lang);
      return lang === 'ta' ? `புகார் நிலையை "${st}" என மாற்ற விரும்புகிறீர்களா?` : `क्या आप वाकई शिकायत की स्थिति "${st}" में बदलना चाहते हैं?`;
    }
    if ((m = text.match(/^(\d+)\s+Unread$/))) {
      return lang === 'ta' ? `${m[1]} படிக்காதவை` : `${m[1]} अपठित`;
    }
    if ((m = text.match(/^(\d+)\s+Departments$/))) {
      return lang === 'ta' ? `${m[1]} துறைகள்` : `${m[1]} विभाग`;
    }
    if ((m = text.match(/^GPS Coordinates Captured:\s*([0-9.-]+,\s*[0-9.-]+)\s*[—-]\s*resolving administrative details\.\.\.$/))) {
      return lang === 'ta'
        ? `ஜிபிஎஸ் ஆயத்தொலைவுகள் பெறப்பட்டன: ${m[1]} — நிர்வாக விவரங்கள் பெறப்படுகின்றன...`
        : `जीपीएस निर्देशांक कैप्चर हो गए: ${m[1]} — प्रशासनिक विवरण प्राप्त किए जा रहे हैं...`;
    }
    if ((m = text.match(/^GPS Coordinates Captured \(([0-9.-]+,\s*[0-9.-]+)\), but address details could not be resolved automatically\.$/))) {
      return lang === 'ta'
        ? `ஜிபிஎஸ் ஆயத்தொலைவுகள் பெறப்பட்டன (${m[1]}), ஆனால் முகவரி விவரங்களைத் தானாகப் பெற முடியவில்லை.`
        : `जीपीएस निर्देशांक कैप्चर हो गए (${m[1]}), लेकिन पता विवरण स्वचालित रूप से प्राप्त नहीं हो सका।`;
    }
    if ((m = text.match(/^Server is waking up or busy \(HTTP (\d+)\)\. Please retry in a few seconds\.$/))) {
      return lang === 'ta'
        ? `சேவையகம் தொடங்குகிறது அல்லது பிஸியாக உள்ளது (HTTP ${m[1]}). சில நொடிகளில் மீண்டும் முயற்சிக்கவும்.`
        : `सर्वर शुरू हो रहा है या व्यस्त है (HTTP ${m[1]})। कृपया कुछ सेकंड में पुनः प्रयास करें।`;
    }
    if ((m = text.match(/^Unexpected response \((\d+)\)\. Please try again\.$/))) {
      return lang === 'ta'
        ? `எதிர்பாராத பதில் (${m[1]}). மீண்டும் முயற்சிக்கவும்.`
        : `अप्रत्याशित प्रतिक्रिया (${m[1]})। कृपया पुनः प्रयास करें।`;
    }
    if ((m = text.match(/^Action failed \((\d+)\)$/))) {
      return lang === 'ta' ? `செயல் தோல்வியடைந்தது (${m[1]})` : `कार्रवाई विफल (${m[1]})`;
    }
    if ((m = text.match(/^(Just now|\d+m ago|\d+h ago|\d+d ago)$/))) {
      if (m[1] === 'Just now') return lang === 'ta' ? 'இப்போது' : 'अभी';
      if (m[1].endsWith('m ago')) {
        const n = parseInt(m[1], 10);
        return lang === 'ta' ? `${n} நிமி முன்பு` : `${n} मि पहले`;
      }
      if (m[1].endsWith('h ago')) {
        const n = parseInt(m[1], 10);
        return lang === 'ta' ? `${n} மணி முன்பு` : `${n} घं पहले`;
      }
      if (m[1].endsWith('d ago')) {
        const n = parseInt(m[1], 10);
        return lang === 'ta' ? `${n} நாட்கள் முன்பு` : `${n} दिन पहले`;
      }
    }
    if ((m = text.match(/^Are you sure you want to (disable|activate) ([a-z ]+?) account (.+)\?$/i))) {
      return lang === 'ta'
        ? `${m[3]} கணக்கை ${m[1].toLowerCase() === 'disable' ? 'முடக்க' : 'செயல்படுத்த'} விரும்புகிறீர்களா?`
        : `क्या आप वाकई खाता ${m[3]} को ${m[1].toLowerCase() === 'disable' ? 'अक्षम' : 'सक्रिय'} करना चाहते हैं?`;
    }
    if ((m = text.match(/^Permanently delete ([a-z ]+?) account (.+?)\? All associated records will be removed\. This cannot be undone\.$/i))) {
      return lang === 'ta'
        ? `${m[2]} கணக்கை நிரந்தரமாக நீக்கவா? தொடர்புடைய அனைத்துப் பதிவுகளும் நீக்கப்படும். இதைத் திரும்பப் பெற முடியாது.`
        : `क्या खाता ${m[2]} को स्थायी रूप से हटाएं? सभी संबंधित रिकॉर्ड हटा दिए जाएंगे। इसे पूर्ववत नहीं किया जा सकता।`;
    }
    return null;
  }

  function translateString(rawText, langOverride) {
    if (rawText === null || rawText === undefined) return '';
    const lang = normalizeLang(langOverride || (window.i18next && window.i18next.language) || initialLang);
    const s = String(rawText);
    const trimmed = s.replace(/\s+/g, ' ').trim();
    if (!trimmed) return s;

    // Skip technical identifiers, emails, complaint refs, pure numbers/symbols
    if (
      /^[#@]?\d+(?:[.,:/-]\d+)*%?$/.test(trimmed) ||
      /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed) ||
      /^(CMP|EMP)-[A-Z0-9-]+$/i.test(trimmed) ||
      /^(English|தமிழ்|हिन्दी)$/.test(trimmed)
    ) {
      return s;
    }

    const canonical = resolveCanonicalEnglish(trimmed);
    const hit = lookupExactPhrase(canonical, lang);
    if (hit) {
      const lead = s.match(/^\s*/)[0];
      const trail = s.match(/\s*$/)[0];
      return lead + hit + trail;
    }

    // Check trailing punctuation stem (":" / "." / "!" / "?")
    for (const punct of ['...', ':', '.', '!', '?']) {
      if (canonical.endsWith(punct) && canonical.length > punct.length) {
        const stem = canonical.slice(0, -punct.length).trim();
        const stemHit = lookupExactPhrase(stem, lang);
        if (stemHit) {
          const lead = s.match(/^\s*/)[0];
          const trail = s.match(/\s*$/)[0];
          return lead + stemHit + punct + trail;
        }
      }
    }

    // Check page titles separated by " | "
    if (canonical.includes(' | ')) {
      const parts = canonical.split(' | ').map((part) => translateString(part, lang));
      return parts.join(' | ');
    }

    const dyn = translateDynamicPatterns(canonical, lang);
    if (dyn) {
      const lead = s.match(/^\s*/)[0];
      const trail = s.match(/\s*$/)[0];
      return lead + dyn + trail;
    }

    if (lang === 'en') {
      const lead = s.match(/^\s*/)[0];
      const trail = s.match(/\s*$/)[0];
      return lead + canonical + trail;
    }
    return s;
  }

  function isExcludedNode(node) {
    const parent = node.parentElement;
    if (!parent) return true;
    const tag = parent.tagName;
    if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'NOSCRIPT' || tag === 'TEXTAREA' || tag === 'CODE' || tag === 'PRE') {
      return true;
    }
    if (parent.closest('[data-no-i18n], .notranslate, select[data-lang-switcher]')) {
      return true;
    }
    return false;
  }

  function translateAttributes(el, lang) {
    const attrs = ['placeholder', 'title', 'aria-label', 'data-confirm', 'data-confirm-title', 'data-confirm-btn', 'data-tooltip'];
    attrs.forEach((attr) => {
      if (!el.hasAttribute(attr)) return;
      const storeKey = `i18nOrig_${attr.replace(/[^a-zA-Z0-9]/g, '_')}`;
      if (!el.dataset[storeKey]) {
        el.dataset[storeKey] = resolveCanonicalEnglish(el.getAttribute(attr));
      }
      const orig = el.dataset[storeKey];
      const next = translateString(orig, lang);
      if (next && el.getAttribute(attr) !== next) {
        el.setAttribute(attr, next);
      }
    });
  }

  function formatNumbersAndDates(rootEl, lang) {
    const locale = INTL_LOCALES[lang] || 'en-IN';
    rootEl.querySelectorAll('time[data-utc]').forEach((el) => {
      const utc = el.getAttribute('data-utc');
      if (!utc) return;
      const d = new Date(utc);
      if (isNaN(d.getTime())) return;
      try {
        el.textContent = new Intl.DateTimeFormat(locale, {
          year: 'numeric',
          month: 'short',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit'
        }).format(d);
      } catch (_) {}
    });
  }

  function applyTranslationsToDOM(rootEl, langOverride) {
    const lang = normalizeLang(langOverride || (window.i18next && window.i18next.language) || initialLang);
    const scope = rootEl || document;
    if (applyingDom) return;
    applyingDom = true;

    try {
      if (scope === document || scope === document.documentElement || scope === document.body) {
        document.documentElement.setAttribute('lang', lang);
        syncSwitcherControls(lang);
        if (document.title) {
          if (!document.documentElement.dataset.i18nOrigTitle) {
            document.documentElement.dataset.i18nOrigTitle = resolveCanonicalEnglish(document.title);
          }
          document.title = translateString(document.documentElement.dataset.i18nOrigTitle, lang);
        }
      }

      const rootNode = scope === document ? document.body : scope;
      if (!rootNode) return;

      // Translate attributes on elements
      if (rootNode.nodeType === 1) {
        translateAttributes(rootNode, lang);
        rootNode.querySelectorAll('*').forEach((el) => {
          if (!el.closest('[data-no-i18n], .notranslate')) {
            translateAttributes(el, lang);
          }
        });
      }

      // Translate text nodes cleanly
      const walker = document.createTreeWalker(rootNode, NodeFilter.SHOW_TEXT, null);
      const nodes = [];
      let cur;
      while ((cur = walker.nextNode())) {
        if (!isExcludedNode(cur) && cur.nodeValue && /[A-Za-z\u0B80-\u0BFF\u0900-\u097F]/.test(cur.nodeValue)) {
          nodes.push(cur);
        }
      }

      nodes.forEach((txtNode) => {
        if (!origTextMap.has(txtNode)) {
          const canon = resolveCanonicalEnglish(txtNode.nodeValue);
          const lead = txtNode.nodeValue.match(/^\s*/)[0];
          const trail = txtNode.nodeValue.match(/\s*$/)[0];
          origTextMap.set(txtNode, lead + canon + trail);
        }
        const orig = origTextMap.get(txtNode);
        const translated = translateString(orig, lang);
        if (translated !== txtNode.nodeValue) {
          txtNode.nodeValue = translated;
        }
      });

      formatNumbersAndDates(rootNode, lang);
    } finally {
      applyingDom = false;
    }
  }

  function syncSwitcherControls(lang) {
    const shortCode = lang === 'ta' ? 'த' : (lang === 'hi' ? 'हि' : 'EN');
    document.querySelectorAll('[data-lang-switcher]').forEach((sel) => {
      if (sel.value !== lang) sel.value = lang;
    });
    document.querySelectorAll('[data-lang-badge-code]').forEach((el) => {
      el.textContent = shortCode;
    });
  }

  async function persistLanguageToServer(lang) {
    const apiUrl = window.getApiUrl ? window.getApiUrl('/api/language') : '/api/language';
    try {
      await fetch(apiUrl, {
        method: 'POST',
        credentials: 'include',
        cache: 'no-store',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({ lang })
      });
    } catch (_) {}
  }

  async function setLanguage(nextLang, options) {
    const opts = options || {};
    const lang = normalizeLang(nextLang);
    await Promise.all([
      fetchLocaleJson('en'),
      fetchLocaleJson(lang)
    ]);

    try {
      localStorage.setItem(STORAGE_KEY, lang);
      localStorage.setItem('i18nextLng', lang);
    } catch (_) {}
    setLangCookies(lang, opts.explicit !== false);

    if (window.i18next && window.i18next.isInitialized) {
      await window.i18next.changeLanguage(lang);
    }

    applyTranslationsToDOM(document, lang);

    if (opts.syncServer !== false) {
      persistLanguageToServer(lang);
    }

    window.dispatchEvent(new CustomEvent('sccmt:language-changed', { detail: { lang } }));
    return lang;
  }

  function bindLanguageSwitchers() {
    document.addEventListener('change', (e) => {
      const sel = e.target.closest('[data-lang-switcher]');
      if (!sel) return;
      const chosen = normalizeLang(sel.value);
      setLanguage(chosen, { explicit: true, syncServer: true });
    });
  }

  function startMutationObserver() {
    if (observer || !document.body) return;
    observer = new MutationObserver(() => {
      if (applyingDom) return;
      clearTimeout(mutationTimer);
      mutationTimer = setTimeout(() => {
        const curLang = normalizeLang((window.i18next && window.i18next.language) || initialLang);
        if (curLang !== 'en') {
          applyTranslationsToDOM(document.body, curLang);
        }
      }, 40);
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  async function initI18n() {
    // Load English reference + initial active locale (plus preload other supported locales cleanly)
    await fetchLocaleJson('en');
    if (initialLang !== 'en') {
      await fetchLocaleJson(initialLang);
    }
    // Load remaining bundles quietly so instant offline/zero-delay switching works in 1ms
    SUPPORTED_LANGS.filter((l) => l !== 'en' && l !== initialLang).forEach((l) => {
      fetchLocaleJson(l);
    });

    if (window.i18next) {
      if (window.i18nextBrowserLanguageDetector) {
        window.i18next.use(window.i18nextBrowserLanguageDetector);
      }
      const resources = {};
      Object.keys(loadedBundles).forEach((l) => {
        resources[l] = { translation: loadedBundles[l] };
      });
      await window.i18next.init({
        lng: initialLang,
        fallbackLng: 'en',
        supportedLngs: SUPPORTED_LANGS,
        resources,
        detection: {
          order: ['localStorage', 'cookie', 'htmlTag', 'navigator'],
          lookupLocalStorage: STORAGE_KEY,
          lookupCookie: STORAGE_KEY,
          caches: ['localStorage', 'cookie']
        },
        interpolation: { escapeValue: false },
        keySeparator: '.',
        nsSeparator: false
      });
    }

    syncSwitcherControls(initialLang);
    if (initialLang !== serverLang) {
      applyTranslationsToDOM(document, initialLang);
      persistLanguageToServer(initialLang);
    } else if (initialLang !== 'en') {
      applyTranslationsToDOM(document, initialLang);
    }

    bindLanguageSwitchers();
    startMutationObserver();
    window.dispatchEvent(new CustomEvent('sccmt:i18n-ready', { detail: { lang: initialLang } }));
  }

  window.scfT = function (text, langOverride) {
    return translateString(text, langOverride);
  };
  window.applyI18nToDOM = applyTranslationsToDOM;
  window.setPortalLanguage = setLanguage;
  window.getPortalLanguage = function () {
    return normalizeLang((window.i18next && window.i18next.language) || initialLang);
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initI18n);
  } else {
    initI18n();
  }
})();
