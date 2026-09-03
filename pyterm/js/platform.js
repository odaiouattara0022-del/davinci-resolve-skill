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

  /* Sur iPhone, le noyau CPython local est hors d'atteinte : rien ne peut
     l'heberger sur l'appareil, et une page servie en HTTPS ne peut pas
     joindre un http://192.168.x.x (contenu mixte). On le dit clairement
     plutot que de laisser l'utilisateur buter dessus.                      */
  function annotateBackendChoice() {
    var select = document.getElementById('set-backend');
    if (!select) return;
    var option = select.querySelector('option[value="native"]');
    if (!option) return;
    if (isIOS) {
      option.textContent = 'Local — vrai CPython (indisponible sur iPhone)';
      option.disabled = true;
      var note = document.createElement('p');
      note.className = 'hint';
      note.textContent = 'iOS n\'autorise aucun interpreteur local, et une page ' +
        'securisee ne peut pas joindre un noyau en http sur le reseau local. ' +
        'Sur iPhone, PyTerm fonctionne donc avec le moteur du navigateur.';
      var field = document.getElementById('field-kernel');
      if (field && field.parentNode) field.parentNode.insertBefore(note, field);
    }
  }

  /* -------------------------------------------------------------- init */

  function init() {
    document.documentElement.setAttribute('data-platform', isIOS ? 'ios' : 'other');
    if (isStandalone) document.documentElement.setAttribute('data-standalone', 'yes');

    wireViewport();
    annotateBackendChoice();

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
    syncHeight: syncHeight,
    init: init
  };
})(window);
