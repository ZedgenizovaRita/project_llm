from config import *
from tool_functions import *

load_dotenv()

API_KEY = os.getenv("API_KEY")
client = Mistral(api_key=API_KEY)

def parse_llm_json(content):
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                return {}
    return {}

def call_llm_with_retry(client, messages, tools=None, tool_choice="auto", retries=10, delay=2):
    for attempt in range(1, retries + 1):
        try:
            response = client.chat.complete(
                model="mistral-large-latest",
                messages=messages,
                tools=tools,
                tool_choice=tool_choice
            )

            if response is None or not getattr(response, "choices", None):
                print(f"Пустой или некорректный ответ от API (попытка {attempt}/{retries}).")
                if attempt < retries:
                    time.sleep(delay)
                    continue
                else:
                    print("Все попытки исчерпаны. Возврат None.")
                    return None

            choice = response.choices[0]
            message = getattr(choice, "message", None)
            if message is None:
                print(f"Нет объекта message в ответе (попытка {attempt}/{retries}).")
                if attempt < retries:
                    time.sleep(delay)
                    continue
                else:
                    return None

            tool_calls = getattr(message, "tool_calls", None)

            if tool_calls:
                print("=== LLM собирается вызвать функции ===")
                for call in tool_calls:
                    print("Имя функции:", call.function.name)
                    print("Аргументы (json):", call.function.arguments)
                    print("ID вызова:", call.id)
                    print("--------------------------")
            else:
                print("LLM не вызвала функций.")

            return response

        except Exception as e:
            err_str = str(e)

            temporary_errors = [
                "Service tier capacity exceeded",
                "Status 503",
                "Status 429",
                "Server disconnected without sending a response",
                "Connection aborted",
                "Remote end closed connection"
            ]

            if any(err in err_str for err in temporary_errors):
                print(f"Ошибка при обращении к API (попытка {attempt}/{retries}): {err_str}")
                if attempt < retries:
                    time.sleep(delay)
                    continue
                else:
                    print("Все попытки исчерпаны. Возврат None.")
                    return None
            else:
                raise e

    return None

def categorize_with_llm(descriptions, batch_size=30):
    categories = {}

    for i in range(0, len(descriptions), batch_size):
        batch = descriptions[i:i + batch_size]

        prompt = (
            "Распредели следующие транзакции по категориям. "
            "Верни строго JSON формат: {\"описание\": \"категория\", ...}. "
            "Категории: Еда, Транспорт, Покупки, Переводы, Доход, Дом, Развлечения, Здоровье, Другое.\n"
            + "\n".join(batch)
        )

        resp = call_llm_with_retry(client,
                                   messages=[{"role": "user", "content": prompt}])
        content = resp.choices[0].message.content.strip()
        batch_categories = parse_llm_json(content)
        categories.update(batch_categories)

        missing = [d for d in batch if d not in batch_categories]
        if missing:
            prompt2 = ("Повтори категоризацию только для этого списка (только JSON):\n" + "\n".join(missing))
            resp2 = call_llm_with_retry(client,
                                        messages=[{"role": "user", "content": prompt2}])
            content2 = resp2.choices[0].message.content.strip()
            categories.update(parse_llm_json(content2))

    for d in descriptions:
        if d not in categories:
            categories[d] = "Другое"

    return categories

def auto_categorize(df):
    if df.empty:
        return df
    descriptions = df["description"].dropna().unique().tolist()
    categories = categorize_with_llm(descriptions)

    df["category"] = df["description"].map(categories)

    return df


tools = [
    # БАЗОВЫЕ ФУНКЦИИ
    {
        "type": "function",
        "function": {
            "name": "get_all_cnt",
            "description": "Возвращает общее количество транзакций в таблице.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_balance",
            "description": "Возвращает текущий баланс пользователя (остаток средств на счету).",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_date",
            "description": "Возвращает сегодняшнюю дату (текущий день, месяц и год).",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_categories",
            "description": "Возвращает список всех категорий расходов, по которым есть ненулевые траты.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_balance_on_date",
            "description": "Возвращает баланс на указанную дату (на момент начала суток)",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Дата в формате YYYY-MM-DD"}
                },
                "required": ["date"]
            }
        }
    },

    # СУММЫ РАСХОДОВ И ДОХОДОВ
    {
        "type": "function",
        "function": {
            "name": "get_sum_exp_period",
            "description": "Возвращает сумму расходов за произвольный период между двумя датами (например, '2025-01-01'–'2025-01-31' для января). Если category не указана, суммируются траты по всем категориям.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_start": {"type": "string", "description": "Дата начала периода (YYYY-MM-DD)"},
                    "date_fin": {"type": "string", "description": "Дата конца периода (YYYY-MM-DD)"},
                    "category": {"type": "string", "description": "Категория расходов (необязательно)"}
                },
                "required": ["date_start", "date_fin"]
            }
        }
    },

    # РАСПРЕДЕЛЕНИЯ И ПРОЦЕНТЫ
    {
    "type": "function",
    "function": {
        "name": "get_cat_array_period",
        "description": "Возвращает словарь (категория: сумма расходов) за указанный период между двумя датами (включительно).",
        "parameters": {
            "type": "object",
            "properties": {
                "date_start": {"type": "string", "description": "Дата начала периода (в формате YYYY-MM-DD)"},
                "date_fin": {"type": "string", "description": "Дата конца периода (в формате YYYY-MM-DD)"}
            },
            "required": ["date_start", "date_fin"]
        }
    }
    },

    # МАТЕМАТИЧЕСКИЕ ФУНКЦИИ
    {
        "type": "function",
        "function": {
            "name": "get_percent",
            "description": "Возвращает процентное соотношение: сколько s1 составляет от s2.",
            "parameters": {
                "type": "object",
                "properties": {"s1": {"type": "number"}, "s2": {"type": "number"}},
                "required": ["s1", "s2"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_percent_array",
            "description": "Принимает словарь {ключ: сумма} и возвращает словарь {ключ: процент от общей суммы}.",
            "parameters": {"type": "object", "properties": {"dict_in": {"type": "object"}}, "required": ["dict_in"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_max_array",
            "description": "Возвращает первые K элементов с наибольшими значениями из любого словаря. Используй для: топ-N категорий по расходам, максимальные суммы, наибольшие значения по периодам и т.д. Работает с любым словарем вида {ключ: число}.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dict_in": {
                        "type": "object",
                        "description": "Любой словарь с числовыми значениями {ключ: число} для анализа"
                    },
                    "k": {
                        "type": "integer",
                        "description": "Количество максимальных элементов для возврата",
                        "default": 3
                    }
                },
                "required": ["dict_in"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_min_array", 
            "description": "Возвращает первые K элементов с наименьшими значениями из любого словаря. Используй для: минимальные расходы по категориям, наименьшие суммы, самые маленькие значения и т.д.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dict_in": {
                        "type": "object",
                        "description": "Любой словарь с числовыми значениями {ключ: число} для анализа"
                    },
                    "k": {
                        "type": "integer",
                        "description": "Количество минимальных элементов для возврата", 
                        "default": 3
                    }
                },
                "required": ["dict_in"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "min_value",
            "description": "Возвращает минимальное из двух чисел.",
            "parameters": {
                "type": "object",
                "properties": {"s1": {"type": "number"}, "s2": {"type": "number"}},
                "required": ["s1", "s2"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "max_value",
            "description": "Возвращает максимальное из двух чисел.",
            "parameters": {
                "type": "object",
                "properties": {"s1": {"type": "number"}, "s2": {"type": "number"}},
                "required": ["s1", "s2"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "is_less",
            "description": "Возвращает True, если первое число меньше второго.",
            "parameters": {
                "type": "object",
                "properties": {"s1": {"type": "number"}, "s2": {"type": "number"}},
                "required": ["s1", "s2"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "is_more",
            "description": "Возвращает True, если первое число больше второго.",
            "parameters": {
                "type": "object",
                "properties": {"s1": {"type": "number"}, "s2": {"type": "number"}},
                "required": ["s1", "s2"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_len",
            "description": "Возвращает длину (количество элементов) переданного массива данных.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_array": {
                        "type": "array",
                        "description": "Список (например, список транзакций), длину которого нужно определить"
                    }
                },
                "required": ["data_array"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_mean_array",
            "description": "Вычисляет среднее значение всех чисел в словаре (например, средние расходы по категориям).",
            "parameters": {
                "type": "object",
                "properties": {
                    "dict_in": {
                        "type": "object",
                        "description": "Словарь вида {ключ: числовое_значение}, например {'Еда': 1200, 'Транспорт': 800}"
                    }
                },
                "required": ["dict_in"]
            }
        }
    },


    # ГРАФИКИ
    {
        "type": "function",
        "function": {
            "name": "plot_bar_chart",
            "description": "Строит столбчатую диаграмму по словарю расходов (категория: сумма) и возвращает изображение в base64.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dict_in": {"type": "object", "description": "Словарь вида категория: сумма расходов"}
                },
                "required": ["dict_in"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "plot_pie_chart",
            "description": "Строит круговую диаграмму по словарю расходов (категория: сумма) и возвращает изображение в base64.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dict_in": {"type": "object", "description": "Словарь вида категория: сумма расходов"}
                },
                "required": ["dict_in"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "plot_balance_line",
            "description": "Строит график изменения баланса по времени на основе начальной и конечной даты периода, возвращает изображение в base64.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Дата начала периода (YYYY-MM-DD, необязательно)"},
                    "fin_date": {"type": "string", "description": "Дата конца периода (YYYY-MM-DD, необязательно)"},
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "plot_expense_timeline",
            "description": "Строит график расходов по неделям, месяцам или годам в указанном периоде . Возвращает изображение в base64.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Дата начала периода (YYYY-MM-DD, необязательно)"},
                    "fin_date": {"type": "string", "description": "Дата конца периода (YYYY-MM-DD, необязательно)"},
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "plot_pareto",
            "description": (
                "Строит диаграмму Парето (Pareto chart) — комбинированный график, "
                "который показывает, какие категории дают наибольший вклад в общие расходы. "
                "Отображает столбчатую диаграмму по категориям и линию накопленного процента, "
                "чтобы определить, какие категории формируют основную часть расходов (правило 80/20)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dict_in": {
                        "type": "object",
                        "description": (
                            "Словарь вида {категория: сумма расходов}. "
                            "Категории сортируются по убыванию суммы перед построением графика."
                        )
                    }
                },
                "required": ["dict_in"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "plot_expenses_bar",
            "description": "Строит столбчатую диаграмму расходов по периодам (неделям, месяцам, годам). Если категория не указана, делает сложенные столбцы по категориям.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period_name": {"type": "string", "description": "Период группировки: week, month или year"},
                    "start_date": {"type": "string", "description": "Дата начала периода (YYYY-MM-DD, необязательно)"},
                    "fin_date": {"type": "string", "description": "Дата конца периода (YYYY-MM-DD, необязательно)"},
                    "category": {"type": "string", "description": "Категория расходов (необязательно)"}
                }
            }
        }
    },

    # РАБОТА С ДАТАМИ
    {
        "type": "function",
        "function": {
            "name": "get_trans_array_period",
            "description": "Возвращает баланс на начало указанного периода и все транзакции в этом периоде за категорию. Если категорий не указа (='nan'), то по всем категориям.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_start": {"type": "string", "description": "Дата начала периода в формате YYYY-MM-DD"},
                    "date_fin": {"type": "string", "description": "Дата окончания периода в формате YYYY-MM-DD"},
                    "category": {"type": "string", "description": "Категория расходов (опционально)"}
                },
                "required": ["date_start", "date_fin"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_income_period",
            "description": "Возвращает общую сумму доходов (amount > 0) за указанный период между двумя датами.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_start": {
                        "type": "string",
                        "description": "Дата начала периода (в формате YYYY-MM-DD)"
                    },
                    "date_fin": {
                        "type": "string",
                        "description": "Дата конца периода (в формате YYYY-MM-DD)"
                    }
                },
                "required": ["date_start", "date_fin"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_exp_by_periods",
            "description": (
                "Возвращает массив расходов, сгруппированных по неделям, месяцам или годам "
                "за указанный период. Если категория не указана, считает по всем категориям."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Дата начала периода (в формате YYYY-MM-DD, опционально)"
                    },
                    "fin_date": {
                        "type": "string",
                        "description": "Дата конца периода (в формате YYYY-MM-DD, опционально)"
                    },
                    "category": {
                        "type": "string",
                        "description": "Категория расходов (необязательно)"
                    },
                    "period_name": {
                        "type": "string",
                        "enum": ["week", "month", "year"],
                        "description": "Тип периода группировки: неделя, месяц или год"
                    }
                },
                "required": ["period_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_income_by_periods",
            "description": (
                "Возвращает массив доходов, сгруппированных по неделям, месяцам или годам "
                "за указанный период. Если категория не указана, считает по всем категориям."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Дата начала периода (в формате YYYY-MM-DD, опционально)"
                    },
                    "fin_date": {
                        "type": "string",
                        "description": "Дата конца периода (в формате YYYY-MM-DD, опционально)"
                    },
                    "category": {
                        "type": "string",
                        "description": "Категория расходов (необязательно)"
                    },
                    "period_name": {
                        "type": "string",
                        "enum": ["week", "month", "year"],
                        "description": "Тип периода группировки: неделя, месяц или год"
                    }
                },
                "required": ["period_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_income_trans_array_period",
            "description": "Возвращает массив всех доходов (положительных транзакций) за указанный период. Можно указать категорию.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_start": {"type": "string", "description": "Дата начала периода (в формате YYYY-MM-DD)"},
                    "date_fin": {"type": "string", "description": "Дата конца периода (в формате YYYY-MM-DD)"},
                    "category": {"type": "string", "description": "Категория доходов (необязательно)"}
                },
                "required": ["date_start", "date_fin"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_exp_by_periods_by_category",
            "description": "Возвращает словарь расходов по категориям, сгруппированных по неделям, месяцам или годам. Каждый период содержит подсловарь с суммами по категориям.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Дата начала периода (в формате YYYY-MM-DD). Если не указана, используется минимальная дата из таблицы."
                    },
                    "fin_date": {
                        "type": "string",
                        "description": "Дата конца периода (в формате YYYY-MM-DD). Если не указана, используется максимальная дата из таблицы."
                    },
                    "period_name": {
                        "type": "string",
                        "enum": ["week", "month", "year"],
                        "description": "Период группировки: 'week' — по неделям, 'month' — по месяцам, 'year' — по годам."
                    }
                },
                "required": []
            }
        }
    },

    {
        "type": "function",
        "function": {
        "name": "get_n_days_ago",
        "description": "Возвращает дату n дней назад от ref (или сегодня, если ref не указан).",
        "parameters": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "description": "Количество дней назад"},
                "ref": {"type": ["string", "null"], "description": "Референсная дата (формат YYYY-MM-DD), по умолчанию сегодня"}
            },
            "required": ["n"]
        },
        "func": get_n_days_ago
        }
    },
    {
        "type": "function",
        "function": {
        "name": "get_n_weeks_ago",
        "description": "Возвращает дату n недель назад от ref (или сегодня, если ref не указан).",
        "parameters": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "description": "Количество недель назад"},
                "ref": {"type": ["string", "null"], "description": "Референсная дата (формат YYYY-MM-DD), по умолчанию сегодня"}
            },
            "required": ["n"]
        },
        "func": get_n_weeks_ago
        }
    },
    {
        "type": "function",
        "function": {
        "name": "get_n_month_ago",
        "description": "Возвращает дату n месяцев назад от ref (или сегодня, если ref не указан).",
        "parameters": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "description": "Количество месяцев назад"},
                "ref": {"type": ["string", "null"], "description": "Референсная дата (формат YYYY-MM-DD), по умолчанию сегодня"}
            },
            "required": ["n"]
        },
        "func": get_n_month_ago
        }
    },
    {
        "type": "function",
        "function": {
        "name": "get_n_year_ago",
        "description": "Возвращает дату n лет назад от ref (или последней даты в DataFrame, или сегодня).",
        "parameters": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "description": "Количество лет назад"},
                "ref": {"type": ["string", "null"], "description": "Референсная дата (формат YYYY-MM-DD), по умолчанию последняя дата df или сегодня"},
            },
            "required": ["n"]
        },
        "func": get_n_year_ago
        }
    },
    {   
        "type": "function",
        "function": {
        "name": "get_year",
        "description": "Возвращает год из даты d (или последней даты df).",
        "parameters": {
            "type": "object",
            "properties": {
                "d": {"type": ["string", "null"], "description": "Дата в формате YYYY-MM-DD"}
            }
        },
        "func": get_year
        }
    },
    {
        "type": "function",
        "function": {
        "name": "get_month",
        "description": "Возвращает месяц из даты d (или последней даты df).",
        "parameters": {
            "type": "object",
            "properties": {
                "d": {"type": ["string", "null"], "description": "Дата в формате YYYY-MM-DD"}
            }
        },
        "func": get_month
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_min_date",
            "description": "Возвращает минимальную дату из таблицы в формате YYYY-MM-DD.",
            "parameters": {
                "type": "object",
            },
            "func": get_min_date
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_max_date",
            "description": "Возвращает минимальную дату из таблицы в формате YYYY-MM-DD.",
            "parameters": {
                "type": "object"
            },
            "func": get_max_date
        }
    },
]

available_functions = {
    "get_balance": get_balance,
    "get_balance_on_date": get_balance_on_date,
    "get_date": get_date,
    "get_categories": get_categories,

    "get_sum_exp_period": get_sum_exp_period,
    "get_income_period": get_income_period,

    "get_cat_array_period": get_cat_array_period,
    
    "get_exp_by_periods": get_exp_by_periods,
    "get_exp_by_periods_by_category": get_exp_by_periods_by_category,
    "get_income_by_periods": get_income_by_periods,

    "get_trans_array_period": get_trans_array_period,
    "get_income_trans_array_period": get_income_trans_array_period,

    "get_percent": get_percent,
    "get_percent_array": get_percent_array,
    "get_max_array": get_max_array,
    "get_min_array": get_min_array,
    "get_mean_array": get_mean_array,
    "get_len": get_len,
    "min_value": min_value,
    "max_value": max_value,
    "is_less": is_less,
    "is_more": is_more,

    "plot_bar_chart": plot_bar_chart,
    "plot_pie_chart": plot_pie_chart,
    "plot_balance_line": plot_balance_line,
    "plot_expense_timeline": plot_expense_timeline,
    "plot_pareto": plot_pareto,
    "plot_expense_timeline": plot_expense_timeline,
    "plot_expenses_bar": plot_expenses_bar,

    "get_min_date": get_min_date,
    "get_max_date": get_max_date,
    "get_n_days_ago": get_n_days_ago,
    "get_n_weeks_ago": get_n_weeks_ago,
    "get_n_month_ago": get_n_month_ago,
    "get_n_year_ago": get_n_year_ago,
    "get_year": get_year,
    "get_month": get_month,
    "get_all_cnt": get_all_cnt
}