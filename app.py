import streamlit as st
import psycopg2
import pandas as pd

# --- НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="АСУ Автосервис", page_icon="🛠️", layout="wide")

# ВАЖНО: Вставь сюда свою рабочую ссылку от Neon (с паролем)!
CONNECTION_STRING = "postgresql://neondb_owner:npg_tnhKFv8Vld3A@ep-plain-bonus-al1s3ur3-pooler.c-3.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# --- ПОДКЛЮЧЕНИЕ К БД ---
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

# ==========================================
# ЭКРАН АВТОРИЗАЦИИ (Если не выполнен вход)
# ==========================================
if not st.session_state.logged_in:
    # Центрируем форму авторизации
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.title("🔐 Вход в систему")
        st.markdown("Пожалуйста, авторизуйтесь для доступа к АСУ «Автосервис».")
        
        with st.form("login_form"):
            username_input = st.text_input("Логин (admin или manager)")
            password_input = st.text_input("Пароль (совпадает с логином)", type="password")
            submit_button = st.form_submit_button("Войти", type="primary", use_container_width=True)
            
            if submit_button:
                # Хардкодим пароли для простоты демонстрации на защите
                if username_input == "admin" and password_input == "admin":
                    st.session_state.logged_in = True
                    st.session_state.role = "Администратор"
                    st.session_state.username = "Директор (Вакина А.С.)"
                    st.rerun() # Перезагружаем страницу
                elif username_input == "manager" and password_input == "manager":
                    st.session_state.logged_in = True
                    st.session_state.role = "Менеджер"
                    st.session_state.username = "Мастер-приемщик (Петров П.П.)"
                    st.rerun()
                else:
                    st.error("❌ Неверный логин или пароль!")
    st.stop() # Останавливаем выполнение остального кода, пока не войдут

# ==========================================
# ГЛАВНОЕ МЕНЮ (Если вход выполнен)
# ==========================================
st.sidebar.title("🛠️ АСУ Автосервис")
st.sidebar.info(f"👤 **{st.session_state.username}**\n\n🔒 Роль: {st.session_state.role}")

if st.sidebar.button("🚪 Выйти из системы", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.role = None
    st.rerun()

st.sidebar.divider()

# Было: "👥 Сотрудники" -> Стало: "👥 Мастера"
menu_options = ["📊 Рабочий стол", "📄 Документы (Заказы)", "🗂️ Справочники (Клиенты)", "📦 Склад", "👥 Мастера"]

# Администратор видит всё, добавляем ему Журнал аудита
if st.session_state.role == "Администратор":
    menu_options.append("🛡️ Журнал аудита")

st.sidebar.subheader("Навигация")
# Вот эта команда должна быть в коде СТРОГО ОДИН РАЗ:
selected_module = st.sidebar.radio("Перейти в раздел:", menu_options)


# ==========================================
# 1. РАБОЧИЙ СТОЛ (Отчеты)
# ==========================================
if selected_module == "📊 Рабочий стол":
    st.title("📊 Аналитический отчет")
    try:
        query_revenue = """
        SELECT e.full_name AS "Сотрудник", COUNT(o.order_id) AS "Количество заказов", SUM(o.total_amount) AS "Выручка (руб.)"
        FROM Orders o JOIN Employees e ON o.employee_id = e.employee_id
        WHERE o.status = 'Закрыт' GROUP BY e.full_name ORDER BY SUM(o.total_amount) DESC;
        """
        df_revenue = pd.read_sql(query_revenue, conn)
        if df_revenue.empty:
            st.info("В этом месяце пока нет оплаченных заказов.")
        else:
            st.dataframe(df_revenue, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Ошибка БД: {e}")

# ==========================================
# 2. ДОКУМЕНТЫ (Формы, Заказы, Триггеры)
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
                st.success("Заказ закрыт!")
        
        with colB: 
                # ПУНКТ 3.7: Скрываем кнопку удаления для Менеджера!
                if st.session_state.role == "Администратор":
                    del_id = st.number_input("№ заказа для УДАЛЕНИЯ", min_value=1, step=1)
                    if st.button("❌ Удалить заказ (Только Администратор)"):
                        try:
                            cur = conn.cursor()
                            # ПЕРЕДАЕМ РОЛЬ В БАЗУ ДАННЫХ
                            cur.execute(f"SET my.app_role = '{st.session_state.role}';")
                            
                            # ТЕПЕРЬ УДАЛЯЕМ
                            cur.execute("DELETE FROM Orders WHERE order_id = %s", (del_id,))
                            st.warning("Заказ удален. Запись отправлена в Журнал Аудита.")
                            st.cache_data.clear()
                        except Exception as e:
                            st.error(f"Ошибка удаления: {e}")
                else:
                    st.info("🚫 У вашей роли (Менеджер) нет прав на удаление заказ-нарядов.")
    with tab2: 
        st.subheader("Форма регистрации нового ремонта")
        with st.form("new_order"):
            car_id = st.number_input("ID Автомобиля клиента", min_value=1, step=1)
            emp_id = st.number_input("ID Мастера", min_value=1, step=1)
            if st.form_submit_button("Создать заказ-наряд"):
                conn.cursor().execute("INSERT INTO Orders (car_id, employee_id) VALUES (%s, %s)", (car_id, emp_id))
                st.success("Заказ-наряд успешно открыт!")

    with tab3: 
        st.subheader("Списание запчастей со склада в заказ")
        with st.form("add_part"):
            ord_id = st.number_input("№ Заказ-наряда", min_value=1, step=1)
            part_id = st.number_input("ID Запчасти", min_value=1, step=1)
            qty = st.number_input("Количество (введите больше остатка для ошибки)", min_value=1, step=1)
            price = st.number_input("Цена продажи (руб)", min_value=100, step=100)
            
            if st.form_submit_button("Добавить в смету"):
                try:
                    conn.cursor().execute("INSERT INTO Order_Parts (order_id, part_id, quantity, current_price) VALUES (%s, %s, %s, %s)", (ord_id, part_id, qty, price))
                    st.success("Деталь добавлена. Сумма заказа автоматически пересчитана (Триггер 2).")
                except Exception as e:
                    st.error(f"Сработал Триггер БД: {e}")

    with tab4: 
        st.subheader("Печатная форма «Смета заказ-наряда»")
        print_id = st.number_input("№ заказа для вывода на печать", min_value=1, step=1)
        if st.button("Сформировать документ"):
            query_print = f"SELECT p.article AS \"Артикул\", p.name AS \"Наименование\", op.quantity AS \"Кол-во\", op.current_price AS \"Цена\", (op.quantity * op.current_price) AS \"Сумма\" FROM Order_Parts op JOIN Parts p ON op.part_id = p.part_id WHERE op.order_id = {print_id};"
            try:
                st.dataframe(pd.read_sql(query_print, conn), use_container_width=True, hide_index=True)
            except:
                st.warning("Смета пуста.")

# ==========================================
# 3. СПРАВОЧНИКИ (Клиенты и Авто)
# ==========================================
elif selected_module == "🗂️ Справочники (Клиенты)":
    st.title("🗂️ База клиентов и автомобилей")
    st.markdown("Реализация пункта 3.4 (Вставка в несколько таблиц) и 3.3 (Представления).")
    
    # 1. СНАЧАЛА ФОРМА ВВОДА (чтобы данные сразу улетали в БД до отрисовки таблицы)
    with st.form("add_client_car", clear_on_submit=True): # clear_on_submit сам очистит поля после успеха!
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Данные владельца**")
            fio = st.text_input("ФИО Клиента *")
            phone = st.text_input("Телефон *")
            
        with col2:
            st.markdown("**Данные автомобиля**")
            vin = st.text_input("VIN код (17 символов) *", max_chars=17)
            plate = st.text_input("Гос. номер *")
            
            # Делаем два поля в одну строку для красоты
            colA, colB = st.columns(2)
            with colA:
                brand_input = st.text_input("Марка (напр., BMW) *")
            with colB:
                model_input = st.text_input("Модель (напр., X5) *")
            
        if st.form_submit_button("Зарегистрировать клиента и авто", type="primary"):
            if fio and phone and vin and plate and brand_input and model_input:
                try:
                    cur = conn.cursor()
                    
                    # ШАГ 1: Ищем марку в справочнике или создаем новую на лету!
                    cur.execute("SELECT brand_id FROM Brand_Model WHERE brand_name = %s AND model_name = %s", (brand_input, model_input))
                    existing_brand = cur.fetchone()
                    
                    if existing_brand:
                        brand_id = existing_brand[0]
                    else:
                        cur.execute("INSERT INTO Brand_Model (brand_name, model_name) VALUES (%s, %s) RETURNING brand_id", (brand_input, model_input))
                        brand_id = cur.fetchone()[0]
                        
                    # ШАГ 2: Добавляем клиента и авто единым сложным SQL-запросом
                    complex_query = """
                    WITH new_client AS (
                        INSERT INTO Clients (full_name, phone) VALUES (%s, %s) RETURNING client_id
                    )
                    INSERT INTO Cars (vin_number, license_plate, brand_id, client_id)
                    SELECT %s, %s, %s, client_id FROM new_client;
                    """
                    cur.execute(complex_query, (fio, phone, vin, plate, brand_id))
                    
                    st.success(f"Успех! Клиент {fio} и автомобиль {brand_input} добавлены в базу.")
                    st.cache_data.clear() # Сбрасываем кэш, чтобы таблица внизу обновилась!
                except Exception as e:
                    st.error(f"Ошибка БД (возможно такой телефон или VIN уже есть): {e}")
            else:
                st.warning("Пожалуйста, заполните все обязательные поля!")

    st.markdown("---")
    
    # 2. ЗАТЕМ ОТРИСОВКА ТАБЛИЦЫ (она подтянет свежие данные, которые мы только что ввели)
    st.subheader("📋 Картотека")
    if st.button("🔄 Принудительно обновить таблицу"): st.cache_data.clear()
    
    try:
        query_view = """
        SELECT 
            car_id AS "ID Авто",
            full_name AS "ФИО Клиента", 
            phone AS "Телефон", 
            license_plate AS "Гос. номер", 
            vin_number AS "VIN код", -- Вернули вывод VIN-кода!
            brand_name || ' ' || model_name AS "Марка и Модель"
        FROM view_client_cars;
        """
        df_clients = pd.read_sql(query_view, conn)
        st.dataframe(df_clients, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Ошибка вывода: {e}")

# ==========================================
# 4. СКЛАД
# ==========================================
elif selected_module == "📦 Склад":
    st.title("📦 Склад автозапчастей")
    
    # Форма для добавления нового товара или пополнения
    with st.expander("➕ Приемка товара на склад (Новый или Пополнение)"):
        with st.form("add_new_part", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                new_article = st.text_input("Артикул (например, BRK-001) *")
                new_name = st.text_input("Наименование детали *")
            with col2:
                new_price = st.number_input("Розничная цена (руб) *", min_value=0.0, step=50.0)
                new_stock = st.number_input("Пришло на склад (шт) *", min_value=1, step=1)
                
            if st.form_submit_button("Добавить / Пополнить", type="primary"):
                if new_article and new_name:
                    try:
                        cur = conn.cursor()
                        # Продвинутый SQL: UPSERT (ON CONFLICT). Если артикул есть - плюсуем остаток!
                        upsert_query = """
                        INSERT INTO Parts (article, name, price, stock) 
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (article) 
                        DO UPDATE SET 
                            stock = Parts.stock + EXCLUDED.stock,
                            price = EXCLUDED.price;
                        """
                        cur.execute(upsert_query, (new_article, new_name, new_price, new_stock))
                        st.success(f"Запасы по артикулу «{new_article}» успешно пополнены на {new_stock} шт!")
                        st.cache_data.clear() # Сбрасываем кэш
                    except Exception as e:
                        st.error(f"Ошибка БД: {e}")
                        st.cache_resource.clear() # Лечим разрыв соединения
                else:
                    st.warning("Заполните Артикул и Наименование!")

    st.markdown("---")
    st.subheader("Текущие остатки")
    if st.button("🔄 Обновить склад"): st.cache_data.clear()

    try:
        df_parts = pd.read_sql("SELECT part_id AS \"ID\", article AS \"Артикул\", name AS \"Наименование\", price AS \"Цена\", stock AS \"Остаток\" FROM Parts ORDER BY part_id;", conn)
        st.dataframe(df_parts, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error("Соединение с БД было разорвано. Пожалуйста, обновите страницу (F5).")
        st.cache_resource.clear()
# ==========================================
# 5. АУДИТ БЕЗОПАСНОСТИ (Только для Админа)
# ==========================================
elif selected_module == "🛡️ Журнал аудита":
    st.title("🛡️ Журнал безопасности (Аудит)")
    st.markdown("Действие **Триггера 3** по отслеживанию удаленных заказов.")
    try:
        df_audit = pd.read_sql("SELECT log_id AS \"ID\", action_date::timestamp(0) AS \"Дата\", db_user AS \"Пользователь\", action_type AS \"Действие\", table_name AS \"Таблица\", record_info AS \"Информация\" FROM audit_log ORDER BY action_date DESC;", conn)
        st.dataframe(df_audit, use_container_width=True, hide_index=True)
    except:
        st.info("Таблица логов пуста.")
# ==========================================
# 6. МАСТЕРА (Вместо Сотрудников)
# ==========================================
elif selected_module == "👥 Мастера":
    st.title("👥 Мастерской состав") 
    st.markdown("Управление списком квалифицированных мастеров и их окладами.")

    # Форма добавления (теперь везде написано "Мастер")
    with st.expander("➕ Принять на работу нового мастера"):
        cur = conn.cursor()
        cur.execute("SELECT position_id, title FROM Positions;")
        positions = cur.fetchall()

        if not positions:
            st.warning("⚠️ Сначала добавьте специализации (должности).")
            with st.form("add_pos"):
                pos_title = st.text_input("Название (например: Автомеханик)")
                pos_salary = st.number_input("Оклад (руб)", min_value=15000.0, step=5000.0)
                if st.form_submit_button("Добавить должность"):
                    cur.execute("INSERT INTO Positions (title, base_salary) VALUES (%s, %s)", (pos_title, pos_salary))
                    st.success("Должность добавлена! Нажмите F5.")
        else:
            pos_dict = {title: pid for pid, title in positions}
            with st.form("add_employee", clear_on_submit=True):
                # МЕНЯЕМ ТЕКСТЫ ТУТ:
                emp_name = st.text_input("ФИО Мастера *")
                emp_phone = st.text_input("Контактный телефон *")
                emp_pos = st.selectbox("Специализация *", options=list(pos_dict.keys()))

                if st.form_submit_button("Добавить мастера в штат", type="primary"):
                    if emp_name and emp_phone:
                        try:
                            cur.execute("INSERT INTO Employees (full_name, phone, position_id) VALUES (%s, %s, %s)",
                                        (emp_name, emp_phone, pos_dict[emp_pos]))
                            st.success(f"Успех! Мастер {emp_name} добавлен.")
                            st.cache_data.clear()
                        except Exception as e:
                            st.error(f"Ошибка БД: {e}")
                    else:
                        st.warning("Заполните поля!")

    st.markdown("---")
    
    # И ТУТ ТОЖЕ МЕНЯЕМ ЗАГОЛОВОК ТАБЛИЦЫ:
    st.subheader("📋 Список действующих мастеров")
    if st.button("🔄 Обновить список"): st.cache_data.clear()

    query_emp = """
    SELECT e.employee_id AS "ID", e.full_name AS "ФИО", e.phone AS "Телефон",
           p.title AS "Специализация", p.base_salary AS "Оклад (руб)"
    FROM Employees e JOIN Positions p ON e.position_id = p.position_id
    ORDER BY e.employee_id;
    """
    try:
        df_emp = pd.read_sql(query_emp, conn)
        st.dataframe(df_emp, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Ошибка: {e}")
