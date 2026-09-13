import SwiftUI
import SwiftData

/// Création / modification d'une dépense.
struct EditeurDepense: View {
    let reglages: Reglages
    var depense: Depense?

    @Environment(\.modelContext) private var contexte
    @Environment(\.dismiss) private var fermer
    @Query(sort: \Categorie.ordre) private var categories: [Categorie]

    @State private var libelle = ""
    @State private var montant: Decimal = 0
    @State private var date = Date()
    @State private var categorieID: UUID?
    @State private var moyenPaiement: MoyenPaiement = .carte
    @State private var notes = ""
    @State private var rendreRecurrente = false
    @State private var frequence: Frequence = .mensuel
    @State private var champsCharges = false

    private var modeEdition: Bool { depense != nil }

    var body: some View {
        NavigationStack {
            Form {
                Section("Dépense") {
                    TextField("Libellé (ex : courses, taxi…)", text: $libelle)
                    HStack {
                        TextField("Montant", value: $montant, format: .number)
                            .keyboardType(.decimalPad)
                        Text(reglages.devise)
                            .foregroundStyle(.secondary)
                    }
                    DatePicker("Date", selection: $date, displayedComponents: .date)
                }

                Section("Classement") {
                    Picker("Catégorie", selection: $categorieID) {
                        Text("Sans catégorie").tag(UUID?.none)
                        ForEach(categories) { categorie in
                            Text("\(categorie.emoji)  \(categorie.nom)").tag(Optional(categorie.id))
                        }
                    }
                    Picker("Moyen de paiement", selection: $moyenPaiement) {
                        ForEach(MoyenPaiement.allCases) { moyen in
                            Label(moyen.libelle, systemImage: moyen.symbole).tag(moyen)
                        }
                    }
                }

                if !modeEdition {
                    Section {
                        Toggle("Dépense qui revient régulièrement", isOn: $rendreRecurrente)
                        if rendreRecurrente {
                            Picker("Fréquence", selection: $frequence) {
                                ForEach(Frequence.allCases.filter { $0 != .unique }) { valeur in
                                    Text(valeur.libelle).tag(valeur)
                                }
                            }
                        }
                    } footer: {
                        if rendreRecurrente {
                            Text("Une dépense prévue sera créée : vous recevrez un rappel avant chaque échéance.")
                        }
                    }
                }

                Section("Notes") {
                    TextField("Facultatif", text: $notes, axis: .vertical)
                        .lineLimit(2...5)
                }

                if modeEdition {
                    Section {
                        Button("Supprimer cette dépense", role: .destructive, action: supprimer)
                    }
                }
            }
            .navigationTitle(modeEdition ? "Modifier" : "Nouvelle dépense")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Annuler") { fermer() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Enregistrer", action: enregistrer)
                        .disabled(libelle.trimmingCharacters(in: .whitespaces).isEmpty || montant <= 0)
                }
            }
            .onAppear(perform: charger)
        }
    }

    // MARK: - Actions

    private func charger() {
        guard !champsCharges else { return }
        champsCharges = true
        guard let depense else { return }
        libelle = depense.libelle
        montant = depense.montant
        date = depense.date
        categorieID = depense.categorie?.id
        moyenPaiement = depense.moyenPaiement
        notes = depense.notes
    }

    private var categorieChoisie: Categorie? {
        categories.first { $0.id == categorieID }
    }

    private func enregistrer() {
        let titre = libelle.trimmingCharacters(in: .whitespaces)

        if let depense {
            depense.libelle = titre
            depense.montant = montant
            depense.date = date
            depense.categorie = categorieChoisie
            depense.moyenPaiement = moyenPaiement
            depense.notes = notes
        } else {
            let nouvelle = Depense(
                libelle: titre,
                montant: montant,
                date: date,
                categorie: categorieChoisie,
                moyenPaiement: moyenPaiement,
                notes: notes
            )
            contexte.insert(nouvelle)

            if rendreRecurrente {
                let planifiee = DepensePlanifiee(
                    libelle: titre,
                    montant: montant,
                    categorie: categorieChoisie,
                    frequence: frequence,
                    dateDebut: date,
                    jourDuMois: frequence.moisParPeriode > 0
                        ? Calendar.current.component(.day, from: date)
                        : nil,
                    moyenPaiement: moyenPaiement,
                    notes: notes
                )
                contexte.insert(planifiee)
            }
        }

        try? contexte.save()
        NotificationCenter.default.post(name: .donneesModifiees, object: nil)
        fermer()
    }

    private func supprimer() {
        if let depense {
            contexte.delete(depense)
            try? contexte.save()
            NotificationCenter.default.post(name: .donneesModifiees, object: nil)
        }
        fermer()
    }
}
