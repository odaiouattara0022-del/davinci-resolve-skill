import SwiftUI
import SwiftData

/// Création / modification d'une dépense prévue (récurrente ou ponctuelle future).
struct EditeurPlanifiee: View {
    let reglages: Reglages
    var planifiee: DepensePlanifiee?

    @Environment(\.modelContext) private var contexte
    @Environment(\.dismiss) private var fermer
    @Query(sort: \Categorie.ordre) private var categories: [Categorie]

    @State private var libelle = ""
    @State private var montant: Decimal = 0
    @State private var montantEstime = false
    @State private var categorieID: UUID?
    @State private var frequence: Frequence = .mensuel
    @State private var intervalle = 1
    @State private var dateDebut = Date()
    @State private var utiliseDateFin = false
    @State private var dateFin = Date()
    @State private var jourDuMois = Calendar.current.component(.day, from: Date())
    @State private var moyenPaiement: MoyenPaiement = .prelevement
    @State private var rappelJoursAvant = 2
    @State private var rappelHeure = 9
    @State private var rappelJourJ = true
    @State private var notes = ""
    @State private var actif = true
    @State private var afficheSuppression = false
    @State private var champsCharges = false

    private var modeEdition: Bool { planifiee != nil }
    private var utiliseJourDuMois: Bool { frequence.moisParPeriode > 0 }

    var body: some View {
        NavigationStack {
            Form {
                Section("Dépense prévue") {
                    TextField("Libellé (loyer, internet, scolarité…)", text: $libelle)
                    HStack {
                        TextField("Montant", value: $montant, format: .number)
                            .keyboardType(.decimalPad)
                        Text(reglages.devise)
                            .foregroundStyle(.secondary)
                    }
                    Toggle("Montant variable (estimation)", isOn: $montantEstime)
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

                Section("Répétition") {
                    Picker("Fréquence", selection: $frequence) {
                        ForEach(Frequence.allCases) { valeur in
                            Text(valeur.libelle).tag(valeur)
                        }
                    }
                    if frequence != .unique {
                        Stepper(value: $intervalle, in: 1...12) {
                            Text(frequence.libelle(intervalle: intervalle))
                                .font(.callout)
                        }
                    }
                    DatePicker("Première échéance", selection: $dateDebut, displayedComponents: .date)
                    if utiliseJourDuMois {
                        Picker("Jour du mois", selection: $jourDuMois) {
                            ForEach(1...31, id: \.self) { jour in
                                Text("Le \(jour)").tag(jour)
                            }
                        }
                    }
                    Toggle("Date de fin", isOn: $utiliseDateFin)
                    if utiliseDateFin {
                        DatePicker("Jusqu'au", selection: $dateFin, displayedComponents: .date)
                    }
                }

                Section("Rappels") {
                    Picker("Prévenir", selection: $rappelJoursAvant) {
                        Text("Le jour même").tag(0)
                        Text("1 jour avant").tag(1)
                        Text("2 jours avant").tag(2)
                        Text("3 jours avant").tag(3)
                        Text("5 jours avant").tag(5)
                        Text("1 semaine avant").tag(7)
                    }
                    Picker("À quelle heure", selection: $rappelHeure) {
                        ForEach(6...22, id: \.self) { heure in
                            Text("\(heure) h").tag(heure)
                        }
                    }
                    Toggle("Rappel le jour de l'échéance", isOn: $rappelJourJ)
                }

                if !apercu.isEmpty {
                    Section("Prochaines échéances") {
                        ForEach(apercu, id: \.self) { date in
                            HStack {
                                Text(Formatteur.dateLongue(date).capitalizedPremiereLettre)
                                Spacer()
                                Text(Formatteur.echeanceRelative(date))
                                    .foregroundStyle(.secondary)
                            }
                            .font(.callout)
                        }
                    }
                }

                Section("Notes") {
                    TextField("Facultatif", text: $notes, axis: .vertical)
                        .lineLimit(2...5)
                }

                if modeEdition {
                    Section {
                        Toggle("Active", isOn: $actif)
                        Button("Supprimer cette dépense prévue", role: .destructive) {
                            afficheSuppression = true
                        }
                    }
                }
            }
            .navigationTitle(modeEdition ? "Modifier" : "Dépense prévue")
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
            .confirmationDialog(
                "Supprimer cette dépense prévue ?",
                isPresented: $afficheSuppression,
                titleVisibility: .visible
            ) {
                Button("Supprimer, garder l'historique", role: .destructive) {
                    supprimer(avecHistorique: false)
                }
                Button("Supprimer, y compris les paiements", role: .destructive) {
                    supprimer(avecHistorique: true)
                }
                Button("Annuler", role: .cancel) {}
            }
        }
    }

    // MARK: - Aperçu

    private var regleCourante: RegleRecurrence {
        RegleRecurrence(
            frequence: frequence,
            intervalle: intervalle,
            dateDebut: dateDebut,
            dateFin: utiliseDateFin ? dateFin : nil,
            jourDuMois: utiliseJourDuMois ? jourDuMois : nil
        )
    }

    private var apercu: [Date] {
        MoteurRecurrence().prochainesOccurrences(regle: regleCourante, aPartirDe: Date(), nombre: 3)
    }

    // MARK: - Actions

    private func charger() {
        guard !champsCharges else { return }
        champsCharges = true
        guard let planifiee else { return }
        libelle = planifiee.libelle
        montant = planifiee.montant
        montantEstime = planifiee.montantEstime
        categorieID = planifiee.categorie?.id
        frequence = planifiee.frequence
        intervalle = planifiee.intervalle
        dateDebut = planifiee.dateDebut
        if let fin = planifiee.dateFin {
            utiliseDateFin = true
            dateFin = fin
        }
        jourDuMois = planifiee.jourDuMois ?? Calendar.current.component(.day, from: planifiee.dateDebut)
        moyenPaiement = planifiee.moyenPaiement
        rappelJoursAvant = planifiee.rappelJoursAvant
        rappelHeure = planifiee.rappelHeure
        rappelJourJ = planifiee.rappelJourJ
        notes = planifiee.notes
        actif = planifiee.actif
    }

    private var categorieChoisie: Categorie? {
        categories.first { $0.id == categorieID }
    }

    private func enregistrer() {
        let titre = libelle.trimmingCharacters(in: .whitespaces)
        let cible = planifiee ?? DepensePlanifiee(libelle: titre, montant: montant)

        cible.libelle = titre
        cible.montant = montant
        cible.montantEstime = montantEstime
        cible.categorie = categorieChoisie
        cible.frequence = frequence
        cible.intervalle = intervalle
        cible.dateDebut = dateDebut
        cible.dateFin = utiliseDateFin ? dateFin : nil
        cible.jourDuMois = utiliseJourDuMois ? jourDuMois : nil
        cible.moyenPaiement = moyenPaiement
        cible.rappelJoursAvant = rappelJoursAvant
        cible.rappelHeure = rappelHeure
        cible.rappelJourJ = rappelJourJ
        cible.notes = notes
        cible.actif = actif

        if planifiee == nil {
            contexte.insert(cible)
        }

        try? contexte.save()
        NotificationCenter.default.post(name: .donneesModifiees, object: nil)
        fermer()
    }

    private func supprimer(avecHistorique: Bool) {
        guard let planifiee else { return }
        GestionnaireEcheances.supprimer(planifiee, supprimerHistorique: avecHistorique, contexte: contexte)
        try? contexte.save()
        NotificationCenter.default.post(name: .donneesModifiees, object: nil)
        fermer()
    }
}
