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
                    st.session_state.username = "Директор (Иванов Д.А.)"
                    st.rerun()
                elif username_input == "manager" and password_input == "manager":
                    st.session_state.logged_in = True
                    st.session_state.role = "Менеджер"
                    st.session_state.username = "Мастер-приемщик (Иванов Иван)"
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
menu_options = ["📊 Рабочий стол", "📄 Документы (Заказы)", "🗂️ Справочники", "📦 Склад", "👥 Мастера"]

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
    
    # ДОБАВИЛИ НОВУЮ ВКЛАДКУ ДЛЯ УСЛУГ
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 Журнал", "➕ Открыть", "🛠️ Услуги", "🔧 Запчасти", "🖨️ Печать Акта"])
    
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
            if st.session_state.role == "Администратор":
                del_id = st.number_input("№ заказа для УДАЛЕНИЯ", min_value=1, step=1)
                if st.button("❌ Удалить заказ"):
                    try:
                        cur = conn.cursor()
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

    # НОВЫЙ БЛОК: ДОБАВЛЕНИЕ УСЛУГ В ЗАКАЗ
    with tab3:
        st.subheader("Внесение выполненных работ (Услуг)")
        with st.form("add_service"):
            ord_id_svc = st.number_input("№ Заказ-наряда", min_value=1, step=1, key="svc_ord")
            svc_id = st.number_input("ID Услуги (из прайс-листа)", min_value=1, step=1)
            qty_svc = st.number_input("Количество (нормо-часов)", min_value=1.0, step=0.5)
            
            if st.form_submit_button("Добавить работу"):
                try:
                    conn.cursor().execute("INSERT INTO Order_Services (order_id, service_id, quantity) VALUES (%s, %s, %s)", (ord_id_svc, svc_id, qty_svc))
                    st.success("Работа добавлена! Сумма документа пересчитана (сработал Триггер 2).")
                except Exception as e:
                    st.error(f"Ошибка БД: {e}")

    with tab4: 
        st.subheader("Списание ТМЦ со склада (Запчасти)")
        with st.form("add_part"):
            ord_id_part = st.number_input("№ Заказ-наряда", min_value=1, step=1, key="part_ord")
            part_id = st.number_input("ID Запчасти", min_value=1, step=1)
            qty_part = st.number_input("Количество единиц", min_value=1, step=1)
            price_part = st.number_input("Отпускная цена (руб)", min_value=100, step=100)
            
            if st.form_submit_button("Добавить запчасть"):
                try:
                    conn.cursor().execute("INSERT INTO Order_Parts (order_id, part_id, quantity, current_price) VALUES (%s, %s, %s, %s)", (ord_id_part, part_id, qty_part, price_part))
                    st.success("Позиция добавлена в смету.")
                except Exception as e:
                    st.error(f"Отказ операции (Сработал триггер склада): {e}")

    # ОБНОВЛЕННЫЙ БЛОК: ПЕЧАТЬ АКТА (показывает и услуги, и запчасти)
    with tab5: 
        st.subheader("Формирование печатной формы «Смета»")
        print_id = st.number_input("Укажите № заказа", min_value=1, step=1, key="print_ord")
        if st.button("Сформировать документ"):
            
            st.markdown("**🛠 Выполненные работы (Услуги):**")
            query_print_svc = f"SELECT s.name AS \"Наименование\", os.quantity AS \"Нормо-часы\", s.price AS \"Цена н/ч\", (os.quantity * s.price) AS \"Сумма\" FROM Order_Services os JOIN Services s ON os.service_id = s.service_id WHERE os.order_id = {print_id};"
            try:
                df_s = pd.read_sql(query_print_svc, conn)
                if not df_s.empty: st.dataframe(df_s, use_container_width=True, hide_index=True)
                else: st.info("Работы в заказ не добавлены.")
            except: pass

            st.markdown("**⚙️ Расходные материалы (Запчасти):**")
            query_print_parts = f"SELECT p.article AS \"Артикул\", p.name AS \"Наименование\", op.quantity AS \"Кол-во\", op.current_price AS \"Цена\", (op.quantity * op.current_price) AS \"Сумма\" FROM Order_Parts op JOIN Parts p ON op.part_id = p.part_id WHERE op.order_id = {print_id};"
            try:
                df_p = pd.read_sql(query_print_parts, conn)
                if not df_p.empty: st.dataframe(df_p, use_container_width=True, hide_index=True)
                else: st.info("Запчасти в заказ не добавлены.")
            except: pass
# ==========================================
# 3. СПРАВОЧНИКИ (База клиентов и Прайс-лист)
# ==========================================
elif selected_module == "🗂️ Справочники":
    st.title("🗂️ Управление справочниками")
    
    # Создаем две вкладки
    tab_clients, tab_services = st.tabs(["👥 Клиенты и Автомобили", "💰 Прайс-лист (Услуги)"])
    
    # ---------------- Вкладка 1: Клиенты ----------------
    with tab_clients:
        st.markdown("Регистрация новых клиентов и транспортных средств.")
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
                with colA: brand_input = st.text_input("Марка *")
                with colB: model_input = st.text_input("Модель *")
                
            if st.form_submit_button("Внести в базу", type="primary"):
                if fio and phone and vin and plate and brand_input and model_input:
                    try:
                        cur = conn.cursor()
                        cur.execute("SELECT brand_id FROM Brand_Model WHERE brand_name = %s AND model_name = %s", (brand_input, model_input))
                        existing_brand = cur.fetchone()
                        
                        if existing_brand: brand_id = existing_brand[0]
                        else:
                            cur.execute("INSERT INTO Brand_Model (brand_name, model_name) VALUES (%s, %s) RETURNING brand_id", (brand_input, model_input))
                            brand_id = cur.fetchone()[0]
                            
                        complex_query = """
                        WITH new_client AS (INSERT INTO Clients (full_name, phone) VALUES (%s, %s) RETURNING client_id)
                        INSERT INTO Cars (vin_number, license_plate, brand_id, client_id) SELECT %s, %s, %s, client_id FROM new_client;
                        """
                        cur.execute(complex_query, (fio, phone, vin, plate, brand_id))
                        st.success("Записи успешно добавлены в структуру БД.")
                        st.cache_data.clear() 
                    except Exception as e:
                        st.error(f"Нарушение уникальности (Такой VIN или телефон уже есть): {e}")
                else:
                    st.warning("Необходимо заполнить все обязательные атрибуты.")

        st.markdown("---")
        st.subheader("📋 Реестр транспортных средств")
        if st.button("🔄 Обновить реестр"): st.cache_data.clear()
        try:
            query_view = "SELECT car_id AS \"ID Авто\", full_name AS \"ФИО Клиента\", phone AS \"Телефон\", license_plate AS \"Гос. номер\", vin_number AS \"VIN код\", brand_name || ' ' || model_name AS \"Марка и Модель\" FROM view_client_cars;"
            st.dataframe(pd.read_sql(query_view, conn), use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Ошибка формирования реестра: {e}")

    # ---------------- Вкладка 2: Прайс-лист ----------------
    with tab_services:
        st.markdown("Управление перечнем выполняемых работ и стоимостью нормо-часов.")
        with st.form("add_service", clear_on_submit=True):
            svc_name = st.text_input("Наименование работы (Услуги) *")
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                svc_price = st.number_input("Стоимость 1 нормо-часа (руб) *", min_value=100.0, step=100.0, value=1500.0)
            with col_s2:
                svc_hours = st.number_input("Норма времени (в часах) *", min_value=0.1, step=0.1, value=1.0)
                
            if st.form_submit_button("Добавить в прайс-лист", type="primary"):
                if svc_name:
                    try:
                        conn.cursor().execute("INSERT INTO Services (name, price, norm_hours) VALUES (%s, %s, %s)", (svc_name, svc_price, svc_hours))
                        st.success(f"Услуга «{svc_name}» успешно добавлена в прайс-лист.")
                        st.cache_data.clear()
                    except Exception as e:
                        st.error(f"Ошибка БД: {e}")
                else:
                    st.warning("Укажите наименование выполняемой работы.")
                    
        st.markdown("---")
        st.subheader("📋 Действующий прайс-лист")
        if st.button("🔄 Обновить прайс"): st.cache_data.clear()
        try:
            df_svc = pd.read_sql("SELECT service_id AS \"ID\", name AS \"Наименование работы\", price AS \"Цена за н/ч (руб)\", norm_hours AS \"Норма времени (ч)\" FROM Services ORDER BY service_id;", conn)
            st.dataframe(df_svc, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Ошибка: {e}")

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
# ==========================================
# КАСТОМНЫЙ ДИЗАЙН (ФОН И ЦВЕТ ТЕКСТА)
# ==========================================
page_bg_img = """
<style>
/* Основной фон страницы */
[data-testid="stAppViewContainer"] {
    background-image: url("https://i.pinimg.com/originals/47/18/51/471851ab77a4b69cee7ccd67c6407afd.jpg?nii=t");
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
}

/* Полупрозрачный темный фон для бокового меню */
[data-testid="stSidebar"] {
    background-color: rgba(15, 17, 22, 0.9); 
}

/* МАГИЯ ЗДЕСЬ: Принудительно делаем весь текст в боковом меню белым */
[data-testid="stSidebar"] * {
    color: white !important;
}

/* Делаем верхнюю полоску (header) прозрачной */
[data-testid="stHeader"] {
    background-color: rgba(0, 0, 0, 0);
}
</style>
"""
st.markdown(page_bg_img, unsafe_allow_html=True)
