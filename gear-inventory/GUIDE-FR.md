# Inventaire matériel — guide de démarrage 🇫🇷

Un inventaire qui tient la route, de votre matériel personnel jusqu'à un parc
de production. Un seul fichier SQLite, aucune dépendance, aucun compte,
fonctionne hors ligne.

## Avant de commencer : faut-il vraiment un outil maison ?

Réponse honnête dans [references/tool-comparison.md](references/tool-comparison.md).
En résumé :

- **Cet outil** — vous voulez vos données chez vous, gratuit, scriptable, pilotable
  par un agent IA, sans coût par utilisateur. Pas d'appli mobile, pas de
  calendrier de réservation, un seul opérateur à la fois.
- **Cheqroom / Shelf** — une équipe non technique, téléphone en main, réservations.
- **Rentman** — vous *louez* du matériel et facturez (devis, contrats, sous-location).
- **Snipe-IT** — parc informatique (ordinateurs, licences).

`export` produit un CSV que tous ces outils importent : commencer ici
n'enferme pas.

## 1. Installation

Rien à installer : Python 3.9+ suffit.

```bash
cd gear-inventory
python3 scripts/inventory.py init --currency EUR
```

Le fichier `inventory.db` est créé dans le dossier courant. Pour le ranger
ailleurs : `export GEAR_INVENTORY_DB=~/Documents/inventaire.db`.

## 2. Les lieux et les personnes

```bash
python3 scripts/inventory.py loc add SHELF-A "Étagère A" --kind shelf
python3 scripts/inventory.py loc add CASE-02 "Flightcase 2" --kind case
python3 scripts/inventory.py loc add VAN-1   "Camion"      --kind vehicle
python3 scripts/inventory.py person add alice "Alice Martin" --team camera
```

## 3. Saisir le matériel

À l'unité :

```bash
python3 scripts/inventory.py add --name "Sony FX6" --category CAM \
  --owner STUDIO --serial SN12345 --location SHELF-A --purchase-price 5900 \
  --maint-interval-days 180
```

L'étiquette (`CAM-0001`) est générée automatiquement à partir de la catégorie.

**Au-delà de ~30 articles, passez par le CSV** — c'est dix fois plus rapide :

```bash
python3 scripts/inventory.py template --out materiel.csv   # gabarit
# … vous remplissez dans un tableur …
python3 scripts/inventory.py import materiel.csv --dry-run  # simulation
python3 scripts/inventory.py import materiel.csv
```

`--dry-run` ne touche à rien et signale chaque ligne fautive avec son numéro.
L'import refuse le fichier entier à la première erreur, pour éviter un
chargement à moitié fait (`--keep-going` pour ignorer les lignes fautives).

### Matériel perso vs matériel pro

Le champ `owner` sépare les deux dans **une seule base** :

```bash
python3 scripts/inventory.py ls --owner PERSO
python3 scripts/inventory.py report by owner
python3 scripts/inventory.py export --owner STUDIO --out assurance-studio.csv
```

### Consommables

Batteries, cartes mémoire, gaffer : `--kind bulk`, on compte des quantités et
non des exemplaires.

```bash
python3 scripts/inventory.py add --name "Batteries V-Mount 95Wh" --category BAT \
  --kind bulk --qty 12 --min-qty 4 --location CASE-02
python3 scripts/inventory.py stock low     # ce qu'il faut recommander
```

## 4. Étiqueter

```bash
python3 scripts/inventory.py labels --out etiquettes.html
```

Ouvrez le fichier dans un navigateur et **imprimez à 100 % (« taille réelle »),
marges désactivées** — c'est la mise à l'échelle qui rend les QR illisibles.
`--columns 3 --rows 8` pour des étiquettes plus grandes.

Imprimez une planche d'essai sur papier ordinaire, scannez une étiquette avec
votre téléphone, et seulement ensuite lancez la série. Détails (matières,
placement, QR vs code-barres vs RFID) : [references/labeling.md](references/labeling.md).

## 5. Sorties et retours

La règle qui décide de tout : **le matériel ne sort que par `checkout` et ne
revient que par `checkin`.**

```bash
python3 scripts/inventory.py checkout CAM-0001 LENS-0004 --to alice \
  --days 3 --project "Spot Nike"
python3 scripts/inventory.py out --overdue        # les retards
python3 scripts/inventory.py checkin CAM-0001 --at SHELF-A --condition worn
```

Mettez **toujours** une échéance (`--days` ou `--due`) : sans elle, rien ne
remonte jamais en retard.

### Avec une douchette code-barres

Une douchette USB se comporte comme un clavier. Le mode `scan` lit les
étiquettes une par ligne : vous scannez, ça s'enregistre.

```bash
python3 scripts/inventory.py scan --mode checkout --to alice --days 2
python3 scripts/inventory.py scan --mode checkin --at SHELF-A
```

C'est le vrai gain de temps dès qu'il y a plus d'une vingtaine d'articles.

### Les kits

Tout ce qui voyage ensemble (boîtier + optiques + batteries + médias) :

```bash
python3 scripts/inventory.py kit new DOC-A "Kit documentaire"
python3 scripts/inventory.py kit add DOC-A CAM-0001 LENS-0004 BAT-0001
python3 scripts/inventory.py kit checkout DOC-A --to alice --days 5
```

Le kit refuse de sortir incomplet (`--partial` pour forcer).

## 6. L'inventaire physique (récolement)

C'est la seule chose qui révèle les pertes et les vols.

```bash
python3 scripts/inventory.py audit new 2026T3-ETAGERE-A --scope location=SHELF-A
python3 scripts/inventory.py scan --mode audit --audit 2026T3-ETAGERE-A
python3 scripts/inventory.py audit report 2026T3-ETAGERE-A
```

Le rapport classe chaque écart :

| Résultat | Signification |
|----------|---------------|
| `MISSING` | attendu ici, pas scanné → à chercher |
| `UNEXPECTED` | scanné ici, enregistré ailleurs → `move` |
| `PRESENT BUT LOGGED OUT` | revenu sans check-in → habitude à corriger |
| `OUT (with alice)` | légitimement sorti |

Lisez le rapport, cherchez les manquants, **puis seulement**
`audit report … --close`, qui bascule en `lost` ce qui reste introuvable.

**Rythme conseillé :** petit parc, deux fois par an. Parc actif, un lieu par
mois en rotation + un comptage complet annuel. Un audit par lieu, jamais le
parc entier d'un coup — sinon il n'est jamais fait.

## 7. Routine hebdomadaire (10 minutes)

```bash
python3 scripts/inventory.py out --overdue        # relancer les retards
python3 scripts/inventory.py stock low            # recommander
python3 scripts/inventory.py maint due --days 30  # entretiens à venir
python3 scripts/inventory.py report summary
```

## 8. Sauvegardes

Tout l'inventaire tient dans un fichier. Deux réflexes :

```bash
cp inventory.db inventory-$(date +%F).db                 # avant tout import massif
python3 scripts/inventory.py export --out inventaire-$(date +%F).csv
```

Le CSV est ce que demanderont votre assureur, votre comptable et n'importe
quel outil futur. Vous pouvez aussi versionner le `.db` dans un dépôt git
privé : l'historique des commits devient un historique daté du parc.

## Et à grande échelle ?

| Taille du parc | Ce qui change |
|----------------|---------------|
| < 100 | Rien. Étiquettes, sorties/retours, un audit par an. |
| 100–500 | Une douchette (`scan`), des kits, des audits mensuels par lieu. |
| 500–5 000 | Lieux jusqu'à l'étagère/la caisse, une personne responsable des données, `out --overdue` chaque semaine, RFID à étudier pour les comptages. |
| > 5 000 | Le blocage devient l'accès multi-utilisateur et l'appli mobile, pas le modèle de données → migrez via `export` (voir le comparatif). |

Le modèle de données ne change pas avec la taille ; c'est la **discipline** qui
change. Tout ce qui précède est une habitude, pas une fonctionnalité.

## Aide

```bash
python3 scripts/inventory.py --help
python3 scripts/inventory.py checkout --help
```

Référence complète des commandes : [references/cli.md](references/cli.md).
