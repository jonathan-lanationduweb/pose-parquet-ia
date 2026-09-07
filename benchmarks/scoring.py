"""Comptage : vrais positifs, vrais négatifs, **faux positifs**, faux négatifs.

## Le défaut du LOT 0 que ce module corrige

Le banc d'essai du LOT 0 ne comptait que les défauts **manqués**
(`missed_issues`). Il rapportait fièrement `withMissedIssues: 0`, et ce chiffre
était vrai. Il était aussi trompeur : un détecteur qui déclare *tous* les
défauts sur *toutes* les photos n'en manque aucun. Ne compter que les manques
récompense donc la sur-détection, exactement le comportement qui rendrait le
service inutilisable — un utilisateur à qui l'on annonce cinq problèmes sur
une photo correcte cesse de lire les avertissements.

D'où la règle : **aucun chiffre de rappel n'est publié sans son faux positif.**

## Comment la matrice est définie

Les étiquettes sont `warnings.SCORED` : les codes que le pipeline sait émettre
et qui affirment quelque chose sur la photo. Pour chaque image :

* **TP** — attendu et détecté ;
* **FN** — attendu, non détecté ;
* **FP** — détecté, non attendu ;
* **TN** — ni attendu ni détecté, parmi les étiquettes possibles.

`TN` a donc un dénominateur explicite, et c'est ce qui le rend lisible : neuf
étiquettes possibles, pas « tous les codes du projet ». Un `TN` calculé sur un
vocabulaire qui grandit à chaque lot gonflerait tout seul.

## Ce qui n'entre pas dans la matrice

Les codes `warnings.INFORMATIONAL`, et notamment
`lens_analysis_undetermined` : c'est un aveu d'ignorance, pas une affirmation.
Il est **compté à part**, dans `undetermined`. Le mettre en faux positif
punirait l'honnêteté ; le mettre en vrai positif récompenserait un détecteur
qui ne répondrait jamais rien.

Les entrées `graded=False` du corpus n'entrent pas non plus : leur bonne
réponse est discutable, et les compter reviendrait à inventer une vérité.
Elles sont mesurées et rapportées, hors comptage.

## Sur le mot « exactitude »

Ce module n'en calcule aucune, et c'est délibéré. Sur un problème multi-label
où la plupart des étiquettes sont négatives, un taux de bonnes réponses est
dominé par les vrais négatifs et flatte n'importe quel détecteur muet. Les
chiffres publiés sont donc les **comptes bruts**, plus deux taux dont la
définition est écrite dans la sortie elle-même.
"""

from dataclasses import dataclass, field

from app.core.warnings import SCORED, Warn


@dataclass(frozen=True, slots=True)
class LabelScore:
    """Matrice de confusion d'une étiquette."""

    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0
    true_negative: int = 0

    def plus(self, other: "LabelScore") -> "LabelScore":
        return LabelScore(
            self.true_positive + other.true_positive,
            self.false_positive + other.false_positive,
            self.false_negative + other.false_negative,
            self.true_negative + other.true_negative,
        )

    def as_dict(self) -> dict[str, int]:
        return {
            "tp": self.true_positive,
            "fp": self.false_positive,
            "fn": self.false_negative,
            "tn": self.true_negative,
        }


@dataclass(frozen=True, slots=True)
class ImageScore:
    """Ce qu'une image a produit, étiquette par étiquette."""

    expected: frozenset[Warn]
    detected: frozenset[Warn]
    false_positives: frozenset[Warn]
    false_negatives: frozenset[Warn]
    #: Codes informationnels émis, hors matrice.
    informational: frozenset[Warn]
    per_label: dict[Warn, LabelScore] = field(default_factory=dict)

    @property
    def perfect(self) -> bool:
        """Ni manque ni sur-détection. Le seul « réussi » qui veuille dire quelque chose."""
        return not self.false_positives and not self.false_negatives


def score_image(expected: set[Warn], emitted: set[Warn]) -> ImageScore:
    """Confronte les attentes du corpus aux avertissements réellement émis.

    Les deux ensembles sont d'abord restreints aux étiquettes comptables :
    un code attendu mais hors `SCORED` serait un défaut du corpus, pas une
    erreur du détecteur, et le compter le masquerait.
    """
    expected_scored = frozenset(expected) & SCORED
    detected = frozenset(emitted) & SCORED

    per_label: dict[Warn, LabelScore] = {}
    for label in SCORED:
        in_expected = label in expected_scored
        in_detected = label in detected
        per_label[label] = LabelScore(
            true_positive=int(in_expected and in_detected),
            false_positive=int(in_detected and not in_expected),
            false_negative=int(in_expected and not in_detected),
            true_negative=int(not in_expected and not in_detected),
        )

    return ImageScore(
        expected=expected_scored,
        detected=detected,
        false_positives=detected - expected_scored,
        false_negatives=expected_scored - detected,
        informational=frozenset(emitted) - SCORED,
        per_label=per_label,
    )


@dataclass(frozen=True, slots=True)
class Totals:
    """Bilan sur un ensemble d'images gradées."""

    images: int
    perfect_images: int
    images_with_false_positive: int
    images_with_false_negative: int
    undetermined_lens: int
    overall: LabelScore
    per_label: dict[Warn, LabelScore]

    def as_dict(self) -> dict[str, object]:
        counts = self.overall
        expected_total = counts.true_positive + counts.false_negative
        detected_total = counts.true_positive + counts.false_positive
        return {
            "definitions": {
                "labelSet": sorted(label.value for label in SCORED),
                "tp": "attendu et détecté",
                "fp": "détecté, non attendu",
                "fn": "attendu, non détecté",
                "tn": "ni attendu ni détecté, parmi les étiquettes du jeu",
                "detectedOfExpected": "tp / (tp + fn) — part des défauts annoncés qui sont vus",
                "falseAlarmsPerImage": "fp / images — sur-détections par image",
                "note": (
                    "Aucune « exactitude » n'est publiée : sur un problème "
                    "multi-label majoritairement négatif, elle est dominée par "
                    "les vrais négatifs et flatte un détecteur muet."
                ),
            },
            "images": self.images,
            "perfectImages": self.perfect_images,
            "imagesWithFalsePositive": self.images_with_false_positive,
            "imagesWithFalseNegative": self.images_with_false_negative,
            "undeterminedLens": self.undetermined_lens,
            "overall": counts.as_dict(),
            "detectedOfExpected": (
                None if expected_total == 0 else round(counts.true_positive / expected_total, 4)
            ),
            "falseAlarmsPerImage": (
                None if self.images == 0 else round(counts.false_positive / self.images, 4)
            ),
            "precisionOfDetections": (
                None if detected_total == 0 else round(counts.true_positive / detected_total, 4)
            ),
            "perLabel": {
                label.value: score.as_dict()
                for label, score in sorted(self.per_label.items(), key=lambda kv: kv[0].value)
                # Une étiquette jamais attendue ni détectée n'apprend rien :
                # la lister ne ferait que diluer le tableau.
                if score.true_positive or score.false_positive or score.false_negative
            },
        }


def total(scores: list[ImageScore], undetermined_lens: int) -> Totals:
    """Agrège les scores d'images gradées."""
    overall = LabelScore()
    per_label: dict[Warn, LabelScore] = {label: LabelScore() for label in SCORED}
    for score in scores:
        for label, label_score in score.per_label.items():
            per_label[label] = per_label[label].plus(label_score)
            overall = overall.plus(label_score)

    return Totals(
        images=len(scores),
        perfect_images=sum(1 for score in scores if score.perfect),
        images_with_false_positive=sum(1 for score in scores if score.false_positives),
        images_with_false_negative=sum(1 for score in scores if score.false_negatives),
        undetermined_lens=undetermined_lens,
        overall=overall,
        per_label=per_label,
    )


@dataclass(frozen=True, slots=True)
class LensScore:
    """Comparaison à la vérité terrain de distorsion, quand elle est connue.

    Trois questions distinctes, et il faut les trois : la présence est-elle
    détectée, le **sens** est-il bon, l'**intensité** est-elle proche ? Un
    détecteur qui repère une distorsion mais se trompe de sens serait
    inexploitable au LOT 4, où le signe décide du sens de la correction.
    """

    truth_k1: float
    truth_sign: str
    truth_distorted: bool
    verdict: str
    detected: bool
    estimated_k1: float | None
    estimated_sign: str | None
    #: `None` quand aucune estimation n'a pu être produite.
    k1_absolute_error: float | None
    sign_correct: bool | None

    def as_dict(self) -> dict[str, object]:
        return {
            "truthK1": self.truth_k1,
            "truthSign": self.truth_sign,
            "truthDistorted": self.truth_distorted,
            "verdict": self.verdict,
            "detected": self.detected,
            "estimatedK1": self.estimated_k1,
            "estimatedSign": self.estimated_sign,
            "k1AbsoluteError": self.k1_absolute_error,
            "signCorrect": self.sign_correct,
        }


def score_lens(
    truth_k1: float, verdict: str, estimated_k1: float | None, estimated_sign: str | None
) -> LensScore:
    """Confronte le verdict d'objectif au k1 réellement imposé."""
    distorted = truth_k1 != 0.0
    truth_sign = "barrel" if truth_k1 > 0 else "pincushion" if truth_k1 < 0 else "none"
    detected = verdict == "distortion_suspected"

    return LensScore(
        truth_k1=truth_k1,
        truth_sign=truth_sign,
        truth_distorted=distorted,
        verdict=verdict,
        detected=detected,
        estimated_k1=estimated_k1,
        estimated_sign=estimated_sign,
        k1_absolute_error=(
            None if estimated_k1 is None else round(abs(estimated_k1 - truth_k1), 5)
        ),
        # Le sens n'a de sens que si la scène en avait un et qu'on a conclu.
        sign_correct=(
            None if not distorted or estimated_sign is None else estimated_sign == truth_sign
        ),
    )
