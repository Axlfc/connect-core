# AUDIT 13: DEPÈNDENCIES I LLIBRERIES
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/13_DEPENDENCIES_AND_LIBRARIES.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/13_DEPENDENCIES_AND_LIBRARIES.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/13_DEPENDENCIES_AND_LIBRARIES.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/13_DEPENDENCIES_AND_LIBRARIES.zh-cn.md)


**Data:** 2024-07-25
**Analista:** Jules

## 1. Resum de Troballes

| Estat | Àrea | Resum de Troballes |
| :--- | :--- | :--- |
| ✓ | **Ús d'Eines Estàndard** | El projecte utilitza gestors de paquets estàndard de la indústria (`pip` per a Python, `npm`/`pnpm` per a Node.js), la qual cosa facilita la gestió i auditoria de les depèndencies. |
| ✗ | **Depèndencies No Fixades (Unpinned)** | **CRÍTIC:** Múltiples fitxers `requirements.txt` i Dockerfiles **no fixen les versions** de les depèndencies que instal·len. Això porta a builds no reproduïbles i crea un risc significatiu que una nova versió d'una llibreria introdueixi una vulnerabilitat o un canvi disruptiu. |
| ✗ | **Falta d'Escaneig de Vulnerabilitats** | No hi ha evidència que s'utilitzi cap eina per escanejar les depèndencies (ex. `pip-audit`, `npm audit`, `snyk`, `trivy`) a la recerca de vulnerabilitats conegudes (CVEs). |
| ⚠️ | **Ús de Depèndencies "Nightly"** | El `Dockerfile.comfyui` instal·la versions "nightly" de PyTorch. Aquestes versions són inestables per definició, no estan pensades per a producció, i poden contenir bugs o vulnerabilitats no descobertes. |
| ⚠️ | **Falta de `package-lock.json`** | El servei `ollama-proxy` (Node.js) no inclou un fitxer `package-lock.json` al repositori. Això significa que les versions exactes de les depèndencies transitives no estan garantides, soscavant la reproduïabilitat. |

---

## 2. Troballes Detallades

### ✓ El que està bé

1.  **Gestió Centralitzada:**
    *   Cada component (ex. `voice-gateway`, `ollama-proxy`) té el seu propi fitxer de depèndencies (`requirements.txt`, `package.json`), la qual cosa és una bona pràctica que aïlla els entorns.

### ✗ Problemes Trobats

| ID | Severitat | Problema | Impacte |
| :- | :--- | :--- | :--- |
| **DEP-01** | **CRÍTIC** | **Versions No Fixades a `requirements.txt`** | El fitxer `voice-gateway/requirements.txt` llista depèndencies com `fastapi` o `redis` sense especificar una versió. `pip install -r requirements.txt` instal·larà l'última versió disponible en aquell moment, la qual cosa pot variar dia a dia, fent impossible garantir un build estable i segur. |
| **DEP-02** | **ALT** | **Ús de Versionat Flexible (`^`) a `package.json`** | L' `ollama-proxy/package.json` utilitza `^` per a les seves depèndencies (ex. `"express": "^4.18.2"`). Tot i que això prevé canvis majors (versió 5.x), continua permetent actualitzacions menors (ex. 4.19.0) que podrien introduir regressions o vulnerabilitats. L'absència d'un `package-lock.json` agreuja aquest problema. |
| **DEP-03** | **ALT** | **Depèndencies "Nightly" a `Dockerfile.comfyui`** | El Dockerfile instal·la PyTorch directament des d'un índex de `nightly`. Això és inacceptable per a un entorn de producció, ja que aquestes builds no tenen cap garantia d'estabilitat o seguretat. |

---

### ⚠️ Avisos/Recomanacions

1.  **Auditoria de Llicències:**
    *   No hi ha un procés per auditar les llicències de les depèndencies. Això podria suposar un risc legal si una llibreria amb una llicència restrictiva (com AGPL) s'utilitzés sense complir els seus termes.

2.  **Depèndencies del Sistema Operatiu:**
    *   Els Dockerfiles instal·len depèndencies del SO a través d' `apt-get` o `apk`. Aquestes depèndencies també haurien de ser auditades i, si és possible, fixades a una versió específica si el gestor de paquets ho permet.

---

### 🔧 Solucions Suggerides

1.  **Per a DEP-01 (Fixar Versions a `requirements.txt` - CRÍTIC):**
    *   **Solució:** Utilitzar una eina com `pip-tools` per gestionar les depèndencies de Python de forma robusta.
        1.  **Crear un fitxer `requirements.in`:**
            ```
            # voice-gateway/requirements.in
            fastapi
            uvicorn
            httpx
            redis
            python-multipart
            ```
        2.  **Generar `requirements.txt`:**
            ```bash
            # Instal·lar pip-tools
            pip install pip-tools
            # Compilar el fitxer de requeriments
            pip-compile voice-gateway/requirements.in > voice-gateway/requirements.txt
            ```
        3.  **Resultado:** El `requirements.txt` generat contindrà les versions exactes de totes les depèndencies i les seves depèndencies transitives, amb hashes per verificar la integritat.
            ```
            # via -r requirements.in
            fastapi==0.109.2
            # ... (totes les altres depèndencies amb versions exactes i hashes)
            ```

2.  **Per a DEP-02 (Fixar Versions a `package.json`):**
    *   **Solució:**
        1.  **Eliminar els `^`:** Reemplaçar `^x.y.z` amb `x.y.z` per a totes les depèndencies a `package.json`.
        2.  **Generar i fer commit del Lock File:** Executar `npm install` localment i afegir el fitxer `package-lock.json` resultant al repositori. Això garantirà que sempre s'instal·lin les mateixes versions exactes de totes les depèndencies.

3.  **Per a DEP-03 (Eliminar Depèndencies "Nightly"):**
    *   **Solució:** Modificar `Dockerfile.comfyui` perquè utilitzi l'última **versió estable** de PyTorch que sigui compatible amb el maquinari de destí.
        ```diff
        # A Dockerfile.comfyui
        -      --index-url https://download.pytorch.org/whl/nightly/cu128
        +      --index-url https://download.pytorch.org/whl/cu128
        ```
    *   Fixar la versió de PyTorch a un número específic és encara millor.

4.  **Implementar Escaneig de Vulnerabilitats:**
    *   **Solució:** Integrar eines d'escaneig en el procés de CI/CD.
        *   **Per a Python:** Afegir un pas que executi `pip-audit`.
        *   **Per a Node.js:** Afegir un pas que executi `npm audit --audit-level=high`.
        *   **Per a Imatges Docker:** Utilitzar una eina com `Trivy` o `Grype` per escanejar les imatges construïdes a la recerca de vulnerabilitats tant a les depèndencies del SO com a les de l'aplicació.
