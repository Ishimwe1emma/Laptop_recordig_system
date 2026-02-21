from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, Response
from functools import wraps
import mysql.connector
from mysql.connector import pooling, Error
import os
import json
import csv
from io import StringIO
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import pymysql

app = Flask(__name__)
app.secret_key = os.urandom(24)

# ===== MySQL DATABASE CONFIGURATION =====
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'EmmaIshimwe#2000'
app.config['MYSQL_DATABASE'] = 'ur_laptop_systems'
app.config['MYSQL_PORT'] = 3306
app.config['MYSQL_CHARSET'] = 'utf8mb4'
app.config['MYSQL_POOL_NAME'] = 'ur_laptop_pool'
app.config['MYSQL_POOL_SIZE'] = 5

# Database connection pool
db_pool = None

def init_db_pool():
    """Initialize MySQL connection pool"""
    global db_pool
    try:
        db_pool = mysql.connector.pooling.MySQLConnectionPool(
            pool_name=app.config['MYSQL_POOL_NAME'],
            pool_size=app.config['MYSQL_POOL_SIZE'],
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DATABASE'],
            port=app.config['MYSQL_PORT'],
            charset=app.config['MYSQL_CHARSET'],
            autocommit=True
        )
        print("✓ MySQL connection pool initialized successfully")
    except Error as e:
        print(f"✗ Error initializing MySQL connection pool: {e}")
        create_database_if_not_exists()
        db_pool = mysql.connector.pooling.MySQLConnectionPool(
            pool_name=app.config['MYSQL_POOL_NAME'],
            pool_size=app.config['MYSQL_POOL_SIZE'],
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DATABASE'],
            port=app.config['MYSQL_PORT'],
            charset=app.config['MYSQL_CHARSET'],
            autocommit=True
        )

def create_database_if_not_exists():
    """Create database if it doesn't exist"""
    try:
        conn = mysql.connector.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            port=app.config['MYSQL_PORT']
        )
        cursor = conn.cursor()
        
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {app.config['MYSQL_DATABASE']} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print(f"✓ Database '{app.config['MYSQL_DATABASE']}' created or already exists")
        
        cursor.close()
        conn.close()
    except Error as e:
        print(f"✗ Error creating database: {e}")

def get_db_connection():
    """Get a connection from the pool"""
    try:
        return db_pool.get_connection()
    except Error as e:
        print(f"✗ Error getting database connection: {e}")
        init_db_pool()
        return db_pool.get_connection()

def get_db():
    """Get database connection and cursor"""
    conn = get_db_connection()
    return conn

# Initialize database pool on startup
init_db_pool()

def init_db():
    """Initialize MySQL database with all tables - REMOVED ADMIN ROLE"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Create users table - ONLY USER ROLE
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                campus VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_username (username),
                INDEX idx_campus (campus)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Create laptop_records table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS laptop_records (
                id INT AUTO_INCREMENT PRIMARY KEY,
                campus VARCHAR(100) NOT NULL,
                college VARCHAR(100) NOT NULL,
                school VARCHAR(100) NOT NULL,
                department VARCHAR(100) NOT NULL,
                year_of_study VARCHAR(20) NOT NULL,
                student_names VARCHAR(255) NOT NULL,
                registration_number VARCHAR(50) NOT NULL,
                telephone VARCHAR(20) NOT NULL,
                laptop_type VARCHAR(100) NOT NULL,
                serial_number VARCHAR(100) NOT NULL,
                direction ENUM('IN', 'OUT') NOT NULL,
                date_time DATETIME NOT NULL,
                recorded_by VARCHAR(50) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_campus_date (campus, date_time),
                INDEX idx_serial (serial_number),
                INDEX idx_registration (registration_number),
                INDEX idx_telephone (telephone),
                INDEX idx_direction (direction),
                INDEX idx_recorded_by (recorded_by)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Create archived records table for soft deletes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS archived_laptop_records (
                id INT AUTO_INCREMENT PRIMARY KEY,
                original_id INT,
                campus VARCHAR(100) NOT NULL,
                college VARCHAR(100) NOT NULL,
                school VARCHAR(100) NOT NULL,
                department VARCHAR(100) NOT NULL,
                year_of_study VARCHAR(20) NOT NULL,
                student_names VARCHAR(255) NOT NULL,
                registration_number VARCHAR(50) NOT NULL,
                telephone VARCHAR(20) NOT NULL,
                laptop_type VARCHAR(100) NOT NULL,
                serial_number VARCHAR(100) NOT NULL,
                direction ENUM('IN', 'OUT') NOT NULL,
                date_time DATETIME NOT NULL,
                recorded_by VARCHAR(50) NOT NULL,
                created_at TIMESTAMP NULL,
                archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                archived_by VARCHAR(50),
                INDEX idx_original_id (original_id),
                INDEX idx_campus (campus),
                INDEX idx_archived_at (archived_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Create audit log table (kept but simplified)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                id INT AUTO_INCREMENT PRIMARY KEY,
                action VARCHAR(20) NOT NULL,
                table_name VARCHAR(50) NOT NULL,
                record_id INT,
                old_data TEXT,
                new_data TEXT,
                changed_by VARCHAR(50) NOT NULL,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                campus VARCHAR(100) NOT NULL,
                INDEX idx_action (action),
                INDEX idx_table_name (table_name),
                INDEX idx_record_id (record_id),
                INDEX idx_changed_at (changed_at),
                INDEX idx_campus (campus)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Check if we need to insert sample users - ONLY REGULAR USERS
        cursor.execute('SELECT COUNT(*) FROM users')
        count = cursor.fetchone()[0]
        
        if count == 0:
            # Create ONLY regular users for each campus
            users_data = []
            for username, campus in [
                ('user_huye', 'Huye Campus'),
                ('user_gikondo', 'Gikondo Campus'),
                ('user_busogo', 'Busogo Campus'),
                ('user_nyagatare', 'Nyagatare Campus'),
                ('user_remera', 'Remera Campus'),
                ('user_nyarugenge', 'Nyarugenge Campus'),
                ('user_rwamagana', 'Rwamagana Campus'),
                ('user_rukara', 'Rukara Campus')
            ]:
                hashed_pw = generate_password_hash('password123')
                users_data.append((username, hashed_pw, campus))
            
            insert_query = 'INSERT INTO users (username, password, campus) VALUES (%s, %s, %s)'
            cursor.executemany(insert_query, users_data)
            print("✓ Sample users created with password: password123")
            print("✓ Only regular users - no admin accounts")
        
        # Create triggers for audit logging (simplified)
        try:
            cursor.execute('DROP TRIGGER IF EXISTS audit_laptop_insert')
            cursor.execute('DROP TRIGGER IF EXISTS audit_laptop_update')
            cursor.execute('DROP TRIGGER IF EXISTS audit_laptop_delete')
            
            # Simplified triggers
            cursor.execute('''
                CREATE TRIGGER audit_laptop_insert 
                AFTER INSERT ON laptop_records
                FOR EACH ROW
                BEGIN
                    INSERT INTO audit_log (action, table_name, record_id, new_data, changed_by, campus)
                    VALUES ('INSERT', 'laptop_records', NEW.id, 
                           JSON_OBJECT(
                               'campus', NEW.campus,
                               'student', NEW.student_names,
                               'registration', NEW.registration_number,
                               'serial', NEW.serial_number,
                               'direction', NEW.direction,
                               'recorded_by', NEW.recorded_by
                           ),
                           NEW.recorded_by, NEW.campus);
                END
            ''')
            
            print("✓ MySQL audit triggers created successfully")
        except Error as e:
            print(f"⚠ Warning: Error creating MySQL triggers: {e}")
        
        conn.commit()
        cursor.close()
        conn.close()
        print("✓ MySQL database initialized successfully")
        
    except Error as e:
        print(f"✗ Error initializing MySQL database: {e}")
        raise

# Initialize database on startup
init_db()

# Login required decorator (NO ADMIN CHECK)
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'loggedin' not in session:
            flash('Please login first', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ===== SIMPLIFIED ROUTES =====

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            flash('Username and password are required', 'danger')
            return render_template('login.html')
        
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['loggedin'] = True
            session['id'] = user['id']
            session['username'] = user['username']
            session['campus'] = user['campus']
            # No role since we removed admin
            flash(f'Welcome back, {user["username"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    today = datetime.now().strftime('%Y-%m-%d')
    
    cursor.execute('''
        SELECT 
            COUNT(*) as total_today,
            SUM(CASE WHEN direction = 'IN' THEN 1 ELSE 0 END) as in_today,
            SUM(CASE WHEN direction = 'OUT' THEN 1 ELSE 0 END) as out_today
        FROM laptop_records 
        WHERE campus = %s AND DATE(date_time) = %s
    ''', (session['campus'], today))
    
    stats = cursor.fetchone()
    
    week_start = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    cursor.execute('''
        SELECT 
            COUNT(*) as total_week,
            SUM(CASE WHEN direction = 'IN' THEN 1 ELSE 0 END) as in_week,
            SUM(CASE WHEN direction = 'OUT' THEN 1 ELSE 0 END) as out_week
        FROM laptop_records 
        WHERE campus = %s AND DATE(date_time) >= %s
    ''', (session['campus'], week_start))
    
    week_stats = cursor.fetchone()
    cursor.close()
    conn.close()
    
    return render_template('dashboard.html', 
                         campus=session['campus'], 
                         username=session['username'],
                         stats=stats,
                         week_stats=week_stats)

@app.route('/add_record', methods=['GET', 'POST'])
@login_required
def add_record():
    if request.method == 'POST':
        try:
            campus = session['campus']
            
            form_campus = request.form.get('campus', '').strip()
            if form_campus and form_campus != session['campus']:
                flash('Cannot add record for different campus', 'danger')
                return redirect(url_for('add_record'))
            
            college = request.form.get('college', '').strip()
            school = request.form.get('school', '').strip()
            department = request.form.get('department', '').strip()
            year_of_study = request.form.get('year_of_study', '').strip()
            student_names = request.form.get('student_names', '').strip()
            registration_number = request.form.get('registration_number', '').strip().upper()
            telephone = request.form.get('telephone', '').strip()
            laptop_type = request.form.get('laptop_type', '').strip()
            serial_number = request.form.get('serial_number', '').strip().upper()
            direction = request.form.get('direction', '').strip()
            date_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            recorded_by = session['username']
            
            # Validate required fields
            required_fields = [
                ('college', college),
                ('school', school),
                ('department', department),
                ('year_of_study', year_of_study),
                ('student_names', student_names),
                ('registration_number', registration_number),
                ('telephone', telephone),
                ('laptop_type', laptop_type),
                ('serial_number', serial_number),
                ('direction', direction)
            ]
            
            missing_fields = []
            for field_name, field_value in required_fields:
                if not field_value:
                    missing_fields.append(field_name.replace('_', ' ').title())
            
            if missing_fields:
                flash(f'Required fields missing: {", ".join(missing_fields)}', 'danger')
                return redirect(url_for('add_record'))
            
            if not telephone.isdigit() or len(telephone) < 10:
                flash('Telephone number must contain only digits and be at least 10 characters', 'danger')
                return redirect(url_for('add_record'))
            
            conn = get_db()
            cursor = conn.cursor(dictionary=True)
            
            # REMOVED DUPLICATE SERIAL NUMBER CHECK
            # Serial numbers can now be repeated
            
            cursor.execute('''
                INSERT INTO laptop_records 
                (campus, college, school, department, year_of_study, student_names, 
                 registration_number, telephone, laptop_type, serial_number, 
                 direction, date_time, recorded_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (campus, college, school, department, year_of_study, student_names,
                  registration_number, telephone, laptop_type, serial_number,
                  direction, date_time, recorded_by))
            
            record_id = cursor.lastrowid
            conn.commit()
            cursor.close()
            conn.close()
            
            flash(f'Record #{record_id} added successfully! Serial number {serial_number} accepted.', 'success')
            return redirect(url_for('dashboard'))
            
        except Error as e:
            flash(f'Error adding record: {str(e)}', 'danger')
            return redirect(url_for('add_record'))
    
    return render_template('add_record.html', 
                         campus=session['campus'], 
                         username=session['username'])

@app.route('/search_record', methods=['GET'])
@login_required
def search_record():
    """Search records - simplified, users can only see their campus records"""
    try:
        search_type = request.args.get('search_type', 'all')
        search_value = request.args.get('search_value', '').strip()
        direction = request.args.get('direction', 'all')
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        if page < 1:
            page = 1
        
        records = []
        total_records = 0
        total_pages = 0
        
        has_search_criteria = bool(search_value) or direction != 'all'
        
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        # Base query - users can only see their own campus records
        base_query = ' FROM laptop_records WHERE campus = %s'
        params = [session['campus']]
        
        # Apply search filters
        if search_value:
            if search_type == 'all':
                base_query += ''' AND (student_names LIKE %s OR registration_number LIKE %s 
                                   OR serial_number LIKE %s OR telephone LIKE %s 
                                   OR college LIKE %s OR department LIKE %s)'''
                search_pattern = f'%{search_value}%'
                params.extend([search_pattern] * 6)
            elif search_type == 'student_names':
                base_query += ' AND student_names LIKE %s'
                params.append(f'%{search_value}%')
            elif search_type == 'registration_number':
                base_query += ' AND registration_number LIKE %s'
                params.append(f'%{search_value}%')
            elif search_type == 'serial_number':
                base_query += ' AND serial_number LIKE %s'
                params.append(f'%{search_value}%')
            elif search_type == 'telephone':
                base_query += ' AND telephone LIKE %s'
                params.append(f'%{search_value}%')
            elif search_type == 'college':
                base_query += ' AND college LIKE %s'
                params.append(f'%{search_value}%')
            elif search_type == 'department':
                base_query += ' AND department LIKE %s'
                params.append(f'%{search_value}%')
        
        # Apply direction filter
        if direction != 'all':
            base_query += ' AND direction = %s'
            params.append(direction)
        
        if has_search_criteria or page > 1:
            count_query = 'SELECT COUNT(*) as total' + base_query
            cursor.execute(count_query, params)
            total_records = cursor.fetchone()['total']
            
            if total_records > 0:
                offset = (page - 1) * per_page
                results_query = 'SELECT *' + base_query + ' ORDER BY date_time DESC LIMIT %s OFFSET %s'
                cursor.execute(results_query, params + [per_page, offset])
                records = cursor.fetchall()
                
                total_pages = (total_records + per_page - 1) // per_page if total_records > 0 else 1
        else:
            total_records = 0
            total_pages = 0
        
        cursor.close()
        conn.close()
        
        return render_template('search_record.html',
                             records=records,
                             total_records=total_records,
                             page=page,
                             total_pages=total_pages,
                             search_type=search_type,
                             search_value=search_value,
                             direction=direction,
                             campus=session['campus'],
                             username=session['username'],
                             has_search_criteria=has_search_criteria)
    except Error as e:
        flash(f'Error searching records: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/export_search', methods=['GET'])
@login_required
def export_search():
    try:
        search_type = request.args.get('search_type', 'all')
        search_value = request.args.get('search_value', '').strip()
        direction = request.args.get('direction', 'all')
        
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        base_query = 'SELECT * FROM laptop_records WHERE campus = %s'
        params = [session['campus']]
        
        if search_value:
            if search_type == 'all':
                base_query += ''' AND (student_names LIKE %s OR registration_number LIKE %s 
                                   OR serial_number LIKE %s OR telephone LIKE %s 
                                   OR college LIKE %s OR department LIKE %s)'''
                search_pattern = f'%{search_value}%'
                params.extend([search_pattern] * 6)
            elif search_type == 'student_names':
                base_query += ' AND student_names LIKE %s'
                params.append(f'%{search_value}%')
            elif search_type == 'registration_number':
                base_query += ' AND registration_number LIKE %s'
                params.append(f'%{search_value}%')
            elif search_type == 'serial_number':
                base_query += ' AND serial_number LIKE %s'
                params.append(f'%{search_value}%')
            elif search_type == 'telephone':
                base_query += ' AND telephone LIKE %s'
                params.append(f'%{search_value}%')
            elif search_type == 'college':
                base_query += ' AND college LIKE %s'
                params.append(f'%{search_value}%')
            elif search_type == 'department':
                base_query += ' AND department LIKE %s'
                params.append(f'%{search_value}%')
        
        if direction != 'all':
            base_query += ' AND direction = %s'
            params.append(direction)
        
        base_query += ' ORDER BY date_time DESC'
        
        cursor.execute(base_query, params)
        records = cursor.fetchall()
        cursor.close()
        conn.close()
        
        output = StringIO()
        writer = csv.writer(output)
        
        writer.writerow(['ID', 'Date', 'Time', 'Campus', 'College', 'School', 'Department', 
                       'Year of Study', 'Student Name', 'Registration', 'Phone', 
                       'Laptop Type', 'Serial', 'Direction', 'Recorded By', 'Created At'])
        
        for record in records:
            dt = record['date_time']
            created_at = record['created_at']
            
            if isinstance(dt, str):
                date_part = dt[:10] if len(dt) >= 10 else dt
                time_part = dt[11:16] if len(dt) >= 16 else ''
            else:
                date_part = dt.strftime('%Y-%m-%d') if hasattr(dt, 'strftime') else str(dt)[:10]
                time_part = dt.strftime('%H:%M') if hasattr(dt, 'strftime') else ''
            
            if isinstance(created_at, str):
                created_date = created_at[:10] if len(created_at) >= 10 else created_at
            else:
                created_date = created_at.strftime('%Y-%m-%d') if hasattr(created_at, 'strftime') else ''
            
            writer.writerow([
                record['id'],
                date_part,
                time_part,
                record['campus'],
                record['college'],
                record['school'],
                record['department'],
                record['year_of_study'],
                record['student_names'],
                record['registration_number'],
                record['telephone'],
                record['laptop_type'],
                record['serial_number'],
                record['direction'],
                record['recorded_by'],
                created_date
            ])
        
        output.seek(0)
        
        today = datetime.now().date()
        filename = f'search_results_{today}.csv'
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment;filename={filename}'}
        )
    except Error as e:
        flash(f'Error exporting data: {str(e)}', 'danger')
        return redirect(url_for('search_record'))

@app.route('/view_record/<int:record_id>')
@login_required
def view_record(record_id):
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute('SELECT * FROM laptop_records WHERE id = %s AND campus = %s', 
                     (record_id, session['campus']))
        
        record = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not record:
            flash('Record not found or access denied', 'danger')
            return redirect(url_for('search_record'))
        
        return render_template('view_record.html', 
                             record=record, 
                             campus=session['campus'],
                             username=session['username'])
    except Error as e:
        flash(f'Error viewing record: {str(e)}', 'danger')
        return redirect(url_for('search_record'))

@app.route('/edit_record/<int:record_id>', methods=['GET', 'POST'])
@login_required
def edit_record(record_id):
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute('SELECT * FROM laptop_records WHERE id = %s AND campus = %s', 
                     (record_id, session['campus']))
        
        record = cursor.fetchone()
        
        if not record:
            cursor.close()
            conn.close()
            flash('Record not found or access denied', 'danger')
            return redirect(url_for('search_record'))
        
        if request.method == 'POST':
            college = request.form.get('college', '').strip()
            school = request.form.get('school', '').strip()
            department = request.form.get('department', '').strip()
            year_of_study = request.form.get('year_of_study', '').strip()
            student_names = request.form.get('student_names', '').strip()
            registration_number = request.form.get('registration_number', '').strip().upper()
            telephone = request.form.get('telephone', '').strip()
            laptop_type = request.form.get('laptop_type', '').strip()
            serial_number = request.form.get('serial_number', '').strip().upper()
            direction = request.form.get('direction', '').strip()
            
            required_fields = [
                ('college', college),
                ('school', school),
                ('department', department),
                ('year_of_study', year_of_study),
                ('student_names', student_names),
                ('registration_number', registration_number),
                ('telephone', telephone),
                ('laptop_type', laptop_type),
                ('serial_number', serial_number),
                ('direction', direction)
            ]
            
            missing_fields = []
            for field_name, field_value in required_fields:
                if not field_value:
                    missing_fields.append(field_name.replace('_', ' ').title())
            
            if missing_fields:
                flash(f'Required fields missing: {", ".join(missing_fields)}', 'danger')
                return redirect(url_for('edit_record', record_id=record_id))
            
            if not telephone.isdigit() or len(telephone) < 10:
                flash('Telephone number must contain only digits and be at least 10 characters', 'danger')
                return redirect(url_for('edit_record', record_id=record_id))
            
            # REMOVED DUPLICATE SERIAL NUMBER CHECK
            # Serial numbers can now be repeated
            
            cursor.execute('''
                UPDATE laptop_records 
                SET college = %s, school = %s, department = %s, year_of_study = %s,
                    student_names = %s, registration_number = %s, telephone = %s,
                    laptop_type = %s, serial_number = %s, direction = %s,
                    recorded_by = %s, date_time = NOW()
                WHERE id = %s
            ''', (college, school, department, year_of_study, student_names,
                  registration_number, telephone, laptop_type, serial_number,
                  direction, session['username'], record_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            flash('Record updated successfully!', 'success')
            return redirect(url_for('view_record', record_id=record_id))
        
        cursor.close()
        conn.close()
        return render_template('edit_record.html', 
                             record=record, 
                             campus=session['campus'],
                             username=session['username'])
    except Error as e:
        flash(f'Error editing record: {str(e)}', 'danger')
        return redirect(url_for('search_record'))

@app.route('/delete_record/<int:record_id>', methods=['POST'])
@login_required
def delete_record(record_id):
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute('SELECT * FROM laptop_records WHERE id = %s AND campus = %s', 
                     (record_id, session['campus']))
        
        record = cursor.fetchone()
        
        if not record:
            cursor.close()
            conn.close()
            flash('Record not found or access denied', 'danger')
            return redirect(url_for('search_record'))
        
        action = request.form.get('action', 'archive')
        
        if action == 'archive':
            cursor.execute('''
                INSERT INTO archived_laptop_records 
                (original_id, campus, college, school, department, year_of_study,
                 student_names, registration_number, telephone, laptop_type,
                 serial_number, direction, date_time, recorded_by, created_at,
                 archived_by)
                SELECT id, campus, college, school, department, year_of_study,
                       student_names, registration_number, telephone, laptop_type,
                       serial_number, direction, date_time, recorded_by, created_at,
                       %s
                FROM laptop_records WHERE id = %s
            ''', (session['username'], record_id))
            
            cursor.execute('DELETE FROM laptop_records WHERE id = %s', (record_id,))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            flash(f'Record archived successfully! Student: {record["student_names"]}', 'info')
            
        else:
            cursor.execute('DELETE FROM laptop_records WHERE id = %s', (record_id,))
            conn.commit()
            cursor.close()
            conn.close()
            
            flash(f'Record permanently deleted! Student: {record["student_names"]}', 'warning')
        
        return redirect(url_for('search_record'))
    except Error as e:
        flash(f'Error deleting record: {str(e)}', 'danger')
        return redirect(url_for('search_record'))

@app.route('/bulk_operations', methods=['GET', 'POST'])
@login_required
def bulk_operations():
    if request.method == 'POST':
        action = request.form.get('bulk_action')
        record_ids = request.form.getlist('record_ids')
        
        if not record_ids:
            flash('No records selected', 'warning')
            return redirect(url_for('search_record'))
        
        record_ids = [int(id) for id in record_ids]
        conn = get_db()
        cursor = conn.cursor()
        
        if action == 'delete':
            placeholders = ','.join(['%s'] * len(record_ids))
            cursor.execute(f'''
                DELETE FROM laptop_records 
                WHERE id IN ({placeholders}) AND campus = %s
            ''', record_ids + [session['campus']])
            
            conn.commit()
            cursor.close()
            conn.close()
            flash(f'{len(record_ids)} records deleted successfully!', 'warning')
            
        elif action == 'export':
            placeholders = ','.join(['%s'] * len(record_ids))
            cursor.execute(f'''
                SELECT * FROM laptop_records 
                WHERE id IN ({placeholders}) AND campus = %s
                ORDER BY date_time DESC
            ''', record_ids + [session['campus']])
            
            records = cursor.fetchall()
            cursor.close()
            conn.close()
            
            output = StringIO()
            writer = csv.writer(output)
            
            writer.writerow(['Date', 'Time', 'Campus', 'Student Name', 'Registration', 
                           'Phone', 'Laptop Type', 'Serial', 'Direction', 'Recorded By'])
            
            for record in records:
                dt = record['date_time']
                if isinstance(dt, str):
                    date_part = dt[:10]
                    time_part = dt[11:16]
                else:
                    date_part = dt.strftime('%Y-%m-%d') if hasattr(dt, 'strftime') else str(dt)[:10]
                    time_part = dt.strftime('%H:%M') if hasattr(dt, 'strftime') else ''
                
                writer.writerow([
                    date_part, time_part, record['campus'],
                    record['student_names'], record['registration_number'],
                    record['telephone'], record['laptop_type'], record['serial_number'],
                    record['direction'], record['recorded_by']
                ])
            
            output.seek(0)
            today = datetime.now().date()
            filename = f'selected_records_{today}.csv'
            
            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment;filename={filename}'}
            )
        
        return redirect(url_for('search_record'))
    
    return render_template('bulk_operations.html', 
                         campus=session['campus'], 
                         username=session['username'])

@app.route('/archived_records')
@login_required
def archived_records():
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute('''
            SELECT * FROM archived_laptop_records 
            WHERE campus = %s 
            ORDER BY archived_at DESC
        ''', (session['campus'],))
        
        archived = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Pass current datetime to template
        now = datetime.now()
        
        return render_template('archived_records.html', 
                             archived=archived, 
                             campus=session['campus'], 
                             username=session['username'],
                             now=now)  # Add this line
    except Error as e:
        flash(f'Error loading archived records: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/reports', methods=['GET', 'POST'])
@login_required
def reports():
    try:
        direction = request.args.get('direction', 'All')
        period = request.args.get('period', 'today')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        today = datetime.now().date()
        
        if period == 'today':
            start_date = today
            end_date = today
        elif period == 'yesterday':
            start_date = today - timedelta(days=1)
            end_date = today - timedelta(days=1)
        elif period == 'last7days':
            start_date = today - timedelta(days=7)
            end_date = today
        elif period == 'last30days':
            start_date = today - timedelta(days=30)
            end_date = today
        elif period == 'thismonth':
            start_date = today.replace(day=1)
            end_date = today
        elif period == 'lastmonth':
            first_day = today.replace(day=1)
            start_date = (first_day - timedelta(days=1)).replace(day=1)
            end_date = first_day - timedelta(days=1)
        elif period == 'custom' and start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid date format. Using today as default.', 'warning')
                start_date = today
                end_date = today
        else:
            start_date = today
            end_date = today
        
        start_date_formatted = start_date.strftime('%Y-%m-%d')
        end_date_formatted = end_date.strftime('%Y-%m-%d')
        
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        query = '''
            SELECT * FROM laptop_records 
            WHERE date(date_time) BETWEEN %s AND %s AND campus = %s
        '''
        params = [start_date_formatted, end_date_formatted, session['campus']]
        
        if direction != 'All':
            query += ' AND direction = %s'
            params.append(direction)
        
        query += ' ORDER BY date_time DESC'
        
        cursor.execute(query, params)
        records = cursor.fetchall()
        
        stats_query = '''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN direction = 'IN' THEN 1 ELSE 0 END) as in_count,
                SUM(CASE WHEN direction = 'OUT' THEN 1 ELSE 0 END) as out_count,
                COUNT(DISTINCT student_names) as unique_students,
                COUNT(DISTINCT serial_number) as unique_laptops
            FROM laptop_records 
            WHERE date(date_time) BETWEEN %s AND %s AND campus = %s
        '''
        stats_params = [start_date_formatted, end_date_formatted, session['campus']]
        
        if direction != 'All':
            stats_query += ' AND direction = %s'
            stats_params.append(direction)
        
        cursor.execute(stats_query, stats_params)
        stats = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return render_template('reports.html',
                             records=records,
                             stats=stats,
                             direction=direction,
                             period=period,
                             start_date=start_date_formatted,
                             end_date=end_date_formatted,
                             username=session['username'],
                             current_campus=session['campus'])
    except Error as e:
        flash(f'Error generating report: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/export_report')
@login_required
def export_report():
    try:
        direction = request.args.get('direction', 'All')
        period = request.args.get('period', 'today')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        today = datetime.now().date()
        
        if period == 'today':
            start_date = today
            end_date = today
        elif period == 'yesterday':
            start_date = today - timedelta(days=1)
            end_date = today - timedelta(days=1)
        elif period == 'last7days':
            start_date = today - timedelta(days=7)
            end_date = today
        elif period == 'last30days':
            start_date = today - timedelta(days=30)
            end_date = today
        elif period == 'thismonth':
            start_date = today.replace(day=1)
            end_date = today
        elif period == 'lastmonth':
            first_day = today.replace(day=1)
            start_date = (first_day - timedelta(days=1)).replace(day=1)
            end_date = first_day - timedelta(days=1)
        elif period == 'custom' and start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid date format. Using today as default.', 'warning')
                start_date = today
                end_date = today
        else:
            start_date = today
            end_date = today
        
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        query = '''
            SELECT * FROM laptop_records 
            WHERE date(date_time) BETWEEN %s AND %s AND campus = %s
        '''
        params = [start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), session['campus']]
        
        if direction != 'All':
            query += ' AND direction = %s'
            params.append(direction)
        
        query += ' ORDER BY date_time DESC'
        
        cursor.execute(query, params)
        records = cursor.fetchall()
        cursor.close()
        conn.close()
        
        output = StringIO()
        writer = csv.writer(output)
        
        writer.writerow(['Date', 'Time', 'Campus', 'College', 'School', 'Department', 
                         'Year of Study', 'Student Name', 'Registration', 'Phone', 
                         'Laptop Type', 'Serial', 'Direction', 'Recorded By', 'Date Added'])
        
        for record in records:
            dt = record['date_time']
            created_at = record['created_at']
            
            if isinstance(dt, str):
                date_part = dt[:10]
                time_part = dt[11:16]
            else:
                date_part = dt.strftime('%Y-%m-%d') if hasattr(dt, 'strftime') else str(dt)[:10]
                time_part = dt.strftime('%H:%M') if hasattr(dt, 'strftime') else ''
            
            if isinstance(created_at, str):
                created_date = created_at[:10]
            else:
                created_date = created_at.strftime('%Y-%m-%d') if hasattr(created_at, 'strftime') else ''
            
            writer.writerow([
                date_part,
                time_part,
                record['campus'],
                record['college'],
                record['school'],
                record['department'],
                record['year_of_study'],
                record['student_names'],
                record['registration_number'],
                record['telephone'],
                record['laptop_type'],
                record['serial_number'],
                record['direction'],
                record['recorded_by'],
                created_date
            ])
        
        output.seek(0)
        
        if period == 'custom':
            filename = f'laptop_report_{start_date}_to_{end_date}_{session["campus"]}.csv'
        else:
            filename = f'laptop_report_{today}_{session["campus"]}_{period}.csv'
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment;filename={filename}'}
        )
    except Error as e:
        flash(f'Error exporting report: {str(e)}', 'danger')
        return redirect(url_for('reports'))

@app.route('/calendar_report', methods=['GET', 'POST'])
@login_required
def calendar_report():
    try:
        today = datetime.now().date()
        start_date_str = request.args.get('start_date', today.strftime('%Y-%m-%d'))
        end_date_str = request.args.get('end_date', today.strftime('%Y-%m-%d'))
        direction = request.args.get('direction', 'all')
        
        try:
            start_date_obj = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date_obj = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date_obj = today
            end_date_obj = today
            start_date_str = today.strftime('%Y-%m-%d')
            end_date_str = today.strftime('%Y-%m-%d')
        
        if start_date_obj > end_date_obj:
            start_date_obj, end_date_obj = end_date_obj, start_date_obj
            start_date_str = start_date_obj.strftime('%Y-%m-%d')
            end_date_str = end_date_obj.strftime('%Y-%m-%d')
        
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        query = '''
            SELECT * FROM laptop_records 
            WHERE DATE(date_time) BETWEEN %s AND %s AND campus = %s
        '''
        params = [start_date_str, end_date_str, session['campus']]
        
        if direction != 'all':
            query += ' AND direction = %s'
            params.append(direction)
        
        query += ' ORDER BY date_time DESC'
        
        cursor.execute(query, params)
        records = cursor.fetchall()
        
        stats_query = '''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN direction = 'IN' THEN 1 ELSE 0 END) as in_count,
                SUM(CASE WHEN direction = 'OUT' THEN 1 ELSE 0 END) as out_count,
                COUNT(DISTINCT student_names) as unique_students,
                COUNT(DISTINCT serial_number) as unique_laptops
            FROM laptop_records 
            WHERE DATE(date_time) BETWEEN %s AND %s AND campus = %s
        '''
        stats_params = [start_date_str, end_date_str, session['campus']]
        
        if direction != 'all':
            stats_query += ' AND direction = %s'
            stats_params.append(direction)
        
        cursor.execute(stats_query, stats_params)
        stats = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        date_range_days = (end_date_obj - start_date_obj).days + 1
        
        return render_template('calendar_report.html',
                             records=records,
                             stats=stats,
                             direction=direction,
                             start_date=start_date_str,
                             end_date=end_date_str,
                             start_date_obj=start_date_obj,
                             end_date_obj=end_date_obj,
                             date_range_days=date_range_days,
                             today=today,
                             username=session['username'],
                             current_campus=session['campus'])
    except Error as e:
        flash(f'Error generating calendar report: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/cleanup_archived', methods=['POST'])
@login_required
def cleanup_archived():
    try:
        days_to_keep = int(request.form.get('days', 90))
        
        conn = get_db()
        cursor = conn.cursor()
        
        cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).strftime('%Y-%m-%d')
        
        cursor.execute('''
            DELETE FROM archived_laptop_records 
            WHERE date(archived_at) < %s AND campus = %s
        ''', [cutoff_date, session['campus']])
        
        deleted_count = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        
        flash(f'Cleaned up {deleted_count} archived records older than {days_to_keep} days.', 'info')
        return redirect(url_for('archived_records'))
    except Error as e:
        flash(f'Error cleaning up archived records: {str(e)}', 'danger')
        return redirect(url_for('archived_records'))

@app.route('/database_info')
@login_required
def database_info():
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute('SELECT VERSION() as version')
        mysql_version = cursor.fetchone()['version']
        
        cursor.execute('SELECT DATABASE() as db_name')
        db_info = cursor.fetchone()
        
        cursor.execute('''
            SELECT 
                TABLE_NAME as table_name,
                TABLE_ROWS as row_count,
                DATA_LENGTH as data_size,
                INDEX_LENGTH as index_size,
                CREATE_TIME as created
            FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA = DATABASE()
            ORDER BY TABLE_NAME
        ''')
        tables = cursor.fetchall()
        
        table_counts = {}
        for table in tables:
            table_name = table['table_name']
            cursor.execute(f'SELECT COUNT(*) as count FROM `{table_name}`')
            table_counts[table_name] = cursor.fetchone()['count']
        
        config_info = {
            'MYSQL_HOST': app.config['MYSQL_HOST'],
            'MYSQL_PORT': app.config['MYSQL_PORT'],
            'MYSQL_USER': app.config['MYSQL_USER'],
            'MYSQL_POOL_SIZE': app.config['MYSQL_POOL_SIZE'],
            'MYSQL_CHARSET': app.config['MYSQL_CHARSET']
        }
        
        cursor.close()
        conn.close()
        
        return render_template('database_info.html',
                             database_type='MySQL',
                             database_name=db_info['db_name'] if db_info else 'Unknown',
                             mysql_version=mysql_version,
                             tables=tables,
                             table_counts=table_counts,
                             config=config_info,
                             campus=session['campus'],
                             username=session['username'])
    except Error as e:
        flash(f'Error getting database info: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

# ===== ERROR HANDLERS =====

@app.errorhandler(404)
def page_not_found(e):
    try:
        return render_template('404.html'), 404
    except:
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>404 - Page Not Found</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                h1 { color: #dc3545; }
                a { color: #007bff; text-decoration: none; }
            </style>
        </head>
        <body>
            <h1>404 - Page Not Found</h1>
            <p>The page you're looking for could not be found.</p>
            <p><a href="/">Return to Dashboard</a></p>
        </body>
        </html>
        ''', 404

@app.errorhandler(500)
def internal_server_error(e):
    try:
        return render_template('500.html'), 500
    except:
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>500 - Internal Server Error</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                h1 { color: #dc3545; }
                a { color: #007bff; text-decoration: none; }
            </style>
        </head>
        <body>
            <h1>500 - Internal Server Error</h1>
            <p>Something went wrong on our server. Please try again later.</p>
            <p><a href="/">Return to Dashboard</a></p>
        </body>
        </html>
        ''', 500

@app.errorhandler(Error)
def handle_mysql_error(e):
    flash(f'Database error: {str(e)}', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/test')
def test():
    return "Flask is running with MySQL - Simple User System!"

if __name__ == '__main__':
    print("=" * 50)
    print("UR Laptop Tracking System - Simple User Version")
    print("=" * 50)
    print(f"✓ Database: MySQL")
    print(f"✓ Host: {app.config['MYSQL_HOST']}")
    print(f"✓ Database: {app.config['MYSQL_DATABASE']}")
    print(f"✓ User: {app.config['MYSQL_USER']}")
    print("=" * 50)
    print(f"✓ Server starting...")
    print(f"✓ Access at: http://localhost:5000")
    print("=" * 50)
    print("✓ Available user logins:")
    print("  Huye Campus: user_huye / password123")
    print("  Gikondo Campus: user_gikondo / password123")
    print("  Busogo Campus: user_busogo / password123")
    print("  Nyagatare Campus: user_nyagatare / password123")
    print("  Remera Campus: user_remera / password123")
    print("  Nyarugenge Campus: user_nyarugenge / password123")
    print("  Rwamagana Campus: user_rwamagana / password123")
    print("  Rukara Campus: user_rukara / password123")
    print("=" * 50)
    print("✓ Features:")
    print("  - No admin accounts")
    print("  - Each user can only access their campus records")
    print("  - Simple user management")
    print("  - DUPLICATE SERIAL NUMBERS ALLOWED")
    print("=" * 50)
    
    if not os.path.exists('templates'):
        os.makedirs('templates')
        print("✓ Created templates directory")
    
    app.run(debug=True, port=5000, host='0.0.0.0')