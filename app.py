import streamlit as st
import psycopg2
import pandas as pd

# ==========================================
# НАСТРОЙКИ СТРАНИЦЫ И ПОДКЛЮЧЕНИЕ К БД
# ==========================================
st.set_page_config(page_title="АСУ Автосервис", page_icon="🛠️", layout="wide")

# Строка подключения к облачной БД PostgreSQL (Neon)
CONNECTION_STRING = "postgresql://neondb_owner:npg_tnhKFv8Vld3A@ep-plain-bonus-al1s3ur3-pooler.c-3.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

@st.cache_resource(ttl=600)
def init_connection():
    conn = psycopg2.connect(CONNECTION_STRING)
    conn.autocommit = True 
    return conn

try:
    conn = init_connection()
    if conn.closed != 0:
        st.cache_resource.clear()
        conn = init_connection()
except Exception as e:
    st.error(f"Ошибка подключения к БД: {e}")
    st.stop()

# ==========================================
# ИНИЦИАЛИЗАЦИЯ СЕССИИ (АВТОРИЗАЦИЯ)
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'role' not in st.session_state:
    st.session_state.role = None
if 'username' not in st.session_state:
    st.session_state.username = None

# Экран аутентификации пользователей
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.title("🔐 Вход в систему")
        st.markdown("Пожалуйста, авторизуйтесь для доступа к АСУ «Автосервис».")
        
        with st.form("login_form"):
            username_input = st.text_input("Логин")
            password_input = st.text_input("Пароль", type="password")
            submit_button = st.form_submit_button("Войти", type="primary", use_container_width=True)
            
            if submit_button:
                # Проверка учетных данных и присвоение ролей (RBAC)
                if username_input == "admin" and password_input == "admin":
                    st.session_state.logged_in = True
                    st.session_state.role = "Администратор"
                    st.session_state.username = "Директор (Вакина А.С.)"
                    st.rerun()
                elif username_input == "manager" and password_input == "manager":
                    st.session_state.logged_in = True
                    st.session_state.role = "Менеджер"
                    st.session_state.username = "Мастер-приемщик (Петров П.П.)"
                    st.rerun()
                else:
                    st.error("❌ Неверный логин или пароль!")
    st.stop()

# ==========================================
# ГЛАВНОЕ МЕНЮ И НАВИГАЦИЯ
# ==========================================
st.sidebar.title("🛠️ АСУ Автосервис")
st.sidebar.info(f"👤 **{st.session_state.username}**\n\n🔒 Роль: {st.session_state.role}")

if st.sidebar.button("🚪 Выйти из системы", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.role = None
    st.rerun()

st.sidebar.divider()

# Формирование пунктов меню на основе роли пользователя
menu_options = ["📊 Рабочий стол", "📄 Документы (Заказы)", "🗂️ Справочники (Клиенты)", "📦 Склад", "👥 Мастера"]

if st.session_state.role == "Администратор":
    menu_options.append("🛡️ Журнал аудита")

st.sidebar.subheader("Навигация")
selected_module = st.sidebar.radio("Перейти в раздел:", menu_options)


# ==========================================
# 1. РАБОЧИЙ СТОЛ (Аналитика)
# ==========================================
if selected_module == "📊 Рабочий стол":
    st.title("📊 Аналитический отчет")
    try:
        # Агрегирующий запрос: расчет выручки с группировкой по мастерам
        query_revenue = """
        SELECT e.full_name AS "Сотрудник", COUNT(o.order_id) AS "Количество заказов", SUM(o.total_amount) AS "Выручка (руб.)"
        FROM Orders o JOIN Employees e ON o.employee_id = e.employee_id
        WHERE o.status = 'Закрыт' GROUP BY e.full_name ORDER BY SUM(o.total_amount) DESC;
        """
        df_revenue = pd.read_sql(query_revenue, conn)
        if df_revenue.empty:
            st.info("В текущем периоде нет закрытых (оплаченных) заказов.")
        else:
            st.dataframe(df_revenue, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Ошибка выполнения запроса: {e}")

# ==========================================
# 2. ДОКУМЕНТЫ (Управление заказ-нарядами)
# ==========================================
elif selected_module == "📄 Документы (Заказы)":
    st.title("📄 Управление заказ-нарядами")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Журнал", "➕ Открыть заказ", "🔧 Добавить запчасть", "🖨️ Печать Акта"])
    
    with tab1:
        if st.button("🔄 Обновить данные"): st.cache_data.clear()
        df_orders = pd.read_sql("SELECT order_id AS \"№ Заказа\", created_at::date AS \"Дата\", status AS \"Статус\", total_amount AS \"Итого (руб.)\" FROM Orders ORDER BY order_id DESC;", conn)
        st.dataframe(df_orders, use_container_width=True, hide_index=True)

        st.markdown("---")
        colA, colB = st.columns(2)
        with colA:
            close_id = st.number_input("№ заказа для ЗАКРЫТИЯ (оплата)", min_value=1, step=1)
            if st.button("✅ Закрыть заказ (Оплатить)"):
                conn.cursor().execute("UPDATE Orders SET status = 'Закрыт', closed_at = CURRENT_TIMESTAMP WHERE order_id = %s", (close_id,))
                st.success("Статус заказа успешно обновлен.")
        
        with colB: 
            # Проверка прав доступа перед операцией удаления (RBAC)
            if st.session_state.role == "Администратор":
                del_id = st.number_input("№ заказа для УДАЛЕНИЯ", min_value=1, step=1)
                if st.button("❌ Удалить заказ"):
                    try:
                        cur = conn.cursor()
                        # Передача текущей роли пользователя в конфигурацию сессии БД для триггера аудита
                        cur.execute(f"SET my.app_role = '{st.session_state.role}';")
                        cur.execute("DELETE FROM Orders WHERE order_id = %s", (del_id,))
                        st.warning("Заказ удален. Запись о действии занесена в журнал аудита.")
                        st.cache_data.clear()
                    except Exception as e:
                        st.error(f"Ошибка при удалении записи: {e}")
            else:
                st.info("🚫 Недостаточно прав для выполнения операции удаления заказ-нарядов.")
                
    with tab2: 
        st.subheader("Регистрация нового документа")
        with st.form("new_order"):
            car_id = st.number_input("ID Автомобиля", min_value=1, step=1)
            emp_id = st.number_input("ID Мастера-приемщика", min_value=1, step=1)
            if st.form_submit_button("Создать заказ-наряд"):
                conn.cursor().execute("INSERT INTO Orders (car_id, employee_id) VALUES (%s, %s)", (car_id, emp_id))
                st.success("Заказ-наряд успешно открыт.")

    with tab3: 
        st.subheader("Списание ТМЦ со склада")
        with st.form("add_part"):
            ord_id = st.number_input("№ Заказ-наряда", min_value=1, step=1)
            part_id = st.number_input("ID Запчасти", min_value=1, step=1)
            qty = st.number_input("Количество единиц", min_value=1, step=1)
            price = st.number_input("Отпускная цена (руб)", min_value=100, step=100)
            
            if st.form_submit_button("Добавить в смету"):
                try:
                    conn.cursor().execute("INSERT INTO Order_Parts (order_id, part_id, quantity, current_price) VALUES (%s, %s, %s, %s)", (ord_id, part_id, qty, price))
                    st.success("Позиция добавлена в смету. Сумма документа пересчитана автоматически.")
                except Exception as e:
                    st.error(f"Отказ операции (Сработал триггер БД): {e}")

    with tab4: 
        st.subheader("Формирование печатной формы «Смета»")
        print_id = st.number_input("Укажите № заказа", min_value=1, step=1)
        if st.button("Сформировать документ"):
            query_print = f"SELECT p.article AS \"Артикул\", p.name AS \"Наименование\", op.quantity AS \"Кол-во\", op.current_price AS \"Цена\", (op.quantity * op.current_price) AS \"Сумма\" FROM Order_Parts op JOIN Parts p ON op.part_id = p.part_id WHERE op.order_id = {print_id};"
            try:
                st.dataframe(pd.read_sql(query_print, conn), use_container_width=True, hide_index=True)
            except:
                st.warning("Смета не содержит позиций.")

# ==========================================
# 3. СПРАВОЧНИКИ (База клиентов)
# ==========================================
elif selected_module == "🗂️ Справочники (Клиенты)":
    st.title("🗂️ Картотека клиентов и автомобилей")
    st.markdown("Модуль ввода данных и просмотра результатов представления `view_client_cars`.")
    
    # Блок регистрации (CRUD - Create)
    with st.form("add_client_car", clear_on_submit=True): 
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Персональные данные**")
            fio = st.text_input("ФИО Клиента *")
            phone = st.text_input("Контактный телефон *")
            
        with col2:
            st.markdown("**Технические параметры ТС**")
            vin = st.text_input("VIN-код (17 символов) *", max_chars=17)
            plate = st.text_input("Регистрационный знак *")
            
            colA, colB = st.columns(2)
            with colA:
                brand_input = st.text_input("Марка *")
            with colB:
                model_input = st.text_input("Модель *")
            
        if st.form_submit_button("Внести в базу", type="primary"):
            if fio and phone and vin and plate and brand_input and model_input:
                try:
                    cur = conn.cursor()
                    
                    # Проверка наличия марки в справочнике Brand_Model
                    cur.execute("SELECT brand_id FROM Brand_Model WHERE brand_name = %s AND model_name = %s", (brand_input, model_input))
                    existing_brand = cur.fetchone()
                    
                    if existing_brand:
                        brand_id = existing_brand[0]
                    else:
                        cur.execute("INSERT INTO Brand_Model (brand_name, model_name) VALUES (%s, %s) RETURNING brand_id", (brand_input, model_input))
                        brand_id = cur.fetchone()[0]
                        
                    # Транзакционное добавление записей в связанные таблицы
                    complex_query = """
                    WITH new_client AS (
                        INSERT INTO Clients (full_name, phone) VALUES (%s, %s) RETURNING client_id
                    )
                    INSERT INTO Cars (vin_number, license_plate, brand_id, client_id)
                    SELECT %s, %s, %s, client_id FROM new_client;
                    """
                    cur.execute(complex_query, (fio, phone, vin, plate, brand_id))
                    
                    st.success(f"Записи успешно добавлены в структуру БД.")
                    st.cache_data.clear() 
                except Exception as e:
                    st.error(f"Нарушение уникальности или иная ошибка БД: {e}")
            else:
                st.warning("Необходимо заполнить все обязательные атрибуты.")

    st.markdown("---")
    
    # Блок просмотра (CRUD - Read)
    st.subheader("📋 Реестр транспортных средств")
    if st.button("🔄 Обновить реестр"): st.cache_data.clear()
    
    try:
        # Вывод данных из заранее подготовленного SQL View
        query_view = """
        SELECT 
            car_id AS "ID Авто",
            full_name AS "ФИО Клиента", 
            phone AS "Телефон", 
            license_plate AS "Гос. номер", 
            vin_number AS "VIN код", 
            brand_name || ' ' || model_name AS "Марка и Модель"
        FROM view_client_cars;
        """
        df_clients = pd.read_sql(query_view, conn)
        st.dataframe(df_clients, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Ошибка формирования реестра: {e}")

# ==========================================
# 4. СКЛАДСКОЙ УЧЕТ
# ==========================================
elif selected_module == "📦 Склад":
    st.title("📦 Модуль складского учета")
    
    # Оформление приходных операций
    with st.expander("➕ Приходная операция (Новая номенклатура / Пополнение)"):
        with st.form("add_new_part", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                new_article = st.text_input("Артикул *")
                new_name = st.text_input("Наименование ТМЦ *")
            with col2:
                new_price = st.number_input("Розничная цена (руб) *", min_value=0.0, step=50.0)
                new_stock = st.number_input("Количество (шт) *", min_value=1, step=1)
                
            if st.form_submit_button("Оформить приход", type="primary"):
                if new_article and new_name:
                    try:
                        cur = conn.cursor()
                        # Использование механизма UPSERT для обновления остатков существующей номенклатуры
                        upsert_query = """
                        INSERT INTO Parts (article, name, price, stock) 
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (article) 
                        DO UPDATE SET 
                            stock = Parts.stock + EXCLUDED.stock,
                            price = EXCLUDED.price;
                        """
                        cur.execute(upsert_query, (new_article, new_name, new_price, new_stock))
                        st.success(f"Остатки по артикулу «{new_article}» актуализированы.")
                        st.cache_data.clear() 
                    except Exception as e:
                        st.error(f"Системная ошибка БД: {e}")
                        st.cache_resource.clear() 
                else:
                    st.warning("Требуется указать Артикул и Наименование.")

    st.markdown("---")
    st.subheader("Текущие складские остатки")
    if st.button("🔄 Обновить ведомость"): st.cache_data.clear()

    try:
        df_parts = pd.read_sql("SELECT part_id AS \"ID\", article AS \"Артикул\", name AS \"Наименование\", price AS \"Цена\", stock AS \"Остаток\" FROM Parts ORDER BY part_id;", conn)
        st.dataframe(df_parts, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error("Ошибка извлечения данных.")
        st.cache_resource.clear()

# ==========================================
# 5. АУДИТ БЕЗОПАСНОСТИ (Только для Админа)
# ==========================================
elif selected_module == "🛡️ Журнал аудита":
    st.title("🛡️ Журнал безопасности транзакций")
    st.markdown("Мониторинг критических DML-операций, зафиксированных серверными триггерами.")
    try:
        df_audit = pd.read_sql("SELECT log_id AS \"ID\", action_date::timestamp(0) AS \"Дата\", db_user AS \"Роль СУБД\", action_type AS \"Операция\", table_name AS \"Отношение\", record_info AS \"Детализация\" FROM audit_log ORDER BY action_date DESC;", conn)
        st.dataframe(df_audit, use_container_width=True, hide_index=True)
    except:
        st.info("В журнале аудита отсутствуют записи.")

# ==========================================
# 6. УПРАВЛЕНИЕ ПЕРСОНАЛОМ (Мастера)
# ==========================================
elif selected_module == "👥 Мастера":
    st.title("👥 Управление производственным персоналом") 
    st.markdown("Справочник сотрудников и штатное расписание СТО.")

    with st.expander("➕ Регистрация нового специалиста"):
        cur = conn.cursor()
        cur.execute("SELECT position_id, title FROM Positions;")
        positions = cur.fetchall()

        if not positions:
            st.warning("Внимание: требуется предварительное заполнение справочника должностей.")
            with st.form("add_pos"):
                pos_title = st.text_input("Наименование должности")
                pos_salary = st.number_input("Базовая ставка (руб)", min_value=15000.0, step=5000.0)
                if st.form_submit_button("Внести в штатное расписание"):
                    cur.execute("INSERT INTO Positions (title, base_salary) VALUES (%s, %s)", (pos_title, pos_salary))
                    st.success("Справочник должностей обновлен. Перезагрузите страницу.")
        else:
            pos_dict = {title: pid for pid, title in positions}
            with st.form("add_employee", clear_on_submit=True):
                emp_name = st.text_input("ФИО Специалиста *")
                emp_phone = st.text_input("Контактный телефон *")
                emp_pos = st.selectbox("Квалификация (Должность) *", options=list(pos_dict.keys()))

                if st.form_submit_button("Зарегистрировать сотрудника", type="primary"):
                    if emp_name and emp_phone:
                        try:
                            cur.execute("INSERT INTO Employees (full_name, phone, position_id) VALUES (%s, %s, %s)",
                                        (emp_name, emp_phone, pos_dict[emp_pos]))
                            st.success(f"Запись сотрудника '{emp_name}' успешно создана.")
                            st.cache_data.clear()
                        except Exception as e:
                            st.error(f"Ошибка записи: {e}")
                    else:
                        st.warning("Требуется заполнение обязательных реквизитов.")

    st.markdown("---")
    st.subheader("📋 Реестр персонала")
    if st.button("🔄 Обновить реестр"): st.cache_data.clear()

    # Запрос с объединением данных из связанных таблиц (Employees и Positions)
    query_emp = """
    SELECT e.employee_id AS "ID", e.full_name AS "ФИО", e.phone AS "Телефон",
           p.title AS "Квалификация", p.base_salary AS "Оклад (руб)"
    FROM Employees e JOIN Positions p ON e.position_id = p.position_id
    ORDER BY e.employee_id;
    """
    try:
        df_emp = pd.read_sql(query_emp, conn)
        st.dataframe(df_emp, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Сбой загрузки данных: {e}")
