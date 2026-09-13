import SwiftUI
import SwiftData

/// Historique des dépenses, mois par mois.
struct VueDepenses: View {
    @ObservedObject var reglages: Reglages

    @Environment(\.modelContext) private var contexte
    @Query(sort: \Depense.date, order: .reverse) private var toutesLesDepenses: [Depense]
    @Query(sort: \Categorie.ordre) private var categories: [Categorie]

    @State private var mois = Date()
    @State private var recherche = ""
    @State private var filtreCategorieID: UUID?
    @State private var afficheAjout = false
    @State private var depenseAModifier: Depense?

    private let calendrier = Calendar.current

    var body: some View {
        NavigationStack {
            List {
                Section {
                    SelecteurMois(mois: $mois)
                    HStack {
                        Text("Total du mois")
                            .font(.subheadline)
                        Spacer()
                        Text(Formatteur.montant(totalAffiche, devise: reglages.devise))
                            .font(.headline)
                            .monospacedDigit()
                    }
                    Picker("Catégorie", selection: $filtreCategorieID) {
                        Text("Toutes les catégories").tag(UUID?.none)
                        ForEach(categories) { categorie in
                            Text("\(categorie.emoji)  \(categorie.nom)").tag(Optional(categorie.id))
                        }
                    }
                }

                if groupes.isEmpty {
                    Section {
                        VueVide(
                            symbole: "magnifyingglass",
                            titre: "Aucune dépense",
                            message: "Aucune dépense ne correspond à ce mois ou à ce filtre."
                        )
                    }
                }

                ForEach(groupes) { groupe in
                    Section {
                        ForEach(groupe.depenses) { depense in
                            Button {
                                depenseAModifier = depense
                            } label: {
                                LigneDepense(depense: depense, devise: reglages.devise)
                            }
                            .buttonStyle(.plain)
                            .swipeActions(edge: .trailing) {
                                Button(role: .destructive) {
                                    supprimer(depense)
                                } label: {
                                    Label("Supprimer", systemImage: "trash")
                                }
                            }
                        }
                    } header: {
                        HStack {
                            Text(Formatteur.titreJour(groupe.jour))
                            Spacer()
                            Text(Formatteur.montant(CalculateurBudget.total(groupe.depenses), devise: reglages.devise))
                        }
                    }
                }
            }
            .searchable(text: $recherche, prompt: "Rechercher une dépense")
            .navigationTitle("Dépenses")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        afficheAjout = true
                    } label: {
                        Label("Ajouter", systemImage: "plus")
                    }
                }
            }
            .sheet(isPresented: $afficheAjout) {
                EditeurDepense(reglages: reglages)
            }
            .sheet(item: $depenseAModifier) { depense in
                EditeurDepense(reglages: reglages, depense: depense)
            }
        }
    }

    // MARK: - Données

    private var depensesFiltrees: [Depense] {
        let intervalle = calendrier.intervalleDuMois(contenant: mois)
        let texte = recherche.trimmingCharacters(in: .whitespaces).lowercased()

        return toutesLesDepenses.filter { depense in
            guard intervalle.contains(depense.date) else { return false }
            if let filtreCategorieID, depense.categorie?.id != filtreCategorieID { return false }
            guard !texte.isEmpty else { return true }
            return depense.libelle.lowercased().contains(texte)
                || depense.notes.lowercased().contains(texte)
                || (depense.categorie?.nom.lowercased().contains(texte) ?? false)
        }
    }

    private var totalAffiche: Decimal {
        CalculateurBudget.total(depensesFiltrees)
    }

    private var groupes: [GroupeJour] {
        let groupees = Dictionary(grouping: depensesFiltrees) { calendrier.startOfDay(for: $0.date) }
        return groupees
            .map { GroupeJour(jour: $0.key, depenses: $0.value.sorted { $0.date > $1.date }) }
            .sorted { $0.jour > $1.jour }
    }

    private func supprimer(_ depense: Depense) {
        contexte.delete(depense)
        try? contexte.save()
        NotificationCenter.default.post(name: .donneesModifiees, object: nil)
    }
}

/// Dépenses d'une même journée.
struct GroupeJour: Identifiable {
    let jour: Date
    let depenses: [Depense]
    var id: Date { jour }
}
