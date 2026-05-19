import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from dotenv import load_dotenv # NUEVO: Importa el lector de contraseñas

# NUEVO: Carga las contraseñas del archivo .env
load_dotenv()

app = Flask(__name__)

# NUEVO: Lee las contraseñas de la caja fuerte, si no las encuentra usa un valor por defecto
app.secret_key = os.environ.get('SECRET_KEY', 'clave_por_defecto_no_segura')
DB_NAME = 'worldmoon.db'
UPLOAD_FOLDER = 'static/images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Configuración de Gmail (Ahora seguro, lee la contraseña del .env)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'worldmoonsudadera16@gmail.com'
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD') # NUEVO: Lee la contraseña segura
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
mail = Mail(app)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, email TEXT UNIQUE, password TEXT, telefono TEXT, direccion TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS pedidos
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, email TEXT, telefono TEXT, productos TEXT, total REAL, estado TEXT DEFAULT 'Pendiente', metodo_pago TEXT DEFAULT 'Efectivo', direccion TEXT DEFAULT '', delivery TEXT DEFAULT 'Recoger en tienda', usuario_id INTEGER, comprobante TEXT DEFAULT '', tlf_pago TEXT DEFAULT '', fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    # NUEVO: Agregada columna 'vendidos'
    cursor.execute('''CREATE TABLE IF NOT EXISTS productos
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, genero TEXT, precio REAL, stock INTEGER DEFAULT 10, imagen TEXT, tallas TEXT, vendidos INTEGER DEFAULT 0)''')

    cursor.execute('SELECT COUNT(*) FROM productos')
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            'INSERT INTO productos (nombre, genero, precio, stock, imagen, tallas, vendidos) VALUES (?, ?, ?, ?, ?, ?, ?)',
            [
                ('Sudadera Deportiva', 'Dama',2.50, 15,
                 'https://i.postimg.cc/FF2Z4vLP/Captura-de-pantalla-2026-05-08-190239.png', 'Única', 0),
                ('Sudadera Urban', 'Caballero', 2.50, 12,
                 'https://i.postimg.cc/sxS5XBhh/Captura-de-pantalla-2026-05-08-190417.png', 'S,M,L', 0),
                ('Sudadera PLUS', 'Caballero', 3.50, 8,
                 'https://i.postimg.cc/9QcymQFS/talla-plus.webp', 'Plus', 0),
                ('Sudadera Galáctica', 'Niños', 2.00, 20,
                 'https://i.postimg.cc/8PSZvDz5/Gemini-Generated-Image-3u57sz3u57sz3u57-(2).png', '2-4,6-8,10-12', 0)
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


@app.route('/api/registro', methods=['POST'])
def api_registro():
    data = request.get_json()
    try:
        hashed_pw = generate_password_hash(data['password'], method='pbkdf2:sha256')
        conn = get_db()
        conn.execute('INSERT INTO usuarios (nombre, email, password, telefono, direccion) VALUES (?, ?, ?, ?, ?)',
                     (data['nombre'], data['email'], hashed_pw, data.get('telefono', ''), data.get('direccion', '')))
        conn.commit()
        user = conn.execute('SELECT * FROM usuarios WHERE email = ?', (data['email'],)).fetchone()
        conn.close()
        session['cliente_id'] = user['id']
        session['cliente_nombre'] = user['nombre']

        # --- NUEVO: ENVIAR CORREO DE BIENVENIDA ---
        try:
            msg_bienvenida = Message("🎉 ¡Bienvenido a World Moon!", sender='worldmoon16@gmail.com',
                                  recipients=[data['email']])
            msg_bienvenida.html = f"<h2 style='color:#9d4edd;'>¡Hola {data['nombre']}! 🌌</h2>" \
                                  f"<p>Te damos la bienvenida oficial a <strong>World Moon</strong>. Estamos felices de que te unas a nuestra comunidad cósmica.</p>" \
                                  f"<p>Ya puedes explorar nuestro catálogo, elegir tus sudaderas favoritas y realizar tus pedidos fácilmente.</p>" \
                                  f"<p>🚀 <a href='https://worldmoon.pythonanywhere.com/' style='color:#00e5ff;'>Visita nuestra tienda</a></p>" \
                                  f"<p>Con cariño,<br>El equipo de World Moon 🌙</p>"
            mail.send(msg_bienvenida)
        except Exception as e:
            print("Error enviando correo de bienvenida: ", e)

        # --- NUEVO: GENERAR LINK DE WHATSAPP DE BIENVENIDA ---
        mensaje_wa = f"Hola World Moon! 🌙 Soy {data['nombre']}, acabo de registrarme en su tienda web. ¡Quiero recibir sus novedades!"
        numero_wa = '584126023833' # Asegúrate de que este sea tu número real
        whatsapp_url = f'https://wa.me/{numero_wa}?text={mensaje_wa}'

        return jsonify({'success': True, 'nombre': user['nombre'], 'whatsapp_url': whatsapp_url})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': 'El correo ya está registrado'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    conn = get_db()
    user = conn.execute('SELECT * FROM usuarios WHERE email = ?', (data['email'],)).fetchone()
    conn.close()
    if user and check_password_hash(user['password'], data['password']):
        session['cliente_id'] = user['id']
        session['cliente_nombre'] = user['nombre']
        return jsonify({'success': True, 'nombre': user['nombre']})
    else:
        return jsonify({'success': False, 'error': 'Correo o contraseña incorrectos'}), 401


@app.route('/api/logout')
def api_logout():
    session.pop('cliente_id', None)
    session.pop('cliente_nombre', None)
    return jsonify({'success': True})


@app.route('/api/check_session')
def check_session():
    if 'cliente_id' in session:
        return jsonify({'logged_in': True, 'nombre': session['cliente_nombre']})
    return jsonify({'logged_in': False})


@app.route('/checkout', methods=['POST'])
def checkout():
    if 'cliente_id' not in session:
        return jsonify({'success': False, 'error': 'Debes iniciar sesión'}), 403

    data = request.get_json()
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO pedidos (nombre, email, telefono, productos, total, metodo_pago, direccion, delivery, usuario_id, comprobante, tlf_pago) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (data.get('nombre'), data.get('email'), data.get('telefono'), data.get('productos'), data.get('total'),
             data.get('metodo_pago', 'Efectivo'), data.get('direccion', ''), data.get('delivery', 'Recoger en tienda'),
             session['cliente_id'], data.get('comprobante', ''), data.get('tlf_pago', '')))
        conn.commit()
        pedido_id = cursor.lastrowid

        items = data.get('items_detalle', [])
        for item in items:
            prod_id = item.get('id')
            qty = item.get('cantidad')
            cursor.execute('UPDATE productos SET stock = stock - ?, vendidos = vendidos + ? WHERE id = ?',
                           (qty, qty, prod_id))
        conn.commit()
        conn.close()

        try:
            msg_cliente = Message(f"World Moon - Pedido #{pedido_id} Confirmado 🚀", sender='worldmoonsudaderas16@gmail.com',
                                  recipients=[data.get('email')])
            msg_cliente.html = f"<h2 style='color:#9d4edd;'>¡Hola {data.get('nombre')}! 🌌</h2><p>Tu pedido ha sido registrado.</p><ul><li><strong>Productos:</strong> {data.get('productos')}</li><li><strong>Total:</strong> ${data.get('total')}</li></ul>"
            mail.send(msg_cliente)
            msg_admin = Message(f"🚨 Nuevo Pedido Web #{pedido_id}", sender='worldmoonsudaderas16@gmail.com',
                                recipients=['worldmoonsudaderas16@gmail.com'])
            msg_admin.html = f"<h2>Nuevo Pedido</h2><p><strong>Cliente:</strong> {data.get('nombre')} (${data.get('total')})</p>"
            mail.send(msg_admin)
        except Exception as e:
            print("Error enviando correo: ", e)

        comp_text = f"\n📄 *Comprobante:* {data.get('comprobante')}\n📱 *Tlf Origen:* {data.get('tlf_pago')}" if data.get(
            'metodo_pago') == 'Pago Movil' else ""
        mensaje_wa = f"Hola World Moon! 🌙 Pedido #{pedido_id}:\n👤 *Nombre:* {data.get('nombre')}\n📦 *Productos:* {data.get('productos')}\n💰 *Total:* ${data.get('total')}{comp_text}"
        numero_wa = '584126023833'
        whatsapp_url = f'https://wa.me/{numero_wa}?text={mensaje_wa}'

        return jsonify({'success': True, 'whatsapp_url': whatsapp_url})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# --- RUTAS DE ADMINISTRACIÓN ---

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        # NUEVO: Lee la contraseña del admin desde la caja fuerte
        admin_pass = os.environ.get('ADMIN_PASSWORD', 'worldmoon2025')
        if request.form.get('usuario') == 'admin' and request.form.get('password') == admin_pass:
            session['admin'] = True
            return redirect('/admin')
        return render_template('admin_login.html', error=True)
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect('/admin/login')


@app.route('/admin')
def admin():
    if not session.get('admin'): return redirect('/admin/login')

    conn = get_db()
    pedidos = conn.execute('SELECT * FROM pedidos ORDER BY fecha DESC').fetchall()
    productos = conn.execute('SELECT * FROM productos ORDER BY vendidos DESC').fetchall()

    # NUEVA LÍNEA: Consultar clientes
    clientes = conn.execute('SELECT * FROM usuarios ORDER BY id DESC').fetchall()

    total_pedidos = conn.execute('SELECT COUNT(*) as c FROM pedidos').fetchone()['c']
    total_ventas = conn.execute('SELECT COALESCE(SUM(total), 0) as s FROM pedidos').fetchone()['s']
    pendientes = conn.execute("SELECT COUNT(*) as c FROM pedidos WHERE estado='Pendiente'").fetchone()['c']
    completados = conn.execute("SELECT COUNT(*) as c FROM pedidos WHERE estado='Completado'").fetchone()['c']

    top_productos = conn.execute(
        'SELECT nombre, vendidos FROM productos WHERE vendidos > 0 ORDER BY vendidos DESC LIMIT 3').fetchall()
    clientes_frecuentes = conn.execute(
        'SELECT nombre, email, COUNT(id) as compras, SUM(total) as total_gastado FROM pedidos GROUP BY email ORDER BY compras DESC LIMIT 3').fetchall()

    conn.close()

    # AQUÍ AGREGAMOS "clientes=clientes"
    return render_template('admin.html', pedidos=pedidos, productos=productos, clientes=clientes,
                           total_pedidos=total_pedidos, total_ventas=total_ventas,
                           pendientes=pendientes, completados=completados,
                           top_productos=top_productos, clientes_frecuentes=clientes_frecuentes)


@app.route('/admin/actualizar_estado/<int:pedido_id>', methods=['POST'])
def actualizar_estado(pedido_id):
    if not session.get('admin'): return jsonify({'success': False}), 403
    conn = get_db()
    conn.execute('UPDATE pedidos SET estado=? WHERE id=?', (request.form.get('estado'), pedido_id))
    conn.commit();
    conn.close()
    return jsonify({'success': True})


@app.route('/admin/restock/<int:producto_id>', methods=['POST'])
def restock(producto_id):
    if not session.get('admin'): return jsonify({'success': False}), 403
    cantidad = int(request.form.get('cantidad', 0))
    if cantidad > 0:
        conn = get_db()
        conn.execute('UPDATE productos SET stock = stock + ? WHERE id=?', (cantidad, producto_id))
        conn.commit();
        conn.close()
    return jsonify({'success': True})


@app.route('/admin/upload', methods=['POST'])
def upload_file():
    if not session.get('admin'): return jsonify({'success': False}), 403
    if 'file' not in request.files: return jsonify({'success': False, 'error': 'No file'})
    file = request.files['file']
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return jsonify({'success': True, 'url': '/static/images/' + filename})
    return jsonify({'success': False, 'error': 'Invalid file'})


@app.route('/admin/agregar_producto', methods=['POST'])
def agregar_producto():
    if not session.get('admin'): return jsonify({'success': False}), 403
    conn = get_db()
    conn.execute('INSERT INTO productos (nombre, genero, precio, stock, imagen, tallas) VALUES (?, ?, ?, ?, ?, ?)',
                 (request.form.get('nombre'), request.form.get('genero'), float(request.form.get('precio')),
                  int(request.form.get('stock')), request.form.get('imagen', ''), request.form.get('tallas', 'Única')))
    conn.commit();
    conn.close()
    return jsonify({'success': True})


@app.route('/admin/editar_producto/<int:producto_id>', methods=['POST'])
def editar_producto(producto_id):
    if not session.get('admin'): return jsonify({'success': False}), 403
    conn = get_db()
    conn.execute('UPDATE productos SET nombre=?, genero=?, precio=?, stock=?, imagen=?, tallas=? WHERE id=?',
                 (request.form.get('nombre'), request.form.get('genero'), float(request.form.get('precio')),
                  int(request.form.get('stock')), request.form.get('imagen'), request.form.get('tallas'), producto_id))
    conn.commit();
    conn.close()
    return jsonify({'success': True})


@app.route('/admin/eliminar_producto/<int:producto_id>', methods=['POST'])
def eliminar_producto(producto_id):
    if not session.get('admin'): return jsonify({'success': False}), 403
    conn = get_db();
    conn.execute('DELETE FROM productos WHERE id=?', (producto_id,));
    conn.commit();
    conn.close()
    return jsonify({'success': True})


@app.route('/admin/eliminar_pedido/<int:pedido_id>', methods=['POST'])
def eliminar_pedido(pedido_id):
    if not session.get('admin'): return jsonify({'success': False}), 403
    conn = get_db();
    conn.execute('DELETE FROM pedidos WHERE id=?', (pedido_id,));
    conn.commit();
    conn.close()
    return jsonify({'success': True})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)