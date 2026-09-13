import SwiftUI
import SwiftData

/// Onglet « Prévues » : le calendrier des échéances du mois et la liste des
/// dépenses récurrentes.
struct VueEcheances: View {
    @ObservedObject var reglages: Reglages

    @Environment(\.modelContext) private var contexte
    @Query private var planifiees: [DepensePlanifiee]
    @Query private var depenses: [Depense]
    @Query private var sautees: [OccurrenceSautee]

    @State private var mois = Date()
    @State private var vueChoisie: Presentation = .calendrier
    @State private var afficheAjout = false
    @State private var planAModifier: DepensePlanifiee?
    @State private var occurrenceAPayer: Occurrence?

    private let calendrier = Calendar.current

    enum Presentation: String, CaseIterable {
        case calendrier = "Échéances"
        case plans = "Dépenses prévues"
    }

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Picker("Affichage", selection: $vueChoisie) {
                        ForEach(Presentation.allCases, id: \.self) { presentation in
                            Text(presentation.rawValue).tag(presentation)
                        }
                    }
                    .pickerStyle(.segmented)
                }

                if vueChoisie == .calendrier {
                    sectionsCalendrier
                } else {
                    sectionPlans
                }
            }
            .navigationTitle("Prévues")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        afficheAjout = true
                    } label: {
                        Label("Ajouter une dépense prévue", systemImage: "plus")
                    }
                }
            }
            .sheet(isPresented: $afficheAjout) {
                EditeurPlanifiee(reglages: reglages)
            }
            .sheet(item: $planAModifier) { plan in
                EditeurPlanifiee(reglages: reglages, planifiee: plan)
            }
            .sheet(item: $occurrenceAPayer) { occurrence in
                FeuillePaiement(occurrence: occurrence, reglages: reglages)
            }
        }
    }

    // MARK: - Calendrier des échéances

    @ViewBuilder
    private var sectionsCalendrier: some View {
        Section {
            SelecteurMois(mois: $mois)
            HStack {
                Text("Total prévu")
                Spacer()
                Text(Formatteur.montant(totalPrevu, devise: reglages.devise))
                    .font(.headline)
                    .monospacedDigit()
            }
            HStack {
                Text("Reste à payer")
                Spacer()
                Text(Formatteur.montant(resteAPayer, devise: reglages.devise))
                    .font(.headline)
                    .monospacedDigit()
                    .foregroundStyle(.orange)
            }
        }

        if occurrencesDuMois.isEmpty {
            Section {
                VueVide(
                    symbole: "calendar.badge.plus",
                    titre: "Aucune échéance ce mois-ci",
                    message: "Ajoutez vos dépenses régulières : loyer, factures, abonnements, scolarité, crédits…"
                )
            }
        }

        Section {
            ForEach(occurrencesDuMois) { occurrence in
                LigneOccurrence(occurrence: occurrence, devise: reglages.devise)
                    .swipeActions(edge: .trailing) {
                        switch occurrence.statut {
                        case .payee:
                            Button(role: .destructive) {
                                GestionnaireEcheances.annulerPaiement(occurrence, contexte: contexte)
                                enregistrer()
                            } label: {
                                Label("Annuler", systemImage: "arrow.uturn.backward")
                            }
                        case .sautee:
                            Button {
                                GestionnaireEcheances.reprendre(occurrence, contexte: contexte)
                                enregistrer()
                            } label: {
                                Label("Rétablir", systemImage: "arrow.clockwise")
                            }
                        default:
                            Button {
                                occurrenceAPayer = occurrence
                            } label: {
                                Label("Payer", systemImage: "checkmark.circle")
                            }
                            .tint(.green)
                            Button {
                                GestionnaireEcheances.ignorer(occurrence, contexte: contexte)
                                enregistrer()
                            } label: {
                                Label("Ignorer", systemImage: "xmark.circle")
                            }
                            .tint(.gray)
                        }
                    }
                    .onTapGesture {
                        if occurrence.statut.resteADebiter { occurrenceAPayer = occurrence }
                    }
            }
        } header: {
            Text("Échéances du mois")
        } footer: {
            Text("Balayez une ligne vers la gauche pour la marquer payée ou l'ignorer.")
        }
    }

    // MARK: - Liste des dépenses prévues

    @ViewBuilder
    private var sectionPlans: some View {
        if planifiees.isEmpty {
            Section {
                VueVide(
                    symbole: "repeat.circle",
                    titre: "Aucune dépense prévue",
                    message: "Touchez + pour programmer une dépense qui revient chaque mois."
                )
            }
        }

        Section {
            ForEach(planifiees.sorted { $0.libelle < $1.libelle }) { plan in
                Button {
                    planAModifier = plan
                } label: {
                    LignePlanifiee(planifiee: plan, devise: reglages.devise)
                }
                .buttonStyle(.plain)
                .swipeActions(edge: .trailing) {
                    Button(role: .destructive) {
                        GestionnaireEcheances.supprimer(plan, supprimerHistorique: false, contexte: contexte)
                        enregistrer()
                    } label: {
                        Label("Supprimer", systemImage: "trash")
                    }
                }
                .swipeActions(edge: .leading) {
                    Button {
                        plan.actif.toggle()
                        enregistrer()
                    } label: {
                        Label(plan.actif ? "Suspendre" : "Activer",
                              systemImage: plan.actif ? "pause.circle" : "play.circle")
                    }
                    .tint(plan.actif ? .orange : .green)
                }
            }
        }
    }

    // MARK: - Calculs

    private var intervalleDuMois: DateInterval {
        calendrier.intervalleDuMois(contenant: mois)
    }

    private var occurrencesDuMois: [Occurrence] {
        CalculateurBudget.occurrences(
            planifiees: planifiees,
            depenses: depenses,
            sautees: sautees,
            dans: intervalleDuMois,
            calendrier: calendrier
        )
    }

    private var totalPrevu: Decimal {
        occurrencesDuMois
            .filter { $0.statut != .sautee }
            .reduce(Decimal(0)) { $0 + $1.montant }
    }

    private var resteAPayer: Decimal {
        CalculateurBudget.resteAPayer(occurrencesDuMois)
    }

    private func enregistrer() {
        try? contexte.save()
        NotificationCenter.default.post(name: .donneesModifiees, object: nil)
    }
}

/// Ligne décrivant une dépense récurrente et sa prochaine échéance.
struct LignePlanifiee: View {
    let planifiee: DepensePlanifiee
    let devise: String

    private var prochaine: Date? {
        MoteurRecurrence().prochaineOccurrence(regle: planifiee.regle, aPartirDe: Date())
    }

    var body: some View {
        HStack(spacing: 12) {
            PastilleCategorie(
                emoji: planifiee.categorie?.emoji ?? "🔁",
                couleurHex: planifiee.categorie?.couleurHex ?? "#4F7CFF"
            )
            VStack(alignment: .leading, spacing: 3) {
                Text(planifiee.libelle)
                    .font(.body)
                    .foregroundStyle(planifiee.actif ? .primary : .secondary)
                Text(planifiee.resumeRecurrence)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                if planifiee.actif, let prochaine {
                    Text("Prochaine : \(Formatteur.dateCourte(prochaine)) • \(Formatteur.echeanceRelative(prochaine))")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                } else if !planifiee.actif {
                    Text("Suspendue")
                        .font(.caption2)
                        .foregroundStyle(.orange)
                }
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 2) {
                Text(Formatteur.montant(planifiee.montant, devise: devise))
                    .font(.body.weight(.medium))
                    .monospacedDigit()
                if planifiee.montantEstime {
                    Text("estimé")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
        }
    }
}
