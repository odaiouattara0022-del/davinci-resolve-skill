import SwiftUI
import SwiftData

/// Confirmation du règlement d'une échéance : le montant réel peut différer de
/// l'estimation (facture d'eau, d'électricité…).
struct FeuillePaiement: View {
    let occurrence: Occurrence
    let reglages: Reglages

    @Environment(\.modelContext) private var contexte
    @Environment(\.dismiss) private var fermer

    @State private var montant: Decimal
    @State private var datePaiement: Date

    init(occurrence: Occurrence, reglages: Reglages) {
        self.occurrence = occurrence
        self.reglages = reglages
        _montant = State(initialValue: occurrence.montant)
        _datePaiement = State(initialValue: occurrence.date)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    LabeledContent("Dépense", value: occurrence.libelle)
                    LabeledContent("Échéance", value: Formatteur.dateLongue(occurrence.date))
                    if let categorie = occurrence.planifiee.categorie {
                        LabeledContent("Catégorie", value: "\(categorie.emoji) \(categorie.nom)")
                    }
                }

                Section("Montant réellement payé") {
                    HStack {
                        TextField("Montant", value: $montant, format: .number)
                            .keyboardType(.decimalPad)
                        Text(reglages.devise)
                            .foregroundStyle(.secondary)
                    }
                    DatePicker("Payé le", selection: $datePaiement, displayedComponents: .date)
                }

                Section {
                    Button {
                        confirmer()
                    } label: {
                        Label("Confirmer le paiement", systemImage: "checkmark.circle.fill")
                    }
                    .disabled(montant <= 0)

                    Button(role: .destructive) {
                        ignorer()
                    } label: {
                        Label("Ignorer cette échéance", systemImage: "xmark.circle")
                    }
                } footer: {
                    Text("« Ignorer » masque l'échéance de ce mois sans supprimer la dépense prévue.")
                }
            }
            .navigationTitle("Régler l'échéance")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Annuler") { fermer() }
                }
            }
        }
    }

    private func confirmer() {
        GestionnaireEcheances.marquerPayee(
            occurrence,
            montantReel: montant,
            datePaiement: datePaiement,
            contexte: contexte
        )
        try? contexte.save()
        NotificationCenter.default.post(name: .donneesModifiees, object: nil)
        fermer()
    }

    private func ignorer() {
        GestionnaireEcheances.ignorer(occurrence, contexte: contexte)
        try? contexte.save()
        NotificationCenter.default.post(name: .donneesModifiees, object: nil)
        fermer()
    }
}
