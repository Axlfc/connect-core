"""
Cognito Stack - Versión Simplificada
Usa requests directamente sin Docker exec
"""

import requests
import json
import time
from typing import Dict, List
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SimpleCognitoStack:
    """Sistema de razonamiento multi-módulo simplificado"""
    
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url
        self.workspace = []
        
        # Modelos optimizados para RTX 5070 12GB
        self.models = {
            "routing": "deepseek-r1:7b",
            "deduction": "deepseek-r1:14b",
            "induction": "gemma3:12b",
            "abduction": "cogito:14b",
            "conduction": "qwen2.5-coder:14b",
            "analogy": "phi4:14b",
            "generative": "llama3.1:8b",
            "social": "gemma3:12b",
            "metareasoning": "cogito:8b"
        }
        
        logger.info("✅ Cognito Stack inicializado")
    
    def generate(self, model: str, prompt: str, system: str = None, temperature: float = 0.7, max_tokens: int = 2048) -> str:
        """Genera respuesta usando Ollama API"""
        
        request_data = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        
        if system:
            request_data["system"] = system
        
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=request_data,
                timeout=300
            )
            
            response.raise_for_status()
            data = response.json()
            
            return data.get('response', '')
            
        except Exception as e:
            logger.error(f"Error generando con {model}: {e}")
            return f"Error: {str(e)}"
    
    def route_task(self, task: str) -> str:
        """Determina qué tipo de razonamiento usar"""
        
        prompt = f"""Analiza esta tarea y determina el mejor tipo de razonamiento.

TIPOS:
- deduction: Lógica formal
- induction: Detectar patrones  
- abduction: Generar hipótesis
- conduction: Planificar/escribir código
- analogy: Transferir conocimiento
- generative: Crear contenido
- social: Consenso social

TAREA: {task[:500]}

Responde SOLO: deduction, induction, abduction, conduction, analogy, generative, o social"""

        result = self.generate(
            model=self.models["routing"],
            prompt=prompt,
            temperature=0.2,
            max_tokens=50
        )
        
        # Extraer tipo de la respuesta
        result_lower = result.lower().strip()
        for rtype in ["deduction", "induction", "abduction", "conduction", "analogy", "generative", "social"]:
            if rtype in result_lower:
                logger.info(f"🧭 Routing: {rtype}")
                return rtype
        
        logger.warning("No se pudo determinar tipo, usando generative")
        return "generative"
    
    def execute_reasoning(self, task: str, reasoning_type: str) -> str:
        """Ejecuta razonamiento específico"""
        
        model = self.models.get(reasoning_type, self.models["generative"])
        
        prompts = {
            "deduction": "Aplica razonamiento DEDUCTIVO riguroso. Identifica premisas, aplica lógica formal, deriva conclusiones válidas.",
            "induction": "Aplica razonamiento INDUCTIVO. Examina datos, identifica patrones, formula generalizaciones.",
            "abduction": "Aplica razonamiento ABDUCTIVO. Analiza observaciones, genera hipótesis explicativas, evalúa la mejor explicación.",
            "conduction": "Aplica razonamiento CONDUCTIVO. Define objetivos, planifica acciones concretas, escribe código funcional.",
            "analogy": "Aplica razonamiento ANALÓGICO. Identifica dominio origen, mapea estructuras, transfiere conocimiento.",
            "generative": "Genera contenido CREATIVO y ORIGINAL. Explora ideas innovadoras, combina conceptos, aporta valor único.",
            "social": "Aplica razonamiento SOCIAL. Identifica perspectivas, analiza normas, busca consenso."
        }
        
        full_prompt = f"""{prompts.get(reasoning_type, prompts['generative'])}

TAREA:
{task}

Tu respuesta:"""
        
        system_prompt = None
        if reasoning_type == "abduction" and "cogito" in model:
            system_prompt = "Enable deep thinking subroutine."
            logger.info("🧠 Deep thinking habilitado")
        
        logger.info(f"⚙️  Ejecutando {reasoning_type} con {model}")
        
        start = time.time()
        result = self.generate(
            model=model,
            prompt=full_prompt,
            system=system_prompt,
            temperature=0.7,
            max_tokens=2048
        )
        elapsed = time.time() - start
        
        logger.info(f"✅ Completado en {elapsed:.2f}s")
        
        return result
    
    def solve(self, task: str) -> str:
        """Resuelve tarea usando el sistema completo"""
        
        logger.info(f"\n{'='*80}\n🎯 TAREA: {task[:100]}...\n{'='*80}")
        
        # 1. Routing
        reasoning_type = self.route_task(task)
        
        # 2. Ejecución
        result = self.execute_reasoning(task, reasoning_type)
        
        logger.info(f"\n{'='*80}\n✅ COMPLETADO\n{'='*80}")
        
        return result


# =============================================================================
# EJEMPLOS DE USO
# =============================================================================

if __name__ == "__main__":
    # Inicializar
    cognito = SimpleCognitoStack()
    
    print("\n" + "="*80)
    print("COGNITO STACK - EJEMPLOS")
    print("="*80)
    
    # =============================================================================
    # EJEMPLO 1: Análisis de Bug
    # =============================================================================
    
    task1 = """
Analiza este código Python y encuentra el bug:

```python
def calcular_promedio(numeros):
    suma = 0
    for num in numeros:
        suma += num
    return suma / len(numeros)

resultado = calcular_promedio([])
print(resultado)
```

Explica el problema y proporciona la solución.
"""
    
    print("\n" + "="*80)
    print("EJEMPLO 1: Análisis de Bug")
    print("="*80)
    
    solution1 = cognito.solve(task1)
    print(f"\n{solution1}\n")
    
    # =============================================================================
    # EJEMPLO 2: Detección de Patrones
    # =============================================================================
    
    task2 = """
Observa estos números: 2, 6, 12, 20, 30, 42

¿Cuál es el patrón y cuál sería el siguiente número?
"""
    
    print("\n" + "="*80)
    print("EJEMPLO 2: Detección de Patrones")
    print("="*80)
    
    solution2 = cognito.solve(task2)
    print(f"\n{solution2}\n")
    
    # =============================================================================
    # EJEMPLO 3: Script Bash
    # =============================================================================
    
    task3 = """
Escribe un script bash que:
1. Busque archivos .log mayores de 100MB en /var/log
2. Los comprima con gzip
3. Mueva los comprimidos a /var/backups/
4. Elimine los originales solo si la compresión fue exitosa
5. Registre todo en un log

El script debe ser robusto con manejo de errores.
"""
    
    print("\n" + "="*80)
    print("EJEMPLO 3: Script Bash")
    print("="*80)
    
    solution3 = cognito.solve(task3)
    print(f"\n{solution3}\n")
    
    print("\n" + "="*80)
    print("✅ TODOS LOS EJEMPLOS COMPLETADOS")
    print("="*80)
