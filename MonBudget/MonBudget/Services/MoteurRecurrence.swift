import Foundation

/// Calcule les échéances d'une `RegleRecurrence`.
///
/// Volontairement sans dépendance à SwiftUI ni SwiftData : toute la logique de
/// dates est testable unitairement (voir `MoteurRecurrenceTests`).
struct MoteurRecurrence {
    var calendrier: Calendar

    init(calendrier: Calendar = .current) {
        self.calendrier = calendrier
    }

    /// Échéance numéro `index` (0 = première échéance théorique).
    /// Renvoie `nil` quand la règle n'a plus d'échéance (cas `.unique`).
    func occurrence(regle: RegleRecurrence, index: Int) -> Date? {
        guard index >= 0 else { return nil }
        let debut = calendrier.startOfDay(for: regle.dateDebut)

        switch regle.frequence {
        case .unique:
            return index == 0 ? debut : nil
        case .quotidien, .hebdomadaire:
            let jours = regle.frequence.joursParPeriode * regle.intervalle * index
            return calendrier.date(byAdding: .day, value: jours, to: debut)
        case .mensuel, .trimestriel, .annuel:
            let mois = regle.frequence.moisParPeriode * regle.intervalle * index
            return dateMensuelle(regle: regle, decalageMois: mois)
        }
    }

    /// Toutes les échéances comprises dans `intervalle` (bornes incluses, au jour près).
    func occurrences(regle: RegleRecurrence, dans intervalle: DateInterval, limite: Int = 400) -> [Date] {
        let debutRegle = calendrier.startOfDay(for: regle.dateDebut)
        let finRegle = regle.dateFin.map { calendrier.startOfDay(for: $0) }
        let debutFenetre = calendrier.startOfDay(for: intervalle.start)
        let finFenetre = calendrier.startOfDay(for: intervalle.end)

        var resultats: [Date] = []
        var index = 0
        while index < 5000, resultats.count < limite {
            guard let date = occurrence(regle: regle, index: index) else { break }
            index += 1

            if let finRegle, date > finRegle { break }
            if date > finFenetre { break }
            if date < debutRegle { continue }
            if date >= debutFenetre { resultats.append(date) }
            if regle.frequence == .unique { break }
        }
        return resultats
    }

    /// Première échéance à partir de `date` (incluse).
    func prochaineOccurrence(regle: RegleRecurrence, aPartirDe date: Date) -> Date? {
        let seuil = calendrier.startOfDay(for: date)
        let debutRegle = calendrier.startOfDay(for: regle.dateDebut)
        let finRegle = regle.dateFin.map { calendrier.startOfDay(for: $0) }

        var index = 0
        while index < 5000 {
            guard let candidate = occurrence(regle: regle, index: index) else { return nil }
            index += 1
            if let finRegle, candidate > finRegle { return nil }
            if candidate < debutRegle { continue }
            if candidate >= seuil { return candidate }
        }
        return nil
    }

    /// Les `nombre` prochaines échéances à partir de `date`.
    func prochainesOccurrences(regle: RegleRecurrence, aPartirDe date: Date, nombre: Int) -> [Date] {
        guard nombre > 0 else { return [] }
        let seuil = calendrier.startOfDay(for: date)
        let debutRegle = calendrier.startOfDay(for: regle.dateDebut)
        let finRegle = regle.dateFin.map { calendrier.startOfDay(for: $0) }

        var resultats: [Date] = []
        var index = 0
        while index < 5000, resultats.count < nombre {
            guard let candidate = occurrence(regle: regle, index: index) else { break }
            index += 1
            if let finRegle, candidate > finRegle { break }
            if candidate < debutRegle { continue }
            if candidate >= seuil { resultats.append(candidate) }
            if regle.frequence == .unique { break }
        }
        return resultats
    }

    // MARK: - Détail mensuel

    /// Décale le mois de départ tout en ramenant le jour au dernier jour du mois
    /// lorsque celui-ci est trop court (31 janvier → 28/29 février).
    private func dateMensuelle(regle: RegleRecurrence, decalageMois: Int) -> Date? {
        let debut = calendrier.startOfDay(for: regle.dateDebut)
        let composantsDebut = calendrier.dateComponents([.year, .month, .day], from: debut)
        let jourSouhaite = regle.jourDuMois ?? composantsDebut.day ?? 1

        var premier = DateComponents()
        premier.year = composantsDebut.year
        premier.month = composantsDebut.month
        premier.day = 1

        guard let premierDuMois = calendrier.date(from: premier),
              let moisCible = calendrier.date(byAdding: .month, value: decalageMois, to: premierDuMois),
              let plage = calendrier.range(of: .day, in: .month, for: moisCible) else {
            return nil
        }

        var cible = calendrier.dateComponents([.year, .month], from: moisCible)
        cible.day = min(max(1, jourSouhaite), plage.count)
        guard let date = calendrier.date(from: cible) else { return nil }
        return calendrier.startOfDay(for: date)
    }
}
