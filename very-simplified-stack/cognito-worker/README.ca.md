# 🛠️ Cognito Worker — Workspace & Git Worktree Execution Service
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](README.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](README.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](README.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](README.zh-cn.md)

Aquest servei (`cognito-worker`) és el component d'execució del costat de l'host que es comunica amb el pla de control (`cognito-backend`). Proporciona una API interna aïllada i segura per a la creació de zones de treball de codi (git worktrees), verificació de compilació, execució de terminals bash del propi agent de manera controlada i signatura criptogràfica.

## 🚀 Característiques Principals

- **Gestor de Worktrees**: Aïllament i clonació de directoris de treball per commit mitjançant `git worktree` per evitar qualsevol col·lisió a la branca de treball activa.
- **Verificació Intel·ligent**: Execució automatitzada de tests locals per avaluar de manera transparent la qualitat dels pegats de l'agent.
- **Signatura Criptogràfica HMAC**: Validació rigorosa d'esquemes HMAC utilitzant un secret compartit per prevenir modificacions o atacs de tipus replay.
- **Integració amb Systemd**: Fitxer de servei d'usuari llest per carregar-se de manera persistent a Linux.

## 🛠️ Instal·lació i Arrencada

### 1. Dependències del Sistema
Assegura't de tenir instal·lats git i python al teu host:
```bash
sudo apt-get update
sudo apt-get install -y python3-venv git
```

### 2. Entorn Virtual
Crea un entorn aïllat de Python i instal·la els paquets:
```bash
cd very-simplified-stack/cognito-worker/
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Execució Directa (Desenvolupament)
```bash
# Iniciar el servei al port 8001
source venv/bin/activate
uvicorn worker_app.main:app --host 0.0.0.0 --port 8001
```

### 4. Execució com a Servei Systemd (Producció)
Per deixar el procés de fons en segon pla:

1. Personalitza els paths dins del fitxer `cognito-worker.service` si cal.
2. Copia l'arxiu cap a la carpeta de systemd:
   ```bash
   sudo cp cognito-worker.service /etc/systemd/system/
   sudo systemctl daemon-reload
   ```
3. Activa i engega el servei:
   ```bash
   sudo systemctl start cognito-worker
   sudo systemctl enable cognito-worker
   ```
4. Comprova la salut del servei:
   ```bash
   sudo systemctl status cognito-worker
   ```

## ⚙️ Configuració (Variables d'Entorn)

Variables d'entorn per parametritzar el worker:

- `COGNITO_WORKER_PORT`: Port d'escolta de la connexió (default: `8001`).
- `COGNITO_WORKER_SECRET`: Clau HMAC compartida amb el backend per a l'autenticació.
- `ALLOWED_ROOTS`: Arrels de carpetes de l'host autoritzades per crear-hi worktrees.
- `WORKER_ID`: Identificador únic del worker.

## 🧪 Pruebes i Validació

Per córrer els tests del worker de manera aïllada:
```bash
source venv/bin/activate
PYTHONPATH=. pytest tests/
```
