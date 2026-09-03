/* ==========================================================================
   platform.js — comportements propres a l'appareil
     * iPhone / iPad : hauteur reelle, clavier, plein ecran, installation
     * Android / bureau : invite d'installation native quand elle existe
   ========================================================================== */
(function (global) {
  'use strict';

  var ua = global.navigator.userAgent || '';
  var platform = global.navigator.platform || '';

  // iPadOS 13+ se declare comme un Mac : on le distingue par le tactile.
  var isIOS = /iPad|iPhone|iPod/.test(ua) ||
              (platform === 'MacIntel' && global.navigator.maxTouchPoints > 1);
  var isSafari = /^((?!chrome|android|crios|fxios).)*safari/i.test(ua);
  var isStandalone = global.navigator.standalone === true ||
                     global.matchMedia('(display-mode: standalone)').matches;

  var DISMISS_KEY = 'pyterm.install.dismissed';
  var deferredPrompt = null;

  /* ------------------------------------------------- hauteur et clavier */

  /* Sur iPhone, la barre d'URL et le clavier changent la hauteur utile sans
     changer 100vh. On pilote donc la hauteur depuis visualViewport.        */
  function syncHeight() {
    var vv = global.visualViewport;
    var height = vv ? vv.height : global.innerHeight;
    document.documentElement.style.setProperty('--app-height', height + 'px');
    if (global.PyApp && global.PyApp.editor) global.PyApp.editor.refresh();
  }

  function wireViewport() {
    syncHeight();
    if (global.visualViewport) {
      global.visualViewport.addEventListener('resize', syncHeight);
      global.visualViewport.addEventListener('scroll', syncHeight);
    }
    global.addEventListener('orientationchange', function () {
      setTimeout(syncHeight, 120);
    });
    global.addEventListener('resize', syncHeight);

    // Empeche iOS de faire glisser toute la page quand un champ prend le focus.
    document.addEventListener('focusin', function () {
      setTimeout(function () { global.scrollTo(0, 0); syncHeight(); }, 60);
    });
    document.addEventListener('focusout', function () {
      setTimeout(function () { global.scrollTo(0, 0); syncHeight(); }, 60);
    });
  }

  /* ------------------------------------------------------- installation */

  function buildSheet() {
    var sheet = document.createElement('div');
    sheet.id = 'install-sheet';
    sheet.className = 'sheet';
    sheet.hidden = true;

    var shareGlyph =
      '<svg viewBox="0 0 24 24" class="ios-share" aria-hidden="true">' +
      '<path d="M12 15V4M8.5 7.5L12 4l3.5 3.5"/>' +
      '<path d="M6 12H5a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-6a1 1 0 0 0-1-1h-1"/>' +
      '</svg>';

    var steps = isIOS
      ? ['Touchez ' + shareGlyph + ' <b>Partager</b>, en bas de Safari.',
         'Faites defiler, puis choisissez <b>Sur l\'ecran d\'accueil</b>.',
         'Touchez <b>Ajouter</b>. PyTerm apparait avec son icone.']
      : ['Ouvrez le menu du navigateur (⋮).',
         'Choisissez <b>Installer l\'application</b> ou <b>Ajouter a l\'ecran d\'accueil</b>.'];

    sheet.innerHTML =
      '<div class="sheet-card" role="dialog" aria-label="Installer PyTerm">' +
        '<img src="assets/icon-192.png" alt="" width="56" height="56" class="sheet-icon">' +
        '<h2>Installer PyTerm</h2>' +
        '<p class="sheet-lead">Pour l\'avoir comme une vraie application : icone sur ' +
          'l\'ecran d\'accueil, plein ecran, et fonctionnement hors connexion.</p>' +
        '<ol class="sheet-steps">' + steps.map(function (s) {
            return '<li>' + s + '</li>';
          }).join('') + '</ol>' +
        '<div class="row end">' +
          (isIOS ? '' : '<button class="btn primary" id="install-now">Installer</button>') +
          '<button class="btn" id="install-later">Plus tard</button>' +
        '</div>' +
      '</div>';

    document.body.appendChild(sheet);

    sheet.addEventListener('click', function (e) {
      if (e.target === sheet) hideSheet(false);
    });
    var later = sheet.querySelector('#install-later');
    if (later) later.addEventListener('click', function () { hideSheet(true); });
    var now = sheet.querySelector('#install-now');
    if (now) {
      now.addEventListener('click', function () {
        hideSheet(true);
        if (deferredPrompt) { deferredPrompt.prompt(); deferredPrompt = null; }
      });
    }
    return sheet;
  }

  function showSheet() {
    var sheet = document.getElementById('install-sheet') || buildSheet();
    sheet.hidden = false;
    requestAnimationFrame(function () { sheet.classList.add('is-open'); });
  }

  function hideSheet(remember) {
    var sheet = document.getElementById('install-sheet');
    if (!sheet) return;
    sheet.classList.remove('is-open');
    setTimeout(function () { sheet.hidden = true; }, 220);
    if (remember) {
      try { global.localStorage.setItem(DISMISS_KEY, '1'); } catch (e) { /* sans importance */ }
    }
  }

  function dismissed() {
    try { return global.localStorage.getItem(DISMISS_KEY) === '1'; }
    catch (e) { return false; }
  }

  /* ------------------------------------------------------------ moteur */

  /* Sur iPhone, aucun interpreteur ne tourne sur l'appareil : le moteur local
     suppose un noyau distant. Une page servie en HTTPS ne peut joindre qu'un
     noyau lui aussi en HTTPS — un http://192.168.x.x est bloque comme contenu
     mixte. On n'interdit donc pas le choix : on l'ouvre des qu'une adresse
     https est renseignee (tunnel, VPS), et on explique sinon.              */
  function backendNote() {
    var note = document.getElementById('backend-note');
    if (note) return note;
    note = document.createElement('p');
    note.id = 'backend-note';
    note.className = 'hint';
    var field = document.getElementById('field-kernel');
    if (field && field.parentNode) field.parentNode.insertBefore(note, field);
    return note;
  }

  function refreshBackendChoice() {
    var select = document.getElementById('set-backend');
    if (!select || !isIOS) return;
    var option = select.querySelector('option[value="native"]');
    if (!option) return;

    var input = document.getElementById('set-kernel-url');
    var url = (input && input.value || '').trim();
    var secure = /^https:\/\//i.test(url);

    option.disabled = !secure;
    option.textContent = secure
      ? 'Local — vrai CPython (noyau distant en HTTPS)'
      : 'Local — vrai CPython (adresse HTTPS requise sur iPhone)';

    backendNote().textContent = secure
      ? 'Adresse securisee detectee : l\'iPhone peut piloter ce noyau. '
        + 'Verifiez qu\'il exige un jeton — il execute le code qu\'il recoit.'
      : 'iOS ne fait tourner aucun interpreteur local, et cette page securisee '
        + 'ne peut pas joindre un noyau en http. Renseignez une adresse https '
        + '(tunnel Cloudflare, Tailscale, VPS) pour activer ce moteur ; sinon '
        + 'PyTerm utilise le moteur du navigateur, qui suffit a la plupart des usages.';
  }

  function wireBackendChoice() {
    refreshBackendChoice();
    var input = document.getElementById('set-kernel-url');
    if (input) {
      input.addEventListener('input', refreshBackendChoice);
      input.addEventListener('change', refreshBackendChoice);
    }
  }

  /* -------------------------------------------------------------- init */

  function init() {
    document.documentElement.setAttribute('data-platform', isIOS ? 'ios' : 'other');
    if (isStandalone) document.documentElement.setAttribute('data-standalone', 'yes');

    wireViewport();
    wireBackendChoice();

    global.addEventListener('beforeinstallprompt', function (e) {
      e.preventDefault();
      deferredPrompt = e;
    });

    // Proposition d'installation : seulement hors app installee, une seule fois.
    if (!isStandalone && !dismissed() && (isIOS ? isSafari : true)) {
      setTimeout(showSheet, 3000);
    }
  }

  global.PyPlatform = {
    isIOS: isIOS,
    isSafari: isSafari,
    isStandalone: isStandalone,
    showInstall: function () { showSheet(); },
    refreshBackendChoice: refreshBackendChoice,
    syncHeight: syncHeight,
    init: init
  };
})(window);
