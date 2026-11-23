# Entorno Python

## Propósito

Este entorno prepara la base reproducible para la etapa posterior de construcción y validación de curvas spot. No realiza consultas a Banxico, no requiere credenciales y no ejecuta macros.

## Versiones requeridas

- Python 3.11 (objetivo de ejecución).
- NumPy 2.2.6.
- SciPy 1.15.3.
- pytest 8.3.5.

Las versiones de las dependencias están fijadas en requirements.txt. NumPy proporciona arreglos numéricos; SciPy incorpora métodos numéricos y de optimización; pytest ejecuta las pruebas automatizadas. No se requieren bibliotecas adicionales en esta etapa.

## Preparación en Windows con PowerShell

Desde la raíz del repositorio, comprueba la versión de Python:

~~~powershell
py -3.11 --version
~~~

Crea el entorno virtual:

~~~powershell
py -3.11 -m venv .venv
~~~

Actívalo para la sesión actual:

~~~powershell
.\.venv\Scripts\Activate.ps1
~~~

Si PowerShell bloquea la activación por política local, usa:

~~~powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
~~~

Instala las dependencias fijadas:

~~~powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
~~~

## Verificación

Comprueba las versiones instaladas:

~~~powershell
python --version
python -c "import numpy, scipy; print('NumPy', numpy.__version__); print('SciPy', scipy.__version__)"
~~~

Ejecuta la prueba de entorno:

~~~powershell
python -m pytest tests/test_environment.py -q
~~~

La prueba sólo valida importaciones y una operación numérica determinista de SciPy. No cubre todavía el cálculo financiero, la API de Banxico, agentes, automatizaciones ni credenciales.

## Salida del entorno

Al terminar la sesión:

~~~powershell
deactivate
~~~
