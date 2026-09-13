import Foundation
import SwiftUI

extension Color {
    /// Crée une couleur à partir d'un code hexadécimal (« #4F7CFF »).
    init(hex: String) {
        let nettoye = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var valeur: UInt64 = 0
        Scanner(string: nettoye).scanHexInt64(&valeur)

        let rouge, vert, bleu: Double
        switch nettoye.count {
        case 6:
            rouge = Double((valeur & 0xFF0000) >> 16) / 255
            vert = Double((valeur & 0x00FF00) >> 8) / 255
            bleu = Double(valeur & 0x0000FF) / 255
        case 8:
            rouge = Double((valeur & 0xFF00_0000) >> 24) / 255
            vert = Double((valeur & 0x00FF_0000) >> 16) / 255
            bleu = Double((valeur & 0x0000_FF00) >> 8) / 255
        default:
            rouge = 0.31
            vert = 0.49
            bleu = 1.0
        }
        self.init(red: rouge, green: vert, blue: bleu)
    }

    /// Palette proposée à la création d'une catégorie.
    static let palette: [String] = [
        "#4F7CFF", "#34C759", "#FF9500", "#AF52DE", "#FF2D55",
        "#5AC8FA", "#FFCC00", "#FF6482", "#00C7BE", "#8E8E93",
    ]
}

extension Calendar {
    /// Intervalle couvrant le mois contenant `date`.
    func intervalleDuMois(contenant date: Date) -> DateInterval {
        let debut = self.date(from: dateComponents([.year, .month], from: date)) ?? startOfDay(for: date)
        let fin = self.date(byAdding: DateComponents(month: 1, day: -1), to: debut) ?? debut
        return DateInterval(start: startOfDay(for: debut), end: endOfDay(pour: fin))
    }

    /// Dernier instant du jour (23:59:59).
    func endOfDay(pour date: Date) -> Date {
        let lendemain = self.date(byAdding: .day, value: 1, to: startOfDay(for: date)) ?? date
        return lendemain.addingTimeInterval(-1)
    }

    /// Le mois décalé de `decalage` mois par rapport à `date`.
    func mois(decale decalage: Int, depuis date: Date) -> Date {
        self.date(byAdding: .month, value: decalage, to: date) ?? date
    }
}
