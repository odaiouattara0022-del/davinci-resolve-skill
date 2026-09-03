# PyTerm — studio Python personnel

Un éditeur **et** un terminal Python complets, dans une page web autonome.
Le même dossier fonctionne sur un téléphone Android/iOS, sur un ordinateur,
en ligne comme hors connexion. L'ergonomie reprend celle de VS Code et de
PyCharm : explorateur, onglets, palette de commandes, console intégrée.

![sans installation](https://img.shields.io/badge/installation-aucune-brightgreen)
![hors-ligne](https://img.shields.io/badge/hors--ligne-oui-blue)

---

## 1. Démarrer en 30 secondes

### Sur téléphone (ou n'importe quel navigateur)

1. Publiez le dossier `pyterm/` sur n'importe quel hébergement statique
   (GitHub Pages, Netlify, Cloudflare Pages…) — voir §6.
2. Ouvrez l'adresse, puis **« Ajouter à l'écran d'accueil »**.
   L'application s'installe comme une vraie app, plein écran, et fonctionne
   ensuite sans connexion.

### Sur ordinateur, avec le vrai Python de la machine

```bash
python3 pyterm/server/kernel.py
# puis ouvrez http://127.0.0.1:8777
```

C'est la configuration la plus complète : l'interface est servie avec les
en-têtes d'isolation qui débloquent `input()` en direct et l'interruption
Ctrl+C, et le moteur *CPython local* devient disponible.

### Sans rien lancer du tout

Ouvrez simplement `pyterm/index.html` dans un navigateur. Tout fonctionne,
à deux détails près : `input()` demande ses réponses avant l'exécution, et
l'arrêt d'un programme redémarre le moteur au lieu de l'interrompre.

---

## 2. Deux moteurs, un seul environnement

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

## 3. Raccourcis

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

## 4. Commandes de la console

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

## 5. Vos fichiers

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

## 6. Héberger l'interface

Le dossier est entièrement statique — aucune construction, aucun `npm`.

**GitHub Pages** : *Settings → Pages → Deploy from a branch*, puis ouvrez
`https://<utilisateur>.github.io/<dépôt>/pyterm/`.

**Serveur local** : n'importe quel serveur statique convient, mais
`server/kernel.py` est préférable — lui seul envoie les en-têtes
`Cross-Origin-Opener-Policy` / `Cross-Origin-Embedder-Policy` qui activent
la saisie clavier en direct et l'interruption propre.

---

## 7. Le noyau local en détail

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

## 8. Structure

```
pyterm/
├── index.html              interface
├── manifest.webmanifest    installation en application
├── sw.js                   service worker (hors-ligne)
├── assets/
│   ├── app.css             thème sombre et clair
│   └── icon.svg
├── js/
│   ├── fs.js               fichiers virtuels + réglages
│   ├── snippets.js         modèles de départ
│   ├── runtime.js          les deux moteurs Python
│   ├── terminal.js         console et historique
│   ├── editor.js           enveloppe CodeMirror
│   └── main.js             assemblage
└── server/
    └── kernel.py           noyau CPython + serveur (stdlib seule)
```

CodeMirror est chargé depuis un CDN à la première visite puis mis en cache
par le service worker ; Pyodide de même, à la première exécution.

---

## 9. Limites connues

- En mode navigateur, un paquet doit être compatible Pyodide : le pur Python
  passe toujours, le code C exige une version compilée en WebAssembly
  (`numpy`, `pandas`, `matplotlib`, `scikit-learn` le sont). Pour le reste,
  passez au moteur local.
- Pas de sockets réseau ni de `subprocess` en mode navigateur : ce sont des
  limites du bac à sable du navigateur, pas de PyTerm.
- `input()` en direct et l'interruption Ctrl+C exigent l'isolation du site,
  c'est-à-dire d'ouvrir l'interface via `server/kernel.py` (ou tout
  hébergement envoyant les en-têtes COOP/COEP).
- La première visite télécharge Pyodide (~10 Mo) : prévoyez-la sur Wi-Fi.

---

## 10. Licence

MIT, comme le reste du dépôt.
