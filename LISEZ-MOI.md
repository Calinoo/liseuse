# Liseuse : défilement automatique pour PDF et EPUB

Une web app à installer sur l'écran d'accueil de l'iPhone ou de l'iPad. Une fois installée, elle marche **sans connexion** et vos livres restent stockés dans l'appareil.

## Utilisation

- **Ajouter un livre** : bouton « + Ajouter un livre », puis choisissez un PDF ou un EPUB dans l'app Fichiers (iCloud Drive, Téléchargements…).
- **Lancer ou arrêter le défilement** : touchez le texte, ou le bouton ▶ en bas.
- **Vitesse** : curseur, ou boutons − et +. Elle est mémorisée.
- **Avancer ou reculer à la main** : glissez le doigt. Le défilement se met en pause pendant le geste et reprend tout seul.
- **Aa** : thème, taille du texte et police (EPUB), choix de la voix.
- **Pincer à deux doigts** : change la taille du texte (EPUB) ou agrandit la page (PDF, jusqu'à 300 %, on glisse alors de côté). L'app elle-même ne zoome jamais.
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

## Lecture à voix haute

- Bouton 🔊 en bas : lit à partir du haut de l'écran. Appui long sur un paragraphe : lit à partir de là.
- La phrase lue est surlignée et le texte suit la voix. Commandes : ⏮ ⏯ ⏭ ■, vitesse de la voix, minuterie ⏲.
- La meilleure voix installée est choisie automatiquement ; on peut en choisir une autre dans **Aa > Voix**.
- Pour une voix plus naturelle (gratuit), téléchargez une voix française « Améliorée » ou « Premium » dans Réglages > Accessibilité > Contenu énoncé > Voix. La Liseuse la choisira automatiquement.
- Limite d'iOS pour les apps web : la lecture s'arrête si l'écran se verrouille ou si vous changez d'app. L'écran reste donc allumé pendant la lecture, et ⏯ reprend à la même phrase.

## Bon à savoir

- **Écran qui se verrouille** : la Liseuse demande à garder l'écran allumé pendant le défilement. C'est pris en charge par les versions récentes d'iOS (18.4 et plus pour une app ajoutée à l'écran d'accueil). Sur une version plus ancienne, augmentez « Verrouillage automatique » dans Réglages > Luminosité et affichage.
- **Livres protégés (DRM)** : les EPUB achetés sur Apple Books, Kindle ou Kobo avec protection ne peuvent pas être ouverts. Les EPUB sans DRM et les PDF fonctionnent.
- **Mise à jour de l'app** : après avoir modifié les fichiers, augmentez le numéro de version (`liseuse-v2` → `liseuse-v3`…) dans `sw.js`, puis remettez le dossier en ligne.
- **Supprimer l'app de l'écran d'accueil efface aussi les livres qu'elle contient.**

## Contenu du dossier

- `index.html`, `style.css`, `app.js` : l'application ; `core.js` : la logique pure, testée unitairement
- `SPEC.md` : la spécification ; `tests/` et `test.sh` : la suite de régression
- `sw.js`, `manifest.webmanifest`, `icons/` : installation et mode hors ligne
- `vendor/` : pdf.js (Mozilla) et JSZip, embarqués pour fonctionner hors connexion

## Développement : spécification et tests

La méthode suivie est **spec d'abord, test ensuite, code en dernier** :

1. Toute nouvelle fonction ou correction commence par une exigence numérotée dans [`SPEC.md`](SPEC.md) (ex. `PROG-5`).
2. On écrit un test qui cite cet identifiant et **qui échoue** (`tests/test_*.py`).
3. On écrit le code minimal qui le fait passer, puis on relance **toute** la suite (régression).

Stratégie de test : on ne relance pas tout à chaque fois.

```bash
./test.sh rapide      # pendant le développement : unitaires + socle stratégique sur iPhone (~30 s)
./test.sh impact      # à chaque changement : tests liés aux fichiers modifiés + socle, 3 cibles
./test.sh livraison   # avant publication : tout sur iPhone + socle sur iPad et Chromium (~1 min 20)
./test.sh complet     # gros changement ou mise à jour de pdf.js/JSZip : tout, partout
./test.sh -k SRCH     # une famille d'exigences précise
```

- **Socle stratégique** (`-m strategic`, liste dans `tests/conftest.py`) : les parcours qui ne doivent jamais casser (importer, ouvrir un PDF et un EPUB, défiler, reprendre, hors ligne, sécurité EPUB, recherche, rotation).
- **Analyse d'impact** (`tests/impact.py`) : associe chaque fichier modifié depuis la dernière publication aux familles d'exigences concernées. `app.js` touchant à tout, le modifier déclenche le mode livraison.
- Les tests tournent en parallèle (pytest-xdist).

- `tests/test_core.py` : tests unitaires de la logique pure (`core.js`).
- Les autres fichiers sont des tests de bout en bout. Ils pilotent la vraie app avec Playwright, dans **WebKit** (le moteur de Safari) en iPhone et iPad, et dans **Chromium**.
- Les livres de test sont générés par `tests/fixtures/make_books.py`. Ils contiennent volontairement des pièges : scripts, chemins tordus, fichiers corrompus.
- Le temps est simulé dans les tests de défilement : les mesures de vitesse sont exactes et reproductibles.
- Limite connue : Playwright WebKit ne gère pas les service workers. Le mode hors ligne (OFF-1) est donc vérifié dans Chromium. Il faudra aussi le vérifier une fois à la main sur l'iPhone (mode avion).
