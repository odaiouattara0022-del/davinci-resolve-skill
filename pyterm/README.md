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

Le workflow [`.github/workflows/pages.yml`](../.github/workflows/pages.yml)
publie automatiquement le dossier `pyterm/` sur GitHub Pages à chaque envoi
sur `main`.

1. Sur GitHub : **Settings → Pages → Source : GitHub Actions**.
2. Fusionnez cette branche dans `main` (ou lancez le workflow à la main
   depuis l'onglet *Actions*).
3. L'adresse s'affiche à la fin du workflow, de la forme
   `https://<votre-compte>.github.io/davinci-resolve-skill/`.

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

## 7. Héberger l'interface

Le dossier est entièrement statique — aucune construction, aucun `npm`.

**GitHub Pages** : *Settings → Pages → Deploy from a branch*, puis ouvrez
`https://<utilisateur>.github.io/<dépôt>/pyterm/`.

**Serveur local** : n'importe quel serveur statique convient, mais
`server/kernel.py` est préférable — lui seul envoie les en-têtes
`Cross-Origin-Opener-Policy` / `Cross-Origin-Embedder-Policy` qui activent
la saisie clavier en direct et l'interruption propre.

---

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
└── tools/
    └── make_icons.py       régénère icônes et écrans de lancement
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
- `input()` en direct et l'interruption Ctrl+C exigent l'isolation du site,
  c'est-à-dire d'ouvrir l'interface via `server/kernel.py` (ou tout
  hébergement envoyant les en-têtes COOP/COEP). GitHub Pages ne les envoie
  pas : sur iPhone, PyTerm demande donc les entrées avant l'exécution, et le
  bouton d'arrêt redémarre le moteur.
- Une application native pour l'App Store exigerait un Mac, Xcode et un
  compte développeur Apple payant. L'installation depuis Safari donne le même
  résultat visible — icône, plein écran, hors-ligne — sans rien de tout cela.
- La première visite télécharge Pyodide (~10 Mo) : prévoyez-la sur Wi-Fi.

---

## 11. Licence

MIT, comme le reste du dépôt.
