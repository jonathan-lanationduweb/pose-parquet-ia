# Image CPU. Aucun GPU, aucun poids de modèle : voir docs/architecture.md.
FROM python:3.12-slim AS base

# OpenCV est installé en variante « headless » : pas de dépendance GUI/X11,
# donc pas de libGL à installer, et une image nettement plus petite.
#
# Si le build échoue sur une bibliothèque partagée manquante — le cas se voit
# selon les versions de wheel et d'image de base — décommenter la ligne
# suivante plutôt que de repasser à `opencv-python` complet :
#
# RUN apt-get update && apt-get install -y --no-install-recommends #       libglib2.0-0 && rm -rf /var/lib/apt/lists/*
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Les dépendances d'abord : cette couche ne se reconstruit que si le
# pyproject change, pas à chaque modification de code.
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir .

# Utilisateur non privilégié. Le service n'écrit rien sur le disque — il n'a
# donc besoin d'aucun droit d'écriture.
RUN useradd --create-home --shell /usr/sbin/nologin ppai
USER ppai

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=2).status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
