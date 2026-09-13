import Combine
import SwiftData
import SwiftUI

extension Notification.Name {
    /// Émise par les éditeurs après un enregistrement, pour recalculer les rappels.
    static let donneesModifiees = Notification.Name("monbudget.donneesModifiees")
}

enum Onglet: Hashable {
    case accueil
    case depenses
    case echeances
    case statistiques
    case reglages
}

struct VueRacine: View {
    @Environment(\.modelContext) private var contexte
    @Environment(\.scenePhase) private var phase

    @Query private var categories: [Categorie]
    @Query private var depenses: [Depense]
    @Query private var planifiees: [DepensePlanifiee]
    @Query private var sautees: [OccurrenceSautee]

    @StateObject private var reglages = Reglages.partages
    @State private var verrouillage = VerrouillageApp()
    @State private var onglet: Onglet = .accueil

    var body: some View {
        ZStack {
            TabView(selection: $onglet) {
                VueAccueil(reglages: reglages, onglet: $onglet)
                    .tabItem { Label("Accueil", systemImage: "house.fill") }
                    .tag(Onglet.accueil)

                VueDepenses(reglages: reglages)
                    .tabItem { Label("Dépenses", systemImage: "list.bullet") }
                    .tag(Onglet.depenses)

                VueEcheances(reglages: reglages)
                    .tabItem { Label("Prévues", systemImage: "calendar.badge.clock") }
                    .tag(Onglet.echeances)

                VueStatistiques(reglages: reglages)
                    .tabItem { Label("Statistiques", systemImage: "chart.pie.fill") }
                    .tag(Onglet.statistiques)

                VueReglages(reglages: reglages)
                    .tabItem { Label("Réglages", systemImage: "gearshape.fill") }
                    .tag(Onglet.reglages)
            }

            if reglages.verrouillageActif && !verrouillage.deverrouille {
                VueVerrouillage(verrouillage: verrouillage)
            }
        }
        .task { await demarrer() }
        .onChange(of: phase) { _, nouvellePhase in
            gererChangementDePhase(nouvellePhase)
        }
        .onChange(of: signatureDonnees) { _, _ in
            Task { await synchroniser() }
        }
        .onReceive(NotificationCenter.default.publisher(for: .donneesModifiees)) { _ in
            Task { await synchroniser() }
        }
        .onReceive(NotificationCenter.default.publisher(for: .ouvrirEcheances)) { _ in
            onglet = .echeances
        }
    }

    /// Change dès qu'une dépense ou une planification est ajoutée/supprimée.
    private var signatureDonnees: String {
        "\(depenses.count)-\(planifiees.count)-\(sautees.count)"
    }

    private func demarrer() async {
        if categories.isEmpty && !reglages.donneesInitialisees {
            Categorie.creerCategoriesParDefaut(dans: contexte)
            try? contexte.save()
            reglages.donneesInitialisees = true
        }

        ServiceNotifications.partage.installerDelegue()

        if reglages.verrouillageActif {
            await verrouillage.deverrouiller()
        }

        if reglages.notificationsActives {
            let statut = await ServiceNotifications.partage.statutAutorisation()
            if statut == .notDetermined {
                await ServiceNotifications.partage.demanderAutorisation()
            }
        }

        await synchroniser()
    }

    private func gererChangementDePhase(_ nouvellePhase: ScenePhase) {
        switch nouvellePhase {
        case .active:
            Task {
                if reglages.verrouillageActif && !verrouillage.deverrouille {
                    await verrouillage.deverrouiller()
                }
                await synchroniser()
            }
        case .background:
            if reglages.verrouillageActif {
                verrouillage.verrouiller()
            }
        default:
            break
        }
    }

    /// Reprogramme les rappels et vérifie le budget du mois.
    private func synchroniser() async {
        await ServiceNotifications.partage.reprogrammerTout(
            planifiees: planifiees,
            depenses: depenses,
            sautees: sautees,
            reglages: reglages
        )
        await SurveillanceBudget.verifier(depenses: depenses, reglages: reglages)
    }
}

/// Écran affiché tant que Face ID / le code n'a pas été validé.
struct VueVerrouillage: View {
    let verrouillage: VerrouillageApp

    var body: some View {
        ZStack {
            Rectangle()
                .fill(.ultraThickMaterial)
                .ignoresSafeArea()

            VStack(spacing: 18) {
                Image(systemName: "lock.fill")
                    .font(.system(size: 44))
                    .foregroundStyle(.tint)
                Text("MonBudget est verrouillé")
                    .font(.headline)
                if let message = verrouillage.messageErreur {
                    Text(message)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
                Button("Déverrouiller") {
                    Task { await verrouillage.deverrouiller() }
                }
                .buttonStyle(.borderedProminent)
            }
            .padding()
        }
    }
}
