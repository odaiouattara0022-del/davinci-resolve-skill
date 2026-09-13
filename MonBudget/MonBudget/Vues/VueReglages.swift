import SwiftData
import SwiftUI
import UIKit

/// Réglages : devise, budget, rappels, sécurité, export.
struct VueReglages: View {
    @ObservedObject var reglages: Reglages

    @Environment(\.modelContext) private var contexte
    @Query private var depenses: [Depense]
    @Query private var categories: [Categorie]

    @State private var budgetSaisi: Double = 0
    @State private var fichierAPartager: FichierPartage?
    @State private var afficheReinitialisation = false
    @State private var autorisationRefusee = false
    @State private var champsCharges = false

    var body: some View {
        NavigationStack {
            Form {
                Section("Argent") {
                    Picker("Devise", selection: Binding(
                        get: { reglages.devise },
                        set: { reglages.devise = $0 }
                    )) {
                        ForEach(devisesDisponibles, id: \.self) { code in
                            Text(code).tag(code)
                        }
                    }

                    HStack {
                        Text("Budget mensuel")
                        Spacer()
                        TextField("0", value: $budgetSaisi, format: .number)
                            .keyboardType(.decimalPad)
                            .multilineTextAlignment(.trailing)
                            .frame(maxWidth: 140)
                            .onChange(of: budgetSaisi) { _, nouveau in
                                reglages.budgetMensuel = max(0, nouveau)
                            }
                        Text(reglages.devise)
                            .foregroundStyle(.secondary)
                    }
                }

                Section {
                    Toggle("Rappels d'échéance", isOn: Binding(
                        get: { reglages.notificationsActives },
                        set: { nouvelle in
                            reglages.notificationsActives = nouvelle
                            Task { await gererAutorisation(nouvelle) }
                        }
                    ))
                    Toggle("Rappel au début du mois", isOn: Binding(
                        get: { reglages.resumeMensuelActif },
                        set: { reglages.resumeMensuelActif = $0; signaler() }
                    ))
                    Toggle("Alerte de dépassement de budget", isOn: Binding(
                        get: { reglages.alerteBudgetActive },
                        set: { reglages.alerteBudgetActive = $0 }
                    ))
                    Picker("Prévenir à partir de", selection: Binding(
                        get: { reglages.seuilAlerte },
                        set: { reglages.seuilAlerte = $0 }
                    )) {
                        Text("50 % du budget").tag(0.5)
                        Text("70 % du budget").tag(0.7)
                        Text("80 % du budget").tag(0.8)
                        Text("90 % du budget").tag(0.9)
                        Text("100 % du budget").tag(1.0)
                    }
                } header: {
                    Text("Notifications")
                } footer: {
                    if autorisationRefusee {
                        VStack(alignment: .leading, spacing: 6) {
                            Text("Les notifications sont désactivées pour MonBudget dans iOS.")
                            Button("Ouvrir les réglages de l'iPhone") {
                                if let url = URL(string: UIApplication.openSettingsURLString) {
                                    UIApplication.shared.open(url)
                                }
                            }
                            .font(.footnote)
                        }
                    } else {
                        Text("Chaque dépense prévue possède son propre délai de rappel, réglable dans sa fiche.")
                    }
                }

                Section("Organisation") {
                    NavigationLink {
                        VueCategories(reglages: reglages)
                    } label: {
                        Label("Catégories (\(categories.count))", systemImage: "square.grid.2x2")
                    }
                }

                Section("Sécurité") {
                    Toggle("Verrouiller avec Face ID / code", isOn: Binding(
                        get: { reglages.verrouillageActif },
                        set: { reglages.verrouillageActif = $0 }
                    ))
                    .disabled(!VerrouillageApp.biometrieDisponible)
                }

                Section("Données") {
                    Button {
                        exporter()
                    } label: {
                        Label("Exporter mes dépenses (CSV)", systemImage: "square.and.arrow.up")
                    }
                    .disabled(depenses.isEmpty)

                    Button {
                        DonneesDemo.installer(dans: contexte)
                        try? contexte.save()
                        signaler()
                    } label: {
                        Label("Charger des données d'exemple", systemImage: "wand.and.stars")
                    }

                    Button(role: .destructive) {
                        afficheReinitialisation = true
                    } label: {
                        Label("Tout effacer", systemImage: "trash")
                    }
                }

                Section {
                    LabeledContent("Version", value: version)
                } footer: {
                    Text("Vos données restent sur votre iPhone : aucune information n'est envoyée sur Internet.")
                }
            }
            .navigationTitle("Réglages")
            .onAppear(perform: charger)
            .task { await verifierAutorisation() }
            .sheet(item: $fichierAPartager) { fichier in
                VuePartage(elements: [fichier.url])
            }
            .confirmationDialog(
                "Effacer toutes les données ?",
                isPresented: $afficheReinitialisation,
                titleVisibility: .visible
            ) {
                Button("Tout effacer", role: .destructive, action: toutEffacer)
                Button("Annuler", role: .cancel) {}
            } message: {
                Text("Dépenses, dépenses prévues et catégories seront supprimées. Cette action est définitive.")
            }
        }
    }

    // MARK: - Actions

    private var devisesDisponibles: [String] {
        var codes = Reglages.devisesProposees
        if !codes.contains(reglages.devise) { codes.insert(reglages.devise, at: 0) }
        return codes
    }

    private var version: String {
        let numero = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0"
        return numero
    }

    private func charger() {
        guard !champsCharges else { return }
        champsCharges = true
        budgetSaisi = reglages.budgetMensuel
    }

    private func verifierAutorisation() async {
        let statut = await ServiceNotifications.partage.statutAutorisation()
        autorisationRefusee = (statut == .denied)
    }

    private func gererAutorisation(_ active: Bool) async {
        if active {
            let statut = await ServiceNotifications.partage.statutAutorisation()
            if statut == .notDetermined {
                await ServiceNotifications.partage.demanderAutorisation()
            }
            await verifierAutorisation()
        } else {
            ServiceNotifications.partage.toutAnnuler()
        }
        signaler()
    }

    private func exporter() {
        do {
            let url = try ExportCSV.fichier(depenses: depenses, devise: reglages.devise)
            fichierAPartager = FichierPartage(url: url)
        } catch {
            fichierAPartager = nil
        }
    }

    private func toutEffacer() {
        DonneesDemo.toutEffacer(dans: contexte)
        try? contexte.save()
        Categorie.creerCategoriesParDefaut(dans: contexte)
        try? contexte.save()
        ServiceNotifications.partage.toutAnnuler()
        signaler()
    }

    private func signaler() {
        NotificationCenter.default.post(name: .donneesModifiees, object: nil)
    }
}

/// Fichier temporaire à partager (CSV).
struct FichierPartage: Identifiable {
    let url: URL
    var id: String { url.absoluteString }
}

/// Feuille de partage iOS.
struct VuePartage: UIViewControllerRepresentable {
    let elements: [Any]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: elements, applicationActivities: nil)
    }

    func updateUIViewController(_ controller: UIActivityViewController, context: Context) {}
}
