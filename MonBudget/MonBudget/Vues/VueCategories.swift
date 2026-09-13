import SwiftData
import SwiftUI
import UIKit

/// Gestion des catégories et de leur plafond mensuel.
struct VueCategories: View {
    @ObservedObject var reglages: Reglages

    @Environment(\.modelContext) private var contexte
    @Query(sort: \Categorie.ordre) private var categories: [Categorie]

    @State private var afficheAjout = false
    @State private var categorieAModifier: Categorie?

    var body: some View {
        List {
            Section {
                ForEach(categories) { categorie in
                    Button {
                        categorieAModifier = categorie
                    } label: {
                        HStack(spacing: 12) {
                            PastilleCategorie(emoji: categorie.emoji, couleurHex: categorie.couleurHex)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(categorie.nom)
                                if let plafond = categorie.plafondMensuel, plafond > 0 {
                                    Text("Plafond : \(Formatteur.montant(plafond, devise: reglages.devise))")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                            }
                            Spacer()
                            Text("\(categorie.depenses.count)")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                    .buttonStyle(.plain)
                }
                .onDelete(perform: supprimer)
                .onMove(perform: deplacer)
            } footer: {
                Text("Supprimer une catégorie ne supprime pas les dépenses : elles deviennent « sans catégorie ».")
            }
        }
        .navigationTitle("Catégories")
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    afficheAjout = true
                } label: {
                    Label("Ajouter", systemImage: "plus")
                }
            }
            ToolbarItem(placement: .topBarLeading) {
                EditButton()
            }
        }
        .sheet(isPresented: $afficheAjout) {
            EditeurCategorie(reglages: reglages, ordreSuivant: categories.count)
        }
        .sheet(item: $categorieAModifier) { categorie in
            EditeurCategorie(reglages: reglages, categorie: categorie, ordreSuivant: categories.count)
        }
    }

    private func supprimer(_ indices: IndexSet) {
        for index in indices {
            contexte.delete(categories[index])
        }
        try? contexte.save()
    }

    private func deplacer(_ source: IndexSet, _ destination: Int) {
        var liste = categories
        liste.move(fromOffsets: source, toOffset: destination)
        for (index, categorie) in liste.enumerated() {
            categorie.ordre = index
        }
        try? contexte.save()
    }
}

/// Création / modification d'une catégorie.
struct EditeurCategorie: View {
    let reglages: Reglages
    var categorie: Categorie?
    var ordreSuivant: Int = 0

    @Environment(\.modelContext) private var contexte
    @Environment(\.dismiss) private var fermer

    @State private var nom = ""
    @State private var emoji = "💸"
    @State private var couleurHex = Color.palette.first ?? "#4F7CFF"
    @State private var utilisePlafond = false
    @State private var plafond: Decimal = 0
    @State private var champsCharges = false

    private let emojisProposes = [
        "🏠", "🛒", "🚌", "🧾", "💊", "🎓", "👨‍👩‍👧", "🎬", "🐖", "💸",
        "☕️", "👕", "⛽️", "📱", "🎁", "✈️", "🏥", "🔧", "🐾", "💼",
    ]

    var body: some View {
        NavigationStack {
            Form {
                Section("Catégorie") {
                    TextField("Nom", text: $nom)
                }

                Section("Icône") {
                    LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 6), spacing: 12) {
                        ForEach(emojisProposes, id: \.self) { valeur in
                            Text(valeur)
                                .font(.title2)
                                .frame(width: 42, height: 42)
                                .background(
                                    Circle().fill(
                                        valeur == emoji
                                            ? Color(hex: couleurHex).opacity(0.25)
                                            : Color(.systemGray6)
                                    )
                                )
                                .onTapGesture { emoji = valeur }
                        }
                    }
                    .padding(.vertical, 4)
                }

                Section("Couleur") {
                    LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 5), spacing: 12) {
                        ForEach(Color.palette, id: \.self) { hex in
                            Circle()
                                .fill(Color(hex: hex))
                                .frame(width: 34, height: 34)
                                .overlay(
                                    Circle()
                                        .stroke(Color.primary, lineWidth: hex == couleurHex ? 2 : 0)
                                )
                                .onTapGesture { couleurHex = hex }
                        }
                    }
                    .padding(.vertical, 4)
                }

                Section {
                    Toggle("Plafond mensuel", isOn: $utilisePlafond)
                    if utilisePlafond {
                        HStack {
                            TextField("Montant", value: $plafond, format: .number)
                                .keyboardType(.decimalPad)
                            Text(reglages.devise)
                                .foregroundStyle(.secondary)
                        }
                    }
                } footer: {
                    Text("Le plafond s'affiche dans les statistiques et signale les catégories qui débordent.")
                }
            }
            .navigationTitle(categorie == nil ? "Nouvelle catégorie" : "Modifier")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Annuler") { fermer() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Enregistrer", action: enregistrer)
                        .disabled(nom.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            }
            .onAppear(perform: charger)
        }
    }

    private func charger() {
        guard !champsCharges else { return }
        champsCharges = true
        guard let categorie else { return }
        nom = categorie.nom
        emoji = categorie.emoji
        couleurHex = categorie.couleurHex
        if let valeur = categorie.plafondMensuel, valeur > 0 {
            utilisePlafond = true
            plafond = valeur
        }
    }

    private func enregistrer() {
        let titre = nom.trimmingCharacters(in: .whitespaces)
        let cible = categorie ?? Categorie(nom: titre, ordre: ordreSuivant)
        cible.nom = titre
        cible.emoji = emoji
        cible.couleurHex = couleurHex
        cible.plafondMensuel = utilisePlafond && plafond > 0 ? plafond : nil

        if categorie == nil {
            contexte.insert(cible)
        }
        try? contexte.save()
        fermer()
    }
}
