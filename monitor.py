"""
Sistema de Monitoreo y Diagnóstico para Cognito Stack + Docker
Optimizado para RTX 5070 12GB
"""

import subprocess
import json
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import sys


@dataclass
class GPUStats:
    """Estadísticas de GPU"""
    vram_used_mb: float
    vram_free_mb: float
    vram_total_mb: float
    gpu_utilization: float
    temperature: float
    power_draw: float
    timestamp: datetime


class DockerGPUMonitor:
    """Monitor de GPU y contenedor Docker con Ollama"""
    
    def __init__(self, container_name: str = "ollama-gpu", max_vram_mb: float = 11500):
        self.container = container_name
        self.max_vram = max_vram_mb
        self.stats_history: List[GPUStats] = []
        
    def get_gpu_stats(self) -> Optional[GPUStats]:
        """Obtiene estadísticas de la GPU"""
        try:
            result = subprocess.run(
                [
                    'nvidia-smi',
                    '--query-gpu=memory.used,memory.free,memory.total,utilization.gpu,temperature.gpu,power.draw',
                    '--format=csv,noheader,nounits'
                ],
                capture_output=True,
                text=True,
                check=True
            )
            
            values = result.stdout.strip().split(', ')
            
            stats = GPUStats(
                vram_used_mb=float(values[0]),
                vram_free_mb=float(values[1]),
                vram_total_mb=float(values[2]),
                gpu_utilization=float(values[3]),
                temperature=float(values[4]),
                power_draw=float(values[5]),
                timestamp=datetime.now()
            )
            
            self.stats_history.append(stats)
            return stats
            
        except Exception as e:
            print(f"❌ Error obteniendo stats GPU: {e}")
            return None
    
    def get_container_status(self) -> Optional[Dict]:
        """Verifica estado del contenedor"""
        try:
            result = subprocess.run(
                ['docker', 'inspect', self.container],
                capture_output=True,
                text=True,
                check=True
            )
            
            data = json.loads(result.stdout)[0]
            
            return {
                'running': data['State']['Running'],
                'status': data['State']['Status'],
                'started_at': data['State']['StartedAt'],
                'image': data['Config']['Image'],
                'gpu_enabled': '--gpus' in ' '.join(data['HostConfig'].get('DeviceRequests', [{}])[0].get('Capabilities', [[]])[0] if data['HostConfig'].get('DeviceRequests') else [])
            }
            
        except Exception as e:
            print(f"❌ Error obteniendo status del contenedor: {e}")
            return None
    
    def get_ollama_models_loaded(self) -> List[Dict]:
        """Lista modelos cargados en Ollama"""
        try:
            result = subprocess.run(
                ['docker', 'exec', self.container, 'ollama', 'ps'],
                capture_output=True,
                text=True,
                check=True
            )
            
            models = []
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            
            for line in lines:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 4:
                        models.append({
                            'name': parts[0],
                            'size': parts[2],
                            'until': parts[3]
                        })
            
            return models
            
        except Exception as e:
            return []
    
    def get_ollama_models_available(self) -> List[Dict]:
        """Lista todos los modelos disponibles"""
        try:
            result = subprocess.run(
                ['docker', 'exec', self.container, 'ollama', 'list'],
                capture_output=True,
                text=True,
                check=True
            )
            
            models = []
            for line in result.stdout.strip().split('\n')[1:]:  # Skip header
                parts = line.split()
                if len(parts) >= 3:
                    models.append({
                        'name': parts[0],
                        'id': parts[1],
                        'size': parts[2],
                        'modified': ' '.join(parts[3:]) if len(parts) > 3 else 'Unknown'
                    })
            return models
            
        except Exception as e:
            print(f"❌ Error listando modelos: {e}")
            return []
    
    def print_dashboard(self):
        """Muestra dashboard completo del sistema"""
        gpu_stats = self.get_gpu_stats()
        container_status = self.get_container_status()
        loaded_models = self.get_ollama_models_loaded()
        available_models = self.get_ollama_models_available()
        
        print("\n" + "="*100)
        print("🎮 COGNITO STACK - DASHBOARD DE MONITOREO".center(100))
        print("="*100)
        
        # GPU Stats
        if gpu_stats:
            vram_percent = (gpu_stats.vram_used_mb / gpu_stats.vram_total_mb) * 100
            vram_bar = self._create_progress_bar(vram_percent, 40)
            
            print(f"\n🖥️  GPU: NVIDIA RTX 5070")
            print(f"{'─'*100}")
            print(f"  VRAM:        {vram_bar} {gpu_stats.vram_used_mb:.0f}MB / {gpu_stats.vram_total_mb:.0f}MB ({vram_percent:.1f}%)")
            print(f"  Disponible:  {gpu_stats.vram_free_mb:.0f}MB")
            print(f"  Utilización: {'█' * int(gpu_stats.gpu_utilization/2.5)} {gpu_stats.gpu_utilization}%")
            print(f"  Temperatura: {self._temp_indicator(gpu_stats.temperature)} {gpu_stats.temperature}°C")
            print(f"  Consumo:     {gpu_stats.power_draw}W")
            
            # Recomendaciones basadas en VRAM
            if vram_percent > 90:
                print(f"  ⚠️  ALERTA: VRAM crítica - considera usar modelos más ligeros")
            elif vram_percent > 75:
                print(f"  ⚡ ADVERTENCIA: VRAM alta - limita context size o usa modelos 7B")
            elif vram_percent < 50:
                print(f"  ✅ EXCELENTE: VRAM holgada - puedes usar modelos 14B con contexto largo")
        
        # Container Stats
        if container_status:
            print(f"\n🐳 CONTENEDOR DOCKER: {self.container}")
            print(f"{'─'*100}")
            status_icon = "✅" if container_status['running'] else "❌"
            print(f"  Estado:      {status_icon} {container_status['status'].upper()}")
            print(f"  Imagen:      {container_status['image']}")
            print(f"  GPU:         {'✅ Habilitada' if container_status.get('gpu_enabled') else '❌ No detectada'}")
            print(f"  Iniciado:    {container_status['started_at'][:19]}")
        
        # Modelos
        print(f"\n📦 MODELOS OLLAMA")
        print(f"{'─'*100}")
        print(f"  Disponibles: {len(available_models)} modelos")
        print(f"  En memoria:  {len(loaded_models)} modelos")
        
        if loaded_models:
            print(f"\n  🔥 MODELOS CARGADOS:")
            for model in loaded_models:
                print(f"     • {model['name']:<30} {model['size']:>10}  (hasta: {model['until']})")
        
        # Top modelos por tamaño
        if available_models:
            print(f"\n  📊 TOP 10 MODELOS POR TAMAÑO:")
            sorted_models = sorted(available_models, key=lambda x: self._parse_size(x['size']), reverse=True)[:10]
            for i, model in enumerate(sorted_models, 1):
                size_gb = self._parse_size(model['size']) / 1024
                fit_indicator = "✅" if size_gb < 10 else "⚠️" if size_gb < 15 else "❌"
                print(f"     {i:2}. {fit_indicator} {model['name']:<35} {model['size']:>8}  ({size_gb:.1f}GB)")
        
        print("\n" + "="*100)
        print(f"⏰ Actualizado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*100 + "\n")
    
    def _create_progress_bar(self, percent: float, width: int = 40) -> str:
        """Crea barra de progreso visual"""
        filled = int(width * percent / 100)
        bar = '█' * filled + '░' * (width - filled)
        return f"[{bar}]"
    
    def _temp_indicator(self, temp: float) -> str:
        """Indicador de temperatura"""
        if temp < 60:
            return "❄️"
        elif temp < 75:
            return "🌡️"
        else:
            return "🔥"
    
    def _parse_size(self, size_str: str) -> float:
        """Parsea string de tamaño a MB"""
        try:
            size_str = size_str.upper().replace(' ', '')
            if 'GB' in size_str:
                return float(size_str.replace('GB', '')) * 1024
            elif 'MB' in size_str:
                return float(size_str.replace('MB', ''))
            else:
                return 0
        except:
            return 0
    
    def generate_recommendations(self) -> List[str]:
        """Genera recomendaciones inteligentes"""
        recommendations = []
        
        gpu_stats = self.get_gpu_stats()
        if not gpu_stats:
            return ["⚠️ No se pudo obtener stats de GPU"]
        
        loaded = self.get_ollama_models_loaded()
        vram_percent = (gpu_stats.vram_used_mb / gpu_stats.vram_total_mb) * 100
        
        # Análisis de VRAM
        if vram_percent > 90:
            recommendations.append(
                "🚨 CRÍTICO: VRAM > 90%. Descarga modelos pesados inmediatamente:\n"
                "   docker exec ollama-gpu pkill ollama (libera toda la VRAM)"
            )
        elif vram_percent > 75:
            recommendations.append(
                "⚠️  VRAM alta. Usa modelos 7B-8B para mejor rendimiento:\n"
                "   - deepseek-r1:7b, llama3.1:8b, cogito:8b"
            )
        
        if len(loaded) > 2:
            recommendations.append(
                f"📦 {len(loaded)} modelos en memoria. Con 12GB VRAM, óptimo es 1-2 modelos:\n"
                "   Espera 2 minutos para auto-descarga o reinicia Ollama"
            )
        
        # Análisis de temperatura
        if gpu_stats.temperature > 80:
            recommendations.append(
                f"🌡️  Temperatura alta ({gpu_stats.temperature}°C). Acciones:\n"
                "   - Verifica ventilación del case\n"
                "   - Reduce carga usando modelos más ligeros\n"
                "   - Limita num_ctx a 8192 para reducir uso de GPU"
            )
        
        # Recomendaciones de optimización
        if vram_percent < 60 and gpu_stats.gpu_utilization < 40:
            recommendations.append(
                "✅ Sistema subutilizado. Puedes optimizar:\n"
                "   - Aumentar num_ctx a 32768 para modelos 7B\n"
                "   - Usar modelos 14B sin problemas\n"
                "   - Procesar batches más grandes"
            )
        
        # Modelos específicos
        available = self.get_ollama_models_available()
        heavy_models = [m for m in available if self._parse_size(m['size']) > 15000]  # >15GB
        
        if heavy_models and vram_percent > 70:
            recommendations.append(
                f"💡 Detectados {len(heavy_models)} modelos pesados (>15GB):\n"
                "   - " + "\n   - ".join([f"{m['name']} ({m['size']})" for m in heavy_models[:3]]) +
                "\n   Estos modelos harán SWAP a RAM (muy lento con 12GB VRAM)"
            )
        
        return recommendations if recommendations else [
            "✅ Sistema operando óptimamente",
            "💡 VRAM disponible para modelos 14B con contexto de 16K",
            "🚀 Puedes ejecutar 2 modelos 7B simultáneamente sin problemas"
        ]


class CognitoHealthCheck:
    """Diagnóstico de salud del sistema Cognito"""
    
    def __init__(self, container_name: str = "ollama-gpu"):
        self.container = container_name
        self.monitor = DockerGPUMonitor(container_name)
    
    def run_diagnostics(self) -> Dict:
        """Ejecuta diagnóstico completo"""
        results = {
            'gpu': self._check_gpu(),
            'docker': self._check_docker(),
            'ollama': self._check_ollama(),
            'models': self._check_models(),
            'config': self._check_config()
        }
        
        return results
    
    def _check_gpu(self) -> Dict:
        """Verifica GPU"""
        stats = self.monitor.get_gpu_stats()
        
        if not stats:
            return {'status': 'ERROR', 'message': 'No se detectó GPU NVIDIA'}
        
        if stats.vram_total_mb < 12000:
            return {'status': 'WARNING', 'message': f'VRAM detectada: {stats.vram_total_mb}MB (esperado: 12GB)'}
        
        return {
            'status': 'OK',
            'vram_total': stats.vram_total_mb,
            'vram_free': stats.vram_free_mb,
            'temperature': stats.temperature
        }
    
    def _check_docker(self) -> Dict:
        """Verifica Docker y contenedor"""
        try:
            # Check Docker instalado
            subprocess.run(['docker', '--version'], capture_output=True, check=True)
            
            # Check contenedor
            status = self.monitor.get_container_status()
            
            if not status:
                return {'status': 'ERROR', 'message': f'Contenedor {self.container} no encontrado'}
            
            if not status['running']:
                return {'status': 'ERROR', 'message': 'Contenedor no está corriendo'}
            
            if not status.get('gpu_enabled'):
                return {'status': 'WARNING', 'message': 'GPU no está habilitada en el contenedor'}
            
            return {'status': 'OK', 'container': status}
            
        except subprocess.CalledProcessError:
            return {'status': 'ERROR', 'message': 'Docker no está instalado o no es accesible'}
    
    def _check_ollama(self) -> Dict:
        """Verifica Ollama"""
        try:
            result = subprocess.run(
                ['docker', 'exec', self.container, 'ollama', '--version'],
                capture_output=True,
                text=True,
                check=True
            )
            
            version = result.stdout.strip()
            
            return {'status': 'OK', 'version': version}
            
        except Exception as e:
            return {'status': 'ERROR', 'message': f'Ollama no responde: {e}'}
    
    def _check_models(self) -> Dict:
        """Verifica modelos esenciales"""
        essential = {
            'routing': ['deepseek-r1:7b', 'cogito:8b'],
            'reasoning': ['deepseek-r1:14b', 'cogito:14b', 'phi4:14b'],
            'coding': ['qwen2.5-coder:14b', 'devstral:24b'],
            'general': ['llama3.1:8b', 'gemma3:12b', 'qwen2.5:14b']
        }
        
        available = self.monitor.get_ollama_models_available()
        available_names = {m['name'] for m in available}
        
        status = {}
        missing_critical = []
        
        for category, models in essential.items():
            found = [m for m in models if m in available_names]
            missing = [m for m in models if m not in available_names]
            
            status[category] = {
                'found': found,
                'missing': missing,
                'coverage': len(found) / len(models) * 100
            }
            
            if category in ['routing', 'reasoning'] and not found:
                missing_critical.extend(missing)
        
        if missing_critical:
            return {
                'status': 'ERROR',
                'message': f'Modelos críticos faltantes: {missing_critical}',
                'details': status
            }
        
        return {'status': 'OK', 'details': status}
    
    def _check_config(self) -> Dict:
        """Verifica configuración óptima"""
        import os
        
        optimal_config = {
            'OLLAMA_FLASH_ATTENTION': '1',
            'OLLAMA_KV_CACHE_TYPE': 'q8_0',
            'OLLAMA_NUM_GPU': '999',
            'OLLAMA_KEEP_ALIVE': '2m',
            'OLLAMA_MAX_LOADED_MODELS': '2'
        }
        
        issues = []
        for var, expected in optimal_config.items():
            actual = os.getenv(var)
            if actual != expected:
                issues.append(f"{var}={actual or 'no configurado'} (recomendado: {expected})")
        
        if issues:
            return {'status': 'WARNING', 'issues': issues}
        
        return {'status': 'OK'}
    
    def print_diagnostics(self):
        """Imprime reporte de diagnóstico"""
        results = self.run_diagnostics()
        
        print("\n" + "="*100)
        print("🔍 DIAGNÓSTICO DEL SISTEMA COGNITO".center(100))
        print("="*100)
        
        # GPU
        print(f"\n1️⃣  GPU")
        print("─" * 100)
        gpu = results['gpu']
        if gpu['status'] == 'OK':
            print(f"   ✅ GPU detectada: RTX 5070")
            print(f"   ✅ VRAM Total: {gpu['vram_total']:.0f}MB")
            print(f"   ✅ VRAM Libre: {gpu['vram_free']:.0f}MB")
            print(f"   ✅ Temperatura: {gpu['temperature']}°C")
        else:
            print(f"   ❌ {gpu['message']}")
        
        # Docker
        print(f"\n2️⃣  DOCKER")
        print("─" * 100)
        docker = results['docker']
        if docker['status'] == 'OK':
            print(f"   ✅ Contenedor: {self.container}")
            print(f"   ✅ Estado: Running")
            print(f"   ✅ GPU: Habilitada")
        else:
            print(f"   ❌ {docker['message']}")
        
        # Ollama
        print(f"\n3️⃣  OLLAMA")
        print("─" * 100)
        ollama = results['ollama']
        if ollama['status'] == 'OK':
            print(f"   ✅ Ollama: {ollama['version']}")
        else:
            print(f"   ❌ {ollama['message']}")
        
        # Modelos
        print(f"\n4️⃣  MODELOS")
        print("─" * 100)
        models = results['models']
        if models['status'] == 'OK':
            for category, info in models['details'].items():
                print(f"   • {category.upper()}: {info['coverage']:.0f}% cobertura")
                if info['found']:
                    print(f"     ✅ Disponibles: {', '.join(info['found'])}")
                if info['missing']:
                    print(f"     ⚠️  Faltantes: {', '.join(info['missing'])}")
        else:
            print(f"   ❌ {models['message']}")
        
        # Configuración
        print(f"\n5️⃣  CONFIGURACIÓN")
        print("─" * 100)
        config = results['config']
        if config['status'] == 'OK':
            print(f"   ✅ Todas las optimizaciones configuradas")
        else:
            print(f"   ⚠️  Optimizaciones faltantes:")
            for issue in config['issues']:
                print(f"      • {issue}")
        
        # Recomendaciones
        print(f"\n6️⃣  RECOMENDACIONES")
        print("─" * 100)
        for rec in self.monitor.generate_recommendations():
            print(f"   {rec}\n")
        
        print("="*100 + "\n")


# =============================================================================
# CLI
# =============================================================================

def main():
    if len(sys.argv) < 2:
        print_help()
        return
    
    command = sys.argv[1]
    container = sys.argv[2] if len(sys.argv) > 2 else "ollama-gpu"
    
    monitor = DockerGPUMonitor(container)
    health = CognitoHealthCheck(container)
    
    if command == "status":
        monitor.print_dashboard()
    
    elif command == "watch":
        print("🔄 Monitoreo continuo (Ctrl+C para salir)...\n")
        try:
            while True:
                monitor.print_dashboard()
                time.sleep(5)
        except KeyboardInterrupt:
            print("\n\n✅ Monitoreo detenido.\n")
    
    elif command == "diagnostics":
        health.print_diagnostics()
    
    elif command == "recommendations":
        print("\n💡 RECOMENDACIONES\n" + "="*80)
        for rec in monitor.generate_recommendations():
            print(f"{rec}\n")
    
    elif command == "models":
        available = monitor.get_ollama_models_available()
        loaded = monitor.get_ollama_models_loaded()
        
        print(f"\n📦 MODELOS DISPONIBLES ({len(available)} total)\n" + "="*100)
        for model in available:
            status = "🔥" if any(m['name'] == model['name'] for m in loaded) else "  "
            print(f"{status} {model['name']:<35} {model['size']:>8}  ({model['modified']})")
    
    else:
        print(f"❌ Comando desconocido: {command}\n")
        print_help()


def print_help():
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    COGNITO STACK - SISTEMA DE MONITOREO                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

USO: python monitor.py <comando> [container_name]

COMANDOS:
  status              Muestra dashboard completo del sistema
  watch               Monitoreo continuo (actualiza cada 5s)
  diagnostics         Ejecuta diagnóstico completo
  recommendations     Muestra recomendaciones de optimización
  models              Lista todos los modelos disponibles

EJEMPLOS:
  python monitor.py status
  python monitor.py watch ollama-gpu
  python monitor.py diagnostics

CONTAINER NAME:
  Por defecto: ollama-gpu
  Personalizado: python monitor.py status mi-contenedor
""")


if __name__ == "__main__":
    main()
