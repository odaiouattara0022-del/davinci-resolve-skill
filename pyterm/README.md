# PyTerm — studio Python personnel

Un éditeur **et** un terminal Python complets, installables comme une vraie
application. Sur iPhone, PyTerm obtient son icône sur l'écran d'accueil, son
écran de lancement, le plein écran sans barre Safari, et fonctionne sans
connexion. Le même dossier sert aussi d'app sur Android, Windows, macOS et
Linux. L'ergonomie reprend celle de VS Code et de PyCharm : explorateur,
onglets, palette de commandes, console intégrée.

![installable](https://img.shields.io/badge/iPhone-installable-brightgreen)
![hors-ligne](https://img.shields.io/badge/hors--ligne-oui-blue)
![sans dépendance](https://img.shields.io/badge/d%C3%A9pendances-aucune-lightgrey)

---

## 1. Installer l'application sur iPhone

iOS n'installe une application depuis le web que si la page est servie en
**HTTPS**. Le dépôt contient le nécessaire pour l'obtenir en trois minutes.

### a. Publier l'application (une seule fois)

Deux routes, détaillées au §7. **Si vous avez un hébergement Hostinger,
utilisez-le** : il vous laisse définir les en-têtes HTTP, ce qui débloque
`input()` en direct et le vrai Ctrl+C sur l'iPhone. GitHub Pages ne le
permet pas.

| | Hostinger (ou tout Apache/LiteSpeed) | GitHub Pages |
|---|---|---|
| Mise en ligne | téléversement du dossier | automatique à chaque `push` |
| `input()` en direct sur iPhone | **oui** | non |
| Arrêt propre d'un programme | **oui** | redémarre le moteur |
| Sans aucun CDN | **oui** (§7c) | possible mais lourd |
| Nom de domaine | le vôtre | `github.io` |

Version courte pour Hostinger : téléversez le contenu de `pyterm/` dans
`public_html/`, activez le SSL gratuit, c'est prêt. Le fichier `.htaccess`
fourni fait le reste.

### b. Poser l'icône sur l'écran d'accueil

1. Ouvrez cette adresse **dans Safari** (Chrome iOS ne sait pas installer).
2. Touchez **Partager** ⬆︎, puis **Sur l'écran d'accueil**, puis **Ajouter**.

PyTerm propose lui-même ces étapes au premier lancement. L'application
apparaît alors avec son icône ; lancée depuis l'écran d'accueil, elle occupe
tout l'écran, affiche son écran de lancement, garde ses propres fichiers et
démarre sans réseau.

> **À savoir sur iPhone.** Le code s'exécute avec le moteur du navigateur
> (Pyodide) : c'est un vrai CPython compilé en WebAssembly, avec presque
> toute la bibliothèque standard. Il ne peut pas ouvrir de sockets ni lancer
> de processus — ce sont les règles d'iOS, pas celles de PyTerm. Le moteur
> « CPython local » est désactivé sur iPhone et l'application vous le dit.
> Prévoyez le premier lancement en Wi-Fi : Pyodide pèse environ 10 Mo, puis
> il est conservé hors ligne.

---

## 2. Les autres appareils

### Android

Même chose que sur iPhone, dans Chrome : menu ⋮ → **Installer l'application**.
Avec [Termux](https://termux.dev) (`pkg install python git`), vous pouvez en
plus lancer le vrai CPython sur le téléphone — voir §8.

### Ordinateur, avec le vrai Python de la machine

```bash
python3 pyterm/server/kernel.py
# puis ouvrez http://127.0.0.1:8777
```

C'est la configuration la plus complète : l'interface est servie avec les
en-têtes d'isolation qui débloquent `input()` en direct et l'interruption
Ctrl+C, et le moteur *CPython local* devient disponible. Chrome et Edge
proposent alors **Installer PyTerm** dans la barre d'adresse : vous obtenez
une fenêtre d'application, sans barre de navigateur.

### Sans rien lancer du tout

Ouvrez `pyterm/index.html` dans un navigateur. Tout fonctionne, à deux détails
près : `input()` demande ses réponses avant l'exécution, et l'arrêt d'un
programme redémarre le moteur au lieu de l'interrompre.

---

## 3. Deux moteurs, un seul environnement

| | **Navigateur — Pyodide** | **Local — CPython** |
|---|---|---|
| Installation | aucune | `python3` sur la machine |
| Où ça tourne | dans l'onglet, en WebAssembly | sur votre machine |
| Hors connexion | oui (après la 1ʳᵉ visite) | oui |
| Bibliothèque standard | quasi complète | complète |
| `pip install` | paquets compatibles Pyodide | **tout PyPI** |
| Sockets, `subprocess`, vrai disque | non | **oui** |
| Téléphone | **oui** | oui, via Termux |

Le moteur se choisit dans **Réglages → Moteur Python**, ou depuis la console
avec `!backend native` / `!backend pyodide`.

En mode local, les fichiers de l'éditeur sont recopiés dans le dossier de
travail du noyau (`~/pyterm-workspace` par défaut) avant chaque exécution :
les `import` entre vos fichiers, `open()`, `pathlib` fonctionnent normalement.

---

## 4. Raccourcis

| Raccourci | Action |
|---|---|
| `Ctrl/Cmd + Entrée` | exécuter le fichier |
| `Ctrl/Cmd + Maj + Entrée` | exécuter la sélection (ou la ligne) |
| `Ctrl/Cmd + S` | enregistrer (l'enregistrement est aussi automatique) |
| `Ctrl/Cmd + P` | palette de commandes et de fichiers |
| `Ctrl/Cmd + Maj + P` | palette de commandes |
| `` Ctrl/Cmd + ` `` | afficher / masquer le terminal |
| `Ctrl/Cmd + B` | afficher / masquer l'explorateur |
| `Ctrl/Cmd + /` | commenter / décommenter |
| `Ctrl/Cmd + D` | dupliquer la ligne |
| `Alt + ↑ / ↓` | déplacer la ligne |
| `Ctrl + Espace` | complétion |
| `Ctrl/Cmd + C` | arrêter l'exécution en cours |
| `↑ / ↓` dans la console | historique des commandes |

Sur téléphone, une barre de symboles (`:` `(` `[` `"` `_` …) s'affiche
au-dessus du clavier ; elle se désactive dans les réglages.

---

## 5. Commandes de la console

La console du bas est un vrai REPL : toute expression y est évaluée et son
résultat affiché. Elle accepte en plus quelques commandes préfixées :

```
!help                  aide
!ls                    liste des fichiers
!open <fichier>        ouvre un fichier dans l'éditeur
!run [fichier]         exécute un fichier
!cat <fichier>         affiche un fichier
!new <fichier>         crée un fichier
!rm <fichier>          supprime un fichier
!pip install <paquet>  installe un paquet
!reset                 vide l'espace de noms Python
!clear                 efface la console
!backend [nom]         change de moteur (pyodide | native)
```

L'espace de noms est partagé entre le fichier exécuté et la console : après
avoir lancé un script, ses variables et ses fonctions sont directement
inspectables — c'est le mode « Run with Python Console » de PyCharm.

---

## 6. Vos fichiers

- Ils vivent dans le stockage local du navigateur et survivent à la
  fermeture de l'onglet.
- **Importer** : bouton ↑ de l'explorateur, ou glisser-déposer sur la page.
- **Exporter** : bouton ↓ pour le fichier actif, *Exporter tout* pour une
  archive `.json` de l'espace entier — c'est le format d'échange entre
  votre téléphone et votre ordinateur.
- En mode CPython local, ils sont également écrits sur le disque, dans le
  dossier de travail du noyau.

> Le stockage d'un navigateur peut être vidé par le système ou la navigation
> privée. Exportez régulièrement ce à quoi vous tenez.

---

## 7. Héberger l'application

Le dossier est entièrement statique — aucune construction, aucun `npm`.

### a. Hostinger, cPanel, o2switch… (recommandé)

1. **hPanel → Gestionnaire de fichiers**, ouvrez `public_html/`.
2. Téléversez le **contenu** de `pyterm/` (pas le dossier lui-même), en
   incluant le fichier `.htaccess`. Le gestionnaire de fichiers masque parfois
   les fichiers commençant par un point : activez *Afficher les fichiers
   cachés*. Par FTP, la plupart des clients ont la même option.
3. **hPanel → SSL**, activez le certificat gratuit. iOS n'installe une
   application que depuis une adresse `https`.
4. Ouvrez votre domaine dans Safari → Partager → **Sur l'écran d'accueil**.

Vous pouvez aussi installer dans un sous-dossier (`public_html/pyterm/`) :
tous les chemins de l'application sont relatifs, rien à modifier.

**Ce que `.htaccess` apporte**, et que les hébergements statiques ne peuvent
pas offrir :

- `Cross-Origin-Opener-Policy` et `Cross-Origin-Embedder-Policy`, qui isolent
  le site et débloquent `SharedArrayBuffer` — donc **`input()` répond pendant
  l'exécution** et **le bouton d'arrêt interrompt vraiment** le programme, au
  lieu de redémarrer le moteur. C'est la différence la plus visible à
  l'usage, sur iPhone comme ailleurs.
- Les types MIME que beaucoup d'hébergements oublient (`.webmanifest`,
  `.wasm`), sans lesquels l'installation et Pyodide échouent.
- La redirection vers HTTPS, le cache long sur les dépendances versionnées
  et la compression.

### b. GitHub Pages

Le workflow [`.github/workflows/pages.yml`](../.github/workflows/pages.yml)
publie `pyterm/` à chaque envoi sur `main`.

1. **Settings → Pages → Source : GitHub Actions**.
2. Fusionnez sur `main`, ou lancez le workflow depuis l'onglet *Actions*.
3. L'adresse s'affiche à la fin du workflow.

Gratuit et automatique, mais GitHub Pages ne laisse pas définir les en-têtes
d'isolation : `input()` demandera ses réponses avant l'exécution.

### c. Se passer complètement des CDN

Par défaut, CodeMirror et Pyodide viennent de CDN publics. Une commande
rapatrie tout chez vous :

```bash
python3 pyterm/tools/vendor_assets.py                    # cœur, ~12 Mo
python3 pyterm/tools/vendor_assets.py --packages numpy   # + numpy hors ligne
python3 pyterm/tools/vendor_assets.py --restore          # revenir en arrière
```

Le script télécharge dans `pyterm/vendor/`, fait pointer `index.html` dessus
et garde une sauvegarde. Téléversez ensuite le dossier complet, `vendor/`
compris. Intérêt : plus aucune dépendance externe, premier chargement plus
rapide depuis votre région, et l'isolation du site devient triviale puisque
tout est servi par la même origine.

### d. Serveur local

`server/kernel.py` reste le meilleur choix pour développer sur ordinateur :
il envoie déjà les mêmes en-têtes d'isolation que le `.htaccess`.

## 8. Le noyau local en détail

```bash
python3 server/kernel.py [options]

  --host 127.0.0.1     adresse d'écoute
  --port 8777          port
  --workdir ~/py       dossier de travail des scripts
  --token secret       jeton exigé sur chaque requête
  --no-app             n'exposer que l'API, sans servir l'interface
  --verbose            journaliser les requêtes
```

Il n'utilise que la bibliothèque standard : aucune dépendance à installer.

**Depuis le téléphone vers l'ordinateur** — les deux appareils sur le même
réseau Wi-Fi :

```bash
python3 server/kernel.py --host 0.0.0.0 --token monsecret
```

puis, sur le téléphone, ouvrez `http://<ip-de-l-ordinateur>:8777/?token=monsecret`.

**Sur Android, sans ordinateur** : installez [Termux](https://termux.dev),
`pkg install python git`, clonez le dépôt et lancez la même commande sur
`127.0.0.1`. Vous obtenez un vrai CPython, avec `pip`, sur le téléphone.

> Ce service exécute le code qu'il reçoit. Il n'écoute que sur `127.0.0.1`
> par défaut, et refuse de démarrer sur une autre adresse sans `--token`.
> Ne l'exposez jamais sur un réseau que vous ne maîtrisez pas.

### Le joindre depuis l'iPhone

Un hébergement mutualisé (Hostinger, cPanel…) ne fait tourner que des fichiers
statiques : `kernel.py` ne peut pas y vivre. Deux options pour que l'iPhone
pilote un vrai CPython :

```bash
cloudflared tunnel --url http://localhost:8777   # adresse https immédiate
tailscale serve 8777                             # via votre réseau privé
```

Renseignez l'adresse `https` obtenue dans **Réglages → Adresse du noyau
local** : le moteur *CPython local* s'active alors sur iPhone. Tant que
l'adresse est en `http`, il reste désactivé — une page sécurisée ne peut pas
joindre un service non sécurisé.

> **À peser sérieusement.** Un tunnel public place un service d'exécution de
> code arbitraire sur Internet. Le jeton est une protection mince : quiconque
> l'obtient exécute ce qu'il veut sur votre machine, avec vos droits.
> Tailscale, qui n'expose rien hors de votre réseau privé, est nettement plus
> sûr qu'un tunnel ouvert. Sur un VPS, faites-le tourner sous un compte
> dédié et sans données sensibles à portée. Pour un usage courant, le moteur
> du navigateur reste le choix raisonnable.

---

## 9. Structure

```
pyterm/
├── index.html              interface
├── manifest.webmanifest    métadonnées d'installation
├── sw.js                   service worker (hors-ligne)
├── assets/
│   ├── app.css             thème sombre et clair
│   ├── icon-*.png          icônes d'application (dont l'icône iOS 180×180)
│   ├── icon.svg            source vectorielle
│   └── splash/             écrans de lancement iPhone
├── js/
│   ├── platform.js         iPhone : hauteur, clavier, installation
│   ├── fs.js               fichiers virtuels + réglages
│   ├── snippets.js         modèles de départ
│   ├── runtime.js          les deux moteurs Python
│   ├── terminal.js         console et historique
│   ├── editor.js           enveloppe CodeMirror
│   └── main.js             assemblage
├── server/
│   └── kernel.py           noyau CPython + serveur (stdlib seule)
├── tools/
│   ├── make_icons.py       régénère icônes et écrans de lancement
│   └── vendor_assets.py    rapatrie CodeMirror et Pyodide en local
├── vendor/                 dépendances auto-hébergées (créé à la demande)
└── .htaccess               en-têtes d'isolation pour Apache / LiteSpeed
```

Les icônes et les écrans de lancement sont dessinés par
`tools/make_icons.py`, sans aucune dépendance : Safari refuse les icônes SVG
pour l'écran d'accueil, et les images de lancement doivent correspondre au
pixel près aux dimensions de chaque iPhone.

CodeMirror est chargé depuis un CDN à la première visite puis mis en cache
par le service worker ; Pyodide de même, à la première exécution.

---

## 10. Limites connues

- En mode navigateur, un paquet doit être compatible Pyodide : le pur Python
  passe toujours, le code C exige une version compilée en WebAssembly
  (`numpy`, `pandas`, `matplotlib`, `scikit-learn` le sont). Pour le reste,
  passez au moteur local.
- Pas de sockets réseau ni de `subprocess` en mode navigateur : ce sont des
  limites du bac à sable du navigateur, pas de PyTerm.
- `input()` en direct et l'interruption Ctrl+C exigent l'isolation du site.
  Elle est acquise avec `server/kernel.py` et avec le `.htaccess` fourni
  (Hostinger et tout Apache/LiteSpeed). Elle ne l'est pas sur GitHub Pages,
  qui ne permet pas de définir ces en-têtes : là, PyTerm demande les entrées
  avant l'exécution et le bouton d'arrêt redémarre le moteur.
- Une application native pour l'App Store exigerait un Mac, Xcode et un
  compte développeur Apple payant. L'installation depuis Safari donne le même
  résultat visible — icône, plein écran, hors-ligne — sans rien de tout cela.
- La première visite télécharge Pyodide (~10 Mo) : prévoyez-la sur Wi-Fi.

---

## 11. Licence

MIT, comme le reste du dépôt.
