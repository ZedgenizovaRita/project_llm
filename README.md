```bash
git clone https://github.com/ZedgenizovaRita/project_llm.git
cd project_llm

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt

Создайте файл `.env` в корне проекта, куда вставьте:
MISTRAL_API_KEY=your_api_key_here
(API-ключ Mistral, без кавычек)

python -m streamlit run app.py

Для примера можно вставить таблицу tr.csv
