import SwiftUI
import SwiftData
import UIKit

/// Tableau de bord : où en est le mois, ce qui reste à payer, les alertes.
struct VueAccueil: View {
    @ObservedObject var reglages: Reglages
    @Binding var onglet: Onglet

    @Environment(\.modelContext) private var contexte
    @Query(sort: \Depense.date, order: .reverse) private var depenses: [Depense]
    @Query private var planifiees: [DepensePlanifiee]
    @Query private var sautees: [OccurrenceSautee]

    @State private var afficheAjout = false
    @State private var occurrenceAPayer: Occurrence?

    private let calendrier = Calendar.current

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    entete
                    carteBudget
                    if !enRetard.isEmpty { sectionRetards }
                    sectionProchaines
                    sectionDernieresDepenses
                }
                .padding(.horizontal)
                .padding(.bottom, 24)
            }
            .background(Color(.systemGroupedBackground))
            .navigationTitle("Accueil")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        afficheAjout = true
                    } label: {
                        Label("Ajouter une dépense", systemImage: "plus.circle.fill")
                    }
                }
            }
            .sheet(isPresented: $afficheAjout) {
                EditeurDepense(reglages: reglages)
            }
            .sheet(item: $occurrenceAPayer) { occurrence in
                FeuillePaiement(occurrence: occurrence, reglages: reglages)
            }
        }
    }

    // MARK: - Sections

    private var entete: some View {
        VStack(spacing: 12) {
            Text(Formatteur.moisEtAnnee(Date()).capitalizedPremiereLettre)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)

            HStack(spacing: 12) {
                CarteStat(
                    titre: "Dépensé ce mois",
                    valeur: Formatteur.montant(totalDuMois, devise: reglages.devise),
                    detail: comparaisonMoisPrecedent,
                    symbole: "arrow.down.circle.fill",
                    couleur: .blue
                )
                CarteStat(
                    titre: "Reste à payer",
                    valeur: Formatteur.montant(resteAPayer, devise: reglages.devise),
                    detail: "\(occurrencesRestantes.count) échéance\(occurrencesRestantes.count > 1 ? "s" : "") prévue\(occurrencesRestantes.count > 1 ? "s" : "")",
                    symbole: "calendar.badge.clock",
                    couleur: .orange
                )
            }
        }
    }

    @ViewBuilder
    private var carteBudget: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Budget du mois")
                    .font(.headline)
                Spacer()
                if let budget = reglages.budgetMensuelDecimal {
                    Text(Formatteur.montant(budget, devise: reglages.devise))
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }

            if let budget = reglages.budgetMensuelDecimal, budget > 0 {
                let progression = totalDuMois.enDouble / budget.enDouble
                BarreProgression(progression: progression)
                HStack {
                    Text("\(Int((progression * 100).rounded())) % utilisé")
                    Spacer()
                    let restant = budget - totalDuMois
                    Text(restant >= 0
                         ? "Il reste \(Formatteur.montant(restant, devise: reglages.devise))"
                         : "Dépassement de \(Formatteur.montant(-restant, devise: reglages.devise))")
                        .foregroundStyle(restant >= 0 ? .secondary : Color.red)
                }
                .font(.caption)
                .foregroundStyle(.secondary)

                if resteAPayer > 0 {
                    Text("Prévisionnel fin de mois : \(Formatteur.montant(totalDuMois + resteAPayer, devise: reglages.devise))")
                        .font(.caption)
                        .foregroundStyle(totalDuMois + resteAPayer > budget ? Color.red : Color.secondary)
                }
            } else {
                Text("Définissez un budget mensuel pour suivre votre marge et être prévenu avant de le dépasser.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Button("Définir un budget") { onglet = .reglages }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 16))
    }

    private var sectionRetards: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("En retard", systemImage: "exclamationmark.triangle.fill")
                .font(.headline)
                .foregroundStyle(.red)
            ForEach(enRetard) { occurrence in
                ligneEcheance(occurrence)
            }
        }
        .padding(14)
        .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 16))
    }

    private var sectionProchaines: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Prochaines échéances")
                    .font(.headline)
                Spacer()
                Button("Tout voir") { onglet = .echeances }
                    .font(.caption)
            }

            if prochaines.isEmpty {
                VueVide(
                    symbole: "calendar",
                    titre: "Rien de prévu",
                    message: "Ajoutez vos dépenses récurrentes (loyer, factures, abonnements) pour être prévenu avant chaque échéance."
                )
            } else {
                ForEach(prochaines) { occurrence in
                    ligneEcheance(occurrence)
                }
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 16))
    }

    private var sectionDernieresDepenses: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Dernières dépenses")
                    .font(.headline)
                Spacer()
                Button("Tout voir") { onglet = .depenses }
                    .font(.caption)
            }

            if depenses.isEmpty {
                VueVide(
                    symbole: "tray",
                    titre: "Aucune dépense",
                    message: "Touchez + pour enregistrer votre première dépense."
                )
            } else {
                ForEach(depenses.prefix(5)) { depense in
                    LigneDepense(depense: depense, devise: reglages.devise)
                    if depense.id != depenses.prefix(5).last?.id {
                        Divider()
                    }
                }
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 16))
    }

    private func ligneEcheance(_ occurrence: Occurrence) -> some View {
        HStack(spacing: 10) {
            LigneOccurrence(occurrence: occurrence, devise: reglages.devise)
            Button {
                occurrenceAPayer = occurrence
            } label: {
                Image(systemName: "checkmark.circle")
                    .font(.title3)
            }
            .buttonStyle(.borderless)
            .accessibilityLabel("Marquer \(occurrence.libelle) comme payé")
        }
        .padding(.vertical, 2)
    }

    // MARK: - Calculs

    private var moisCourant: DateInterval {
        calendrier.intervalleDuMois(contenant: Date())
    }

    private var totalDuMois: Decimal {
        CalculateurBudget.total(depenses, dans: moisCourant)
    }

    private var comparaisonMoisPrecedent: String? {
        let moisPrecedent = calendrier.intervalleDuMois(contenant: calendrier.mois(decale: -1, depuis: Date()))
        let total = CalculateurBudget.total(depenses, dans: moisPrecedent)
        guard total > 0 else { return nil }
        let ecart = (totalDuMois - total).enDouble / total.enDouble * 100
        let signe = ecart >= 0 ? "+" : ""
        return "\(signe)\(Int(ecart.rounded())) % vs mois dernier"
    }

    private var occurrencesDuMois: [Occurrence] {
        CalculateurBudget.occurrences(
            planifiees: planifiees,
            depenses: depenses,
            sautees: sautees,
            dans: moisCourant,
            calendrier: calendrier
        )
    }

    private var occurrencesRestantes: [Occurrence] {
        occurrencesDuMois.filter { $0.statut.resteADebiter }
    }

    private var resteAPayer: Decimal {
        CalculateurBudget.resteAPayer(occurrencesDuMois)
    }

    private var enRetard: [Occurrence] {
        CalculateurBudget.prochainesEcheances(
            planifiees: planifiees,
            depenses: depenses,
            sautees: sautees,
            calendrier: calendrier
        )
        .filter { $0.statut == .enRetard }
    }

    private var prochaines: [Occurrence] {
        let candidats = CalculateurBudget.prochainesEcheances(
            planifiees: planifiees,
            depenses: depenses,
            sautees: sautees,
            limite: 12,
            calendrier: calendrier
        )
        return Array(candidats.filter { $0.statut != .enRetard }.prefix(5))
    }
}
