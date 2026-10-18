# Публикация сайта (Streamlit Community Cloud)

Репозиторий уже подготовлен: `requirements.txt`, `.gitignore`, тема в `.streamlit/config.toml`.

1. Создайте на github.com новый репозиторий (например, `astana-guide`), публичный или приватный.
2. Загрузите в него проект (из папки проекта):
   ```bash
   git remote add origin https://github.com/<ваш-логин>/astana-guide.git
   git push -u origin main
   ```
   (Если GitHub попросит пароль, используйте Personal Access Token или GitHub Desktop.)
3. Откройте https://share.streamlit.io → **Create app** → выберите репозиторий, ветку `main`, файл `app.py`.
4. В **Advanced settings** выберите Python 3.12 или 3.13. Если есть ключ Gemini, добавьте в **Secrets**:
   ```toml
   GEMINI_API_KEY = "ваш_ключ"
   ```
   Без ключа приложение работает: текст рекомендаций собирается по найденным данным.
5. Нажмите **Deploy**. Через 2–3 минуты появится постоянная ссылка вида `https://<имя>.streamlit.app`.

Что видно публично: код (если репозиторий публичный), фото мест из `assets/photos/`, база мест `data/pois.json`.
