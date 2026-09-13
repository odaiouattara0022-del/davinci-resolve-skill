import XCTest
@testable import MonBudget

final class BudgetTests: XCTestCase {

    func testPalierAucunSansBudget() {
        XCTAssertEqual(SurveillanceBudget.palier(depense: 500, budget: 0, seuil: 0.8), .aucun)
    }

    func testPalierSousLeSeuil() {
        XCTAssertEqual(SurveillanceBudget.palier(depense: 500, budget: 1000, seuil: 0.8), .aucun)
    }

    func testPalierAtteint() {
        XCTAssertEqual(SurveillanceBudget.palier(depense: 800, budget: 1000, seuil: 0.8), .seuil)
    }

    func testPalierDepassement() {
        XCTAssertEqual(SurveillanceBudget.palier(depense: 1001, budget: 1000, seuil: 0.8), .depassement)
    }

    func testIntervalleDuMoisCouvreToutLeMois() {
        var calendrier = Calendar(identifier: .gregorian)
        calendrier.timeZone = TimeZone(identifier: "UTC")!
        let reference = calendrier.date(from: DateComponents(year: 2026, month: 2, day: 14))!

        let intervalle = calendrier.intervalleDuMois(contenant: reference)

        XCTAssertEqual(intervalle.start, calendrier.date(from: DateComponents(year: 2026, month: 2, day: 1)))
        XCTAssertTrue(intervalle.contains(calendrier.date(from: DateComponents(year: 2026, month: 2, day: 28))!))
        XCTAssertFalse(intervalle.contains(calendrier.date(from: DateComponents(year: 2026, month: 3, day: 1))!))
    }

    func testFormatteurEcheanceRelative() {
        var calendrier = Calendar(identifier: .gregorian)
        calendrier.timeZone = TimeZone(identifier: "UTC")!
        let aujourdHui = calendrier.date(from: DateComponents(year: 2026, month: 5, day: 10))!
        let dans3Jours = calendrier.date(from: DateComponents(year: 2026, month: 5, day: 13))!
        let hier = calendrier.date(from: DateComponents(year: 2026, month: 5, day: 9))!

        XCTAssertEqual(Formatteur.echeanceRelative(aujourdHui, reference: aujourdHui, calendrier: calendrier), "Aujourd'hui")
        XCTAssertEqual(Formatteur.echeanceRelative(dans3Jours, reference: aujourdHui, calendrier: calendrier), "Dans 3 jours")
        XCTAssertEqual(Formatteur.echeanceRelative(hier, reference: aujourdHui, calendrier: calendrier), "Hier")
    }
}
