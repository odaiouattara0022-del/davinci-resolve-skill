import Foundation
import UserNotifications

extension Notification.Name {
    /// Émise quand l'utilisateur ouvre l'app depuis un rappel d'échéance.
    static let ouvrirEcheances = Notification.Name("monbudget.ouvrirEcheances")
}

/// Programme les rappels locaux (aucun serveur, tout reste sur l'iPhone).
///
/// iOS limite à 64 le nombre de notifications en attente : on reprogramme donc
/// l'ensemble à chaque changement de données, en gardant les plus proches.
final class ServiceNotifications: NSObject, UNUserNotificationCenterDelegate {
    static let partage = ServiceNotifications()

    private let centre = UNUserNotificationCenter.current()
    private let limiteNotifications = 56
    /// Nombre d'échéances futures prises en compte par dépense planifiée.
    private let echeancesParPlanification = 4

    private override init() {
        super.init()
    }

    func installerDelegue() {
        centre.delegate = self
    }

    @discardableResult
    func demanderAutorisation() async -> Bool {
        do {
            return try await centre.requestAuthorization(options: [.alert, .sound, .badge])
        } catch {
            return false
        }
    }

    func statutAutorisation() async -> UNAuthorizationStatus {
        await centre.notificationSettings().authorizationStatus
    }

    // MARK: - Programmation

    /// Recalcule tous les rappels. À appeler après chaque modification de données.
    func reprogrammerTout(
        planifiees: [DepensePlanifiee],
        depenses: [Depense],
        sautees: [OccurrenceSautee],
        reglages: Reglages,
        calendrier: Calendar = .current,
        maintenant: Date = Date()
    ) async {
        centre.removeAllPendingNotificationRequests()
        guard reglages.notificationsActives else { return }
        guard await statutAutorisation() == .authorized || await statutAutorisation() == .provisional else { return }

        var demandes = demandesEcheances(
            planifiees: planifiees,
            depenses: depenses,
            sautees: sautees,
            devise: reglages.devise,
            calendrier: calendrier,
            maintenant: maintenant
        )

        if reglages.resumeMensuelActif, let resume = demandeResumeMensuel(heure: reglages.heureResume) {
            demandes.append(resume)
        }

        for demande in demandes.prefix(limiteNotifications) {
            try? await centre.add(demande)
        }
    }

    /// Prévient immédiatement quand le budget du mois franchit le seuil d'alerte.
    func alerterBudget(depense: Decimal, budget: Decimal, devise: String, depassement: Bool) async {
        let contenu = UNMutableNotificationContent()
        contenu.title = depassement ? "Budget dépassé" : "Attention au budget"
        contenu.body = depassement
            ? "Vous avez dépensé \(Formatteur.montant(depense, devise: devise)) sur un budget de \(Formatteur.montant(budget, devise: devise))."
            : "Déjà \(Formatteur.montant(depense, devise: devise)) dépensés sur \(Formatteur.montant(budget, devise: devise)) ce mois-ci."
        contenu.sound = .default

        let demande = UNNotificationRequest(
            identifier: "alerte-budget-\(Int(Date().timeIntervalSince1970))",
            content: contenu,
            trigger: UNTimeIntervalNotificationTrigger(timeInterval: 2, repeats: false)
        )
        try? await centre.add(demande)
    }

    func toutAnnuler() {
        centre.removeAllPendingNotificationRequests()
    }

    // MARK: - Construction des demandes

    private func demandesEcheances(
        planifiees: [DepensePlanifiee],
        depenses: [Depense],
        sautees: [OccurrenceSautee],
        devise: String,
        calendrier: Calendar,
        maintenant: Date
    ) -> [UNNotificationRequest] {
        let moteur = MoteurRecurrence(calendrier: calendrier)
        let clesPayees = Set(depenses.compactMap { depense -> String? in
            guard let origine = depense.origineID, let echeance = depense.dateEcheance else { return nil }
            return CalculateurBudget.cleOccurrence(planifieeID: origine, date: echeance, calendrier: calendrier)
        })
        let clesSautees = Set(sautees.map {
            CalculateurBudget.cleOccurrence(planifieeID: $0.planifieeID, date: $0.date, calendrier: calendrier)
        })

        var prevues: [(declenchement: Date, demande: UNNotificationRequest)] = []

        for planifiee in planifiees where planifiee.actif {
            let echeances = moteur.prochainesOccurrences(
                regle: planifiee.regle,
                aPartirDe: maintenant,
                nombre: echeancesParPlanification
            )

            for echeance in echeances {
                let cle = CalculateurBudget.cleOccurrence(planifieeID: planifiee.id, date: echeance, calendrier: calendrier)
                if clesPayees.contains(cle) || clesSautees.contains(cle) { continue }

                if planifiee.rappelJoursAvant > 0,
                   let dateRappel = dateDeclenchement(
                       echeance: echeance,
                       joursAvant: planifiee.rappelJoursAvant,
                       heure: planifiee.rappelHeure,
                       calendrier: calendrier
                   ),
                   dateRappel > maintenant {
                    let demande = construireDemande(
                        identifiant: "echeance-\(cle)-avant",
                        titre: "Échéance dans \(planifiee.rappelJoursAvant) jour\(planifiee.rappelJoursAvant > 1 ? "s" : "")",
                        corps: corps(pour: planifiee, echeance: echeance, devise: devise, calendrier: calendrier),
                        date: dateRappel,
                        planifieeID: planifiee.id,
                        calendrier: calendrier
                    )
                    prevues.append((dateRappel, demande))
                }

                if planifiee.rappelJourJ || planifiee.rappelJoursAvant == 0,
                   let dateJourJ = dateDeclenchement(
                       echeance: echeance,
                       joursAvant: 0,
                       heure: planifiee.rappelHeure,
                       calendrier: calendrier
                   ),
                   dateJourJ > maintenant {
                    let demande = construireDemande(
                        identifiant: "echeance-\(cle)-jourj",
                        titre: "À payer aujourd'hui",
                        corps: corps(pour: planifiee, echeance: echeance, devise: devise, calendrier: calendrier),
                        date: dateJourJ,
                        planifieeID: planifiee.id,
                        calendrier: calendrier
                    )
                    prevues.append((dateJourJ, demande))
                }
            }
        }

        return prevues
            .sorted { $0.declenchement < $1.declenchement }
            .map { $0.demande }
    }

    private func corps(
        pour planifiee: DepensePlanifiee,
        echeance: Date,
        devise: String,
        calendrier: Calendar
    ) -> String {
        let montant = Formatteur.montant(planifiee.montant, devise: devise)
        let jour = Formatteur.dateCourte(echeance)
        let estimation = planifiee.montantEstime ? " (estimation)" : ""
        return "\(planifiee.libelle) — \(montant)\(estimation), prévu le \(jour)."
    }

    private func construireDemande(
        identifiant: String,
        titre: String,
        corps: String,
        date: Date,
        planifieeID: UUID,
        calendrier: Calendar
    ) -> UNNotificationRequest {
        let contenu = UNMutableNotificationContent()
        contenu.title = titre
        contenu.body = corps
        contenu.sound = .default
        contenu.userInfo = ["planifieeID": planifieeID.uuidString]

        var composants = calendrier.dateComponents([.year, .month, .day, .hour, .minute], from: date)
        composants.second = 0

        return UNNotificationRequest(
            identifier: identifiant,
            content: contenu,
            trigger: UNCalendarNotificationTrigger(dateMatching: composants, repeats: false)
        )
    }

    private func dateDeclenchement(
        echeance: Date,
        joursAvant: Int,
        heure: Int,
        calendrier: Calendar
    ) -> Date? {
        guard let jour = calendrier.date(byAdding: .day, value: -joursAvant, to: echeance) else { return nil }
        return calendrier.date(
            bySettingHour: min(max(0, heure), 23),
            minute: 0,
            second: 0,
            of: jour
        )
    }

    private func demandeResumeMensuel(heure: Int) -> UNNotificationRequest? {
        let contenu = UNMutableNotificationContent()
        contenu.title = "Nouveau mois"
        contenu.body = "Ouvrez MonBudget pour vérifier vos dépenses prévues et ajuster votre budget."
        contenu.sound = .default

        var composants = DateComponents()
        composants.day = 1
        composants.hour = min(max(0, heure), 23)
        composants.minute = 0

        return UNNotificationRequest(
            identifier: "resume-mensuel",
            content: contenu,
            trigger: UNCalendarNotificationTrigger(dateMatching: composants, repeats: true)
        )
    }

    // MARK: - UNUserNotificationCenterDelegate

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification
    ) async -> UNNotificationPresentationOptions {
        [.banner, .sound, .list]
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse
    ) async {
        await MainActor.run {
            NotificationCenter.default.post(name: .ouvrirEcheances, object: nil)
        }
    }
}
