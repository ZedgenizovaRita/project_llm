from config import *
import tool_functions
import mistral_functions
from mistral_functions import auto_categorize, call_llm_with_retry, tools, available_functions

load_dotenv()

API_KEY = os.getenv("API_KEY")
client = Mistral(api_key=API_KEY)

def get_role(msg):
    if isinstance(msg, dict):
        return msg.get("role")
    return getattr(msg, "role", None)

def preprocess_df(df):
    required_columns = {"date", "amount", "description"}

    missing = required_columns - set(df.columns)
    if missing:
        df = pd.DataFrame()
        return df

    df = df[[col for col in df.columns if col in required_columns]].copy()

    df['datetime_value'] = pd.to_datetime(df['date'], errors="coerce")
    df = df.dropna(subset=["datetime_value"])

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = df.dropna(subset=["amount"])

    df = df.sort_values(by="datetime_value").reset_index(drop=True)

    if "description" in df.columns:
        df["description"] = df["description"].fillna("").astype(str).str.strip()

    return df

st.set_page_config(page_title="Анализ транзакций", layout="wide")
st.title("Анализ транзакций с помощью LLM")
st.markdown("""
Этот инструмент помогает анализировать ваши банковские транзакции с помощью языковой модели.  
Загрузите CSV-файл — категории определятся автоматически.
Задавайте вопросы по транзакциям в чат-бот. Например, он умеет считать суммы расходов и доходов за конкретный период,
выводить статистику трат по категориям или месяцам,
строить графики, давать советы по оптимизации трат. Старайся излагать свои вопросы точно и ясно.
""")

uploaded_file = st.file_uploader("Загрузите CSV-файл с транзакциями", type=["csv"])

if "df" not in st.session_state:
    st.session_state.df = None

if uploaded_file is not None:
    wrong_file = False
    if st.session_state.df is None or st.session_state.get("uploaded_name") != uploaded_file.name:
        st.session_state.uploaded_name = uploaded_file.name
        with st.spinner("🔄 Обработка данных с помощью LLM..."):
            df = pd.read_csv(uploaded_file, encoding="utf-8")
            df = preprocess_df(df)
            df = auto_categorize(df)

        if df.empty:
            wrong_file = True
            st.success("Ваш файл не соотвествует условиям загрузки")
        else:
            st.session_state.df = df
            tool_functions.set_df(df)
            st.success("✅ Обработка завершена!")
    else:
        df = st.session_state.df

    if not wrong_file:
        col1, col2 = st.columns(2)
        show_table = col1.button("📋 Показать таблицу")

        if show_table:
            st.subheader("📋 Таблица транзакций с категориями")
            st.dataframe(df.drop(columns=['datetime_value']))


        with st.sidebar:
            st.header("🤖 Чат с LLM")

            if "chat_history" not in st.session_state:
                st.session_state.chat_history = []
            if "messages" not in st.session_state:
                st.session_state.messages = []

            user_input = st.text_input("Введите вопрос:")

            if st.button("📨 Отправить"):
                st.session_state.show_table_disabled = True
                if user_input.strip():
                    st.session_state.messages.append({"role": "user", "content": user_input})
                    st.session_state.chat_history.append({"role": "user", "content": user_input})

                    system_prompt = """
                            Ты — финансовый помощник, который анализирует таблицу банковских транзакций.
                            Ты отвечаешь на вопросы пользователя, используя только доступные функции (tools).
                            Никогда не придумывай значения вручную — используй функции для получения данных.

                            ДОСТУПНЫЕ ФУНКЦИИ:
                            - Баланс: get_balance, get_balance_on_date
                            - Вычисление дат: get_date, get_year и др.
                            - Категории: get_categories
                            - Суммы расходов: get_sum_exp_period
                            - Суммы доходов: get_income_period  
                            - Распределение расходов по категориям: get_cat_array_period
                            - Распределени трат по периодам: get_exp_by_periods
                            - Топы и минимумы: get_max_array, get_min_array
                            - Проценты: get_percent, get_percent_array
                            - Сравнения: is_less, is_more, min_value, max_value
                            - Графики: plot_bar_chart, plot_pie_chart, plot_pareto, plot_balance_line, plot_expense_timeline

                            ПРАВИЛА ОПРЕДЕЛЕНИЯ ДАТ:

                            ТЕКУЩАЯ ДАТА:
                            - Всегда используй актуальную дату через функцию get_date()
                            - Не предполагай текущий месяц/год - вызывай get_date(), get_year(), get_month() для точных данных

                            СТАНДАРТНЫЕ ПЕРИОДЫ:
                            - "последний месяц" → предыдущий календарный месяц (например, если сейчас октябрь → сентябрь)
                            - "текущий месяц" → текущий календарный месяц
                            - "прошлый месяц" → предыдущий календарный месяц  
                            - "в прошлом месяце" → предыдущий календарный месяц
                            - "в этом месяце" → текущий календарный месяц
                            - "за последние 30 дней" → от сегодня минус 30 дней до сегодня
                            - "в [месяц]" → первый и последний день указанного месяца в текущем году
                            - "в прошлом году" → с 1 января по 31 декабря предыдущего года

                            ФОРМАТ ДАТ:
                            - Всегда используй формат YYYY-MM-DD
                            - Первый день месяца: YYYY-MM-01
                            - Последний день месяца: вычисляй корректно (28-31 в зависимости от месяца)

                            АЛГОРИТМ ОПРЕДЕЛЕНИЯ ДАТ:
                            1. Для "последний месяц"/"прошлый месяц":
                            - Получи текущую дату через get_date()
                            - Первый день = первый день предыдущего месяца
                            - Последний день = последний день предыдущего месяца

                            2. Для "текущий месяц"/"в этом месяце":
                            - Получи текущую дату через get_date() 
                            - Первый день = первый день текущего месяца
                            - Последний день = последний день текущего месяца

                            3. Для "в [месяц]":
                            - Месяц в текущем году: YYYY-MM-01 — YYYY-MM-31
                            - Например: "в январе" → [текущий_год]-01-01 — [текущий_год]-01-31

                            4. Для "в прошлом году":
                            - [прошлый_год]-01-01 — [прошлый_год]-12-31

                            5. Для "за всё время", "за весь период":
                            - date_start = get_min_date, date_fin = get_max_date

                            ЦЕПОЧКИ ВЫЗОВОВ ДЛЯ СЛОЖНЫХ ЗАПРОСОВ:

                            ДЛЯ ТОП-КАТЕГОРИЙ:
                            Запрос: "топ-3 категории за последний месяц"
                            1. get_cat_array_period(...)
                            2. get_max_array(dict_in=<результат_шага1>, k=3)

                            Запрос: "самые большие траты за октябрь"  
                            1. get_cat_array_period(...)
                            2. get_max_array(dict_in=<результат_шага1>, k=5)

                            ДЛЯ ГРАФИКОВ ПО ТОПАМ:
                            Запрос: "построй график по топ-3 категориям"
                            1. get_cat_array_period(...)
                            2. get_max_array(dict_in=<результат>, k=3)  
                            3. plot_bar_chart(dict_in=<топ_категории>)

                            ДЛЯ ПРОЦЕНТОВ:
                            Запрос: "какой процент от общих трат составляет еда?"
                            1. get_cat_array_period(...) → получаешь все категории
                            2. get_percent(s1=сумма_еды, s2=общая_сумма_расходов)

                            ВАЖНЫЕ ПРАВИЛА:
                            - Всегда вызывай функции ПОСЛЕДОВАТЕЛЬНО, по шагам, если одна функция зависит от результата другой.
                            - Никогда не вызывай несколько функций одновременно, если хотя бы одна из них должна использовать результат другой (например: сначала get_min_date и get_max_date, потом get_sum_exp_period).
                            - Если для функции нужны даты начала и конца — сначала получи их вызовами get_min_date() и get_max_date(), дождись их результатов, и только потом вызови основную функцию (например get_sum_exp_period).
                            - Не вызывай сразу несколько функций для вычисления разных параметров — выполняй их поочерёдно.
                            - После каждого вызова функции обязательно дождись результата, прежде чем планировать следующий вызов.
                            - Если в запросе фигурирует «за всё время», «за весь период», «все расходы» и т.п. — сначала определи границы периода (get_min_date и get_max_date), затем используй их в основной функции (например get_sum_exp_period(date_start=..., date_fin=...)).
                            - Не выдумывай даты — используй только результаты вызовов функций get_min_date(), get_max_date(), get_date(), get_year(), get_month().
                            - не проси вызвать сразу две функции, если в одну нужно подставить результат другой
                            - все суммы указаны в рублях
                            - если пользователь не пишет в запросе год, уточни его
                            - не выводи один и тот же график 2 раза за 1 запрос
                            - в tool-вызовах на графики ты получаешь пустой резульат - это нормально
                            - если пользователь просит вывести что-то за весь период, считай это периодом с date_start=
                            get_min_date(), date_fin = get_max_date()
                            - "трата" = amount < 0 (отрицательная сумма)
                            - Если категория не указана → category="nan"
                            - Если тип графика не ясен - уточни его
                            - Всегда вызывай функции последовательно для сложных запросов
                            - После получения данных от функций → сформулируй краткий понятный ответ
                            - Если функция вернула ошибку → сообщи пользователю и предложи альтернативу
                            - Не предлагай функции, которых нет в списке
                            - Всегда считай проценты через get_percent_array

                            ФОРМАТ ОТВЕТА:
                            - Кратко и по делу
                            - Используй цифры и факты из результатов функций
                            - Добавляй выводы если уместно
                            - Для графиков просто вызови функцию и кратко опиши что показывает график
                            """


                    try:
                        while True:
                            messages= [{"role": "system", "content": system_prompt}] + st.session_state.messages[-50:]

                            if len(messages) > 1 and get_role(messages[1]) == "tool":
                                for i in range(1, len(messages)):
                                    if get_role(messages[i]) in ("user", "assistant"):
                                        messages = [messages[0]] + messages[i:]
                                        break
                                else:
                                    messages = [messages[0]]

                            #print(messages)
                            response = call_llm_with_retry(client, messages=messages, tools=tools, tool_choice="auto")
                            if not response or not getattr(response, "choices", None):
                                st.session_state.messages.append({"role": "assistant", "content": "Модель временно недоступна"})
                                break
                            else:
                                st.session_state.messages.append(response.choices[0].message)

                            choice = response.choices[0]
                            message = choice.message
                            tool_calls = getattr(message, "tool_calls", None)

                            if tool_calls:
                                for call in tool_calls:
                                    func_name = getattr(call.function, "name", None)
                                    args = {}
                                    if getattr(call.function, "arguments", None):
                                        try:
                                            args = json.loads(call.function.arguments)
                                        except Exception:
                                            args = {}

                                    func = available_functions.get(func_name)
                                    if func:
                                        try:
                                            result = func(**args) if callable(func) else func
                                        except Exception as e:
                                            result = {"error": f"Ошибка выполнения функции {func_name}: {e}"}
                                    else:
                                        result = {"error": f"Функция {func_name} не найдена"}

                                    if isinstance(result, dict) and "image_base64" in result:
                                        safe_result = result.copy()
                                        st.session_state.chat_history.append({"role": "assistant", "content": safe_result})
                                        result["image_base64"] = ''

                                    st.session_state.messages.append({
                                        "role": "tool",
                                        "tool_call_id": getattr(call, "id", None),
                                        "content": json.dumps(result, ensure_ascii=False, default=str)
                                    })

                            else:
                                answer = getattr(message, "content", None) or "Модель не вернула текст."
                                image_indicators = ['<img', '![', '.jpg', '.png', '.gif', '.webp', 'data:image']
                                has_image = any(indicator in answer.lower() for indicator in image_indicators)
        
                                if not has_image:
                                    st.session_state.chat_history.append({"role": "assistant", "content": answer})
                                break
                    
                    except Exception as e:
                        st.session_state.chat_history.append({"role": "assistant", "content": f"Ошибка при обращении к API: {e}"})
                else:
                    st.warning("Введите текст перед отправкой.")

            if st.button("🗑️ Очистить чат"):
                st.session_state.chat_history = []
                st.success("История чата очищена.")

            if st.session_state.chat_history:
                st.markdown("---")
                st.subheader("💬 История диалога")

                for msg in reversed(st.session_state.chat_history):
                    role = msg.get("role")
                    content = msg.get("content")

                    if role == "user" and content:
                        st.markdown(f"**👤 Вы:** {content}")

                    elif role == "assistant":
                        if isinstance(content, dict) and "image_base64" in content:
                            if content["image_base64"]:
                                try:
                                    img_bytes = base64.b64decode(content["image_base64"])
                                    image = Image.open(BytesIO(img_bytes))
                                    st.image(image, caption="📊 График", width="stretch")
                                except Exception as e:
                                    st.warning(f"Не удалось отобразить график: {e}")
                        elif content:
                            st.markdown(f"**🤖 Бот:** {content}")
    else:
        st.info("⬆️ Загрузите CSV-файл, чтобы начать анализ.")


else:
    st.info("⬆️ Загрузите CSV-файл, чтобы начать анализ.")
