FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY bot.py config.py database.py docker_manager.py xui_manager.py ./

RUN python -m py_compile bot.py config.py database.py docker_manager.py xui_manager.py

CMD ["python", "bot.py"]
