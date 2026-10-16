/** Catalogue commercial local. Matières de démonstration approximatives. */
(function () {
  const PREMIBEL = 'local-demo-assets/premibel/';
  window.PP_PREMIBEL_PRODUCTS = [
    {
      id: 'POINF36005', ref: 'POINF36005', source: 'premibel', compatibility: 'interior', usage: 'interieur',
      name: 'Point de Hongrie Zeus Naturel',
      fullTitle: 'POINT DE HONGRIE ZEUS NATUREL 92X12X520',
      productUrl: 'https://www.premibel.fr/parquet-flottant-chene-verni/POINF36005/',
      imageSourceUrl: 'https://www.premibel.fr/wp-content/uploads/2026/07/POINF36005.jpg',
      heroImage: PREMIBEL + 'POINF36005.jpg',
      catalogThumbnail: PREMIBEL + 'thumb.POINF36005.jpg',
      catalogThumbnailSource: 'premibel_photo_crop',
      checkedAt: '2026-09-08',
      species: 'Chêne', pattern: 'point-de-hongrie', widthMm: 92, lengthMm: 520,
      thicknessMm: 12, finish: 'verni', aspect: 'Brossé', premibelFamily: 'FLCHEN08',
      tone: 'clair',
      /* Ce que l'adaptateur envoie au renderer. Uniquement des proprietes
         que le moteur honore vraiment : materiau, motif, largeur, angle. */
      renderProfile: {
        materialFamily: 'chene-miel',  // LOT PHOTO.2 : couleur de la vignette, mesuree
        pattern: 'point-de-hongrie',
        widthM: 0.092,
        lengthM: 0.52,
        orientationDeg: 0,
      },
      /* L'exactitude, attribut par attribut — un seul mot pour tout le
         produit cachait que la geometrie est juste et la matiere non. */
      renderAccuracy: {
        pattern: 'exact',
        width: 'exact',
        orientation: 'exact',
        tone: 'approximate',
        grain: 'approximate',
        finish: 'approximate',
      },
      rendererMapping: {
        status: 'approximate', familyId: 'chene-sable', pattern: 'point-de-hongrie',
        widthM: 0.092, familySource: 'pilote du front (products.premibel-pilot.json)',
        exact: ['pattern', 'widthMm', 'angle'],
        approximate: ['tone', 'grain', 'finish'],
        unavailable: ['albedo', 'normal', 'roughness'],
      },
      visualAccuracy: 'approximate',
    },
    {
      id: 'BTRPF39009', ref: 'BTRPF39009', source: 'premibel', compatibility: 'interior', usage: 'interieur',
      name: 'Bâton rompu Notting Hill Invisible',
      fullTitle: 'Baton rompu notting hill invisible 90X15X600mm',
      productUrl: 'https://www.premibel.fr/parquet-flottant-chene-verni/BTRPF39009/',
      imageSourceUrl: 'https://www.premibel.fr/wp-content/uploads/2026/04/BTRPF39009.png',
      heroImage: PREMIBEL + 'BTRPF39009.png',
      catalogThumbnail: PREMIBEL + 'thumb.BTRPF39009.jpg',
      catalogThumbnailSource: 'premibel_photo_crop',
      checkedAt: '2026-09-08',
      species: 'Chêne', pattern: 'baton-rompu', widthMm: 90, lengthMm: 600,
      thicknessMm: 15, finish: 'verni', aspect: 'Brossé', premibelFamily: 'FLCHEN08',
      tone: 'clair',
      substituteFor: 'BTRPF39008 « Piccadilly », introuvable au 8 septembre 2026',
      /* Ce que l'adaptateur envoie au renderer. Uniquement des proprietes
         que le moteur honore vraiment : materiau, motif, largeur, angle. */
      renderProfile: {
        materialFamily: 'chene-naturel',  // LOT PHOTO.2 : couleur de la vignette, mesuree
        pattern: 'baton-rompu',
        widthM: 0.09,
        lengthM: 0.6,
        orientationDeg: 0,
      },
      /* L'exactitude, attribut par attribut — un seul mot pour tout le
         produit cachait que la geometrie est juste et la matiere non. */
      renderAccuracy: {
        pattern: 'exact',
        width: 'exact',
        orientation: 'exact',
        tone: 'approximate',
        grain: 'approximate',
        finish: 'approximate',
      },
      rendererMapping: {
        status: 'approximate', familyId: 'chene-craie', pattern: 'baton-rompu',
        widthM: 0.09, familySource: 'pilote du front (products.premibel-pilot.json)',
        exact: ['pattern', 'widthMm', 'angle'],
        approximate: ['tone', 'grain', 'finish'],
        unavailable: ['albedo', 'normal', 'roughness'],
      },
      visualAccuracy: 'approximate',
    },
    {
      id: 'CHENF39031', ref: 'CHENF39031', source: 'premibel', compatibility: 'interior', usage: 'interieur',
      name: 'Chêne naturel Houston',
      fullTitle: 'Chêne naturel houston 190X15X400mm',
      productUrl: 'https://www.premibel.fr/parquet-flottant-chene-verni/CHENF39031/',
      imageSourceUrl: 'https://www.premibel.fr/wp-content/uploads/2025/11/CHENF39031.jpg',
      heroImage: PREMIBEL + 'CHENF39031.jpg',
      catalogThumbnail: PREMIBEL + 'thumb.CHENF39031.jpg',
      catalogThumbnailSource: 'renderer_crop',
      checkedAt: '2026-09-08',
      species: 'Chêne', pattern: 'lames', widthMm: 190, lengthMm: 1900,
      lengthNote: 'tableau : 1900 mm · titre de la fiche : 400 mm — non arbitré',
      thicknessMm: 15, finish: 'verni', aspect: 'Brossé, Satiné', premibelFamily: 'FLCHEN08',
      tone: 'naturel',
      /* Ce que l'adaptateur envoie au renderer. Uniquement des proprietes
         que le moteur honore vraiment : materiau, motif, largeur, angle. */
      renderProfile: {
        materialFamily: 'chene-naturel',
        pattern: 'lames',
        widthM: 0.19,
        lengthM: 1.9,
        orientationDeg: 0,
      },
      /* L'exactitude, attribut par attribut — un seul mot pour tout le
         produit cachait que la geometrie est juste et la matiere non. */
      renderAccuracy: {
        pattern: 'exact',
        width: 'exact',
        orientation: 'exact',
        tone: 'approximate',
        grain: 'approximate',
        finish: 'approximate',
      },
      rendererMapping: {
        status: 'approximate', familyId: 'chene-naturel', pattern: 'lames',
        widthM: 0.19, familySource: 'le nôtre, absent du pilote du front, non validé',
        exact: ['pattern', 'widthMm', 'angle'],
        approximate: ['tone', 'grain', 'finish'],
        unavailable: ['albedo', 'normal', 'roughness'],
      },
      visualAccuracy: 'approximate',
    },
    {
      id: 'CHENF36014', ref: 'CHENF36014', source: 'premibel', compatibility: 'interior', usage: 'interieur',
      name: 'Chêne Colza',
      fullTitle: 'CHENE COLZA 150X15',
      productUrl: 'https://www.premibel.fr/parquet-flottant-chene-verni/CHENF36014/',
      imageSourceUrl: 'https://www.premibel.fr/wp-content/uploads/2026/07/CHENF36014.jpg',
      heroImage: PREMIBEL + 'CHENF36014.jpg',
      catalogThumbnail: PREMIBEL + 'thumb.CHENF36014.jpg',
      catalogThumbnailSource: 'premibel_photo_crop',
      checkedAt: '2026-09-08',
      species: 'Chêne', pattern: 'lames', widthMm: 150, lengthMm: 1900,
      thicknessMm: 15, finish: 'verni', aspect: 'Brossé, Mat', premibelFamily: 'FLCHEN08',
      tone: 'clair',
      /* Ce que l'adaptateur envoie au renderer. Uniquement des proprietes
         que le moteur honore vraiment : materiau, motif, largeur, angle. */
      renderProfile: {
        materialFamily: 'chene-caramel',  // LOT PHOTO.2 : couleur de la vignette, mesuree
        pattern: 'lames',
        widthM: 0.15,
        lengthM: 1.9,
        orientationDeg: 0,
      },
      /* L'exactitude, attribut par attribut — un seul mot pour tout le
         produit cachait que la geometrie est juste et la matiere non. */
      renderAccuracy: {
        pattern: 'exact',
        width: 'exact',
        orientation: 'exact',
        tone: 'approximate',
        grain: 'approximate',
        finish: 'approximate',
      },
      rendererMapping: {
        status: 'approximate', familyId: 'chene-sable', pattern: 'lames',
        widthM: 0.15, familySource: 'pilote du front (products.premibel-pilot.json)',
        exact: ['pattern', 'widthMm', 'angle'],
        approximate: ['tone', 'grain', 'finish'],
        unavailable: ['albedo', 'normal', 'roughness'],
      },
      visualAccuracy: 'approximate',
    },
    {
      id: 'CHENF36015', ref: 'CHENF36015', source: 'premibel', compatibility: 'interior', usage: 'interieur',
      name: 'Chêne Invisible Pivoine',
      fullTitle: 'CHENE INVISIBLE PIVOINE 150X15',
      productUrl: 'https://www.premibel.fr/parquet-flottant-chene-verni/CHENF36015/',
      imageSourceUrl: 'https://www.premibel.fr/wp-content/uploads/2026/07/CHENF36015.jpg',
      heroImage: PREMIBEL + 'CHENF36015.jpg',
      catalogThumbnail: PREMIBEL + 'thumb.CHENF36015.jpg',
      catalogThumbnailSource: 'premibel_photo_crop',
      checkedAt: '2026-09-08',
      species: 'Chêne', pattern: 'lames', widthMm: 150, lengthMm: 1900,
      thicknessMm: 15, finish: 'verni', aspect: 'Brossé, Mat', premibelFamily: 'FLCHEN08',
      tone: 'chaud',
      /* Ce que l'adaptateur envoie au renderer. Uniquement des proprietes
         que le moteur honore vraiment : materiau, motif, largeur, angle. */
      renderProfile: {
        materialFamily: 'chene-naturel',  // LOT PHOTO.2 : couleur de la vignette, mesuree
        pattern: 'lames',
        widthM: 0.15,
        lengthM: 1.9,
        orientationDeg: 0,
      },
      /* L'exactitude, attribut par attribut — un seul mot pour tout le
         produit cachait que la geometrie est juste et la matiere non. */
      renderAccuracy: {
        pattern: 'exact',
        width: 'exact',
        orientation: 'exact',
        tone: 'approximate',
        grain: 'approximate',
        finish: 'approximate',
      },
      rendererMapping: {
        status: 'approximate', familyId: 'chene-rustique', pattern: 'lames',
        widthM: 0.15, familySource: 'pilote du front (products.premibel-pilot.json)',
        exact: ['pattern', 'widthMm', 'angle'],
        approximate: ['tone', 'grain', 'finish'],
        unavailable: ['albedo', 'normal', 'roughness'],
      },
      visualAccuracy: 'approximate',
    },
  ];

})();
