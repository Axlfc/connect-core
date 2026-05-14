# Guia de Recuperació davant Desastres (Disaster Recovery)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/DISASTER_RECOVERY.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/DISASTER_RECOVERY.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/DISASTER_RECOVERY.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/DISASTER_RECOVERY.zh-cn.md)


## 1. Introducció

Aquest document descriu l'estratègia de còpies de seguretat i els procediments de restauració per a l'stack `connect-core`. L'objectiu és assegurar la integritat i disponibilitat de les dades crítiques en cas d'una fallada del sistema, corrupció de dades o qualsevol altre esdeveniment catastròfic.

L'estratègia es basa en l'ús de **Duplicati**, un client de còpies de seguretat de codi obert que s'executa com un contenidor dins de l'stack.

## 2. Accés a Duplicati

La interfície web de Duplicati està disponible al següent `URL`:

- **URL:** `http://duplicati.localhost` (o el domini que hagis configurat)
- **Accés:** Protegit per Authelia. Hauràs d'iniciar sessió amb les teves credencials.

## 3. Configuració d'un Treball de Còpia de Seguretat

A continuació, es detalla el procediment per crear un treball de còpia de seguretat per a les dades més crítiques del sistema.

### Pas 1: Afegir una nova còpia de seguretat

1.  A la interfície de Duplicati, fes clic a **"Add backup"**.
2.  Selecciona **"Configure a new backup"** i fes clic a "Next".

### Pas 2: Configuració general

1.  **Name:** Assigna un nom descriptiu (ex. "connect-core Critical Data").
2.  **Encryption:** Es recomana encaridament **habilitar el xifratge**. Selecciona "AES-256 encryption, built-in" i genera una contrasenya segura. **Guarda aquesta contrasenya en un lloc segur! Sense ella, no podràs restaurar les teves dades.**
3.  Fes clic a "Next".

### Pas 3: Destí de la còpia de seguretat

1.  **Storage Type:** Tria on vols emmagatzemar les teves còpies de seguretat. Duplicati suporta una gran varietat de destins, com `SFTP`, `WebDAV`, `Google Drive`, `Amazon S3`, etc.
2.  **Local folder or drive:** Per a aquest exemple, utilitzarem un directori local al `host`. La ruta dins del contenidor que apunta a un directori al `host` és `/backups`.
    - **Path:** `/backups`
3.  Configura les credencials o la informació de connexió necessària per al teu destí triat.
4.  Fes clic a **"Test connection"** per verificar que Duplicati pot accedir al destí.
5.  Fes clic a "Next".

### Pas 4: Dades d'origen

1.  Aquesta és la part més important. Aquí seleccionaràs els directoris que vols protegir. Les dades dels serveis de Docker es troben al directori `/source` dins del contenidor de Duplicati.
2.  Expandeix l'arbre de directoris i selecciona els següents volums, que contenen les dades més crítiques:
    - `postgres_storage`
    - `n8n_storage`
    - `forgejo_data`
    - `redis_data`
    - `qdrant_storage`
    - `matrix_data`
    - `authelia` (per a la configuració d'usuaris)
3.  Fes clic a "Next".

### Pas 5: Programació

1.  Defineix amb quina freqüència vols que s'executin les còpies de seguretat. Es recomana una còpia de seguretat **diària**.
2.  Selecciona una hora en què el sistema tingui poca càrrega (ex. 3:00 AM).
3.  Fes clic a "Next".

### Pas 6: Opcions de la còpia de seguretat

1.  **Remote volume size:** Ajusta la mida dels volums de la còpia de seguretat. Un valor de `50 MB` és un bon punt de partida.
2.  **Backup retention:** Defineix quant de temps vols conservar les còpies de seguretat. Es recomana **"Keep a specific number of backups"** i establir un valor com `14` per tenir dues setmanes d'historial.
3.  Fes clic a **"Save"**.

## 4. Procediment de Restauració

En cas que necessitis restaurar les dades, segueix aquests passos:

### Pas 1: Aturar els serveis

Abans de restaurar, és crucial aturar tots els serveis per evitar inconsistències en les dades.

```bash
./stop.sh
```

### Pas 2: Accedir a la restauració a Duplicati

1.  Obre la interfície de Duplicati.
2.  Fes clic en el treball de còpia de seguretat que vols restaurar.
3.  Fes clic a **"Restore"**.

### Pas 3: Seleccionar els fitxers a restaurar

1.  Selecciona la data de la còpia de seguretat que vols restaurar.
2.  Pots restaurar tots els fitxers o seleccionar directoris específics. Per a una recuperació completa, selecciona tots els directoris.
3.  Fes clic a "Continue".

### Pas 4: Opcions de restauració

1.  **Restore to original location:** Selecciona aquesta opció per restaurar els fitxers als seus directoris originals.
2.  **Overwrite:** Selecciona "Overwrite" per reemplaçar qualsevol fitxer existent (corrupte) amb la versió de la còpia de seguretat.
3.  Fes clic a **"Restore"**.

### Pas 5: Verificar i reiniciar els serveis

1.  Una vegada que la restauració s'hagi completat, verifica que els fitxers s'han restaurat correctament als volums de Docker al `host`.
2.  Reinicia l'stack de `connect-core`.

```bash
./start.sh
```

## 5. Conclusió

Aquesta guia proporciona els passos fonamentals per assegurar i restaurar les dades de `connect-core`. És responsabilitat de l'administrador del sistema assegurar-se que les còpies de seguretat es configurin correctament, s'executin de forma regular i es provin periòdicament.
