import Foundation
import SwiftData

/// Une dépense prévue : loyer, abonnement, scolarité, crédit…
///
/// L'objet décrit *la règle* ; les échéances concrètes sont calculées à la volée
/// par `MoteurRecurrence`, ce qui évite de stocker des milliers de lignes.
@Model
final class DepensePlanifiee {
    var id: UUID = UUID()
    var libelle: String = ""
    var montant: Decimal = Decimal(0)
    var notes: String = ""
    var actif: Bool = true

    var frequenceBrute: String = Frequence.mensuel.rawValue
    var intervalle: Int = 1
    var dateDebut: Date = Date()
    var dateFin: Date?
    var jourDuMois: Int?

    var moyenPaiementBrut: String = MoyenPaiement.prelevement.rawValue
    /// Nombre de jours de préavis pour le rappel (0 = le jour même).
    var rappelJoursAvant: Int = 2
    /// Heure d'envoi du rappel (0-23).
    var rappelHeure: Int = 9
    /// Rappel supplémentaire le jour de l'échéance.
    var rappelJourJ: Bool = true
    /// Montant variable (facture d'électricité par ex.) : le montant sert d'estimation.
    var montantEstime: Bool = false

    var creeLe: Date = Date()
    var categorie: Categorie?

    init(
        id: UUID = UUID(),
        libelle: String,
        montant: Decimal,
        categorie: Categorie? = nil,
        frequence: Frequence = .mensuel,
        intervalle: Int = 1,
        dateDebut: Date = Date(),
        dateFin: Date? = nil,
        jourDuMois: Int? = nil,
        moyenPaiement: MoyenPaiement = .prelevement,
        rappelJoursAvant: Int = 2,
        rappelHeure: Int = 9,
        rappelJourJ: Bool = true,
        montantEstime: Bool = false,
        notes: String = "",
        actif: Bool = true
    ) {
        self.id = id
        self.libelle = libelle
        self.montant = montant
        self.categorie = categorie
        self.frequenceBrute = frequence.rawValue
        self.intervalle = max(1, intervalle)
        self.dateDebut = dateDebut
        self.dateFin = dateFin
        self.jourDuMois = jourDuMois
        self.moyenPaiementBrut = moyenPaiement.rawValue
        self.rappelJoursAvant = rappelJoursAvant
        self.rappelHeure = rappelHeure
        self.rappelJourJ = rappelJourJ
        self.montantEstime = montantEstime
        self.notes = notes
        self.actif = actif
        self.creeLe = Date()
    }

    var frequence: Frequence {
        get { Frequence(rawValue: frequenceBrute) ?? .mensuel }
        set { frequenceBrute = newValue.rawValue }
    }

    var moyenPaiement: MoyenPaiement {
        get { MoyenPaiement(rawValue: moyenPaiementBrut) ?? .prelevement }
        set { moyenPaiementBrut = newValue.rawValue }
    }

    var regle: RegleRecurrence {
        RegleRecurrence(
            frequence: frequence,
            intervalle: intervalle,
            dateDebut: dateDebut,
            dateFin: dateFin,
            jourDuMois: jourDuMois
        )
    }

    var resumeRecurrence: String {
        frequence.libelle(intervalle: intervalle)
    }
}

/// Échéance volontairement ignorée par l'utilisateur (« pas ce mois-ci »).
@Model
final class OccurrenceSautee {
    var id: UUID = UUID()
    var planifieeID: UUID = UUID()
    var date: Date = Date()

    init(planifieeID: UUID, date: Date) {
        self.id = UUID()
        self.planifieeID = planifieeID
        self.date = date
    }
}
