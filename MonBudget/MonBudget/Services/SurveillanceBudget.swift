import Foundation

/// Surveille le budget du mois et déclenche au plus une alerte par palier et par mois.
enum SurveillanceBudget {
    enum Palier: Int {
        case aucun = 0
        case seuil = 1
        case depassement = 2
    }

    static func palier(depense: Decimal, budget: Decimal, seuil: Double) -> Palier {
        guard budget > 0 else { return .aucun }
        let ratio = depense.enDouble / budget.enDouble
        if ratio >= 1 { return .depassement }
        if ratio >= seuil { return .seuil }
        return .aucun
    }

    /// Vérifie le budget et notifie si un nouveau palier est franchi ce mois-ci.
    static func verifier(
        depenses: [Depense],
        reglages: Reglages,
        maintenant: Date = Date(),
        calendrier: Calendar = .current,
        stockage: UserDefaults = .standard
    ) async {
        guard reglages.alerteBudgetActive,
              reglages.notificationsActives,
              let budget = reglages.budgetMensuelDecimal else { return }

        let mois = calendrier.intervalleDuMois(contenant: maintenant)
        let total = CalculateurBudget.total(depenses, dans: mois)
        let nouveau = palier(depense: total, budget: budget, seuil: reglages.seuilAlerte)
        guard nouveau != .aucun else { return }

        let composants = calendrier.dateComponents([.year, .month], from: maintenant)
        let cle = "alerte.budget.\(composants.year ?? 0)-\(composants.month ?? 0)"
        let dejaSignale = stockage.integer(forKey: cle)
        guard nouveau.rawValue > dejaSignale else { return }

        stockage.set(nouveau.rawValue, forKey: cle)
        await ServiceNotifications.partage.alerterBudget(
            depense: total,
            budget: budget,
            devise: reglages.devise,
            depassement: nouveau == .depassement
        )
    }
}
