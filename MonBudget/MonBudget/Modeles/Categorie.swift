import Foundation
import SwiftData

/// Catégorie de dépense (Logement, Transport, Alimentation…).
///
/// `plafondMensuel` permet de fixer une enveloppe par catégorie : l'application
/// prévient quand le seuil d'alerte est franchi.
@Model
final class Categorie {
    var id: UUID = UUID()
    var nom: String = ""
    var emoji: String = "💸"
    var couleurHex: String = "#4F7CFF"
    var plafondMensuel: Decimal?
    var ordre: Int = 0

    @Relationship(deleteRule: .nullify, inverse: \Depense.categorie)
    var depenses: [Depense] = []

    @Relationship(deleteRule: .nullify, inverse: \DepensePlanifiee.categorie)
    var planifiees: [DepensePlanifiee] = []

    init(
        id: UUID = UUID(),
        nom: String,
        emoji: String = "💸",
        couleurHex: String = "#4F7CFF",
        plafondMensuel: Decimal? = nil,
        ordre: Int = 0
    ) {
        self.id = id
        self.nom = nom
        self.emoji = emoji
        self.couleurHex = couleurHex
        self.plafondMensuel = plafondMensuel
        self.ordre = ordre
    }
}

extension Categorie {
    /// Jeu de catégories créé au premier lancement.
    static let modelesParDefaut: [(nom: String, emoji: String, couleur: String)] = [
        ("Logement", "🏠", "#4F7CFF"),
        ("Alimentation", "🛒", "#34C759"),
        ("Transport", "🚌", "#FF9500"),
        ("Factures & abonnements", "🧾", "#AF52DE"),
        ("Santé", "💊", "#FF2D55"),
        ("Éducation", "🎓", "#5AC8FA"),
        ("Famille", "👨‍👩‍👧", "#FFCC00"),
        ("Loisirs", "🎬", "#FF6482"),
        ("Épargne", "🐖", "#00C7BE"),
        ("Divers", "💸", "#8E8E93"),
    ]

    static func creerCategoriesParDefaut(dans contexte: ModelContext) {
        for (index, modele) in modelesParDefaut.enumerated() {
            let categorie = Categorie(
                nom: modele.nom,
                emoji: modele.emoji,
                couleurHex: modele.couleur,
                ordre: index
            )
            contexte.insert(categorie)
        }
    }
}
