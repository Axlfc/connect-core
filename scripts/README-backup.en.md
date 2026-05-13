[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/scripts/README-backup.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/scripts/README-backup.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/scripts/README-backup.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/scripts/README-backup.zh-cn.md)

Backup/Restore scripts

Overview
- `backup.sh` : crea dumps y exporta volúmenes críticos a `backups/<timestamp>/`.
- `restore.sh`: lista backups y permite restaurar SQL y/o volúmenes desde un timestamp.

Defaults and configuration
- `BACKUP_DIR` : directorio raíz (por defecto `backups`)
- `POSTGRES_SERVICE` : nombre del servicio Postgres en compose (por defecto `postgres`)
- `VOLUMES` : lista de volúmenes a exportar (por defecto: postgres_storage n8n_storage qdrant_storage duplicati_config comfyui_local)
- `KEEP_DAYS` : días a conservar backups (por defecto 14)

Examples
1) Crear backup (modo normal):

```bash
./scripts/backup.sh
```

2) Simular backup sin ejecutar acciones:

```bash
./scripts/backup.sh --dry-run
```

3) Listar backups disponibles:

```bash
./scripts/restore.sh --list
```

4) Restaurar SQL y volúmenes desde un timestamp:

```bash
./scripts/restore.sh 20260105T120000Z --restore-postgres --restore-volumes
```

Duplicati integration
---------------------

- `backup-to-duplicati.sh` : ejecuta `backup.sh` con destino en `./backups/sources/` (la ruta montada por Duplicati) y luego intenta pedir a Duplicati que ejecute un job inmediatamente (petición HTTP best-effort). Si quieres que Duplicati haga copias incrementales cifradas, configura un job en la UI que lea desde `/source` y escriba al backend deseado.

Systemd / Cron
--------------

- Ejemplos de `systemd` en `contrib/systemd/`: `cognito-backup.service` y `cognito-backup.timer`. Copia ambos a `/etc/systemd/system/`, ajusta `ExecStart` y el `WorkingDirectory`, habilita con `systemctl enable --now cognito-backup.timer`.

Notes
- El script `backup-to-duplicati.sh` intenta varios endpoints HTTP para disparar Duplicati; si la invocación automática falla, abre la UI en `http://localhost:8200` y lanza el job manualmente.


Warnings
- Restaurar archivos de base de datos en crudo (restaurar los datos del volumen de Postgres) puede ser riesgoso si las versiones no coinciden; preferir la restauración por SQL cuando sea posible.
- Asegúrate de que `docker` y `docker compose` (o `docker-compose`) estén disponibles y que los contenedores estén accesibles.
