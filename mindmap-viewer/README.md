# Mindmap Atlas

Interface de consultation pour la collection de mindmaps cybersécurité
[**Ignitetechnologies/Mindmap**](https://github.com/Ignitetechnologies/Mindmap)
(Hacking Articles) — 114 mindmaps, 12 catégories.

Le dépôt d'origine n'est qu'une arborescence de dossiers : pour trouver une carte
il faut parcourir 78 répertoires et ouvrir des PNG de plusieurs milliers de pixels
dans la visionneuse GitHub. Cette interface remplace ça par un catalogue
recherchable et une visionneuse zoom/pan.

## Utilisation

```bash
# 1. la façon la plus simple : ouvrir le fichier
xdg-open index.html        # Linux
open index.html            # macOS
start index.html           # Windows
```

`index.html` est **autonome** : aucune dépendance, aucun build, aucun serveur.
Le catalogue est embarqué dans le fichier et les images sont chargées depuis
GitHub (CDN jsDelivr par défaut, bascule automatique sur `raw.githubusercontent.com`).

### Mode hors-ligne / local

Pour travailler sans réseau, copier `index.html` **à la racine d'un clone** du
dépôt Mindmap, puis choisir *Fichiers locaux* dans « Source des images »
(barre latérale) :

```bash
git clone https://github.com/Ignitetechnologies/Mindmap
cp index.html Mindmap/
cd Mindmap && python3 -m http.server 8000   # puis http://localhost:8000/index.html
```

### Publication

Le fichier fonctionne tel quel sur n'importe quel hébergement statique
(GitHub Pages, Netlify, un simple partage réseau) : il suffit de déposer
`index.html`, les images restant servies par le CDN.

## Fonctionnalités

| | |
|---|---|
| **Recherche** | instantanée, insensible aux accents, multi-termes (`ad kerberos`), sur le titre, la catégorie, le dossier et des mots-clés FR/EN |
| **Catégories** | 12 thématiques (Active Directory, Web, OSINT, Red Team, Blue Team, conformité…) avec compteurs |
| **Visionneuse** | zoom molette centré sur le curseur, déplacement à la souris/au doigt, ajuster / 1:1, navigation entre cartes |
| **Qualités** | bascule SD / HD / UHD selon ce qui existe pour chaque mindmap |
| **PDF** | lien direct vers le PDF d'origine quand il existe (104 des 114 cartes) |
| **Favoris & récents** | mémorisés localement (`localStorage`) |
| **Affichage** | grille ou liste compacte, thème clair/sombre, responsive mobile |
| **Liens partageables** | `index.html#/map/nmap` ouvre directement une carte |

### Raccourcis clavier

| Touche | Action |
|---|---|
| `/` | placer le curseur dans la recherche |
| `←` `→` | carte précédente / suivante |
| `+` `−` | zoom avant / arrière |
| `0` | ajuster à l'écran |
| `1` | taille réelle (1:1) |
| `f` | ajouter/retirer des favoris |
| `Échap` | fermer la visionneuse (ou vider la recherche) |

## Régénérer le catalogue

Le dépôt source évolue (nouvelles mindmaps). `build_catalog.py` relit
l'arborescence, regroupe les variantes `Normal` / `HD` / `UHD` d'une même carte,
rattache le PDF correspondant, attribue une catégorie, puis écrit `catalog.json`
et le réinjecte dans `index.html` entre les marqueurs `/* CATALOG:START */` et
`/* CATALOG:END */`.

```bash
git clone --depth 1 https://github.com/Ignitetechnologies/Mindmap /tmp/Mindmap
python3 build_catalog.py --repo /tmp/Mindmap
# 114 mindmaps, 12 catégories -> catalog.json
# index.html mis à jour
```

On peut aussi partir d'une simple liste de chemins :

```bash
python3 build_catalog.py --file-list chemins.txt
```

Le classement par catégorie est piloté par la table `CATEGORIES` en haut du
script (dossier → thématique) ; ajouter un dossier inconnu le range dans
« Divers ».

## Fichiers

```
mindmap-viewer/
├── index.html         # l'interface complète, catalogue embarqué (autonome)
├── catalog.json       # le même catalogue, lisible/réutilisable
├── build_catalog.py   # génère catalog.json et l'injecte dans index.html
└── README.md
```

## Crédits

Les mindmaps (PNG, PDF) sont l'œuvre de **Hacking Articles / Ignite Technologies**
et restent hébergées sur leur dépôt : <https://github.com/Ignitetechnologies/Mindmap>.
Cette interface ne fait que les indexer et les afficher — aucune image n'est
copiée ici.
