# MonBudget — suivi et planification des dépenses

Deux versions du même outil vivent dans ce dossier :

| Dossier | Ce que c'est | Pour qui |
| --- | --- | --- |
| **`web/`** | Application web à ajouter à l'écran d'accueil de l'iPhone — **utilisable aujourd'hui, sans Mac, sans compte développeur** | La version en service |
| `MonBudget/`, `MonBudgetTests/` | Application iPhone native (SwiftUI + SwiftData) | Le jour où un Mac ou un compte développeur Apple est disponible |

---

## Version web (celle qui tourne)

Lien : <https://claude.ai/code/artifact/3f4e6267-9eb2-40f3-9a46-2a6bca3ac976>

### L'installer sur l'iPhone

1. Ouvrir le lien dans **Safari**.
2. Toucher le bouton **Partager** (le carré avec une flèche vers le haut).
3. Choisir **Sur l'écran d'accueil**, puis **Ajouter**.

MonBudget s'ouvre alors en plein écran avec son icône, comme une application, et
continue de fonctionner sans réseau une fois chargée.

### Ce qu'elle fait

- **Accueil** : dépensé ce mois, comparaison avec le mois dernier, jauge de budget,
  reste à payer, échéances en retard, prochaines échéances et dernières dépenses.
- **Dépenses** : historique mois par mois, regroupé par jour, avec recherche.
- **Prévues** : les échéances du mois (payer, passer, rétablir) et la liste des
  dépenses récurrentes — fréquence, jour du mois, date de fin, montant estimé.
- **Analyse** : six derniers mois, répartition par catégorie, plafonds, top 5.
- **Réglages** : devise, budget, catégories, export CSV, sauvegarde JSON, rappels.

### Les rappels

Une application web ne peut pas envoyer d'alerte toute seule sur iPhone. MonBudget
fabrique donc un fichier `.ics` que le **Calendrier de l'iPhone** importe : les
échéances deviennent des événements récurrents avec alarme (J-X puis le jour même),
et les notifications arrivent même application fermée. Bouton
**Réglages ▸ Créer mes rappels de calendrier**, à relancer après avoir modifié une
dépense prévue.

### Où vivent les données

Sur l'iPhone (stockage local du navigateur), plus une sauvegarde en ligne quand
l'app est ouverte depuis claude.ai. **Réglages ▸ Sauvegarder tout** produit un
fichier JSON à conserver ; **Restaurer une sauvegarde** le relit et fusionne sans
rien écraser.

### Le code

`web/index.html` contient toute l'application (aucune dépendance, hors les polices
Google). `web/sw.js` assure le fonctionnement hors ligne, `web/manifest.json` et
`web/icone-*.png` l'installation sur l'écran d'accueil (`web/icones.py` régénère les
icônes).

---

## Version iPhone native (en attente d'un Mac)


Le projet Swift complet est prêt dans `MonBudget/`. Il apporte ce que le web ne
peut pas faire sur iPhone : de **vraies notifications locales**, sans passer par le
Calendrier. Il lui manque seulement une machine pour être compilé — un Mac avec
Xcode, ou un service de compilation à distance (Codemagic, GitHub Actions) doublé
d'un compte développeur Apple à 99 $/an pour l'installer via TestFlight.

Application native (SwiftUI + SwiftData), entièrement en français, qui :

- enregistre et **classe** toutes vos dépenses (catégorie, moyen de paiement, notes) ;
- **programme les dépenses de chaque mois** (loyer, factures, abonnements, scolarité, crédits…) avec toutes les fréquences utiles ;
- **vous prévient avant chaque échéance** par une notification, et vous alerte si le budget du mois est en train d'être dépassé ;
- vous montre **où part votre argent** (graphiques par catégorie, évolution sur 6 mois) ;
- fonctionne **100 % hors ligne** : rien ne sort de l'iPhone, aucun compte à créer.

---

## 1. Les écrans

| Onglet | Ce qu'il apporte |
| --- | --- |
| **Accueil** | Total dépensé ce mois, comparaison avec le mois précédent, budget restant, **reste à payer**, échéances en retard, prochaines échéances (avec bouton « payé »), dernières dépenses. |
| **Dépenses** | Historique mois par mois, regroupé par jour, recherche, filtre par catégorie, modification et suppression par balayage. |
| **Prévues** | Deux vues : le **calendrier des échéances du mois** (payer / ignorer / rétablir en balayant) et la liste de vos **dépenses récurrentes** (suspendre, modifier, supprimer). |
| **Statistiques** | Camembert par catégorie avec part en %, respect des plafonds, histogramme des 6 derniers mois, moyenne mensuelle, plus grosses dépenses. |
| **Réglages** | Devise, budget mensuel, rappels, seuil d'alerte, catégories et plafonds, verrouillage Face ID, export CSV, données d'exemple, remise à zéro. |

### Comment fonctionne la planification

Une dépense prévue décrit **une règle**, pas une liste de lignes : libellé, montant (fixe ou « estimé » pour une facture variable), fréquence (une fois, quotidienne, hebdomadaire, mensuelle, trimestrielle, annuelle), intervalle (« tous les 2 mois »), jour du mois, date de début, date de fin facultative.

Les échéances sont **calculées à la volée** par `MoteurRecurrence`. Cas traités :

- le 31 de chaque mois devient automatiquement le 28/29 février, le 30 avril, etc. ;
- une règle qui commence le 15 janvier mais paye « le 1er » démarre au 1er février ;
- la date de fin arrête la série ;
- une échéance peut être **payée** (elle devient une vraie dépense, montant réel ajustable) ou **ignorée** pour ce mois seulement.

### Comment fonctionnent les rappels

Tout passe par les **notifications locales** d'iOS (aucun serveur) :

1. un rappel **J-X** (réglable par dépense : le jour même, 1, 2, 3, 5 ou 7 jours avant) à l'heure choisie ;
2. un rappel **le jour de l'échéance** ;
3. un rappel **le 1er du mois** pour faire le point ;
4. une alerte quand le budget atteint le seuil choisi (50 à 100 %) puis quand il est dépassé.

iOS n'accepte que 64 notifications en attente : l'app les **recalcule à chaque modification** et garde les plus proches, en sautant les échéances déjà payées ou ignorées.

---

## 2. Installer l'app sur votre iPhone

Il faut un **Mac avec Xcode 16 ou plus récent** (gratuit sur le Mac App Store). iOS 17 minimum sur l'iPhone.

1. Copiez le dossier `MonBudget/` sur le Mac.
2. Double-cliquez sur `MonBudget.xcodeproj`.
3. Dans Xcode : onglet **Signing & Capabilities** de la cible `MonBudget` → cochez *Automatically manage signing* → choisissez votre **équipe** (votre identifiant Apple suffit, il est ajouté via Xcode ▸ Settings ▸ Accounts).
4. Changez si besoin le *Bundle Identifier* (`com.monbudget.app` → `com.votrenom.monbudget`) : il doit être unique.
5. Branchez l'iPhone, sélectionnez-le dans la barre du haut, puis ▶︎ (Cmd+R).
6. Sur l'iPhone : *Réglages ▸ Général ▸ VPN et gestion de l'appareil* → faites confiance à votre certificat de développeur.
7. Au premier lancement, acceptez les **notifications** (sinon aucun rappel ne sera programmé), puis allez dans **Réglages** pour fixer votre devise et votre budget mensuel.

> Avec un compte Apple gratuit, l'app doit être réinstallée tous les 7 jours. Avec le programme développeur Apple (99 $/an), elle reste installée un an et peut être publiée sur l'App Store ou distribuée via TestFlight.

Pour découvrir l'app sans rien saisir : **Réglages ▸ Charger des données d'exemple**.

Le projet peut aussi être régénéré avec [XcodeGen](https://github.com/yonaskolb/XcodeGen) à partir de `project.yml` :

```bash
brew install xcodegen
cd MonBudget && xcodegen generate
```

---

## 3. Organisation du code

```
MonBudget/
├── MonBudgetApp.swift              # Point d'entrée, conteneur SwiftData
├── Modeles/
│   ├── Depense.swift               # Dépense réelle + moyens de paiement
│   ├── DepensePlanifiee.swift      # Dépense prévue + échéances ignorées
│   ├── Categorie.swift             # Catégories, plafonds, jeu par défaut
│   └── Recurrence.swift            # Fréquences et règle de répétition
├── Services/
│   ├── MoteurRecurrence.swift      # Calcul des échéances (100 % testable)
│   ├── CalculateurBudget.swift     # Agrégation dépenses / échéances / totaux
│   ├── GestionnaireEcheances.swift # Payer, annuler, ignorer, supprimer
│   ├── ServiceNotifications.swift  # Programmation des rappels iOS
│   ├── SurveillanceBudget.swift    # Alertes de seuil et de dépassement
│   ├── Reglages.swift              # Préférences (UserDefaults)
│   ├── VerrouillageApp.swift       # Face ID / Touch ID / code
│   ├── ExportCSV.swift             # Export vers Excel / Numbers
│   └── DonneesDemo.swift           # Données d'exemple et remise à zéro
├── Vues/                           # Un fichier par écran + Composants/
└── Utilitaires/                    # Formatage français, couleurs, dates
MonBudgetTests/                     # Tests unitaires du moteur de récurrence
```

**Tests** : `Cmd+U` dans Xcode. Ils couvrent les cas de dates délicats (mois courts, années bissextiles, intervalles, dates de fin, première échéance) et les paliers d'alerte budget.

---

## 4. Idées pour une meilleure application

Classées par rapport « utilité / effort ». Les trois premières sont celles qui changent le plus le quotidien.

### À faire en priorité

1. **Widget + écran verrouillé** — voir « reste à payer : 85 000 F » et la prochaine échéance sans ouvrir l'app (WidgetKit).
2. **Bouton « Payé » directement dans la notification** — régler une échéance en deux secondes sans ouvrir l'app (actions de notification).
3. **Ajouter les revenus** — salaire et rentrées d'argent, pour afficher le vrai **reste à vivre** (solde = revenus − dépenses − échéances à venir) plutôt que seulement les dépenses.
4. **Saisie vocale / Siri** — « Dis Siri, note 3 000 de taxi » (App Intents), plus un raccourci sur l'écran d'accueil.
5. **Photo du reçu** attachée à la dépense, avec lecture automatique du montant (VisionKit).

### Ensuite

6. **Synchronisation iCloud** (CloudKit) : sauvegarde automatique et même budget sur iPhone et iPad — indispensable en cas de perte du téléphone.
7. **Budget partagé** (couple, famille) : plusieurs personnes alimentent le même budget, chacun voit qui a payé quoi.
8. **Objectifs d'épargne** : « 500 000 pour l'école en décembre », avec versement mensuel conseillé et barre de progression.
9. **Dettes et prêts** : qui vous doit combien, qui vous avez remboursé, avec rappels.
10. **Détecteur d'abonnements** : repère les montants identiques qui reviennent chaque mois et propose de les transformer en dépense prévue — très efficace pour retrouver les abonnements oubliés.
11. **Import de relevés** : CSV bancaire, ou lecture des SMS Mobile Money (Orange/MTN/Moov/Wave) pour ne rien saisir à la main.
12. **Prévision intelligente de fin de mois** : à partir de la moyenne des 3 derniers mois + les échéances restantes, dire « à ce rythme vous finirez à 420 000 ».

### Plus tard

13. **Multi-devises** avec taux de change (utile en cas de dépenses à l'étranger).
14. **Catégorisation automatique** : l'app apprend que « Total » = Transport, « Pharmacie X » = Santé.
15. **Rapport mensuel PDF** envoyable par e-mail ou WhatsApp.
16. **Apple Watch** pour la saisie express, **Apple Pay/Wallet** pour rapprocher les paiements.
17. **Règle 50/30/20** (besoins / envies / épargne) : classer les catégories en trois familles et suivre l'équilibre.
18. **Défis** : « semaine sans dépense superflue », série de mois sous le budget — la gamification aide vraiment à tenir un budget.

### Détails d'ergonomie qui font la différence

- Saisie du montant **en premier**, au clavier numérique, l'app propose ensuite le libellé et la catégorie les plus fréquents à cette date/heure.
- **Dépenses fréquentes épinglées** (taxi, café, marché) : un appui = une dépense enregistrée.
- **Arrondi psychologique** : afficher les montants sans décimales quand la devise n'en utilise pas (déjà le cas pour le franc CFA).
- **Rappel intelligent** : prévenir plus tôt pour les grosses échéances (scolarité, loyer) que pour les petites.
- **Mode « mois serré »** : quand le prévisionnel dépasse le budget, l'app propose les catégories où réduire, chiffres à l'appui.

---

## 5. Limites connues

- Le projet a été écrit hors de Xcode : **la compilation n'a pas pu être vérifiée** ici (ni Swift ni Xcode ne sont disponibles sur la machine de développement utilisée). Prévoyez que le premier build puisse demander une correction mineure.
- L'icône de l'app est vide : ajoutez une image 1024×1024 dans `Ressources/Assets.xcassets/AppIcon.appiconset`.
- Pas encore de synchronisation iCloud : les données vivent sur l'iPhone (l'export CSV sert de sauvegarde).
- L'interface est en français uniquement (textes écrits directement dans les vues) ; une traduction passerait par un fichier de localisation.
