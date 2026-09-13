import Foundation
import SwiftData

/// Actions sur une échéance : payer, annuler, ignorer.
enum GestionnaireEcheances {

    /// Transforme une échéance en dépense réelle.
    @discardableResult
    static func marquerPayee(
        _ occurrence: Occurrence,
        montantReel: Decimal? = nil,
        datePaiement: Date? = nil,
        contexte: ModelContext
    ) -> Depense {
        retirerSaut(occurrence, contexte: contexte)

        let depense = Depense(
            libelle: occurrence.planifiee.libelle,
            montant: montantReel ?? occurrence.planifiee.montant,
            date: datePaiement ?? occurrence.date,
            categorie: occurrence.planifiee.categorie,
            moyenPaiement: occurrence.planifiee.moyenPaiement,
            notes: occurrence.planifiee.notes,
            origineID: occurrence.planifiee.id,
            dateEcheance: Calendar.current.startOfDay(for: occurrence.date)
        )
        contexte.insert(depense)
        return depense
    }

    static func annulerPaiement(_ occurrence: Occurrence, contexte: ModelContext) {
        guard let depense = occurrence.depenseAssociee else { return }
        contexte.delete(depense)
    }

    /// « Pas ce mois-ci » : l'échéance est masquée et ne déclenche plus de rappel.
    static func ignorer(_ occurrence: Occurrence, contexte: ModelContext) {
        guard saut(pour: occurrence, contexte: contexte).isEmpty else { return }
        let element = OccurrenceSautee(
            planifieeID: occurrence.planifiee.id,
            date: Calendar.current.startOfDay(for: occurrence.date)
        )
        contexte.insert(element)
    }

    static func reprendre(_ occurrence: Occurrence, contexte: ModelContext) {
        retirerSaut(occurrence, contexte: contexte)
    }

    /// Supprime une planification et, au choix, les dépenses déjà enregistrées pour elle.
    static func supprimer(
        _ planifiee: DepensePlanifiee,
        supprimerHistorique: Bool,
        contexte: ModelContext
    ) {
        let identifiant = planifiee.id
        let identifiantOptionnel: UUID? = identifiant
        if supprimerHistorique {
            let descripteur = FetchDescriptor<Depense>(
                predicate: #Predicate { $0.origineID == identifiantOptionnel }
            )
            for depense in (try? contexte.fetch(descripteur)) ?? [] {
                contexte.delete(depense)
            }
        }
        let sauts = FetchDescriptor<OccurrenceSautee>(
            predicate: #Predicate { $0.planifieeID == identifiant }
        )
        for saut in (try? contexte.fetch(sauts)) ?? [] {
            contexte.delete(saut)
        }
        contexte.delete(planifiee)
    }

    // MARK: - Interne

    private static func saut(pour occurrence: Occurrence, contexte: ModelContext) -> [OccurrenceSautee] {
        let identifiant = occurrence.planifiee.id
        let jour = Calendar.current.startOfDay(for: occurrence.date)
        let descripteur = FetchDescriptor<OccurrenceSautee>(
            predicate: #Predicate { $0.planifieeID == identifiant && $0.date == jour }
        )
        return (try? contexte.fetch(descripteur)) ?? []
    }

    private static func retirerSaut(_ occurrence: Occurrence, contexte: ModelContext) {
        for element in saut(pour: occurrence, contexte: contexte) {
            contexte.delete(element)
        }
    }
}
