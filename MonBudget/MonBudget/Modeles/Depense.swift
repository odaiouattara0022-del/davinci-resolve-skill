import Foundation
import SwiftData

/// Une dépense réellement effectuée.
///
/// Une dépense peut être ponctuelle (saisie à la main) ou provenir d'une
/// `DepensePlanifiee` : dans ce cas `origineID` pointe vers la planification et
/// `dateEcheance` mémorise l'échéance qui a été réglée.
@Model
final class Depense {
    var id: UUID = UUID()
    var libelle: String = ""
    var montant: Decimal = Decimal(0)
    var date: Date = Date()
    var notes: String = ""
    var moyenPaiementBrut: String = MoyenPaiement.carte.rawValue
    var origineID: UUID?
    var dateEcheance: Date?
    var creeLe: Date = Date()

    var categorie: Categorie?

    init(
        id: UUID = UUID(),
        libelle: String,
        montant: Decimal,
        date: Date = Date(),
        categorie: Categorie? = nil,
        moyenPaiement: MoyenPaiement = .carte,
        notes: String = "",
        origineID: UUID? = nil,
        dateEcheance: Date? = nil
    ) {
        self.id = id
        self.libelle = libelle
        self.montant = montant
        self.date = date
        self.categorie = categorie
        self.moyenPaiementBrut = moyenPaiement.rawValue
        self.notes = notes
        self.origineID = origineID
        self.dateEcheance = dateEcheance
        self.creeLe = Date()
    }

    var moyenPaiement: MoyenPaiement {
        get { MoyenPaiement(rawValue: moyenPaiementBrut) ?? .autre }
        set { moyenPaiementBrut = newValue.rawValue }
    }

    /// `true` si la dépense a été créée en réglant une échéance planifiée.
    var vientDunePlanification: Bool { origineID != nil }
}

enum MoyenPaiement: String, CaseIterable, Identifiable, Codable {
    case carte
    case especes
    case mobileMoney
    case virement
    case prelevement
    case cheque
    case autre

    var id: String { rawValue }

    var libelle: String {
        switch self {
        case .carte: return "Carte"
        case .especes: return "Espèces"
        case .mobileMoney: return "Mobile Money"
        case .virement: return "Virement"
        case .prelevement: return "Prélèvement"
        case .cheque: return "Chèque"
        case .autre: return "Autre"
        }
    }

    var symbole: String {
        switch self {
        case .carte: return "creditcard"
        case .especes: return "banknote"
        case .mobileMoney: return "iphone.radiowaves.left.and.right"
        case .virement: return "arrow.left.arrow.right"
        case .prelevement: return "arrow.down.circle"
        case .cheque: return "doc.text"
        case .autre: return "ellipsis.circle"
        }
    }
}
