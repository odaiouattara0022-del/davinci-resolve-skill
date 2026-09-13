import SwiftUI
import UIKit

/// Grande carte chiffrée du tableau de bord.
struct CarteStat: View {
    let titre: String
    let valeur: String
    var detail: String?
    var symbole: String = "eurosign.circle"
    var couleur: Color = .accentColor

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Image(systemName: symbole)
                    .foregroundStyle(couleur)
                Text(titre)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Text(valeur)
                .font(.title2.weight(.semibold))
                .minimumScaleFactor(0.6)
                .lineLimit(1)
            if let detail {
                Text(detail)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 16))
    }
}

/// Barre de progression colorée (verte, orange puis rouge selon le remplissage).
struct BarreProgression: View {
    let progression: Double
    var couleur: Color?
    var hauteur: CGFloat = 10

    private var teinte: Color {
        if let couleur { return couleur }
        if progression >= 1 { return .red }
        if progression >= 0.8 { return .orange }
        return .green
    }

    var body: some View {
        GeometryReader { geometrie in
            ZStack(alignment: .leading) {
                Capsule()
                    .fill(Color(.systemGray5))
                Capsule()
                    .fill(teinte)
                    .frame(width: max(0, min(1, progression)) * geometrie.size.width)
            }
        }
        .frame(height: hauteur)
        .accessibilityLabel("Progression \(Int((progression * 100).rounded())) pour cent")
    }
}

/// Pastille emoji colorée d'une catégorie.
struct PastilleCategorie: View {
    let emoji: String
    let couleurHex: String
    var taille: CGFloat = 38

    var body: some View {
        Text(emoji)
            .font(.system(size: taille * 0.5))
            .frame(width: taille, height: taille)
            .background(Color(hex: couleurHex).opacity(0.18), in: Circle())
    }
}

/// Étiquette de statut d'une échéance.
struct EtiquetteStatut: View {
    let statut: StatutOccurrence

    private var couleur: Color {
        switch statut {
        case .payee: return .green
        case .sautee: return .gray
        case .enRetard: return .red
        case .aujourdHui: return .orange
        case .aVenir: return .blue
        }
    }

    var body: some View {
        Text(statut.libelle)
            .font(.caption2.weight(.semibold))
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(couleur.opacity(0.15), in: Capsule())
            .foregroundStyle(couleur)
    }
}

/// Sélecteur « ‹ septembre 2026 › ».
struct SelecteurMois: View {
    @Binding var mois: Date
    var calendrier: Calendar = .current

    var body: some View {
        HStack {
            Button {
                mois = calendrier.mois(decale: -1, depuis: mois)
            } label: {
                Image(systemName: "chevron.left")
            }
            .buttonStyle(.borderless)

            Spacer()
            Text(Formatteur.moisEtAnnee(mois).capitalizedPremiereLettre)
                .font(.headline)
            Spacer()

            Button {
                mois = calendrier.mois(decale: 1, depuis: mois)
            } label: {
                Image(systemName: "chevron.right")
            }
            .buttonStyle(.borderless)
        }
        .padding(.vertical, 4)
    }
}

/// Message affiché quand une liste est vide.
struct VueVide: View {
    let symbole: String
    let titre: String
    let message: String

    var body: some View {
        VStack(spacing: 10) {
            Image(systemName: symbole)
                .font(.largeTitle)
                .foregroundStyle(.secondary)
            Text(titre)
                .font(.headline)
            Text(message)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 28)
    }
}

/// Ligne d'une dépense dans une liste.
struct LigneDepense: View {
    let depense: Depense
    let devise: String

    var body: some View {
        HStack(spacing: 12) {
            PastilleCategorie(
                emoji: depense.categorie?.emoji ?? "💸",
                couleurHex: depense.categorie?.couleurHex ?? "#8E8E93"
            )
            VStack(alignment: .leading, spacing: 2) {
                Text(depense.libelle)
                    .font(.body)
                HStack(spacing: 6) {
                    Text(depense.categorie?.nom ?? "Sans catégorie")
                    Text("•")
                    Label(depense.moyenPaiement.libelle, systemImage: depense.moyenPaiement.symbole)
                        .labelStyle(.titleOnly)
                    if depense.vientDunePlanification {
                        Image(systemName: "repeat")
                    }
                }
                .font(.caption)
                .foregroundStyle(.secondary)
            }
            Spacer()
            Text(Formatteur.montant(depense.montant, devise: devise))
                .font(.body.weight(.medium))
                .monospacedDigit()
        }
    }
}

/// Ligne d'une échéance planifiée.
struct LigneOccurrence: View {
    let occurrence: Occurrence
    let devise: String

    var body: some View {
        HStack(spacing: 12) {
            PastilleCategorie(
                emoji: occurrence.planifiee.categorie?.emoji ?? "🗓",
                couleurHex: occurrence.planifiee.categorie?.couleurHex ?? "#4F7CFF"
            )
            VStack(alignment: .leading, spacing: 3) {
                Text(occurrence.libelle)
                    .font(.body)
                HStack(spacing: 6) {
                    Text(Formatteur.dateCourte(occurrence.date))
                    Text("•")
                    Text(Formatteur.echeanceRelative(occurrence.date))
                }
                .font(.caption)
                .foregroundStyle(.secondary)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 4) {
                Text(Formatteur.montant(occurrence.montant, devise: devise))
                    .font(.body.weight(.medium))
                    .monospacedDigit()
                EtiquetteStatut(statut: occurrence.statut)
            }
        }
    }
}
