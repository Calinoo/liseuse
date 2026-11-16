# Liseuse : défilement automatique pour PDF et EPUB

Une web app à installer sur l'écran d'accueil de l'iPhone ou de l'iPad. Une fois installée, elle marche **sans connexion** et vos livres restent stockés dans l'appareil.

## Utilisation

- **Ajouter un livre** : bouton « + Ajouter un livre », puis choisissez un PDF ou un EPUB dans l'app Fichiers (iCloud Drive, Téléchargements…).
- **Lancer ou arrêter le défilement** : touchez le texte, ou le bouton ▶ en bas.
- **Vitesse** : curseur, ou boutons − et +. Elle est mémorisée.
- **Avancer ou reculer à la main** : glissez le doigt. Le défilement se met en pause pendant le geste et reprend tout seul.
- **Aa** : thème clair, sépia ou sombre ; taille du texte et police (EPUB).
- La position de lecture est enregistrée en continu. Le livre se rouvre là où vous l'avez laissé.

## Installation sur iPhone / iPad (une seule fois)

Le dossier doit être mis en ligne en HTTPS, car iOS exige HTTPS pour le mode hors connexion. C'est gratuit.

### Option simple : Netlify Drop
1. Sur le Mac, ouvrez https://app.netlify.com/drop (compte gratuit).
2. Glissez-déposez **tout le dossier `liseuse`** sur la page.
3. Netlify vous donne une adresse du type `https://xxxx.netlify.app`.

### Ensuite, sur l'iPhone ou l'iPad
1. Ouvrez cette adresse dans **Safari**.
2. Touchez **Partager** (carré avec une flèche), puis **« Sur l'écran d'accueil »**.
3. Ouvrez la Liseuse depuis son icône une première fois avec Internet. Ensuite, elle fonctionne en mode avion.

> Les livres sont enregistrés dans l'app installée, pas sur le serveur. Rien n'est envoyé en ligne.

## Bon à savoir

- **Écran qui se verrouille** : la Liseuse demande à garder l'écran allumé pendant le défilement. C'est pris en charge par les versions récentes d'iOS (18.4 et plus pour une app ajoutée à l'écran d'accueil). Sur une version plus ancienne, augmentez « Verrouillage automatique » dans Réglages > Luminosité et affichage.
- **Livres protégés (DRM)** : les EPUB achetés sur Apple Books, Kindle ou Kobo avec protection ne peuvent pas être ouverts. Les EPUB sans DRM et les PDF fonctionnent.
- **Mise à jour de l'app** : après avoir modifié les fichiers, changez `liseuse-v1` en `liseuse-v2` dans `sw.js`, puis remettez le dossier en ligne.
- **Supprimer l'app de l'écran d'accueil efface aussi les livres qu'elle contient.**

## Contenu du dossier

- `index.html`, `style.css`, `app.js` : l'application
- `sw.js`, `manifest.webmanifest`, `icons/` : installation et mode hors ligne
- `vendor/` : pdf.js (Mozilla) et JSZip, embarqués pour fonctionner hors connexion
