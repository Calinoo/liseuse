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
| BIB-9 | Chaque livre reçoit une empreinte de son contenu (SHA-256), calculée à l'import, ou à la première ouverture pour les livres importés avant cette version. Réimporter un fichier identique ne crée pas de doublon : un message indique qu'il est déjà dans la bibliothèque. *(Prépare la synchronisation : un même livre a la même empreinte sur l'iPhone et l'iPad.)* |

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
| DEF-9 | **Fluidité** : pendant le défilement, le texte avance d'une quantité régulière à chaque image (au sous-pixel près), sans alterner « 1 px / 0 px ». À 30 px/s et 60 images/s, chaque image avance de 0,5 px (± 0,08). |
| DEF-10 | Pendant le défilement, aucun travail coûteux n'est fait à chaque image : les barres masquées ne sont plus dessinées (`visibility: hidden`), et le pourcentage et le temps restant sont rafraîchis au plus 4 fois par seconde. |

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

## 5 bis. Navigation rapide (NAV)

| ID | Exigence |
|---|---|
| NAV-1 | Quand les barres sont visibles, une barre de progression (0 à 100 %) permet de sauter n'importe où dans le livre en la faisant glisser. |
| NAV-2 | Pendant le glissement, le défilement automatique se met en pause et une étiquette indique où l'on arrive : pour un EPUB, le titre du chapitre (premier titre de la section, sinon « Chapitre n ») ; pour un PDF, « Page n / N ». |
| NAV-3 | La barre de progression suit la lecture : elle reflète la progression actuelle (PROG-1). |
| NAV-4 | Après un saut, la nouvelle position est enregistrée (PROG-3). |

## 5 ter. Recherche dans le livre (SRCH)

| ID | Exigence |
|---|---|
| SRCH-1 | Une loupe 🔍 dans la barre du haut ouvre le panneau de recherche, avec le champ de saisie prêt à taper. L'ouvrir met le défilement en pause. |
| SRCH-2 | La recherche ignore les majuscules, les accents et le type d'apostrophe (« elegante » trouve « Élégante », « l'ete » trouve « L’été »). Les espaces multiples comptent pour un seul. Un mot coupé par une mise en forme (italique…) est trouvé quand même. Elle démarre à partir de 2 caractères (sinon le message « Tapez au moins 2 caractères » s'affiche). |
| SRCH-3 | Chaque résultat affiche un extrait (environ 40 caractères de contexte de chaque côté, le passage trouvé mis en évidence) et son emplacement : le titre du chapitre pour un EPUB, « Page n / N » pour un PDF. Le nombre de résultats s'affiche (« 1 résultat », « 12 résultats », « Aucun résultat »). |
| SRCH-4 | Au-delà de 200 résultats, seuls les 200 premiers sont listés et le compteur affiche « 200+ résultats ». |
| SRCH-5 | Toucher un résultat ferme le panneau, amène le passage au tiers supérieur de l'écran (dans la limite de la fin du livre) et le surligne pendant quelques secondes. La position est enregistrée. |
| SRCH-6 | Un PDF sans texte (page scannée) affiche « Ce PDF ne contient pas de texte cherchable ». |
| SRCH-7 | Le bouton ✕ ou la touche Échap ferme le panneau. En le rouvrant, la recherche précédente et ses résultats sont toujours là (tant que le livre reste ouvert). |

## 5 quater. Lecture à voix haute (TTS)

Utilise les voix installées sur l'appareil (synthèse vocale du système) : gratuit, hors connexion, rien n'est envoyé sur Internet.

| ID | Exigence |
|---|---|
| TTS-1 | Un bouton 🔊 dans la barre du bas lance la lecture à voix haute à partir de la première phrase visible en haut de l'écran (sous la barre du haut). Le bouton est absent si l'appareil n'a pas de synthèse vocale. |
| TTS-2 | La lecture avance phrase par phrase dans tout le livre, en passant d'un chapitre ou d'une page à l'autre, jusqu'à la fin, où elle s'arrête. Un titre, un paragraphe ou un élément de liste n'est jamais fusionné avec le suivant. Une phrase de plus de 250 caractères est découpée (à une ponctuation `, ; :` si possible, sinon à un espace), car iOS coupe les phrases trop longues. Les abréviations courantes (M., Mme, Dr, etc.) et les initiales ne coupent pas une phrase. |
| TTS-3 | Voix : celle de la langue du livre (français par défaut). On préfère d'abord la variante régionale demandée (France pour « fr »), puis la qualité : « Premium », puis « Améliorée », puis standard. La qualité se lit dans le nom **ou dans l'identifiant** de la voix (`voiceURI`), car sur iPhone la voix améliorée porte le même nom que la standard (ex. deux « Audrey »). Les voix fantaisie ou robotiques (Eddy, Flo, Grandma, Grandpa, Reed, Rocko, Sandy, Shelley, voix « Eloquence » et voix gadgets macOS) ne sont jamais choisies automatiquement. Une voix est identifiée par son `voiceURI` (à défaut, son nom). Sans voix de cette langue, la voix par défaut de l'appareil. |
| TTS-4 | **Suivi** : la phrase lue est surlignée (couleur distincte de la recherche). Quand elle sort de la zone entre 15 % et 60 % de la hauteur de l'écran, le texte défile doucement pour la ramener au tiers supérieur. Si l'utilisateur fait défiler à la main, le suivi est suspendu pendant 3 s. |
| TTS-5 | **Commandes** pendant la lecture, à la place de celles du défilement : ⏯ pause/reprise (toucher le texte fait de même ; la reprise relit la phrase en cours depuis son début), ⏮ phrase précédente, ⏭ phrase suivante, ■ arrêt (le surlignage disparaît et les commandes du défilement reviennent). Lancer la voix met le défilement automatique en pause, et inversement. |
| TTS-6 | **Vitesse de la voix** de 0,5× à 2,0× par pas de 0,1 (affichée « 1,0× »), mémorisée. Un changement s'applique tout de suite en relisant la phrase en cours. |
| TTS-7 | **Appui long** (0,6 s sans bouger de plus de 10 px) sur un paragraphe d'un EPUB, ou sur une ligne d'un PDF, lance la lecture à partir de là. Un appui long ne compte pas comme un toucher (pas de lecture/pause), et n'ouvre pas le menu de sélection de texte d'iOS dans le lecteur. Un appui plus court, ou qui bouge, ne lance rien. Seul le doigt qui appuie compte : un autre doigt, une souris ou un trackpad ne l'annulent pas. |
| TTS-8 | **Minuterie de sommeil** : un bouton fait défiler Désactivée → 15 min → 30 min → 60 min → Fin du chapitre (EPUB seulement) → Désactivée, et affiche le temps restant. Quand elle arrive à échéance, la voix s'arrête à la fin de la phrase en cours. |
| TTS-9 | Pendant la lecture, l'écran reste allumé (comme DEF-8). Si l'app passe en arrière-plan ou si l'écran se verrouille, la lecture se met en pause (limite d'iOS pour les apps web) et reprend à la même phrase avec ⏯. |
| TTS-10 | Un PDF sans texte affiche « Ce PDF ne contient pas de texte à lire ». La position de lecture est enregistrée au fil de la voix (PROG-3). |
| TTS-11 | **Choix de la voix** dans le panneau Aa (absent sans synthèse vocale) : « Automatique » (TTS-3) puis les voix de la langue du livre, sans les voix fantaisie, triées par région demandée, puis qualité, puis nom ; chaque voix est libellée « Nom · Premium », « Nom · Améliorée » ou « Nom », suivie du pays s'il diffère (ex. « (Canada) »). Le choix est mémorisé et s'applique tout de suite en relisant la phrase en cours. Une voix choisie qui n'existe plus sur l'appareil revient à « Automatique ». Une aide rappelle que des voix plus naturelles se téléchargent gratuitement dans Réglages > Accessibilité > Contenu énoncé > Voix. |

## 6. Affichage (AFF)

| ID | Exigence |
|---|---|
| AFF-1 | Six thèmes : **Clair**, **Sépia**, **Vert reposant** (clairs) et **Sombre**, **Nuit**, **Nuit ambrée** (sombres). Ils s'appliquent à toute l'app, PDF compris : avec un thème sombre, les pages PDF sont inversées (teinte ambrée pour Nuit ambrée). |
| AFF-2 | EPUB : taille du texte de 13 à 34 px (19 par défaut) ; police Serif ou Sans. Ces réglages sont masqués pour les PDF. |
| AFF-3 | Changer la taille ou la police conserve la position de lecture (à 2 % près). |
| AFF-4 | Tous les réglages d'affichage sont mémorisés entre les sessions. |
| AFF-6 | Après une rotation de l'appareil (ou un redimensionnement de la fenêtre), la position de lecture est conservée à 1 % près, pour les EPUB comme pour les PDF (voir aussi PDF-4). |
| AFF-7 | **Mode immersif** : le texte occupe tout l'écran, y compris sous la barre d'état de l'iPhone (heure, batterie), qui devient transparente. Les barres de l'app se masquent pendant la lecture. *(Limite d'iOS : une app web ne peut pas masquer l'heure et la batterie.)* |
| AFF-8 | **Plein écran** : quand l'appareil le permet (iPad dans Safari, ordinateur) et que l'app n'est pas déjà installée en plein écran, un bouton ⛶ active ou quitte le plein écran. Sinon, ce bouton est absent. |
| AFF-9 | Lisibilité des nouveaux thèmes : le contraste texte/fond est d'au moins 7:1 (niveau AAA) pour chaque thème. **Nuit** : fond noir pur, texte gris clair atténué (contraste au plus 13:1, pour éviter l'éblouissement). **Nuit ambrée** : fond noir, texte ambre presque sans lumière bleue (composante bleue du texte au plus 40 % de la rouge). **Vert reposant** : fond vert pâle, texte vert foncé. |
| AFF-10 | **Automatique jour/nuit** : une option fait suivre au thème le mode clair/sombre de l'iPhone, en direct, sans recharger. Elle mémorise un thème de jour (par défaut Clair) et un thème de nuit (par défaut Nuit). Choisir un thème pendant que l'option est active remplace le thème de la période en cours. L'option et les deux thèmes sont mémorisés. |
| AFF-11 | Les curseurs (vitesse, barre de progression) restent visibles dans tous les thèmes : leur rail contraste d'au moins 3:1 avec le fond (critère WCAG pour les éléments d'interface), et le bouton du curseur est à la couleur d'accent du thème. |
| AFF-12 | **Pincement à deux doigts.** L'app elle-même ne zoome jamais : barres et boutons gardent leur taille, et l'app reste utilisable (zoom de la page bloqué : `maximum-scale=1` et gestes de Safari annulés). Dans un **EPUB**, pincer change la taille du texte en direct : taille de départ × (écart des doigts ÷ écart initial), arrondie et bornée comme le bouton A−/A+. La taille est mémorisée, et la position de lecture est conservée à 1 % près. Dans un **PDF**, pincer agrandit les pages de 100 % à 300 % (par pas de 5 %). Au-delà de 100 %, on glisse aussi de côté. La position verticale est conservée à 1 % près, et les pages sont redessinées nettes à la fin du geste. Le zoom est mémorisé. Un pincement ne compte ni comme un toucher (pas de lecture/pause), ni comme un appui long. Un redimensionnement qui ne change pas la taille de la fenêtre ne touche ni à la position ni aux pages. |
| AFF-5 | L'interface est utilisable sans défilement horizontal sur iPhone (375 px de large) comme sur iPad, en portrait et en paysage, en respectant les zones de sécurité (encoche, barre d'accueil). |

## 7. Hors connexion (OFF)

| ID | Exigence |
|---|---|
| OFF-1 | Après une première visite en ligne, l'app entière (code, bibliothèques, icônes) est en cache et démarre sans réseau. |
| OFF-2 | Les livres ne sont jamais envoyés sur le réseau. |
| OFF-3 | L'app est installable (manifeste, icônes, mode `standalone`). |

---

## Hors périmètre (pour l'instant)
Lecture à voix haute écran verrouillé ou en arrière-plan (impossible pour une app web sur iOS : nécessiterait une app native), voix neuronales en ligne, EPUB protégés par DRM, synchronisation entre appareils (prévue dans un second temps : le choix de la technique reste à faire), annotations, mise en page fixe (EPUB « fixed layout »).
