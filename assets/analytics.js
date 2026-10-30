(() => {
  'use strict';
  const id = 'G-129XGJDT47';
  const preferenceKey = 'codeedge-analytics-choice-v1';
  const maxAge = 180 * 24 * 60 * 60 * 1000;
  let loaded = false;
  let allowed = false;
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(preferenceKey)); } catch (_) {}
  if (!saved || !['granted', 'denied'].includes(saved.choice) || !Number.isFinite(saved.at) || Date.now() - saved.at > maxAge) saved = null;

  const panel = document.querySelector('[data-analytics-panel]');
  if (!panel) return;
  panel.hidden = Boolean(saved);
  const settings = document.createElement('button');
  settings.type = 'button';
  settings.className = 'analytics-settings';
  settings.textContent = 'Cookie settings';
  (document.querySelector('.footer-bottom') || document.body).append(settings);
  const cleanUrl = value => {
    try { const u = new URL(value); return u.origin + u.pathname; } catch (_) { return ''; }
  };
  const context = () => ({ page_location: location.origin + location.pathname, page_referrer: cleanUrl(document.referrer), page_title: document.title });
  const event = name => {
    if (allowed && loaded) window.gtag('event', name, context());
  };
  function start() {
    allowed = true;
    window['ga-disable-' + id] = false;
    if (loaded) return;
    loaded = true;
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    window.gtag('consent', 'default', { analytics_storage: 'denied', ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied' });
    window.gtag('consent', 'update', { analytics_storage: 'granted', ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied' });
    window.gtag('js', new Date());
    window.gtag('config', id, { send_page_view: false, cookie_expires: maxAge / 1000, allow_google_signals: false, allow_ad_personalization_signals: false, ...context() });
    event('page_view');
    const script = document.createElement('script');
    script.async = true;
    script.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(id);
    document.head.append(script);
  }
  function save(choice) {
    try { localStorage.setItem(preferenceKey, JSON.stringify({ choice, at: Date.now() })); } catch (_) {}
    panel.hidden = true;
    settings.focus({ preventScroll: true });
    if (choice === 'granted') { start(); return; }
    allowed = false;
    window['ga-disable-' + id] = true;
    for (const item of document.cookie.split(';')) {
      const name = item.split('=')[0].trim();
      if (!/^_ga(?:_|$)/.test(name)) continue;
      for (const domain of ['', location.hostname, '.' + location.hostname]) {
        document.cookie = name + '=; Max-Age=0; Path=/' + (domain ? '; Domain=' + domain : '') + '; SameSite=Lax; Secure';
      }
    }
    if (loaded) location.reload();
  }
  panel.querySelector('[data-analytics-accept]').addEventListener('click', () => save('granted'));
  panel.querySelector('[data-analytics-reject]').addEventListener('click', () => save('denied'));
  settings.addEventListener('click', () => { document.documentElement.classList.remove('analytics-known'); panel.hidden = false; panel.querySelector('button').focus(); });
  document.addEventListener('click', e => {
    const link = e.target.closest('a[href]');
    if (!link) return;
    if (link.protocol === 'tel:') event('phone_click');
    else {
      try { if (new URL(link.href).hostname === 'wa.me') event('whatsapp_click'); } catch (_) {}
    }
  });
  const form = document.querySelector('[data-form] form, form[data-form]');
  if (form) form.addEventListener('submit', () => { if (form.checkValidity()) event('contact_request_prepared'); });
  if (saved?.choice === 'granted') start();
  else if (!saved) panel.hidden = false;
})();
