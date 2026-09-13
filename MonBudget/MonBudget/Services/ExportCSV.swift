import Foundation

/// Export des dépenses au format CSV (ouvrable dans Excel / Numbers / Sheets).
enum ExportCSV {
    static func contenu(depenses: [Depense], devise: String) -> String {
        let entete = "Date;Libellé;Catégorie;Montant;Devise;Moyen de paiement;Origine;Notes"
        let formatDate = Date.FormatStyle(date: .numeric).locale(Formatteur.locale)

        let lignes = depenses
            .sorted { $0.date > $1.date }
            .map { depense -> String in
                let champs = [
                    depense.date.formatted(formatDate),
                    depense.libelle,
                    depense.categorie?.nom ?? "",
                    montantBrut(depense.montant),
                    devise,
                    depense.moyenPaiement.libelle,
                    depense.vientDunePlanification ? "Planifiée" : "Ponctuelle",
                    depense.notes,
                ]
                return champs.map(echapper).joined(separator: ";")
            }

        return ([entete] + lignes).joined(separator: "\n")
    }

    /// Écrit le CSV dans un fichier temporaire et renvoie son URL (pour `ShareLink`).
    static func fichier(depenses: [Depense], devise: String) throws -> URL {
        let nom = "depenses-\(Date().formatted(Date.ISO8601FormatStyle(dateSeparator: .dash).year().month().day())).csv"
        let url = FileManager.default.temporaryDirectory.appendingPathComponent(nom)
        let texte = contenu(depenses: depenses, devise: devise)
        // BOM UTF-8 : Excel ouvre alors correctement les accents.
        let donnees = "\u{FEFF}".data(using: .utf8)! + Data(texte.utf8)
        try donnees.write(to: url, options: .atomic)
        return url
    }

    private static func montantBrut(_ montant: Decimal) -> String {
        montant.formatted(
            .number.locale(Formatteur.locale).grouping(.never).precision(.fractionLength(0...2))
        )
    }

    private static func echapper(_ champ: String) -> String {
        guard champ.contains(";") || champ.contains("\"") || champ.contains("\n") else { return champ }
        return "\"" + champ.replacingOccurrences(of: "\"", with: "\"\"") + "\""
    }
}
