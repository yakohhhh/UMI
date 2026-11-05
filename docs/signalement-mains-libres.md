# Signaler un danger sans toucher son téléphone

Note de conception · 24 octobre 2026 · réponses aux quatre questions posées sur le signalement en roulant, les faux positifs et les récompenses. Ce qui est décrit ici est maquetté dans le prototype (voir « Dans le prototype » à la fin).

## En bref

1. **Un bouton sur le Clip, pas de mot d'activation.** Un appui court pose un drapeau (lieu, heure, mesures du moment). Un appui long ouvre 4 secondes pour dire **un seul mot** (« obres », « bache », « blocked »…). Un double appui annule. Le Clip confirme par un bip et sa LED. Le téléphone reste dans la poche.
2. **Le « où » et le « quoi » sont séparés.** L'appui fixe le lieu et l'heure. Le contenu vient du mot dit, ou d'un tap après le trajet. Si le vent couvre la voix, rien n'est perdu.
3. **Un freinage brusque est un fait, sa cause est un contexte.** Le chien qui traverse n'est pas un faux positif : le freinage reste compté pour le carrefour, avec sa raison. Seul « c'était moi » sort des données de la rue.
4. **On récompense ce qui s'est passé, pas l'appui.** Pas de points à dépenser, pas de classement, pas d'argent par signalement. On montre l'impact (« 57 cyclistes prévenus », « réparé : confort 52 → 81 »), un niveau de confiance privé, et des remerciements rares et non annoncés.

## 1. Comment prévenir d'un danger en roulant

### Ce qu'on écarte : « UMI, record » en écoute permanente

| Problème | Détail |
| --- | --- |
| Langues | La reconnaissance de commandes hors ligne d'Espressif (MultiNet, sur notre ESP32-S3) ne connaît que l'anglais et le chinois. Rien en espagnol, catalan ou français. |
| Mot d'activation | « Hola UMI » demande un entraînement payant chez Espressif (2 à 3 semaines, 500+ locuteurs). Le catalan n'est pas proposé. « UMI » seul est trop court (3 à 6 syllabes recommandées). |
| Batterie | Écouter en continu garde le processeur et la PSRAM éveillés tout le trajet. Écouter seulement pendant l'appui coûte presque rien (~0,08 mAh par signalement). |
| Vent | À 20-30 km/h, le bruit du vent sur un micro de guidon couvre souvent une voix forte. Les mousses ne récupèrent que 9 à 16 dB. |
| Confiance | « Un micro qui écoute » contredit notre promesse actuelle et attirerait l'attention de l'AEPD. La voix est une donnée biométrique pour le CEPD. |

Même Waze (2025, avec Gemini) demande un tap avant de parler. Garmin demande environ 4 taps sur l'écran.

### Ce qu'on propose : un bouton étanche sur le Clip

| Geste | Effet | Retour |
| --- | --- | --- |
| Appui court | Pose un drapeau : heure, position GNSS, instantané IMU et dB(A) | 1 bip court + flash orange |
| Appui long (~1 s) | Ouvre 4 s pour dire un mot (option « Voice keywords », désactivée par défaut) | LED orange qui pulse, puis 2 bips montants si le mot est compris, 1 bip grave sinon (le drapeau est gardé) |
| Double appui | Annule le dernier drapeau | 2 bips courts |

- **Le retour se fait sur le Clip.** Depuis le RD 518/2026 (art. 18.2 du RGC, en vigueur depuis le 1er octobre 2026), les cyclistes et trottinettes n'ont droit ni au téléphone ni à aucun type d'écouteurs. Pas d'audio dans les oreilles, donc : bip piézo (2-4 kHz, au-dessus du vent) et LED, jamais la couleur seule (le nombre de bips compte).
- **Vocabulaire de départ : 5 types + « annuler ».** Travaux, nid-de-poule, voie bloquée, obstacle, danger, en catalan, espagnol et anglais (le français ensuite). On n'élargit qu'après avoir mesuré les confusions.
- **Confidentialité.** L'audio reste quelques secondes dans la RAM du Clip, n'est jamais écrit en mémoire, jamais envoyé. Seuls sortent : le mot reconnu, la confiance, l'heure, la position. Pas d'identification du locuteur. On remplace « never records audio » par **« audio never leaves the Clip and is never stored »**, qui reste vrai.
- **Trottinettes.** On conseille « appuyez à l'arrêt » et la qualification après le trajet : lâcher une main sur petites roues est plus risqué.
- **Coureurs.** Même bouton. Ils sont piétons au sens du code : ils peuvent aussi utiliser Siri avec des écouteurs (raccourci d'app, plus tard).

### À valider avant de promettre la voix

1. **Composants :** vérifier que le Clip a 8 Mo de PSRAM et 16 Mo de flash. Sans PSRAM, la voix exige une nouvelle révision matérielle, pas une mise à jour.
2. **Terrain :** prototype en anglais (MultiNet7) sur carte de dev avec le micro et le boîtier du Clip. Mesurer la précision à 0, 15, 25 et 30 km/h. On ne lance la voix qu'à ≥ 90 % de précision à 20 km/h et < 1 fausse détection pour 100 fenêtres.
3. **Production :** modèle de mots-clés maison (ESP-DL ou TFLite Micro) entraîné sur Common Voice ES/CA/EN + bruit de vent et de circulation enregistré à Barcelone.
4. **Acoustique :** ouverture du micro à l'arrière ou dessous, membrane IP54 + mousse, filtre passe-haut 200-300 Hz.
5. **Juridique :** faire confirmer par un avocat qu'un bouton ou une commande vocale sur le Clip n'est pas « un autre système de communication » au sens de l'art. 18.2. L'exception vise la communication « sans employer les mains » : le bouton utilise une main, la voix sans appui serait plus proche de l'exception. C'est exactement la question à poser.
6. **Coût :** bouton étanche + nouvel outillage du boîtier + buzzer piézo. Chiffrer, et revérifier les 38 g et l'autonomie « une semaine de trajets ».

## 2. Pourquoi l'utilisateur prendrait la peine de signaler

Il le fait d'abord pour lui. Laia passe 168 fois par mois sur le Passeig de Sant Joan : la réparation profite d'abord à son propre trajet.

| Pour le cycliste | Pour la ville |
| --- | --- |
| Sa rue réparée, avec la preuve (« confort 52 → 81 ») | Des signalements dédupliqués, vérifiés, priorisés |
| Son itinéraire « Calmest » évite les dangers vérifiés | Les quasi-accidents, que les données officielles ne voient pas |
| Son rapport de trajet s'explique (« pourquoi ce freinage ? ») | Une détection plus précoce que les canaux classiques |
| Prévenir ses amis et son club sur les trajets partagés | La preuve objective qu'une intervention a marché |

**Le levier le plus fort est de boucler la boucle.** Sur FixMyStreet (399 364 utilisateurs), ceux dont le premier signalement a obtenu une réponse étaient 57 % plus nombreux à en faire un second. C'est une corrélation, pas une preuve de causalité, mais tous les autres signaux vont dans le même sens. Il faut donc :

- une notification « Réparé » avec la preuve mesurée par les Clips ;
- un flux de statut IRIS (reçu, attribué, clôturé) dans le contrat du pilote avec l'Ajuntament ;
- des retours que UMI contrôle seul, pour quand la ville ne répond pas : « vérifié par 4 cyclistes », « 57 prévenus ».

**Comment les autres sont prévenus.** Avant le trajet (carte, itinéraires) et, en option, par 2 bips graves du Clip à l'approche d'un danger vérifié. Les alertes de danger vérifié sont **gratuites pour tous**. Les mettre dans Premium réduirait l'impact visible du signalement, donc l'envie de signaler.

### Ce qu'on demande après le trajet

- **2 questions maximum par trajet**, choisies parmi les événements ambigus ou à forte valeur, plus chaque drapeau posé sans mot. Un tap, moins de 10 secondes, on peut passer.
- **Jamais en roulant :** une fois le trajet terminé et l'utilisateur arrêté depuis 2 min, ou à la prochaine ouverture de l'app. Pas de notification après le trajet du matin (taux de réponse au plus bas entre 7 h 30 et 9 h) : une carte dans le rapport suffit.
- Sans réponse, l'événement compte à **moitié** dans le score de sécurité.

## 3. Les « faux positifs » qui n'en sont pas

Un capteur fixé détecte bien qu'il y a eu un freinage. Il ne sait pas pourquoi. On ne supprime donc jamais un freinage pour sa cause : la réponse décide **où il compte**.

| Réponse (un tap) | Catégorie | Ce que ça devient |
| --- | --- | --- |
| Un véhicule a coupé · Quelqu'un a traversé · **Un animal** · Portière | Circulation | Reste dans le score de sécurité du carrefour, avec sa raison |
| Voie bloquée · Revêtement · Travaux · Carrefour ou feu | Problème de rue | Part dans la liste de maintenance de la ville quand 5 cyclistes sont d'accord |
| C'était moi | Personnel | Reste dans le trajet de l'utilisateur, sort des scores de rue et des données de la ville |
| Pas de réponse | — | Compte à moitié |

Le chien est un vrai signal. Des freinages « animal » répétés au même endroit (une sortie de parc, la promenade du Passeig de Sant Joan) sont un problème d'aménagement. Dans le prototype, 10 % des freinages expliqués à Verdaguer sont dus à des animaux.

« Accrochage serré » (close pass) n'est volontairement pas dans la liste : le Clip ne peut pas le détecter seul, il ne déclenche pas de freinage.

### Cycle de vie d'un drapeau

```
appui ─▶ en attente (vous seul)
        ─▶ vérifié (3+ cyclistes différents, y compris les Clips qui confirment passivement) ─▶ visible sur la carte de tous
        ─▶ envoyé à la ville (5+ cyclistes) ─▶ City Insights + export IRIS
        ─▶ réparé (les Clips mesurent la différence)  ou  disparu (des cyclistes sont passés, plus rien)
```

**Durées de vie :**

| Type | Durée de vie |
| --- | --- |
| Obstacle | 2 h sans nouvelle confirmation |
| Travaux | Jusqu'à ce que les cyclistes disent que c'est fini, revérifié à 14 jours |
| Nid-de-poule | Jusqu'à ce que les Clips ne sentent plus l'impact |
| Voie bloquée | Motif par tranche horaire, s'efface après 30 jours |
| Danger | Rejoint le score de sécurité du carrefour, s'efface après 30 jours |

**Notre atout face aux applis téléphone :** les autres Clips qui passent confirment ou font expirer un danger avec leurs capteurs, sans aucun tap.

## 4. Comment récompenser

Les études vont toutes dans le même sens :

- **Récompense matérielle attendue :** elle réduit la motivation intrinsèque (méta-analyse Deci, Koestner et Ryan 1999, 128 expériences). Nuance : les récompenses inattendues ne le font pas. Signaler des nids-de-poule n'est pas passionnant en soi : le vrai risque est le manque de motivation, plus que l'effet d'éviction.
- **Retour positif :** il augmente la motivation (d = +0,33).
- **Points et classements :** ils augmentent le volume, pas la qualité.

| Couche | Ce que c'est | Ce que ça débloque |
| --- | --- | --- |
| **Impact** (visible) | Cyclistes prévenus, drapeaux vérifiés, réparations, réponses données | Rien à dépenser : c'est la preuve d'utilité |
| **Confiance** (privée, 0 à 10, aucun classement) | Monte avec les drapeaux vérifiés par d'autres et les « toujours là ? » confirmés par les capteurs | Au niveau 7 : les Clips qui passent revérifient ses drapeaux en priorité. Au niveau 8 : « Street steward » de ses rues, peut lever seul un danger. Les seuils de 3 et 5 cyclistes ne changent jamais |
| **Merci** (rare, non annoncé) | Un mois Premium, une révision chez un vélociste partenaire, toujours avec l'option « donner à une cause » | Jamais présenté comme un barème |

**Règles anti-triche :**

- **Toutes les réponses rapportent pareil**, « c'était moi » compris. En fait elles ne rapportent rien en elles-mêmes, donc personne n'a intérêt à exagérer. Le crédit vient seulement des drapeaux vérifiés et des vérifications confirmées par les capteurs. Pas par la majorité : ça évite l'effet mouton.
- **Identité liée au Clip, avec signature matérielle.** Un numéro de série envoyé en Bluetooth se copie. Il faut que chaque Clip signe ses rapports avec une clé non extractible (périphérique de signature et eFuse de l'ESP32-S3 + secure boot).
- **Plausibilité :** un signalement ne compte que si le cycliste roulait sur ce segment. Un seul par danger et par cycliste, avec un plafond quotidien.
- **Diversité :** des confirmateurs qui ne roulent pas toujours ensemble (contre les flottes de livreurs ou un club qui s'entendrait). Audit d'un échantillon aléatoire.
- **Badges de résultat** plutôt que de volume : « Fixed it : 3 drapeaux réparés » plutôt que « 50 signalements ».

**Financement réaliste, dans l'ordre :**

1. Retours d'impact (quasi gratuits).
2. Mois Premium non annoncés (coût marginal nul, top 5-10 % par quartier).
3. Vélocistes partenaires (5 à 10 pour commencer, qui sont aussi notre canal de vente).
4. Programmes au km financés par les employeurs (plans de mobilité de la Ley 9/2025, date limite à vérifier au BOE) ou par la ville, où UMI fournit des trajets vérifiés sans jamais payer elle-même au km.

## Confidentialité, en une ligne par règle

- City Insights ne reçoit un danger qu'à partir de **5 cyclistes différents** (c'est notre promesse k ≥ 5 actuelle). La carte des cyclistes à partir de 3.
- Dates au jour près, jamais d'heure par événement, jamais qui a signalé.
- Répartition des causes arrondie à 10 %, causes sous 10 % regroupées en « autre », « c'était moi » exclu.
- Drapeaux dans les 200 m de début et de fin de trajet : exclus des données ville (comme les traces aujourd'hui).
- Faire une analyse d'impact (AIPD) avant de lancer la voix. La confiance est un profilage au sens du RGPD : à déclarer.

## Ce qui reste à trancher

- **Densité :** avec ~600 Clips au lancement, combien de dangers éphémères (un obstacle vit 2 h) seront croisés par 3 cyclistes à temps ? Sinon, le premier signaleur n'a jamais de retour. Piste : confirmation passive par capteurs, et retour « 57 prévenus » qui ne dépend pas de la vérification.
- **Mineurs :** consentement parental sous 14 ans (LOPDGDD art. 7). Pas de récompenses ciblant les mineurs.
- **Langues :** l'app est en anglais. Le Codi de consum de Catalunya impose le catalan pour l'information au consommateur.
- **Responsabilité :** si une rue est affichée « calme » à tort. La nouvelle directive européenne sur les produits défectueux couvre le logiciel et le firmware.
- **EU Data Act :** pour un objet connecté mis sur le marché après le 12 septembre 2026, il faut l'accès aux données dès la conception et un contrat pour revendre des données non personnelles à la ville.
- **IRIS :** vérifier que l'Ajuntament expose une API de statut. La notification « Réparé » en dépend.

## Dans le prototype

| Où | Quoi |
| --- | --- |
| `/app/activities/laia-20261015-0752` | « 2 moments to check » : le freinage de 07:59 à Verdaguer (« Why did you brake? ») et le drapeau de 08:07 posé sans mot (« What was it? »). Le drapeau vocal « roadworks » de 08:02 est vérifié par 4 cyclistes. |
| `/app/activities/laia-20261014-0754` | Le freinage expliqué « An animal » : il reste compté pour le carrefour. |
| `/app/profile#contributions` | Impact, niveau de confiance privé, historique des drapeaux avec leur statut et la preuve de réparation. |
| `/app/profile#clip` | Le bouton du Clip : appui, appui long, double appui, mots-clés vocaux (désactivés par défaut), bip, alerte à l'approche. |
| `/app/map` | Couche « Rider flags » (dangers vérifiés par 3+ cyclistes). |
| `/city/safety` | « Why riders brake » par carrefour (5+ cyclistes) et « Flagged by riders » avec export IRIS. |

Code : règles dans `src/lib/reports.ts`, données de démo dans `src/lib/mock/flags.ts`, types dans `src/lib/types.ts`.

## Sources principales (vérifiées)

- Espressif ESP-SR : [commandes](https://docs.espressif.com/projects/esp-sr/en/latest/esp32s3/speech_command_recognition/README.html) (MultiNet : EN et CN uniquement), [mots d'activation personnalisés](https://docs.espressif.com/projects/esp-sr/en/latest/esp32s3/wake_word_engine/ESP_Wake_Words_Customization.html), [benchmarks mémoire et précision](https://docs.espressif.com/projects/esp-sr/en/latest/esp32s3/benchmark/README.html).
- Code de la route : [RGC consolidé, art. 18.2](https://www.boe.es/buscar/act.php?id=BOE-A-2003-23514), modifié par le [RD 518/2026](https://www.boe.es/boe/dias/2026/06/26/pdfs/BOE-A-2026-13889.pdf).
- CEPD : [lignes directrices sur les assistants vocaux](https://www.edpb.europa.eu/system/files/2021-07/edpb_guidelines_202102_on_vva_v2.0_adopted_en.pdf).
- Waze : [signalement conversationnel](https://9to5google.com/2025/10/06/waze-conversational-reporting-voice-command-feature/) (un tap avant de parler).
- FixMyStreet : [Sjoberg, Mellon et Peixoto 2017](https://ora.ox.ac.uk/objects/uuid:2bd169fd-0b27-46e4-8b81-1ccfccf7c55a), +57 %, observationnel.
- Récompenses : [Deci, Koestner et Ryan 1999](https://home.ubalt.edu/ntygmitc/642/Articles%20syllabus/Deci%20Koestner%20Ryan%20meta%20IM%20psy%20bull%2099.pdf) ; [Mellström et Johannesson 2008](https://swopec.hhs.se/gunwpe/abs/gunwpe0180.htm) (don du sang, effet chez les femmes seulement, petit échantillon).
- Quasi-accidents : [SimRa, TU Berlin](https://arxiv.org/pdf/2006.08481v1) (détection automatique + qualification après le trajet, le modèle le plus proche du nôtre) ; [Near Miss Project, Aldred](https://road.cc/content/news/154392-cyclists-experience-scary-near-miss-once-week-according-study).
