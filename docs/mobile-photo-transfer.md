# Transfert photo depuis téléphone : contrat futur

Le fichier local fonctionne dès maintenant. Aucun QR Code n’est affiché tant
qu’un téléphone ne peut pas rejoindre un endpoint autorisé et fonctionnel.
Le serveur Product Dev reste limité à 127.0.0.1 : un QR Code pointant vers cette
adresse ne fonctionnerait pas sur le téléphone.

Contrat proposé (non implémenté) : POST /v1/photo-transfer-sessions crée un jeton
aléatoire à usage unique, de durée maximale 10 minutes. Le desktop reçoit une
URL HTTPS accessible au téléphone et un jeton de lecture distinct. Le mobile
POSTe un JPEG/PNG/WebP sous limite de taille sur la session. Le desktop suit
l’état pending/received/expired/consumed par polling ou SSE, récupère les octets,
puis le serveur les efface après consommation ou expiration. Pas de compte,
pas de stockage durable, pas de lien réutilisable. Les limites MIME, taille,
réessais, quotas et contrôle d’accès doivent être validés avant publication.

Il faudra choisir explicitement l’hébergement HTTPS et l’accès réseau avant de
réaliser ce transfert. Le lancement local actuel n’ouvre aucun port public.
