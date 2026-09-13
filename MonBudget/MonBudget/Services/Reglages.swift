import Combine
import Foundation

/// Préférences de l'application, stockées dans `UserDefaults`.
///
/// Un objet observable unique plutôt que des `@AppStorage` dispersés : les
/// services (notifications, export) ont besoin des mêmes valeurs que les vues.
final class Reglages: ObservableObject {
    static let partages = Reglages()

    private let stockage: UserDefaults

    init(stockage: UserDefaults = .standard) {
        self.stockage = stockage
        self.devise = stockage.string(forKey: Cle.devise) ?? Reglages.deviseDuTelephone
        self.budgetMensuel = stockage.double(forKey: Cle.budgetMensuel)
        self.notificationsActives = stockage.object(forKey: Cle.notificationsActives) as? Bool ?? true
        self.resumeMensuelActif = stockage.object(forKey: Cle.resumeMensuel) as? Bool ?? true
        self.heureResume = stockage.object(forKey: Cle.heureResume) as? Int ?? 9
        self.alerteBudgetActive = stockage.object(forKey: Cle.alerteBudget) as? Bool ?? true
        self.seuilAlerte = stockage.object(forKey: Cle.seuilAlerte) as? Double ?? 0.8
        self.verrouillageActif = stockage.bool(forKey: Cle.verrouillage)
        self.donneesInitialisees = stockage.bool(forKey: Cle.donneesInitialisees)
    }

    @Published var devise: String {
        didSet { stockage.set(devise, forKey: Cle.devise) }
    }

    /// Budget global du mois. `0` signifie « aucun budget défini ».
    @Published var budgetMensuel: Double {
        didSet { stockage.set(budgetMensuel, forKey: Cle.budgetMensuel) }
    }

    @Published var notificationsActives: Bool {
        didSet { stockage.set(notificationsActives, forKey: Cle.notificationsActives) }
    }

    @Published var resumeMensuelActif: Bool {
        didSet { stockage.set(resumeMensuelActif, forKey: Cle.resumeMensuel) }
    }

    @Published var heureResume: Int {
        didSet { stockage.set(heureResume, forKey: Cle.heureResume) }
    }

    @Published var alerteBudgetActive: Bool {
        didSet { stockage.set(alerteBudgetActive, forKey: Cle.alerteBudget) }
    }

    /// Part du budget à partir de laquelle on prévient (0,8 = 80 %).
    @Published var seuilAlerte: Double {
        didSet { stockage.set(seuilAlerte, forKey: Cle.seuilAlerte) }
    }

    @Published var verrouillageActif: Bool {
        didSet { stockage.set(verrouillageActif, forKey: Cle.verrouillage) }
    }

    @Published var donneesInitialisees: Bool {
        didSet { stockage.set(donneesInitialisees, forKey: Cle.donneesInitialisees) }
    }

    var budgetMensuelDecimal: Decimal? {
        budgetMensuel > 0 ? Decimal(budgetMensuel) : nil
    }

    static var deviseDuTelephone: String {
        Locale.current.currency?.identifier ?? "EUR"
    }

    /// Devises proposées dans les réglages (les plus courantes d'abord).
    static let devisesProposees = [
        "XOF", "EUR", "USD", "XAF", "MAD", "CAD", "GBP", "CHF", "NGN", "GHS", "TND", "DZD",
    ]

    private enum Cle {
        static let devise = "reglage.devise"
        static let budgetMensuel = "reglage.budgetMensuel"
        static let notificationsActives = "reglage.notificationsActives"
        static let resumeMensuel = "reglage.resumeMensuel"
        static let heureResume = "reglage.heureResume"
        static let alerteBudget = "reglage.alerteBudget"
        static let seuilAlerte = "reglage.seuilAlerte"
        static let verrouillage = "reglage.verrouillage"
        static let donneesInitialisees = "reglage.donneesInitialisees"
    }
}
