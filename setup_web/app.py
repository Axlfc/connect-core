from flask import Flask, render_template, request, send_file, redirect, url_for, flash
from pathlib import Path
import secrets
import os

app = Flask(__name__)
app.secret_key = secrets.token_urlsafe(16)

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = REPO_ROOT / '.env.example'
ENV_OUT = REPO_ROOT / '.env'

DEFAULT_KEYS = [
    'N8N_ENCRYPTION_KEY',
    'N8N_USER_MANAGEMENT_JWT_SECRET',
    'N8N_AUTH_JWT_SECRET',
    'POSTGRES_PASSWORD',
    'REDIS_PASSWORD',
    'N8N_RUNNERS_AUTH_TOKEN',
    'ZROK_AUTH_TOKEN',
]


def generate_secret(name: str) -> str:
    if 'PASSWORD' in name or 'TOKEN' in name or 'AUTH' in name:
        return secrets.token_urlsafe(16)
    return secrets.token_urlsafe(32)


def load_env_example() -> dict:
    data = {}
    if not ENV_EXAMPLE.exists():
        return data
    for line in ENV_EXAMPLE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            k, v = line.split('=', 1)
            data[k.strip()] = v.strip()
    return data


def build_env(profile: str) -> str:
    env_map = load_env_example()
    for key in DEFAULT_KEYS:
        if not env_map.get(key):
            env_map[key] = generate_secret(key)
    env_map['STACK_PROFILE'] = profile
    # Preserve other keys from example; if none, include the generated ones
    lines = []
    if ENV_EXAMPLE.exists():
        for line in ENV_EXAMPLE.read_text().splitlines():
            if not line.strip() or line.strip().startswith('#'):
                lines.append(line)
                continue
            if '=' in line:
                k, _ = line.split('=', 1)
                k = k.strip()
                v = env_map.get(k, '')
                lines.append(f"{k}={v}")
            else:
                lines.append(line)
    else:
        for k, v in env_map.items():
            lines.append(f"{k}={v}")
    return '\n'.join(lines) + '\n'


@app.route('/')
def index():
    return redirect(url_for('setup'))


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    generated = None
    if request.method == 'POST':
        profile = request.form.get('profile', 'cpu')
        env_text = build_env(profile)
        try:
            ENV_OUT.write_text(env_text)
            generated = env_text
            flash('.env generado con éxito en la raíz del repositorio.', 'success')
        except Exception as e:
            flash(f'Error escribiendo .env: {e}', 'danger')
    return render_template('setup.html', generated=generated)


@app.route('/download')
def download():
    if not ENV_OUT.exists():
        flash('No existe .env. Genera uno primero.', 'warning')
        return redirect(url_for('setup'))
    return send_file(str(ENV_OUT), as_attachment=True, download_name='.env')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9999)
