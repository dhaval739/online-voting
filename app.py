import os
from flask import Flask, render_template, flash, redirect, url_for, session, request, logging
from flask_mysqldb import MySQL
from wtforms import Form, StringField, IntegerField, TextAreaField, PasswordField, validators, RadioField
from wtforms.fields.html5 import DateField, DateTimeField
from passlib.hash import sha256_crypt
from functools import wraps
from datetime import datetime
import pytz
from werkzeug.utils import secure_filename
from flask import send_from_directory
from werkzeug import SharedDataMiddleware
import ext_finger as sm
import pickle

UPLOAD_FOLDER ="D:/newproj/static/uploads"
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'tif'])
simfin = sm.initialize() 
app = Flask(__name__)

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'beproj'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

mysql = MySQL(app)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html")

    
@app.route('/')
def index():
    return render_template('home.html')

@app.route('/about')
def about():
    return render_template('about.html')


class RegisterForm(Form):
    name = StringField('Name', [validators.Length(min=1, max=50)])
    dob = DateField('DOB',format='%Y-%m-%d')
    aid = IntegerField('Aadhar Number')   
    # eid =  
    password = PasswordField('Password', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Passwords do not match')
    ])
    confirm = PasswordField('Confirm Password')
    


# User Register
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm(request.form)
    if request.method == 'POST' and form.validate():
        name = form.name.data
        aid = form.aid.data
        dob = form.dob.data
        password = sha256_crypt.encrypt(str(form.password.data))
        
        # Create cursor
        cur = mysql.connection.cursor()

        # Execute query
        cur.execute("INSERT INTO voter(vname, aid, dob, pwd) VALUES(%s, %s, %s, %s)", (name,  aid, dob, password))

        # Commit to DB
        mysql.connection.commit()

        # Close connection
        cur.close()

        flash('You are now registered and can log in', 'success')

        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Get Form Fields
        aid = request.form['aid']
        password_candidate = request.form['pwd']


        # Create cursor
        cur = mysql.connection.cursor()

        # Get user by aid
        result = cur.execute("SELECT * FROM voter WHERE aid = %s", [aid])

        if result > 0:
            # Get stored hash
            data = cur.fetchone()
            password = data['pwd']
            username = data['vname']

            # Compare Passwords
            if sha256_crypt.verify(password_candidate, password):
                # Passed
                session['logged_in'] = True
                session['aid'] = aid
                session['username']= username

                flash('You are now logged in', 'success')
                return redirect(url_for('polls'))
            else:
                error = 'Invalid login'
                return render_template('login.html', error=error)
            # Close connection
            cur.close()
        else:
            error = 'AId not found'
            return render_template('login.html', error=error)

    return render_template('login.html')

# Check if user logged in
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('Unauthorized, Please login', 'danger')
            return redirect(url_for('login'))
    return wrap



# Logout
@app.route('/logout')
@is_logged_in
def logout():
    session.clear()
    flash('You are now logged out', 'success')
    return redirect(url_for('login'))





@app.route('/polls')
@is_logged_in
def polls():
    # Create cursor
    cur = mysql.connection.cursor()

    # Get articles
    result = cur.execute("SELECT * FROM poll")

    polls = cur.fetchall()
    nowdt = datetime.now()

    # Close connection
    cur.close()

    if result > 0:
        return render_template('polls.html', polls=polls,nowdt=nowdt)
    else:
        msg = 'No Polls Found'
        return render_template('polls.html', msg=msg)
    

@app.route('/polls/<string:id>/', methods=['GET', 'POST'])
def poll(id):
    #Create cursor
    cur = mysql.connection.cursor()


    if request.method == 'POST':

        ch = request.form['optradio']

        cur.execute("UPDATE candidate SET vote_cnt = vote_cnt+1 WHERE id =%s", [ch])

        # Commit to DB
        mysql.connection.commit()

        #Close connection
        cur.close()

        
        return redirect(url_for('polls'))
    else:

        # Get article
        result = cur.execute("SELECT v.vname, c.id FROM voter v INNER JOIN candidate c on v.aid = c.id where c.poll_id =%s", [id])

        candidates = cur.fetchall()

        #Close connection
        cur.close()
        
        if result > 0:
            return render_template('poll.html', candidates=candidates)
        else:
            msg = 'No Candidates Found'
            return render_template('poll.html', msg=msg)
        






#----------------------------------------------------------------------------

@app.route('/admin/', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        # Get Form Fields
        aaid = request.form['aaid']
        password_candidate = request.form['pwd']

        
        password = '$5$rounds=535000$0YpldUAa2kj8nWL6$Qmjtj68ih20lFQcAKyoLYWkPvtDNef0/2t4hBoz8Gy8'
        username = 'Admin'

        # Compare Passwords and aaid
        if aaid=='12345' and sha256_crypt.verify(password_candidate, password):
            # Passed
            session['is_admin'] = True            
            session['username']= username

            flash('You are now logged in', 'success')
            return redirect(url_for('admin_index'))
        else:
            error = 'Invalid login credentials'
            return render_template('admin_login.html', error=error)
        
    return render_template('admin_login.html')


def is_admin(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'is_admin' in session:            
            return f(*args, **kwargs)
        else:
            flash('Unauthorized, Please login', 'danger')
            return redirect(url_for('admin_login'))
    return wrap


@app.route('/admin/options')
@is_admin
def admin_index():
    session['poll_id'] = '' 
    return render_template('admin_ops.html')

@app.route('/admin/add_users')
@is_admin
def add_users():
    # Create cursor
    cur = mysql.connection.cursor()

    # Get articles
    result = cur.execute("SELECT aid, vname, dob FROM voter where approved = 0")

    voters = cur.fetchall()
    
    # Close connection
    cur.close()

    if result > 0:
        return render_template('add_users.html', voters=voters)
    else:
        msg = 'No Remainig Voter Request'
        return render_template('add_users.html', msg=msg)
    



class pollForm(Form):
    ptitle = StringField('Poll Title', [validators.Length(min=3, max=50)])
    strt = DateTimeField('Starts From',format='%Y-%m-%d %H:%M:%S')
    end = DateTimeField('Ends at',format='%Y-%m-%d %H:%M:%S')

@app.route('/admin/add_poll', methods=['GET', 'POST'])
@is_admin
def add_poll():
    form = pollForm(request.form)
    if request.method == 'POST' and form.validate():
        ptitle = form.ptitle.data
        strt = form.strt.data
        end = form.end.data

        # Create cursor
        cur = mysql.connection.cursor()

        # Execute query
        cur.execute("INSERT INTO poll (poll_title,starts_from, ends_at) VALUES(%s, %s, %s)", (ptitle, strt, end))

        #set poll id
        session['poll_id'] = mysql.connection.insert_id()
        
        # Commit to DB
        mysql.connection.commit()


        # Close connection
        cur.close()

        return redirect(url_for('add_candidates'))

    return render_template('add_poll.html',form=form)

@app.route('/admin/add_candidates', methods=['GET', 'POST'])
@is_admin
def add_candidates():
    pid = session['poll_id']
    # Create cursor
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        # Get Form Field
        aaid = request.form['aaid']
        

        # Get user by aid
        result = cur.execute("SELECT * FROM voter WHERE aid = %s", [aaid])

        if result > 0:
            cur.execute("INSERT INTO candidate (id, poll_id) VALUES(%s, %s)", (aaid, pid))

            # Commit to DB
            mysql.connection.commit()

            # Close connection
            cur.close()

            return redirect(url_for('add_candidates'))

        else:
            error = 'AId not found'
            return render_template('add_candidates.html', error=error)
    
    else:
        result = cur.execute("SELECT v.vname, c.id FROM voter v INNER JOIN candidate c on v.aid = c.id where c.poll_id =%s", [pid])

        candidates = cur.fetchall()

        #Close connection
        cur.close()
        
        if result > 0:
            return render_template('add_candidates.html', candidates=candidates)
        else:
            msg = 'Add Few Candidates'
            return render_template('add_candidates.html', msg=msg)
    





@app.route('/', methods=['GET', 'POST'])
@is_admin
def upload_file():
    if request.method == 'POST':       

        vid = request.form['voter_id']

        #Create cursor
        cur = mysql.connection.cursor()

        cur.execute("UPDATE voter SET approved = 1 WHERE aid =%s", [vid])


        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part','danger')
            return redirect(url_for('add_users'))
        file = request.files['file']

        # if user does not select file, browser also
        # submit a empty part without filename
        if file.filename == '':
            flash('No selected file','danger')
                
            return redirect(url_for('add_users'))
        if file and allowed_file(file.filename):
            
            filename = secure_filename(file.filename)
            #print(filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            fim = "/".join([UPLOAD_FOLDER,filename])
            mint = simfin.ext_finger(fim, 0)
            #print(mint)  
            
            pickle_in = open("dict.pickle","rb")
            try:
                eg_dict = pickle.load(pickle_in)
            except EOFError:
                eg_dict = {}
            
            

            pickle_in.close()


            eg_dict.update({vid:mint})  
            
            pickle_out = open("dict.pickle","wb")
            pickle.dump(eg_dict, pickle_out)
	            pickle_out.close()         
            
            
            #print("abcd")
            #print(vid)

            
            simfin.terminate()

            # Commit to DB
            mysql.connection.commit()

            #Close connection
            cur.close()


            #print("klmn")
            return redirect(url_for('add_users'))

                                    
    return redirect(url_for('add_users'))


@app.route('/admin/read', methods=['GET', 'POST'])
def read_file():
    if request.method == 'POST':
        #eg_dict = {}

        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # if user does not select file, browser also
        # submit a empty part without filename
        if file.filename == '':
            flash('No selected file')
                
            return redirect(request.url)
        if file and allowed_file(file.filename):
            
            filename = secure_filename(file.filename)
            print(filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            fim = "/".join([UPLOAD_FOLDER,filename])
            mint = simfin.ext_finger(fim, 0)
            print(mint)



            
            pickle_in = open("dict.pickle","rb")
            try:
                eg_dict = pickle.load(pickle_in)
                flash()
            except EOFError:
                eg_dict = {}
            
            
            s = simfin.match(mint, eg_dict[1997], 1)
            print(s)
            pickle_in.close()            

            return redirect(url_for('add_users'))
    return render_template('auth2.html')



@app.route('/test', methods=['GET', 'POST'])
def test():
    return render_template('test.html')



if __name__ == '__main__':
    app.secret_key='secret123guesspasswordeasy101'
    app.run(debug=True)

