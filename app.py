import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'worldmoon2025'
DB_NAME = 'worldmoon.db'
UPLOAD_FOLDER = 'static/images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS pedidos
                      (
                          id
                          INTEGER
                          PRIMARY
                          KEY
                          AUTOINCREMENT,
                          nombre
                          TEXT,
                          email
                          TEXT,
                          telefono
                          TEXT,
                          productos
                          TEXT,
                          total
                          REAL,
                          estado
                          TEXT
                          DEFAULT
                          'Pendiente',
                          metodo_pago
                          TEXT
                          DEFAULT
                          'Efectivo',
                          direccion
                          TEXT
                          DEFAULT
                          '',
                          delivery
                          TEXT
                          DEFAULT
                          'Recoger en tienda',
                          fecha
                          TIMESTAMP
                          DEFAULT
                          CURRENT_TIMESTAMP
                      )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS productos
                      (
                          id
                          INTEGER
                          PRIMARY
                          KEY
                          AUTOINCREMENT,
                          nombre
                          TEXT,
                          genero
                          TEXT,
                          precio
                          REAL,
                          stock
                          INTEGER
                          DEFAULT
                          10,
                          imagen
                          TEXT,
                          tallas
                          TEXT
                      )''')

    cursor.execute('SELECT COUNT(*) FROM productos')
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            'INSERT INTO productos (nombre, genero, precio, stock, imagen, tallas) VALUES (?, ?, ?, ?, ?, ?)', [
                ('Sudadera Clásica', 'Dama', 2.50, 15,
                 'https://images.unsplash.com/photo-1618354691373-d851c5c3a990?w=500&q=80', 'Única'),
                ('Sudadera Deportiva', 'Dama', 2.50, 10,
                 'https://images.unsplash.com/photo-1556821840-3a63f95609a7?w=500&q=80', 'S,M,L'),
                ('Sudadera Urban', 'Caballero', 2.50, 12,
                 'https://images.unsplash.com/photo-1578768079052-aa76e52ff62e?w=500&q=80', 'M,L,Plus'),
                ('Sudadera Premium', 'Caballero', 3.50, 8,
                 'https://images.unsplash.com/photo-1611312449412-6cefac5dc3e4?w=500&q=80', 'L,Plus')
            ])

    conn.commit()
    conn.close()


init_db()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/productos')
def api_productos():
    conn = get_db()
    productos = conn.execute('SELECT * FROM productos').fetchall()
    conn.close()
    return jsonify([dict(p) for p in productos])


@app.route('/checkout', methods=['POST'])
def checkout():
    data = request.get_json()
    try:
        conn = get_db()
        conn.execute(
            'INSERT INTO pedidos (nombre, email, telefono, productos, total, metodo_pago, direccion, delivery) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (data.get('nombre'), data.get('email'), data.get('telefono'), data.get('productos'), data.get('total'),
             data.get('metodo_pago', 'Efectivo'), data.get('direccion', ''), data.get('delivery', 'Recoger en tienda')))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        password = request.form.get('password')
        if usuario == 'admin' and password == 'worldmoon2025':
            session['admin'] = True
            return redirect('/admin')
        else:
            return render_template('admin_login.html', error=True)
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect('/admin/login')


@app.route('/admin')
def admin():
    if not session.get('admin'):
        return redirect('/admin/login')

    conn = get_db()
    pedidos = conn.execute('SELECT * FROM pedidos ORDER BY fecha DESC').fetchall()
    productos = conn.execute('SELECT * FROM productos').fetchall()

    total_pedidos = conn.execute('SELECT COUNT(*) as c FROM pedidos').fetchone()['c']
    total_ventas = conn.execute('SELECT COALESCE(SUM(total), 0) as s FROM pedidos').fetchone()['s']
    pendientes = conn.execute("SELECT COUNT(*) as c FROM pedidos WHERE estado='Pendiente'").fetchone()['c']
    completados = conn.execute("SELECT COUNT(*) as c FROM pedidos WHERE estado='Completado'").fetchone()['c']

    conn.close()
    return render_template('admin.html', pedidos=pedidos, productos=productos,
                           total_pedidos=total_pedidos, total_ventas=total_ventas,
                           pendientes=pendientes, completados=completados)


@app.route('/admin/actualizar_estado/<int:pedido_id>', methods=['POST'])
def actualizar_estado(pedido_id):
    if not session.get('admin'):
        return jsonify({'success': False}), 403
    estado = request.form.get('estado')
    conn = get_db()
    conn.execute('UPDATE pedidos SET estado=? WHERE id=?', (estado, pedido_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/admin/upload', methods=['POST'])
def upload_file():
    if not session.get('admin'):
        return jsonify({'success': False}), 403
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No se seleccionó archivo'})
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No se seleccionó archivo'})
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return jsonify({'success': True, 'url': '/static/images/' + filename})
    return jsonify({'success': False, 'error': 'Tipo de archivo no permitido'})


@app.route('/admin/agregar_producto', methods=['POST'])
def agregar_producto():
    if not session.get('admin'):
        return jsonify({'success': False}), 403
    nombre = request.form.get('nombre')
    genero = request.form.get('genero')
    precio = request.form.get('precio')
    stock = request.form.get('stock')
    imagen = request.form.get('imagen', 'https://images.unsplash.com/photo-1618354691373-d851c5c3a990?w=500&q=80')
    tallas = request.form.get('tallas', 'Única')
    conn = get_db()
    conn.execute('INSERT INTO productos (nombre, genero, precio, stock, imagen, tallas) VALUES (?, ?, ?, ?, ?, ?)',
                 (nombre, genero, float(precio), int(stock), imagen, tallas))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/admin/editar_producto/<int:producto_id>', methods=['POST'])
def editar_producto(producto_id):
    if not session.get('admin'):
        return jsonify({'success': False}), 403
    nombre = request.form.get('nombre')
    genero = request.form.get('genero')
    precio = request.form.get('precio')
    stock = request.form.get('stock')
    imagen = request.form.get('imagen')
    tallas = request.form.get('tallas')
    conn = get_db()
    conn.execute('UPDATE productos SET nombre=?, genero=?, precio=?, stock=?, imagen=?, tallas=? WHERE id=?',
                 (nombre, genero, float(precio), int(stock), imagen, tallas, producto_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/admin/eliminar_producto/<int:producto_id>', methods=['POST'])
def eliminar_producto(producto_id):
    if not session.get('admin'):
        return jsonify({'success': False}), 403
    conn = get_db()
    conn.execute('DELETE FROM productos WHERE id=?', (producto_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/admin/eliminar_pedido/<int:pedido_id>', methods=['POST'])
def eliminar_pedido(pedido_id):
    if not session.get('admin'):
        return jsonify({'success': False}), 403
    conn = get_db()
    conn.execute('DELETE FROM pedidos WHERE id=?', (pedido_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))