import SwiftData
import SwiftUI

@main
struct MonBudgetApp: App {
    private let conteneur: ModelContainer

    init() {
        let schema = Schema([
            Depense.self,
            DepensePlanifiee.self,
            Categorie.self,
            OccurrenceSautee.self,
        ])
        let configuration = ModelConfiguration(schema: schema, isStoredInMemoryOnly: false)
        do {
            conteneur = try ModelContainer(for: schema, configurations: [configuration])
        } catch {
            // En cas de schéma incompatible, on repart d'une base en mémoire
            // plutôt que de planter au lancement.
            let secours = ModelConfiguration(schema: schema, isStoredInMemoryOnly: true)
            conteneur = try! ModelContainer(for: schema, configurations: [secours])
        }
    }

    var body: some Scene {
        WindowGroup {
            VueRacine()
        }
        .modelContainer(conteneur)
    }
}
