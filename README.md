Sigue estos pasos para instalar we

1. Clona el repo, en github we hay un boton verde q dice code, le picas y dice https una liga, pon el comando y copia y pega, vuala papito ya tienes app.
# git clone -liga del repo-

2. Creas tu entornito virtual
python -m venv venv #Este comando crea la carpeta del venv con lo que ocupas.
2.1 usa cmd en windous para activar ese entorno virtual venv\Scripts\activate.bat

#tambien visual studio code puede activar este entorno al abrir terminal checa esa config.

3. Instala lo que ocupas de dependencias we
pip install -requirements.txt

4. carpeta .env
Aprendi para que sirve ahorta we, la gente quiere tu app en blanco, no ver el intento de usuario que creaste Furro69

en settings.py esta la secret_key de django automatica con python decouple le dices que ahora busque en tu .env la contra, tu carpeta .env ahora es tu secret_key, esto para proteger contraseñas de los usuarios yu no ponerlas en el repo we.

5. Corre el servidor webon
python manage.py runserver

