import Foundation

/// Formatage des montants et des dates, en français.
enum Formatteur {
    static let locale = Locale(identifier: "fr_FR")

    static func montant(_ valeur: Decimal, devise: String) -> String {
        valeur.formatted(.currency(code: devise).locale(locale))
    }

    /// Montant sans décimales, pour les grands nombres des graphiques.
    static func montantCompact(_ valeur: Decimal, devise: String) -> String {
        valeur.formatted(.currency(code: devise).locale(locale).precision(.fractionLength(0)))
    }

    static func dateCourte(_ date: Date) -> String {
        date.formatted(Date.FormatStyle(date: .abbreviated).locale(locale))
    }

    static func dateLongue(_ date: Date) -> String {
        date.formatted(Date.FormatStyle(date: .long).locale(locale))
    }

    /// « septembre 2026 »
    static func moisEtAnnee(_ date: Date) -> String {
        date.formatted(
            Date.FormatStyle()
                .locale(locale)
                .month(.wide)
                .year()
        )
    }

    /// « sept. » — libellé court pour les graphiques.
    static func moisAbrege(_ date: Date) -> String {
        date.formatted(Date.FormatStyle().locale(locale).month(.abbreviated))
    }

    /// « Aujourd'hui », « Demain », « Dans 5 jours », « Il y a 3 jours ».
    static func echeanceRelative(_ date: Date, reference: Date = Date(), calendrier: Calendar = .current) -> String {
        let jours = calendrier.dateComponents(
            [.day],
            from: calendrier.startOfDay(for: reference),
            to: calendrier.startOfDay(for: date)
        ).day ?? 0

        switch jours {
        case 0: return "Aujourd'hui"
        case 1: return "Demain"
        case 2...: return "Dans \(jours) jours"
        case -1: return "Hier"
        default: return "Il y a \(abs(jours)) jours"
        }
    }

    /// Titre d'une section de liste : « Aujourd'hui », « Hier », puis la date.
    static func titreJour(_ date: Date, reference: Date = Date(), calendrier: Calendar = .current) -> String {
        if calendrier.isDate(date, inSameDayAs: reference) { return "Aujourd'hui" }
        if let hier = calendrier.date(byAdding: .day, value: -1, to: reference),
           calendrier.isDate(date, inSameDayAs: hier) {
            return "Hier"
        }
        return date.formatted(Date.FormatStyle(date: .complete).locale(locale)).capitalizedPremiereLettre
    }
}

extension String {
    var capitalizedPremiereLettre: String {
        guard let premiere = first else { return self }
        return String(premiere).uppercased() + dropFirst()
    }
}

extension Decimal {
    var enDouble: Double {
        NSDecimalNumber(decimal: self).doubleValue
    }
}
