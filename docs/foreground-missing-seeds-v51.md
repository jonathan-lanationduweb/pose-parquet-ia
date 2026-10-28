# MISSING-SEED CASES — V5.1

Audit visuel, coordonnées à résolution source, pas de GT exhaustive. Les crops et points restent dans la revue privée. Une zone approximative n'est pas une annotation de segmentation.

| Scène / objet | Taille source / zone approximative | Contraste | Seed coarse | V5 peut récupérer ? | Constat |
|---|---|---|---|---|---|
| Chambre / tige verte | Environ 1–4 px de large, ROI [120,270,205,410], source 900×1029 | Chromatique, fond bois | Partiel, trou local | Oui, ancrages existants | Dix centres annotés déjà 10/10 V5 et conservés V5.1 ; pas un objet entièrement absent. |
| Chambre / coussin sombre droit | Environ 130×90 px, ROI [620,550,770,640] | Sombre sur bois clair | Présent, incomplet | En partie ; l'intérieur mal semé reste difficile | Crop contact propose une grande partie manquante ; ne suffit pas à autoriser toutes ses autres additions. |
| Bureau / câbles et petit support sous plateau | Fil de quelques px, ROI [280,520,660,750], source 1124×750 | Sombre sur tapis sombre | Câbles non distingués en tant qu'objets ; voisinage meuble présent | Pas un câble entièrement sans ancrage par simple morphologie | Photo montre aussi un tapis : une partie est déjà protégée par l'exclusion tapis/fixture. Ne pas appeler chaque pixel non rouge du câble une fuite de parquet utile. Les crops ne retrouvent pas fiablement les fils. |
| Salle à manger / pieds et passages entre chaises | Largeur variable, ROI [580,580,705,750], source 1125×750 | Bois sombre sur parquet chaud | Présent | Oui sur contours locaux | Le crop contact classe aussi du sol entre pieds comme objet. Les petites zones blanches de pied visibles dans la photo ne doivent pas être supprimées. |
| Salon / bande sous meuble TV | Quelques px à dizaines de px, ROI [540,405,930,495], source 1536×1024 | Très sombre, ombre de contact | Meuble présent, bande ambiguë | Pas de certitude par couleur seule | Peut mêler ombre photographique et pied. Ne pas l'étiqueter objet sans vérification. |
| Tapis clair / bord et pot | Bord fin, ROI tapis [0,430,500,730], source 800×916 | Proche du bois / pot sombre | Présent, parfois incomplet | Raffinement local, pas une invention d'objet | Les tuiles inventent 87005 pixels de tapis sur le bois ; aucune intégration automatique. |

La réduction 512 peut effacer des structures d'un pixel ; les exemples entièrement absents et utiles au composite ne sont pas encore suffisamment annotés pour conclure à plusieurs catégories critiques manquées. Aucun score de rappel global ni calibration de foregroundQuality n'est déduit de cette liste. Un nouveau modèle n'est donc ni téléchargé ni ajouté.

Décision : conserver les optimisations exactes ; rejeter les unions de crops non validées. Le prochain essai doit partir de GT localisées distinguant objet, ombre, tapis déjà exclu et vrai sol visible. Un meilleur échantillonnage sémantique peut fournir des seeds supplémentaires mais ne garantit pas leur validité.
