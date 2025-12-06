from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
from mysql.connector import Error
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change for production

# Database Configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'peace',
    'database': 'inventory'
}

def get_connection():
    try:
        return mysql.connector.connect(**db_config)
    except Error as e:
        flash(f"Database connection error: {e}", 'danger')
        return None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'admin' and password == 'admin123':
            session['logged_in'] = True
            return redirect(url_for('inventory'))
        else:
            flash('Invalid credentials!', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
def home():
    return redirect(url_for('inventory'))

@app.route('/main_menu')
@login_required
def main_menu():
    return render_template('main_menu.html')

@app.route('/inventory_menu')
@login_required
def inventory_menu():
    return render_template('inventory_menu.html')

@app.route('/reports_menu')
@login_required
def reports_menu():
    return render_template('reports_menu.html')

@app.route('/view_stock', methods=['GET', 'POST'])
@login_required
def view_stock():
    if request.method == 'POST':
        product_name = request.form['product_name']
        conn = get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT GetStockLevelByName(%s)", (product_name,))
                stock_level = cursor.fetchone()[0]
                return render_template('view_stock.html', stock_level=stock_level, product_name=product_name)
            except Error as e:
                flash(f"Error searching stock: {e}", 'danger')
            finally:
                conn.close()
    return render_template('view_stock.html')

@app.route('/inventory')
@login_required
def inventory():
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM current_stock_view")
            stock = cursor.fetchall()
            return render_template('inventory.html', stock=stock)
        except Error as e:
            flash(f"Error fetching inventory: {e}", 'danger')
        finally:
            conn.close()
    return redirect(url_for('home'))

@app.route('/add_purchase', methods=['GET', 'POST'])
@login_required
def add_purchase():
    if request.method == 'POST':
        try:
            purchase_id = int(request.form['purchase_id'])
            product_id = int(request.form['product_id'])
            supplier_id = int(request.form['supplier_id'])
            quantity = int(request.form['quantity'])
            price = float(request.form['price'])
            date = request.form['date']

            product_name = request.form['product_name'].strip()
            category = request.form['category'].strip() or "Uncategorized"

            conn = get_connection()
            cursor = conn.cursor()

            # Check if product exists
            cursor.execute("SELECT * FROM products WHERE product_id = %s", (product_id,))
            product_exists = cursor.fetchone()

            if not product_exists:
                if not product_name:
                    flash("New product name is required when product ID does not exist.", "danger")
                    return redirect(url_for('add_purchase'))

                # Insert new product using form values
                cursor.execute("""
                    INSERT INTO products (product_id, name, category, quantity_in_stock, price_per_unit)
                    VALUES (%s, %s, %s, %s, %s)
                """, (product_id, product_name, category, 0, price))

            # Insert purchase
            cursor.execute("""
                INSERT INTO purchases (purchase_id, product_id, supplier_id, quantity, purchase_date, price_per_unit)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (purchase_id, product_id, supplier_id, quantity, date, price))

            # Update stock
            cursor.execute("""
                UPDATE products 
                SET quantity_in_stock = quantity_in_stock + %s 
                WHERE product_id = %s
            """, (quantity, product_id))

            conn.commit()
            flash('Purchase added successfully!', 'success')
        except Error as e:
            conn.rollback()
            flash(f'Error adding purchase: {e}', 'danger')
        finally:
            if conn:
                conn.close()
        return redirect(url_for('purchase_history'))
    return render_template('add_purchase.html')

@app.route('/purchase_history')
@login_required
def purchase_history():
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT pu.purchase_id, pr.name AS product_name, pu.quantity, 
                       pu.purchase_date, pu.price_per_unit, 
                       (pu.quantity * pu.price_per_unit) AS total_cost
                FROM purchases pu
                JOIN products pr ON pu.product_id = pr.product_id
                ORDER BY pu.purchase_date DESC
            """)
            purchases = cursor.fetchall()
            return render_template('purchase_history.html', purchases=purchases)
        except Error as e:
            flash(f"Error fetching purchase history: {e}", 'danger')
        finally:
            conn.close()
    return redirect(url_for('home'))

@app.route('/add_sale', methods=['GET', 'POST'])
@login_required
def add_sale():
    if request.method == 'POST':
        try:
            sale_id = int(request.form['sale_id'])
            product_id = int(request.form['product_id'])
            quantity = int(request.form['quantity'])
            price = float(request.form['price'])  # <-- Get price from form
            date = request.form['date']

            conn = get_connection()
            cursor = conn.cursor()

            # Check if product exists
            cursor.execute("SELECT * FROM products WHERE product_id = %s", (product_id,))
            product = cursor.fetchone()
            if not product:
                flash('Product ID not found!', 'danger')
                return redirect(url_for('add_sale'))

            cursor.execute(
                "INSERT INTO sales (sale_id, product_id, quantity_sold, sale_date, price_per_unit) "
                "VALUES (%s, %s, %s, %s, %s)",
                (sale_id, product_id, quantity, date, price)
            )

            conn.commit()
            flash('Sale added successfully!', 'success')
        except Error as e:
            conn.rollback()
            flash(f'Error adding sale: {e}', 'danger')
        finally:
            if conn:
                conn.close()
        return redirect(url_for('sales_history'))
    return render_template('add_sale.html')

@app.route('/sales_history')
@login_required
def sales_history():
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT s.sale_id, p.name AS product_name, s.quantity_sold, 
                       s.sale_date, s.price_per_unit, 
                       (s.quantity_sold * s.price_per_unit) AS total_sale
                FROM sales s
                JOIN products p ON s.product_id = p.product_id
                ORDER BY s.sale_date DESC
            """)
            sales = cursor.fetchall()
            return render_template('sales_history.html', sales=sales)
        except Error as e:
            flash(f"Error fetching sales history: {e}", 'danger')
        finally:
            conn.close()
    return redirect(url_for('home'))

@app.route('/add_supplier', methods=['GET', 'POST'])
@login_required
def add_supplier():
    if request.method == 'POST':
        try:
            supplier_id = int(request.form['supplier_id'])
            name = request.form['name']
            email = request.form['email']
            phone = request.form['phone']
            address = request.form['address']

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO suppliers (supplier_id, name, email, phone, address) "
                "VALUES (%s, %s, %s, %s, %s)",
                (supplier_id, name, email, phone, address)
            )
            conn.commit()
            flash('Supplier added successfully!', 'success')
        except Error as e:
            conn.rollback()
            flash(f'Error adding supplier: {e}', 'danger')
        finally:
            if conn:
                conn.close()
        return redirect(url_for('suppliers'))
    return render_template('add_supplier.html')

@app.route('/suppliers')
@login_required
def suppliers():
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM suppliers")
            suppliers = cursor.fetchall()
            return render_template('suppliers.html', suppliers=suppliers)
        except Error as e:
            flash(f"Error fetching suppliers: {e}", 'danger')
        finally:
            conn.close()
    return redirect(url_for('home'))

@app.route('/profit_report', methods=['GET', 'POST'])
@login_required
def profit_report():
    if request.method == 'POST':
        month = request.form['month']
        year = request.form['year']
        conn = get_connection()
        if conn:
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.callproc('GetMonthlyProfitSummary', (month, year))
                results = []
                for result in cursor.stored_results():
                    results = result.fetchall()
                return render_template('profit_report.html', results=results, month=month, year=year)
            except Error as e:
                flash(f"Error generating profit report: {e}", 'danger')
            finally:
                conn.close()
    return render_template('profit_report.html')

@app.route('/search_stock', methods=['GET', 'POST'])
@login_required
def search_stock():
    if request.method == 'POST':
        product_name = request.form['product_name']
        conn = get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT GetStockLevelByName(%s)", (product_name,))
                stock_level = cursor.fetchone()[0]
                return render_template('search_stock.html', stock_level=stock_level, product_name=product_name)
            except Error as e:
                flash(f"Error searching stock: {e}", 'danger')
            finally:
                conn.close()
    return render_template('search_stock.html')

if __name__ == '__main__':
    app.run(debug=True)
