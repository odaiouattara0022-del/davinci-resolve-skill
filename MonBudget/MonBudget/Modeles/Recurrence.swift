import Foundation

/// Fréquence de répétition d'une dépense planifiée.
enum Frequence: String, CaseIterable, Identifiable, Codable {
    case unique
    case quotidien
    case hebdomadaire
    case mensuel
    case trimestriel
    case annuel

    var id: String { rawValue }

    var libelle: String {
        switch self {
        case .unique: return "Une seule fois"
        case .quotidien: return "Tous les jours"
        case .hebdomadaire: return "Toutes les semaines"
        case .mensuel: return "Tous les mois"
        case .trimestriel: return "Tous les trimestres"
        case .annuel: return "Tous les ans"
        }
    }

    /// Libellé tenant compte de l'intervalle (« tous les 2 mois »).
    func libelle(intervalle: Int) -> String {
        guard intervalle > 1 else { return libelle }
        switch self {
        case .unique: return libelle
        case .quotidien: return "Tous les \(intervalle) jours"
        case .hebdomadaire: return "Toutes les \(intervalle) semaines"
        case .mensuel: return "Tous les \(intervalle) mois"
        case .trimestriel: return "Tous les \(intervalle * 3) mois"
        case .annuel: return "Tous les \(intervalle) ans"
        }
    }

    /// Nombre de mois ajoutés à chaque répétition (0 pour les fréquences en jours).
    var moisParPeriode: Int {
        switch self {
        case .mensuel: return 1
        case .trimestriel: return 3
        case .annuel: return 12
        default: return 0
        }
    }

    /// Nombre de jours ajoutés à chaque répétition (0 pour les fréquences en mois).
    var joursParPeriode: Int {
        switch self {
        case .quotidien: return 1
        case .hebdomadaire: return 7
        default: return 0
        }
    }
}

/// Règle de répétition, indépendante de SwiftData pour rester testable.
struct RegleRecurrence: Equatable {
    var frequence: Frequence
    /// Répéter toutes les N périodes (1 = chaque période).
    var intervalle: Int
    var dateDebut: Date
    var dateFin: Date?
    /// Jour du mois souhaité pour les fréquences mensuelles/annuelles.
    /// Si le mois est plus court (31 → février), la date est ramenée au dernier jour du mois.
    var jourDuMois: Int?

    init(
        frequence: Frequence,
        intervalle: Int = 1,
        dateDebut: Date,
        dateFin: Date? = nil,
        jourDuMois: Int? = nil
    ) {
        self.frequence = frequence
        self.intervalle = max(1, intervalle)
        self.dateDebut = dateDebut
        self.dateFin = dateFin
        self.jourDuMois = jourDuMois
    }
}
