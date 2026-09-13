import Foundation
import SwiftData

/// Jeu de données d'exemple, pour découvrir l'app sans rien saisir.
enum DonneesDemo {
    static func installer(dans contexte: ModelContext, calendrier: Calendar = .current) {
        let categories = (try? contexte.fetch(FetchDescriptor<Categorie>())) ?? []
        func categorie(_ nom: String) -> Categorie? {
            categories.first { $0.nom == nom }
        }

        let aujourdHui = Date()
        let debutDuMois = calendrier.intervalleDuMois(contenant: aujourdHui).start

        let planifiees: [DepensePlanifiee] = [
            DepensePlanifiee(
                libelle: "Loyer",
                montant: 150_000,
                categorie: categorie("Logement"),
                frequence: .mensuel,
                dateDebut: debutDuMois,
                jourDuMois: 5,
                moyenPaiement: .virement,
                rappelJoursAvant: 3
            ),
            DepensePlanifiee(
                libelle: "Électricité",
                montant: 25_000,
                categorie: categorie("Factures & abonnements"),
                frequence: .mensuel,
                dateDebut: debutDuMois,
                jourDuMois: 15,
                moyenPaiement: .mobileMoney,
                rappelJoursAvant: 2,
                montantEstime: true
            ),
            DepensePlanifiee(
                libelle: "Abonnement internet",
                montant: 20_000,
                categorie: categorie("Factures & abonnements"),
                frequence: .mensuel,
                dateDebut: debutDuMois,
                jourDuMois: 20,
                moyenPaiement: .prelevement,
                rappelJoursAvant: 1
            ),
            DepensePlanifiee(
                libelle: "Scolarité",
                montant: 300_000,
                categorie: categorie("Éducation"),
                frequence: .trimestriel,
                dateDebut: debutDuMois,
                jourDuMois: 10,
                moyenPaiement: .virement,
                rappelJoursAvant: 7
            ),
            DepensePlanifiee(
                libelle: "Épargne automatique",
                montant: 50_000,
                categorie: categorie("Épargne"),
                frequence: .mensuel,
                dateDebut: debutDuMois,
                jourDuMois: 28,
                moyenPaiement: .virement,
                rappelJoursAvant: 2
            ),
        ]
        planifiees.forEach { contexte.insert($0) }

        let exemples: [(String, Decimal, String, Int, MoyenPaiement)] = [
            ("Marché", 12_500, "Alimentation", -1, .especes),
            ("Taxi", 2_000, "Transport", -1, .especes),
            ("Pharmacie", 8_400, "Santé", -3, .carte),
            ("Restaurant", 15_000, "Loisirs", -4, .carte),
            ("Crédit téléphone", 5_000, "Factures & abonnements", -6, .mobileMoney),
            ("Courses du mois", 45_000, "Alimentation", -8, .carte),
            ("Carburant", 20_000, "Transport", -10, .carte),
        ]

        for (libelle, montant, nomCategorie, decalage, moyen) in exemples {
            let date = calendrier.date(byAdding: .day, value: decalage, to: aujourdHui) ?? aujourdHui
            let depense = Depense(
                libelle: libelle,
                montant: montant,
                date: date,
                categorie: categorie(nomCategorie),
                moyenPaiement: moyen
            )
            contexte.insert(depense)
        }
    }

    /// Supprime toutes les données saisies (utilisé par « Réinitialiser »).
    static func toutEffacer(dans contexte: ModelContext) {
        try? contexte.delete(model: Depense.self)
        try? contexte.delete(model: DepensePlanifiee.self)
        try? contexte.delete(model: OccurrenceSautee.self)
        try? contexte.delete(model: Categorie.self)
    }
}
