import Foundation

/// État d'une échéance à une date donnée.
enum StatutOccurrence: String {
    case payee
    case sautee
    case enRetard
    case aujourdHui
    case aVenir

    var libelle: String {
        switch self {
        case .payee: return "Payé"
        case .sautee: return "Ignoré"
        case .enRetard: return "En retard"
        case .aujourdHui: return "Aujourd'hui"
        case .aVenir: return "À venir"
        }
    }

    /// Compte dans le « reste à payer » du mois.
    var resteADebiter: Bool {
        self == .enRetard || self == .aujourdHui || self == .aVenir
    }
}

/// Une échéance concrète d'une dépense planifiée (calculée, non stockée).
struct Occurrence: Identifiable {
    let planifiee: DepensePlanifiee
    let date: Date
    let statut: StatutOccurrence
    let depenseAssociee: Depense?

    var id: String { "\(planifiee.id.uuidString)-\(Int(date.timeIntervalSince1970))" }
    var montant: Decimal { depenseAssociee?.montant ?? planifiee.montant }
    var libelle: String { planifiee.libelle }
}

/// Total d'une catégorie sur une période.
struct TotalCategorie: Identifiable {
    let categorie: Categorie?
    let total: Decimal

    var id: String { categorie?.id.uuidString ?? "sans-categorie" }
    var nom: String { categorie?.nom ?? "Sans catégorie" }
    var emoji: String { categorie?.emoji ?? "❔" }
    var couleurHex: String { categorie?.couleurHex ?? "#8E8E93" }
    var plafond: Decimal? { categorie?.plafondMensuel }
}

/// Agrège dépenses réelles et échéances prévues.
enum CalculateurBudget {

    // MARK: - Échéances

    static func occurrences(
        planifiees: [DepensePlanifiee],
        depenses: [Depense],
        sautees: [OccurrenceSautee],
        dans intervalle: DateInterval,
        aujourdHui: Date = Date(),
        calendrier: Calendar = .current
    ) -> [Occurrence] {
        let moteur = MoteurRecurrence(calendrier: calendrier)
        let indexPayees = indexDesPaiements(depenses, calendrier: calendrier)
        let indexSautees = indexDesSauts(sautees, calendrier: calendrier)
        let jourActuel = calendrier.startOfDay(for: aujourdHui)

        var resultats: [Occurrence] = []
        for planifiee in planifiees where planifiee.actif {
            for date in moteur.occurrences(regle: planifiee.regle, dans: intervalle) {
                let cle = cleOccurrence(planifieeID: planifiee.id, date: date, calendrier: calendrier)
                let depense = indexPayees[cle]
                let statut = statutPour(
                    date: date,
                    jourActuel: jourActuel,
                    estPayee: depense != nil,
                    estSautee: indexSautees.contains(cle)
                )
                resultats.append(
                    Occurrence(planifiee: planifiee, date: date, statut: statut, depenseAssociee: depense)
                )
            }
        }
        return resultats.sorted { gauche, droite in
            if gauche.date == droite.date { return gauche.libelle < droite.libelle }
            return gauche.date < droite.date
        }
    }

    /// Les prochaines échéances non réglées, tous plans confondus.
    static func prochainesEcheances(
        planifiees: [DepensePlanifiee],
        depenses: [Depense],
        sautees: [OccurrenceSautee],
        aPartirDe date: Date = Date(),
        horizonJours: Int = 60,
        limite: Int = 10,
        calendrier: Calendar = .current
    ) -> [Occurrence] {
        let debut = calendrier.date(byAdding: .day, value: -45, to: date) ?? date
        let fin = calendrier.date(byAdding: .day, value: horizonJours, to: date) ?? date
        let intervalle = DateInterval(start: min(debut, fin), end: max(debut, fin))
        return occurrences(
            planifiees: planifiees,
            depenses: depenses,
            sautees: sautees,
            dans: intervalle,
            aujourdHui: date,
            calendrier: calendrier
        )
        .filter { $0.statut.resteADebiter }
        .prefix(limite)
        .map { $0 }
    }

    // MARK: - Totaux

    static func total(_ depenses: [Depense], dans intervalle: DateInterval) -> Decimal {
        depenses
            .filter { intervalle.contains($0.date) }
            .reduce(Decimal(0)) { $0 + $1.montant }
    }

    static func total(_ depenses: [Depense]) -> Decimal {
        depenses.reduce(Decimal(0)) { $0 + $1.montant }
    }

    static func resteAPayer(_ occurrences: [Occurrence]) -> Decimal {
        occurrences
            .filter { $0.statut.resteADebiter }
            .reduce(Decimal(0)) { $0 + $1.montant }
    }

    static func totauxParCategorie(_ depenses: [Depense]) -> [TotalCategorie] {
        var totaux: [String: (Categorie?, Decimal)] = [:]
        for depense in depenses {
            let cle = depense.categorie?.id.uuidString ?? "sans-categorie"
            let courant = totaux[cle]?.1 ?? Decimal(0)
            totaux[cle] = (depense.categorie, courant + depense.montant)
        }
        return totaux.values
            .map { TotalCategorie(categorie: $0.0, total: $0.1) }
            .sorted { $0.total > $1.total }
    }

    // MARK: - Outils internes

    private static func statutPour(
        date: Date,
        jourActuel: Date,
        estPayee: Bool,
        estSautee: Bool
    ) -> StatutOccurrence {
        if estPayee { return .payee }
        if estSautee { return .sautee }
        if date < jourActuel { return .enRetard }
        if date == jourActuel { return .aujourdHui }
        return .aVenir
    }

    private static func indexDesPaiements(_ depenses: [Depense], calendrier: Calendar) -> [String: Depense] {
        var index: [String: Depense] = [:]
        for depense in depenses {
            guard let origine = depense.origineID, let echeance = depense.dateEcheance else { continue }
            index[cleOccurrence(planifieeID: origine, date: echeance, calendrier: calendrier)] = depense
        }
        return index
    }

    private static func indexDesSauts(_ sautees: [OccurrenceSautee], calendrier: Calendar) -> Set<String> {
        Set(sautees.map { cleOccurrence(planifieeID: $0.planifieeID, date: $0.date, calendrier: calendrier) })
    }

    static func cleOccurrence(planifieeID: UUID, date: Date, calendrier: Calendar = .current) -> String {
        let jour = calendrier.startOfDay(for: date)
        return "\(planifieeID.uuidString)-\(Int(jour.timeIntervalSince1970))"
    }
}
