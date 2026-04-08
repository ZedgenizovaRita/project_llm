from config import *

df = None

def set_df(df1):
    global df
    df = df1

def get_min_date():
    print(df['datetime_value'].min().strftime("%Y-%m-%d"))
    return df['datetime_value'].min().strftime("%Y-%m-%d")

def get_max_date():
    print(df['datetime_value'].max().strftime("%Y-%m-%d"))
    return df['datetime_value'].max().strftime("%Y-%m-%d")

def get_date():
    print(datetime.now().strftime("%Y-%m-%d"))
    return datetime.now().strftime("%Y-%m-%d")

def get_n_days_ago(n, ref) :
    if ref is None or ref == "nan":
        ref = datetime.now().date()
    return ref - timedelta(days=n)

def get_n_weeks_ago(n, ref) :
    return get_n_days_ago(n * 7, ref)

def get_n_month_ago(n, ref) :
    if ref is None or ref == "nan":
        ref = datetime.now().date()
    year = ref.year
    month = ref.month - n

    while month <= 0:
        month += 12
        year -= 1

    day = min(ref.day, calendar.monthrange(year, month)[1])
    return date(year, month, day).strftime("%Y-%m-%d")

def get_n_year_ago(n, ref):
    if ref is None or ref == "nan":
        ref = get_date()
    
    year = ref.year - n
    month = ref.month
    day = ref.day

    if month == 2 and day == 29:
        if not (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)):
            day = 28
    
    return ref.replace(year=year, day=day)

def get_year(d):
    if d is None or d == "nan":
        d = get_date()
    d = pd.to_datetime(d, errors="coerce")
    return d.year

def get_month(d):
    if d is None or d == "nan":
        d = get_date()
    d = pd.to_datetime(d, errors="coerce")
    return d.month

def get_percent(s1, s2):
    return ((s1 / s2 * 100) if s2 else 0)

def get_percent_array(dict_in):
    total = sum(dict_in.values())
    return {k: (v / total * 100) for k, v in dict_in.items()}

def get_len(data_array):
    return len(data_array)

def get_mean_array(dict_in):
    if not dict_in:
        return {}
    
    values = list(dict_in.values())
    numeric_values = [v for v in values if isinstance(v, (int, float))]

    if not numeric_values:
        return 0.0

    mean_value = sum(numeric_values) / len(numeric_values)
    return float(mean_value)

def get_categories():
    cats = df["category"].unique().tolist()
    return cats

def get_all_cnt():
    return len(df)

def get_max_array(dict_in, k=1):
    if not dict_in:
        return {}
    sorted_items = sorted(dict_in.items(), key=lambda x: x[1], reverse=True)
    top_items = sorted_items[:k]
    result = {cat: val for cat, val in top_items}
    return result

def get_min_array(dict_in, k=1):
    if not dict_in:
        return {}
    sorted_items = sorted(dict_in.items(), key=lambda x: x[1])
    bottom_items = sorted_items[:k]
    result = {cat: val for cat, val in bottom_items}
    return result

def min_value(s1, s2): return min(s1, s2)
def max_value(s1, s2): return max(s1, s2)
def is_less(s1, s2): return s1 < s2
def is_more(s1, s2): return s1 > s2

def get_balance():
    balance = float(df["amount"].sum())
    print(balance)
    return balance

def get_balance_on_date(date):
    target_date = pd.to_datetime(date)
    df_filtered = df[df['datetime_value'] < target_date] 
    balance = df_filtered['amount'].sum()

    print(balance)
    
    return balance

def get_income_period(date_start, date_fin):
    start_date = pd.to_datetime(date_start)
    end_date = pd.to_datetime(date_fin)

    mask = (df["datetime_value"] >= start_date) & (df["datetime_value"] <= end_date)
    mask &= (df["amount"] > 0)
    total = df.loc[mask, "amount"].sum()

    print(f"Доходы за период {start_date} — {end_date}, сумма: {total}")
    return float(total)

def get_sum_exp_period(date_start, date_fin, category=None):
    date_start = pd.to_datetime(date_start, errors="coerce")
    date_fin = pd.to_datetime(date_fin, errors="coerce")

    mask = (df["datetime_value"] >= date_start) & (df["datetime_value"] <= date_fin) & (df["amount"] < 0)
    
    if category and str(category).lower() != "nan":
        mask &= (df["category"] == category)
    mask &= (df["amount"] < 0)

    total = df.loc[mask, "amount"].sum()
    
    print(f"Период: {date_start} — {date_fin}, категория: {category}, сумма: {-total}")
    
    return float(-total)

def get_trans_array_period(date_start, date_fin):
    start_date = pd.to_datetime(date_start)
    end_date = pd.to_datetime(date_fin)
    
    balance_before = get_balance_on_date(date_start)
    
    mask = (df["datetime_value"] >= start_date) & (df["datetime_value"] <= end_date)
    df_period = df.loc[mask].copy()

    return float(balance_before), df_period[["date", "category", "amount", "description"]].to_dict(orient="records")

def get_cat_array_period(date_start, date_fin):
    date_start = pd.to_datetime(date_start, errors="coerce")
    date_fin = pd.to_datetime(date_fin, errors="coerce")

    mask = (df["datetime_value"] >= date_start) & (df["datetime_value"] <= date_fin) & (df["amount"] < 0)

    summary = df[mask].loc.groupby("category")["amount"].sum()

    result = {cat: -total for cat, total in summary.items()}

    for cat, total in result.items():
        print(cat, total)

    return result

def get_exp_by_periods(start_date=None, fin_date=None, category=None, period_name="week"):
    if start_date is None:
        start_date = df["datetime_value"].min()
    else:
        start_date = pd.to_datetime(start_date, errors="coerce")

    if fin_date is None:
        fin_date = df["datetime_value"].max()
    else:
        fin_date = pd.to_datetime(fin_date, errors="coerce")

    mask = (df["datetime_value"] >= start_date) & (df["datetime_value"] <= fin_date)
    if category and str(category).lower() != "nan":
        mask &= df["category"].str.lower().eq(str(category).lower())
    mask &= df["amount"] < 0

    df_period = df.loc[mask].copy()
    if df_period.empty:
        return []

    df_period["date"] = pd.to_datetime(df_period["date"], errors="coerce")

    if period_name.lower() in ["week", "weeks"]:
        df_period["start"] = df_period["date"] - pd.to_timedelta(df_period["date"].dt.weekday, unit="d")
        df_period["period_label"] = df_period["start"].dt.strftime("%Y-W%V")
    elif period_name.lower() in ["month", "months"]:
        df_period["start"] = df_period["date"].dt.to_period("M").dt.to_timestamp()
        df_period["period_label"] = df_period["start"].dt.strftime("%Y-%m")
    elif period_name.lower() in ["year", "years"]:
        df_period["start"] = pd.to_datetime(df_period["date"].dt.year.astype(str) + "-01-01")
        df_period["period_label"] = df_period["start"].dt.strftime("%Y")

    grouped = (
        df_period.groupby("period_label")["amount"]
        .sum()
        .apply(lambda x: -x)
        .reset_index()
    )

    result = grouped.rename(columns={"period_label": "period", "amount": "sum"}).to_dict(orient="records")
    print("get_exp_by_periods:", result)
    return result

def get_exp_by_periods_by_category(start_date=None, fin_date=None, period_name="month"):
    mask = df["amount"] < 0

    if start_date:
        start_date = pd.to_datetime(start_date)
        mask &= (df["datetime_value"] >= start_date)

    if fin_date:
        fin_date = pd.to_datetime(fin_date)
        mask &= (df["datetime_value"] <= fin_date)

    df_copy = df[mask].copy()

    if period_name in ["week", "weeks"]:
        df_copy["period"] = df_copy["datetime_value"].dt.to_period("W").apply(lambda r: r.start_time.strftime("%Y-%m-%d"))
    elif period_name in ["month", "months"]:
        df_copy["period"] = df_copy["datetime_value"].dt.to_period("M").astype(str)
    elif period_name in ["year", "years"]:
        df_copy["period"] = df_copy["datetime_value"].dt.year.astype(str)
    else:
        raise ValueError(f"Некорректный period_name: {period_name}")

    grouped = (
        df_copy.groupby(["period", "category"])["amount"]
        .sum()
        .apply(lambda x: -x)
        .reset_index()
    )

    result = {}
    for period, group in grouped.groupby("period"):
        result[period] = dict(zip(group["category"], group["amount"]))

    return result

def get_income_trans_array_period(date_start, date_fin, category=None):
    start_date = pd.to_datetime(date_start)
    end_date = pd.to_datetime(date_fin)

    mask = (df["datetime_value"] >= start_date) & (df["datetime_value"] <= end_date) & (df["amount"] > 0)
    if category and category in get_categories(df):
        mask &= (df["category"] == category)

    df_income = df.loc[mask].copy()
    if df_income.empty:
        return []

    return df_income[["date", "category", "amount", "description"]].to_dict(orient="records")

def get_income_by_periods(start_date=None, fin_date=None, category=None, period_name = "week"):
    if start_date is None:
        start_date = df["datetime_value"].min()
    else:
        start_date = pd.to_datetime(start_date, errors="coerce")

    if fin_date is None:
        fin_date = df["datetime_value"].max()
    else:
        fin_date = pd.to_datetime(fin_date, errors="coerce")

    mask = (df["datetime_value"] >= start_date) & (df["datetime_value"] <= fin_date)
    if category and str(category).lower() != "nan":
        mask &= df["category"].str.lower().eq(str(category).lower())
    mask &= df["amount"] > 0

    df_period = df.loc[mask].copy()
    if df_period.empty:
        return []

    df_period["date"] = pd.to_datetime(df_period["date"], errors="coerce")

    if period_name.lower() in ["week", "weeks"]:
        df_period["start"] = df_period["date"] - pd.to_timedelta(df_period["date"].dt.weekday, unit="d")
        df_period["period_label"] = df_period["start"].dt.strftime("%Y-W%V")
    elif period_name.lower() in ["month", "months"]:
        df_period["start"] = df_period["date"].dt.to_period("M").dt.to_timestamp()
        df_period["period_label"] = df_period["start"].dt.strftime("%Y-%m")
    elif period_name.lower() in ["year", "years"]:
        df_period["start"] = pd.to_datetime(df_period["date"].dt.year.astype(str) + "-01-01")
        df_period["period_label"] = df_period["start"].dt.strftime("%Y")

    grouped = (
        df_period.groupby("period_label")["amount"]
        .sum()
        .apply(lambda x: -x)
        .reset_index()
    )

    result = grouped.rename(columns={"period_label": "period", "amount": "sum"}).to_dict(orient="records")
    print("get_income_by_periods:", result)
    return result

def plot_bar_chart(dict_in):
    categories = list(dict_in.keys())
    values = list(dict_in.values())

    plt.figure(figsize=(8, 4))
    plt.bar(categories, values)
    plt.title("Траты по категориям")
    plt.xlabel("Категория")
    plt.ylabel("Сумма трат")
    plt.xticks(rotation=30)
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format="png")
    plt.close()
    buf.seek(0)
    img_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return {"image_base64": img_base64}

def plot_pie_chart(dict_in):
    categories = list(dict_in.keys())
    values = list(dict_in.values())

    plt.figure(figsize=(6, 6))
    plt.pie(values, labels=categories, autopct="%1.1f%%", startangle=90)
    plt.title("Доля категорий в расходах")

    buf = BytesIO()
    plt.savefig(buf, format="png")
    plt.close()
    buf.seek(0)
    img_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return {"image_base64": img_base64}

def plot_balance_line(start_date=None, fin_date=None):
    initial_balance, transactions = get_trans_array_period(start_date, fin_date)

    transactions = pd.DataFrame(transactions)

    transactions["date"] = pd.to_datetime(transactions["date"])
    transactions = transactions.sort_values("date")

    transactions["balance"] = initial_balance + transactions["amount"].cumsum()

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(transactions["date"], transactions["balance"], marker='o', linestyle='-')

    ax.set_title("Изменение баланса по времени")
    ax.set_xlabel("Дата")
    ax.set_ylabel("Баланс")
    ax.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode("utf-8")

    return {"image_base64": img_base64}

def plot_expense_timeline(period_name="month", start_date=None, fin_date=None, category=None):
    period_name = str(period_name).lower().strip()

    data = get_exp_by_periods(start_date, fin_date, category, period_name)

    if not data or len(data) == 0:
        return {"error": "Нет данных для построения графика."}

    label_map = {
        "week": "Неделям",
        "weeks": "Неделям",
        "month": "Месяцам",
        "months": "Месяцам",
        "year": "Годам",
        "years": "Годам"
    }
    label = label_map.get(period_name, "Период")

    df_plot = pd.DataFrame(data)
    df_plot = df_plot.sort_values("period")

    plt.figure(figsize=(8, 4))
    plt.plot(df_plot["period"], df_plot["sum"], marker="o", linewidth=2)
    plt.title(f"📊 Расходы по {label.lower()}")
    plt.xlabel(label)
    plt.ylabel("Сумма расходов")
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close()
    buf.seek(0)

    image_base64 = base64.b64encode(buf.read()).decode("utf-8")

    return {"image_base64": image_base64}

def plot_expenses_bar(period_name="month", start_date=None, fin_date=None, category=None):
    data = get_exp_by_periods_by_category(start_date, fin_date, period_name)

    if not data:
        return {"error": "Нет данных для построения графика."}

    df_plot = pd.DataFrame(data).fillna(0).T 

    plt.figure(figsize=(8, 4))

    label_map = {
        "week": "Неделям",
        "weeks": "Неделям",
        "month": "Месяцам",
        "months": "Месяцам",
        "year": "Годам",
        "years": "Годам"
    }
    label = label_map.get(period_name, "Период")

    if category and str(category).lower() != "nan":
        if category not in df_plot.columns:
            return {"error": f"Категория '{category}' не найдена."}
        plt.bar(df_plot.index, df_plot[category], color="skyblue")
        plt.title(f"📊 Расходы по категории '{category}' по {label}")
        plt.ylabel("Сумма расходов")
    else:
        df_plot.plot(kind="bar", stacked=True, figsize=(8, 4))
        plt.title(f"📊 Расходы по категориям по {label}")
        plt.ylabel("Сумма расходов")

    plt.xlabel("Период")
    plt.xticks(rotation=45)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close()
    buf.seek(0)

    image_base64 = base64.b64encode(buf.read()).decode("utf-8")
    return {"image_base64": image_base64}

def plot_pareto(dict_in):
    if not dict_in or not isinstance(dict_in, dict):
        return {"error": "Некорректные данные для построения графика."}

    sorted_items = sorted(dict_in.items(), key=lambda x: x[1], reverse=True)
    categories = [k for k, _ in sorted_items]
    values = [v for _, v in sorted_items]

    cumulative = []
    total = sum(values)
    running_sum = 0
    for v in values:
        running_sum += v
        cumulative.append(running_sum / total * 100)

    fig, ax1 = plt.subplots(figsize=(8, 4))

    ax1.bar(categories, values, color="skyblue")
    ax1.set_xlabel("Категория")
    ax1.set_ylabel("Сумма трат", color="blue")
    ax1.tick_params(axis="y", labelcolor="blue")
    ax1.tick_params(axis="x", rotation=30)

    ax2 = ax1.twinx()
    ax2.plot(categories, cumulative, color="red", marker="o", linewidth=2)
    ax2.set_ylabel("Накопленный процент", color="red")
    ax2.tick_params(axis="y", labelcolor="red")
    ax2.set_ylim(0, 110)

    plt.title("Диаграмма Парето (правило 80/20)")
    plt.grid(axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    img_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return {"image_base64": img_base64}


