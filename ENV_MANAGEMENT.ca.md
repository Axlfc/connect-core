# Gestió de Variables d'Entorn
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/ENV_MANAGEMENT.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/ENV_MANAGEMENT.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/ENV_MANAGEMENT.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/ENV_MANAGEMENT.zh-cn.md)


Aquest projecte inclou diversos scripts per gestionar les variables d'entorn de forma intel·ligent i segura.

## 📁 Fitxers

- **`.env`** - Fitxer real amb els teus valors (NO fer commit a git)
- **`.env.example`** - Plantilla amb valors d'exemple (SÍ fer commit)
- **`generate_env_example.sh`** - Genera .env.example des de .env
- **`init_env.sh`** - Inicialitza .env des de .env.example

## 🚀 Inici Ràpid

### Primera vegada (nou usuari del projecte)

```bash
# 1. Inicialitzar el fitxer .env
./init_env.sh

# 2. L'script generarà automàticament valors segurs i et preguntarà pels opcionals
# Segueix les instruccions interactives

# 3. Revisa i ajusta si cal
nano .env

# 4. Inicia els serveis
./start.sh --voice
```

### Mode automàtic (CI/CD o scripting)

```bash
# Genera .env amb valors segurs sense interacció
./init_env.sh --auto

# Després configura les variables opcionals manualment
echo "TELEGRAM_BOT_TOKEN=el_teu_token" >> .env
echo "ZROK_AUTH_TOKEN=el_teu_token" >> .env
```

## 🔄 Flux de Treball per a Desenvolupadors

### Actualitzar .env.example després de canviar .env

```bash
# Genera .env.example preservant valors útils
./generate_env_example.sh

# Revisa els canvis
git diff .env.example

# Fes commit si està bé
git add .env.example
git commit -m "Update .env.example with new variables"
```

### Sincronitzar el teu .env amb noves variables

```bash
# Si algú ha afegit variables noves al projecte
git pull

# Actualitza el teu .env amb les noves variables
./init_env.sh
# Selecciona 'n' per no sobreescriure les existents
# O manualment:
cat .env.example >> .env
nano .env  # Elimina duplicats i configura les noves
```

## 🎯 Comportament de generate_env_example.sh

Aquest script és **intel·ligent** i preserva valors útils:

### ✅ Variables que ES PRESERVEN:

1. **Valors predefinits** (configuració tècnica):
   ```bash
   WHISPER_MODEL=base.en
   REDIS_PORT=6379
   POSTGRES_USER_ID=999
   ```

2. **Valors d'exemple** del .env.example existent:
   ```bash
   WEBHOOK_URL=http://localhost:5678
   ZROK_API_ENDPOINT=https://api.zrok.io
   ```

3. **Valors que semblen de documentació**:
   ```bash
   EXAMPLE_KEY=la_teva_clau_aqui
   TEST_VALUE=canvia_aixo
   ```

### 🔒 Variables que ES BUIDEN:

Variables sensibles (contenen aquests patrons):
- `*PASSWORD*`
- `*SECRET*`
- `*KEY*` (excepte predefinides)
- `*TOKEN*`
- `*AUTH*`
- `*JWT*`

```bash
# Abans a .env
POSTGRES_PASSWORD=el_meu_super_secret_123

# Després a .env.example
POSTGRES_PASSWORD=
```

## 📋 Exemples d'Ús

### Exemple 1: Configuració inicial del projecte

```bash
# Clonar repositori
git clone https://github.com/[EL_TEU_USUARI]/connect-core.git
cd connect-core

# Fer els scripts executables
chmod +x *.sh

# Inicialitzar entorn
./init_env.sh

# Sortida esperada:
# ✅ Còpia de seguretat creada: .env.backup.20250101_120000
# ℹ️  Fitxer .env creat des de .env.example
#
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Variable: N8N_ENCRYPTION_KEY
# Valor generat: 8f4e3c2b1a9d8e7f...
# Vols utilitzar aquest valor? (S/n/personalitzar): s
# ✅ N8N_ENCRYPTION_KEY configurat
```

### Exemple 2: Afegir una nova variable al projecte

```bash
# 1. Editar .env per a proves
echo "NEW_FEATURE_API_KEY=test_value_123" >> .env

# 2. Comprovar que funciona
./start.sh

# 3. Generar .env.example actualitzat
./generate_env_example.sh

# Sortida:
# 🔒 POSTGRES_PASSWORD (sensible - buidat)
# ✓ WHISPER_MODEL (preservat)
# 🔒 NEW_FEATURE_API_KEY (sensible - buidat)

# 4. Verificar el resultat
cat .env.example | grep NEW_FEATURE
# NEW_FEATURE_API_KEY=

# 5. Fer commit
git add .env.example
git commit -m "Add NEW_FEATURE_API_KEY configuration"
```

### Exemple 3: Afegir un nou valor predefinit

```bash
# Editar generate_env_example.sh
# Afegir a EXAMPLE_VALUES:

declare -A EXAMPLE_VALUES=(
    ...
    ["NEW_SERVICE_PORT"]="8888"
    ["NEW_SERVICE_HOST"]="0.0.0.0"
)

# Regenerar
./generate_env_example.sh

# Ara aquests valors es preservaran sempre
```

## 🔐 Generació de Valors Segurs

L'script `init_env.sh` utilitza aquests mètodes (per ordre de preferència):

1. **OpenSSL** (més comú):
   ```bash
   openssl rand -hex 32
   ```

2. **Python** (si openssl no està disponible):
   ```python
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

3. **Bash** (fallback):
   ```bash
   cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 64 | head -n 1
   ```

### Generar manualment

```bash
# Generar clau de 64 caràcters hex
openssl rand -hex 32

# Generar clau de 32 caràcters alfanumèrics
cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1
```

## 🛡️ Seguretat

### ✅ Bones Pràctiques

1. **MAI** facis commit del `.env` a git:
   ```bash
   # Verificar que està al .gitignore
   cat .gitignore | grep ".env"
   # Hauria de mostrar: .env
   ```

2. **SEMPRE** rota els secrets en producció:
   ```bash
   # Abans de fer deploy
   ./init_env.sh --auto
   # Configura manualment els serveis externs
   ```

3. **Còpia de seguretat** abans de regenerar:
   ```bash
   # Els scripts fan còpia de seguretat automàtica, però per si de cas:
   cp .env .env.backup.manual
   ```

4. **Revisar** els canvis abans de fer commit del .env.example:
   ```bash
   git diff .env.example
   ```

### ⚠️ Què NO fer

- ❌ Fer commit del `.env` amb valors reals
- ❌ Compartir el `.env` per correu/slack
- ❌ Utilitzar valors d'exemple en producció
- ❌ Reutilitzar contrasenyes entre serveis
- ❌ Posar secrets directament al codi (hardcode)

## 🔍 Resolució de Problemes

### Problema: "No es generen valors segurs"

```bash
# Verificar que tens les eines
which openssl
which python3

# Si no, instal·lar-les
# Ubuntu/Debian
sudo apt install openssl python3

# macOS
brew install openssl python3
```

### Problema: "Les variables no es preserven al .env.example"

```bash
# Veure quines variables s'estan processant
./generate_env_example.sh 2>&1 | grep "🔒\|✓\|∅"

# Si una variable s'hauria de preservar però es buida:
# 1. Verifica que no conté patrons sensibles (PASSWORD, SECRET, etc.)
# 2. O afegeix-la a EXAMPLE_VALUES a l'script
```

### Problema: ".env sobreescrit accidentalment"

```bash
# Restaurar des de la còpia de seguretat automàtica
ls -la .env.backup.*
cp .env.backup.YYYYMMDD_HHMMSS .env

# O des de git si s'havia fet commit (malament)
git checkout .env  # No ho facis si el .env és al .gitignore!
```

## 📚 Referència Ràpida

### Variables Requerides (han de tenir valor)

```bash
# Seguretat n8n
N8N_ENCRYPTION_KEY=
N8N_USER_MANAGEMENT_JWT_SECRET=
N8N_AUTH_JWT_SECRET=
N8N_RUNNERS_AUTH_TOKEN=

# Bases de dades
POSTGRES_PASSWORD=
REDIS_PASSWORD=

# Per a Forgejo
FORGEJO_DB_PASSWORD=
```

### Variables Opcionals

```bash
# Bot de Telegram
TELEGRAM_BOT_TOKEN=

# Túnel públic
ZROK_AUTH_TOKEN=

# Cerca web
MCP_BRAVE_API_KEY=
```

### Variables amb Valors Predefinits (no canviar)

```bash
WHISPER_MODEL=base.en
REDIS_PORT=6379
POSTGRES_PORT=5432
VOICE_GATEWAY_PORT=9000
```

## 🤝 Contribuir

En afegir noves variables:

1. Afegeix-les al `.env.example` amb:
   - Comentari descriptiu
   - Valor d'exemple o buit segons correspongui
   - Secció apropiada

2. Si és un valor tècnic (port, versió, etc.):
   ```bash
   # Afegir a EXAMPLE_VALUES a generate_env_example.sh
   ["NOVA_VARIABLE"]="valor_per_defecte"
   ```

3. Si és sensible:
   ```bash
   # No cal fer res, es detecta automàticament
   # pels patrons: PASSWORD, SECRET, TOKEN, KEY, AUTH
   ```

4. Documentar-ho al README principal

## 📞 Suport

Si tens problemes:

1. Revisa els logs dels scripts
2. Verifica que el `.env.example` està actualitzat
3. Executa `./debug_whisper.sh` per al diagnòstic
4. Obre un issue a GitHub

---

**Última actualització**: 2025-01-01
