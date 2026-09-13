import Foundation
import LocalAuthentication
import Observation

/// Verrouillage de l'app par Face ID / Touch ID / code de l'iPhone.
@Observable
final class VerrouillageApp {
    var deverrouille = false
    var messageErreur: String?

    static var biometrieDisponible: Bool {
        let contexte = LAContext()
        var erreur: NSError?
        return contexte.canEvaluatePolicy(.deviceOwnerAuthentication, error: &erreur)
    }

    func verrouiller() {
        deverrouille = false
    }

    func deverrouiller() async {
        let contexte = LAContext()
        contexte.localizedCancelTitle = "Annuler"

        var erreur: NSError?
        guard contexte.canEvaluatePolicy(.deviceOwnerAuthentication, error: &erreur) else {
            // Aucun code ni biométrie configurés : on n'enferme pas l'utilisateur dehors.
            deverrouille = true
            return
        }

        do {
            let succes = try await contexte.evaluatePolicy(
                .deviceOwnerAuthentication,
                localizedReason: "Déverrouillez pour consulter vos dépenses"
            )
            deverrouille = succes
            messageErreur = succes ? nil : "Authentification refusée."
        } catch {
            deverrouille = false
            messageErreur = "Authentification impossible."
        }
    }
}
