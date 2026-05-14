# Contribuir a connect-core 🤝
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/CONTRIBUTING.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/CONTRIBUTING.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/CONTRIBUTING.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/CONTRIBUTING.zh-cn.md)


Gràcies pel teu interès a contribuir a connect-core! Aquest document proporciona les pautes per contribuir al projecte.

## Taula de continguts

- [Codi de conducta](#codi-de-conducta)
- [Com contribuir-hi?](#com-contribuir-hi)
- [Informar d'errors](#informar-derrors)
- [Suggerir millores](#suggerir-millores)
- [Pull Requests](#pull-requests)
- [Estàndards de codi](#estandards-de-codi)
- [Validació local](#validacio-local)
- [Commit conventions](#commit-conventions)

---

## Codi de conducta

### La nostra promesa

Ens comprometem a proporcionar un entorn obert i acollidor per a tothom, independentment de:
- Edat, mida corporal, capacitat/discapacitat
- Ètnia, identitat i expressió de gènere
- Nivell d'experiència, educació
- Situació socioeconòmica

### Els nostres estàndards

Comportaments que contribueixen a crear un entorn positiu:
- ✅ Utilitzar llenguatge inclusiu i acollidor
- ✅ Ser respectuós amb els punts de vista diferents
- ✅ Acceptar crítiques constructives
- ✅ Enfocar-se en el millor per a la comunitat
- ✅ Mostrar empatia cap als altres membres

Comportaments inacceptables:
- ❌ Llenguatge o imatges sexuals
- ❌ Trolling, comentaris insultants o atacs personals
- ❌ Assetjament públic o privat
- ❌ Publicar informació privada sense consentiment
- ❌ Altres conductes inapropiades

---

## Com contribuir-hi?

### Requisits previs

- Git instal·lat (`git --version`)
- Docker & Docker Compose (`docker --version`, `docker compose version`)
- Bash 4.0+ (`bash --version`)
- Compte de GitHub

### Flux de treball de contribució

1. **Fes un fork del repositori**
   ```bash
   # A GitHub, fes clic a "Fork"
   # Després clona el teu fork
   git clone https://github.com/[EL_TEU_USUARI]/connect-core.git
   cd connect-core
   ```

2. **Crea una branca per a la teva funcionalitat**
   ```bash
   git checkout -b feature/descripcio-clara
   # o per a errors:
   git checkout -b fix/descripcio-de-l-error
   ```

3. **Realitza canvis**
   - Edita els fitxers necessaris
   - Mantén commits atòmics i amb missatges clars
   - Valida localment (vegeu [Validació local](#validacio-local))

4. **Puja al teu fork**
   ```bash
   git push origin feature/descripcio-clara
   ```

5. **Obre un Pull Request**
   - Fes clic a "New Pull Request" a GitHub
   - Completa la plantilla de PR
   - Espera la revisió

---

## Informar d'errors

### Abans d'informar

- ✅ Verifica que no existeixi un issue similar
- ✅ Actualitza al codi més recent (`git pull origin master`)
- ✅ Reprodueix l'error amb el codi actual
- ✅ Recull informació de depuració

### Com informar

**Obre un issue** amb els següents detalls:

```markdown
## Descripció
Breu descripció de l'error

## Passos per reproduir
1. ...
2. ...
3. ...

## Comportament actual
Què ha passat?

## Comportament esperat
Què hauria de passar?

## Informació del sistema
- OS: [ex: Ubuntu 22.04]
- Docker version: [ex: 24.0.0]
- Profile: [cpu/gpu-nvidia/gpu-amd]

## Logs
```
<logs rellevants aquí>
```

## Informació addicional
Qualsevol context addicional
```

---

## Suggerir millores

### Abans de suggerir

- ✅ Llegeix la documentació
- ✅ Busca suggeriments similars
- ✅ Considera l'abast del projecte

### Plantilla de suggeriment

```markdown
## Descripció breu
Una línia descrivint la millora

## Problema que resol
Quin problema d'usuari resol això?

## Solució proposada
Descripció de la millora

## Beneficis
- Benefici 1
- Benefici 2

## Exemples d'implementació
Pseudocodi o exemples si s'aplica

## Alternatives considerades
Altres solucions avaluades
```

---

## Pull Requests

### Checklist abans d'obrir un PR

- [ ] El meu codi segueix els estàndards de codi del projecte
- [ ] He actualitzat la documentació
- [ ] Els meus commits tenen missatges clars i descriptius
- [ ] He validat localment amb `scripts/validate.sh`
- [ ] He fet proves amb `scripts/smoke-test.sh`
- [ ] No conté codi "en construcció" o temporal
- [ ] No afegeix dependències innecessàries

### Procés de revisió

1. **Validació automàtica** (GitHub Actions)
   - YAML validation
   - Shell linting
   - Dockerfile linting
   - Docker Compose validation
   - Security checks

2. **Revisió manual**
   - Revisió de codi
   - Avaluació de canvis
   - Sol·licitud de canvis si és necessari

3. **Merge**
   - Aprovació del maintainer
   - Squash & merge a master
   - CI/CD desplega els canvis

### Plantilla de PR

```markdown
## Descripció
Breve descripció dels canvis

## Relacionat amb
- Closes #123
- Fixes #456

## Tipus de canvi
- [ ] Correcció d'error (Bug fix)
- [ ] Nova funcionalitat (Feature)
- [ ] Canvi de documentació
- [ ] Refactorització

## Canvis realitzats
- Canvi 1
- Canvi 2
- Canvi 3

## Proves realitzades
Descriu com has provat els canvis

## Screenshots (si s'aplica)
Afegeix captures de pantalla si hi ha canvis visuals

## Notes addicionals
Qualsevol informació addicional per als revisors
```

---

## Estàndards de codi

### Shell Scripts (.sh)

```bash
#!/bin/bash
set -e  # Surt en cas d'error

# Utilitzar comentaris descriptius
# Variables en MAJÚSCULES
CONFIG_FILE="/path/to/file"

# Funcions amb noms descriptius
print_info() {
    echo "ℹ️ $1"
}

# Validació d'entrada
if [ -z "$1" ]; then
    echo "Error: Falta paràmetre"
    exit 1
fi

# Utilitzar cometes per a les variables
echo "Missatge: $CONFIG_FILE"
```

**Eina:** `shellcheck`
```bash
shellcheck script.sh
```

### Dockerfiles

```dockerfile
FROM base-image:version

LABEL maintainer="maintainer@example.com"
LABEL description="Clear description"

# Utilitzar comentaris per a les seccions
USER root

# Combinar RUN quan sigui possible
RUN apt-get update && \
    apt-get install -y \
    package1 \
    package2 && \
    rm -rf /var/lib/apt/lists/*

# Exposar ports explícitament
EXPOSE 5678

# Definir volums
VOLUME ["/data"]

# Usuari no-root
USER appuser

ENTRYPOINT ["./entrypoint.sh"]
CMD ["start"]
```

**Eina:** `hadolint`
```bash
hadolint Dockerfile
```

### YAML (docker-compose.yml)

```yaml
# Indentació de 2 espais
version: "3.8"

services:
  service-name:
    image: image:version

    # Organització lògica
    container_name: service-name
    restart: unless-stopped

    # Variables d'entorn primer
    environment:
      - VAR_NAME=value

    # Ports
    ports:
      - "5678:5678"

    # Volums
    volumes:
      - volume-name:/path

    # Healthcheck
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5678"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  network-name:
    driver: bridge
```

### JSON (n8n-task-runners.json)

```json
{
  "task-runners": [
    {
      "runner-type": "python",
      "command": "/usr/bin/python3",
      "args": ["--flag", "value"],
      "health-check-server-port": "5682"
    }
  ]
}
```

**Validar amb:** `python -m json.tool n8n-task-runners.json`

### Documentació (Markdown)

- ✅ Títols jeràrquics clars
- ✅ Exemples de codi en blocs
- ✅ Enllaços interns a fitxers
- ✅ Taula de continguts per a documents llargs
- ✅ Notes destacades amb blockquotes
- ✅ Llistes estructurades

```markdown
# Títol Principal

## Subtítol

### Subsubtítulo

**Text en negreta** i *en cursiva*

> Nota o cita important

### Exemple de codi
\`\`\`bash
# Codi Bash
echo "Hola"
\`\`\`

- Punt 1
- Punt 2
  - Subpunt 2a
```

---

## Validació local

### 1. Script de validació general

```bash
# Executa totes les comprovacions
./scripts/validate.sh

# Sortida esperada:
# ✓ Validacions passades
# ⚠ Avisos (no bloqueja)
# ✗ Errors (bloqueja)
```

### 2. Prova de fum (Smoke test)

```bash
# Prova ràpida de l'stack (requereix Docker)
./scripts/smoke-test.sh          # Utilitza el perfil CPU
./scripts/smoke-test.sh gpu-nvidia  # Utilitza GPU NVIDIA
./scripts/smoke-test.sh gpu-amd     # Utilitza GPU AMD

# Comprova:
# - Inici de serveis
# - Health checks
# - Disponibilitat d'APIs
```

### 3. Linting manual

```bash
# Shell
shellcheck *.sh

# Dockerfiles
hadolint Dockerfile*

# YAML
python3 -c "import yaml; yaml.safe_load(open('docker-compose.yml'))"

# JSON
python3 -m json.tool n8n-task-runners.json

# Markdown
markdownlint *.md
```

### 4. Validació de Docker Compose

```bash
# Verificar sintaxi
docker compose config --quiet

# Llistar serveis
docker compose config | grep "^  [a-z]"

# Simular inici (sense pull)
docker compose --profile cpu config --quiet
```

---

## Commit conventions

### Format del missatge

```
<tipus>(<abast>): <assumpte>

<descripció>

<footer>
```

### Tipus de commit

- `feat:` Nova funcionalitat
- `fix:` Correcció d'error
- `docs:` Canvis de documentació
- `style:` Canvis de format (no lògica)
- `refactor:` Refactorització sense canvi funcional
- `test:` Canvis en tests/validació
- `ci:` Canvis en CI/CD
- `chore:` Canvis de build, dependències, etc.

### Exemples

```bash
# Feature
git commit -m "feat(n8n): afegir suport per a runners paral·lels"

# Bug fix
git commit -m "fix(docker-compose): corregir port d'Ollama"

# Documentation
git commit -m "docs: actualitzar guia d'instal·lació"

# Amb descripció
git commit -m "feat(comfyui): afegir suport per a nodes personalitzats

- Instal·la git durant la construcció
- Clona el repositori de nodes personalitzats
- Configura les rutes correctes

Closes #42"
```

---

## Preguntes freqüents (FAQ)

### Quin és el procés de llançament (release)?

1. Els canvis a master van a producció
2. GitHub Actions valida i construeix imatges
3. Les imatges es publiquen a GHCR
4. Tags semàntics per a llançaments

### Com informo d'una vulnerabilitat?

**NO** obris un issue públic. Contacta amb nosaltres privadament:
- Email: [EMAIL_DEL_MANTENIDOR]
- GitHub Security Advisory: Utilitza l'opció "Report a vulnerability"

### Quant de temps triga la revisió?

- Errors crítics: 24-48 hores
- Funcionalitats: 3-7 dies
- Documentació: 1-3 dies
- Depèn de la complexitat i disponibilitat

### Puc suggerir noves dependències?

Sí, però:
- Justifica per què és necessària
- Considera alternatives lleugeres
- Actualitza els Dockerfiles corresponents
- Afegeix a la documentació

---

## Recursos útils

- [GitHub Flow Guide](https://guides.github.com/introduction/flow/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Markdown Guide](https://www.markdownguide.org/)
- [ShellCheck Wiki](https://www.shellcheck.net/wiki/)
- [Dockerfile Best Practices](https://docs.docker.com/develop/dev-best-practices/)

---

## Reconeixement

Gràcies per contribuir a connect-core! Cada contribució, sense importar la seva mida, ajuda a millorar el projecte.

Si tens preguntes, no dubtis a obrir un issue de discussió o contactar amb els mantenidors.

---

<div align="center">

**Esperem la teva contribució! ❤️**

</div>
