import Charts
import SwiftData
import SwiftUI

/// Analyse des dépenses : répartition par catégorie et évolution sur 6 mois.
struct VueStatistiques: View {
    @ObservedObject var reglages: Reglages

    @Query(sort: \Depense.date, order: .reverse) private var depenses: [Depense]
    @State private var mois = Date()

    private let calendrier = Calendar.current

    var body: some View {
        NavigationStack {
            List {
                Section {
                    SelecteurMois(mois: $mois)
                    HStack {
                        Text("Total du mois")
                        Spacer()
                        Text(Formatteur.montant(totalDuMois, devise: reglages.devise))
                            .font(.headline)
                            .monospacedDigit()
                    }
                }

                if totauxParCategorie.isEmpty {
                    Section {
                        VueVide(
                            symbole: "chart.pie",
                            titre: "Pas encore de statistiques",
                            message: "Enregistrez quelques dépenses pour voir où part votre argent."
                        )
                    }
                } else {
                    Section("Répartition par catégorie") {
                        Chart(totauxParCategorie) { ligne in
                            SectorMark(
                                angle: .value("Montant", ligne.total.enDouble),
                                innerRadius: .ratio(0.58),
                                angularInset: 1.5
                            )
                            .cornerRadius(4)
                            .foregroundStyle(Color(hex: ligne.couleurHex))
                        }
                        .frame(height: 200)
                        .padding(.vertical, 6)

                        ForEach(totauxParCategorie) { ligne in
                            LigneCategorieStat(
                                ligne: ligne,
                                total: totalDuMois,
                                devise: reglages.devise
                            )
                        }
                    }

                    Section("Évolution sur 6 mois") {
                        Chart(historique) { point in
                            BarMark(
                                x: .value("Mois", Formatteur.moisAbrege(point.debut)),
                                y: .value("Dépenses", point.total.enDouble)
                            )
                            .foregroundStyle(
                                calendrier.isDate(point.debut, equalTo: mois, toGranularity: .month)
                                    ? Color.accentColor
                                    : Color.accentColor.opacity(0.35)
                            )
                            .cornerRadius(5)
                        }
                        .frame(height: 180)
                        .padding(.vertical, 6)

                        HStack {
                            Text("Moyenne mensuelle")
                            Spacer()
                            Text(Formatteur.montant(moyenneMensuelle, devise: reglages.devise))
                                .foregroundStyle(.secondary)
                                .monospacedDigit()
                        }
                        .font(.callout)
                    }

                    Section("Plus grosses dépenses du mois") {
                        ForEach(plusGrossesDepenses) { depense in
                            LigneDepense(depense: depense, devise: reglages.devise)
                        }
                    }
                }
            }
            .navigationTitle("Statistiques")
        }
    }

    // MARK: - Calculs

    private var intervalleDuMois: DateInterval {
        calendrier.intervalleDuMois(contenant: mois)
    }

    private var depensesDuMois: [Depense] {
        depenses.filter { intervalleDuMois.contains($0.date) }
    }

    private var totalDuMois: Decimal {
        CalculateurBudget.total(depensesDuMois)
    }

    private var totauxParCategorie: [TotalCategorie] {
        CalculateurBudget.totauxParCategorie(depensesDuMois)
    }

    private var plusGrossesDepenses: [Depense] {
        Array(depensesDuMois.sorted { $0.montant > $1.montant }.prefix(5))
    }

    private var historique: [PointMensuel] {
        (0..<6).reversed().map { decalage in
            let moisCible = calendrier.mois(decale: -decalage, depuis: mois)
            let intervalle = calendrier.intervalleDuMois(contenant: moisCible)
            return PointMensuel(
                debut: intervalle.start,
                total: CalculateurBudget.total(depenses, dans: intervalle)
            )
        }
    }

    private var moyenneMensuelle: Decimal {
        let totaux = historique.map(\.total)
        let moisRenseignes = totaux.filter { $0 > 0 }
        guard !moisRenseignes.isEmpty else { return 0 }
        let somme = moisRenseignes.reduce(Decimal(0), +)
        return somme / Decimal(moisRenseignes.count)
    }
}

/// Total d'un mois, pour le graphique d'évolution.
struct PointMensuel: Identifiable {
    let debut: Date
    let total: Decimal
    var id: Date { debut }
}

/// Ligne détaillant une catégorie : part du total et respect du plafond.
struct LigneCategorieStat: View {
    let ligne: TotalCategorie
    let total: Decimal
    let devise: String

    private var part: Double {
        guard total > 0 else { return 0 }
        return ligne.total.enDouble / total.enDouble
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("\(ligne.emoji)  \(ligne.nom)")
                Spacer()
                Text(Formatteur.montant(ligne.total, devise: devise))
                    .monospacedDigit()
            }
            .font(.callout)

            BarreProgression(progression: part, couleur: Color(hex: ligne.couleurHex), hauteur: 6)

            HStack {
                Text("\(Int((part * 100).rounded())) % des dépenses")
                Spacer()
                if let plafond = ligne.plafond, plafond > 0 {
                    let depassement = ligne.total > plafond
                    Text(depassement
                         ? "Plafond dépassé (\(Formatteur.montant(plafond, devise: devise)))"
                         : "Plafond : \(Formatteur.montant(plafond, devise: devise))")
                        .foregroundStyle(depassement ? Color.red : Color.secondary)
                }
            }
            .font(.caption2)
            .foregroundStyle(.secondary)
        }
        .padding(.vertical, 2)
    }
}
