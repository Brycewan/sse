from flask import Flask, request, redirect, url_for, render_template, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:20010422@localhost:5432/postgres'
app.config['SECRET_KEY'] = 'your_secret_key'
db = SQLAlchemy(app)

# database models
class Users(db.Model):
    username = db.Column(db.String(80), primary_key=True)
    password = db.Column(db.String(80), nullable=False)

class Friendships(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(80), db.ForeignKey('users.username'), nullable=False)
    friend_id = db.Column(db.String(80), db.ForeignKey('users.username'), nullable=False)
    status = db.Column(db.Boolean, default=False)

class FriendRequests(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_username = db.Column(db.String(80), nullable=False)
    receiver_username = db.Column(db.String(80), nullable=False)
    status = db.Column(db.String(20), default='pending')



@app.route('/')
def index():
    # if 'user_id' in session:
    #     user = Users.query.get(session['user_id'])
    #     return render_template('index.html', logged_in=True, username=user.username)
    if 'username' in session:
        return render_template('index.html', logged_in=False, username=session['username'])
    else:
        return render_template('index.html', logged_in=False)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # hashed_password = generate_password_hash(password)
        new_user = Users(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = Users.query.filter_by(username=username).first()
        # if user and check_password_hash(user.password, password):
        if user and user.password == password:
            session['username'] = user.username
            return redirect(url_for('info'))
        else:
            return 'Invalid username or password'
    return render_template('login.html')

@app.route('/info')
def info():
    if 'username' in session:
        username = session['username']
        friend_requests = get_friend_requests(username)
        friends=get_friends(username)
        return render_template('info.html', username=session['username'], friends=friends, friend_requests=friend_requests)
    else:
        return redirect(url_for('login'))
    
def get_friends(username):
    user = Users.query.filter_by(username=username).first()
    if user:
        friend_list = Friendships.query.filter_by(user_id=username, status=True).all()
        return [friend.friend_id for friend in friend_list]
    return []

def get_friend_requests(username):
    user = Users.query.filter_by(username=username).first()
    if user:
        return FriendRequests.query.filter_by(receiver_username=username).all()
    return []

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))

@app.route('/add_friend', methods=['POST'])
def add_friend():
    if 'username' in session:
        sender_username = session['username']
        receiver_username = request.form['friend_username']
        friend = Users.query.filter_by(username=receiver_username).first()
        if friend:
            # check if the friendship already exists
            existing_friendship = Friendships.query.filter_by(user_id=sender_username, friend_id=receiver_username, status=True).first()
            existing_request = FriendRequests.query.filter_by(sender_username=sender_username, receiver_username=receiver_username).first()
            if existing_friendship:
                print(Friendships.user_id, Friendships.friend_id, sender_username, receiver_username, Friendships.status)
                return 'Already friends'
            elif existing_request:
                return 'Friend request already sent'
            else:
                # create a friend request
                friend_request = FriendRequests(sender_username=sender_username, receiver_username=receiver_username)
                db.session.add(friend_request)
                db.session.commit()
                return redirect(url_for('info'))
        else:
            return 'User not found'
    else:
        return redirect(url_for('login'))

    
@app.route('/accept_request/<int:request_id>')
def accept_request(request_id):
    # return 'Accept request'
    friend_request = FriendRequests.query.get(request_id)
    if friend_request:
        sender_username = friend_request.sender_username
        receiver_username = friend_request.receiver_username
        # create two friendships
        friendship1 = Friendships(user_id=sender_username, friend_id=receiver_username, status=True)
        friendship2 = Friendships(user_id=receiver_username, friend_id=sender_username, status=True)
        # delete the friend request and add the friendships
        db.session.delete(friend_request)
        db.session.add(friendship1)
        db.session.add(friendship2)
        db.session.commit()
        return redirect(url_for('info'))
    else:
        return 'Friend request not found'

@app.route('/reject_request/<int:request_id>')
def reject_request(request_id):
    friend_request = FriendRequests.query.get(request_id)
    if friend_request:
        db.session.delete(friend_request)
        db.session.commit()
        return redirect(url_for('info'))
    else:
        return 'Friend request not found'


if __name__ == "__main__":
    app.run(debug=True)