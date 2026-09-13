import XCTest
@testable import MonBudget

final class MoteurRecurrenceTests: XCTestCase {

    private var calendrier: Calendar = {
        var calendrier = Calendar(identifier: .gregorian)
        calendrier.timeZone = TimeZone(identifier: "UTC")!
        calendrier.locale = Locale(identifier: "fr_FR")
        return calendrier
    }()

    private lazy var moteur = MoteurRecurrence(calendrier: calendrier)

    private func date(_ annee: Int, _ mois: Int, _ jour: Int) -> Date {
        calendrier.date(from: DateComponents(year: annee, month: mois, day: jour))!
    }

    // MARK: - Mensuel

    func testEcheanceMensuelleSimple() {
        let regle = RegleRecurrence(frequence: .mensuel, dateDebut: date(2026, 1, 5), jourDuMois: 5)

        XCTAssertEqual(moteur.occurrence(regle: regle, index: 0), date(2026, 1, 5))
        XCTAssertEqual(moteur.occurrence(regle: regle, index: 1), date(2026, 2, 5))
        XCTAssertEqual(moteur.occurrence(regle: regle, index: 12), date(2027, 1, 5))
    }

    func testJour31RameneAuDernierJourDeFevrier() {
        let regle = RegleRecurrence(frequence: .mensuel, dateDebut: date(2026, 1, 31), jourDuMois: 31)

        XCTAssertEqual(moteur.occurrence(regle: regle, index: 1), date(2026, 2, 28))
        XCTAssertEqual(moteur.occurrence(regle: regle, index: 2), date(2026, 3, 31))
        XCTAssertEqual(moteur.occurrence(regle: regle, index: 3), date(2026, 4, 30))
    }

    func testAnneeBissextile() {
        let regle = RegleRecurrence(frequence: .mensuel, dateDebut: date(2028, 1, 31), jourDuMois: 31)

        XCTAssertEqual(moteur.occurrence(regle: regle, index: 1), date(2028, 2, 29))
    }

    func testIntervalleDeDeuxMois() {
        let regle = RegleRecurrence(
            frequence: .mensuel,
            intervalle: 2,
            dateDebut: date(2026, 1, 10),
            jourDuMois: 10
        )

        XCTAssertEqual(moteur.occurrence(regle: regle, index: 1), date(2026, 3, 10))
        XCTAssertEqual(moteur.occurrence(regle: regle, index: 2), date(2026, 5, 10))
    }

    // MARK: - Autres fréquences

    func testFrequenceHebdomadaire() {
        let regle = RegleRecurrence(frequence: .hebdomadaire, dateDebut: date(2026, 9, 1))

        XCTAssertEqual(moteur.occurrence(regle: regle, index: 1), date(2026, 9, 8))
        XCTAssertEqual(moteur.occurrence(regle: regle, index: 4), date(2026, 9, 29))
    }

    func testFrequenceTrimestrielle() {
        let regle = RegleRecurrence(frequence: .trimestriel, dateDebut: date(2026, 1, 15), jourDuMois: 15)

        XCTAssertEqual(moteur.occurrence(regle: regle, index: 1), date(2026, 4, 15))
    }

    func testFrequenceUniqueNaQuUneEcheance() {
        let regle = RegleRecurrence(frequence: .unique, dateDebut: date(2026, 5, 20))

        XCTAssertEqual(moteur.occurrence(regle: regle, index: 0), date(2026, 5, 20))
        XCTAssertNil(moteur.occurrence(regle: regle, index: 1))
    }

    // MARK: - Fenêtres et bornes

    func testOccurrencesDansUnMois() {
        let regle = RegleRecurrence(frequence: .mensuel, dateDebut: date(2026, 1, 5), jourDuMois: 5)
        let mois = calendrier.intervalleDuMois(contenant: date(2026, 6, 15))

        let resultats = moteur.occurrences(regle: regle, dans: mois)

        XCTAssertEqual(resultats, [date(2026, 6, 5)])
    }

    func testOccurrencesHebdomadairesDansUnMois() {
        let regle = RegleRecurrence(frequence: .hebdomadaire, dateDebut: date(2026, 9, 3))
        let mois = calendrier.intervalleDuMois(contenant: date(2026, 9, 15))

        let resultats = moteur.occurrences(regle: regle, dans: mois)

        XCTAssertEqual(resultats, [date(2026, 9, 3), date(2026, 9, 10), date(2026, 9, 17), date(2026, 9, 24)])
    }

    func testDateDeFinArreteLaSerie() {
        let regle = RegleRecurrence(
            frequence: .mensuel,
            dateDebut: date(2026, 1, 10),
            dateFin: date(2026, 3, 31),
            jourDuMois: 10
        )
        let annee = DateInterval(start: date(2026, 1, 1), end: date(2026, 12, 31))

        let resultats = moteur.occurrences(regle: regle, dans: annee)

        XCTAssertEqual(resultats, [date(2026, 1, 10), date(2026, 2, 10), date(2026, 3, 10)])
    }

    func testEcheancesAvantLaDateDeDebutSontIgnorees() {
        // Début le 15 janvier mais paiement le 1er du mois : la première
        // échéance réelle est le 1er février.
        let regle = RegleRecurrence(frequence: .mensuel, dateDebut: date(2026, 1, 15), jourDuMois: 1)

        let prochaine = moteur.prochaineOccurrence(regle: regle, aPartirDe: date(2026, 1, 15))

        XCTAssertEqual(prochaine, date(2026, 2, 1))
    }

    func testProchaineOccurrenceIncluLeJourMeme() {
        let regle = RegleRecurrence(frequence: .mensuel, dateDebut: date(2026, 1, 5), jourDuMois: 5)

        let prochaine = moteur.prochaineOccurrence(regle: regle, aPartirDe: date(2026, 4, 5))

        XCTAssertEqual(prochaine, date(2026, 4, 5))
    }

    func testProchainesOccurrencesLimitees() {
        let regle = RegleRecurrence(frequence: .mensuel, dateDebut: date(2026, 1, 5), jourDuMois: 5)

        let resultats = moteur.prochainesOccurrences(regle: regle, aPartirDe: date(2026, 1, 1), nombre: 3)

        XCTAssertEqual(resultats, [date(2026, 1, 5), date(2026, 2, 5), date(2026, 3, 5)])
    }
}
