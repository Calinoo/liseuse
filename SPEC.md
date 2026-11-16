# Spécification : Liseuse à défilement automatique

Ce document est la référence du comportement attendu. Chaque exigence a un identifiant (`BIB-1`, `DEF-3`…). Chaque test automatique cite l'identifiant qu'il vérifie (voir `tests/`).
**Règle :** on modifie d'abord la spec, puis on écrit un test qui échoue, puis on écrit le code.

Cibles : Safari iOS / iPadOS 16+ (app ajoutée à l'écran d'accueil). Également utilisable dans un navigateur de bureau récent.

---

## 1. Bibliothèque (BIB)

| ID | Exigence |
|---|---|
| BIB-1 | Au premier lancement, la bibliothèque est vide et affiche un message expliquant comment ajouter un livre. |
| BIB-2 | Le bouton « + Ajouter un livre » ouvre le sélecteur de fichiers. Il accepte les `.pdf` et `.epub`, et plusieurs fichiers à la fois. |
| BIB-3 | Le type est déterminé par l'extension (insensible à la casse), sinon par le type MIME. Tout autre fichier est refusé avec un message, sans bloquer l'import des autres fichiers. |
| BIB-4 | Le titre d'un EPUB est son `dc:title`. À défaut, et pour les PDF, c'est le nom du fichier sans son extension. |
| BIB-5 | Les livres sont triés du plus récemment ouvert (ou ajouté) au plus ancien. |
| BIB-6 | Chaque livre affiche : son type, son titre, le pourcentage lu, sa taille (« 15 Ko », « 1,2 Mo ») et une barre de progression. |
| BIB-7 | Le bouton ✕ retire le livre après confirmation. En cas d'annulation, rien ne change. |
| BIB-8 | Les livres et leur progression survivent à un rechargement de l'app (stockage IndexedDB local). |

## 2. Lecture PDF (PDF)

| ID | Exigence |
|---|---|
| PDF-1 | Toutes les pages sont affichées les unes sous les autres, à la largeur de l'écran (max. 1000 px), dans leurs vraies proportions. |
| PDF-2 | Seules les pages proches de l'écran sont dessinées. Les pages éloignées sont libérées (limite mémoire iOS). |
| PDF-3 | Un PDF illisible affiche un message d'erreur et ramène à la bibliothèque. |
| PDF-4 | Après une rotation ou un redimensionnement, la position de lecture est conservée. |

## 3. Lecture EPUB (EPUB)

| ID | Exigence |
|---|---|
| EPUB-1 | Tous les chapitres de la `spine` sont affichés à la suite, dans l'ordre, en un seul long texte. |
| EPUB-2 | Les images internes au livre s'affichent (chemins relatifs, `../`, noms encodés en `%20`). |
| EPUB-3 | Sécurité : aucun script, aucune feuille de style, aucun attribut `on*` ni `style` du livre n'est conservé. |
| EPUB-4 | Un lien interne (`chapitre.xhtml#ancre` ou `#ancre`) fait défiler jusqu'à la cible et met la lecture en pause. |
| EPUB-5 | Un lien externe (`http(s)`) demande une confirmation avant de s'ouvrir. |
| EPUB-6 | Un EPUB invalide (sans `container.xml` ou sans OPF) affiche un message d'erreur clair. |

## 4. Défilement automatique (DEF)

| ID | Exigence |
|---|---|
| DEF-1 | Toucher le texte lance le défilement. Le toucher à nouveau le met en pause. Le bouton ▶/❚❚ fait de même. |
| DEF-2 | Le défilement avance à la vitesse réglée, en pixels CSS par seconde, de façon régulière, quelle que soit la fréquence d'images. |
| DEF-3 | La vitesse va de 5 à 200. Les boutons −/+ avancent par pas de 1 (vitesse < 20), 2 (< 60) ou 5 (au-delà). Elle est mémorisée entre les sessions. |
| DEF-4 | Pendant que le doigt touche l'écran, le défilement est suspendu. Il reprend 0,7 s après le relâchement, à partir de la nouvelle position. |
| DEF-5 | Arrivé à la fin du livre, le défilement s'arrête tout seul. |
| DEF-6 | Pendant le défilement, les barres se masquent après 2 s. À la pause, elles réapparaissent. |
| DEF-7 | Quand l'app passe en arrière-plan, le défilement se met en pause et la position est enregistrée. |
| DEF-8 | Pendant le défilement, l'app demande à garder l'écran allumé (Wake Lock) si l'appareil le permet, et libère cette demande à la pause. |

## 5. Progression (PROG)

| ID | Exigence |
|---|---|
| PROG-1 | La progression est la fraction parcourue : `scrollTop / (scrollHeight − clientHeight)`, bornée à [0, 1]. Elle vaut 0 si le contenu tient dans l'écran. |
| PROG-2 | Elle s'affiche en pourcentage arrondi dans la barre du haut et se met à jour pendant la lecture. |
| PROG-3 | Elle est enregistrée au plus tard 3 s après chaque mouvement, ainsi qu'à la pause, à la fermeture et au passage en arrière-plan. |
| PROG-4 | En rouvrant un livre, la lecture reprend à la progression enregistrée (à 1 % près). |
| PROG-5 | **Temps restant** : la barre du haut affiche une estimation du temps de lecture restant à la vitesse actuelle : `(scrollHeight − clientHeight − scrollTop) / vitesse` secondes. |
| PROG-6 | Format du temps restant : `Terminé` s'il reste moins d'une demi-seconde ; `< 1 min` sous 60 s ; `~N min` sous 1 h (arrondi à la minute la plus proche) ; `~H h MM` au-delà (minutes sur 2 chiffres). |
| PROG-7 | Le temps restant se met à jour quand la position ou la vitesse change. |

## 6. Affichage (AFF)

| ID | Exigence |
|---|---|
| AFF-1 | Trois thèmes : Clair, Sépia, Sombre. Ils s'appliquent à toute l'app, PDF compris (le mode sombre inverse les couleurs des pages). |
| AFF-2 | EPUB : taille du texte de 13 à 34 px (19 par défaut) ; police Serif ou Sans. Ces réglages sont masqués pour les PDF. |
| AFF-3 | Changer la taille ou la police conserve la position de lecture (à 2 % près). |
| AFF-4 | Tous les réglages d'affichage sont mémorisés entre les sessions. |
| AFF-6 | Après une rotation de l'appareil (ou un redimensionnement de la fenêtre), la position de lecture est conservée à 1 % près, pour les EPUB comme pour les PDF (voir aussi PDF-4). |
| AFF-5 | L'interface est utilisable sans défilement horizontal sur iPhone (375 px de large) comme sur iPad, en portrait et en paysage, en respectant les zones de sécurité (encoche, barre d'accueil). |

## 7. Hors connexion (OFF)

| ID | Exigence |
|---|---|
| OFF-1 | Après une première visite en ligne, l'app entière (code, bibliothèques, icônes) est en cache et démarre sans réseau. |
| OFF-2 | Les livres ne sont jamais envoyés sur le réseau. |
| OFF-3 | L'app est installable (manifeste, icônes, mode `standalone`). |

---

## Hors périmètre (pour l'instant)
EPUB protégés par DRM, synchronisation entre appareils, annotations, recherche dans le texte, mise en page fixe (EPUB « fixed layout »).
