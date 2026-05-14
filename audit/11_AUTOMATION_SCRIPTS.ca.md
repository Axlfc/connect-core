# AUDIT 11: SCRIPTS D'AUTOMATITZACIÓ
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/11_AUTOMATION_SCRIPTS.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/11_AUTOMATION_SCRIPTS.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/11_AUTOMATION_SCRIPTS.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/11_AUTOMATION_SCRIPTS.zh-cn.md)


**Data:** 2024-07-25
**Analista:** Jules

## 1. Resum de Troballes

| Estat | Àrea | Resum de Troballes |
| :--- | :--- | :--- |
| ✓ | **Robustesa i Usabilitat** | Els scripts principals (`start.sh`, `stop.sh`, `init_env.sh`) són **excepcionalment robustos i fàcils d'utilitzar**. Inclouen gestió d'errors (`set -e`), sortida de text amb colors, missatges d'ajuda clars i gestió de paràmetres per a diferents entorns. |
| ✓ | **Seguretat en la Destrucció de Dades** | L'script `stop.sh` implementa una **mesura de seguretat crítica** en requerir una confirmació explícita de l'usuari (`type 'yes'`) abans d'executar l'acció destructiva d'eliminar volums, prevenint la pèrdua accidental de dades. |
| ⚠️ | **Manipulació Directa de Fitxers `.env`** | L'script `start.sh` modifica directament el fitxer `.env` per actualitzar la `WEBHOOK_URL` de Zrok. Tot i que és funcional, la modificació programàtica de fitxers de configuració sensibles és una pràctica que s'ha de gestionar amb molta cura. |
| ⚠️ | **Potencial Fuga d'Informació** | L'script `start.sh` utilitza `docker inspect` per als health checks. En cas d'error, aquesta ordre pot bolcar tota la configuració del contenidor a la consola, incloent variables d'entorn que podrien ser sensibles. |
| ✗ | **Falta de Validació d'Entrades** | L'script `init_env.sh`, en el seu mode interactiu, no saneja ni valida les entrades de l'usuari per als valors de les variables. Un usuari podria injectar accidentalment o maliciosament caràcters especials o ordres que podrien corrompre el fitxer `.env` o ser interpretades pel shell. |

---

## 2. Troballes Detallades

### ✓ El que està bé

1.  **Gestió d'Errors (`set -e`):**
    *   Tots els scripts principals comencen amb `set -e`. Aquesta és una de les millors pràctiques més importants en scripting de shell, ja que assegura que l'script falli immediatament si una ordre retorna un codi de sortida diferent de zero, evitant comportaments inesperats o perillosos.

2.  **Scripts de Cicle de Vida Clars:**
    *   La separació de responsabilitats entre `start.sh`, `stop.sh`, `init_env.sh`, `setup-permissions.sh`, etc., és molt clara. Cada script té un propòsit ben definit, cosa que facilita enormement el manteniment i la comprensió del sistema.

3.  **Lògica de Neteja Robusta:**
    *   L'script `stop.sh` no només executa `docker compose down`, sinó que també realitza una neteja explícita de contenidors (`docker rm -f`) i xarxes. Això ajuda a prevenir l'acumulació de recursos orfes de Docker, un problema comú en entorns de desenvolupament complexos.

### ✗ Problemes Trobats

| ID | Severitat | Problema | Impacte |
| :- | :--- | :--- | :--- |
| **AS-01** | **BAIXA** | **Falta de Sanejament d'Entrades a `init_env.sh`** | En el mode interactiu, un usuari pot introduir qualsevol cadena de text com a valor per a una variable. Si introdueixen `valor; rm -rf /`, tot i que en aquest cas només corrompria el fitxer `.env`, és una mala pràctica no validar o escapar les entrades. |
| **AS-02** | **BAIXA** | **Modificació Directa del `.env` per `start.sh`** | L'script `start.sh` usa `sed` per actualitzar la `WEBHOOK_URL`. Si el format del fitxer `.env` canviés o si el valor de l'URL contingués caràcters especials que `sed` interpreta, podria corrompre el fitxer. |

---

### ⚠️ Avisos/Recomanacions

1.  **Idempotència:**
    *   Els scripts són majoritàriament idempotents (es poden executar diverses vegades sense efectes secundaris negatius), però la lògica de còpia de seguretat a `init_env.sh` crea un nou fitxer de backup cada vegada, cosa que podria portar a l'acumulació de molts fitxers de backup. Es podria millorar perquè només es creï un backup si el fitxer `.env` ha canviat.

2.  **Complexitat de les ordres `docker compose`:**
    *   Les ordres `docker compose` a `start.sh` i `stop.sh` són bastant complexes a causa de la gestió de múltiples perfils.
        ```bash
        docker compose -f "$COMPOSE_FILE" --profile "$PROFILE" $([ "$ENABLE_VOICE" = true ] && echo "--profile voice" || [ "$PROFILE" = "cpu" ] && [ "$ENABLE_VOICE" = true ] && echo "--profile voice-cpu") up -d ...
        ```
    *   **Recomanació:** Per millorar la llegibilitat, aquesta lògica podria ser refactoritzada en una funció o una variable.
        ```bash
        # Exemple de refactorització
        PROFILES_TO_RUN=("--profile" "$PROFILE")
        if [ "$ENABLE_VOICE" = true ]; then
            if [ "$PROFILE" = "cpu" ]; then
                PROFILES_TO_RUN+=("--profile" "voice-cpu")
            else
                PROFILES_TO_RUN+=("--profile" "voice")
            fi
        fi
        docker compose -f "$COMPOSE_FILE" "${PROFILES_TO_RUN[@]}" up -d
        ```

---

### 🔧 Solucions Suggerides

1.  **Per a AS-01 (Validació d'Entrades):**
    *   **Solució:** Afegir una validació simple a `init_env.sh` per assegurar que els valors introduïts no continguin caràcters perillosos. Es poden envoltar les variables en cometes per a major seguretat.
        ```bash
        # A la secció de 'personalitzar' de init_env.sh
        echo -n "Introdueix el valor per a $var: "
        read -r new_value
        # Validar que no conté caràcters problemàtics (ex. punt i coma, salts de línia)
        if [[ "$new_value" =~ [;\n] ]]; then
            print_error "El valor conté caràcters no permesos."
            continue
        fi
        # Utilitzar cometes en escriure al fitxer
        sed -i "s|^${var}=.*|${var}=\"${new_value}\"|" "$TARGET_FILE"
        ```

2.  **Per a AS-02 (Modificació Segura del `.env`):**
    *   **Solució:** Utilitzar un enfocament més segur que no depengui de `sed` per parsejar el fitxer. Una alternativa és llegir el fitxer línia per línia, modificar la línia desitjada en memòria i després reescriure el fitxer complet.
        ```bash
        # Lògica millorada a start.sh
        TEMP_ENV=$(mktemp)
        while IFS= read -r line; do
            if [[ "$line" == WEBHOOK_URL=* ]]; then
                echo "WEBHOOK_URL=$FULL_WEBHOOK_URL" >> "$TEMP_ENV"
            else
                echo "$line" >> "$TEMP_ENV"
            fi
        done < "$ENV_FILE"
        mv "$TEMP_ENV" "$ENV_FILE"
        ```
    *   Aquest enfocament és més resistent a errors de format i a caràcters especials.
